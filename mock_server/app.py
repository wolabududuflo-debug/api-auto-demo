"""Mock 服务：把真实项目里"不可控"的外部依赖，压缩成一个本地可跑的 Flask 应用。

复刻的接口行为：
  GET  /auth/pubkey     下发 RSA 公钥
  POST /auth/login      RSA 加密密码 + MD5 签名登录，返回 token / refresh_token
  POST /auth/refresh    刷新 token
  GET  /song/search     返回 AES 加密的业务数据（需要有效 token）
  POST /order/create    创建订单（idempotency_key 幂等）
  POST /pay             支付（按 order_id 幂等，重复支付不重复入账）
  GET  /debug/stats     测试用：登录次数、订单数、支付流水数
"""
import base64
import hashlib
import json
import threading
import time
from pathlib import Path

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad
from flask import Flask, jsonify, request

KEY_DIR = Path(__file__).resolve().parent / "keys"
KEY_FILE = KEY_DIR / "demo_rsa.pem"

APP_SECRET = "demo-secret-2026"
AES_KEY = b"0123456789abcdef"
AES_IV = b"abcdef9876543210"
TOKEN_TTL = 300
USERS = {"tester": "Test@123"}

CODE_OK = 0
CODE_BAD_CREDENTIAL = 1001
CODE_BAD_SIGN = 1002
CODE_EXPIRED_TS = 1003
CODE_UNAUTHORIZED = 401
CODE_EMPTY_KEYWORD = 2001


def _aes_encrypt(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(pad(raw, AES.block_size))).decode("ascii")


def _load_or_create_key():
    """密钥首次生成后落盘缓存，避免每次启动都做一次 2048 位密钥生成。"""
    KEY_DIR.mkdir(exist_ok=True)
    if KEY_FILE.exists():
        return RSA.import_key(KEY_FILE.read_bytes())
    key = RSA.generate(2048)
    KEY_FILE.write_bytes(key.export_key())
    return key


