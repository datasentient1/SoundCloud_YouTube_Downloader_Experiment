#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall backend
python3 - <<'PY'
from backend.app.downloader import command_for, infer_source
from pathlib import Path

assert infer_source("https://www.youtube.com/playlist?list=test") == "youtube"
assert infer_source("https://soundcloud.com/example/sets/catalog") == "soundcloud"
assert command_for("youtube", "https://youtu.be/example", Path("/tmp/out"))[0] == "yt-dlp"
assert command_for("soundcloud", "https://soundcloud.com/example/sets/catalog", Path("/tmp/out"))[0] == "scdl"
print("smoke checks passed")
PY
