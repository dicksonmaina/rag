#!/usr/bin/env python3
"""
Windows Local RAG System - LangChain + Redis + ChromaDB
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Vector Store: ChromaDB
- LLM: Ollama
- Cache: Redis
"""

import os
import sys
import hashlib
import json
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "documents"
DB_DIR = BASE_DIR / "chroma_db"

# Redis config
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_DB = 0

# Ollama config
OLLAMA_BASE_URL = "http://localhost:11434"
LLM_MODEL = "qwen2:0.5b"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking config
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def get_redis():
    try:
        import redis
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    except Exception as e:
        print(f"[WARN] Redis not available: {e}")
        return None


def get_ollama_llm():
    from langchain_ollama import OllamaLLM
    return OllamaLLM(base_url=OLLAMA_BASE_URL, model=LLM_MODEL)


def get_ollama_embeddings():
    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(base_url=OLLAMA_BASE_URL, model=LLM_MODEL)


def get_hf_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def get_vector_store():
    from langchain_chroma import Chroma
    from langchain_core.embeddings import Embeddings
    
    embeddings = get_hf_embeddings()
    
    return Chroma(
        persist_directory=str(DB_DIR),
        embedding_function=embeddings,
        collection_name="rag_documents",
        collection_metadata={"hnsw:space": "cosine"}
    )


def load_documents():
    from langchain_community.document_loaders import TextLoader
    from langchain_core.documents import Document
    
    docs = []
    for path in DOCS_DIR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".txt", ".md", ".csv", ".json"}:
            try:
                loader = TextLoader(str(path), encoding="utf-8")
                loaded = loader.load()
                for doc in loaded:
                    doc.metadata["source"] = str(path.relative_to(DOCS_DIR))
                docs.extend(loaded)
            except Exception as e:
                print(f"[WARN] Failed to load {path}: {e}")
    return docs


def split_documents(docs):
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    return splitter.split_documents(docs)


def index_documents(vector_store, chunks):
    redis = get_redis()
    new_count = 0
    
    for chunk in chunks:
        content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()
        
        if redis:
            cached = redis.get(f"rag:chunk:{content_hash}")
            if cached:
                continue
        
        try:
            vector_store.add_documents([chunk])
            new_count += 1
            
            if redis:
                redis.setex(f"rag:chunk:{content_hash}", 86400, "1")
        except Exception as e:
            print(f"[WARN] Failed to index chunk: {e}")
    
    if redis:
        redis.set("rag:last_index_time", str(__import__('time').time()))
    
    print(f"[INFO] Indexed {new_count} new chunks.")


def retrieve(vector_store, query, top_k=5):
    return vector_store.similarity_search_with_score(query, k=top_k)


def build_prompt(query, context_docs):
    context = "\n\n".join([doc.page_content for doc in context_docs])
    prompt = (
        "You are a helpful assistant. Use the following context to answer the question.\n"
        "If the answer is not in the context, say you don't know.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
    )
    return prompt


def generate(llm, prompt):
    try:
        response = llm.invoke(prompt)
        return response if isinstance(response, str) else str(response)
    except Exception as e:
        return f"[ERROR] Generation failed: {e}"


def cmd_index():
    print("[INFO] Loading documents...")
    docs = load_documents()
    if not docs:
        print("[INFO] No documents found in documents/ folder.")
        return
    
    print(f"[INFO] Loaded {len(docs)} documents.")
    print("[INFO] Splitting documents...")
    chunks = split_documents(docs)
    print(f"[INFO] Created {len(chunks)} chunks.")
    
    print("[INFO] Indexing into ChromaDB...")
    vector_store = get_vector_store()
    index_documents(vector_store, chunks)
    print("[INFO] Indexing complete.")


def cmd_query(query):
    vector_store = get_vector_store()
    
    try:
        count = vector_store._collection.count()
    except Exception:
        count = 0
    
    if count == 0:
        print("[INFO] No documents indexed. Run 'index' first.")
        return
    
    print(f"[INFO] Retrieving relevant chunks...")
    results = retrieve(vector_store, query)
    
    if not results:
        print("[INFO] No relevant chunks found.")
        return
    
    context_docs = [doc for doc, score in results]
    
    print(f"[INFO] Retrieved {len(context_docs)} chunks:")
    for i, (doc, score) in enumerate(results, 1):
        print(f"  {i}. {doc.metadata.get('source', 'unknown')} (score={score:.4f})")
    
    prompt = build_prompt(query, context_docs)
    print("\n[INFO] Generating answer...")
    
    llm = get_ollama_llm()
    answer = generate(llm, prompt)
    
    print(f"\nAnswer:\n{answer}")


def cmd_serve():
    print("[INFO] Starting RAG interactive mode...")
    vector_store = get_vector_store()
    
    try:
        count = vector_store._collection.count()
    except Exception:
        count = 0
    
    print(f"[INFO] Indexed chunks: {count}")
    print("[INFO] Type 'exit' to quit.")
    
    llm = get_ollama_llm()
    
    while True:
        try:
            query = input("\nQuery> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not query or query.lower() in {"exit", "quit"}:
            break
        
        results = retrieve(vector_store, query)
        if not results:
            print("[INFO] No relevant chunks found.")
            continue
        
        context_docs = [doc for doc, score in results]
        prompt = build_prompt(query, context_docs)
        answer = generate(llm, prompt)
        print(f"\nAnswer:\n{answer}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python langchain_rag.py <index|query|serve> [query_text]")
        sys.exit(1)
    
    cmd = sys.argv[1].lower()
    if cmd == "index":
        cmd_index()
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: python langchain_rag.py query <your question>")
            sys.exit(1)
        cmd_query(" ".join(sys.argv[2:]))
    elif cmd == "serve":
        cmd_serve()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
