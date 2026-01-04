# RabbitMQ 工具与在线状态检测使用说明

本文档介绍 `utils/kc_rabbitmq.py` 中提供的两个核心组件：

- `RabbitMQClient`：轻量级 RabbitMQ 客户端封装，统一管理连接参数，提供交换机/队列声明、绑定、消息发布与基本 QOS 能力。
- `PresenceManager`：基于 RabbitMQ 的多服务在线状态检测工具，支持心跳广播、监控端监听与在线判断，以及 RPC 风格的 ping 探测。

在阅读本文档之前，请确保你已安装依赖并配置好环境变量（见下文）。

---

## 环境准备

1) 安装依赖

```bash
pip install -r requirements.txt
```

该模块依赖 `pika`：

```
pika==1.3.2
```

2) 配置环境变量（`.env` 或系统环境变量）

在项目根目录的 `.env.example` 已提供示例，可复制为 `.env` 并按需修改：

```
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_VHOST=/
RABBITMQ_HEARTBEAT=30
```

说明：
- `RABBITMQ_HOST`/`RABBITMQ_PORT`：RabbitMQ 服务地址与端口。
- `RABBITMQ_USER`/`RABBITMQ_PASSWORD`：认证信息（开发环境默认 `guest/guest`，生产必须改为安全账号）。
- `RABBITMQ_VHOST`：虚拟主机（默认 `/`）。
- `RABBITMQ_HEARTBEAT`：连接心跳（秒），用于保活与检测断线，默认 30。

---

## 组件概览

### RabbitMQClient

功能要点：
- 统一连接参数管理（支持环境变量与构造参数）。
- 声明交换机 / 队列 / 绑定。
- 发布消息（自动 JSON 序列化、消息持久化开关、TTL）。
- 基本 QOS：`basic_qos(prefetch_count=N)`。
- 发布确认：尝试 `confirm_delivery()`（部分环境可能不支持，已容错）。

线程安全：
- `BlockingConnection/Channel` 不是线程安全的，请不要跨线程共享。
- 若需要在多个线程中使用，请在每个线程中创建独立的连接与通道。

常用 API：
- `open_connection() -> BlockingConnection`：创建并返回新连接，失败抛出 `KCRM_CONNECT_ERROR`。
- `open_channel(conn) -> BlockingChannel`：基于连接创建通道，失败抛出 `KCRM_CHANNEL_ERROR`。
- `declare_exchange(ch, name, ex_type="topic", durable=True, auto_delete=False)`：声明交换机，失败抛出 `KCRM_DECLARE_ERROR`。
- `declare_queue(ch, name, durable=True, exclusive=False, auto_delete=False, arguments=None) -> (queue, msg_cnt, consumer_cnt)`：声明队列，失败抛出 `KCRM_DECLARE_ERROR`。
- `bind_queue(ch, queue, exchange, routing_key)`：队列绑定到交换机，失败抛出 `KCRM_DECLARE_ERROR`。
- `set_prefetch(ch, prefetch_count=10)`：设置预取数，失败抛出 `KCRM_CHANNEL_ERROR`。
- `publish(ch, exchange, routing_key, body, content_type="application/json", persistent=True, expiration_ms=None, headers=None, reply_to=None, correlation_id=None)`：发布消息，失败抛出 `KCRM_PUBLISH_ERROR`。

错误处理：
- 统一使用 `common/errors.py` 中的 `KCRM_*` 常量封装错误，便于上层捕获与日志记录。

### PresenceManager

设计与能力：
- 使用 `topic` 交换机 `kc.presence` 承载心跳广播。
- 心跳：每个服务周期性发布到 `heartbeat.<service_id>`，负载包含时间戳与元信息。
- 监听：监控端消费 `heartbeat.*`，维护最近心跳时间并判断是否在线（默认阈值 15 秒，可配置）。
- RPC ping：主动向队列 `kc.presence.ping.<target_id>` 发送请求，目标服务收到后通过 `reply_to` 指定的临时队列快速回发 Pong。

线程与连接管理：
- 内部为心跳、监听、Ping 响应分别维护独立的 `BlockingConnection/Channel` 与线程，避免跨线程共享导致不稳定。

常用 API：
- `start_heartbeat(service_id: str, meta: dict | None)`：启动心跳线程。
- `stop_heartbeat()`：停止心跳线程并释放连接资源。
- `start_watch(watcher_id: str | None)`：启动监听线程，维护在线状态映射。
- `stop_watch()`：停止监听线程并释放连接资源。
- `is_online(service_id: str, threshold_sec: int | None = None) -> bool`：判断指定服务是否在线（默认阈值 `online_threshold_sec`）。
- `get_online_services(threshold_sec: int | None = None) -> Dict[str, float]`：返回在线服务及其最后心跳时间戳。
- `start_ping_responder(service_id: str)`：启动 Ping 响应线程，监听队列 `kc.presence.ping.<service_id>`。
- `stop_ping_responder()`：停止 Ping 响应线程并释放连接资源。
- `ping(target_service_id: str, timeout_sec: float = 3.0) -> bool`：主动向目标发送 ping 请求并等待 pong 回复。

