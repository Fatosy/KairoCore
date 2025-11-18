"""
Taskiq 工具封装：提供统一的异步任务提交接口。

设计目标：
- 封装 broker/result backend 的初始化（默认使用 Redis）。
- 提供一个统一函数 `schedule_async(func, *args, **kwargs)` 用于提交异步函数到任务队列，全异步执行。
- 提供可复用的 TaskiqClient 类，便于在应用启动时统一管理。

使用说明：
- 需要先启动 worker：
  taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover
  或在你的应用模块中引用 `broker` 并使用相同路径。
- 在代码中：
  from KairoCore.utils.kc_taskiq import schedule_async
  await schedule_async(async_func, arg1, arg2, kw=1)

环境变量：
- TASKIQ_REDIS_URL（可选，默认：redis://localhost:6379/0）
- TASKIQ_QUEUE_NAME（可选，默认：kc_taskiq_queue）
- 若未设置 TASKIQ_REDIS_URL，可使用以下变量自动拼接：
  - TASKIQ_REDIS_HOST / PORT / DB
  - TASKIQ_REDIS_USERNAME / TASKIQ_REDIS_PASSWORD（或 REDIS_USERNAME / REDIS_PASSWORD）
  - TASKIQ_REDIS_SSL=true（使用 rediss://，需 Redis TLS）
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Awaitable, Callable, Optional
import importlib
from urllib.parse import quote

from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker
from taskiq.result import TaskiqResult
from taskiq_redis.exceptions import ResultIsMissingError

# 加载 .env（多路径尝试，增强跨项目导入时的鲁棒性）
def _load_env_multiple():
    # 1) 默认搜索（从调用位置向上）
    p1 = find_dotenv()
    if p1:
        load_dotenv(p1, override=False)
    # 2) 从当前工作目录搜索
    p2 = find_dotenv(usecwd=True)
    if p2:
        load_dotenv(p2, override=False)
    # 3) KairoCore 包根目录下的 .env（例如 /home/Coding/KairoCore/.env）
    pkg_root = Path(__file__).resolve().parents[1]
    p3 = pkg_root / ".env"
    if p3.exists():
        load_dotenv(p3, override=False)

_load_env_multiple()

def _resolve_redis_url() -> str:
    """解析 Redis 连接 URL，支持：
    - 直接提供 TASKIQ_REDIS_URL（优先）
    - 或通过主机/端口/DB 与用户名/密码自动拼接
    - 兼容 REDIS_* 通用变量，便于与现有配置复用

    说明：
    - 有密码但无用户名时，使用 ":password@" 的形式（默认用户）。
    - 开启 TLS 时，使用 rediss:// 前缀（需 Redis 启用 TLS）。
    """
    url = os.getenv("TASKIQ_REDIS_URL")
    if url:
        return url

    host = os.getenv("TASKIQ_REDIS_HOST") or os.getenv("REDIS_HOST", "localhost")
    port = os.getenv("TASKIQ_REDIS_PORT") or os.getenv("REDIS_PORT", "6379")
    db = os.getenv("TASKIQ_REDIS_DB") or os.getenv("REDIS_DB", "0")

    username = os.getenv("TASKIQ_REDIS_USERNAME") or os.getenv("REDIS_USERNAME")
    password = os.getenv("TASKIQ_REDIS_PASSWORD") or os.getenv("REDIS_PASSWORD")

    ssl_flag = str(os.getenv("TASKIQ_REDIS_SSL", "false")).lower() in {"1", "true", "yes"}
    scheme = "rediss" if ssl_flag else "redis"

    # 对用户名与密码进行 URL 编码，避免特殊字符破坏连接串
    user_enc = quote(username, safe="") if username else None
    pass_enc = quote(password, safe="") if password else None

    if user_enc and pass_enc:
        auth = f"{user_enc}:{pass_enc}@"
    elif pass_enc and not user_enc:
        # Redis 默认用户（ACL）使用 ":password@" 形式
        auth = f":{pass_enc}@"
    elif user_enc and not pass_enc:
        # 仅用户名（极少见），尝试 "username@"
        auth = f"{user_enc}@"
    else:
        auth = ""

    return f"{scheme}://{auth}{host}:{port}/{db}"


# 读取配置
TASKIQ_REDIS_URL = _resolve_redis_url()
TASKIQ_QUEUE_NAME = os.getenv("TASKIQ_QUEUE_NAME", "kc_taskiq_queue")


def _build_broker() -> RedisStreamBroker:
    """构建 RedisStreamBroker 并配置结果后端。"""
    result_backend = RedisAsyncResultBackend(
        redis_url=TASKIQ_REDIS_URL,
        # 建议加上过期，避免结果在 Redis 中无限堆积
        result_ex_time=3600,
    )
    broker = RedisStreamBroker(
        url=TASKIQ_REDIS_URL,
        queue_name=TASKIQ_QUEUE_NAME,
    ).with_result_backend(result_backend)
    return broker


# 暴露一个可供 worker CLI 使用的 broker 变量
broker = _build_broker()


class TaskiqClient:
    """Taskiq 客户端封装，用于应用内统一管理 broker 生命周期。"""

    def __init__(self):
        self._broker = broker
        self._started = False

    async def startup(self):
        if not self._started:
            await self._broker.startup()
            self._started = True

    async def shutdown(self):
        if self._started:
            await self._broker.shutdown()
            self._started = False

    def task(self):
        """返回装饰器，用于声明任务。"""
        return self._broker.task

    async def kiq(self, func: Callable[..., Awaitable[Any]], *args, **kwargs):
        """
        将异步函数提交为任务。

        分两种模式：
        1) 通用执行器模式（推荐）：通过预定义的通用任务在 worker 端按模块路径动态导入并执行函数。
           要求 func 可通过 `func.__module__` 与 `func.__qualname__` 在 worker 端被导入与解析。
        2) 若 func 已经被 @broker.task 装饰（具备 .kiq），则直接使用其 .kiq 提交。
        """

        # 启动 broker
        await self.startup()

        # 如果函数已装饰为 taskiq 任务，直接使用 .kiq
        if hasattr(func, "kiq") and callable(getattr(func, "kiq")):
            return await func.kiq(*args, **kwargs)

        # 否则，使用通用执行器：传递模块路径与限定名，由 worker 端动态导入执行
        module = getattr(func, "__module__", None)
        qualname = getattr(func, "__qualname__", getattr(func, "__name__", None))
        if not module or not qualname:
            raise ValueError("提供的函数不可导入：缺少 __module__ 或 __qualname__，请确保为可导入的顶层函数。")

        return await _exec_task.kiq(module, qualname, list(args), dict(kwargs))

    async def get_result(self, task_id: str) -> Optional[TaskiqResult]:
        """通过 task_id 读取任务结果（不阻塞）。
        如果结果尚不可用，返回 None。
        要求 broker 配置了异步结果后端（kc_taskiq 默认已启用 RedisAsyncResultBackend）。
        """
        await self.startup()
        rb = getattr(self._broker, "result_backend", None)
        if rb is None:
            raise RuntimeError("当前 broker 未配置 result_backend，无法读取任务结果。")
        # RedisAsyncResultBackend 是异步的
        try:
            res = await rb.get_result(task_id)
            return res
        except ResultIsMissingError:
            # 结果尚不可用（未写入或已过期），按约定返回 None
            return None

    async def wait_result(self, task_id: str, timeout: Optional[float] = None, poll_interval: float = 0.2) -> TaskiqResult:
        """轮询等待直到拿到任务结果或超时。
        - timeout: 最大等待秒数；为 None 时无限等待（不推荐）。
        - poll_interval: 轮询间隔秒数。
        """
        start = asyncio.get_event_loop().time()
        while True:
            res = await self.get_result(task_id)
            if res is not None:
                return res
            if timeout is not None and (asyncio.get_event_loop().time() - start) >= timeout:
                raise TimeoutError(f"等待任务结果超时：task_id={task_id}, timeout={timeout}s")
            await asyncio.sleep(poll_interval)


_default_client: Optional[TaskiqClient] = None


def _get_default_client() -> TaskiqClient:
    global _default_client
    if _default_client is None:
        _default_client = TaskiqClient()
    return _default_client


class KcTaskiqFunc:
    """
        封装 Taskiq 函数调用，支持异步提交与结果等待。
    """

    @staticmethod
    async def schedule_async(func: Callable[..., Awaitable[Any]], *args, **kwargs):
        """
        对外统一入口：提交一个异步任务函数及其参数，交给 Taskiq 全异步执行。

        用法：
            await schedule_async(my_async_func, 1, 2, kw=3)

        返回：TaskiqTask 对象（可用 .wait_result(timeout=...) 等方法获取结果）。
        """
        client = _get_default_client()
        return await client.kiq(func, *args, **kwargs)
    
    @staticmethod
    def schedule_async_sync(func: Callable[..., Awaitable[Any]], *args, **kwargs):
        """
        在非 async 上下文中提交异步任务：内部建立事件循环运行提交，返回 TaskiqTask。
        仅用于临时脚本或测试场景，生产代码建议始终在 async 上下文中使用 schedule_async。
        """
        return asyncio.run(KcTaskiqFunc.schedule_async(func, *args, **kwargs))
    
    @staticmethod
    async def get_task_result(task_id: str) -> Optional[TaskiqResult]:
        """通过 task_id 获取任务结果（若尚未完成，则返回 None）。"""
        client = _get_default_client()
        return await client.get_result(task_id)
    
    @staticmethod
    def get_task_result_sync(task_id: str) -> Optional[TaskiqResult]:
        """在同步环境中获取结果（一次性查询，不等待）。"""
        return asyncio.run(KcTaskiqFunc.get_task_result(task_id))
    
    @staticmethod
    async def wait_task_result(task_id: str, timeout: Optional[float] = None, poll_interval: float = 0.2) -> TaskiqResult:
        """等待指定 task_id 的结果，支持超时与轮询间隔设置。"""
        client = _get_default_client()
        return await client.wait_result(task_id, timeout=timeout, poll_interval=poll_interval)
    
    @staticmethod
    def wait_task_result_sync(task_id: str, timeout: Optional[float] = None, poll_interval: float = 0.2) -> TaskiqResult:
        """在同步环境中等待任务结果。"""
        return asyncio.run(KcTaskiqFunc.wait_task_result(task_id, timeout=timeout, poll_interval=poll_interval))


# 通用执行器任务：worker 端根据模块与限定名导入并执行函数
@broker.task(task_name="kc.exec")
async def _exec_task(module: str, qualname: str, args: list[Any], kwargs: dict[str, Any]):
    mod = importlib.import_module(module)
    # 逐级解析限定名（支持嵌套，如 ClassName.method）
    obj: Any = mod
    for part in qualname.split("."):
        obj = getattr(obj, part)
    if not asyncio.iscoroutinefunction(obj):
        raise TypeError(f"目标函数不是异步可等待的：{module}.{qualname}")
    return await obj(*args, **kwargs)