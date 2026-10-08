import json
import os
import uuid
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Smolchat VLLM Backend", description="Direct vLLM-served chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_MODE = os.getenv("BACKEND_MODE", "proxy").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4")
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8001"))

engine = None
tokenizer = None
SamplingParams = None
engine_init_error: Optional[str] = None

if BACKEND_MODE == "local":
    try:
        from transformers import AutoTokenizer
        from vllm.engine.arg_utils import AsyncEngineArgs
        from vllm.engine.async_llm_engine import AsyncLLMEngine
        from vllm.sampling_params import SamplingParams as VllmSamplingParams

        engine_args = AsyncEngineArgs(
            model=MODEL_NAME,
            trust_remote_code=True,
            max_model_len=2048,
            gpu_memory_utilization=0.8,
            quantization="gptq",
        )
        engine = AsyncLLMEngine.from_engine_args(engine_args)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        SamplingParams = VllmSamplingParams
    except Exception as e:
        engine_init_error = str(e)

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

# Basic in-memory history 
sessions: Dict[str, List[Dict[str, str]]] = {}


@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": BACKEND_MODE,
        "local_engine_ready": bool(engine and tokenizer),
        "model": MODEL_NAME,
        "vllm_base_url": VLLM_BASE_URL,
        "engine_init_error": engine_init_error,
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id not in sessions:
        sessions[session_id] = [
            {"role": "system", "content": "You are a helpful AI assistant."}
        ]

    # Append user message
    sessions[session_id].append({"role": "user", "content": request.message})

    async def stream_local_results():
        if not engine or not tokenizer or not SamplingParams:
            yield f"data: {json.dumps({'content': 'Local vLLM mode is not ready. Check backend logs or use proxy mode.'})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        prompt = tokenizer.apply_chat_template(
            sessions[session_id], tokenize=False, add_generation_prompt=True
        )

        sampling_params = SamplingParams(
            temperature=0.7,
            max_tokens=1024,
            stop_token_ids=[tokenizer.eos_token_id] if tokenizer.eos_token_id else [],
        )
        request_id = str(uuid.uuid4())

        results_generator = engine.generate(prompt, sampling_params, request_id)
        last_yielded_len = 0
        full_text = ""

        async for request_output in results_generator:
            text = request_output.outputs[0].text
            new_text = text[last_yielded_len:]

            if new_text:
                full_text += new_text
                yield f"data: {json.dumps({'content': new_text})}\n\n"
                last_yielded_len = len(text)

        sessions[session_id].append({"role": "assistant", "content": full_text})
        yield f"data: {json.dumps({'done': True})}\n\n"

    async def stream_proxy_results():
        payload = {
            "model": MODEL_NAME,
            "messages": sessions[session_id],
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": True,
        }
        full_text = ""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{VLLM_BASE_URL}/chat/completions", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        delta = parsed.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            full_text += token
                            yield f"data: {json.dumps({'content': token})}\n\n"
        except Exception as e:
            err = f"Proxy mode error: {e}. Ensure vLLM OpenAI server is reachable at {VLLM_BASE_URL}."
            yield f"data: {json.dumps({'content': err})}\n\n"

        sessions[session_id].append({"role": "assistant", "content": full_text})
        yield f"data: {json.dumps({'done': True})}\n\n"

    stream_fn = stream_local_results if BACKEND_MODE == "local" else stream_proxy_results
    return StreamingResponse(stream_fn(), media_type="text/event-stream")

@app.post("/clear")
async def clear_chat(request: ChatRequest):
    session_id = request.session_id
    sessions[session_id] = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]
    return {"status": "cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=BACKEND_PORT, reload=True)
