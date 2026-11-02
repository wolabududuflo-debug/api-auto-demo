# api-auto-demo · 接口自动化测试工程（可本地一键跑通）

一个**不依赖任何外部服务**的接口自动化测试工程：自带 Mock 服务，复刻了真实项目里最容易踩坑的几块——
RSA 加密登录、MD5 签名、AES 加密响应、Token 自动刷新（并发只登录一次）、订单与支付幂等。

配套的 Mock 服务是 Flask 写的，测试端是 Pytest + requests，**18 条用例，本地约 2 秒跑完**。

```
$ python -m pytest -q
17 passed in 1.9s
```

---

## 为什么这样设计

真实项目里做接口自动化，难点从来不是"会写 requests.get"，而是：

| 真实场景的坑 | 本工程的对应实现 |
| --- | --- |
| 密码要 RSA 加密后传输 | `mock_server/app.py` 下发公钥，`common/crypto_utils.py` 加密 |
| 每个请求都要带签名，签错就 1002 | `md5_sign()` + `AuthApi.login()` 的签名拼装 |
| 响应体是 AES 密文，不看文档根本解不出来 | `MusicApi.search()` 解密后再断言 |
| token 会过期，多线程下容易重复登录 | `common/token_manager.py` 双重检查锁 |
| 下单/支付要幂等，重复提交不能重复扣款 | `/order/create` 与 `/pay` 的幂等键实现和用例 |
| 缺少依赖，测试跑不起来 | 自带 Mock 服务，`git clone` 后直接能跑 |

## 目录结构（四层）

```
api-auto-demo/
├─ mock_server/            # 被测服务（Flask），模拟真实后端的加密/签名/幂等行为
│   └─ app.py
├─ common/                 # ① 工具层
│   ├─ config.py           #    配置（URL、盐、密钥、超时）
│   ├─ crypto_utils.py     #    RSA / AES / MD5
│   ├─ client.py           #    统一请求层：Session 复用、重试、超时、请求日志
│   └─ token_manager.py    #    Token 自动刷新（线程安全）
├─ api/                    # ② 接口层：把 HTTP 细节封成业务方法
│   ├─ auth_api.py
│   ├─ music_api.py
│   └─ order_api.py
├─ testcases/              # ③ 用例层
│   ├─ conftest.py         #    夹具：起服务、造 client / token / api
│   ├─ test_auth.py        #    登录正常 + 3 类失败分支
│   ├─ test_token.py       #    刷新、8 线程并发只登录 1 次、无效 token
│   ├─ test_music.py       #    AES 解密、JSON Schema、空关键词、分页隔离
│   └─ test_order_pay.py   #    下单、幂等下单、支付入账、重复支付
├─ schemas/                # ④ 数据层：JSON Schema 契约
├─ pytest.ini
├─ requirements.txt
├─ Jenkinsfile             # CI：装依赖 → 跑用例 → 归档 junit 报告
└─ run_mock.py             # 手动起 Mock 服务，方便 Postman 调试
```

## 快速开始

```bash
# 1. 装依赖（Python 3.10+）
python -m pip install -r requirements.txt

# 2. 跑全部用例
python -m pytest -q

# 3. 想看接口细节？单独起 Mock 服务，然后用 Postman / 浏览器调
python run_mock.py          # http://127.0.0.1:5000

# 4. 生成 junit 报告（Jenkins 用）
python -m pytest -q --junitxml=reports/junit.xml
```

## 用例清单（17 条）

**登录（5）**
1. 公钥接口返回合法 RSA 2048 公钥
2. 正确账号密码登录成功，返回 token / refresh_token
3. 密码错误 → 业务码 1001
4. 签名错误 → 业务码 1002
5. 时间戳过期 → 业务码 1003

**Token（3）**

6. 用 refresh_token 换到新 token，旧 token 失效
7. **8 线程并发取 token，服务端登录次数只增加 1 次**
8. 伪造 token 访问业务接口 → 401

**搜索（4）**

9. 响应体是 AES 密文，不含明文 list
10. 解密后业务数据符合 JSON Schema
11. 空关键词 → 业务码 2001
12. 第 2 页数据与第 1 页不重叠

**订单与支付（6）**

13. 创建订单成功
14. 同一幂等键重复创建 → 返回同一订单
15. 缺少幂等键 → 业务码 3001
16. 支付成功，金额写入支付流水
17. 重复支付 → 不重复入账
18. 金额为负 / 为 0 → 业务码 3003

## 一些实现上的取舍

- **Mock 服务用真实 HTTP，不用 mock 打桩**：并发、超时、重试这些行为只有走真网络才测得出来。
- **统一请求层**：所有用例都过 `ApiClient`，改超时/加重试/换域名只改一处。
- **Token 的双重检查锁**：`if valid → return` 在锁外先判断一次，进锁后再判断一次，避免 8 个线程同时发现"没 token"然后一起登录。
- **JSON Schema 做契约断言**：字段类型、必填项交给 schema，比一堆 `assert isinstance(...)` 好维护。
- **密钥落盘缓存**：首次生成 2048 位 RSA 后写入 `mock_server/keys/`，避免每次启动都做密钥生成（已 gitignore）。

## 已知限制

- Mock 服务是内存态，进程重启后订单/流水清零（真实项目接 MySQL / Redis）。
- 没有做性能测试与 UI 自动化，工程只覆盖接口层。
