"""登录接口：正常登录 + 三类失败分支（密码错、签名错、时间戳过期）。"""
import time

from common.crypto_utils import load_public_key


def test_public_key_is_valid_rsa(client):
    resp = client.get("/auth/pubkey")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    key = load_public_key(body["data"]["pubkey"])
    assert key.size_in_bits() == 2048


def test_login_success(auth):
    data = auth.login_ok()
    assert data["token"].startswith("tk-")
    assert data["expires_in"] > 0
    assert data["token"] != data["refresh_token"]


def test_login_wrong_password(auth):
    resp = auth.login(password="wrong-password")
    body = resp.json()
    assert resp.status_code == 400
    assert body["code"] == 1001


def test_login_bad_signature(auth):
    resp = auth.login(sign_override="0" * 32)
    body = resp.json()
    assert resp.status_code == 400
    assert body["code"] == 1002


def test_login_expired_timestamp(auth):
    resp = auth.login(ts=int(time.time()) - 1000)
    body = resp.json()
    assert resp.status_code == 400
    assert body["code"] == 1003
