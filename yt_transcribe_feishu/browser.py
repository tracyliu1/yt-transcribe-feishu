import os
import subprocess
import time
import urllib.request

from playwright.sync_api import sync_playwright

from . import config


def ensure_chrome_cdp(cdp_url=None, chrome_profile_dir=None, display=None):
    """Start or reuse a Chrome CDP instance. Returns the CDP URL."""
    cdp_url = cdp_url or config.CDP_URL
    chrome_profile_dir = chrome_profile_dir or config.CHROME_PROFILE_DIR
    display = display or config.CHROME_DISPLAY

    port = int(cdp_url.rsplit(":", 1)[-1])

    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=2) as resp:
            if resp.status == 200:
                return cdp_url
    except Exception:
        pass

    os.makedirs(chrome_profile_dir, exist_ok=True)

    cmd = [
        "google-chrome",
        f"--user-data-dir={chrome_profile_dir}",
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "https://tingwu.aliyun.com/home",
    ]

    env = os.environ.copy()
    env["DISPLAY"] = display

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    for _ in range(20):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=2) as resp:
                if resp.status == 200:
                    return cdp_url
        except Exception:
            continue

    raise RuntimeError("Chrome CDP 启动超时")


class BrowserSession:
    """Playwright session connected to an existing Chrome CDP instance."""

    def __init__(self, cdp_url=None):
        self.cdp_url = cdp_url or config.CDP_URL
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def connect(self):
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.connect_over_cdp(
            self.cdp_url, timeout=10000
        )
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self

    def close(self):
        if self.browser:
            self.browser.close()
            self.browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
