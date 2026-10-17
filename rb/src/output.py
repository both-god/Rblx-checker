from datetime import datetime
from threading import Lock

from colorama import Fore, init

init()

_print_lock = Lock()

_LEVEL_STYLES = {
    "INFO":      (Fore.LIGHTCYAN_EX,   "^"),
    "CAPTCHA":   (Fore.LIGHTBLUE_EX,   "\U0001f916"),
    "ERROR":     (Fore.LIGHTRED_EX,    "\u274c"),
    "SUCCESS":   (Fore.LIGHTGREEN_EX,  "\u2705"),
    "FAVOURITE": (Fore.YELLOW,         "\U0001f31f"),
    "MAIL":      (Fore.RESET,          "\U0001f4e9"),
    "HUMANIZE":  (Fore.YELLOW,         "\U0001f466"),
    "GROUP":     (Fore.MAGENTA,        "\U0001f465"),
    "FOLLOW":    (Fore.YELLOW,         "\U0001f466"),
}


# ── Logging ────────────────────────────────────────────────────

class Output:
    def __init__(self, level: str):
        self.level = level

    def log(self, message: str) -> None:
        color, icon = _LEVEL_STYLES.get(self.level, (Fore.RESET, "?"))
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = (
            f"{Fore.LIGHTBLACK_EX}[{timestamp}]{Fore.RESET} "
            f"({color}{icon}{Fore.RESET}) "
            f"{color}{message}{Fore.RESET}"
        )
        with _print_lock:
            print(line)