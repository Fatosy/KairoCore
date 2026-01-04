# 🚀 Taskiq 异步任务工具使用说明

本文档基于 `utils/kc_taskiq.py`，介绍如何使用 Taskiq 实现完全异步的分布式任务执行，并提供统一的任务提交函数。

---

## 📌 功能概览

你可以通过两种方式使用 Taskiq（按需选择）：

- 类方法入口（推荐简单直观）：
  - 提交任务：`KcTaskiqFunc.schedule_async(func, *args, **kwargs)`
  - 取结果：`KcTaskiqFunc.get_task_result(task_id)` 或 `KcTaskiqFunc.wait_task_result(task_id)`
  - 同步环境：`KcTaskiqFunc.schedule_async_sync(...)` 与 `KcTaskiqFunc.wait_task_result_sync(...)`
- 对象入口（需要更强的生命周期控制时）：
  - `TaskiqClient` 提供 `startup()/shutdown()` 与任务方法 `kiq()/get_result()/wait_result()`。

默认实现：Redis Stream Broker + RedisAsyncResultBackend
- 可靠投递（ack 支持）、结果写入 Redis（默认结果过期 1 小时）。

---

## ⚙️ 环境与依赖

1) 安装依赖

```bash
pip install -r requirements.txt
```

确保存在以下依赖：
- `taskiq`
- `taskiq-redis`

2) 环境变量（可选，支持密码/用户名/TLS）

kc_taskiq.py 会在导入时尝试多路径加载 .env（find_dotenv()/usecwd/KairoCore 包根目录），并解析以下变量：

- 首选：直接提供 URL
  - `TASKIQ_REDIS_URL=redis://127.0.0.1:6379/0`
  - 如 Redis 要求密码（默认用户）：`TASKIQ_REDIS_URL=redis://:your-pass@127.0.0.1:6379/0`
  - 如使用用户名+密码（ACL）：`TASKIQ_REDIS_URL=redis://user:your-pass@127.0.0.1:6379/0`
  - 如启用 TLS（你的 Redis 必须开启 TLS）：`TASKIQ_REDIS_URL=rediss://:your-pass@127.0.0.1:6379/0`

- 未提供 URL 时，自动拼接（并对用户名/密码做 URL 编码）：
  - `TASKIQ_REDIS_HOST` / `TASKIQ_REDIS_PORT` / `TASKIQ_REDIS_DB`
  - `TASKIQ_REDIS_USERNAME`（可选） / `TASKIQ_REDIS_PASSWORD`（建议设置）
  - `TASKIQ_REDIS_SSL`（true/1/yes 使用 rediss://）
  - 兼容通用变量：`REDIS_HOST`/`REDIS_PORT`/`REDIS_DB`/`REDIS_USERNAME`/`REDIS_PASSWORD`

- 在KairoCore项目中，需要额外开启终端运行broker
  - `PYTHONPATH=/home/your_project_name TASKIQ_REDIS_URL=redis://:123456@127.0.0.1:6379/10 taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover`
  - 因为在KairoCore项目中不指定项目目录的话，会报错

- 队列名：`TASKIQ_QUEUE_NAME=kc_taskiq_queue`


快速自检：

```bash
python -c "from KairoCore.utils.kc_taskiq import TASKIQ_REDIS_URL; print(TASKIQ_REDIS_URL)"
```

若输出为空或不含 @password，说明环境变量未生效，请按上述方式配置 .env 或在命令行直接注入。

---

## 🧵 启动 worker

Taskiq 需要独立的 worker 进程来消费任务。项目中已经暴露了 `broker` 变量，位于 `KairoCore.utils.kc_taskiq`。

启动方式：

```bash
# 常规启动（要求 KairoCore 可被 import 到）：
taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover

# 临时注入 Redis URL（仅密码，默认用户）：
TASKIQ_REDIS_URL=redis://:123456@127.0.0.1:6379/0 taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover

# 用户名+密码：
TASKIQ_REDIS_URL=redis://user:123456@127.0.0.1:6379/0 taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover

# 启用 TLS：
TASKIQ_REDIS_URL=rediss://:123456@127.0.0.1:6379/0 taskiq worker KairoCore.utils.kc_taskiq:broker --fs-discover
```

说明：
- `--fs-discover` 会自动扫描当前目录及子目录中名为 `tasks.py` 的模块并导入（可选）。
- 你也可以在命令中手动追加要导入的模块路径，如：
  `taskiq worker KairoCore.utils.kc_taskiq:broker my_project.tasks another.module.tasks`

---

