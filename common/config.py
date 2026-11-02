"""全局配置。

真实项目里这些值应该来自环境变量或配置中心，这里为了可运行直接写死。
"""

DEFAULT_BASE_URL = "http://127.0.0.1:5000"

# 接口签名用的盐，前后端约定一致（生产环境应放环境变量）
APP_SECRET = "demo-secret-2026"

# 响应体 AES 加密用的密钥与 IV（生产环境由登录响应下发）
AES_KEY = b"0123456789abcdef"
AES_IV = b"abcdef9876543210"

# 请求层参数
TIMEOUT = 5
RETRIES = 2

# 演示账号
USERNAME = "tester"
PASSWORD = "Test@123"
