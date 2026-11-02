"""加解密与签名工具。

对应简历里的 "RSA / AES 加解密、MD5 签名"。
"""
import base64
import hashlib

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad


def load_public_key(pubkey_b64: str):
    """把服务端下发的 base64(DER) 公钥还原成 RSA key 对象。"""
    return RSA.import_key(base64.b64decode(pubkey_b64))


def rsa_encrypt(text: str, public_key) -> str:
    """用 RSA 公钥加密（登录密码走这条链路），返回 base64 密文。"""
    cipher = PKCS1_v1_5.new(public_key)
    return base64.b64encode(cipher.encrypt(text.encode("utf-8"))).decode("ascii")


def md5_sign(*parts) -> str:
    """按 "参数拼接 + 盐" 的规则生成 MD5 签名。"""
    raw = "".join(str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def aes_encrypt(text: str, key: bytes, iv: bytes) -> str:
    """AES-CBC 加密，返回 base64（Mock 服务端用它加密响应体）。"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return base64.b64encode(cipher.encrypt(pad(text.encode("utf-8"), AES.block_size))).decode("ascii")


def aes_decrypt(data_b64: str, key: bytes, iv: bytes) -> str:
    """AES-CBC 解密，去掉 PKCS7 填充（测试端用它解响应体）。"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plain = cipher.decrypt(base64.b64decode(data_b64))
    return unpad(plain, AES.block_size).decode("utf-8")
