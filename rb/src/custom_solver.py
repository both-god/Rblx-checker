from time import sleep

from curl_cffi import requests

from util import Util

config = Util.get_config()

SOLVER_KEY = config["solverKey"]
CAPTCHA_PUBLIC_KEY = "476068BF-9607-4799-B53D-966BE98E2B81"
MAX_POLL_ATTEMPTS = 60


# ── Captcha solver ─────────────────────────────────────────────

def get_token(roblox_session, blob: str, proxy: str) -> str | None:
    session = requests.Session()

    challenge_info = {
        "publicKey": CAPTCHA_PUBLIC_KEY,
        "site": "https://www.roblox.com/",
        "surl": "https://arkoselabs.roblox.com",
        "capiMode": "inline",
        "styleTheme": "default",
        "languageEnabled": False,
        "jsfEnabled": False,
        "extraData": {"blob": blob},
        "ancestorOrigins": ["https://www.roblox.com"],
        "treeIndex": [1],
        "treeStructure": "[[],[]]",
        "locationHref": "https://www.roblox.com/arkose/iframe",
        "documentReferrer": "https://www.roblox.com/login",
    }

    browser_info = {
        "Sec-Ch-Ua": roblox_session.headers["sec-ch-ua"],
        "User-Agent": roblox_session.headers["user-agent"],
        "Mobile": False,
    }

    payload = {
        "key": SOLVER_KEY,
        "challengeInfo": challenge_info,
        "browserInfo": browser_info,
        "proxy": proxy,
    }

    response = session.post(
        "https://rosolve.pro/createTask", json=payload, timeout=120
    ).json()

    task_id = response.get("taskId")

    if task_id is None:
        error = response.get("error", "unknown")
        raise ValueError(f"Failed to get taskId: {error}")

    # Poll for result

    for _ in range(MAX_POLL_ATTEMPTS):
        sleep(1)

        result = session.post(
            "https://rosolve.pro/taskResult",
            json={"key": SOLVER_KEY, "taskId": task_id},
        ).json()

        if result["status"] == "completed":
            return result["result"]["solution"]

        if result["status"] == "failed":
            return None

    return None