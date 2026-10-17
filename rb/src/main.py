import os
import sys
from pathlib import Path
from threading import Thread

from counter import counter
from output import Output
from roblox import Roblox
from thread_lock import lock
from util import Util

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_DIRS = [
    "output",
    "output/payment_info",
    "output/pending",
    "output/premium",
    "output/rap",
    "output/robux",
    "output/summary",
]


def main() -> None:
    for directory in OUTPUT_DIRS:
        os.makedirs(directory, exist_ok=True)

    config = Util.get_config()
    accounts = Util.get_accounts()
    thread_count = min(config["threads"], len(accounts))

    if thread_count == 0:
        Output("ERROR").log("No accounts to check")
        return

    threads = []

    for _ in range(thread_count):
        checker = Roblox(lock, counter, accounts)
        thread = Thread(target=checker.check)
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    Output("SUCCESS").log("Finished checking all accounts")


if __name__ == "__main__":
    main()