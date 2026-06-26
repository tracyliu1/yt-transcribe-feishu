import json
from datetime import datetime

import requests

from . import config


def _get_token():
    """Get Feishu tenant access token."""
    if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET:
        raise RuntimeError("未配置飞书应用凭证")

    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        headers={"Content-Type": "application/json"},
        json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
        timeout=10,
    )
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {result}")
    return result["tenant_access_token"]


def create_document(content: dict) -> str:
    """Create a Feishu doc and populate it with blocks."""
    title = _build_title(content)
    token = _get_token()

    resp = requests.post(
        "https://open.feishu.cn/open-apis/docx/v1/documents",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"title": title},
        timeout=10,
    )
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"创建文档失败: {result}")

    doc_id = result["data"]["document"]["document_id"]
    blocks = _build_blocks(content)
    _batch_write_blocks(doc_id, blocks, token)

    url = f"https://bytedance.larkoffice.com/docx/{doc_id}"
    return url


def _build_title(content):
    """Build title in format: YYYY-MM-DD title - author (max 50 chars for title part)."""
    import re

    publish_date = content.get("publish_date", "")
    author = content.get("author", "")
    title = content.get("title", "未命名文档")

    # Sanitize title same as download.py: replace special chars, collapse spaces, truncate
    safe_title = re.sub(r'[\\/:*?"<>|]', ' ', title)
    safe_title = re.sub(r'\s+', ' ', safe_title).strip()
    if len(safe_title) > 50:
        safe_title = safe_title[:50].rstrip() + '...'

    parts = []
    if publish_date:
        parts.append(publish_date)
    parts.append(safe_title)
    if author:
        parts.append(f"- {author}")
    return " ".join(parts)


def _make_heading(text):
    return {
        "block_type": 3,
        "heading1": {"elements": [{"text_run": {"content": text}}]},
    }


def _make_text(text, bold=False):
    style = {"bold": True} if bold else {}
    return {
        "block_type": 2,
        "text": {
            "elements": [
                {"text_run": {"content": text, "text_element_style": style}}
            ]
        },
    }


def _build_blocks(content):
    blocks = []

    publish_date = content.get("publish_date", "")
    author = content.get("author", "")
    title = content.get("title", "未命名")

    doc_title_parts = []
    if publish_date:
        doc_title_parts.append(f"[{publish_date}]")
    doc_title_parts.append(title)
    if author:
        doc_title_parts.append(f"- {author}")
    blocks.append(_make_heading(" ".join(doc_title_parts)))

    blocks.append(_make_heading("基本信息"))
    if author:
        blocks.append(_make_text(f"作者/频道：{author}"))
    if publish_date:
        blocks.append(_make_text(f"发布时间：{publish_date}"))

    youtube_url = content.get("youtube_url", "")
    if youtube_url:
        blocks.append(_make_text(f"YouTube链接：{youtube_url}"))

    tingwu_url = content.get("source_url", "")
    if tingwu_url:
        blocks.append(_make_text(f"通义听悟链接：{tingwu_url}"))

    blocks.append(_make_heading("关键词"))
    keywords = content.get("keywords", [])
    blocks.append(_make_text("、".join(keywords)))

    blocks.append(_make_heading("AI摘要"))
    blocks.append(_make_text(content.get("ai_summary", "")))

    qa_list = content.get("qa", [])
    if qa_list:
        blocks.append(_make_heading("问答回顾"))
        for qa in qa_list:
            blocks.append(_make_text(qa.get("question", ""), bold=True))
            blocks.append(_make_text(qa.get("answer", "")))

    full_text = content.get("full_text", [])
    if full_text:
        blocks.append(_make_heading("完整原文"))
        for para in full_text:
            time_str = para.get("time", "")
            speaker = para.get("speaker", "")
            text = para.get("content", "")
            line = f"[{time_str}] {speaker}：{text}"
            blocks.append(_make_text(line))

    return blocks


def _batch_write_blocks(doc_id, blocks, token):
    """Batch write blocks; raise on any failure."""
    batch_size = 50
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i : i + batch_size]
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"children": batch},
            timeout=30,
        )
        result = resp.json()
        if result.get("code") != 0:
            error_msg = f"Batch {i // batch_size + 1} failed: {result}"
            print(error_msg)
            raise RuntimeError(error_msg)
        print(f"Batch {i // batch_size + 1}: success ({len(batch)} blocks)")


def send_notification(doc_url: str, video_title: str) -> bool:
    """Send notification to Feishu group webhook and/or personal message."""
    message = f"新视频转录完成：{video_title}\n\n文档链接：{doc_url}"
    group_sent = False

    if config.FEISHU_WEBHOOK_URL and (config.FEISHU_GROUP_NOTIFY or config.FEISHU_GROUP_ONLY):
        try:
            resp = requests.post(
                config.FEISHU_WEBHOOK_URL,
                headers={"Content-Type": "application/json"},
                json={"msg_type": "text", "content": {"text": message}},
                timeout=10,
            )
            result = resp.json()
            if result.get("code") == 0:
                print("群聊消息已发送 (webhook)")
                group_sent = True
            else:
                print(f"群聊消息发送失败: {result}")
        except Exception as e:
            print(f"群聊消息发送异常: {e}")
    elif config.FEISHU_WEBHOOK_URL and not (config.FEISHU_GROUP_NOTIFY or config.FEISHU_GROUP_ONLY):
        print("群聊通知已禁用（设置 FEISHU_GROUP_NOTIFY=1 或 FEISHU_GROUP_ONLY=1 开启）")

    if config.FEISHU_GROUP_ONLY:
        print("FEISHU_GROUP_ONLY=1，跳过个人消息")
        return group_sent

    if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET or not config.FEISHU_USER_OPEN_ID:
        print("未配置飞书个人通知，跳过")
        return group_sent

    token = _get_token()
    resp = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params={"receive_id_type": "open_id"},
        json={
            "receive_id": config.FEISHU_USER_OPEN_ID,
            "msg_type": "text",
            "content": json.dumps({"text": message}),
        },
        timeout=10,
    )
    result = resp.json()
    if result.get("code") == 0:
        print("个人消息已发送")
        return True
    print(f"个人消息发送失败: {result}")
    return group_sent


def send_error_notification(error_msg: str) -> bool:
    """Send an error notification to the configured Feishu user."""
    message = (
        f"YouTube流水线出错：\n{error_msg}\n\n"
        f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET or not config.FEISHU_USER_OPEN_ID:
        print("未配置飞书应用凭证，无法发送错误通知")
        return False

    try:
        token = _get_token()
        resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params={"receive_id_type": "open_id"},
            json={
                "receive_id": config.FEISHU_USER_OPEN_ID,
                "msg_type": "text",
                "content": json.dumps({"text": message}),
            },
            timeout=10,
        )
        result = resp.json()
        if result.get("code") == 0:
            print("错误通知已发送")
            return True
        print(f"发送错误通知失败: {result}")
        return False
    except Exception as e:
        print(f"发送错误通知异常: {e}")
        return False
