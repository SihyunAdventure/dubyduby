#!/usr/bin/env bash
# First-time bootstrap. Idempotent — safe to re-run.
# - Python 3.12 venv + supertonic pip install
# - yt-dlp binary download
# - .env init from .env.example
# - ffmpeg presence check (system PATH)
set -e
cd "$(dirname "$0")/.."

echo "[setup] dubyduby bootstrap"

# 1. uv check
if ! command -v uv >/dev/null; then
  echo "[setup] uv missing — install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

# 2. Python 3.12 venv
if [ ! -d .venv ]; then
  echo "[setup] creating Python 3.12 venv..."
  uv venv --python 3.12 .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 3. Python deps (supertonic includes onnxruntime / numpy / soundfile)
echo "[setup] installing supertonic + deps..."
uv pip install -q supertonic

# 4. Pretendard font (for subtitles) — extract TTF from release zip
mkdir -p fonts
if [ ! -f fonts/Pretendard-Bold.ttf ]; then
  echo "[setup] downloading Pretendard..."
  TMP_ZIP=$(mktemp -t pretendard).zip
  curl -sL -o "$TMP_ZIP" \
    "https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip"
  unzip -jq "$TMP_ZIP" "public/static/alternative/Pretendard-Bold.ttf" -d fonts/
  rm -f "$TMP_ZIP"
fi

# 5. yt-dlp binary
mkdir -p binaries
if [ ! -x binaries/yt-dlp ]; then
  echo "[setup] downloading yt-dlp..."
  case "$(uname -s)" in
    Darwin)   URL=https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos ;;
    Linux)    URL=https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux ;;
    *)        echo "[setup] unsupported OS"; exit 1 ;;
  esac
  curl -sL -o binaries/yt-dlp "$URL"
  chmod +x binaries/yt-dlp
fi

# 6. ffmpeg/ffprobe in PATH — libass required for subtitle burn-in
# Check both system ffmpeg and ffmpeg-full (keg-only on macOS)
has_libass=0
if command -v ffmpeg >/dev/null && ffmpeg -hide_banner -filters 2>&1 | grep -q "subtitles"; then
  has_libass=1
fi
if [ "$has_libass" = "0" ] && ls /opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg >/dev/null 2>&1; then
  if /opt/homebrew/Cellar/ffmpeg-full/*/bin/ffmpeg -hide_banner -filters 2>&1 | grep -q "subtitles"; then
    has_libass=1
  fi
fi
need_ffmpeg_full=$([ "$has_libass" = "0" ] && echo 1 || echo 0)
if [ "$need_ffmpeg_full" = "1" ]; then
  case "$(uname -s)" in
    Darwin)
      echo "[setup] installing ffmpeg-full (includes libass for subtitle rendering)..."
      brew install ffmpeg-full || {
        echo "  Manual install needed: brew install ffmpeg-full"; exit 1; }
      ;;
    Linux)
      echo "[setup] install ffmpeg with libass:"
      echo "  apt install ffmpeg libavfilter-extra   # Ubuntu/Debian"
      echo "  dnf install ffmpeg-free libass         # Fedora"
      exit 1
      ;;
    *)
      echo "[setup] unsupported OS for auto ffmpeg install"
      exit 1
      ;;
  esac
fi
for bin in ffprobe jq; do
  if ! command -v "$bin" >/dev/null; then
    echo "[setup] $bin missing — install via brew/apt"
    exit 1
  fi
done

# 6. .env init
if [ ! -f .env ]; then
  echo "[setup] copying .env.example → .env (edit to add SONIOX_API_KEY)"
  cp .env.example .env
fi

# 7. Git hooks — wire repo-owned hooks (pre-commit safety net) if in a git checkout
if [ -d .git ] || git rev-parse --git-dir >/dev/null 2>&1; then
  current_hooks_path=$(git config --get core.hooksPath || echo "")
  if [ "$current_hooks_path" != "scripts/git-hooks" ]; then
    echo "[setup] enabling repo-owned git hooks (core.hooksPath=scripts/git-hooks)..."
    git config core.hooksPath scripts/git-hooks
  fi
fi

echo "[setup] ready. Supertonic model (~260MB) downloads on first synth (automatic)."
echo "[setup] next: bash scripts/dub.sh <youtube_url>"
