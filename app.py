import uvicorn
from fastapi import FastAPI as KarioCore
from .utils.panic import register_exception_handlers
from .utils.router import (
    register_routes, 
    print_registered_routes,
    create_init_router
)
from .utils.log import get_logger

logger = get_logger()

def run_kairo(app_name: str, app_port: int=8000, app_host: str="0.0.0.0") -> KarioCore:
    """
    创建并配置 KairoCore 应用实例
    
    Returns:
        KairoCore: 配置好的 KairoCore 应用实例
    """
    app = KarioCore()

    # 注册初始化路由
    create_init_router(app)
    
    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册全局路由
    api_prefix = f"/{app_name}/api/"
    register_routes(app, api_prefix)

    # 打印全局路由
    print_registered_routes(app, app_host, app_port)
    
    uvicorn.run(app, host=app_host, port=app_port)