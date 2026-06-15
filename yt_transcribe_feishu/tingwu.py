import argparse
import json
import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import browser, config


def load_cdp_cookies(session, cookie_file: str = None) -> bool:
    """Load cookies exported from Chrome CDP (Network.getCookies)."""
    cookie_file = cookie_file or os.path.expanduser(
        "~/.config/google-chrome-tingwu/tingwu_cookies.json"
    )
    if not os.path.exists(cookie_file):
        return False

    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    valid = []
    for c in cookies:
        try:
            expires = c.get("expires", -1)
            if expires == -1:
                expires = -1
            else:
                expires = int(expires)
            valid.append(
                {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ""),
                    "path": c.get("path", "/"),
                    "expires": expires,
                    "httpOnly": c.get("httpOnly", False),
                    "secure": c.get("secure", False),
                    "sameSite": c.get("sameSite") or "None",
                }
            )
        except Exception:
            continue

    ctx = session.context
    try:
        ctx.add_cookies(valid)
        print(f"[{_now()}] 已从 {cookie_file} 加载 {len(valid)} 个 cookie")
        return True
    except Exception as e:
        print(f"[{_now()}] [WARN] 加载 cookies 失败: {e}")
        return False


def check_login(session):
    """Check if Tingwu is logged in by looking for the login button."""
    page = session.page
    page.goto("https://tingwu.aliyun.com/", timeout=30000)
    page.wait_for_timeout(3000)
    return page.query_selector('text=立即登录') is None


