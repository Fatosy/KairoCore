"""
Taskiq 示例路由：

提供以下接口：
- POST /taskiq/submit          提交任务（不等待），返回 task_id
- GET  /taskiq/status/{task_id} 非阻塞查询状态：unfinished/pending 或 success/error
- GET  /taskiq/wait/{task_id}   可选等待超时；返回 success/error/timeout

函数约定：
- 顶层异步函数 add(a, b)，便于 worker 通过 kc.exec 导入执行（依赖 func.__module__/__qualname__）

使用前提：
- 已启动 Taskiq worker：
  taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover
- Redis 凭证配置正确（见 docs/TaskiqDoc.md）
"""

from typing import Optional
import asyncio
from KairoCore import kcRouter
from KairoCore.utils.kc_taskiq import KcTaskiqFunc, broker
from pydantic import BaseModel

router = kcRouter(tags=["Taskiq 示例"])


# 顶层异步函数（便于 worker 导入执行）
async def add(a: int, b: int) -> int:
    # 可选：模拟耗时
    await asyncio.sleep(0.5)
    return a + b


class AddBody(BaseModel):
    a: int
    b: int

@router.post("/taskiq/submit")
async def submit_task(body: AddBody):
    """提交任务但不等待，直接返回 task_id。"""
    task = await KcTaskiqFunc.schedule_async(add, body.a, body.b)
    return {"task_id": task.task_id}


class TaskQuery(BaseModel):
    task_id: str

@router.get("/taskiq/status")
async def get_task_status(query: TaskQuery):
    """非阻塞查询任务状态：未完成/成功/失败。"""
    task_id = query.task_id
    res = await KcTaskiqFunc.get_task_result(task_id)
    if res is None:
        # 更明确地标识任务“未完成”，并附带细节（当前为 pending）
        return {"task_id": task_id, "status": "unfinished", "detail": "pending"}

    if res.is_err:
        return {"task_id": task_id, "status": "error", "error": str(res.error)}
    else:
        return {"task_id": task_id, "status": "success", "result": res.return_value}


# 演示：阻塞等待指定时间并返回“超时/成功/失败”的状态
class WaitQuery(BaseModel):
    task_id: str
    timeout: Optional[float] = 5.0

@router.get("/taskiq/wait")
async def wait_task_until_done(query: WaitQuery):
    """等待任务在 timeout 秒内完成；超时返回 timeout。"""
    try:
        res = await KcTaskiqFunc.wait_task_result(query.task_id, timeout=query.timeout)
    except TimeoutError:
        return {"task_id": query.task_id, "status": "timeout", "timeout": query.timeout}

    if res.is_err:
        return {"task_id": task_id, "status": "error", "error": str(res.error)}
    else:
        return {"task_id": task_id, "status": "success", "result": res.return_value}


# 装饰器方式的任务（可选演示）：worker 可直接通过 task_name 路由执行
@broker.task(task_name="example.add")
async def add_task(a: int, b: int) -> int:
    await asyncio.sleep(0.2)
    return a + b


class AddDecoratedBody(BaseModel):
    a: int
    b: int

@router.post("/taskiq/submit_decorated")
async def submit_decorated(body: AddDecoratedBody):
    """提交已声明为 Taskiq 任务的函数。"""
    task = await add_task.kiq(body.a, body.b)
    return {"task_id": task.task_id}