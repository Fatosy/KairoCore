import os
from typing import Optional, Union
import redis
import redis.asyncio as aioredis
from ..utils.log import get_logger 
from ..common.errors import (
    KCR_CONNECT_ERROR,
    KCR_USE_ERROR
)

logger = get_logger()


class RedisClient:
    """
    同步 Redis 客户端封装，使用连接池管理连接。
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        max_connections: int = 20 # 连接池最大连接数
    ):
        """
        初始化 RedisClient 实例。

        Args:
            host (str, optional): Redis 服务器主机名。默认从环境变量 'REDIS_HOST' 获取，否则为 'localhost'。
            port (int, optional): Redis 服务器端口。默认从环境变量 'REDIS_PORT' 获取，否则为 6379。
            db (int, optional): Redis 数据库编号。默认从环境变量 'REDIS_DB' 获取，否则为 0。
            password (str, optional): Redis 服务器密码。默认从环境变量 'REDIS_PASSWORD' 获取。
            max_connections (int): 连接池的最大连接数。默认为 20。
        """
        self.host = host or os.getenv('REDIS_HOST')
        self.port = port or int(os.getenv('REDIS_PORT'))
        if self.host is None or self.port is None:
            raise KCR_CONNECT_ERROR.msg_format("请检查环境变量 'REDIS_HOST' 和 'REDIS_PORT' 是否设置正确。")
        self.db = db or int(os.getenv('REDIS_DB', 0))
        self.password = password or os.getenv('REDIS_PASSWORD')
        self.max_connections = max_connections
        
        # 创建连接池
        self.pool: Optional[redis.ConnectionPool] = None
        # 创建客户端实例 (使用连接池)
        self.client: Optional[redis.Redis] = None
        self._init_pool_and_client()

    def _init_pool_and_client(self):
        """初始化连接池和客户端实例。"""
        try:
            # 创建连接池
            self.pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=False, # 保持字节流，由调用者决定是否解码
                retry_on_timeout=True,
                health_check_interval=30 # 定期检查连接健康
            )
            # 创建客户端，使用连接池
            self.client = redis.Redis(connection_pool=self.pool)
            logger.debug(f"RedisClient 初始化成功 (Host: {self.host}, Port: {self.port}, DB: {self.db})")
        except Exception as e:
            raise KCR_CONNECT_ERROR.msg_format(f"RedisClient 连接失败: {e}")

    def get_client(self) -> redis.Redis:
        """
        获取 Redis 客户端实例。

        Returns:
            redis.Redis: Redis 客户端实例。
        
        Raises:
            RuntimeError: 如果客户端未正确初始化。
        """
        if self.client is None:
            raise KCR_CONNECT_ERROR.msg_format("Redis 客户端未初始化或初始化失败。")
        return self.client

    def close(self):
        """关闭连接池，释放所有连接。"""
        if self.pool:
            try:
                self.pool.disconnect()
                logger.debug("Redis 连接池已关闭。")
            except Exception as e:
                raise KCR_CONNECT_ERROR.msg_format(f"关闭 Redis 连接池时出错: {e}")
            finally:
                self.pool = None
                self.client = None

    # --- Redis 操作方法 ---
    # 注意：这些方法现在直接使用 self.client，不再通过装饰器注入连接

    def set_key(self, key: str, value: Union[str, bytes], ex: Optional[int] = None) -> bool:
        """
        设置一个键值对。

        Args:
            key (str): 键名。
            value (Union[str, bytes]): 值。
            ex (int, optional): 过期时间（秒）。默认不过期。

        Returns:
            bool: 成功返回 True，失败返回 False。
        """
        try:
            # redis-py 的 set 方法返回 bool
            return self.get_client().set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"设置键 '{key}' 时出错: {e}")
            return False

    def get_key(self, key: str) -> Optional[bytes]:
        """
        获取指定键的值。

        Args:
            key (str): 键名。

        Returns:
            Optional[bytes]: 如果键存在则返回其对应的值（bytes），否则返回 None。
        """
        try:
            # redis-py 的 get 方法返回 bytes 或 None
            return self.get_client().get(key)
        except Exception as e:
            logger.error(f"获取键 '{key}' 时出错: {e}")
            return None

    def delete_key(self, key: str) -> int:
        """
        删除指定键。

        Args:
            key (str): 键名。

        Returns:
            int: 被删除的键的数量 (0 或 1)。
        """
        try:
            # redis-py 的 delete 方法返回被删除的键的数量
            return self.get_client().delete(key)
        except Exception as e:
            raise KCR_USE_ERROR.msg_format(f"删除键 '{key}' 时出错: {e}")


    def exists(self, key: str) -> bool:
        """
        检查键是否存在。

        Args:
            key (str): 键名。

        Returns:
            bool: 存在返回 True，不存在返回 False。
        """
        try:
            # redis-py 的 exists 方法返回存在的键的数量
            return self.get_client().exists(key) == 1
        except Exception as e:
            logger.error(f"检查键 '{key}' 是否存在时出错: {e}")
            return False # 假设出错则认为不存在

    # --- 上下文管理器支持 ---
    def __enter__(self):
        """进入上下文管理器。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器，自动关闭连接池。"""
        self.close()



class AsyncRedisClient:
    """
    异步 Redis 客户端封装，基于 redis-py 的异步支持。
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        max_connections: int = 10 # 异步连接池最大连接数
    ):
        """
        初始化 AsyncRedisClient 实例。

        Args:
            host (str, optional): Redis 服务器主机名。默认从环境变量 'REDIS_HOST' 获取，否则为 'localhost'。
            port (int, optional): Redis 服务器端口。默认从环境变量 'REDIS_PORT' 获取，否则为 6379。
            db (int, optional): Redis 数据库编号。默认从环境变量 'REDIS_DB' 获取，否则为 0。
            password (str, optional): Redis 服务器密码。默认从环境变量 'REDIS_PASSWORD' 获取。
            max_connections (int): 连接池的最大连接数。默认为 10。
        """
        self.host = host or os.getenv('REDIS_HOST')
        self.port = port or int(os.getenv('REDIS_PORT'))
        if self.host is None or self.port is None:
            raise KCR_CONNECT_ERROR.msg_format("Redis 连接信息不完整。请检查环境变量 'REDIS_HOST' 和 'REDIS_PORT' 是否已设置。")
        self.db = db or int(os.getenv('REDIS_DB', 0))
        self.password = password or os.getenv('REDIS_PASSWORD')
        self.max_connections = max_connections

        # 创建异步连接池
        self.pool: Optional[aioredis.ConnectionPool] = None
        # 创建异步客户端实例 (使用连接池)
        self.client: Optional[aioredis.Redis] = None
        # 注意：连接池和客户端的初始化放在 async 方法中或首次使用时

    async def _init_pool_and_client(self):
        """异步初始化连接池和客户端实例。"""
        if self.pool is None:
            try:
                # 创建异步连接池
                self.pool = aioredis.ConnectionPool(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    max_connections=self.max_connections,
                    decode_responses=False,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                # 创建异步客户端，使用连接池
                self.client = aioredis.Redis(connection_pool=self.pool)
                logger.info(f"AsyncRedisClient 初始化成功 (Host: {self.host}, Port: {self.port}, DB: {self.db})")
            except Exception as e:
                raise KCR_CONNECT_ERROR.msg_format(f"AsyncRedisClient 初始化失败: {e}")

    async def get_client(self) -> aioredis.Redis:
        """
        异步获取 Redis 客户端实例。

        Returns:
            aioredis.Redis: Redis 客户端实例。
        
        Raises:
            RuntimeError: 如果客户端未正确初始化。
        """
        if self.client is None:
            await self._init_pool_and_client() # 按需初始化
        if self.client is None:
            raise KCR_CONNECT_ERROR.msg_format("Redis 异步客户端未初始化或初始化失败。")
        return self.client

    async def close(self):
        """异步关闭连接池，释放所有连接。"""
        if self.pool:
            try:
                await self.pool.disconnect()
                logger.info("Redis 异步连接池已关闭。")
            except Exception as e:
                logger.error(f"关闭 Redis 异步连接池时出错: {e}")
            finally:
                self.pool = None
                self.client = None

    # --- 异步 Redis 操作方法 ---
    async def set_key(self, key: str, value: Union[str, bytes], ex: Optional[int] = None) -> bool:
        """
        异步设置一个键值对。

        Args:
            key (str): 键名。
            value (Union[str, bytes]): 值。
            ex (int, optional): 过期时间（秒）。默认不过期。

        Returns:
            bool: 成功返回 True，失败返回 False。
        """
        try:
            client = await self.get_client()
            # aioredis 的 set 方法返回 bool
            return await client.set(key, value, ex=ex)
        except Exception as e:
            logger.error(f"异步设置键 '{key}' 时出错: {e}")
            return False

    async def get_key(self, key: str) -> Optional[bytes]:
        """
        异步获取指定键的值。

        Args:
            key (str): 键名。

        Returns:
            Optional[bytes]: 如果键存在则返回其对应的值（bytes），否则返回 None。
        """
        try:
            client = await self.get_client()
            # aioredis 的 get 方法返回 bytes 或 None
            return await client.get(key)
        except Exception as e:
            logger.error(f"异步获取键 '{key}' 时出错: {e}")
            return None

    async def delete_key(self, key: str) -> int:
        """
        异步删除指定键。

        Args:
            key (str): 键名。

        Returns:
            int: 被删除的键的数量 (0 或 1)。
        """
        try:
            client = await self.get_client()
            # aioredis 的 delete 方法返回被删除的键的数量
            return await client.delete(key)
        except Exception as e:
            raise KCR_USE_ERROR.msg_format(f"异步删除键 '{key}' 时出错: {e}")

    async def exists(self, key: str) -> bool:
        """
        异步检查键是否存在。

        Args:
            key (str): 键名。

        Returns:
            bool: 存在返回 True，不存在返回 False。
        """
        try:
            client = await self.get_client()
            # aioredis 的 exists 方法返回存在的键的数量
            return await client.exists(key) == 1
        except Exception as e:
            logger.error(f"异步检查键 '{key}' 是否存在时出错: {e}")
            return False

    # --- 异步上下文管理器支持 ---
    async def __aenter__(self):
        """进入异步上下文管理器。"""
        # 可以在这里触发初始化
        await self._init_pool_and_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理器，自动关闭连接池。"""
        await self.close()


# --- 使用示例 ---
# import asyncio

# 同步使用示例
# def sync_example():
#     try:
#         # 方式一：直接实例化和使用
#         client = RedisClient(host="localhost", port=6379)
#         success = client.set_key("sync_key", "sync_value", ex=10)
#         print(f"同步设置键: {success}")
#         value = client.get_key("sync_key")
#         print(f"同步获取键值: {value.decode('utf-8') if value else None}")
#         client.close() # 手动关闭
#
#         print("---")
#
#         # 方式二：使用上下文管理器 (推荐)
#         with RedisClient() as client_ctx: # 会自动从环境变量读取配置
#             success = client_ctx.set_key("sync_key_ctx", "sync_value_ctx")
#             print(f"同步上下文设置键: {success}")
#             value = client_ctx.get_key("sync_key_ctx")
#             print(f"同步上下文获取键值: {value.decode('utf-8') if value else None}")
#             # 退出 with 块时会自动调用 client_ctx.close()
#
#     except Exception as e:
#         print(f"同步示例出错: {e}")

# 异步使用示例
# async def async_example():
#     try:
#         # 方式一：直接实例化和使用
#         aclient = AsyncRedisClient(host="localhost", port=6379)
#         success = await aclient.set_key("async_key", "async_value", ex=10)
#         print(f"异步设置键: {success}")
#         value = await aclient.get_key("async_key")
#         print(f"异步获取键值: {value.decode('utf-8') if value else None}")
#         await aclient.close() # 手动关闭
#
#         print("---")
#
#         # 方式二：使用异步上下文管理器 (推荐)
#         async with AsyncRedisClient() as aclient_ctx: # 会自动从环境变量读取配置
#             success = await aclient_ctx.set_key("async_key_ctx", "async_value_ctx")
#             print(f"异步上下文设置键: {success}")
#             value = await aclient_ctx.get_key("async_key_ctx")
#             print(f"异步上下文获取键值: {value.decode('utf-8') if value else None}")
#             # 退出 async with 块时会自动调用 await aclient_ctx.close()
#
#     except Exception as e:
#         print(f"异步示例出错: {e}")

# if __name__ == "__main__":
#     # 运行同步示例
#     sync_example()
#
#     # 运行异步示例
#     # asyncio.run(async_example())



