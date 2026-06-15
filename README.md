# yt-transcribe-feishu

YouTube RSS → 音频下载 → 通义听悟转写 → 飞书文档 → 飞书通知

## 1. 给 Hermes 看的一句话

Hermes 每隔几分钟执行一次这个命令即可：

```bash
/home/liudi/skills/yt-transcribe-feishu/run.sh
```

不用 `cd`，不用激活虚拟环境，脚本自己会处理。

## 2. 人类首次部署步骤

```bash
# 1. 进入仓库
cd /home/liudi/skills/yt-transcribe-feishu

# 2. 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 3. 复制配置文件
cp .env.example .env
cp config/channels.json.example config/channels.json

# 4. 编辑 .env 和 config/channels.json，填入真实值
#    .env 里主要是飞书凭证和 Chrome CDP 配置
#    config/channels.json 里填要监控的 YouTube 频道 ID

# 5. 手动跑一次，确认能通
./run.sh
```

## 3. Hermes 周期任务配置示例

在 Hermes 里加一条定时任务，比如每 10 分钟执行一次：

```bash
*/10 * * * * /home/liudi/skills/yt-transcribe-feishu/run.sh
```

或者让 Hermes 每分钟轮询（更及时）：

```bash
* * * * * /home/liudi/skills/yt-transcribe-feishu/run.sh
```

## 4. 运行输出与退出码

| 场景 | 输出 | 退出码 |
|------|------|--------|
| 没有新视频 | `[SILENT]` | `0` |
| 成功生成文档 | `文档已生成: https://...` | `0` |
| 出错 | 错误日志 + 飞书通知 | `1` |

Hermes 判断逻辑建议：

- 退出码 `0` 就是正常，不用管 `[SILENT]`。
- 退出码 `1` 表示失败，脚本已经自动发飞书错误通知。

## 5. 文件说明

```
yt-transcribe-feishu/
├── run.sh                      # Hermes / cron 入口
├── .env                        # 本地 secrets（git 忽略）
├── .env.example                # secrets 示例
├── config/channels.json        # YouTube 频道配置（git 忽略）
├── config/channels.json.example
├── data/processed.json         # 已处理视频记录（git 忽略）
├── yt_transcribe_feishu/       # Python 代码
└── README.md                   # 本文件
```

## 6. 常见操作

```bash
# 手动跑一次
./run.sh

# 测试模式（不执行实际流程，只加载配置）
./run.sh --test

# 单独保存通义听悟登录态（登录成功后执行）
python3 -m yt_transcribe_feishu.tingwu --save-login
```

## 7. 注意事项

1. **不要提交 secrets**：`.env`、`config/channels.json`、`data/processed.json` 已在 `.gitignore` 里。
2. **Chrome CDP**：默认连接 `http://127.0.0.1:9226`，使用 profile `~/.config/google-chrome-tingwu`。如果实际配置不同，改 `.env`。
3. **超时**：所有命令 180s，转写等待默认 180s，代码硬上限 300s，不会出现 60 分钟超时。
4. **登录态**：脚本启动时会自动加载 `~/.config/google-chrome-tingwu/tingwu_cookies.json`，如果还是提示未登录，手动登录一次再执行 `python3 -m yt_transcribe_feishu.tingwu --save-login`。
5. **每次修改后必须验证**：跑一遍 `./run.sh`，不要“等下次”。

## 8. 环境变量速查

| 变量 | 作用 | 默认值 |
|------|------|--------|
| `CDP_URL` | Chrome CDP 地址 | `http://127.0.0.1:9226` |
| `CHROME_PROFILE_DIR` | Chrome profile | `~/.config/google-chrome-tingwu` |
| `FEISHU_APP_ID` | 飞书应用 ID | 空 |
| `FEISHU_APP_SECRET` | 飞书应用 Secret | 空 |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook | 空 |
| `FEISHU_USER_OPEN_ID` | 接收通知的个人 open_id | 空 |
| `YOUTUBE_CHANNELS_CONFIG` | 频道配置文件 | `./config/channels.json` |
| `YOUTUBE_RSS_STATE_FILE` | 已处理记录 | `./data/processed.json` |
| `TINGWU_TRANSCRIBE_TIMEOUT` | 转写等待秒数 | `180`（最大 `300`） |
| `RUN_CMD_TIMEOUT` | 命令超时秒数 | `180` |
