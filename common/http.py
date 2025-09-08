from enum import IntEnum
from fastapi import status

class HttpStatusCode(IntEnum):
    """封装常用的 FastAPI/Starlette HTTP 状态码常量。"""

    # --- 2xx 成功 (Success) ---
    OK = status.HTTP_200_OK
    """200 OK: 请求成功。"""

    CREATED = status.HTTP_201_CREATED
    """201 Created: 请求成功并且服务器创建了新的资源。"""

    ACCEPTED = status.HTTP_202_ACCEPTED
    """202 Accepted: 服务器已接受请求，但尚未处理完成。"""

    NO_CONTENT = status.HTTP_204_NO_CONTENT
    """204 No Content: 服务器成功处理了请求，但没有返回任何内容。"""

    # --- 3xx 重定向 (Redirection) ---
    MOVED_PERMANENTLY = status.HTTP_301_MOVED_PERMANENTLY
    """301 Moved Permanently: 请求的资源已被永久移动到新位置。"""

    NOT_MODIFIED = status.HTTP_304_NOT_MODIFIED
    """304 Not Modified: 资源未修改，可以使用缓存的版本。"""

    TEMPORARY_REDIRECT = status.HTTP_307_TEMPORARY_REDIRECT
    """307 Temporary Redirect: 请求的资源临时从不同的 URI 响应。"""

    PERMANENT_REDIRECT = status.HTTP_308_PERMANENT_REDIRECT
    """308 Permanent Redirect: 请求和所有未来的请求应重复发送到新 URI。"""

    # --- 4xx 客户端错误 (Client Error) ---
    BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    """400 Bad Request: 服务器认为客户端发送的请求存在语法错误或无法理解。"""

    UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
    """401 Unauthorized: 请求要求用户的身份认证。"""

    FORBIDDEN = status.HTTP_403_FORBIDDEN
    """403 Forbidden: 服务器理解请求，但是拒绝执行此请求。"""

    NOT_FOUND = status.HTTP_404_NOT_FOUND
    """404 Not Found: 服务器无法根据客户端的请求找到资源。"""

    METHOD_NOT_ALLOWED = status.HTTP_405_METHOD_NOT_ALLOWED
    """405 Method Not Allowed: 客户端使用了服务器不支持的请求方法。"""

    CONFLICT = status.HTTP_409_CONFLICT
    """409 Conflict: 请求与服务器的当前状态冲突。"""

    UNPROCESSABLE_ENTITY = status.HTTP_422_UNPROCESSABLE_ENTITY
    """422 Unprocessable Entity: 请求格式正确，但语义错误（如验证失败）。"""

    TOO_MANY_REQUESTS = status.HTTP_429_TOO_MANY_REQUESTS
    """429 Too Many Requests: 用户在给定的时间内发送了太多的请求（限流）。"""

    # --- 5xx 服务器错误 (Server Error) ---
    INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
    """500 Internal Server Error: 服务器遇到了不知道如何处理的情况。"""

    NOT_IMPLEMENTED = status.HTTP_501_NOT_IMPLEMENTED
    """501 Not Implemented: 服务器不支持请求的功能。"""

    BAD_GATEWAY = status.HTTP_502_BAD_GATEWAY
    """502 Bad Gateway: 作为网关或代理工作的服务器从上游服务器收到了无效的响应。"""

    SERVICE_UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE
    """503 Service Unavailable: 服务器暂时无法处理请求（通常是过载或维护）。"""

    GATEWAY_TIMEOUT = status.HTTP_504_GATEWAY_TIMEOUT
    """504 Gateway Timeout: 充当网关或代理的服务器，未及时从上游服务器获得请求。"""
