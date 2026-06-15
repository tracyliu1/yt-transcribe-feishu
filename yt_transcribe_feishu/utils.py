import logging
import subprocess
import sys


def setup_logging(level=None):
    """Configure stdout logging."""
    if level is None:
        from . import config
        level = config.LOG_LEVEL
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_cmd(cmd, timeout=None, shell=True, capture_output=True):
    """Run a shell command and raise on failure."""
    from . import config

    if timeout is None:
        timeout = config.RUN_CMD_TIMEOUT
    logging.info("[CMD] %s", cmd)
    result = subprocess.run(
        cmd,
        shell=shell,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        logging.error("returncode=%s", result.returncode)
        logging.error("stderr: %s", result.stderr[:500])
        raise RuntimeError(f"命令失败: {cmd}\nstderr: {result.stderr[:500]}")
    return result.stdout
