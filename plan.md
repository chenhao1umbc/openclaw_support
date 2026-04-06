# Plan
**Task**: Migrate openclaw_support from pip+venv+Python3.12 to uv+pyproject.toml+Python3.13
**Date**: 2026-04-06
**Stack**: Python 3.13, uv, FastAPI, mlx-whisper, piper-tts, bash

> Only the reviewer may mark tasks [x].

## Sub-tasks
- [ ] 1. pyproject.toml: create pyproject.toml with all dependencies, replacing requirements.txt
- [ ] 2. server scripts: update sys.path python3.12 → python3.13 in whisper_server.py and tts_server.py
- [ ] 3. setup.sh: replace pip+venv with uv venv + uv pip install; update Python paths to 3.13; remove requirements.txt reference
- [ ] 4. cleanup: delete requirements.txt; commit and push
- [ ] 5. robustness: add startup readiness guard + health endpoint to both servers; add ThrottleInterval to launchd plists to prevent rapid crash-restart loops