class State:
    """内存态：真实项目里这里是数据库 / Redis。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.rsa_key = _load_or_create_key()
        self.tokens = {}          # token -> 过期时间
        self.refresh_tokens = {}  # refresh_token -> token
        self.login_count = 0
        self.orders = {}          # idempotency_key -> order
        self.payments = {}        # order_id -> 金额
        self.seq = 0


def create_app() -> Flask:
    app = Flask(__name__)
    state = State()
    app.state = state  # 测试里可以直接读，用来断言服务端副作用

    # ------------------------------------------------------------------ 鉴权
    def current_token():
        header = request.headers.get("Authorization", "")
        token = header.replace("Bearer ", "", 1).strip()
        with state.lock:
            expire_at = state.tokens.get(token)
        if not expire_at or expire_at < time.time():
            return None
        return token

    def unauthorized():
        return jsonify(code=CODE_UNAUTHORIZED, msg="token 无效或已过期"), 401

    # ------------------------------------------------------------- 登录相关
    @app.get("/auth/pubkey")
    def pubkey():
        der = state.rsa_key.publickey().export_key(format="DER")
        return jsonify(code=CODE_OK, msg="ok",
                       data={"pubkey": base64.b64encode(der).decode("ascii")})

    @app.post("/auth/login")
    def login():
        body = request.get_json(force=True, silent=True) or {}
        username = str(body.get("username", ""))
        password_enc = str(body.get("password_enc", ""))
        sign = str(body.get("sign", ""))

        try:
            ts = int(body.get("ts", 0))
        except (TypeError, ValueError):
            ts = 0
        if abs(time.time() - ts) > 300:
            return jsonify(code=CODE_EXPIRED_TS, msg="时间戳过期"), 400

        expect = hashlib.md5(
            f"{username}{password_enc}{ts}{APP_SECRET}".encode("utf-8")).hexdigest()
        if sign != expect:
            return jsonify(code=CODE_BAD_SIGN, msg="签名错误"), 400

        sentinel = b"__decode_failed__"
        try:
            password = PKCS1_v1_5.new(state.rsa_key).decrypt(
                base64.b64decode(password_enc), sentinel)
        except (ValueError, TypeError):
            password = sentinel
        if password == sentinel or password.decode("utf-8", "ignore") != USERS.get(username):
            return jsonify(code=CODE_BAD_CREDENTIAL, msg="用户名或密码错误"), 400

        token = f"tk-{int(time.time() * 1000)}-{username}"
        refresh = f"rf-{int(time.time() * 1000)}-{username}"
        with state.lock:
            state.login_count += 1
            state.tokens[token] = time.time() + TOKEN_TTL
            state.refresh_tokens[refresh] = token
        return jsonify(code=CODE_OK, msg="ok",
                       data={"token": token, "refresh_token": refresh,
                             "expires_in": TOKEN_TTL})

    @app.post("/auth/refresh")
    def refresh():
        body = request.get_json(force=True, silent=True) or {}
        refresh_token = str(body.get("refresh_token", ""))
        with state.lock:
            old = state.refresh_tokens.get(refresh_token)
        if not old:
            return jsonify(code=CODE_UNAUTHORIZED, msg="refresh_token 无效"), 401

        new_token = f"tk-{int(time.time() * 1000)}-r"
        new_refresh = f"rf-{int(time.time() * 1000)}-r"
        with state.lock:
            state.tokens.pop(old, None)
            state.tokens[new_token] = time.time() + TOKEN_TTL
            state.refresh_tokens.pop(refresh_token, None)
            state.refresh_tokens[new_refresh] = new_token
        return jsonify(code=CODE_OK, msg="ok",
                       data={"token": new_token, "refresh_token": new_refresh,
                             "expires_in": TOKEN_TTL})

    # ---------------------------------------------------------------- 业务
    @app.get("/song/search")
    def song_search():
        if current_token() is None:
            return unauthorized()
        keyword = request.args.get("keyword", "")
        try:
            page = int(request.args.get("page", 1))
            size = int(request.args.get("size", 10))
        except ValueError:
            return jsonify(code=2002, msg="分页参数非法"), 400
        if not keyword.strip():
            return jsonify(code=CODE_EMPTY_KEYWORD, msg="关键词不能为空"), 400

        songs = [{"id": i, "name": f"{keyword}-{i}", "singer": "demo",
                  "duration": 180 + i}
                 for i in range((page - 1) * size, page * size)]
        payload = {"total": 100, "page": page, "size": size, "list": songs}
        return jsonify(code=CODE_OK, msg="ok", data_enc=_aes_encrypt(payload))

    @app.post("/order/create")
    def order_create():
        if current_token() is None:
            return unauthorized()
        body = request.get_json(force=True, silent=True) or {}
        idem = str(body.get("idempotency_key", ""))
        try:
            amount = float(body.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0
        if not idem:
            return jsonify(code=3001, msg="idempotency_key 不能为空"), 400
        if amount <= 0:
            return jsonify(code=3003, msg="金额必须大于 0"), 400
        with state.lock:
            if idem in state.orders:                     # 幂等：直接返回首次结果
                return jsonify(code=CODE_OK, msg="cached",
                               data=state.orders[idem])
            state.seq += 1
            order = {"order_id": f"ORD{state.seq:04d}", "amount": amount,
                     "status": "created"}
            state.orders[idem] = order
        return jsonify(code=CODE_OK, msg="ok", data=order)

    @app.post("/pay")
    def pay():
        if current_token() is None:
            return unauthorized()
        body = request.get_json(force=True, silent=True) or {}
        order_id = str(body.get("order_id", ""))
        amount = body.get("amount", 0)
        if not order_id:
            return jsonify(code=3002, msg="order_id 不能为空"), 400
        with state.lock:
            if order_id in state.payments:               # 幂等：不重复入账
                return jsonify(code=CODE_OK, msg="already paid",
                               data={"order_id": order_id, "paid": True,
                                     "repeat": True})
            state.payments[order_id] = amount
        return jsonify(code=CODE_OK, msg="ok",
                       data={"order_id": order_id, "paid": True, "repeat": False})

    # ---------------------------------------------------------------- 调试
    @app.get("/debug/stats")
    def stats():
        with state.lock:
            return jsonify(code=CODE_OK, msg="ok", data={
                "login_count": state.login_count,
                "tokens": len(state.tokens),
                "orders": len(state.orders),
                "payments": len(state.payments),
            })

    return app
