import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI as KarioCore
from .code_generate.generator_router import router as generator_router
from .utils.panic import register_exception_handlers
from .utils.router import (
    register_routes, 
    print_registered_routes,
    create_init_router,
    add_cors_middleware
)
from .utils.log import get_logger

logger = get_logger()


def run_kairo(app_name: str, app_port: int=8000, app_host: str="0.0.0.0") -> KarioCore:
    """
    创建并配置 KairoCore 应用实例
    
    Returns:
        KarioCore: 配置好的 KairoCore 应用实例
    """
    load_dotenv()
    app = KarioCore()

    # 添加CORS中间件以解决跨域问题
    add_cors_middleware(app)

    # 注册初始化路由
    create_init_router(app)
    
    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册全局路由
    api_prefix = f"/{app_name}/api/"
    register_routes(app, api_prefix)

    # 注册代码生成器路由
    app.include_router(generator_router, prefix="/api", tags=["代码生成器"])

    # 打印全局路由
    print_registered_routes(app, app_host, app_port)
    
    uvicorn.run(app, host=app_host, port=app_port)