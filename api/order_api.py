"""订单与支付接口：重点覆盖幂等（重复创建、重复支付）。"""


class OrderApi:
    def __init__(self, client, token_manager):
        self.client = client
        self.tokens = token_manager

    def create(self, amount: float, idempotency_key: str):
        resp = self.client.post(
            "/order/create",
            json={"amount": amount, "idempotency_key": idempotency_key},
            headers=self.tokens.headers(),
        )
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, body
        return body["data"]

    def pay(self, order_id: str, amount: float):
        resp = self.client.post(
            "/pay",
            json={"order_id": order_id, "amount": amount},
            headers=self.tokens.headers(),
        )
        body = resp.json()
        assert resp.status_code == 200 and body["code"] == 0, body
        return body["data"]

    def create_raw(self, payload: dict, token: str = None):
        headers = {"Authorization": f"Bearer {token}"} if token else self.tokens.headers()
        return self.client.post("/order/create", json=payload, headers=headers)