def restore_login(session, state_file=None):
    """Restore Tingwu login state from a JSON file."""
    state_file = state_file or config.TINGWU_STATE_FILE
    if not os.path.exists(state_file):
        return False

    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    ctx = session.context
    for c in state.get("cookies", []):
        try:
            ctx.add_cookie(c)
        except Exception:
            pass

    page = session.page
    for k, v in state.get("localStorage", {}).items():
        try:
            page.evaluate("(k, v) => localStorage.setItem(k, v)", k, v)
        except Exception:
            pass

    page.goto("https://tingwu.aliyun.com/home", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    content = page.content()
    is_logged_in = "立即登录" not in content and (
        "我的记录" in content or "退出" in content
    )
    return is_logged_in


def save_login(session, state_file=None):
    """Save current Tingwu login state to a JSON file."""
    state_file = state_file or config.TINGWU_STATE_FILE
    ctx = session.context
    page = session.page

    cookies = ctx.cookies("https://tingwu.aliyun.com")
    local_storage = page.evaluate(
        "() => Object.fromEntries(Object.entries(localStorage))"
    )

    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(
            {"cookies": cookies, "localStorage": local_storage},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"登录态已保存: {len(cookies)} cookies, {len(local_storage)} localStorage -> {state_file}")


def upload_and_transcribe(
    session, audio_path: str, timeout: int = None, poll_interval: int = None
):
    """Upload audio to Tingwu and wait for transcription to complete.

    Returns {"url": <result url>, "success": True} when the transcript page
    shows content. The actual content extraction is done by extract_content().
    """
    timeout = timeout or config.TINGWU_TRANSCRIBE_TIMEOUT
    poll_interval = poll_interval or config.TINGWU_POLL_INTERVAL

    page = session.page
    basename = Path(audio_path).stem

    page.goto("https://tingwu.aliyun.com/home", wait_until="domcontentloaded")
    time.sleep(3)

    print(f"[{_now()}] 点击'上传音视频'...")
    upload_btn = page.get_by_text("上传音视频").first
    upload_btn.wait_for(state="visible", timeout=30000)
    upload_btn.click(force=True)

    print(f"[{_now()}] 点击'上传本地音视频文件'...")
    local_upload_btn = page.get_by_text("上传本地音视频文件").first
    local_upload_btn.wait_for(state="visible", timeout=30000)
    local_upload_btn.click(force=True)

    print(f"[{_now()}] 设置文件...")
    inputs = page.locator('input[type="file"]').all()
    if not inputs:
        raise RuntimeError("找不到文件 input")
    inputs[0].set_input_files(audio_path)

    # Wait for the file to appear in the UI and the start button to become
    # available. Large files may take a few seconds to register.
    print(f"[{_now()}] 等待文件上传 UI 就绪...")
    page.locator(f'text="{basename}"').first.wait_for(state="visible", timeout=60000)
    page.get_by_text("开始转写").first.wait_for(state="visible", timeout=60000)

    print(f"[{_now()}] 点击'开始转写'...")
    page.get_by_text("开始转写").first.click(force=True)
    print(f"[{_now()}] 已提交")

    # After submission Tingwu creates a record card on the home page. We poll
    # the home page, click the card, and then wait for the result page to show
    # transcript content.
    start = time.time()
    result_url = None
    while time.time() - start < timeout:
        page.goto("https://tingwu.aliyun.com/home", wait_until="domcontentloaded")
        time.sleep(3)

        body_text = page.inner_text("body")
        cards = page.locator(f'text="{basename}"').all()

        for card in cards:
            try:
                card_text = card.inner_text()
                if (
                    basename in card_text
                    and "上传失败" not in card_text
                    and "转写失败" not in card_text
                ):
                    print(f"[{_now()}] 发现记录，打开结果页: {basename}")
                    card.click(force=True)
                    time.sleep(3)
                    if "/doc/transcripts/" in page.url:
                        result_url = page.url
                    break
            except Exception:
                continue

        if result_url:
            break

        # Check for a failed upload of this specific file.
        if basename in body_text:
            lines = body_text.split("\n")
            for i, line in enumerate(lines):
                if basename in line:
                    context = "\n".join(lines[max(0, i - 2) : i + 3])
                    if "上传失败" in context or "转写失败" in context:
                        raise RuntimeError(f"上传/转写失败: {basename}")
                    break

        if "转写中" in body_text:
            print(f"[{_now()}] 仍在转写中...")

        time.sleep(poll_interval)

    if not result_url:
        raise RuntimeError(f"等待转写超时: {basename}")

    print(f"[{_now()}] 结果页: {result_url}")

    # Poll the result page until transcript content appears.
    while time.time() - start < timeout:
        page.reload(wait_until="domcontentloaded")
        time.sleep(3)

        body_text = page.inner_text("body")
        if "原文" in body_text and "发言人" in body_text:
            print(f"[{_now()}] 转写完成")
            return {"url": result_url, "success": True}

        if "转写失败" in body_text or "上传失败" in body_text:
            raise RuntimeError(f"上传/转写失败: {basename}")

        if "转写中" in body_text:
            print(f"[{_now()}] 仍在转写中...")

        time.sleep(poll_interval)

    raise RuntimeError(f"等待转写结果超时: {basename}")


def _extract_transcript(page):
    """Extract transcript text grouped by speaker."""
    try:
        body_text = page.evaluate("() => document.body.innerText")
        lines = body_text.split("\n")
        transcript_lines = []
        in_transcript = False

        skip_phrases = [
            "正文",
            "记录你的灵感和思考...",
            "万语千言，心领神悟",
            "倍速",
            "成功添加到转写列表",
            "更多AI总结加载中",
            "使用高峰期可能稍有延迟",
            "请稍后查看",
            "在这里记录你的想法吧",
            "可以插入图片和表格哦",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if any(phrase in line for phrase in skip_phrases):
                continue
            if "发言人" in line and len(line) < 20:
                in_transcript = True
                transcript_lines.append(f"\n【{line}】")
            elif in_transcript and len(line) > 3:
                if not all(c in "0123456789:." for c in line):
                    transcript_lines.append(line)

        return "\n".join(transcript_lines).strip()[:20000]
    except Exception as e:
        print(f"[WARN] 提取转写失败: {e}")
        return ""


def _extract_summary(page):
    """Extract AI summary (full summary + chapter overview)."""
    try:
        body_text = page.evaluate("() => document.body.innerText")
        parts = []

        if "全文概要" in body_text:
            idx = body_text.index("全文概要")
            end_idx = body_text.find("章节速览", idx)
            if end_idx == -1:
                end_idx = body_text.find("发言总结", idx)
            if end_idx == -1:
                end_idx = idx + 3000
            parts.append("【全文概要】\n" + body_text[idx:end_idx].strip())

        if "章节速览" in body_text:
            idx = body_text.index("章节速览")
            end_idx = body_text.find("发言总结", idx)
            if end_idx == -1:
                end_idx = body_text.find("原文", idx)
            if end_idx == -1:
                end_idx = idx + 3000
            parts.append("\n\n【章节速览】\n" + body_text[idx:end_idx].strip())

        return "\n".join(parts)[:10000]
    except Exception as e:
        print(f"[WARN] 提取总结失败: {e}")
        return ""


def extract_content(session, url: str, meta: dict = None):
    """Extract full content from a Tingwu result page.

    Requires clicking "展开全部" and scrolling to load lazy content.
    """
    page = session.page
    meta = meta or {}

    trans_result = None

    def handle_response(response):
        nonlocal trans_result
        if "getTransResult" in response.url and response.status == 200:
            try:
                data = response.json()
                if data.get("data") and data["data"].get("result"):
                    trans_result = data["data"]
            except Exception:
                pass

    page.on("response", handle_response)
    page.goto(url, timeout=60000)
    page.wait_for_timeout(5000)

    print("点击展开全部...")
    for _ in range(5):
        expand_btns = page.locator("text=展开全部").all()
        clicked = False
        for btn in expand_btns:
            try:
                if btn.is_visible():
                    btn.click()
                    clicked = True
                    time.sleep(2)
            except Exception:
                pass
        if not clicked:
            break
        time.sleep(2)

    print("滚动加载全部内容...")
    for _ in range(20):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)
    for _ in range(10):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

    page.wait_for_timeout(5000)

    body_text = page.evaluate("() => document.body.innerText")
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]

    title = page.evaluate("() => document.title") or "未命名"
    upstream_title = meta.get("title", "")
    if upstream_title and len(upstream_title) > 5:
        title = upstream_title
    elif len(title) < 15 or title == "通义听悟":
        for line in lines:
            if (
                line
                and len(line) > 15
                and len(line) < 100
                and line not in ["通义听悟", "立即登录", "我的记录", "上传音视频"]
                and any(kw in line for kw in ["解读", "分析", "讨论", "回顾", "展望", "深度"])
            ):
                title = line
                break
        if title == "未命名" or len(title) < 15:
            for line in lines:
                if (
                    line
                    and len(line) > 15
                    and len(line) < 100
                    and line not in ["通义听悟", "立即登录", "我的记录", "上传音视频"]
                ):
                    title = line
                    break

    title = title.replace("...展开全部", "").replace("展开全部", "").strip()

    ai_summary = ""
    in_summary = False
    for line in lines:
        if line == "全文概要":
            in_summary = True
            continue
        if in_summary:
            if line in ["章节速览", "发言总结", "要点回顾", "原文"]:
                break
            if line == "展开全部":
                continue
            ai_summary += line + "\n"

    summary_points = []
    seen_points = set()
    for paragraph in ai_summary.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        points = [p.strip() for p in paragraph.split("。") if p.strip()]
        for point in points:
            if len(point) > 10:
                point_with_period = point + "。"
                is_duplicate = False
                for seen in summary_points:
                    if point_with_period[:50] == seen[:50]:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    summary_points.append(point_with_period)
                    seen_points.add(point_with_period)
    if not summary_points:
        summary_points = [ai_summary.strip()]

    keywords = []
    in_keywords = False
    for line in lines:
        if line == "关键词":
            in_keywords = True
            continue
        if in_keywords:
            if line in ["展开全部", "全文概要", "章节速览", "原文"]:
                break
            if len(line) < 20 and not line.startswith("00:"):
                keywords.append(line)

    chapters = []
    in_chapters = False
    current_chapter = None
    for line in lines:
        if line == "章节速览":
            in_chapters = True
            continue
        if in_chapters:
            if line in ["发言总结", "要点回顾", "原文", "展开全部章节"]:
                if current_chapter:
                    chapters.append(current_chapter)
                break
            if re.match(r"^\d{2}:\d{2}$", line):
                if current_chapter:
                    chapters.append(current_chapter)
                current_chapter = {"time": line, "title": "", "summary": ""}
            elif current_chapter and not current_chapter["title"]:
                current_chapter["title"] = line
            elif current_chapter:
                current_chapter["summary"] += line + " "

    paragraphs = []
    if trans_result and "result" in trans_result:
        try:
            result_json = json.loads(trans_result["result"])
            for pg in result_json.get("pg", []):
                sentences = []
                for sc in pg.get("sc", []):
                    sentences.append({"text": sc.get("tc", ""), "begin_time": sc.get("bt", 0)})
                if sentences:
                    content = "".join(s["text"] for s in sentences)
                    begin_time = sentences[0]["begin_time"]
                    minutes = begin_time // 60000
                    seconds = (begin_time % 60000) // 1000
                    time_str = f"{minutes:02d}:{seconds:02d}"
                    paragraphs.append(
                        {
                            "time": time_str,
                            "speaker": f"发言人{pg.get('ui', '1')}",
                            "content": content,
                        }
                    )
        except Exception as e:
            print(f"解析 API 响应失败: {e}")

    return {
        "title": title,
        "author": meta.get("author", ""),
        "publish_date": meta.get("publish_date", ""),
        "youtube_url": meta.get("youtube_url", ""),
        "source_url": url,
        "ai_summary": "\n".join(summary_points),
        "chapters": chapters,
        "qa": [],
        "keywords": keywords,
        "has_chapter_overview": len(chapters) > 0,
        "full_text": paragraphs,
    }


def _now():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def main():
    parser = argparse.ArgumentParser(description="通义听悟工具")
    parser.add_argument("--save-login", action="store_true", help="保存当前登录态")
    args = parser.parse_args()

    browser.ensure_chrome_cdp()
    session = browser.BrowserSession().connect()
    try:
        if args.save_login:
            save_login(session)
            return 0
        print("请使用 pipeline.py 运行完整流程")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
