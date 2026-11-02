"""登录相关接口：公钥、登录、刷新 token。"""
import time

from common import config
from common.crypto_utils import load_public_key, md5_sign, rsa_encrypt


class AuthApi:
    def __init__(self, client, username: str = config.USERNAME,
                 password: str = config.PASSWORD):
        self.client = client
        self.username = username
        self.password = password
        self._public_key = None

    def public_key(self):
        if self._public_key is None:
            resp = self.client.get("/auth/pubkey")
            resp.raise_for_status()
            self._public_key = load_public_key(resp.json()["data"]["pubkey"])
        return self._public_key

    # ---------- 原始请求（给异常用例用） ----------
    def login(self, password: str = None, ts: int = None,
              sign_override: str = None):
        password = self.password if password is None else password
        ts = int(time.time()) if ts is None else ts
        password_enc = rsa_encrypt(password, self.public_key())
        sign = sign_override or md5_sign(self.username, password_enc, ts,
                                         config.APP_SECRET)
        return self.client.post("/auth/login", json={
            "username": self.username,
            "password_enc": password_enc,
            "ts": ts,
            "sign": sign,
        })

    def refresh(self, refresh_token: str):
        return self.client.post("/auth/refresh",
                                json={"refresh_token": refresh_token})

    # ---------- 成功路径（给 TokenManager 用） ----------
    def login_ok(self) -> dict:
        resp = self.login()
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, body
        return body["data"]

    def refresh_ok(self, refresh_token: str) -> dict:
        resp = self.refresh(refresh_token)
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, body
        return body["data"]
