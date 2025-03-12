import getpass
import os
from langchain_openai import OpenAIEmbeddings
from vector_store import ProtocolsVectorStore

from langgraph.graph import MessagesState, StateGraph
from langchain_core.tools import tool

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import END
from langgraph.prebuilt import ToolNode, tools_condition


import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

from langchain.chat_models import init_chat_model

llm = init_chat_model("gpt-4o-mini", model_provider="openai")

vector_store = ProtocolsVectorStore()


graph_builder = StateGraph(MessagesState)


@tool(response_format="content_and_artifact")
def retrieve(query: str):
    """
    Use this tool to retrieve relevant DeFi investment strategy information
    from the vector store based on the user's query (e.g., desired APR,
    specific protocol name, or general DeFi strategies).

    When called, it performs a similarity search on the underlying vector
    database (vector_store) and returns:

    1. A serialized text block (content) that includes metadata and a summary
       of each retrieved document. This is useful for LLM responses where you
       want to display or reason about the content in plain text.

    2. The raw document objects (artifact) themselves, allowing further
       programmatic inspection or specialized handling.

    Example usage:
    - If a user asks: "What yield strategies are available for stablecoins?",
      use this tool to fetch relevant documents about stablecoin staking or
      lending protocols and then incorporate those details into your response.
    """
    retrieved_docs = vector_store.similarity_search(query)
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\n" f"Content: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs


# Step 1: Generate an AIMessage that may include a tool-call to be sent.
def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    llm_with_tools = llm.bind_tools([retrieve])
    response = llm_with_tools.invoke(state["messages"])
    # MessagesState appends messages to state instead of overwriting
    return {"messages": [response]}


# Step 2: Execute the retrieval.
tools = ToolNode([retrieve])


# Step 3: Generate a response using the retrieved content.
def generate(state: MessagesState):
    """Generate answer."""
    # Get generated ToolMessages
    recent_tool_messages = []
    for message in reversed(state["messages"]):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    # Format into prompt
    docs_content = "\n\n".join(doc.content for doc in tool_messages)
    system_message_content = (
        "You are an assistant for question-answering tasks. "
        """
        I want your answer strictly follow this JSON format:
            1. LLM_response: A short description text with recommended options and ask for the user's choice.
            2. type: always be "EXECUTE_TRANSACTION"
            3. A list of strategies, each with the following fields:
                - label: A short name for the strategy.
                - description: A brief description of the strategy.
                - strategyID: The unique ID for the strategy.
                - stakeToken: The token address for staking 

            For example:
            ---
            {{
                "LLM_response": "Here are some staking protocols with at least 5% APR for you to consider: 
                    1. Earn 6% APR by staking in ether.fi, a non-custodial staking service.
                    2. Earn 5% APR with Ethena, a stable LSD protocol for Ethereum collateral.",
                "type": "EXECUTE_TRANSACTION",
                "strategies": [
                        {
                            "label": "ether.fi",
                            "description": "Earn 6% APR by staking in ether.fi, a non-custodial staking service.",
                            "strategyID": 1,
                            "stakeToken": "0x........"
                        },
                        {
                            "label": "Ethena",
                            "description": "Earn 5% APR with Ethena, a stable LSD protocol for Ethereum collateral.",
                            "strategyID": 2,
                            "stakeToken": "0x........""
                        }
                ]
            }}
            ---
        """
        "Use the following pieces of retrieved context to answer "
        "the question. If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the "
        "answer concise."
        "\n\n"
        f"{docs_content}"
    )
    conversation_messages = [
        message
        for message in state["messages"]
        if message.type in ("human", "system")
        or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(system_message_content)] + conversation_messages

    # Run
    response = llm.invoke(prompt)
    return {"messages": [response]}


graph_builder.add_node(query_or_respond)
graph_builder.add_node(tools)
graph_builder.add_node(generate)

graph_builder.set_entry_point("query_or_respond")
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"},
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = graph_builder.compile(checkpointer=memory)

from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png()))

# Specify an ID for the thread
config = {"configurable": {"thread_id": "abc123"}}

# --- 定義 FastAPI 後端 ---
app = FastAPI()


# Request 與 Response 的資料模型
class RequestBody(BaseModel):
    userInput: str


class Strategy(BaseModel):
    label: str
    description: str
    strategyID: int
    stakeToken: str


class ResponseBody(BaseModel):
    LLM_response: str
    type: str
    strategies: list[Strategy]


@app.get("/", response_model=str)
async def root():
    return "Hello World! This is the root endpoint."

@app.post("/userQuery", response_model=ResponseBody)
async def userQuery(request: RequestBody):
    # 建立初始對話訊息
    user_message = {"role": "user", "content": request.userInput}
    final_message = None
    
    # 執行 graph.stream 並獲取最終回應
    for step in graph.stream(
        {"messages": [user_message]},
        stream_mode="values",
        config=config,
    ):
        final_message = step["messages"][-1]
    
    if final_message is None:
        raise HTTPException(status_code=500, detail="No response from LLM.")

    try:
        # 嘗試解析 LLM 返回的 JSON 字符串
        response_dict = json.loads(final_message.content)
        return ResponseBody(**response_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from LLM: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    
    # input_message = "Recommend some staking protocols for me, at least 5% APR."

    # for step in graph.stream(
    #     {"messages": [{"role": "user", "content": input_message}]},
    #     stream_mode="values",
    #     config=config,
    # ):
    #     step["messages"][-1].pretty_print()
        

    # input_message = "what I just ask you?"

    # for step in graph.stream(
    #     {"messages": [{"role": "user", "content": input_message}]},
    #     stream_mode="values",
    #     config=config,
    # ):
    #     step["messages"][-1].pretty_print()
