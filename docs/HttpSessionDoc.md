# 🌐 HTTP 会话使用说明（KcHttpSession）

本指南介绍如何使用项目内置的异步 HTTP 会话类 KcHttpSession，进行稳定可靠的外部接口调用。内容简洁明了，示例可直接复制运行。🚀

---

## ✨ 功能概览
- 统一的响应封装：`KcHttpResponse`（自动解析 JSON/Text/Bytes）
- 稳健的请求能力：超时、重试、退避、状态码检查、日志
- 连接池与性能：`httpx.AsyncClient` 连接复用与 keep-alive
- 可选参数：`base_url`、`headers`、`verify`、`proxies`、`timeout`、`retries`、`retry_backoff`
- 下载能力：`session.download(url, save_path)` 流式写入

---

## 📦 安装前提
项目已内置依赖 `httpx`，直接使用即可。

---

## 🚀 快速上手
```python
import asyncio
from KairoCore.utils.kc_http import KcHttpSession

async def main():
    # 建议在应用范围内复用会话（保持连接池与性能）
    async with KcHttpSession(base_url="https://api.example.com", timeout=10, retries=2) as session:
        # GET 请求（自动拼接 base_url）
        resp = await session.get("/v1/ping", params={"q": "hello"})
        print(resp.status_code, resp.data)

        # POST 请求（JSON）
        resp2 = await session.post("/v1/items", json={"name": "demo"})
        print(resp2.status_code, resp2.data)

asyncio.run(main())
```

---

## 📄 响应结构：KcHttpResponse
- `status_code: int` —— HTTP 状态码
- `headers: Dict[str, str]` —— 响应头
- `data: Any` —— 自动解析：
  - `application/json` → `resp.json()`（dict/list）
  - `text/*` 或空 `Content-Type` → `resp.text`（str）
  - 其他 → `resp.content`（bytes）
- `raw: httpx.Response` —— 原始响应对象
- `is_ok(): bool` —— 状态码是否在 2xx

示例：
```python
if resp.is_ok():
    print("✅ OK", resp.data)
else:
    print("❌ Bad status:", resp.status_code)
```

---

## 🔧 常用请求示例
```python
# 1) GET with params & 临时 headers 覆盖
resp = await session.get("/v1/search", params={"q": "kairo"}, headers={"X-Trace": "abc"})

# 2) POST: JSON 请求体
resp = await session.post("/v1/create", json={"title": "hello"})

# 3) POST: 表单或字符串/二进制数据
resp = await session.post("/v1/upload", data={"k": "v"})
# 或：resp = await session.post("/v1/raw", data=b"binary-data")

# 4) PUT / DELETE
await session.put("/v1/items/123", json={"name": "new"})
await session.delete("/v1/items/123")

# 5) 单次请求自定义超时（覆盖会话默认）
resp = await session.get("/v1/slow", timeout=3.0)
```

---

## 📥 文件下载
```python
save_path = await session.download("https://example.com/file.zip", 
                                  save_path="/tmp/file.zip",
                                  chunk_size=1024*64)
print("已保存到:", save_path)
```

---

## 🧯 错误处理
KcHttpSession 会在合适的时机抛出统一的错误类型，便于上层捕获与统一处理：
- `KCHT_INIT_ERROR` —— 会话初始化失败（参数/环境问题）
- `KCHT_TIMEOUT_ERROR` —— 请求超时
- `KCHT_STATUS_ERROR` —— 4xx/5xx 状态码错误（5xx可重试，4xx不重试）
- `KCHT_REQUEST_ERROR` —— 其他请求错误（网络/协议等）
- `KCHT_PARSE_ERROR` —— 响应解析失败（Content-Type 与内容不匹配等）

示例：
```python
from KairoCore.common.errors import (
    KCHT_TIMEOUT_ERROR, KCHT_STATUS_ERROR, KCHT_REQUEST_ERROR, KCHT_PARSE_ERROR
)

try:
    resp = await session.get("/v1/data")
    print(resp.data)
except KCHT_TIMEOUT_ERROR as e:
    print("⏳ 超时:", e)
except KCHT_STATUS_ERROR as e:
    print("🔢 状态码异常:", e)
except KCHT_PARSE_ERROR as e:
    print("🧩 解析失败:", e)
except KCHT_REQUEST_ERROR as e:
    print("📡 请求错误:", e)
```

---

## ⚙️ 参数说明与实践建议
- `base_url`：设置后可在请求中使用相对路径（如 `/v1/items`），更易维护。
- `timeout`：会话默认超时（秒）。可在单次请求中通过 `timeout=` 覆盖。
- `retries`：重试次数（默认 2）。服务器 5xx 会重试，客户端 4xx 不重试。
- `retry_backoff`：退避系数（默认 0.5），每次重试会 `await asyncio.sleep(backoff * attempt)`。
- `max_keepalive`：连接池并发上限（默认 10）。高并发场景可适当调大。
- `headers`：会话级公共 Header，可在每次请求 `headers` 临时覆盖/追加。
- `verify`：TLS 校验（True/False 或 CA 路径）。生产环境建议保持开启。
- `proxies`：代理（字符串或字典），如需通过网关访问外部服务。
- 日志：内置关键日志，便于排查（初始化、关闭、下载完成、重试等）。

最佳实践：
- 复用会话实例（例如挂载到 `app.state`）以最大化连接池收益。
- 为慢接口设置单次请求 `timeout`，避免阻塞。
- 对关键外部依赖适度提高 `retries` 与 `max_keepalive`。

---

## 🔌 与 FastAPI 生命周期集成（可选）
在 `app.py` 或 `example/your_project_name/main.py` 中：
```python
from KairoCore.utils.kc_http import KcHttpSession

kc_http = KcHttpSession(base_url="https://api.example.com", timeout=10, retries=2)
app.state.kc_http = kc_http

@app.on_event("startup")
async def startup_event():
    # 可在此进行健康检查或预热
    pass

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.kc_http.close()
```

---

## 📚 相关文件
- 会话实现：`utils/kc_http.py`
- 错误常量：`common/errors.py`

如需将鉴权（API_KEY 或 Token）加入外部请求的 `headers`，也可在会话级统一设置，例如：
```python
session = KcHttpSession(headers={"Authorization": "Bearer <token>", "X-API-Key": "<api_key>"})
```

祝你调用顺利！🌈