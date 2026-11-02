"""统一请求层：Session 复用 + 自动重试 + 统一超时 + 请求日志。

所有业务 API 都走这一层，好处是改一处（代理、超时、重试、公共头）全局生效。
"""
import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common import config

log = logging.getLogger("api")


class ApiClient:
    def __init__(self, base_url: str = config.DEFAULT_BASE_URL,
                 timeout: int = config.TIMEOUT, retries: int = config.RETRIES):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=retries,
            backoff_factor=0.1,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        log.info(">>> %s %s params=%s json=%s", method, url,
                 kwargs.get("params"), kwargs.get("json"))
        resp = self.session.request(method, url, **kwargs)
        log.info("<<< %s %s elapsed=%sms body=%s", resp.status_code,
                 url, int(resp.elapsed.total_seconds() * 1000), resp.text[:300])
        return resp

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def close(self) -> None:
        self.session.close()
