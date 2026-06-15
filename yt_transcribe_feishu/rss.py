import argparse
import json
import os
import urllib.request
import xml.etree.ElementTree as ET

from . import config


def _state_file(state_file=None):
    return state_file or config.YOUTUBE_RSS_STATE_FILE


def load_state(state_file=None):
    """Load processed video IDs per channel."""
    state_file = _state_file(state_file)
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state, state_file=None):
    """Save processed video IDs per channel."""
    state_file = _state_file(state_file)
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _rss_url(channel_id):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_feed(channel_id):
    """Fetch RSS feed for a channel."""
    feed_url = _rss_url(channel_id)
    try:
        req = urllib.request.Request(
            feed_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RSS checker)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"获取 RSS 失败: {e}")


def parse_feed(xml_content, channel_id):
    """Parse RSS XML into a list of video dicts."""
    if not xml_content:
        return []

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        raise RuntimeError(f"解析 XML 失败: {e}")

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    videos = []
    for entry in root.findall("atom:entry", ns):
        video_id_elem = entry.find("yt:videoId", ns)
        if video_id_elem is None:
            continue
        video_id = video_id_elem.text

        title_elem = entry.find("atom:title", ns)
        title = title_elem.text if title_elem is not None else "未知标题"

        published_elem = entry.find("atom:published", ns)
        published = published_elem.text if published_elem is not None else ""

        link_elem = entry.find("atom:link", ns)
        url = (
            link_elem.get("href")
            if link_elem is not None
            else f"https://www.youtube.com/watch?v={video_id}"
        )

        channel_id_elem = entry.find("yt:channelId", ns)
        channel_id_from_entry = (
            channel_id_elem.text if channel_id_elem is not None else channel_id
        )

        author_elem = entry.find("atom:author/atom:name", ns)
        author = author_elem.text if author_elem is not None else ""

        videos.append(
            {
                "id": video_id,
                "video_id": video_id,
                "title": title,
                "url": url,
                "published": published,
                "channel_id": channel_id_from_entry,
                "channel_name": author,
            }
        )

    return videos


def check_new_videos(channel_id, state):
    """Return new videos for a channel and update state."""
    xml_content = fetch_feed(channel_id)
    videos = parse_feed(xml_content, channel_id)
    processed = state.get(channel_id, [])

    new_videos = [v for v in videos if v["id"] not in processed]
    state[channel_id] = processed + [v["id"] for v in new_videos]
    return new_videos


def check_rss(channels_config=None, state_file=None, limit=1, dry_run=False):
    """Check all configured channels and return new videos."""
    channels_config = channels_config or config.YOUTUBE_CHANNELS_CONFIG

    with open(channels_config, "r", encoding="utf-8") as f:
        channels = json.load(f).get("channels", [])

    state = load_state(state_file)
    all_new_videos = []

    for channel_id in channels:
        new_videos = check_new_videos(channel_id, state)
        all_new_videos.extend(new_videos[:limit])

    if not dry_run:
        save_state(state, state_file)

    return {
        "title": all_new_videos[0]["title"] if all_new_videos else "",
        "author": all_new_videos[0]["channel_name"] if all_new_videos else "",
        "publish_date": all_new_videos[0]["published"][:10]
        if all_new_videos
        else "",
        "youtube_url": all_new_videos[0]["url"] if all_new_videos else "",
        "videos": all_new_videos,
    }


def main():
    parser = argparse.ArgumentParser(description="YouTube RSS 监控")
    parser.add_argument("--config", help="频道配置文件路径")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("--limit", type=int, default=10, help="每频道最大返回视频数")
    parser.add_argument("--dry-run", action="store_true", help="不保存状态")
    args = parser.parse_args()

    result = check_rss(
        channels_config=args.config,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"共发现 {len(result['videos'])} 个新视频")
    print(f"结果保存到: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
