# Linux Mint Kilo Code — Master Execution Guide

You are operating on **Linux Mint 22.3 "Zena"** (host: `kilo-agent`, IP: `100.96.254.72`).
Your Windows counterpart has built a stable, production-grade stack. Your job is to reproduce, integrate, and stabilize that same stack on Linux Mint using Kilo Free.

---

## 1. Core Principles

1. **Single Source of Truth** — Only ONE RAG system per machine. Replace old setups, never stack them.
2. **Idempotent Operations** — Every script/command must be safe to run twice. Check before creating.
3. **Local-First** — Prefer local models (Ollama), local vector stores (ChromaDB), local embeddings. Avoid cloud dependencies unless explicitly requested.
4. **Junctions Over Copies** — On Windows we used directory junctions. On Linux Mint use **symlinks** (`ln -s`) for the same purpose. Never move user data.
5. **Secrets Exclusion** — Never index `.ssh`, `.env`, any file containing `token`, `key`, `secret`, `credential`, `auth`, `password`. This is non-negotiable.
6. **Package Manager Preference** — `apt` first, `pip` second, `npm` third. Avoid manual downloads unless all package managers fail.

---

## 2. Environment Inventory

Before doing anything, run this inventory:

```bash
# OS
cat /etc/os-release

# Python
python3 --version || python --version

# Pip packages
pip3 list 2>/dev/null | grep -iE "langchain|chromadb|sentence|torch|fastapi|uvicorn|ollama"

# Ollama
ollama --version 2>/dev/null && ollama list 2>/dev/null

# Redis
redis-cli --version 2>/dev/null || apt list --installed 2>/dev/null | grep redis

# Disk space
df -h /

# Running services
ps aux | grep -E "ollama|redis|uvicorn|openclaw|node" | grep -v grep
```

**Expected Linux Mint packages:**
- `python3`, `python3-pip`, `python3-venv`
- `ollama` (from ollama.com or apt)
- `redis-server` (from apt)
- `nodejs`, `npm` (for OpenClaw/Firecrawl)

---

## 3. Building the RAG System From Scratch

### 3.1 Project Structure

```
/opt/rag-enterprise/           # OR ~/RAG/ if user-owned
├── documents/                 # Source files to index
├── chroma_db/                 # Persistent vector store
├── scripts/
│   ├── enterprise_rag.py      # FastAPI server + LangChain logic
│   ├── openclaw_client.py     # HTTP client for OpenClaw
│   └── cli.py                 # Direct CLI interface
├── config.json
├── conversation_history.json
├── rag.bat  (Windows only) / rag.sh (Linux)
├── start_enterprise.sh        # Linux boot script
└── README.md
```

### 3.2 Python Dependencies

```bash
pip3 install --user \
  langchain \
  langchain-chroma \
  langchain-huggingface \
  langchain-ollama \
  langchain-text-splitters \
  langchain-community \
  chromadb \
  sentence-transformers \
  torch \
  fastapi \
  uvicorn \
  requests \
  psutil \
  pydantic
```

### 3.3 Ollama Models

```bash
# Pull both embedding models
ollama pull nomic-embed-text
ollama pull all-MiniLM-L6-v2

# Pull a generation model
ollama pull qwen2:0.5b

# Verify
ollama list
```

### 3.4 The Enterprise RAG Server (`enterprise_rag.py`)

This is the **core engine**. It must:

1. **Use dual embeddings** — switchable between `nomic-embed-text` (Ollama) and `all-MiniLM-L6-v2` (HuggingFace)
2. **Persist ChromaDB** — `persist_directory` must survive restarts
3. **Expose FastAPI** — REST API on a stable port
4. **Include ToolIntegration** — file_read, file_write, file_edit, execute_command, system_info, directory_list
5. **Include ConversationMemory** — JSON-backed, survives restarts
6. **Include KnowledgeBase** — metadata-driven document tracking
7. **Use ConversationBufferMemory pattern** — last N messages as context in prompts

