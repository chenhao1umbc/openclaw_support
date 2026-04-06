import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

_VENV_SITE = Path.home() / ".openclaw_support" / "venv" / "lib" / "python3.13" / "site-packages"

# Startup readiness guard — fail cleanly so launchd ThrottleInterval backs off.
if not _VENV_SITE.exists():
    print(f"[whisper] ERROR: venv site-packages not found at {_VENV_SITE}. Run setup.sh.", flush=True)
    sys.exit(1)

if str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

import mlx.core as mx
import mlx_whisper
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from mlx_whisper.transcribe import ModelHolder

MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-medium-mlx")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load model weights into cache so first request has no cold-start delay.
    print(f"[whisper] Loading model {MODEL} ...", flush=True)
    ModelHolder.get_model(MODEL, mx.float16)
    print("[whisper] Model ready.", flush=True)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="whisper-1"),
    language: Optional[str] = Form(default=None),
    prompt: Optional[str] = Form(default=None),
    response_format: str = Form(default="json"),
    temperature: float = Form(default=0.0),
):
    suffix = Path(file.filename).suffix if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        kwargs = {"path_or_hf_repo": MODEL}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["initial_prompt"] = prompt
        if temperature:
            kwargs["temperature"] = temperature
        result = mlx_whisper.transcribe(tmp_path, **kwargs)
        text = result["text"].strip()
    finally:
        os.unlink(tmp_path)

    if response_format == "text":
        return text
    return JSONResponse({"text": text})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
