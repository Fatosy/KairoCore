from typing import Any, List, Dict, Awaitable, TypeVar
from fastapi import FastAPI as KarioCore
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.requests import Request
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from ..common.http import HttpStatusCode
from ..utils.log import get_logger

logger = get_logger()

T = TypeVar("T")

class Panic(Exception):
    """
    自定义业务异常类，用于处理应用程序中的业务逻辑错误
    
    Attributes:
        bussiness_code (int): 业务错误码
        message (str): 错误消息
        back_message (str): 原始错误消息
        status_code (HttpStatusCode): HTTP状态码
    """

    def __init__(self, bussiness_code: int, message: str, status_code: HttpStatusCode = HttpStatusCode.INTERNAL_SERVER_ERROR):
        """
        初始化Panic异常实例
        
        Args:
            bussiness_code (int): 业务错误码
            message (str): 错误消息
            status_code (HttpStatusCode, optional): HTTP状态码，默认为500 INTERNAL_SERVER_ERROR
            
        Raises:
            TypeError: 当status_code不是HttpStatusCode类型时抛出
        """
        if not isinstance(status_code, HttpStatusCode):
            raise TypeError("异常类的status_code参数必须是HttpStatusCode枚举类型")
        self.bussiness_code = bussiness_code
        self.message = message
        self.back_message = message
        self.status_code = status_code

    def to_response(self) -> JSONResponse:
        """
        将异常转换为JSON响应格式
        
        Returns:
            JSONResponse: 包含错误信息的JSON响应对象
                - code: 业务错误码
                - error: 布尔值，始终为True表示错误
                - message: 错误消息
        """
        res_json = {
            "code": self.bussiness_code,
            "error": True,
            "message": self.message,
        }
        
        # 返回 JSON 响应
        return JSONResponse(
            status_code=self.status_code,
            content=res_json
        )

    def msg_format(self, msg: str) -> 'Panic':
        """
        格式化错误消息并返回新的Panic实例
        
        Args:
            msg (str): 要添加到原始消息的额外信息
            
        Returns:
            Panic: 新的Panic实例，包含格式化后的错误消息
        """
        new_message = f'{self.message}: {msg}'
        newError = Panic(self.bussiness_code, new_message, self.status_code)
        return newError

class QueryResponse:
    """
    查询响应类，用于构建标准的查询结果响应
    
    Attributes:
        status_code (HttpStatusCode): HTTP状态码，默认为200 OK
        message (str): 响应消息，默认为"Success"
        bussiness_code (int): 业务状态码，默认为200
    """

    def __init__(self):
        """
        初始化QueryResponse实例
        
        设置默认的响应属性：
        - status_code: HttpStatusCode.OK (200)
        - message: "Success"
        - bussiness_code: 200
        """
        self.status_code = HttpStatusCode.OK
        self.message = "Success"
        self.bussiness_code = 200

    def to_response(self, data: List[Any]=[], total: int=0, limit:int=None, offset:int=None, msg: str=None):
        """
        将查询结果转换为标准JSON响应格式
        
        Args:
            data (List[Any]): 查询结果数据列表
            total (int): 数据总数量
            
        Returns:
            JSONResponse: 包含查询结果的JSON响应对象，格式如下：
                - code: 业务状态码
                - error: 布尔值，始终为False表示成功
                - message: 响应消息
                - data: 查询结果数据
                - total: 数据总数量
                - limit: 每页数据数量，可选
                - offset: 数据偏移量，可选
                - msg: 额外的消息，可选
        """
        pagination = {
            "limit": limit,
            "offset": offset
        }
        res_json = {
            "code": self.bussiness_code,
            "error": False,
            "message": self.message if not msg else msg,
            "data": data,
            "total": total,
            "pagination": pagination if limit and offset else {}
        }
        
        # 返回 JSON 响应
        return JSONResponse(
            status_code=self.status_code,
            content=res_json
        )

def register_exception_handlers(app: KarioCore):
    """
    注册全局异常处理器
    
    Args:
        app (KarioCore): KarioCore 应用实例
    """
    # 处理自定义的 Panic 异常
    @app.exception_handler(Panic)
    async def panic_exception_handler(request: Request, exc: Panic):
        logger.error(f"业务代码: {exc.bussiness_code}，业务异常: {exc.message}")
        return exc.to_response()
    
    # 处理 HTTP 异常
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.error(f"状态码: {exc.status_code}，HTTP异常: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "error": True,
                "message": exc.detail
            }
        )
    
    # 处理请求验证异常
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"请求验证失败: {exc.errors()}")
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": 422,
                "error": True,
                "message": "请求参数验证失败",
                "details": exc.errors()
            }
        )
    
    # 处理未捕获的服务器异常
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的服务器异常: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "error": True,
                "message": "服务器内部错误"
            }
        )
    
# 通用路由异常包装，确保接口层统一返回 KCFU_* 异常
async def exec_with_route_error(awaitable: Awaitable[T], error_const: Panic) -> T:
    # 参数校验：awaitable 必须为可等待对象，error_const 必须为 Panic 实例
    # 惰性导入集中定义的 Panic 常量，避免模块级循环依赖
    from ..common.errors import (
        KCP_EXEC_AWAITABLE_TYPE_ERROR,
        KCP_EXEC_PANIC_CONST_TYPE_ERROR,
    )
    if not hasattr(awaitable, "__await"):
        raise KCP_EXEC_AWAITABLE_TYPE_ERROR
    if not isinstance(error_const, Panic):
        raise KCP_EXEC_PANIC_CONST_TYPE_ERROR
    try:
        return await awaitable
    except Panic:
        raise
    except Exception as e:
        raise error_const.msg_format(str(e)) from e