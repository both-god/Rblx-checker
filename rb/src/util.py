import sys
from datetime import datetime
from json import load
from pathlib import Path
from random import choice, randint
from string import ascii_letters, digits

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT_DIR / "input"

sys.path.insert(0, str(ROOT_DIR))


def _load_lines(filepath: Path) -> list[str]:
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return [line.strip() for line in f if line.strip()]


def _load_json(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return load(f)


_proxies = _load_lines(INPUT_DIR / "proxies.txt")
_config = _load_json(INPUT_DIR / "config.json")
_accounts = _load_lines(INPUT_DIR / "accounts.txt")


# ── Public API ─────────────────────────────────────────────────

class Util:
    @staticmethod
    def get_random_proxy() -> str:
        if not _proxies:
            return ""
        return choice(_proxies)

    @staticmethod
    def get_config() -> dict:
        return _config

    @staticmethod
    def get_accounts() -> list[str]:
        return _accounts

    @staticmethod
    def get_random_string(length_min: int = 12, length_max: int = 20) -> str:
        return "".join(choice(ascii_letters + digits) for _ in range(randint(length_min, length_max)))

    @staticmethod
    def get_date_formatted() -> str:
        return datetime.now().strftime("%m/%d/%Y %H:%M:%S")