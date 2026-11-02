"""歌曲搜索：AES 解密、JSON Schema 断言、空关键词、分页隔离。"""
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "search_schema.json").read_text(encoding="utf-8"))


def test_search_returns_encrypted_payload(music):
    resp = music.search_raw("周杰伦")
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert "data_enc" in body, "响应必须走 AES 加密"
    assert "list" not in body, "明文数据不应直接出现在响应里"


def test_search_payload_matches_schema(music):
    payload = music.search("周杰伦")
    jsonschema.validate(payload, SCHEMA)
    assert len(payload["list"]) == 10
    assert payload["list"][0]["name"].startswith("周杰伦")


def test_search_empty_keyword_rejected(music):
    resp = music.search_raw("")
    body = resp.json()
    assert resp.status_code == 400
    assert body["code"] == 2001


def test_search_pagination_is_disjoint(music):
    page1 = music.search("周杰伦", page=1, size=5)
    page2 = music.search("周杰伦", page=2, size=5)
    ids1 = {item["id"] for item in page1["list"]}
    ids2 = {item["id"] for item in page2["list"]}
    assert len(ids1) == len(ids2) == 5
    assert ids1.isdisjoint(ids2), "第 2 页不应重复第 1 页的数据"
