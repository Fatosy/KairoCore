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
    统一的HTTP响应封装
    - status_code: int 状态码
    - headers: Dict 响应头
    - data: Any 响应数据（自动解析 json / text / bytes）
    - raw: httpx.Response 原始响应对象
    """
    def __init__(self, resp: httpx.Response):
        self.status_code = resp.status_code
        self.headers = dict(resp.headers)
        self.raw = resp
        # 尝试解析响应数据
        self.data = None
        try:
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                self.data = resp.json()
            elif "text/" in content_type or content_type == "":
                self.data = resp.text
            else:
                self.data = resp.content
        except Exception as e:
            raise KCHT_PARSE_ERROR.msg_format(str(e))

    def is_ok(self) -> bool:
        return 200 <= self.status_code < 300

class KcHttpSession:
    """
    异步 HTTP 会话类
    - 支持连接池、超时、重试、日志
    - 与 FastAPI 兼容，可在应用启动/关闭时统一管理生命周期
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
            self.base_url = base_url
            self.timeout = httpx.Timeout(timeout)
            self.retries = max(0, retries)
            self.retry_backoff = max(0.0, retry_backoff)
            self.headers = dict(headers or {})
            self.verify = verify
            self.proxies = proxies
            # 连接池配置
            limits = httpx.Limits(max_keepalive_connections=max_keepalive, max_connections=max_keepalive)
            self._client: Optional[httpx.AsyncClient] = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
                verify=self.verify,
                proxies=self.proxies,
                limits=limits,
                follow_redirects=True,
            )
            logger.info(f"KcHttpSession 初始化完成 base_url={self.base_url}, timeout={timeout}, retries={self.retries}")
        except Exception as e:
            raise KCHT_INIT_ERROR.msg_format(str(e))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
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
        带重试的底层请求
        """
        attempt = 0
        last_exc: Optional[Exception] = None
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
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
                last_exc = e
                logger.warning(f"HTTP 超时: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_TIMEOUT_ERROR.msg_format(str(e))
            except httpx.HTTPStatusError as e:
                last_exc = e
                status = getattr(e.response, "status_code", None)
                logger.warning(f"HTTP 状态异常: {method} {url} status={status} attempt={attempt} err={e}")
                if attempt >= self.retries or (status and 400 <= status < 500):
                    # 客户端错误不重试
                    raise KCHT_STATUS_ERROR.msg_format(f"status={status}: {str(e)}")
            except httpx.HTTPError as e:
                last_exc = e
                logger.error(f"HTTP 请求异常: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_REQUEST_ERROR.msg_format(str(e))
            except Exception as e:
                last_exc = e
                logger.error(f"未知请求异常: {method} {url} attempt={attempt} err={e}")
                if attempt >= self.retries:
                    raise KCHT_REQUEST_ERROR.msg_format(str(e))
            # 退避等待
            attempt += 1
            await asyncio.sleep(self.retry_backoff * attempt)
        # 正常不会走到这里
        raise KCHT_REQUEST_ERROR.msg_format(str(last_exc) if last_exc else "未知错误")

    # 公开方法
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        return await self._request("GET", url, params=params, headers=headers, timeout=timeout)

    async def post(self, url: str, data: Optional[Union[Dict[str, Any], str, bytes]] = None, json: Optional[Any] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        return await self._request("POST", url, data=data, json=json, headers=headers, timeout=timeout)

    async def put(self, url: str, data: Optional[Union[Dict[str, Any], str, bytes]] = None, json: Optional[Any] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        return await self._request("PUT", url, data=data, json=json, headers=headers, timeout=timeout)

    async def delete(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> KcHttpResponse:
        return await self._request("DELETE", url, params=params, headers=headers, timeout=timeout)

    async def download(self, url: str, save_path: str, chunk_size: int = 1024 * 64, headers: Optional[Mapping[str, str]] = None, timeout: Optional[float] = None) -> str:
        """下载文件到指定路径，返回保存路径"""
        req_headers = dict(self.headers)
        if headers:
            req_headers.update(headers)
        req_timeout = self.timeout if timeout is None else httpx.Timeout(timeout)
        try:
            async with self._client.stream("GET", url, headers=req_headers, timeout=req_timeout) as resp:
                if resp.status_code >= 400:
                    raise KCHT_STATUS_ERROR.msg_format(f"status={resp.status_code}")
                with open(save_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size):
                        f.write(chunk)
            logger.info(f"下载完成: {url} -> {save_path}")
            return save_path
        except httpx.TimeoutException as e:
            raise KCHT_TIMEOUT_ERROR.msg_format(str(e))
        except httpx.HTTPError as e:
            raise KCHT_REQUEST_ERROR.msg_format(str(e))
        except Exception as e:
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