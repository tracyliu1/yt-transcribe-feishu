# Hermes 操作指南

你是 Hermes，负责周期性执行 `yt-transcribe-feishu` 流水线。请严格按以下指令操作，不要自行发挥。

## 1. 你要执行的命令

每隔 10 分钟执行一次：

```bash
/home/liudi/skills/yt-transcribe-feishu/run.sh
```

不要 `cd`、不要激活虚拟环境、不要改命令。`run.sh` 会自己处理。

## 2. 周期任务配置

用 cron，每 10 分钟一次：

```bash
*/10 * * * * /home/liudi/skills/yt-transcribe-feishu/run.sh
```

## 3. 如何判断结果

只看退出码，不要分析日志内容：

| 退出码 | 含义 | 你要做什么 |
|--------|------|-----------|
| `0` | 正常。可能输出 `[SILENT]`（没有新视频），也可能输出 `文档已生成: https://...` | 什么都不用做 |
| `1` | 出错了 | 脚本已经自动发送飞书错误通知，你不用额外通知 |

**重要**：输出 `[SILENT]` 不是错误，只是表示当前没有新视频。

## 4. 禁止事项

- 不要修改仓库里的代码。
- 不要修改 `.env`、`config/channels.json`、`data/processed.json`。
- 不要用 `python3 -m yt_transcribe_feishu.pipeline` 直接运行，必须用 `run.sh`。
- 不要手动登录通义听悟，登录态由脚本自动维护。

## 5. 如果连续失败

如果连续 3 次退出码都是 `1`：

1. 检查 Chrome CDP 是否在跑：`curl -s http://127.0.0.1:9226/json/version`
2. 如果 CDP 没跑，先启动 Chrome（参考 README.md）。
3. 如果还失败，通知主人，不要自己修代码。

## 6. 文件位置

- 仓库：`/home/liudi/skills/yt-transcribe-feishu`
- 入口脚本：`/home/liudi/skills/yt-transcribe-feishu/run.sh`
- 配置：`.env` 和 `config/channels.json`（已存在，不要改）
- 日志：脚本直接输出到 stdout/stderr，由你的调度系统捕获

## 7. 这条指令最重要

**你只负责定时调用 `/home/liudi/skills/yt-transcribe-feishu/run.sh`，其他什么都不做。**
