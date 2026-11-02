"""歌曲搜索接口：拿到的响应体是 AES 密文，这里负责解密成业务数据。"""
import json

from common import config
from common.crypto_utils import aes_decrypt


class MusicApi:
    def __init__(self, client, token_manager):
        self.client = client
        self.tokens = token_manager

    def search_raw(self, keyword: str, page: int = 1, size: int = 10):
        """原始响应，异常/边界用例直接断言它的状态码与业务码。"""
        return self.client.get(
            "/song/search",
            params={"keyword": keyword, "page": page, "size": size},
            headers=self.tokens.headers(),
        )

    def search(self, keyword: str, page: int = 1, size: int = 10) -> dict:
        """解密后的业务数据，正常用例用它。"""
        resp = self.search_raw(keyword, page, size)
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, body
        plain = aes_decrypt(body["data_enc"], config.AES_KEY, config.AES_IV)
        return json.loads(plain)
