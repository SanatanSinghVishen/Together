import os
import chromadb
import logging
from typing import List, Dict, Any, Optional
from chromadb.utils import embedding_functions

from shared.config import CHROMA_DB_DIR

logger = logging.getLogger("TogetherEmbeddings")

# Lazy initialization of the Vector Store
class ChromaVectorStore:
    def __init__(self, collection_name: str, persist_directory: str = None):
        # Resolve DB persistence directory
        if persist_directory is None:
            self.persist_directory = CHROMA_DB_DIR
        else:
            self.persist_directory = persist_directory
            
        self.collection_name = collection_name
        
        # Initialize local persistent Chroma client
        os.makedirs(self.persist_directory, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Setup local sentence transformer embedding function (runs 100% locally and costs $0.00 credits!)
        # ChromaDB automatically downloads this lightweight model (all-MiniLM-L6-v2) on first run
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        # Get or create collection using the local embedding function
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )
        logger.info(f"Initialized ChromaVectorStore for collection '{collection_name}' at {self.persist_directory} using local embeddings.")

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """Adds documents to ChromaDB (Chroma automatically computes embeddings locally)"""
        if not documents:
            return
            
        logger.info(f"Adding {len(documents)} documents to '{self.collection_name}' (Chroma computing local embeddings)...")
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info("Local Ingestion complete.")

    def search(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Searches vector database for matches (Chroma computes query embedding locally)"""
        logger.info(f"Searching collection '{self.collection_name}' for: '{query_text}'")
        
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Format the query output to a cleaner structure
        formatted_results = []
        if results and 'documents' in results and results['documents']:
            docs = results['documents'][0]
            metas = results['metadatas'][0] if 'metadatas' in results and results['metadatas'] else [{}] * len(docs)
            ids = results['ids'][0]
            distances = results['distances'][0] if 'distances' in results and results['distances'] else [0.0] * len(docs)
            
            for doc, meta, doc_id, dist in zip(docs, metas, ids, distances):
                # Cosine distance to similarity conversion
                relevance = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                formatted_results.append({
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta,
                    "relevance_score": relevance
                })
                
        return formatted_results

    def reset_collection(self):
        """Clears all records in the collection"""
        try:
            self.chroma_client.delete_collection(self.collection_name)
        except Exception:
            pass # ignore if collection didn't exist
            
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function
        )
        logger.info(f"Reset collection '{self.collection_name}' complete.")
