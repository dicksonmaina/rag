# MANAGEMENT.md - RAG Knowledge Indexer

## Purpose
This document defines how this project is maintained, upgraded, and secured.

## Stack
- Python 3.11+ (scripts)
- Requests library (HTTP)
- Local RAG server at `http://localhost:9000`

## Security Rules
- Never commit API keys, tokens, or credentials
- Validate all file paths before processing
- Sanitize all text before indexing
- No external data exfiltration

## Adding Features
1. Create new script in `scripts/`
2. Add requirements to `requirements.txt`
3. Test locally with `python scripts/your_script.py`
4. Run `python -m py_compile` on all modified files
5. Update this MANAGEMENT.md if stack changes

## CI/CD
- GitHub Actions runs Python syntax check on every push
- Dependencies validation on every push
- No automated deployment

## Support
- Issues: https://github.com/dicksonmaina/rag/issues
- Docs: See `README.md`
