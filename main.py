import getpass
import os
from vector_store import ProtocolsVectorStore

from langgraph.graph import MessagesState, StateGraph
from langchain_core.tools import tool

from langchain_core.messages import SystemMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import END
from langgraph.prebuilt import ToolNode, tools_condition
from collections import defaultdict
from langgraph.checkpoint.memory import MemorySaver

import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from check_user_position import query_all_positions


if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

from langchain.chat_models import init_chat_model

llm = init_chat_model("gpt-4o-mini", model_provider="openai")

vector_store = ProtocolsVectorStore()

graph_builder = StateGraph(MessagesState)


@tool(response_format="content_and_artifact")
def check_user_position(user_address: str):
    """
    Use this tool if a user wants to check or withdraw his/her DeFi positions (e.g., staked tokens, balances, rewards).
    Returns (serialized_info, raw_positions).
    """
    user_positions = query_all_positions(user_address)
    serialized = "User Positions:\n" + "\n".join(str(pos) for pos in user_positions)
    return serialized, user_positions


@tool(response_format="content_and_artifact")
def retrieve_defi_info(query: str):
    """
    Use this tool to retrieve relevant DeFi investment strategy information
    from the vector store based on the user's query (e.g., desired APR,
    specific protocol name, or general DeFi strategies). 
    If user wants to stake specific token on a protocol, use this tool to fetch the strategy details.

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
    """Generate tool call for tool-calling or respond."""
    
    # Check user address
    user_context = None
    for message in state["messages"]:
        if hasattr(message, "additional_kwargs") and "user_address" in message.additional_kwargs:
            user_context = f"""
            Current user address: {message.additional_kwargs['user_address']}
            IMPORTANT: Always use check_user_position tool when the question is about user's positions, rewards, or tokens.
            Don't rely on previous responses, always get fresh data.
            """
            break
    
    if user_context:
        state["messages"].insert(0, SystemMessage(content=user_context))
    
    llm_with_tools = llm.bind_tools([retrieve_defi_info, check_user_position])
    response = llm_with_tools.invoke(state["messages"])
    
    # If LLM decide not to use tools, format the response as a JSON string and respond directly
    if response.tool_calls == []:
        formatted_content = json.dumps({
            "LLM_response": response.content,
            "type": "PURE_STRING_RESPONSE",
            "strategies": []
        })
        response.content = formatted_content
    
    return {"messages": [response]}


# Step 2: Execute the retrieval.
tools = ToolNode([retrieve_defi_info, check_user_position])

# Step 3: Generate a response using the retrieved content.
def generate(state: MessagesState):
    """Generate answer."""
    # collect tool messages by tool name
    tool_messages_by_name = defaultdict(list)
    for message in reversed(state["messages"]):
        if message.type == "tool":
            tool_messages_by_name[message.name].append(message)
        else:
            break

    # compose system prompts based on different tool messages
    system_prompts = []

    if "retrieve_defi_info" in tool_messages_by_name:
        retrieve_contents = "\n\n".join(
            m.content for m in tool_messages_by_name["retrieve_defi_info"]
        )
        system_prompts.append(
            "You have retrieved some DeFi strategy info which we offer for users to stake or yield:\n"
            f"{retrieve_contents}\n"
            """Consider these strategies when answering the user's question.\n 
            In this scenario, the type would be "EXECUTE_TRANSACTION"
            """
        )

    if "check_user_position" in tool_messages_by_name:
        pos_contents = "\n\n".join(
            m.content for m in tool_messages_by_name["check_user_position"]
        )
        system_prompts.append(
            "You have retrieved the user's staked position details:\n"
            f"{pos_contents}\n"
            "When the user inquires about their staked tokens, summarize their positions concisely.\n"
            "- If the user only wants to check their positions, set the response type to 'PURE_STRING_RESPONSE'.\n"
            "- If the user intends to withdraw, set the response type to 'WITHDRAW_POSITION' and provide all the strategies where the user has deposited funds."
        )

    # Combine system prompts
    combined_system_prompt = (
        "You are an assistant for DeFi yeild & staking related question-answering tasks.\n\n"
        + "\n".join(system_prompts)
    )
    combined_system_prompt += (
        "\n"
        "Now provide a response accordingly. If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the answer concise.\n"
        """
        I want your answer strictly follow this JSON format:
            1. LLM_response: A concise answer for the user's question about yields or protocols. This is the response directly showing to the user.\n"
            2. type: "EXECUTE_TRANSACTION" or "PURE_STRING_RESPONSE" or "WITHDRAW_POSITION" based on the information above.\n"
            3. strategies: A list of strategies (Can be empty if not applicable), each with the following fields:
                - label: A short name for the strategy.
                - description: A brief description of the strategy.
                - strategyID: The unique ID for the strategy.
                - stakeToken: The token address for staking 

            For example:
            ---
            {{
                "LLM_response": "Here are some staking protocols with at least 5% APR for you to consider: \n
                    1. Earn 6% APR by staking in ether.fi, a non-custodial staking service.\n
                    2. Earn 5% APR with Ethena, a stable LSD protocol for Ethereum collateral.\n",
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
    )

    conversation_messages = [
        message
        for message in state["messages"]
        if message.type in ("human", "system")
        or (message.type == "ai" and not message.tool_calls)
    ]
    prompt = [SystemMessage(combined_system_prompt)] + conversation_messages

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

graph = graph_builder.compile()

# Specify an ID for the thread
config = {"configurable": {"thread_id": "abc123"}}

# --- FastAPI Backend ---
app = FastAPI()


# Data type of Request and Response
class RequestBody(BaseModel):
    userInput: str
    userAddress: str = "0x0000000000000000000000000000000000000000"  # 預設地址


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
    # init user message
    user_message = {
        "role": "user", 
        "content": request.userInput,
        "additional_kwargs": {"user_address": request.userAddress}
    }
    final_message = None
    
    # Run the graph
    for step in graph.stream(
        {"messages": [user_message]},
        stream_mode="values",
        config=config,
    ):
        final_message = step["messages"][-1]
    
    if final_message is None:
        raise HTTPException(status_code=500, detail="No response from LLM.")

    try:
        # Parse the JSON response
        response_dict = json.loads(final_message.content)
        return ResponseBody(**response_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON response from LLM: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # input_message = "Recommend some staking protocols for me, at least 5% APR."
    # # input_message = "hi, how are you?"
    # for step in graph.stream(
    #     {"messages": [{"role": "user", "content": input_message}]},
    #     stream_mode="values",
    #     config=config,
    # ):
    #     step["messages"][-1].pretty_print()
        

    # input_message = "what I just ask you?"
    # for step in graph.stream(    #     {"messages": [{"role": "user", "content": input_message}]},    #     stream_mode="values",    #     config=config,    # ):    #     step["messages"][-1].pretty_print()
