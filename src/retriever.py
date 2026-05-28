import os
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any

# 1. setup db folder in data dir
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")

# 2. init chromadb client
chroma_client = chromadb.PersistentClient(path=DB_PATH)

# 3. set up fast embedding model
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def store_document_chunks(doc_id: str, chunks: List[str], document_type: str):
    """
    Takes the structured chunks from Segment 1, generates vector embeddings, 
    and saves them into ChromaDB with explicit tracking metadata for strict grounding.
    """
    # make or load doc collection
    collection = chroma_client.get_or_create_collection(
        name="legal_documents", 
        embedding_function=embedding_func
    )
    
    ids = []
    metadatas = []
    documents = []
    
    if not chunks:
        print(f"[Vector DB] Warning: No chunks found to index for document '{doc_id}'.")
        return
        
    # loop chunks to prep for db insert
    for idx, chunk in enumerate(chunks):
        # make unique id for chunk
        chunk_unique_id = f"{doc_id}_chunk_{idx}"
        ids.append(chunk_unique_id)
        documents.append(chunk)
        
        # metadata is super important for evidence tracking
        metadatas.append({
            "source_document_id": doc_id,
            "document_type": document_type,
            "chunk_index": idx
        })
        
    # bulk insert chunks into local db
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    print(f"[Vector DB] Successfully indexed {len(chunks)} chunks under ID '{doc_id}'.")

def retrieve_relevant_evidence(query: str, n_results: int = 7, document_id: str = None) -> List[Dict[str, Any]]:
    """
    Performs a semantic search on your database to pull out the exact chunks 
    most relevant to a given prompt or query.
    """
    collection = chroma_client.get_or_create_collection(
        name="legal_documents", 
        embedding_function=embedding_func
    )
    
    # make query args
    query_args = {
        "query_texts": [query],
        "n_results": n_results
    }
    
    # filter by doc id if provided
    if document_id:
        query_args["where"] = {"source_document_id": document_id}
    
    # query db using semantic search
    results = collection.query(**query_args)
    
    # flatten chromadb output into simple list
    formatted_evidence = []
    if results['documents'] and results['documents'][0]:
        for i in range(len(results['documents'][0])):
            formatted_evidence.append({
                "id": results['ids'][0][i],
                "text": results['documents'][0][i],
                "metadata": results['metadatas'][0][i]
            })
            
    return formatted_evidence