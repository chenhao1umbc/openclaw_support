import io
import sys
import wave
from pathlib import Path

_VENV_SITE = Path.home() / ".openclaw_support" / "venv" / "lib" / "python3.13" / "site-packages"
_MODELS_DIR = Path.home() / ".openclaw_support" / "models" / "tts"

# Startup readiness guard — fail cleanly so launchd ThrottleInterval backs off.
if not _VENV_SITE.exists():
    print(f"[tts] ERROR: venv site-packages not found at {_VENV_SITE}. Run setup.sh.", flush=True)
    sys.exit(1)
if not any(_MODELS_DIR.glob("*.onnx")):
    print(f"[tts] ERROR: no voice models found in {_MODELS_DIR}. Run setup.sh.", flush=True)
    sys.exit(1)

if str(_VENV_SITE) not in sys.path:
    sys.path.insert(0, str(_VENV_SITE))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from piper.voice import PiperVoice
from pydantic import BaseModel

app = FastAPI()

MODELS_DIR = _MODELS_DIR

# Map OpenAI built-in voice names to piper models.
# Custom names (e.g. "en_US-lessac-medium") pass through directly.
OPENAI_VOICE_MAP = {
    "alloy": "en_US-lessac-medium",
    "echo": "en_US-lessac-medium",
    "fable": "en_US-lessac-medium",
    "onyx": "en_US-ryan-medium",
    "nova": "en_US-lessac-medium",
    "shimmer": "en_US-lessac-medium",
}

_voice_cache: dict[str, PiperVoice] = {}


def load_voice(name: str) -> PiperVoice:
    model_name = OPENAI_VOICE_MAP.get(name, name)
    if model_name not in _voice_cache:
        model_path = MODELS_DIR / f"{model_name}.onnx"
        if not model_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Voice model not found: {model_name}. Run setup.sh to download models.",
            )
        _voice_cache[model_name] = PiperVoice.load(str(model_path))
    return _voice_cache[model_name]


class TTSRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = "alloy"
    response_format: str = "wav"


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/audio/speech")
async def synthesize(req: TTSRequest) -> Response:
    voice = load_voice(req.voice)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(req.input, wav_file)
    return Response(content=buf.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5002)
