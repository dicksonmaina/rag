#!/usr/bin/env python3
"""
Enterprise RAG System with FastAPI Server
Supports multiple embedding models, knowledge base management, and tool integration.
"""

import os
import sys
import json
import time
import uuid
import hashlib
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from collections import defaultdict

# FastAPI and server imports
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# RAG imports
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document

# System imports
import subprocess
import psutil
import platform

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "documents"
KB_DIR = BASE_DIR / "knowledge_base"
DB_DIR = BASE_DIR / "chroma_db"
CONFIG_FILE = BASE_DIR / "config.json"
HISTORY_FILE = BASE_DIR / "conversation_history.json"
INDEXED_FILES_TRACKER = BASE_DIR / "indexed_files.json"

# Default config
DEFAULT_CONFIG = {
    "llm_model": "qwen2:0.5b",
    "embedding_models": {
        "sentence_transformers": "all-MiniLM-L6-v2",
        "nomic": "nomic-embed-text"
    },
    "default_embedding": "nomic",
    "chunk_size": 500,
    "chunk_overlap": 50,
    "top_k": 5,
    "collection_name": "enterprise_rag"
}

# Ensure directories exist
DOCS_DIR.mkdir(parents=True, exist_ok=True)
KB_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)


class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load_config()
    
    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                self.config.update(saved)
    
    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save_config()


config = ConfigManager()


class ConversationMemory:
    def __init__(self, max_history=50):
        self.history = []
        self.max_history = max_history
        self.load_history()
    
    def load_history(self):
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r') as f:
                self.history = json.load(f)
    
    def save_history(self):
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history[-self.max_history:], f, indent=2)
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.history.append(message)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.save_history()
    
    def get_context(self, last_n=5):
        return self.history[-last_n:] if self.history else []
    
    def clear(self):
        self.history = []
        self.save_history()


class KnowledgeBase:
    def __init__(self):
        self.documents = {}
        self.metadata = {}
        self.load_metadata()
    
    def load_metadata(self):
        meta_file = KB_DIR / "metadata.json"
        if meta_file.exists():
            with open(meta_file, 'r') as f:
                data = json.load(f)
                self.metadata = data.get("documents", {})
    
    def save_metadata(self):
        meta_file = KB_DIR / "metadata.json"
        with open(meta_file, 'w') as f:
            json.dump({"documents": self.metadata}, f, indent=2)
    
    def add_document(self, doc_id: str, name: str, content: str, doc_type: str, tags: List[str] = None):
        self.metadata[doc_id] = {
            "name": name,
            "type": doc_type,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "size": len(content)
        }
        self.save_metadata()
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        return self.metadata.get(doc_id)
    
    def list_documents(self, tag: str = None) -> List[Dict]:
        docs = []
        for doc_id, meta in self.metadata.items():
            if tag and tag not in meta.get("tags", []):
                continue
            docs.append({"id": doc_id, **meta})
        return docs
    
    def delete_document(self, doc_id: str):
        if doc_id in self.metadata:
            del self.metadata[doc_id]
            self.save_metadata()