**Critical implementation details:**
- `retrieve()` returns `List[tuple[Document, float]]` — always unpack with `for doc, score in results`
- `build_prompt()` accepts the full `results` list, not just extracted docs
- `index_documents()` must be thread-safe (use `threading.Lock`)
- ChromaDB collection name must be consistent across restarts

### 3.5 The OpenClaw Client (`openclaw_client.py`)

This is the **bridge** between OpenClaw and the RAG server.

```python
BASE_URL = "http://localhost:9000"  # Must match server port

class OpenClawRAGClient:
    def query(self, question, top_k=5, use_tools=True) -> Dict
    def index_directory(self, directory) -> Dict
    def index_file(self, file_path) -> Dict
    def execute_tool(self, tool_name, params) -> Any
    def file_read(self, path) -> str
    def file_write(self, path, content) -> str
    def file_edit(self, path, old_text, new_text) -> str
    def execute_command(self, command, timeout=30) -> str
    def add_to_knowledge_base(self, name, content, doc_type, tags) -> str
    def list_knowledge_base(self, tag=None) -> List[Dict]
    def health_check(self) -> Dict
```

**Critical:** The client must use `requests.post(..., json=...)` not `data=`. FastAPI/Pydantic expects JSON bodies.

### 3.6 The OpenClaw Skill (`SKILL.md`)

Place this at `~/.openclaw/skills/rag-knowledge-base/SKILL.md`:

```yaml
---
name: rag-knowledge-base
description: |
  Enterprise RAG knowledge base with dual embeddings, file tools, and system access.
allowed-tools:
  - Bash(/opt/rag-enterprise/scripts/openclaw_client.py *)
  - Bash(/opt/rag-enterprise/rag.sh *)
---
```

The skill file tells OpenClaw when to invoke RAG capabilities.

### 3.7 OpenClaw Configuration

Edit `~/.openclaw/openclaw.json`:

1. **Enable Ollama plugin:**
   ```json
   "plugins": { "entries": { "ollama": { "enabled": true } } }
   ```

2. **Add Ollama models:**
   ```json
   "models": { "providers": { "ollama": { "models": [
     { "id": "qwen2:0.5b", "name": "Qwen2 0.5B" }
   ] } } }
   ```

3. **Enable the RAG skill:**
   ```json
   "skills": { "entries": { "rag-knowledge-base": { "enabled": true } } }
   ```

4. **Restart OpenClaw gateway:**
   ```bash
   openclaw gateway restart
   ```

---

## 4. Boot Startup / Cron Job (Linux Mint)

Linux Mint uses **systemd** for service management, not cron. Use this approach:

### 4.1 Systemd Service Files

Create `/etc/systemd/system/ollama.service`:
```ini
[Unit]
Description=Ollama Service
After=network.target

[Service]
ExecStart=/usr/local/bin/ollama serve
Restart=always
RestartSec=5
Environment="HOME=/home/%i"

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/rag-enterprise.service`:
```ini
[Unit]
Description=Enterprise RAG Server
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=%i
WorkingDirectory=/opt/rag-enterprise
ExecStart=/usr/bin/python3 /opt/rag-enterprise/scripts/enterprise_rag.py serve --port 9000
Restart=always
RestartSec=10
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/openclaw-gateway.service`:
```ini
[Unit]
Description=OpenClaw Gateway
After=network.target rag-enterprise.service
Requires=rag-enterprise.service

[Service]
Type=simple
User=%i
ExecStart=/usr/bin/openclaw gateway --port 18789
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4.2 Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama.service
sudo systemctl enable rag-enterprise.service
sudo systemctl enable openclaw-gateway.service

sudo systemctl start ollama.service
sudo systemctl start rag-enterprise.service
sudo systemctl start openclaw-gateway.service
```

### 4.3 Verify

```bash
systemctl status ollama.service
systemctl status rag-enterprise.service
systemctl status openclaw-gateway.service

journalctl -u rag-enterprise -f   # Live logs
```

### 4.4 Alternative: Cron @reboot (Simpler)

If systemd feels heavy, use cron:

