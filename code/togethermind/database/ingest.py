import os
import json
import logging
from shared.embeddings import ChromaVectorStore
from shared.config import DATASETS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TogetherIngest")

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Helper to split text into overlapping chunks"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def ingest_all_knowledge():
    blog_file = os.path.join(DATASETS_DIR, "together_fund_blog_posts.json")
    essays_file = os.path.join(DATASETS_DIR, "paul_graham_essays.json")
    
    # Initialize Vector DB
    store = ChromaVectorStore(collection_name="operator_knowledge")
    store.reset_collection() # Clear old data
    
    documents = []
    metadatas = []
    ids = []
    
    # 1. Ingest Together Fund Blogs
    if os.path.exists(blog_file):
        logger.info("Ingesting Together Fund blog posts...")
        with open(blog_file, "r") as f:
            blogs = json.load(f)
            
        for b_idx, blog in enumerate(blogs):
            title = blog.get("title", "Together Fund Blog")
            url = blog.get("url", "https://together.fund")
            content = blog.get("content", "")
            author = blog.get("author", "Together Fund GP")
            date = blog.get("date", "2024-2025")
            
            chunks = chunk_text(content, chunk_size=800, overlap=150)
            for c_idx, chunk in enumerate(chunks):
                doc_id = f"tf_blog_{b_idx}_chunk_{c_idx}"
                documents.append(chunk)
                metadatas.append({
                    "title": title,
                    "url": url,
                    "author": author,
                    "date": date,
                    "source": "together_fund"
                })
                ids.append(doc_id)
    else:
        logger.warning(f"Together Fund blog posts file not found at: {blog_file}")

    # 2. Ingest Paul Graham Essays
    if os.path.exists(essays_file):
        logger.info("Ingesting Paul Graham essays...")
        with open(essays_file, "r") as f:
            essays = json.load(f)
            
        for e_idx, essay in enumerate(essays):
            title = essay.get("title", "Paul Graham Essay")
            url = essay.get("url", "http://paulgraham.com")
            content = essay.get("content", "")
            author = essay.get("author", "Paul Graham")
            date = essay.get("date", "Unknown")
            
            chunks = chunk_text(content, chunk_size=1000, overlap=200)
            for c_idx, chunk in enumerate(chunks):
                doc_id = f"pg_essay_{e_idx}_chunk_{c_idx}"
                documents.append(chunk)
                metadatas.append({
                    "title": title,
                    "url": url,
                    "author": author,
                    "date": date,
                    "source": "paulgraham.com"
                })
                ids.append(doc_id)
    else:
        logger.warning(f"Paul Graham essays file not found at: {essays_file}")

    # Load everything into the vector database
    if documents:
        store.add_documents(documents, metadatas, ids)
        logger.info(f"Successfully ingested {len(documents)} total knowledge chunks into ChromaDB.")
    else:
        logger.error("No documents found to ingest.")

if __name__ == "__main__":
    ingest_all_knowledge()
