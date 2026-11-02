"""订单与支付：创建、幂等创建、支付入账、重复支付不重复扣款。"""


def test_create_order(order):
    data = order.create(amount=128.0, idempotency_key="idem-create-1")
    assert data["order_id"].startswith("ORD")
    assert data["amount"] == 128.0
    assert data["status"] == "created"


def test_create_order_is_idempotent(order, server):
    first = order.create(amount=200.0, idempotency_key="idem-create-2")
    second = order.create(amount=200.0, idempotency_key="idem-create-2")
    assert first["order_id"] == second["order_id"], "同一幂等键必须返回同一单"
    assert len(server["state"].orders) >= 1
    # 幂等键只对应一条订单记录
    assert server["state"].orders["idem-create-2"]["order_id"] == first["order_id"]


def test_create_order_without_idempotency_key_rejected(order):
    resp = order.create_raw({"amount": 10})
    assert resp.status_code == 400
    assert resp.json()["code"] == 3001


def test_pay_writes_ledger(order, server):
    created = order.create(amount=99.0, idempotency_key="idem-pay-1")
    data = order.pay(order_id=created["order_id"], amount=99.0)
    assert data["paid"] is True
    assert data["repeat"] is False
    assert server["state"].payments[created["order_id"]] == 99.0


def test_pay_twice_charges_once(order, server):
    created = order.create(amount=66.0, idempotency_key="idem-pay-2")
    order.pay(order_id=created["order_id"], amount=66.0)
    again = order.pay(order_id=created["order_id"], amount=66.0)
    assert again["repeat"] is True
    paid = [k for k in server["state"].payments if k == created["order_id"]]
    assert len(paid) == 1, "重复支付不应重复入账"
