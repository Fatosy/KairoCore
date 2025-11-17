import os
import json
import time
import uuid
import threading
from typing import Optional, Callable, Dict, Any, Tuple

import pika

from ..utils.log import get_logger
from ..common.errors import (
    KCRM_CONNECT_ERROR,
    KCRM_CHANNEL_ERROR,
    KCRM_DECLARE_ERROR,
    KCRM_PUBLISH_ERROR,
    KCRM_CONSUME_ERROR,
)


logger = get_logger()


class RabbitMQClient:
    """
    轻量级 RabbitMQ 客户端封装，基于 pika.BlockingConnection。

    特性：
    - 统一的连接参数管理（支持环境变量）
    - 声明交换机 / 队列 / 绑定
    - 发布消息（支持 JSON 自动编码）
    - 消费消息（带 prefetch）

    注意：BlockingConnection/Channel 不是线程安全的，不要跨线程共享。
    在多线程场景（例如心跳发送/监听）请为每个线程创建独立的连接。
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        vhost: Optional[str] = None,
        heartbeat: Optional[int] = None,
        blocked_connection_timeout: int = 30,
        connection_attempts: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        self.host = host or os.getenv("RABBITMQ_HOST", "127.0.0.1")
        self.port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = username or os.getenv("RABBITMQ_USER", "guest")
        self.password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
        self.vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
        self.heartbeat = heartbeat or int(os.getenv("RABBITMQ_HEARTBEAT", "30"))
        self.blocked_connection_timeout = blocked_connection_timeout
        self.connection_attempts = connection_attempts
        self.retry_delay = retry_delay

        self._params = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=pika.PlainCredentials(self.username, self.password),
            heartbeat=self.heartbeat,
            blocked_connection_timeout=self.blocked_connection_timeout,
            connection_attempts=self.connection_attempts,
            retry_delay=self.retry_delay,
        )

    def open_connection(self) -> pika.BlockingConnection:
        """创建并返回新的连接实例。"""
        try:
            conn = pika.BlockingConnection(self._params)
            return conn
        except Exception as e:
            raise KCRM_CONNECT_ERROR.msg_format(f"连接 RabbitMQ 失败: {e}")

    @staticmethod
    def open_channel(conn: pika.BlockingConnection) -> pika.adapters.blocking_connection.BlockingChannel:
        """基于连接创建 Channel，并启用 confirm 模式。"""
        try:
            ch = conn.channel()
            # 开启发布确认，提高可靠性
            try:
                ch.confirm_delivery()
            except Exception:
                # 某些版本/场景可能不支持，忽略
                pass
            return ch
        except Exception as e:
            raise KCRM_CHANNEL_ERROR.msg_format(f"创建通道失败: {e}")

    @staticmethod
    def declare_exchange(
        ch: pika.adapters.blocking_connection.BlockingChannel,
        name: str,
        ex_type: str = "topic",
        durable: bool = True,
        auto_delete: bool = False,
    ) -> None:
        try:
            ch.exchange_declare(exchange=name, exchange_type=ex_type, durable=durable, auto_delete=auto_delete)
        except Exception as e:
            raise KCRM_DECLARE_ERROR.msg_format(f"声明交换机 '{name}' 失败: {e}")

    @staticmethod
    def declare_queue(
        ch: pika.adapters.blocking_connection.BlockingChannel,
        name: str,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int, int]:
        try:
            method = ch.queue_declare(queue=name, durable=durable, exclusive=exclusive, auto_delete=auto_delete, arguments=arguments)
            return method.method.queue, method.method.message_count, method.method.consumer_count
        except Exception as e:
            raise KCRM_DECLARE_ERROR.msg_format(f"声明队列 '{name}' 失败: {e}")

    @staticmethod
    def bind_queue(
        ch: pika.adapters.blocking_connection.BlockingChannel,
        queue: str,
        exchange: str,
        routing_key: str,
    ) -> None:
        try:
            ch.queue_bind(queue=queue, exchange=exchange, routing_key=routing_key)
        except Exception as e:
            raise KCRM_DECLARE_ERROR.msg_format(f"绑定队列 '{queue}' 到交换机 '{exchange}' 失败: {e}")

    @staticmethod
    def set_prefetch(ch: pika.adapters.blocking_connection.BlockingChannel, prefetch_count: int = 10) -> None:
        try:
            ch.basic_qos(prefetch_count=prefetch_count)
        except Exception as e:
            raise KCRM_CHANNEL_ERROR.msg_format(f"设置预取失败: {e}")

    @staticmethod
    def publish(
        ch: pika.adapters.blocking_connection.BlockingChannel,
        exchange: str,
        routing_key: str,
        body: Any,
        content_type: str = "application/json",
        persistent: bool = True,
        expiration_ms: Optional[int] = None,
        headers: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        发布消息。
        - body 为非 bytes 时自动 JSON 序列化
        - persistent=True 使用投递模式 2（持久化）
        - expiration_ms 设置消息过期时间（字符串，单位毫秒）
        """
        try:
            payload: bytes
            if isinstance(body, (bytes, bytearray)):
                payload = body
            else:
                payload = json.dumps(body, ensure_ascii=False).encode("utf-8")

            props = pika.BasicProperties(
                content_type=content_type,
                delivery_mode=2 if persistent else 1,
                headers=headers or {},
                expiration=str(expiration_ms) if expiration_ms else None,
                reply_to=reply_to,
                correlation_id=correlation_id,
            )
            ch.basic_publish(exchange=exchange, routing_key=routing_key, body=payload, properties=props)
        except Exception as e:
            raise KCRM_PUBLISH_ERROR.msg_format(f"发布消息失败 exchange='{exchange}' routing='{routing_key}': {e}")