## 🧪 代码中提交任务（教程与示例）

你可以选择“类方法入口”或“对象入口”两种风格，下面分别演示。

示例 1（类方法入口，推荐）：提交一个可导入的异步函数并等待结果

```python
# 文件 my_project/tasks.py（顶层异步函数，便于 worker 导入）
async def add(a: int, b: int) -> int:
    return a + b

# 任意位置提交任务（类方法入口）
from KairoCore.utils.kc_taskiq import KcTaskiqFunc

async def main():
    # 提交任务
    task = await KcTaskiqFunc.schedule_async(add, 1, 2)

    # 方式 1：直接等待 TaskiqTask 的结果
    result = await task.wait_result(timeout=5)
    if not result.is_err:
        print("返回值:", result.return_value)
    else:
        print("错误:", result.error)

    # 方式 2：通过 task_id 查询或等待（适合跨进程/跨模块场景）
    rid = task.task_id
    result2 = await KcTaskiqFunc.wait_task_result(rid, timeout=5)
    print("返回值2:", result2.return_value if not result2.is_err else result2.error)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

示例 1.1（不等待，接口轮询状态与结果）：提交后立刻返回 task_id，通过接口用 task_id 获取状态；如果已成功则返回结果

```python
from fastapi import APIRouter
from KairoCore.utils.kc_taskiq import KcTaskiqFunc

router = APIRouter(tags=["任务管理"])

# 顶层异步函数，便于 worker 导入
async def add(a: int, b: int) -> int:
    return a + b

@router.post("/tasks/submit")
async def submit_task(a: int, b: int):
    # 提交任务但不等待，直接返回 task_id
    task = await KcTaskiqFunc.schedule_async(add, a, b)
    return {"task_id": task.task_id}

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    # 非阻塞查询：若结果尚不可用（排队或执行中），返回未完成状态
    res = await KcTaskiqFunc.get_task_result(task_id)
    if res is None:
        # 更明确地标识任务“未完成”，并附带细节（当前为 pending）
        return {"task_id": task_id, "status": "unfinished", "detail": "pending"}

    # 已有结果，判断成功/失败
    if res.is_err:
        return {"task_id": task_id, "status": "error", "error": str(res.error)}
    else:
        return {"task_id": task_id, "status": "success", "result": res.return_value}
```

示例 2：已声明为 Taskiq 任务的函数（装饰器方式）

```python
from KairoCore.utils.kc_taskiq import broker

@broker.task(task_name="my.add")
async def add(a: int, b: int) -> int:
    return a + b

# 提交任务（两种方式等价）
task = await add.kiq(3, 4)
# 或
from KairoCore.utils.kc_taskiq import KcTaskiqFunc
task = await KcTaskiqFunc.schedule_async(add, 3, 4)
```

返回值获取：

```python
res = await task.wait_result(timeout=5)
if res.is_err:
    print("任务异常:", res.error)
else:
    print("执行耗时(s):", res.execution_time)
    print("返回值:", res.return_value)
```

示例 3（对象入口）：使用 TaskiqClient 管理生命周期并提交任务

```python
from KairoCore.utils.kc_taskiq import TaskiqClient

async def add(a: int, b: int) -> int:
    return a + b

async def main():
    tc = TaskiqClient()
    await tc.startup()
    try:
        # 对象版提交任务（等价于类方法入口）
        task = await tc.kiq(add, 1, 2)
        rid = task.task_id

        # 对象版等待结果
        result = await tc.wait_result(rid, timeout=5.0)
        if not result.is_err:
            print("返回值:", result.return_value)
        else:
            print("错误:", result.error)
    finally:
        await tc.shutdown()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## 🧠 通用执行器 kc.exec 的设计

在 `schedule_async` 中，为了避免每个函数都必须预先声明为任务，我们采用“通用执行器”任务：

- 任务名：`kc.exec`
- 参数：`module`（函数所在模块路径）、`qualname`（限定名）、`args`、`kwargs`
- 逻辑：worker 端通过 `importlib.import_module(module)` 导入模块，再逐级解析 `qualname` 获取目标函数并执行。

约束：
- 函数必须是“可导入的顶层异步函数”，能够通过 `__module__` 与 `__qualname__` 在 worker 端解析。
- 局部定义的函数、lambda、或非异步函数不适用（将抛出类型错误）。

适用场景：
- 一次性提交某些异步函数，无需改动原有代码结构。
- 对于高频任务，建议使用 `@broker.task` 声明并赋予固定 `task_name`，利于路由与管理。

补充：提交后返回的 `TaskiqTask` 包含 `task_id`，可用于异步/同步查询结果（见下节）。

