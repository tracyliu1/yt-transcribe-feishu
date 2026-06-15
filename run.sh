#!/usr/bin/env bash
# YouTube → 通义听悟 → 飞书文档 流水线入口脚本
# 用法：./run.sh
# Hermes / cron 直接调用这个脚本即可，不需要手动进目录、激活虚拟环境。

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# 优先使用虚拟环境里的 Python；没有就用系统 python3
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

export PYTHONPATH="${REPO_DIR}:${PYTHONPATH:-}"

exec "$PYTHON" -m yt_transcribe_feishu.pipeline "$@"