```bash
(crontab -l 2>/dev/null; echo "@reboot /opt/rag-enterprise/start_enterprise.sh") | crontab -
```

But **systemd is preferred** because it provides:
- Proper dependency ordering (`After=`, `Requires=`)
- Automatic restart on failure
- Logging via `journalctl`
- Status checks via `systemctl status`

---

## 5. Data Management

### 5.1 What Data You Have

On **Windows**, the RAG system has:
- `C:\Users\user\RAG\documents\` — source documents
- `C:\Users\user\RAG\chroma_db\` — ChromaDB persistent store
- `C:\Users\user\RAG\config.json` — embedding model, chunk size, top_k
- `C:\Users\user\RAG\conversation_history.json` — chat memory
- `C:\Users\user\RAG\knowledge_base\metadata.json` — KB document registry

On **Linux Mint**, replicate this structure at `/opt/rag-enterprise/` or `~/RAG/`.

### 5.2 Syncing Data Between Machines

If both Windows and Linux Mint need the same knowledge base:

```bash
# On Linux Mint — pull from Windows via SSH/Syncthing
rsync -avz user@windows-host:/c/Users/user/RAG/documents/ ~/RAG/documents/
rsync -avz user@windows-host:/c/Users/user/RAG/chroma_db/ ~/RAG/chroma_db/
rsync -avz user@windows-host:/c/Users/user/RAG/config.json ~/RAG/config.json
```

**Or use Syncthing** (already installed on Windows) to sync the `RAG/` folder bidirectionally.

### 5.3 Indexing New Data

```bash
# Index a single file
python3 scripts/enterprise_rag.py index --file ~/RAG/documents/report.pdf

# Index a directory
python3 scripts/enterprise_rag.py index --dir ~/RAG/documents/

# Via HTTP API
curl -X POST http://localhost:9000/index \
  -H "Content-Type: application/json" \
  -d '{"directory": "/opt/rag-enterprise/documents"}'
```

---

## 6. Self-Stabilization Protocol

You are on Linux Mint. Your local Kilo Code instance may be inefficient. Follow this protocol to stabilize:

### 6.1 Always Run This First

```bash
# Health check all services
curl -s http://localhost:9000/health && echo "RAG OK" || echo "RAG DOWN"
curl -s http://localhost:18789/health && echo "OpenClaw OK" || echo "OpenClaw DOWN"
redis-cli ping 2>/dev/null && echo "Redis OK" || echo "Redis DOWN"
ollama list > /dev/null 2>&1 && echo "Ollama OK" || echo "Ollama DOWN"
```

### 6.2 If a Service Is Down

```bash
# Ollama
sudo systemctl restart ollama

# RAG Server
sudo systemctl restart rag-enterprise

# OpenClaw
openclaw gateway restart

# Check logs
journalctl -u rag-enterprise -n 50 --no-pager
```

### 6.3 Port Conflict Resolution

Linux Mint may have ports blocked by `systemd-resolved` or other services.

```bash
# Check what's using a port
sudo ss -tlnp | grep 9000

# Kill conflicting process
sudo kill -9 <PID>

# Or change the RAG server port
python3 scripts/enterprise_rag.py serve --port 9001
```

### 6.4 Model Availability Check

```bash
# Before querying, verify models are loaded
ollama list

