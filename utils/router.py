import os
import importlib.util
import inspect
import functools
from pydantic import BaseModel
from typing import Any, Callable, Dict, List, Optional, get_type_hints, Union
from fastapi import FastAPI, APIRouter, params
from utils.panic import Panic
from utils.log import get_logger

app_logger = get_logger()
# --- 定义允许的参数名称 ---
ALLOWED_PARAM_NAMES = {"query", "body"}
# --- 定义参数到 FastAPI 依赖类型的映射 ---
PARAM_TO_DEPENDENCY_TYPE = {
    "query": params.Query,
    "body": params.Body,
}

def _create_enforced_wrapper(original_func: Callable, allowed_param_names: set):
    """
    创建一个包装函数，该函数强制执行允许的参数名称
    并为 'query' 和 'body' 注入 FastAPI 依赖项。
    """
    sig = inspect.signature(original_func)
    type_hints = get_type_hints(original_func)

    new_params = []
    old_params_list = list(sig.parameters.values())

    # 保留 'self' 参数（如果存在）
    has_self = old_params_list and old_params_list[0].name == 'self'
    if has_self:
        new_params.append(old_params_list[0])
        old_params_list = old_params_list[1:]

    # 为允许的参数创建新的参数规范，保持原始顺序
    for original_param in old_params_list:
        param_name = original_param.name
        if param_name in allowed_param_names:
            param_type = type_hints.get(param_name, Any)
            # 获取对应的 FastAPI 依赖类型，如果没有则默认为 Query
            dependency_type = PARAM_TO_DEPENDENCY_TYPE.get(param_name, params.Query)

            # 创建新的参数，注入 FastAPI 依赖 (Query, Body)
            new_param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                # 使用原始参数的默认值，包装在 FastAPI 依赖中
                default=dependency_type(default=original_param.default),
                annotation=param_type
            )
            new_params.append(new_param)
        # else: 忽略不允许的参数（理论上 enforce_signature 已经检查过，这里不会出现）

    # 创建新的签名
    new_sig = sig.replace(parameters=new_params)

    # --- 提取公共的异常处理逻辑 ---
    def _handle_exception(e, func_name):
        """处理路由函数内部异常的公共逻辑"""
        if isinstance(e, Panic):
            raise # 重新抛出 Panic
        else:
            # --- 记录路由处理函数内部的非 Panic 异常 ---
            app_logger.error(
                f"路由处理函数 '{func_name}' 内部发生异常: {e}",
                exc_info=True
            )
            # 重新抛出异常，让全局异常处理器捕获
            raise

    # --- 创建包装器函数 ---
    if inspect.iscoroutinefunction(original_func):
        @functools.wraps(original_func) # 使用 wraps 简化
        async def wrapper(*args, **kwargs):
            # 过滤 kwargs，只保留允许的参数
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_param_names}
            try:
                return await original_func(*args, **filtered_kwargs)
            except Exception as e:
                _handle_exception(e, original_func.__name__)
    else:
        @functools.wraps(original_func) # 使用 wraps 简化
        def wrapper(*args, **kwargs):
            # 过滤 kwargs，只保留允许的参数
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_param_names}
            try:
                return original_func(*args, **filtered_kwargs)
            except Exception as e:
                _handle_exception(e, original_func.__name__)

    # 将新的签名赋给包装器
    wrapper.__signature__ = new_sig
    # 注意：通常不需要手动设置 __annotations__，因为 functools.wraps 和 __signature__ 已足够
    # 如果确实需要，应该基于 new_sig 或 type_hints 构建，而不是额外的 dict
    # wrapper.__annotations__ = {p.name: p.annotation for p in new_params if p.name != 'self'} # 示例，通常不需要

    return wrapper

