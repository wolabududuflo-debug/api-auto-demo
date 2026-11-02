"""Token 相关：刷新、8 线程并发只登录一次、无效 token 拦截。"""
import threading

from common.token_manager import TokenManager


def test_refresh_returns_new_token(token_manager):
    first = token_manager.token()
    second = token_manager.refresh_token()
    assert second and second != first
    assert token_manager.token() == second


def test_concurrent_threads_login_only_once(auth, server):
    """8 个线程同时要 token，服务端只应该收到 1 次登录。"""
    manager = TokenManager(auth)
    before = server["state"].login_count
    barrier = threading.Barrier(8)
    results = []

    def worker():
        barrier.wait()
        results.append(manager.token())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 8
    assert len(set(results)) == 1, "8 个线程应拿到同一个 token"
    assert manager.login_times == 1
    assert server["state"].login_count - before == 1, "并发只应触发一次登录"


def test_invalid_token_rejected(client):
    resp = client.get("/song/search", params={"keyword": "x"},
                      headers={"Authorization": "Bearer bogus-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 401