class PresenceManager:
    """
    多服务在线状态检测工具。

    设计：
    - 使用 topic 交换机 'kc.presence'。
    - 心跳：每个服务周期性发布到 routing_key 'heartbeat.<service_id>'，负载包含时间戳和元信息。
    - 监听：监控端消费 'heartbeat.*'，维护最近心跳时间并判断是否在线（阈值）。
    - Ping：RPC 风格 ping，向队列 'kc.presence.ping.<target_id>' 发送请求，目标服务收到后立即回复到请求者的临时队列。

    注意：内部使用独立连接线程（BlockingConnection 不可跨线程共享）。
    """

    def __init__(
        self,
        base_client: Optional[RabbitMQClient] = None,
        heartbeat_interval_sec: int = 5,
        online_threshold_sec: int = 15,
        exchange: str = "kc.presence"
    ) -> None:
        self.client = base_client or RabbitMQClient()
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.online_threshold_sec = online_threshold_sec
        self.EXCHANGE = exchange

        # --- 心跳线程相关 ---
        self._hb_conn: Optional[pika.BlockingConnection] = None
        self._hb_ch: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._hb_thread: Optional[threading.Thread] = None
        self._hb_stop = threading.Event()
        self._service_id: Optional[str] = None
        self._service_meta: Dict[str, Any] = {}

        # --- 监听线程相关 ---
        self._watch_conn: Optional[pika.BlockingConnection] = None
        self._watch_ch: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._watch_stop = threading.Event()
        self._last_seen: Dict[str, float] = {}

        # --- ping 响应线程 ---
        self._ping_conn: Optional[pika.BlockingConnection] = None
        self._ping_ch: Optional[pika.adapters.blocking_connection.BlockingChannel] = None
        self._ping_thread: Optional[threading.Thread] = None
        self._ping_stop = threading.Event()
        self._ping_service_id: Optional[str] = None

    # ---------- 心跳 ----------
    def start_heartbeat(self, service_id: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """启动心跳发送线程。"""
        if self._hb_thread and self._hb_thread.is_alive():
            logger.warning("心跳线程已运行，无需重复启动。")
            return

        self._service_id = service_id
        self._service_meta = meta or {}
        self._hb_stop.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, name=f"presence-hb-{service_id}", daemon=True)
        self._hb_thread.start()
        logger.info(f"Presence 心跳线程已启动 service_id={service_id}")

    def stop_heartbeat(self) -> None:
        self._hb_stop.set()
        if self._hb_thread and self._hb_thread.is_alive():
            self._hb_thread.join(timeout=5)
        self._safe_close(self._hb_ch, self._hb_conn)
        self._hb_ch = None
        self._hb_conn = None
        logger.info("Presence 心跳线程已停止")

    def _heartbeat_loop(self) -> None:
        assert self._service_id is not None
        while not self._hb_stop.is_set():
            try:
                if not self._hb_conn or self._hb_conn.is_closed:
                    self._hb_conn = self.client.open_connection()
                    self._hb_ch = RabbitMQClient.open_channel(self._hb_conn)
                    # 声明交换机
                    RabbitMQClient.declare_exchange(self._hb_ch, self.EXCHANGE, ex_type="topic", durable=True)

                payload = {
                    "service_id": self._service_id,
                    "ts": int(time.time()),
                    "meta": self._service_meta,
                }
                routing_key = f"heartbeat.{self._service_id}"
                # 心跳消息可设置短过期（可选）
                RabbitMQClient.publish(
                    self._hb_ch, self.EXCHANGE, routing_key, payload, persistent=False, expiration_ms=15000
                )
                logger.debug(f"心跳已发送 {routing_key}: {payload}")
            except Exception as e:
                logger.error(f"心跳发送失败，将在 {self.client.retry_delay}s 后重试: {e}")
                self._safe_close(self._hb_ch, self._hb_conn)
                self._hb_ch = None
                self._hb_conn = None
                time.sleep(self.client.retry_delay)
            finally:
                # 控制发送间隔
                stop_wait = self._hb_stop.wait(self.heartbeat_interval_sec)
                if stop_wait:
                    break

    # ---------- 监听 ----------
    def start_watch(self, watcher_id: Optional[str] = None) -> None:
        """启动监听心跳的线程，维护在线状态。"""
        if self._watch_thread and self._watch_thread.is_alive():
            logger.warning("监听线程已运行，无需重复启动。")
            return

        self._watch_stop.clear()
        self._watch_thread = threading.Thread(target=self._watch_loop, name=f"presence-watch-{watcher_id or 'default'}", daemon=True)
        self._watch_thread.start()
        logger.info("Presence 监听线程已启动")

    def stop_watch(self) -> None:
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=5)
        self._safe_close(self._watch_ch, self._watch_conn)
        self._watch_ch = None
        self._watch_conn = None
        logger.info("Presence 监听线程已停止")

    def _watch_loop(self) -> None:
        queue_name = f"kc.presence.watch.{uuid.uuid4().hex}"
        while not self._watch_stop.is_set():
            try:
                # 建立连接和通道
                self._watch_conn = self.client.open_connection()
                self._watch_ch = RabbitMQClient.open_channel(self._watch_conn)

                # 声明交换机和临时队列
                RabbitMQClient.declare_exchange(self._watch_ch, self.EXCHANGE, ex_type="topic", durable=True)
                RabbitMQClient.declare_queue(
                    self._watch_ch,
                    name=queue_name,
                    durable=False,
                    exclusive=True,
                    auto_delete=True,
                )
                RabbitMQClient.bind_queue(self._watch_ch, queue_name, self.EXCHANGE, "heartbeat.*")
                RabbitMQClient.set_prefetch(self._watch_ch, prefetch_count=100)

                def on_message(ch: pika.adapters.blocking_connection.BlockingChannel, method, properties, body):
                    try:
                        data = json.loads(body.decode("utf-8"))
                        sid = data.get("service_id")
                        ts = data.get("ts") or int(time.time())
                        self._last_seen[sid] = float(ts)
                    except Exception as ex:
                        logger.error(f"处理心跳消息失败: {ex}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                self._watch_ch.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=False)
                # 阻塞消费，直到 stop 信号或连接异常
                while not self._watch_stop.is_set():
                    self._watch_conn.process_data_events(time_limit=1)
                # 收到 stop 后，尝试停止消费
                try:
                    self._watch_ch.stop_consuming()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"监听心跳失败，将在 {self.client.retry_delay}s 后重试: {e}")
                time.sleep(self.client.retry_delay)
            finally:
                self._safe_close(self._watch_ch, self._watch_conn)
                self._watch_ch = None
                self._watch_conn = None

    def is_online(self, service_id: str, threshold_sec: Optional[int] = None) -> bool:
        """判断指定服务是否在线。"""
        th = threshold_sec or self.online_threshold_sec
        last = self._last_seen.get(service_id)
        if not last:
            return False
        return (time.time() - last) <= th

    def get_online_services(self, threshold_sec: Optional[int] = None) -> Dict[str, float]:
        """返回在线服务及其最后心跳时间戳。"""
        th = threshold_sec or self.online_threshold_sec
        now = time.time()
        return {sid: ts for sid, ts in self._last_seen.items() if now - ts <= th}

    # ---------- Ping 响应 ----------
    def start_ping_responder(self, service_id: str) -> None:
        """
        启动 Ping 响应线程。
        - 监听队列 'kc.presence.ping.<service_id>'
        - 收到后立即回复到 properties.reply_to（默认交换机，routing_key=reply_to）
        """
        if self._ping_thread and self._ping_thread.is_alive():
            logger.warning("Ping 响应线程已运行，无需重复启动。")
            return

        self._ping_service_id = service_id
        self._ping_stop.clear()
        self._ping_thread = threading.Thread(target=self._ping_loop, name=f"presence-ping-{service_id}", daemon=True)
        self._ping_thread.start()
        logger.info(f"Presence Ping 响应线程已启动 service_id={service_id}")

    def stop_ping_responder(self) -> None:
        self._ping_stop.set()
        if self._ping_thread and self._ping_thread.is_alive():
            self._ping_thread.join(timeout=5)
        self._safe_close(self._ping_ch, self._ping_conn)
        self._ping_ch = None
        self._ping_conn = None
        logger.info("Presence Ping 响应线程已停止")

    def _ping_loop(self) -> None:
        assert self._ping_service_id is not None
        queue_name = f"kc.presence.ping.{self._ping_service_id}"
        while not self._ping_stop.is_set():
            try:
                self._ping_conn = self.client.open_connection()
                self._ping_ch = RabbitMQClient.open_channel(self._ping_conn)
                # 声明队列（默认交换机投递）
                RabbitMQClient.declare_queue(self._ping_ch, name=queue_name, durable=False, exclusive=False, auto_delete=True)
                RabbitMQClient.set_prefetch(self._ping_ch, prefetch_count=50)

                def on_ping(ch, method, properties, body):
                    try:
                        # 回应 Pong（直接发到 reply_to 指定的队列）
                        reply_to = properties.reply_to
                        corr_id = properties.correlation_id
                        payload = {
                            "service_id": self._ping_service_id,
                            "ts": int(time.time()),
                            "ok": True,
                        }
                        ch.basic_publish(
                            exchange="",
                            routing_key=reply_to,
                            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            properties=pika.BasicProperties(content_type="application/json", correlation_id=corr_id),
                        )
                    except Exception as ex:
                        logger.error(f"Pong 回复失败: {ex}")
                    finally:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                self._ping_ch.basic_consume(queue=queue_name, on_message_callback=on_ping, auto_ack=False)
                while not self._ping_stop.is_set():
                    self._ping_conn.process_data_events(time_limit=1)
                try:
                    self._ping_ch.stop_consuming()
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Ping 响应失败，将在 {self.client.retry_delay}s 后重试: {e}")
                time.sleep(self.client.retry_delay)
            finally:
                self._safe_close(self._ping_ch, self._ping_conn)
                self._ping_ch = None
                self._ping_conn = None

    # ---------- 主动 Ping ----------
    def ping(self, target_service_id: str, timeout_sec: float = 3.0) -> bool:
        """
        主动向目标服务发送 ping 请求，并等待其响应。
        实现：
        - 临时声明一个独占自动删除的回复队列 'kc.presence.rpc.reply.<uuid>'
        - 向默认交换机发布到队列 'kc.presence.ping.<target>'，设置 reply_to=临时队列
        - 轮询临时队列 basic_get，等待 pong
        """
        reply_queue = f"kc.presence.rpc.reply.{uuid.uuid4().hex}"
        conn = None
        ch = None
        try:
            conn = self.client.open_connection()
            ch = RabbitMQClient.open_channel(conn)
            # 声明临时回复队列
            RabbitMQClient.declare_queue(ch, name=reply_queue, durable=False, exclusive=True, auto_delete=True)

            corr_id = uuid.uuid4().hex
            # 发布 Ping 到目标的 ping 队列（默认交换机）
            ch.basic_publish(
                exchange="",
                routing_key=f"kc.presence.ping.{target_service_id}",
                body=json.dumps({"ts": int(time.time())}).encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    reply_to=reply_queue,
                    correlation_id=corr_id,
                    delivery_mode=1,
                ),
            )

            # 轮询等待回复
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                method_frame, properties, body = ch.basic_get(queue=reply_queue, auto_ack=True)
                if method_frame:
                    try:
                        data = json.loads(body.decode("utf-8"))
                        ok = bool(data.get("ok"))
                        return ok
                    except Exception:
                        return False
                time.sleep(0.05)
            return False
        except Exception as e:
            raise KCRM_CONSUME_ERROR.msg_format(f"Ping 过程失败: {e}")
        finally:
            # 最终关闭临时资源
            self._safe_close(ch, conn)

    # ---------- 工具 ----------
    @staticmethod
    def _safe_close(ch: Optional[pika.adapters.blocking_connection.BlockingChannel], conn: Optional[pika.BlockingConnection]) -> None:
        try:
            if ch and ch.is_open:
                try:
                    ch.close()
                except Exception:
                    pass
            if conn and conn.is_open:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            pass


# 使用示例（参考）：
#
# from KairoCore.utils.kc_rabbitmq import RabbitMQClient, PresenceManager
#
# # 心跳发送方（服务 A）
# pm_a = PresenceManager()
# pm_a.start_heartbeat(service_id="service-A", meta={"version": "1.0.0"})
# pm_a.start_ping_responder(service_id="service-A")
#
# # 监控方（例如一个管理服务）
# pm_watch = PresenceManager()
# pm_watch.start_watch()
# time.sleep(10)
# print(pm_watch.get_online_services())
# print(pm_watch.is_online("service-A"))
#
# # 其他服务主动检测（服务 B）
# pm_b = PresenceManager()
# pm_b.start_ping_responder(service_id="service-B")
# # 试探 service-A 是否在线（RPC）
# is_ok = pm_b.ping(target_service_id="service-A", timeout_sec=2)
# print("service-A ping:", is_ok)