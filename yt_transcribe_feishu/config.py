import os
from pathlib import Path

from dotenv import load_dotenv

_repo_root = Path(__file__).resolve().parent.parent

# Load environment variables from .env in repo root (if present).
load_dotenv(_repo_root / ".env")


def _expand(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


# Chrome / CDP
CDP_URL = os.getenv("CDP_URL", "http://127.0.0.1:9226")
CHROME_PROFILE_DIR = _expand(os.getenv("CHROME_PROFILE_DIR", "~/.config/google-chrome-tingwu"))
CHROME_DISPLAY = os.getenv("CHROME_DISPLAY", os.environ.get("DISPLAY", ":10"))

# State files
STATE_DIR = _expand(os.getenv("STATE_DIR", "~/.config/yt-transcribe-feishu"))
TINGWU_STATE_FILE = _expand(
    os.getenv("TINGWU_STATE_FILE", os.path.join(STATE_DIR, "tingwu_state.json"))
)
YOUTUBE_RSS_STATE_FILE = _expand(
    os.getenv("YOUTUBE_RSS_STATE_FILE", str(_repo_root / "data" / "processed.json"))
)
YOUTUBE_CHANNELS_CONFIG = _expand(
    os.getenv("YOUTUBE_CHANNELS_CONFIG", str(_repo_root / "config" / "channels.json"))
)

# Feishu
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "")
FEISHU_USER_OPEN_ID = os.getenv("FEISHU_USER_OPEN_ID", "")
FEISHU_GROUP_NOTIFY = os.getenv("FEISHU_GROUP_NOTIFY", "").lower() in ("1", "true", "yes", "on")
FEISHU_GROUP_ONLY = os.getenv("FEISHU_GROUP_ONLY", "").lower() in ("1", "true", "yes", "on")

# Timeouts (seconds). Per requirement: no timeout > 5 minutes (300s).
RUN_CMD_TIMEOUT = min(int(os.getenv("RUN_CMD_TIMEOUT", "180")), 300)
# Single-video transcription should finish within 3 minutes; hard cap at 5 min.
TINGWU_TRANSCRIBE_TIMEOUT = min(int(os.getenv("TINGWU_TRANSCRIBE_TIMEOUT", "180")), 300)
TINGWU_POLL_INTERVAL = int(os.getenv("TINGWU_POLL_INTERVAL", "5"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
