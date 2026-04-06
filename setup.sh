#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Everything launchd touches lives in ~/.openclaw_support/ (outside ~/Documents)
# to avoid macOS TCC privacy blocking file access when launchd runs Python
# without Full Disk Access.
DEPLOY_DIR="$HOME/.openclaw_support"
VENV="$DEPLOY_DIR/venv"
MODELS_DIR="$DEPLOY_DIR/models/tts"
LOGS_DIR="$DEPLOY_DIR/logs"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"

mkdir -p "$DEPLOY_DIR" "$MODELS_DIR" "$LOGS_DIR"

# ── uv ────────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "[setup] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "[setup] Creating Python 3.13 venv at $VENV ..."
    uv venv "$VENV" --python 3.13
fi

echo "[setup] Installing Python dependencies..."
UV_PROJECT_ENVIRONMENT="$VENV" uv sync --project "$SCRIPT_DIR" --quiet

# ── Deploy server scripts ─────────────────────────────────────────────────────
# Scripts are kept in the project dir for editing, deployed here for launchd.
echo "[setup] Deploying server scripts to $DEPLOY_DIR ..."
cp "$SCRIPT_DIR/whisper_server.py" "$DEPLOY_DIR/whisper_server.py"
cp "$SCRIPT_DIR/tts_server.py"     "$DEPLOY_DIR/tts_server.py"

# ── Piper voice models ────────────────────────────────────────────────────────
HF_PIPER="https://huggingface.co/rhasspy/piper-voices/resolve/main"

download_voice() {
    local lang_path="$1"   # e.g. en/en_US/lessac/medium
    local model_name="$2"  # e.g. en_US-lessac-medium

    local onnx="$MODELS_DIR/${model_name}.onnx"
    local json="$MODELS_DIR/${model_name}.onnx.json"

    if [ ! -f "$onnx" ]; then
        echo "[setup] Downloading ${model_name}.onnx ..."
        curl -fL --progress-bar \
            "${HF_PIPER}/${lang_path}/${model_name}.onnx" \
            -o "$onnx"
    fi
    if [ ! -f "$json" ]; then
        echo "[setup] Downloading ${model_name}.onnx.json ..."
        curl -fL --progress-bar \
            "${HF_PIPER}/${lang_path}/${model_name}.onnx.json" \
            -o "$json"
    fi
}

download_voice "en/en_US/lessac/medium" "en_US-lessac-medium"
download_voice "en/en_US/ryan/medium"   "en_US-ryan-medium"
download_voice "zh/zh_CN/huayan/medium" "zh_CN-huayan-medium"

# ── Whisper model pre-fetch ───────────────────────────────────────────────────
echo "[setup] Pre-fetching Whisper medium model (downloads on first call if missing)..."
"$VENV/bin/python" -c "import mlx_whisper; mlx_whisper.transcribe('/dev/null', path_or_hf_repo='mlx-community/whisper-medium-mlx')" 2>/dev/null || true

# ── launchd plists ────────────────────────────────────────────────────────────
PYTHON_BIN="$(readlink -f "${VENV}/bin/python3.13")"
SITE_PACKAGES="${VENV}/lib/python3.13/site-packages"

write_plist() {
    local label="$1"
    local script="$2"
    local port="$3"
    local plist="$LAUNCH_AGENTS/${label}.plist"

    cat > "$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${script}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${SITE_PACKAGES}</string>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${DEPLOY_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOGS_DIR}/${label}.log</string>
    <key>StandardErrorPath</key>
    <string>${LOGS_DIR}/${label}.err</string>
</dict>
</plist>
PLIST

    # Unload if already loaded, then load fresh
    launchctl unload "$plist" 2>/dev/null || true
    launchctl load "$plist"
    echo "[setup] Registered launchd service: ${label} (port ${port})"
}

write_plist "com.openclaw.whisper" "$DEPLOY_DIR/whisper_server.py" "5001"
write_plist "com.openclaw.tts"     "$DEPLOY_DIR/tts_server.py"     "5002"

echo ""
echo "[setup] Done."
echo ""
echo "  Whisper STT : http://100.65.129.114:5001/v1/audio/transcriptions"
echo "  TTS         : http://100.65.129.114:5002/v1/audio/speech"
echo ""
echo "Configure OpenClaw on Linux (100.102.43.44) with:"
echo "  OPENAI_WHISPER_BASE_URL=http://100.65.129.114:5001/v1"
echo "  OPENAI_TTS_BASE_URL=http://100.65.129.114:5002/v1"