def enforce_signature(router: APIRouter):
    """
    检查并强制执行 APIRouter 内所有路由处理函数的签名。
    就地修改路由器。
    """
    # --- 记录开始强制签名 ---
    router_prefix = getattr(router, 'prefix', 'N/A')
    # app_logger.debug(f"开始对路由器 {router_prefix} 强制执行签名。")

    for route in router.routes:
        original_endpoint = route.endpoint
        sig = inspect.signature(original_endpoint)
        # 获取原始函数参数名（排除 'self'）
        param_names = {p.name for p in sig.parameters.values() if p.name != 'self'}

        # 检查是否有无效参数
        invalid_params = param_names - ALLOWED_PARAM_NAMES
        if invalid_params:
            error_msg = (
                f"路由函数 '{original_endpoint.__name__}' 使用了无效的参数名: {sorted(invalid_params)}。 "
                f"仅允许使用参数名 {sorted(ALLOWED_PARAM_NAMES)}。"
            )
            app_logger.error(error_msg)
            raise Panic(
                code=500,
                msg="路由签名强制执行失败",
                error=error_msg,
                data={"函数名": original_endpoint.__name__, "文件": inspect.getfile(original_endpoint)}
            )

        try:
            # 创建并应用强制签名的包装器
            # 传递 ALLOWED_PARAM_NAMES 集合，供 _create_enforced_wrapper 内部使用
            enforced_wrapper = _create_enforced_wrapper(original_endpoint, ALLOWED_PARAM_NAMES)
            route.endpoint = enforced_wrapper
            # app_logger.debug(f"已为路由处理函数 '{original_endpoint.__name__}' 强制执行签名。")
        except Panic:
            # 重新抛出 Panic
            raise
        except Exception as e:
            error_msg = f"无法为 '{original_endpoint.__name__}' 创建强制执行包装器: {str(e)}"
            app_logger.critical(error_msg, exc_info=True)
            raise Panic(
                code=500,
                msg="路由签名强制执行失败",
                error=error_msg,
                data={"函数名": original_endpoint.__name__, "文件": inspect.getfile(original_endpoint)}
            )

    app_logger.debug("路由器签名强制执行完成。")
    return router


