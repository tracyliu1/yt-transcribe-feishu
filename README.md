# yt-transcribe-feishu

YouTube RSS → 音频下载 → 通义听悟转写 → 飞书文档 → 飞书通知

> 如果你是 Hermes，不要读这个文件，去读 `PROMPT.md`。

## 目录

- [yt-transcribe-feishu](#yt-transcribe-feishu)
  - [目录](#目录)
  - [快速开始](#快速开始)
  - [环境变量](#环境变量)
  - [用法](#用法)
  - [文件结构](#文件结构)
  - [注意事项](#注意事项)

## 快速开始

```bash
# 1. 进入仓库
cd /home/liudi/skills/yt-transcribe-feishu

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install chromium

# 4. 复制配置文件
cp .env.example .env
cp config/channels.json.example config/channels.json
# 编辑 .env 和 config/channels.json，填入真实值

# 5. 启动 Chrome CDP（或让脚本自动启动）
# 脚本会自动尝试连接 CDP_URL；如果未运行，会用 CHROME_PROFILE_DIR 启动 Chrome

# 6. 运行流水线
python3 -m yt_transcribe_feishu.pipeline
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CDP_URL` | Chrome CDP 地址 | `http://127.0.0.1:9226` |
| `CHROME_PROFILE_DIR` | Chrome profile 目录 | `~/.config/google-chrome-tingwu` |
| `CHROME_DISPLAY` | X11 DISPLAY | `:10` |
| `TINGWU_STATE_FILE` | 登录态保存文件 | `~/.config/yt-transcribe-feishu/tingwu_state.json` |
| `TINGWU_TRANSCRIBE_TIMEOUT` | 转写等待超时（秒） | `180` |
| `TINGWU_POLL_INTERVAL` | 转写轮询间隔（秒） | `5` |
| `FEISHU_APP_ID` | 飞书应用 ID | - |
| `FEISHU_APP_SECRET` | 飞书应用 Secret | - |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook | - |
| `FEISHU_USER_OPEN_ID` | 接收通知的用户 open_id | - |
| `FEISHU_GROUP_NOTIFY` | 是否发送群通知 | `1` |
| `FEISHU_GROUP_ONLY` | 是否只发群通知 | `0` |
| `RUN_CMD_TIMEOUT` | 命令执行超时（秒） | `180` |
| `YOUTUBE_CHANNELS_CONFIG` | 频道配置文件 | `./config/channels.json` |
| `YOUTUBE_RSS_STATE_FILE` | 已处理视频状态文件 | `./data/processed.json` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

## 用法

```bash
# 运行完整流水线
python3 -m yt_transcribe_feishu.pipeline

# 测试模式（不执行实际流程，仅加载配置）
python3 -m yt_transcribe_feishu.pipeline --test

# 单独保存通义听悟登录态（登录成功后执行）
python3 -m yt_transcribe_feishu.tingwu --save-login

# 单独检查 RSS
python3 -m yt_transcribe_feishu.rss --output /tmp/new_videos.json --limit 1

# Hermes / cron 入口（详见 PROMPT.md）
./run.sh
```

## 文件结构

```
yt-transcribe-feishu/
├── yt_transcribe_feishu/     # Python 包
│   ├── __init__.py
│   ├── config.py             # 配置加载
│   ├── utils.py              # 通用工具（run_cmd、日志）
│   ├── browser.py            # Chrome CDP 管理
│   ├── rss.py                # YouTube RSS 检查
│   ├── download.py           # 音频下载
│   ├── tingwu.py             # 通义听悟上传/提取
│   ├── feishu.py             # 飞书文档/通知
│   └── pipeline.py           # 主流程
├── config/
│   ├── channels.json         # 本地频道配置（未跟踪）
│   └── channels.json.example # 示例配置
├── data/
│   ├── processed.json        # 已处理视频记录（未跟踪）
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── .env                      # 本地 secrets（未跟踪）
├── .env.example              # secrets 示例
├── .gitignore
├── run.sh                    # Hermes / cron 入口
├── PROMPT.md                 # 给 Hermes 看的操作说明
├── requirements.txt
└── README.md
```

## 注意事项

1. **不要提交 secrets**：`.env`、`config/channels.json`、`data/processed.json`、`tingwu_state.json` 都已加入 `.gitignore`。
2. **超时**：所有命令默认超时 180 秒（`RUN_CMD_TIMEOUT`）。转写等待默认 180 秒，代码硬上限 300 秒，不会出现 Hermes 之前那种 60 分钟超时。
3. **Chrome profile**：默认使用 `~/.config/google-chrome-tingwu`。如果实际 profile 路径不同，请在 `.env` 中设置 `CHROME_PROFILE_DIR`。
4. **登录态**：脚本启动时会自动加载 `~/.config/google-chrome-tingwu/tingwu_cookies.json`。如果还是提示未登录，先手动登录通义听悟，然后运行 `python3 -m yt_transcribe_feishu.tingwu --save-login` 保存状态。
5. **验证**：每次修改后请先用 `--test` 模式或一次完整运行验证，不要“等下次”。
