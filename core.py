from dotenv import load_dotenv
import re
import json
from typing import List
load_dotenv()

from typing import Any, Dict, List

from langchain import hub
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.prompts.chat import MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.retrieval import create_retrieval_chain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from vector_store import ProtocolsVectorStore

from callbacks import AgentCallbackHandler

def run_llm(query: str, chat_history: List[Dict[str, Any]] = []):
    vector_store = ProtocolsVectorStore()

    chat = ChatOpenAI(
        model_name="gpt-4o-mini", 
        verbose=True, 
        temperature=0,
        callbacks=[AgentCallbackHandler()],
    )

    rephrase_prompt = hub.pull("langchain-ai/chat-langchain-rephrase")

    retrieval_qa_chat_prompt = hub.pull("langchain-ai/retrieval-qa-chat")

    # Get original messages（A list）
    original_messages = retrieval_qa_chat_prompt.messages

    # Add a new system prompt
    new_system_prompt = SystemMessagePromptTemplate.from_template(
        """ 
        I want your answer strictly follow this format:
        1. A short description text with recommended options
        2. Followed by JSON that includes an array named “protocols” 

        For example:
        ---
        {{A short description text}}:
        1. Earn 7% APR by staking in XX protocol. 
        2. Earn 13% APR by providing liquidity in OO finance.
        {{
        "protocols": ["XX protocol", "OO finance"]
        }}
        ---

        """
    )

    # Insert this prompt to the front of `messages`
    updated_messages = [new_system_prompt] + original_messages

    # Create a new ChatPromptTemplate including the new messages
    retrieval_qa_chat_prompt = ChatPromptTemplate(messages=updated_messages)
    stuff_documents_chain = create_stuff_documents_chain(chat, retrieval_qa_chat_prompt)

    history_aware_retriever = create_history_aware_retriever(
        llm=chat, retriever=vector_store.as_retriever(), prompt=rephrase_prompt
    )
    qa = create_retrieval_chain(
        retriever=history_aware_retriever, combine_docs_chain=stuff_documents_chain
    )

    result = qa.invoke(input={"input": query, "chat_history": chat_history})
    formatted_answer = extract_protocols(result["answer"])
    result["answer"] = formatted_answer[0]
    result["protocols"] = formatted_answer[1]
    return result


def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


from typing import List, Tuple
import re
import json


def extract_protocols(text: str) -> Tuple[str, List[str]]:
    """
    Extract description text and protocols array from input text
    Args:
        text: String containing description and JSON with protocols array
    Returns:
        Tuple of (description_text, protocols_list)
    """
    try:
        # Find JSON block using regex
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            return text.strip(), []

        # Split text into description and JSON
        description = text[: json_match.start()].strip()
        json_str = json_match.group(0)

        # Parse JSON and extract protocols
        data = json.loads(json_str)
        protocols = data.get("protocols", [])

        return description, protocols

    except (json.JSONDecodeError, AttributeError):
        return text.strip(), []


# if __name__ == "__main__":
# run_llm(
#     query="Recommend some staking protocols for me, at least 5% APR.",
#     chat_history=[],
# )

#     input = """
#     According to your preference, we found the following staking protocols with at least 5% APR:
# 1. Earn 6% APR by staking in ether.fi, a non-custodial staking service with operator diversification.
# 2. Earn 5% APR by staking in Ethena, a stable LSD protocol enabling yield from Ethereum collateral.
# 3. Earn 7.5% APR by using Babylon, a restaking platform that allows staking across multiple strategies.
# 4. Earn 8% APR by restaking in EigenLayer, which allows stakers to compound ETH rewards across multiple services.
# 5. Earn 10% APR by participating in Pendle, a yield-trading protocol that splits yield and principal tokens.

# {
# "protocols": ["ether.fi", "Ethena", "Babylon", "EigenLayer", "Pendle"]
# }
# """
#     result = extract_protocols(input)
#     print(result[0])
#     print("*"*10)
#     print(result[1])