class ToolIntegration:
    def __init__(self):
        self.available_tools = {
            "file_read": self.file_read,
            "file_write": self.file_write,
            "file_edit": self.file_edit,
            "file_list": self.file_list,
            "directory_list": self.directory_list,
            "execute_command": self.execute_command,
            "system_info": self.system_info,
            "web_search": self.web_search,
            "web_scrape": self.web_scrape
        }
    
    def get_available_tools(self) -> List[Dict]:
        return [
            {"name": name, "description": func.__doc__ or name}
            for name, func in self.available_tools.items()
        ]
    
    def execute_tool(self, tool_name: str, params: Dict) -> Any:
        if tool_name not in self.available_tools:
            raise ValueError(f"Unknown tool: {tool_name}")
        return self.available_tools[tool_name](**params)
    
    def file_read(self, path: str) -> str:
        """Read a file from the filesystem"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    
    def file_write(self, path: str, content: str) -> str:
        """Write content to a file"""
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
    
    def file_edit(self, path: str, old_text: str, new_text: str) -> str:
        """Edit a file by replacing old text with new text"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if old_text not in content:
                return "Error: old_text not found in file"
            content = content.replace(old_text, new_text)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {e}"
    
    def file_list(self, path: str = ".") -> List[str]:
        """List files in a directory"""
        try:
            return os.listdir(path)
        except Exception as e:
            return [f"Error listing files: {e}"]
    
    def directory_list(self, path: str = ".") -> List[Dict]:
        """List directories with details"""
        try:
            items = []
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                items.append({
                    "name": item,
                    "is_dir": os.path.isdir(full_path),
                    "size": os.path.getsize(full_path) if os.path.isfile(full_path) else None
                })
            return items
        except Exception as e:
            return [{"error": str(e)}]
    
    def execute_command(self, command: str, timeout: int = 30) -> str:
        """Execute a system command"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd()
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            return output if output else "Command executed successfully (no output)"
        except subprocess.TimeoutExpired:
            return f"Command timed out after {timeout} seconds"
        except Exception as e:
            return f"Error executing command: {e}"
    
    def system_info(self) -> Dict:
        """Get system information"""
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "memory": psutil.virtual_memory()._asdict(),
            "cpu_count": psutil.cpu_count()
        }
    
    def web_search(self, query: str) -> List[Dict]:
        """Web search (placeholder - can integrate with real search API)"""
        return [{"title": f"Search: {query}", "url": "", "snippet": "Web search integration needed"}]
    
    def web_scrape(self, url: str) -> str:
        """Web scraping (placeholder - can integrate with Firecrawl)"""
        return f"Web scraping integration needed for: {url}"


class EnterpriseRAG:
    def __init__(self):
        self.memory = ConversationMemory()
        self.kb = KnowledgeBase()
        self.tools = ToolIntegration()
        self.embeddings = None
        self.vector_store = None
        self.llm = None
        self._lock = threading.Lock()
        self._indexed_files = {}
        self._load_indexed_files_tracker()
    
    def _load_indexed_files_tracker(self):
        if INDEXED_FILES_TRACKER.exists():
            with open(INDEXED_FILES_TRACKER, 'r') as f:
                self._indexed_files = json.load(f)
    
    def _save_indexed_files_tracker(self):
        with open(INDEXED_FILES_TRACKER, 'w') as f:
            json.dump(self._indexed_files, f, indent=2)
    
    def _is_file_indexed(self, path: str, mtime: float) -> bool:
        entry = self._indexed_files.get(path)
        if not entry:
            return False
        return entry.get("mtime") == mtime
    
    def _register_indexed_file(self, path: str, mtime: float, size: int, chunks: int):
        self._indexed_files[path] = {
            "mtime": mtime,
            "size": size,
            "chunks": chunks,
            "indexed_at": datetime.now().isoformat()
        }
        self._save_indexed_files_tracker()
    
    def initialize_embeddings(self, model_type: str = None):
        model_type = model_type or config.get("default_embedding")
        
        if model_type == "nomic":
            self.embeddings = OllamaEmbeddings(
                base_url="http://localhost:11434",
                model="nomic-embed-text"
            )
        elif model_type == "sentence_transformers":
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
        else:
            raise ValueError(f"Unknown embedding model: {model_type}")
        
        self.vector_store = Chroma(
            persist_directory=str(DB_DIR),
            embedding_function=self.embeddings,
            collection_name=config.get("collection_name", "enterprise_rag")
        )
    
    def initialize_llm(self):
        self.llm = OllamaLLM(
            base_url="http://localhost:11434",
            model=config.get("llm_model")
        )
    
    def load_documents(self, directory: str = None) -> List[Document]:
        directory = directory or str(DOCS_DIR)
        docs = []
        supported_extensions = {
            ".txt": TextLoader,
            ".pdf": PyPDFLoader,
            ".docx": Docx2txtLoader,
            ".md": TextLoader
        }
        
        for root, _, files in os.walk(directory):
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in supported_extensions:
                    file_path = os.path.join(root, file)
                    try:
                        loader = supported_extensions[ext](file_path)
                        loaded = loader.load()
                        file_mtime = os.path.getmtime(file_path)
                        for doc in loaded:
                            doc.metadata["source"] = file_path
                            doc.metadata["mtime"] = file_mtime
                        docs.extend(loaded)
                    except Exception as e:
                        print(f"[WARN] Failed to load {file_path}: {e}")
        
        return docs
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.get("chunk_size", 500),
            chunk_overlap=config.get("chunk_overlap", 50),
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return splitter.split_documents(documents)
    
    def index_documents(self, documents: List[Document]):
        if not self.vector_store:
            self.initialize_embeddings()
        
        chunks = self.split_documents(documents)
        
        with self._lock:
            self.vector_store.add_documents(chunks)
        
        sources = {}
        for doc in documents:
            source = doc.metadata.get("source")
            mtime = doc.metadata.get("mtime")
            if source and mtime:
                sources[source] = {
                    "mtime": mtime,
                    "size": doc.metadata.get("size", len(doc.page_content))
                }
        
        existing_docs = {d["name"]: d for d in self.kb.list_documents()}
        for source, meta in sources.items():
            if source not in existing_docs:
                doc_id = str(uuid.uuid4())
                self.kb.add_document(
                    doc_id=doc_id,
                    name=source,
                    content=f"Indexed file: {source}",
                    doc_type="indexed_file",
                    tags=["auto-indexed"]
                )
            self._register_indexed_file(
                path=source,
                mtime=meta["mtime"],
                size=meta["size"],
                chunks=len(chunks)
            )
        
        return len(chunks)
    
    def retrieve(self, query: str, top_k: int = None) -> List[tuple]:
        if not self.vector_store:
            self.initialize_embeddings()
        
        top_k = top_k or config.get("top_k", 5)
        return self.vector_store.similarity_search_with_score(query, k=top_k)
    
    def build_prompt(self, query: str, context_docs: List[tuple], conversation_history: List[Dict] = None) -> str:
        context = "\n\n".join([doc.page_content for doc, score in context_docs])
        
        history_text = ""
        if conversation_history:
            history_text = "\n\nConversation History:\n"
            for msg in conversation_history[-3:]:
                history_text += f"{msg['role'].title()}: {msg['content']}\n"
        
        prompt = f"""You are an enterprise AI assistant with access to a knowledge base and various tools.
