import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from vector_store import ProtocolsVectorStore
import json
from langchain.docstore.document import Document


def ingest_json() -> None:
    vector_store = ProtocolsVectorStore()

    with open("protocols_data.json", "r") as f:
        data = json.load(f)  # data: List[Dict]
        print(data)

    try:
        documents = []
        for record in data:
            # 將 record 轉成文本，例如 key-value pair 的格式
            text_content = "\n".join([f"{k}: {v}" for k, v in record.items()])

            # 假設我們把整筆 record 當成一個 chunk
            doc = Document(
                page_content=text_content,
                metadata={
                    "category": record["category"],
                },  
            )
            documents.append(doc)

        print(f"Starting clear all old docs in Pinecone vectorstore")
        vector_store.delete_all_documents()

        print(f"Starting insert {len(documents)} to Pinecone vectorstore")
        vector_store.add_documents(documents)
        
        print("****** Successfully added to Pinecone vectorstore ******")

    except Exception as e:
        print(f"Error during document processing: {str(e)}")


if __name__ == "__main__":
    ingest_json()
