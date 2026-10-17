from primp import Client

from util import Util

IMPERSONATE = "chrome_133"
SEC_CH_UA = '"Not/A)Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"'
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)


class Session:
    @staticmethod
    def create() -> tuple[Client, str, str, str]:
        proxy = Util.get_random_proxy()
        client = Client(impersonate=IMPERSONATE, impersonate_os="windows", proxy=proxy, verify=False)
        return client, SEC_CH_UA, USER_AGENT, proxy