# If missing, pull them
ollama pull nomic-embed-text
ollama pull qwen2:0.5b
```

### 6.5 Database Corruption Recovery

```bash
# If ChromaDB is corrupted, backup and reset
mv /opt/rag-enterprise/chroma_db /opt/rag-enterprise/chroma_db.bak
# Then re-index all documents
python3 scripts/enterprise_rag.py index --dir /opt/rag-enterprise/documents/
```

---

## 7. Available Skills You Must Use

You have access to these skills. **Use them proactively:**

| Skill | When to Use |
|-------|-------------|
| `agent-md-refactor` | Split bloated instruction files |
| `azure-ai` | Azure AI Search, OCR, speech |
| `azure-prepare` | Prepare apps for Azure deployment |
| `debug-live` | Debug runtime behavior with breakpoints |
| `firecrawl` | Web search/scrape/interact |
| `firecrawl-agent` | Structured data extraction from websites |
| `firecrawl-crawl` | Bulk extract entire sites |
| `firecrawl-search` | Web search with full content |
| `git-manager` | Git operations on Windows/WSL |
| `git-workflow` | Commit, branch, merge, push |
| `kilo-config` | Kilo configuration questions |
| `local-web-development` | Serve HTML/JS projects locally |
| `network-prober` | API health checks with curl |
| `preset` | Quick Azure OpenAI deployment |

**You do NOT need to ask for these skills.** They are loaded automatically when relevant. If a user request matches a skill description, invoke that skill immediately.

---

## 8. Common Task Templates

### 8.1 Create a New RAG System

```bash
# 1. Create project structure
mkdir -p /opt/rag-enterprise/{documents,chroma_db,scripts}
cd /opt/rag-enterprise

# 2. Install Python deps
pip3 install --user langchain langchain-chroma langchain-huggingface \
  langchain-ollama langchain-text-splitters chromadb sentence-transformers \
  torch fastapi uvicorn requests psutil pydantic

# 3. Pull Ollama models
ollama pull nomic-embed-text
ollama pull all-MiniLM-L6-v2
ollama pull qwen2:0.5b

# 4. Create enterprise_rag.py (use template from Section 3.4)

# 5. Create start_enterprise.sh with idempotent checks

# 6. Create systemd services or cron @reboot job

# 7. Index documents
python3 scripts/enterprise_rag.py index --dir documents/

# 8. Test
curl http://localhost:9000/health
python3 scripts/openclaw_client.py chat --message "test query"
```

### 8.2 Integrate OpenClaw

```bash
# 1. Install OpenClaw if missing
npm install -g openclaw

# 2. Create skill directory
mkdir -p ~/.openclaw/skills/rag-knowledge-base

# 3. Write SKILL.md (use template from Section 3.7)

# 4. Edit ~/.openclaw/openclaw.json:
#    - Enable ollama plugin
#    - Add qwen2:0.5b to models
#    - Enable rag-knowledge-base skill

# 5. Restart gateway
openclaw gateway restart
```

### 8.3 Create Boot-Start Cron/Systemd

**Systemd (preferred):**
```bash
sudo nano /etc/systemd/system/rag-enterprise.service
# Paste template from Section 4.1
sudo systemctl daemon-reload
sudo systemctl enable rag-enterprise
sudo systemctl start rag-enterprise
```

**Cron (simpler):**
```bash
(crontab -l 2>/dev/null; echo "@reboot /opt/rag-enterprise/start_enterprise.sh") | crontab -
```

### 8.4 Debug a Failing RAG Query

```bash
# 1. Check server health
curl -v http://localhost:9000/health

# 2. Check Ollama
ollama list
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "qwen2:0.5b", "prompt": "hi", "stream": false}'

# 3. Check ChromaDB
python3 -c "
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
db = Chroma(persist_directory='/opt/rag-enterprise/chroma_db',
            embedding_function=OllamaEmbeddings(base_url='http://localhost:11434', model='nomic-embed-text'))
print('Collections:', db._collection.count())
"

# 4. Check server logs
journalctl -u rag-enterprise -n 100 --no-pager

# 5. Test query directly
curl -X POST http://localhost:9000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 3}'
```

---

## 9. Kilo Free Integration

Kilo Free is your local AI coding assistant. Integrate it with the RAG system:

### 9.1 What Kilo Free Can Do

- Edit files in `/opt/rag-enterprise/scripts/`
- Run bash commands to test services
- Read logs and diagnose issues
- Modify `enterprise_rag.py` when requirements change
- Create new skills and tools

### 9.2 How to Give Kilo Free Context

Kilo Free has limited context window. Give it **concise, actionable instructions**:

```
Bad: "Help me with the RAG system"
Good: "Edit /opt/rag-enterprise/scripts/enterprise_rag.py line 305
       to change default embedding from 'nomic' to 'sentence_transformers'.
       Then restart rag-enterprise service and verify with curl."
