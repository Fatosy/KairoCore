import asyncio
from typing import Any, Dict, Optional, Union, Mapping

import httpx

from ..utils.log import get_logger
from ..common.errors import (
    KCHT_INIT_ERROR,
    KCHT_REQUEST_ERROR,
    KCHT_TIMEOUT_ERROR,
    KCHT_STATUS_ERROR,
    KCHT_PARSE_ERROR,
)

logger = get_logger()

class KcHttpResponse:
    """
    统一的 HTTP 响应封装
    
    字段：
    - status_code: int 状态码
    - headers: Dict[str, str] 响应头
    - data: Any 解析后的数据（按 Content-Type 自动解析 json / text / bytes）
    - raw: httpx.Response 原始响应对象，保留供高级使用
    
    说明：
    - 当解析失败时抛出 KCHT_PARSE_ERROR，调用方应捕获并按需处理。
    - is_ok() 用于快速判断 2xx 响应。
    """
    def __init__(self, resp: httpx.Response):
        # 基本属性直接从原始响应复制
        self.status_code = resp.status_code
        self.headers = dict(resp.headers)
        self.raw = resp
        # 尝试解析响应数据
        self.data = None
        try:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                self.data = resp.json()  # 自动 JSON 解析
            elif "text/" in content_type or content_type == "":
                self.data = resp.text   # 文本或未声明类型，按文本处理
            else:
                self.data = resp.content  # 其他类型按二进制处理
        except Exception as e:
            # 解析失败统一包装为 PARSE_ERROR，便于上层捕获
            raise KCHT_PARSE_ERROR.msg_format(str(e))

    def is_ok(self) -> bool:
        """是否为 2xx 状态。"""
        return 200 <= self.status_code < 300

