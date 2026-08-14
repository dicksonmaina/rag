#!/usr/bin/env python3
"""
OpenClaw Integration Client for Enterprise RAG
Provides a simple interface for OpenClaw to interact with the RAG system.
"""

import requests
import json
from typing import List, Dict, Any, Optional

BASE_URL = "http://localhost:9000"


class OpenClawRAGClient:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session_history = []
    
    def query(self, question: str, top_k: int = 5, use_tools: bool = True) -> Dict[str, Any]:
        """Query the RAG system with a question"""
        try:
            response = requests.post(
                f"{self.base_url}/query",
                json={
                    "query": question,
                    "top_k": top_k,
                    "use_tools": use_tools
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            self.session_history.append({"role": "user", "content": question})
            self.session_history.append({"role": "assistant", "content": result["answer"]})
            return result
        except Exception as e:
            return {"error": str(e), "answer": f"Error: {e}"}
    
    def index_directory(self, directory: str) -> Dict[str, Any]:
        """Index all documents in a directory"""
        try:
            response = requests.post(
                f"{self.base_url}/index",
                json={"directory": directory},
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def index_file(self, file_path: str) -> Dict[str, Any]:
        """Index a single file"""
        try:
            response = requests.post(
                f"{self.base_url}/index",
                json={"file_path": file_path},
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Execute a system tool"""
        try:
            response = requests.post(
                f"{self.base_url}/tool/execute",
                json={"tool_name": tool_name, "params": params},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def file_read(self, path: str) -> str:
        """Read a file using RAG tools"""
        result = self.execute_tool("file_read", {"path": path})
        return result.get("result", f"Error: {result.get('error', 'Unknown error')}")
    
    def file_write(self, path: str, content: str) -> str:
        """Write to a file using RAG tools"""
        result = self.execute_tool("file_write", {"path": path, "content": content})
        return result.get("result", f"Error: {result.get('error', 'Unknown error')}")
    
    def file_edit(self, path: str, old_text: str, new_text: str) -> str:
        """Edit a file using RAG tools"""
        result = self.execute_tool("file_edit", {"path": path, "old_text": old_text, "new_text": new_text})
        return result.get("result", f"Error: {result.get('error', 'Unknown error')}")
    
    def execute_command(self, command: str, timeout: int = 30) -> str:
        """Execute a system command via RAG"""
        result = self.execute_tool("execute_command", {"command": command, "timeout": timeout})
        return result.get("result", f"Error: {result.get('error', 'Unknown error')}")
    
    def list_directory(self, path: str = ".") -> List[Dict]:
        """List directory contents"""
        result = self.execute_tool("directory_list", {"path": path})
        return result.get("result", [])
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        result = self.execute_tool("system_info", {})
        return result.get("result", {})
    
    def web_search(self, query: str) -> List[Dict]:
        """Web search via RAG"""
        result = self.execute_tool("web_search", {"query": query})
        return result.get("result", [])
    
    def web_scrape(self, url: str) -> str:
        """Web scrape via RAG"""
        result = self.execute_tool("web_scrape", {"url": url})
        return result.get("result", "")
    
    def add_to_knowledge_base(self, name: str, content: str, doc_type: str, tags: List[str] = None) -> str:
        """Add content to knowledge base"""
        try:
            response = requests.post(
                f"{self.base_url}/knowledge-base/add",
                json={
                    "name": name,
                    "content": content,
                    "doc_type": doc_type,
                    "tags": tags or []
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("doc_id", "Error")
        except Exception as e:
            return f"Error: {e}"
    
    def list_knowledge_base(self, tag: str = None) -> List[Dict]:
        """List knowledge base documents"""
        try:
            url = f"{self.base_url}/knowledge-base"
            if tag:
                url += f"?tag={tag}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json().get("documents", [])
        except Exception as e:
            return [{"error": str(e)}]
    
    def get_history(self) -> List[Dict]:
        """Get conversation history"""
        try:
            response = requests.get(f"{self.base_url}/history", timeout=30)
            response.raise_for_status()
            return response.json().get("history", [])
        except Exception as e:
            return [{"error": str(e)}]
    
    def clear_history(self) -> Dict[str, Any]:
        """Clear conversation history"""
        try:
            response = requests.post(f"{self.base_url}/history/clear", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Check RAG system health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def chat(self, message: str, auto_tools: bool = True) -> str:
        """Simple chat interface that returns just the answer"""
        result = self.query(message, use_tools=auto_tools)
        if "error" in result:
            return f"Error: {result['error']}"
        return result.get("answer", "No response")


def main():
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaw RAG Client")
    parser.add_argument("command", choices=["chat", "query", "index", "tools", "kb", "health"])
    parser.add_argument("--message", type=str, help="Message for chat/query")
    parser.add_argument("--file", type=str, help="File to index")
    parser.add_argument("--dir", type=str, help="Directory to index")
    parser.add_argument("--tool", type=str, help="Tool to execute")
    parser.add_argument("--params", type=str, help="Tool parameters as JSON")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    
    client = OpenClawRAGClient()
    
    if args.command == "chat":
        if not args.message:
            print("Error: --message required")
            sys.exit(1)
        response = client.chat(args.message)
        print(response)
    
    elif args.command == "query":
        if not args.message:
            print("Error: --message required")
            sys.exit(1)
        result = client.query(args.message, top_k=args.top_k)
        print(json.dumps(result, indent=2))
    
    elif args.command == "index":
        if args.file:
            result = client.index_file(args.file)
        elif args.dir:
            result = client.index_directory(args.dir)
        else:
            print("Error: --file or --dir required")
            sys.exit(1)
        print(json.dumps(result, indent=2))
    
    elif args.command == "tools":
        tools = client.execute_tool("get_available_tools", {})
        print(json.dumps(tools, indent=2))
    
    elif args.command == "kb":
        docs = client.list_knowledge_base()
        print(json.dumps(docs, indent=2))
    
    elif args.command == "health":
        health = client.health_check()
        print(json.dumps(health, indent=2))


if __name__ == "__main__":
    main()