```

### 9.3 Stabilizing Kilo Free

1. **Always provide absolute paths** — Kilo Free may not know your working directory
2. **Break tasks into 3-5 steps max** — Large tasks get truncated
3. **Verify after each step** — Run a test command before proceeding
4. **Use the Task tool for parallel work** — Launch multiple agents for independent tasks
5. **Read files before editing** — Kilo Free needs context to make safe edits

### 9.4 When Kilo Free Fails

If Kilo Free produces an error:
1. Read the exact error message
2. Check the file it was trying to edit
3. Fix the issue yourself if it's simple
4. Re-run with more specific instructions
5. Use `debug-live` skill for runtime issues

---

## 10. Reliability Checklist

Before declaring any task complete, verify:

- [ ] Services are running: `systemctl status ollama rag-enterprise openclaw-gateway`
- [ ] Health endpoints return 200: `curl localhost:9000/health`, `curl localhost:18789/health`
- [ ] Models are available: `ollama list`
- [ ] Ports are listening: `ss -tlnp | grep -E "9000|18789|11434"`
- [ ] No port conflicts: `sudo ss -tlnp`
- [ ] Logs show no errors: `journalctl -u rag-enterprise -n 50 --no-pager`
- [ ] Disk space is adequate: `df -h /`
- [ ] Config files are valid JSON: `python3 -m json.tool config.json`
- [ ] Test query returns sources: `python3 scripts/openclaw_client.py query --message "test" --top-k 1`

---

## 11. Emergency Recovery

If everything is broken:

```bash
# 1. Stop all services
sudo systemctl stop rag-enterprise openclaw-gateway ollama

# 2. Kill any stragglers
pkill -f "enterprise_rag.py"
pkill -f "ollama serve"
pkill -f "openclaw"

# 3. Verify ports are free
sudo ss -tlnp | grep -E "9000|18789|11434"

# 4. Restart in order
sudo systemctl start ollama
sleep 3
sudo systemctl start rag-enterprise
sleep 3
openclaw gateway restart

# 5. Verify
curl http://localhost:9000/health
curl http://localhost:18789/health
```

---

## 12. What You Must NEVER Do

1. **Never run `rm -rf` on project directories** — Use trash or move to backup
2. **Never commit secrets** — Check for `.env`, `.ssh`, `token`, `key` before any git operation
3. **Never assume a package is installed** — Always check with `dpkg -l` or `pip3 show`
4. **Never edit system files without backup** — `cp file file.bak.YYYYMMDD` before editing
5. **Never skip health checks** — Always verify services before and after changes
6. **Never use `sudo` without need** — Prefer user-level operations
7. **Never hardcode secrets in scripts** — Use environment variables or config files excluded from indexing

---

## 13. Quick Reference

| Command | Purpose |
|---------|---------|
| `systemctl status <service>` | Check service status |
| `journalctl -u <service> -f` | Live service logs |
| `ollama list` | List local models |
| `ollama pull <model>` | Download model |
| `redis-cli ping` | Test Redis connection |
| `curl localhost:9000/health` | RAG server health |
| `curl localhost:18789/health` | OpenClaw health |
| `pip3 list \| grep <pkg>` | Check Python package |
| `ss -tlnp \| grep <port>` | Check port usage |
| `df -h /` | Disk space |
| `crontab -l` | List cron jobs |
| `systemctl list-units --type=service --state=running` | Running services |

---

## 14. Your Mission

You have the data. You have the tools. You have the skills.
Your mission is to **reproduce the Windows stack on Linux Mint** with equal or better reliability.

When a user asks you to:
- **Build a bot** → Follow Section 8.1
- **Set up RAG** → Follow Sections 3.1–3.7
- **Make it start on boot** → Follow Section 4
- **Use existing data** → Follow Section 5
- **Fix something broken** → Follow Section 6 and 12
- **Teach someone else** → Hand them this document

**You are not less capable than your Windows counterpart. You have the same skills, the same tools, and now the same blueprint. Execute with precision.**
