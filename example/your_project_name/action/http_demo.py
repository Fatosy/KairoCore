"""
HTTP 会话示例路由：演示如何在项目中使用 KcHttpSession 进行异步 HTTP 请求
- GET 示例：请求 httpbin.org/get 并回显查询参数
- POST 示例：请求 httpbin.org/post 并回显提交的 JSON
- 状态码示例：请求 httpbin.org/status/{code} 展示错误处理（4xx/5xx）
- 下载示例：下载 httpbin 的图片到本地 /tmp 目录

说明：
- 仅使用框架允许的参数名 query/body，保持与现有签名强制规则一致
- 使用 async with 上下文管理自动释放连接资源
"""
from typing import Optional
from pydantic import BaseModel

from KairoCore import kcRouter, kQuery, KcHttpSession

# 分组到文档中 "HTTP会话示例"
router = kcRouter(tags=["HTTP会话示例"])

class GetDemoQuery(BaseModel):
    foo: Optional[str] = "bar"

class PostDemoBody(BaseModel):
    x: int = 123
    msg: str = "hello"

class StatusQuery(BaseModel):
    code: int = 200

class DownloadQuery(BaseModel):
    # 需要下载的 URL（示例默认是 httpbin 的 png 图片）
    url: str = "https://httpbin.org/image/png"
    # 保存路径（默认保存到 /tmp/httpbin.png）
    save_path: str = "/tmp/httpbin.png"

@router.get("/get")
async def demo_get(query: GetDemoQuery):
    """演示 GET 请求：将 query.foo 作为查询参数发送到 httpbin，并返回响应"""
    async with KcHttpSession(base_url="https://httpbin.org", timeout=10, retries=2) as http:
        resp = await http.get("/get", params={"foo": query.foo})
        # 统一响应封装，直接返回 httpbin 的响应数据
        return kQuery.to_response(data=resp.data, msg="GET 成功")

@router.post("/post")
async def demo_post(body: PostDemoBody):
    """演示 POST 请求：将 body 序列化为 JSON 发送到 httpbin，并返回响应"""
    async with KcHttpSession(base_url="https://httpbin.org", timeout=10, retries=2) as http:
        resp = await http.post("/post", json=body.model_dump())
        return kQuery.to_response(data=resp.data, msg="POST 成功")

@router.get("/status")
async def demo_status(query: StatusQuery):
    """演示状态码处理：请求 /status/{code}，当 code 为 4xx/5xx 时会抛出统一异常并被全局捕获"""
    async with KcHttpSession(base_url="https://httpbin.org", timeout=5, retries=1) as http:
        # 2xx 时正常返回；4xx/5xx 时将抛出 Panic（KCHT_STATUS_ERROR/KCHT_REQUEST_ERROR），由全局异常处理器接管
        resp = await http.get(f"/status/{query.code}")
        return kQuery.to_response(data={"status_code": resp.status_code}, msg="状态码请求成功")

@router.get("/download")
async def demo_download(query: DownloadQuery):
    """演示文件下载：下载指定 URL 到本地 save_path"""
    async with KcHttpSession(timeout=10, retries=1) as http:
        path = await http.download(url=query.url, save_path=query.save_path)
        return kQuery.to_response(data={"saved": path}, msg="下载完成")