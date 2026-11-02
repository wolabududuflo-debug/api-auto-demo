"""手动起 Mock 服务（浏览器/Postman 调试用）：python run_mock.py"""
from mock_server.app import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, threaded=True)
