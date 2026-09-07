"""Environment, paths, and logging shared by the downloader, pipeline, and benchmark CLIs."""

import logging
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
HISTORICAL_DIR = DATA_DIR / "historical"
LOG_DIR = DATA_DIR / "logs"

GOVINFO_BASE_URL = "https://api.govinfo.gov"

# STATUTE volumes at or below this number are scanned images; later ones are born digital.
LAST_SCANNED_VOLUME = 116


class MissingEnv(RuntimeError):
    """A required environment variable is unset or empty."""


def require_env(name: str, hint: str = "") -> str:
    """Return the value of an environment variable or raise MissingEnv.

    Values are never defaulted. Secrets reach the container through .env (env_file in
    docker-compose.yml).
    """
    value = os.environ.get(name, "").strip()
    if not value:
        message = f"{name} is not set. Add it to .env (see .env.example)."
        if hint:
            message = f"{message} {hint}"
        raise MissingEnv(message)
    return value


def govinfo_api_key() -> str:
    return require_env("GOVINFO_API_KEY", "Request a key at https://api.govinfo.gov/docs/.")


def exit_on_missing_env(func):
    """Decorator for CLI entry points: print a MissingEnv message and exit with status 2."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MissingEnv as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(2)

    return wrapper


def setup_logging(script_name: str, log_dir: Path | str | None = None, level: int = logging.INFO) -> Path:
    """Log to stdout and to <log_dir>/<script>-<date>.log. Returns the log file path."""
    log_dir = Path(log_dir) if log_dir else LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{script_name}-{date.today().isoformat()}.log"

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
    for noisy in ("httpx", "httpcore", "huggingface_hub", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_path


def is_scanned_volume(volume: int) -> bool:
    return volume <= LAST_SCANNED_VOLUME