def register_routes(app: FastAPI, base_prefix: str = "", actions_dir: str = "action"):
    """
    扫描 'actions_dir' 目录并自动注册其中定义的 FastAPI 路由器 (APIRouter)。
    每个子目录被视为一个模块，该模块下应包含一个定义了 'router' 的 Python 文件。
    该函数会扫描子目录中的所有 .py 文件来查找 router 实例。
    在注册前会强制执行函数签名检查 (enforce_signature)。

    Args:
        app (FastAPI): FastAPI 应用实例。
        actions_dir (str): 包含路由模块的根目录名称。默认为 "action"。
        base_prefix (str): 应用于所有注册路由的全局前缀。默认为空字符串。
                           注意：确保 base_prefix 格式正确，例如以 '/' 开头。
    """
    app_logger.info(f"开始扫描 Action 目录: {actions_dir}")

    if not os.path.isdir(actions_dir):
        error_msg = f"未找到 Action 目录 '{actions_dir}'。"
        app_logger.error(error_msg)
        return

    # 确保 base_prefix 格式正确 (以 '/' 开头，除非是空字符串)
    normalized_base_prefix = base_prefix if base_prefix == "" or base_prefix.startswith('/') else f"/{base_prefix}"
    normalized_base_prefix = normalized_base_prefix.rstrip('/') # 移除末尾的 '/' 以防重复
    
    for module_name in os.listdir(actions_dir):
        module_path = os.path.join(actions_dir, module_name)
        if os.path.isdir(module_path):
            # app_logger.debug(f"正在扫描模块目录: {module_path}")
            
            # 查找模块目录中的所有 .py 文件
            router_files = []
            for file in os.listdir(module_path):
                if file.endswith('.py') and file != '__init__.py':
                    router_files.append(os.path.join(module_path, file))
            
            if not router_files:
                app_logger.warning(f"在模块目录 {module_path} 中未找到 Python 文件")
                continue
                
            # app_logger.debug(f"找到 {len(router_files)} 个候选文件: {router_files}")
            
            # 遍历所有 .py 文件查找 router
            for router_file in router_files:
                # app_logger.debug(f"正在检查文件: {router_file}")
                
                # 构造模块名
                file_name_without_ext = os.path.splitext(os.path.basename(router_file))[0]
                full_module_name = f"action.{module_name}.{file_name_without_ext}"
                
                try:
                    spec = importlib.util.spec_from_file_location(full_module_name, router_file)
                    if spec is None:
                        app_logger.error(f"无法为文件 {router_file} 创建模块规范 (spec)。")
                        continue
                        
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # app_logger.debug(f"成功导入模块: {router_file}")
                    
                except Exception as e:
                    error_msg = f"从 {router_file} 导入模块失败: {e}"
                    app_logger.error(error_msg, exc_info=True)
                    continue

                # 检查模块中是否有 router
                router = getattr(module, 'router', None)
                if isinstance(router, APIRouter):
                    try:
                        # 强制执行函数签名检查
                        enforce_signature(router)
                        # 构造该模块的路由前缀
                        module_prefix = f"/{module_name}"
                        # 拼接完整前缀
                        full_prefix = f"{normalized_base_prefix}{module_prefix}"
                        app.include_router(router, prefix=full_prefix)
                        success_msg = f"已注册（并强制执行签名）来自 {router_file} 的路由器，完整前缀为 {full_prefix}"
                        # app_logger.info(success_msg)
                        break  # 找到 router 后就不再继续查找
                    except Panic:
                        # 重新抛出 Panic 异常
                        raise
                    except Exception as e:
                        error_msg = f"注册路由器 {router_file} 时失败: {e}"
                        app_logger.error(error_msg, exc_info=True)
                        raise RuntimeError(error_msg) from e
                else:
                    app_logger.debug(f"在 {router_file} 中未找到有效的 'router' (APIRouter 实例)")
            
            # 如果遍历完所有文件都没找到 router
            if not isinstance(router, APIRouter):
                warn_msg = f"在模块目录 {module_path} 中未找到有效的 'router' (APIRouter 实例)。"
                app_logger.warning(warn_msg)

    app_logger.info("Action 目录扫描和路由注册完成。")


def print_registered_routes(app: FastAPI, app_host: str, app_port: int):
    """
    打印所有已注册的路由信息
    
    Args:
        app (FastAPI): FastAPI 应用实例
    """
    app_logger = get_logger()
    app_logger.info("已注册的路由列表:")
    app_logger.info("-" * 80)
    
    # 按路径分组路由
    routes_by_path = {}
    for route in app.routes:
        if hasattr(route, 'path'):
            if route.path not in routes_by_path:
                routes_by_path[route.path] = []
            routes_by_path[route.path].append(route)
    
    # 打印路由信息
    for path, routes in routes_by_path.items():
        methods = []
        for route in routes:
            if hasattr(route, 'methods'):
                methods.extend(list(route.methods))
        
        # 去重并排序
        methods = sorted(list(set(methods)))
        path = f"http://{app_host}:{app_port}{path}" if app_host and app_port else path
        
        app_logger.info(f"路由: [{', '.join(methods) if methods else 'N/A'}] {path}")
        # app_logger.info(f"  方法: {', '.join(methods) if methods else 'N/A'}")
        
        # 打印处理函数信息
        #for route in routes:
        #    if hasattr(route, 'endpoint'):
        #        func_name = route.endpoint.__name__
        #        module_name = route.endpoint.__module__
        #        app_logger.info(f"  处理函数: {module_name}.{func_name}")
    
    app_logger.info(f"总共注册了 {len(app.routes)} 个路由")
    app_logger.info("-" * 80)

# --- 示例调用 ---
# 假设你的 main.py 或应用初始化代码中这样调用：
# from fastapi import FastAPI
# from .action import register_routes # 假设 register_routes 在 action 包下
#
# app = FastAPI()
# register_routes(app, actions_dir="action", base_prefix="/api/v1")
# # 这样会尝试注册 action/users/users.py 中的 router 到 /api/v1/users