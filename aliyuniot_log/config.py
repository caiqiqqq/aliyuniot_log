from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _path_env(name: str, default: str) -> Path:
    value = os.getenv(name, default)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    log_url: str
    network_url_keywords: tuple[str, ...]
    db_path: Path


def get_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    return Settings(
        log_url=os.getenv("ALIYUN_IOT_LOG_URL", "https://iot.console.aliyun.com/lk/monitor/log"),
        network_url_keywords=_csv_env(
            "ALIYUN_NETWORK_URL_KEYWORDS",
            "iot.console.aliyun.com,log",
        ),
        db_path=_path_env("ALIYUN_DB_PATH", "data/iot_logs.db"),
    )


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    value = os.getenv(name, default)
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())
