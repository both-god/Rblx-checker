from functools import wraps

from primp import Client

UNKNOWN = "_unknown"

def _retry(max_attempts: int = 3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
        return wrapper
    return decorator


@_retry()
def _get_rap(session: Client, user_id: int) -> int:
    total_value = 0
    cursor = ""

    while True:
        response = session.get(
            f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles"
            f"?sortOrder=Asc&limit=100&cursor={cursor}"
        )
        data = response.json()

        for item in data.get("data", []):
            rap = item.get("recentAveragePrice")
            if rap is not None:
                total_value += int(rap)

        next_cursor = data.get("nextPageCursor")
        if not next_cursor or next_cursor == "null":
            break
        cursor = next_cursor

    return total_value

@_retry()
def _get_robux(session: Client, user_id: int) -> int:

    return session.get(f"https://economy.roblox.com/v1/users/{user_id}/currency").json()["robux"]

@_retry()
def _is_premium(session: Client, user_id: int) -> bool:
    text = session.get(
        f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership"
    ).text
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError("Failed to get premium status")

@_retry()
def _get_pending_and_summary(session: Client, user_id: int) -> tuple[int, int]:
    data = session.get(
        f"https://economy.roblox.com/v2/users/{user_id}/transaction-totals"
        f"?timeFrame=Year&transactionType=summary"
    ).json()
    return data["pendingRobuxTotal"], data["incomingRobuxTotal"]

@_retry()
def _has_payment_info(session: Client) -> bool:
    response = session.get(
        "https://apis.roblox.com/payments-gateway/v1/payment-profiles"
    )
    return response.status_code == 200 and len(response.json()) > 0


# ── Public API ─────────────────────────────────────────────────

class AccountInfo:
    @staticmethod
    def get_account_info(session: Client, user_id: int) -> dict:
        info = {}

        for key, func, args in [
            ("robux",        _get_robux,          (session, user_id)),
            ("payment_info", _has_payment_info,    (session,)),
            ("premium",      _is_premium,          (session, user_id)),
            ("rap",          _get_rap,             (session, user_id)),
        ]:
            try:
                info[key] = func(*args)
            except Exception:
                info[key] = UNKNOWN

        try:
            pending, summary = _get_pending_and_summary(session, user_id)
            info["pending"] = pending
            info["summary"] = summary
        except Exception:
            info["pending"] = UNKNOWN
            info["summary"] = UNKNOWN

        return info