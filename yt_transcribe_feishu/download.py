import os
import shlex

from . import utils


def _parse_meta(video_url: str):
    """Fetch video metadata without downloading."""
    cmd = (
        f"yt-dlp --print '%(title)s\t%(uploader)s\t%(upload_date)s' "
        f"--no-download {shlex.quote(video_url)}"
    )
    stdout = utils.run_cmd(cmd, timeout=60)
    if not stdout:
        return None

    parts = stdout.strip().split("\t")
    if len(parts) < 3:
        return None

    title, author, date_str = parts[0], parts[1], parts[2]
    if len(date_str) == 8:
        publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    else:
        publish_date = date_str

    return {"title": title, "author": author, "publish_date": publish_date}


def download_audio(video_url: str, video_id: str, output_dir: str = "/tmp"):
    """Download audio as MP3 using the video ID as filename.

    Returns (audio_path, meta_dict).
    """
    meta = _parse_meta(video_url)
    if meta is None:
        meta = {"title": "未命名", "author": "", "publish_date": ""}

    audio_path = os.path.join(output_dir, f"{video_id}.mp3")

    cmd = (
        f"yt-dlp -f 'bestaudio[ext=mp3]/bestaudio' --extract-audio "
        f"--audio-format mp3 -o {shlex.quote(audio_path)} {shlex.quote(video_url)}"
    )
    utils.run_cmd(cmd)

    full_meta = {
        "video_id": video_id,
        "title": meta["title"],
        "author": meta["author"],
        "publish_date": meta["publish_date"],
        "youtube_url": video_url,
    }
    return audio_path, full_meta