class KcHttpSession:
    """
    异步 HTTP 会话类（基于 httpx.AsyncClient）。
    
    能力：
    - 连接池与超时配置
    - 带退避的重试（超时/服务端错误）
    - 统一的异常与日志
    - 便捷的请求方法与下载方法
    
    典型用法：
    - 在应用启动时创建实例，并在关闭时调用 close() 释放资源
    - 或通过 async with 语法在局部作用域中使用
    """
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        max_keepalive: int = 10,
        retries: int = 2,
        retry_backoff: float = 0.5,
        headers: Optional[Mapping[str, str]] = None,
        verify: Union[bool, str] = True,
        proxies: Optional[Union[str, Dict[str, str]]] = None,
    ):
        try:
            # 基础配置与参数归一化
            self.base_url = base_url
            self.timeout = httpx.Timeout(timeout)
            self.retries = max(0, retries)
            self.retry_backoff = max(0.0, retry_backoff)
            self.headers = dict(headers or {})  # 会话级默认请求头（可用于鉴权）
            self.verify = verify
            self.proxies = proxies
            # 连接池配置（max_keepalive 用于并发连接与复用）
            limits = httpx.Limits(max_keepalive_connections=max_keepalive, max_connections=max_keepalive)
            # 创建底层异步客户端
            self._client: Optional[httpx.AsyncClient] = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
                verify=self.verify,
                proxy=self.proxies,
                limits=limits,
                follow_redirects=True,  # 默认为允许跟随重定向
            )
            logger.info(f"KcHttpSession 初始化完成 base_url={self.base_url}, timeout={timeout}, retries={self.retries}")
        except Exception as e:
            # 初始化失败统一包装为 INIT_ERROR
            raise KCHT_INIT_ERROR.msg_format(str(e))

    async def __aenter__(self):
        """支持 async with 用法。"""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """退出时自动关闭底层客户端。"""
        await self.close()

    async def close(self):
        """关闭会话，释放连接池资源。"""
        if self._client:
            await self._client.aclose()
            logger.info("KcHttpSession 已关闭")

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> KcHttpResponse:
        """
        底层请求方法（带重试与退避）。
        
        流程：
        1) 合并会话级与方法级的 headers
        2) 处理超时参数（方法级优先）
        3) 循环重试：
           - 5xx 作为服务端错误可重试
           - 4xx 客户端错误不重试，直接抛出状态异常
           - 超时按配置重试，最后一次抛出超时异常
        4) 请求成功后封装为 KcHttpResponse 返回
        """
        attempt = 0
        last_exc: Optional[Exception] = None
        # 合并请求头：方法级覆盖会话级
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        # 处理方法级超时
        req_timeout = self.timeout if timeout is None else httpx.Timeout(timeout)
        while attempt <= self.retries:
            try:
                logger.debug(f"HTTP {method} {url} attempt={attempt} params={params} headers={req_headers}")
                resp = await self._client.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=req_headers,
                    timeout=req_timeout,
                )
                # 状态码检查：500+ 作为可重试的服务端错误，400-499 直接抛出客户端错误
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError("server error", request=resp.request, response=resp)
                elif resp.status_code >= 400:
                    raise httpx.HTTPStatusError("client error", request=resp.request, response=resp)
                result = KcHttpResponse(resp)
                return result
            except httpx.TimeoutException as e:
                # 超时：记录最后异常并决定是否结束重试
                last_exc = e
                logger.warning(f"HTTP 超时: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_TIMEOUT_ERROR.msg_format(str(e))
            except httpx.HTTPStatusError as e:
                # 状态码异常：4xx 不重试；5xx 可根据 attempt 决定重试
                last_exc = e
                status = getattr(e.response, "status_code", None)
                logger.warning(f"HTTP 状态异常: {method} {url} status={status} attempt={attempt} err={e}")
                if attempt >= self.retries or (status and 400 <= status < 500):
                    # 客户端错误不重试
                    raise KCHT_STATUS_ERROR.msg_format(f"status={status}: {str(e)}")
            except httpx.HTTPError as e:
                # httpx 的其他错误（网络异常等）
                last_exc = e
                logger.error(f"HTTP 请求异常: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_REQUEST_ERROR.msg_format(str(e))
            except Exception as e:
                # 未知异常统一包装为 REQUEST_ERROR
                last_exc = e
                logger.error(f"未知请求异常: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_REQUEST_ERROR.msg_format(str(e))
            # 退避等待（逐次递增），继续下一次尝试
            attempt += 1
            await asyncio.sleep(self.retry_backoff * attempt)
        # 正常不会走到这里，兜底抛出最后一个异常信息
        raise KCHT_REQUEST_ERROR.msg_format(str(last_exc) if last_exc else "未知错误")

    # 公开方法
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        """GET 请求。"""
        return await self._request("GET", url, params=params, headers=headers, timeout=timeout)

    async def post(self, url: str, data: Optional[Union[Dict[str, Any], str, bytes]] = None, json: Optional[Any] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        """POST 请求（支持 form/data/raw 或 JSON）。"""
        return await self._request("POST", url, data=data, json=json, headers=headers, timeout=timeout)

    async def put(self, url: str, data: Optional[Union[Dict[str, Any], str, bytes]] = None, json: Optional[Any] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        """PUT 请求（支持 form/data/raw 或 JSON）。"""
        return await self._request("PUT", url, data=data, json=json, headers=headers, timeout=timeout)

    async def delete(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        """DELETE 请求（支持查询参数）。"""
        return await self._request("DELETE", url, params=params, headers=headers, timeout=timeout)

    async def download(self, url: str, save_path: str, chunk_size: int = 1024 * 64, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> str:
        """流式下载文件到指定路径，返回保存路径。
        
        - 使用 httpx.AsyncClient.stream 进行边读边写，适合大文件
        - chunk_size 默认 64KB，可按网络与磁盘性能调整
        - 支持方法级 headers 与超时覆盖会话级配置
        - 4xx 直接视为状态异常；其他错误分别包装为超时/请求错误
        """
        # 合并请求头与超时设置
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        req_timeout = self.timeout if timeout is None else httpx.Timeout(timeout)
        try:
            async with self._client.stream("GET", url, headers=req_headers, timeout=req_timeout) as resp:
                if resp.status_code >= 400:
                    # 客户端或服务端错误直接抛出状态异常
                    raise KCHT_STATUS_ERROR.msg_format(f"status={resp.status_code}")
                with open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size):
                        f.write(chunk)
            logger.info(f"下载完成: {url} -> {save_path}")
            return save_path
        except httpx.TimeoutException as e:
            # 超时错误单独包装，便于调用层区分
            raise KCHT_TIMEOUT_ERROR.msg_format(str(e))
        except httpx.HTTPError as e:
            # 其他 HTTP 错误统一包装为请求错误
            raise KCHT_REQUEST_ERROR.msg_format(str(e))
        except Exception as e:
            # 未知错误统一包装为请求错误
            raise KCHT_REQUEST_ERROR.msg_format(str(e))

# FastAPI 生命周期集成示例（可选）
# 在 app.py 或 main.py 中：
# from .utils.kc_http import KcHttpSession
# kc_http = KcHttpSession(base_url="https://api.example.com", timeout=10, retries=2)
# app.state.kc_http = kc_http
# @app.on_event("startup")
# async def startup_event():
#     pass
# @app.on_event("shutdown")
# async def shutdown_event():
#     await app.state.kc_http.close()