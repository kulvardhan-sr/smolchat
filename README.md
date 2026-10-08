# Smolchat

Smolchat is a split frontend/backend chat app:
- Frontend: React + Vite + TypeScript
- Backend: FastAPI with streaming SSE responses
- LLM: vLLM-compatible workflow (proxy mode by default, local in-process mode optional)

## Features
- Black terminal-style UI with monospace typography
- Sidebar + chat box layout
- Streaming chat responses
- Markdown rendering with code highlighting
- FastAPI backend with session history

## Project Structure
```text
smolchat/
	backend/
		main.py
		requirements.txt
		requirements-vllm.txt
	frontend/
		src/
	legacy/
```

## Important Python Note
If `pip freeze` is empty or `pip` is missing, your virtualenv is incomplete. Repair it with:

```bash
cd /path/to/smolchat
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install --upgrade pip
```

## Backend Setup
Use your root `.venv` (or any active virtualenv):

```bash
cd /path/to/smolchat
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r backend/requirements.txt
```

### Run Backend (Default: Proxy Mode)
Proxy mode expects an OpenAI-compatible vLLM server running separately.

Start vLLM first (uses your requested settings):

```bash
vllm serve Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4 \
	--host 0.0.0.0 \
	--port 8000 \
	--gpu-memory-utilization 0.85 \
	--max-num-seqs 32 \
	--max-model-len 8192 \
	--enforce-eager
```

Then run FastAPI backend on a different port (8001) to avoid conflicts:

```bash
cd /path/to/smolchat/backend
BACKEND_MODE=proxy VLLM_BASE_URL=http://127.0.0.1:8000/v1 \
	/path/to/smolchat/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Optional: Local In-Process vLLM Mode
Install optional deps (only in a Python/CUDA environment supported by vLLM):

```bash
cd /path/to/smolchat
.venv/bin/python -m pip install -r backend/requirements-vllm.txt
```

Run backend in local mode:

```bash
cd /path/to/smolchat/backend
BACKEND_MODE=local MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4 \
	/path/to/smolchat/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Check backend health:

```bash
curl http://127.0.0.1:8001/health
```

## Frontend Setup
```bash
cd /path/to/smolchat/frontend
npm install
echo "VITE_BACKEND_URL=http://127.0.0.1:8001" > .env.local
npm run dev
```

Open the Vite URL shown in terminal (usually `http://127.0.0.1:5173`).

## One-Command Dev Launcher
If you already started vLLM on port `8000`, you can launch backend + frontend together from the project root:

```bash
cd /path/to/smolchat
make dev
```

This starts:
- FastAPI backend on `http://127.0.0.1:8001` (proxying to `http://127.0.0.1:8000/v1`)
- Vite frontend on its default dev port (usually `http://127.0.0.1:5173`)

Optional overrides:

```bash
BACKEND_PORT=8010 VLLM_BASE_URL=http://127.0.0.1:8000/v1 make dev
```