---

## 💡 进阶与最佳实践

1) 结果过期
- 默认 `RedisAsyncResultBackend(result_ex_time=3600)`，结果保存 1 小时。
- 可根据场景调整或使用 `result_px_time` 毫秒级过期。

2) 通过 task_id 获取结果（类方法 / 对象方法）

```python
from KairoCore.utils.kc_taskiq import KcTaskiqFunc  # 类方法
from KairoCore.utils.kc_taskiq import TaskiqClient   # 对象方法

# 类方法：一次性查询与等待
resA = await KcTaskiqFunc.get_task_result(task_id)  # 未就绪返回 None
resB = await KcTaskiqFunc.wait_task_result(task_id, timeout=5.0)

# 对象方法：一次性查询与等待
tc = TaskiqClient()
await tc.startup()
try:
    resC = await tc.get_result(task_id)
    resD = await tc.wait_result(task_id, timeout=5.0)
finally:
    await tc.shutdown()

for res in [resA, resB, resC, resD]:
    if res and not res.is_err:
        print("返回值:", res.return_value)
```

2) 可靠性与吞吐
- Redis Stream Broker 支持 ack，适合需要可靠投递的场景。
- 队列名称、连接池大小、labels 等均可在 broker 初始化时调整。

3) 模块组织
- 为便于 `--fs-discover`，建议将任务函数集中在 `tasks.py` 模块或统一命名的包中。
- 复杂业务建议使用装饰器方式声明任务，并为不同任务设置唯一的 `task_name`。

4) 与 FastAPI 集成（示例）

```python
from fastapi import FastAPI
from KairoCore.utils.kc_taskiq import TaskiqClient

app = FastAPI()
tc = TaskiqClient()

@app.on_event("startup")
async def on_startup():
    await tc.startup()

@app.on_event("shutdown")
async def on_shutdown():
    await tc.shutdown()
```

5) 跨项目启动 worker 与导入路径
- 如果你在“其他项目”里运行 worker，确保当前 Python 解释器能 import 到 KairoCore：
  - 在 venv 中安装：`pip install -e /home/Coding/KairoCore`
  - 或设置 `PYTHONPATH=/home/Coding`
- 也可在你的项目中创建包装模块（例如 myproj/broker.py）：
  ```python
  from KairoCore.utils.kc_taskiq import broker
  ```
  然后启动：`taskiq worker myproj.broker:broker --fs-discover`

6) 同步环境下的便捷方法
```python
from KairoCore.utils.kc_taskiq import KcTaskiqFunc

t = KcTaskiqFunc.schedule_async_sync(add, 1, 2)
r = KcTaskiqFunc.wait_task_result_sync(t.task_id, timeout=5.0)
print(r.return_value)
```

---

## ❓ 常见问题（FAQ）

1) 提交任务后没有执行
- 检查是否已启动 worker（`taskiq worker KairoCore.utils.kc_taskiq:broker`）。
- 检查 Redis 连接是否可达、权限配置是否正确。

2) 等待结果时报错或超时
- 确认任务函数是异步函数（`async def`），且 worker 能正确导入该函数。
- 如为高耗时任务，请适当增大 `wait_result(timeout)`。

3) 在非 async 环境提交任务
- 使用 `schedule_async_sync(func, *args, **kwargs)`，内部会自动创建事件循环提交（适用于脚本或测试）。

---

## 参考

- `utils/kc_taskiq.py`
- Taskiq 文档：https://taskiq-python.github.io/
- taskiq-redis：https://github.com/taskiq-python/taskiq-redis
- 4) 报错：`redis.exceptions.AuthenticationError: Authentication required`
  - 说明 Redis 开启了认证，但连接未带凭证。请在 .env 或命令中提供密码：
    - 仅密码：`TASKIQ_REDIS_URL=redis://:your-pass@127.0.0.1:6379/0`
    - 用户名+密码：`TASKIQ_REDIS_URL=redis://user:your-pass@127.0.0.1:6379/0`
    - 或设置分散变量：`TASKIQ_REDIS_HOST/PORT/DB/PASSWORD`（kc_taskiq 会自动拼接）；如启用 TLS 设置 `TASKIQ_REDIS_SSL=true`。
  - 快速测试连接：
    ```bash
    redis-cli -h 127.0.0.1 -p 6379 -a your-pass ping
    ```
  - 检查解析后的 URL：
    ```bash
    python -c "from KairoCore.utils.kc_taskiq import TASKIQ_REDIS_URL; print(TASKIQ_REDIS_URL)"
    ```