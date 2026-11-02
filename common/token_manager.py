"""Token 管理：过期自动登录/刷新，多线程下只登录一次。

这就是简历里那条 "Token 自动刷新（8 线程只登录 1 次）" 的实现。
"""
import threading
import time


class TokenManager:
    def __init__(self, auth_api, leeway: int = 5):
        self._auth = auth_api
        self._leeway = leeway
        self._lock = threading.Lock()
        self._token = None
        self._refresh = None
        self._expire_at = 0.0
        self.login_times = 0          # 自己统计登录次数，测试里可以直接断言

    # ---------- 对外 ----------
    def token(self, force_login: bool = False) -> str:
        if not force_login and self._is_valid():
            return self._token
        # 双重检查：并发进来时，只有第一个线程真正去登录
        with self._lock:
            if not force_login and self._is_valid():
                return self._token
            data = self._auth.login_ok()
            self._store(data)
            self.login_times += 1
            return self._token

    def refresh_token(self) -> str:
        with self._lock:
            data = self._auth.refresh_ok(self._refresh)
            self._store(data)
            return self._token

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}"}

    def reset(self) -> None:
        with self._lock:
            self._token = None
            self._refresh = None
            self._expire_at = 0.0

    # ---------- 内部 ----------
    def _is_valid(self) -> bool:
        return self._token is not None and time.time() < self._expire_at

    def _store(self, data: dict) -> None:
        self._token = data["token"]
        self._refresh = data["refresh_token"]
        self._expire_at = time.time() + data["expires_in"] - self._leeway
