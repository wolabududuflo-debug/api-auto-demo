"""边界与异常：金额非法时服务端必须拒绝，而不是照单生成订单。"""


def test_create_order_with_negative_amount_is_rejected(order):
    resp = order.create_raw({"amount": -100, "idempotency_key": "neg-1"})
    assert resp.status_code == 400, "金额为负必须被拒绝"
    assert resp.json()["code"] == 3003