import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Ensure venv site-packages are on path when launched by launchd.
_VENV_SITE = Path.home() / ".openclaw_support" / "venv" / "lib" / "python3.13" / "site-packages"
if str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

import mlx_whisper
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()

MODEL = os.environ.get("WHISPER_MODEL", "mlx-community/whisper-medium-mlx")


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