Use the following context to answer the question accurately.
If the answer is not in the context, say you don't know, but you can use tools to find information.

Context:
{context}
{history_text}
Question: {query}

Answer:"""
        return prompt
    
    def generate(self, prompt: str) -> str:
        if not self.llm:
            self.initialize_llm()
        
        try:
            response = self.llm.invoke(prompt)
            return response if isinstance(response, str) else str(response)
        except Exception as e:
            return f"[ERROR] Generation failed: {e}"
    
    def query(self, query: str, use_tools: bool = True, top_k: int = None) -> Dict:
        start_time = time.time()
        
        self.memory.add_message("user", query)
        
        results = self.retrieve(query, top_k)
        if not results:
            answer = "I don't have any information about that in my knowledge base."
            self.memory.add_message("assistant", answer)
            return {
                "answer": answer,
                "sources": [],
                "tools_used": [],
                "time": time.time() - start_time
            }
        
        context_docs = [doc for doc, score in results]
        conversation_history = self.memory.get_context()
        
        prompt = self.build_prompt(query, results, conversation_history)
        answer = self.generate(prompt)
        
        sources = []
        for doc, score in results:
            sources.append({
                "source": doc.metadata.get("source", "unknown"),
                "score": float(score),
                "content": doc.page_content[:200] + "..."
            })
        
        self.memory.add_message("assistant", answer, {"sources": sources})
        
        return {
            "answer": answer,
            "sources": sources,
            "tools_used": [],
            "time": time.time() - start_time
        }
    
    def use_tool(self, tool_name: str, params: Dict) -> Any:
        return self.tools.execute_tool(tool_name, params)
    
    def get_conversation_history(self) -> List[Dict]:
        return self.memory.history
    
    def clear_history(self):
        self.memory.clear()


# FastAPI Models
class QueryRequest(BaseModel):
    query: str
    use_tools: bool = True
    top_k: int = None
    embedding_model: str = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict]
    tools_used: List[str]
    time: float

class ToolRequest(BaseModel):
    tool_name: str
    params: Dict

class IndexRequest(BaseModel):
    directory: str = None
    file_path: str = None

class ConfigRequest(BaseModel):
    key: str
    value: Any

class KBAddRequest(BaseModel):
    name: str
    content: str
    doc_type: str
    tags: List[str] = None

# Initialize RAG system
rag = EnterpriseRAG()
rag.initialize_embeddings()
rag.initialize_llm()

# FastAPI app
app = FastAPI(
    title="Enterprise RAG System",
    description="Advanced RAG with knowledge base, tool integration, and conversation memory",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "name": "Enterprise RAG System",
        "version": "1.0.0",
        "status": "running",
        "models": {
            "llm": config.get("llm_model"),
            "embeddings": list(config.get("embedding_models", {}).keys())
        }
    }

@app.get("/tools")
async def get_tools():
    return {"tools": rag.tools.get_available_tools()}

@app.post("/tool/execute")
async def execute_tool(request: ToolRequest):
    try:
        result = rag.use_tool(request.tool_name, request.params)
        return {"tool": request.tool_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/query")
async def query(request: QueryRequest):
    try:
        if request.embedding_model:
            rag.initialize_embeddings(request.embedding_model)
        result = rag.query(request.query, request.use_tools, request.top_k)
        return result
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{tb}")

@app.post("/index")
async def index_documents(background_tasks: BackgroundTasks, request: IndexRequest):
    def index_task():
        try:
            if request.file_path:
                loader = TextLoader(request.file_path)
                docs = loader.load()
            else:
                docs = rag.load_documents(request.directory)
            
            chunks_indexed = rag.index_documents(docs)
            return {"status": "completed", "chunks_indexed": chunks_indexed}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    background_tasks.add_task(index_task)
    return {"status": "indexing started"}

@app.get("/history")
async def get_history():
    return {"history": rag.get_conversation_history()}

@app.post("/history/clear")
async def clear_history():
    rag.clear_history()
    return {"status": "history cleared"}

@app.get("/knowledge-base")
async def list_kb(tag: str = None):
    return {"documents": rag.kb.list_documents(tag)}

@app.post("/knowledge-base/add")
async def add_to_kb(request: KBAddRequest):
    doc_id = str(uuid.uuid4())
    rag.kb.add_document(doc_id, request.name, request.content, request.doc_type, request.tags)
    return {"doc_id": doc_id, "status": "added"}

@app.get("/config")
async def get_config():
    return config.config

@app.post("/config")
async def update_config(request: ConfigRequest):
    config.set(request.key, request.value)
    return {"status": "updated", "key": request.key, "value": request.value}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "ollama_connected": True,
        "vector_db": str(DB_DIR)
    }

def start_server(host: str = "127.0.0.1", port: int = 8000):
    print(f"[INFO] Starting Enterprise RAG Server on {host}:{port}")
    print(f"[INFO] API docs available at http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Enterprise RAG System")
    parser.add_argument("command", choices=["serve", "index", "query", "history", "tools"])
    parser.add_argument("--query", type=str)
    parser.add_argument("--file", type=str)
    parser.add_argument("--dir", type=str)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    if args.command == "serve":
        start_server(port=args.port)
    elif args.command == "index":
        if args.file:
            loader = TextLoader(args.file)
            docs = loader.load()
        elif args.dir:
            docs = rag.load_documents(args.dir)
        else:
            docs = rag.load_documents()
        
        chunks = rag.index_documents(docs)
        print(f"[INFO] Indexed {chunks} chunks")
    elif args.command == "query":
        if not args.query:
            print("Error: --query required")
            sys.exit(1)
        result = rag.query(args.query, top_k=args.top_k)
        print(f"\nAnswer: {result['answer']}")
        print(f"\nSources: {len(result['sources'])}")
        for i, source in enumerate(result['sources'], 1):
            print(f"  {i}. {source['source']} (score: {source['score']:.4f})")
    elif args.command == "history":
        history = rag.get_conversation_history()
        for msg in history:
            print(f"[{msg['role']}] {msg['content'][:100]}...")
    elif args.command == "tools":
        tools = rag.tools.get_available_tools()
        print("Available tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
