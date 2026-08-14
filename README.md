# Enterprise RAG System

## Components
- **Embeddings**: Dual-model support (nomic-embed-text via Ollama + all-MiniLM-L6-v2 via HuggingFace)
- **Vector Store**: ChromaDB (persistent, stored in `chroma_db/`)
- **LLM**: Ollama `qwen2:0.5b` (local inference)
- **Server**: FastAPI + Uvicorn (REST API on port 9000)
- **Client**: Python CLI + OpenClaw integration skill

## Setup Complete
1. Embedding models installed: `nomic-embed-text` (274MB) + `all-MiniLM-L6-v2` (80MB)
2. Ollama models: `qwen2:0.5b` + `nomic-embed-text`
3. RAG server running on `http://localhost:9000`
4. OpenClaw skill installed at `C:\Users\user\.openclaw\skills\rag-knowledge-base\`
5. Enterprise documents indexed in knowledge base

## Quick Start

### Start all services
```powershell
# Start RAG server + OpenClaw gateway
C:\Users\user\RAG\start_enterprise.bat
```

### Or start individually
```powershell
# Start RAG server only
rag.bat serve

# Query via CLI
rag.bat query "What is RAG?"

# Chat interface
rag.bat chat "Hello"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | System status |
| `/health` | GET | Health check |
| `/query` | POST | Query knowledge base |
| `/index` | POST | Index documents |
| `/tools` | GET | List available tools |
| `/tool/execute` | POST | Execute a system tool |
| `/knowledge-base` | GET | List KB documents |
| `/knowledge-base/add` | POST | Add to knowledge base |
| `/history` | GET | Conversation history |
| `/config` | GET/POST | View/update config |

## Available Tools

| Tool | Description |
|------|-------------|
| `file_read` | Read any file from disk |
| `file_write` | Write/create files |
| `file_edit` | Search-and-replace edit files |
| `file_list` | List directory contents |
| `directory_list` | Detailed directory listing |
| `execute_command` | Run system commands |
| `system_info` | Platform/memory/CPU info |
| `web_search` | Web search placeholder |
| `web_scrape` | Web scraping placeholder |

## OpenClaw Integration

The `rag-knowledge-base` skill is installed and enabled. OpenClaw can:
- Query the knowledge base with natural language
- Read, write, and edit files on the device
- Execute system commands through the RAG backend
- Access conversation memory and sources

Restart OpenClaw to load the new skill:
```powershell
openclaw gateway restart
```

## Architecture
```
OpenClaw (port 18789)
    └── rag-knowledge-base skill
            └── openclaw_client.py
                    └── Enterprise RAG Server (port 9000)
                            ├── FastAPI
                            ├── ChromaDB (vector store)
                            ├── Ollama (embeddings + LLM)
                            ├── HuggingFace (embeddings)
                            └── System Tools (file, command, etc.)
```

## Notes
- Ollama must be running (`ollama serve`)
- First query may take a few seconds to load models
- Windows firewall may prompt for Python network access on first run
- Port 9000 is used (ports 8000-8100 are reserved by Windows)
