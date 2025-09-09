from typing import Any, List, Dict
from fastapi import FastAPI as KarioCore
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from starlette.requests import Request
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from ..common.http import HttpStatusCode
from ..utils.log import get_logger

logger = get_logger()

class Panic(Exception):

    def __init__(self, bussiness_code: int, message: str, status_code: HttpStatusCode = HttpStatusCode.INTERNAL_SERVER_ERROR):
        if not isinstance(status_code, HttpStatusCode):
            raise TypeError("异常类的status_code参数必须是HttpStatusCode枚举类型")
        self.bussiness_code = bussiness_code
        self.message = message
        self.back_message = message
        self.status_code = status_code

    def to_response(self):
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

class QueryResponse:

    def __init__(self):
        self.status_code = HttpStatusCode.OK
        self.message = "Success"
        self.bussiness_code = 200

    def to_response(self, data: List[Any], total: int):
        res_json = {
            "code": self.bussiness_code,
            "error": False,
            "message": self.message,
            "data": data,
            "total": total
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
    
