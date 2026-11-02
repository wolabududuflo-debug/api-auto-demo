"""pytest 公共夹具：启动 Mock 服务、构造请求层 / Token 管理 / 业务 API。"""
import logging
import threading

import pytest
from werkzeug.serving import make_server

from api.auth_api import AuthApi
from api.music_api import MusicApi
from api.order_api import OrderApi
from common.client import ApiClient
from common.token_manager import TokenManager
from mock_server.app import create_app


@pytest.fixture(scope="session", autouse=True)
def _log_config():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
    )


@pytest.fixture(scope="session")
def server():
    """在后台线程里起一个真实 HTTP 服务（threaded=True，才能测并发）。"""
    app = create_app()
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    port = srv.server_port
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield {"url": f"http://127.0.0.1:{port}", "state": app.state}
    srv.shutdown()
    thread.join(timeout=5)


@pytest.fixture()
def client(server):
    c = ApiClient(server["url"])
    yield c
    c.close()


@pytest.fixture()
def auth(client):
    return AuthApi(client)


@pytest.fixture()
def token_manager(auth):
    return TokenManager(auth)


@pytest.fixture()
def music(client, token_manager):
    return MusicApi(client, token_manager)


@pytest.fixture()
def order(client, token_manager):
    return OrderApi(client, token_manager)
