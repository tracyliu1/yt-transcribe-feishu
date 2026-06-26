import argparse
import logging
import os
import sys

from . import browser, config, download, feishu, rss, tingwu, utils


def _cleanup(audio_path):
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)
        logging.info("已清理本地文件: %s", audio_path)


def run(test_mode: bool = False) -> int:
    """Run the full pipeline."""
    utils.setup_logging()
    session = None
    audio_path = None

    if test_mode:
        logging.info("测试模式：仅验证环境配置，不执行实际流程")
        # TODO: add a dry-run check if needed.
        return 0

    try:
        logging.info("=== 步骤1：检查 RSS ===")
        result = rss.check_rss(limit=3, save_state=False)
        videos = result.get("videos", [])
        if not videos:
            print("[SILENT]", flush=True)
            return 0

        logging.info("=== 步骤2：连接 Chrome CDP 并检查登录 ===")
        browser.ensure_chrome_cdp()
        session = browser.BrowserSession().connect()
        tingwu.load_cdp_cookies(session)

        if not tingwu.check_login(session):
            logging.info("尝试从保存的登录态恢复...")
            if not tingwu.restore_login(session):
                raise RuntimeError(
                    "通义听悟未登录。请手动登录后运行 "
                    "python3 -m yt_transcribe_feishu.tingwu --save-login"
                )

        processed_count = 0
        failed_count = 0

        for video in videos:
            video_id = video["video_id"]
            video_url = video["url"]
            video_title = video["title"]
            channel_id = video.get("channel_id", "")
            audio_path = None

            try:
                logging.info("=== 处理视频: %s ===", video_title)

                logging.info("=== 步骤2：下载音频 ===")
                audio_path, meta = download.download_audio(video_url, video_id)

                logging.info("=== 步骤4：上传并转写 ===")
                upload_result = tingwu.upload_and_transcribe(session, audio_path)
                if not upload_result.get("url"):
                    raise RuntimeError("未能获取转录 URL")

                logging.info("=== 步骤5：提取内容 ===")
                content = tingwu.extract_content(session, upload_result["url"], meta=meta)

                # Ensure upstream metadata is preferred.
                content.setdefault("title", meta["title"])
                content.setdefault("author", meta["author"])
                content.setdefault("publish_date", meta["publish_date"])
                content.setdefault("youtube_url", meta["youtube_url"])

                logging.info("=== 步骤6：创建飞书文档 ===")
                doc_url = feishu.create_document(content)

                logging.info("=== 步骤7：发送通知 ===")
                feishu.send_notification(doc_url, content["title"])

                logging.info("文档已生成: %s", doc_url)
                logging.info("标题: %s", content["title"])

                # Mark video as processed only after full success.
                try:
                    state = rss.load_state()
                    if channel_id not in state:
                        state[channel_id] = []
                    if video_id not in state[channel_id]:
                        state[channel_id].append(video_id)
                        rss.save_state(state)
                        logging.info("已标记为处理: %s", video_id)
                except Exception as e:
                    logging.warning("标记处理状态失败: %s", e)

                processed_count += 1

            except Exception as e:
                error_msg = f"视频 [{video_title}] 处理异常: {e}"
                logging.exception(error_msg)
                feishu.send_error_notification(error_msg)
                failed_count += 1

            finally:
                if audio_path:
                    _cleanup(audio_path)

        if processed_count == 0 and failed_count > 0:
            return 1
        return 0

    except Exception as e:
        error_msg = f"流水线异常: {e}"
        logging.exception(error_msg)
        feishu.send_error_notification(error_msg)
        return 1

    finally:
        if session:
            session.close()


def main():
    parser = argparse.ArgumentParser(description="YouTube → 飞书文档流水线")
    parser.add_argument("--test", action="store_true", help="测试模式（不执行实际流程）")
    args = parser.parse_args()
    sys.exit(run(test_mode=args.test))


if __name__ == "__main__":
    main()
