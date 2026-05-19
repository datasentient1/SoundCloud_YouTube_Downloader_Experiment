#!/usr/bin/env bash
set -euo pipefail

python3 -m compileall backend
python3 - <<'PY'
from backend.app.downloader import command_for, infer_source, normalize_url
from pathlib import Path

assert infer_source("https://www.youtube.com/playlist?list=test") == "youtube"
assert infer_source("https://soundcloud.com/example/sets/catalog") == "soundcloud"
assert normalize_url("https://soundcloud.com/artist/track?in=owner/sets/catalog&si=abc") == "https://soundcloud.com/owner/sets/catalog"
assert normalize_url("https://soundcloud.com/owner/sets/catalog?utm_source=clipboard") == "https://soundcloud.com/owner/sets/catalog"
yt_cmd = command_for("youtube", "https://youtu.be/example", Path("/tmp/out"), Path("/tmp/job"))
assert yt_cmd[0] == "yt-dlp"
assert "--newline" in yt_cmd
assert "--format" in yt_cmd
assert "--impersonate" in yt_cmd
assert command_for("soundcloud", "https://soundcloud.com/example/sets/catalog", Path("/tmp/out"))[0] == "scdl"
print("smoke checks passed")
PY