构造参数：
- `PresenceManager(base_client: RabbitMQClient | None, heartbeat_interval_sec: int = 5, online_threshold_sec: int = 15)`
  - `heartbeat_interval_sec`：心跳发送周期（秒）。
  - `online_threshold_sec`：在线判断阈值（秒）。

---

## 快速上手示例

### 服务 A：心跳 + Ping 响应

```python
from KairoCore import PresenceManager

pm_a = PresenceManager()
pm_a.start_heartbeat(service_id="service-A", meta={"version": "1.0.0"})
pm_a.start_ping_responder(service_id="service-A")

# 结束时优雅关闭
# pm_a.stop_heartbeat()
# pm_a.stop_ping_responder()
```

### 监控服务：监听在线状态

```python
from KairoCore import PresenceManager
import time

pm_watch = PresenceManager()
pm_watch.start_watch()

time.sleep(5)  # 等待积累心跳
print("在线服务:", pm_watch.get_online_services())
print("service-A 是否在线:", pm_watch.is_online("service-A"))

# 结束时优雅关闭
# pm_watch.stop_watch()
```

### 服务 B：主动 ping 服务 A

```python
from KairoCore import PresenceManager

pm_b = PresenceManager()
pm_b.start_ping_responder(service_id="service-B")  # 让 B 也能被 ping 到
ok = pm_b.ping(target_service_id="service-A", timeout_sec=2.0)
print("ping service-A:", ok)

# 结束时优雅关闭
# pm_b.stop_ping_responder()
```

### 在 FastAPI 中集成（可选）

```python
from fastapi import FastAPI
from KairoCore import PresenceManager

app = FastAPI()
pm = PresenceManager()

@app.on_event("startup")
def on_startup():
    pm.start_heartbeat(service_id="service-A", meta={"version": "1.0.0"})
    pm.start_ping_responder(service_id="service-A")
    # 如果本服务还要监控其他服务
    # pm.start_watch()

@app.on_event("shutdown")
def on_shutdown():
    pm.stop_heartbeat()
    pm.stop_ping_responder()
    pm.stop_watch()
```

---

## 进阶与最佳实践

1) 消息过期与持久化
- 心跳消息默认使用非持久化投递，示例中设置了短 TTL（15 秒），仅用于在线判断与实时监控，不做持久化存储。
- 如需持久化事件，请在业务消息中使用 `persistent=True` 并将交换机/队列设置为持久化，配合存储系统（如 MySQL/Redis/ZK）进行状态记录与回溯。

2) 线程与连接
- PresenceManager 内部为不同功能维护独立的连接与通道；不要在多个线程间共享同一连接或通道。
- 当网络抖动或服务重启导致连接异常时，会自动重试并重建连接。

3) 错误处理
- 统一通过 `KCRM_*` 常量抛出异常，包含连接、通道、声明、发布与消费等类型，便于上层统一捕获与日志记录。

4) 安全与权限
- 生产环境请为 RabbitMQ 设置独立的虚拟主机与限权账号，避免使用 `guest/guest`。
- 根据需要配置交换机与队列的策略（如 TTL、DLX、限流策略等）。

5) 参数调优
- `heartbeat_interval_sec` 与 `online_threshold_sec` 可按场景调优：心跳更频繁可带来更及时的在线判断，但会增加消息量；阈值过小可能误判短暂抖动为离线，过大则降低敏感度。

---

## 常见问题（FAQ）

1) 连接失败或超时
- 检查 RabbitMQ 服务是否启动、端口是否开放、防火墙与容器网络是否可达。
- 确认 `RABBITMQ_HOST/PORT/USER/PASSWORD/VHOST` 是否正确，是否有访问权限。
- 调整 `RABBITMQ_HEARTBEAT` 与客户端的 `blocked_connection_timeout/connection_attempts/retry_delay`（在 `RabbitMQClient` 构造参数中可配置）。

2) 无法消费心跳消息
- 确保交换机 `kc.presence` 为 `topic` 类型，且监听端队列已绑定 `heartbeat.*` 路由键。
- 检查监听线程是否启动、进程是否存活，日志中是否有异常提示。

3) Ping 请求无响应
- 确认目标服务已调用 `start_ping_responder(service_id)` 并处于运行状态。
- 检查请求方是否正确设置了 `reply_to`（内部自动配置为临时队列）以及网络连通性。

---

## 参考

- `utils/kc_rabbitmq.py`
- `README.md` 中的相关章节：RabbitMQ 在线状态与心跳使用说明
- `common/errors.py` 中的 `KCRM_*` 异常常量