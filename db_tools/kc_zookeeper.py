import os
import aiozk
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Generator, Any, AsyncGenerator, Union
from kazoo.client import KazooClient
from kazoo.recipe.lock import Lock
from kazoo import security as kazoo_acl
from kazoo.exceptions import NodeExistsError, NoNodeError, ZookeeperError, BadVersionError
from ..utils.log import get_logger
from ..common.errors import (
    KCZ_CONNECT_ERROR,
    KCZ_USE_ERROR
)

logger = get_logger()


class ZkClient:
    """
    同步 Zookeeper 客户端封装，基于 kazoo 库。
    """

    def __init__(self, hosts: Optional[str] = None):
        """
        初始化 ZkClient 实例。

        Args:
            hosts (str, optional): Zookeeper 服务器地址列表，格式为 'host1:port1,host2:port2'。
                                   如果未提供，则从环境变量 'ZOOKEEPER_HOSTS' 读取，
                                   默认为 '127.0.0.1:2181'。
        """
        self.zk_hosts = hosts or os.getenv('ZOOKEEPER_HOSTS')
        if self.zk_hosts is None:
            raise KCZ_CONNECT_ERROR.msg_format("未提供 Zookeeper 主机列表。请设置环境变量 'ZOOKEEPER_HOSTS' 或提供参数 'hosts'。")
        # 注意：KazooClient 的初始化通常是轻量级的，实际连接在 start() 时建立
        self.zk: Optional[KazooClient] = KazooClient(hosts=self.zk_hosts)
        logger.info(f"ZkClient 已初始化，主机列表: {self.zk_hosts}")

    def connect(self) -> None:
        """
        连接到 Zookeeper 集群。
        如果已经连接，则不执行任何操作。
        """
        if self.zk and not self.zk.connected:
            try:
                # start() 方法会阻塞直到连接建立或超时
                self.zk.start()
                logger.info("已连接到 Zookeeper。")
            except Exception as e:
                logger.error(f"连接 Zookeeper 失败: {e}")
                # 将底层异常包装成更明确的应用级异常
                raise KCZ_CONNECT_ERROR.msg_format(f"无法连接到 Zookeeper {str(e)}")

    def disconnect(self) -> None:
        """
        断开与 Zookeeper 集群的连接。
        如果未连接或已关闭，则不执行任何操作。
        """
        if self.zk and self.zk.connected:
            try:
                # stop() 停止事件循环，close() 关闭连接
                self.zk.stop()
                self.zk.close()
                logger.info("已断开与 Zookeeper 的连接。")
            except Exception as e:
                # 重新抛出以便调用者知晓断开连接时的问题
                raise KCZ_CONNECT_ERROR.msg_format(f"无法断开与 Zookeeper 的连接 {str(e)}")

    @contextmanager
    def session(self) -> Generator['ZkClient', None, None]:
        """
        上下文管理器，用于管理 Zookeeper 会话的生命周期。
        自动处理连接和断开连接。

        Yields:
            ZkClient: 当前的客户端实例，可在 with 代码块内使用。

        Example:
            with client.session() as zk_client:
                data, stat = zk_client.zk.get("/my/path")
                # ... perform other zk operations ...
        """
        self.connect()
        try:
            yield self # 将已连接的实例传递出去
        finally:
            self.disconnect() # 确保退出时断开连接

    @contextmanager
    def acquire_lock(self, path: str, identifier: Optional[str] = None) -> Generator[None, None, None]:
        """
        上下文管理器，用于获取和自动释放 Zookeeper 分布式锁。
        注意：此操作应在已建立的会话中进行。

        Args:
            path (str): 锁的 Zookeeper 路径。
            identifier (str, optional): 锁的标识符，用于区分不同的锁持有者。

        Yields:
            None: 在获取锁后，执行 with 代码块内的代码。

        Raises:
            RuntimeError: 如果客户端未连接。
            Exception: 获取或持有锁期间发生的任何其他异常。

        Example:
            with client.session(): # 确保会话已建立
                with client.acquire_lock("/my/lock/path", "my_identifier"):
                    # 执行需要互斥保护的代码
                    print("锁已获取，执行关键任务...")
        """
        # 确保在获取锁之前客户端已连接
        if not self.zk or not self.zk.connected:
            raise KCZ_USE_ERROR.msg_format("获取锁前必须连接客户端。请使用, 请先使用 'session()' 上下文管理器连接客户端。")

        lock: Optional[Lock] = None
        try:
            # 创建锁对象（不存储在 self.lock 实例变量中，避免并发问题）
            # identifier 通常用于区分不同客户端或线程
            lock = self.zk.Lock(path, identifier=identifier)
            logger.debug(f"尝试获取锁 {path}，标识符 {identifier}")
            # acquire() 方法会阻塞直到获得锁或发生异常
            lock.acquire()
            logger.debug(f"锁已获取 {path}")
            yield # 执行 with 块中的代码
        except Exception as e:
            # 重新抛出异常，让调用者决定如何处理
            raise KCZ_USE_ERROR.msg_format(f"获取或持有锁 {path} 时出错: {str(e)}")
        finally:
            # 确保锁被释放
            if lock and lock.is_acquired:
                try:
                    # release() 方法释放锁
                    lock.release()
                    logger.info(f"锁已释放 {path}")
                except Exception as e:
                    # 释放锁失败是一个严重问题，可能导致死锁
                    # 重新抛出异常，让调用者知晓
                    raise KCZ_USE_ERROR.msg_format(f"释放锁 {path} 时出错: {str(e)}")

    def __enter__(self) -> 'ZkClient':
        """
        进入上下文管理器，连接到 Zookeeper。

        Returns:
            ZkClient: 当前实例。
        """
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        退出上下文管理器，断开与 Zookeeper 的连接。
        """
        self.disconnect()

    # --- 新增：创建节点 ---
    def create_node(
        self,
        path: str,
        value: Union[str, bytes] = b"",
        ephemeral: bool = False,
        sequence: bool = False,
        makepath: bool = False,
        acl: Optional[list] = None
    ) -> str:
        """
        创建一个 Zookeeper 节点 (znode)。

        Args:
            path (str): 要创建的节点的完整路径 (e.g., '/myapp/config').
            value (Union[str, bytes]): 节点关联的数据。如果为字符串，将被编码为 UTF-8 字节。
                                       默认为空字节串 b""。
            ephemeral (bool): 如果为 True，则创建临时节点。临时节点在客户端会话结束时自动删除。
                              默认为 False。
            sequence (bool): 如果为 True，则创建顺序节点。Zookeeper 会在路径末尾附加一个单调递增的计数器。
                             路径名应该是固定的，例如 '/myapp/queue/queue-'。
                             默认为 False。
            makepath (bool): 如果为 True，且路径的父节点不存在，则会自动创建所需的父节点。
                             默认为 False。
            acl (Optional[list]): 应用于新节点的 ACL (Access Control List) 列表。
                                  默认为 None，表示使用 Zookeeper 的 OPEN_ACL_UNSAFE (完全开放)。

        Returns:
            str: 实际创建的节点的完整路径。如果 `sequence` 为 True，这将包含服务器生成的序列号。

        Raises:
            RuntimeError: 如果客户端未连接。
            NodeExistsError: 如果节点已存在且 `makepath` 为 False (或父节点不存在且 `makepath` 为 False)。
            NoNodeError: 如果父节点不存在且 `makepath` 为 False。
            ZookeeperError: 其他 Zookeeper 相关错误。
            ValueError: 如果 value 是不支持的类型。
        """
        if not self.zk or not self.zk.connected:
            raise RuntimeError("客户端未连接。请使用上下文管理器或先调用 'connect()'。")

        # 处理数据值
        if isinstance(value, str):
            data = value.encode('utf-8')
        elif isinstance(value, bytes):
            data = value
        else:
            raise ValueError(f"值必须是 str 或 bytes 类型，但得到了 {type(value)}")

        # 设置默认 ACL
        if acl is None:
            acl = [kazoo_acl.make_digest_acl('world', 'anyone', all=True)] # OPEN_ACL_UNSAFE

        try:
            # 调用 KazooClient 的 create 方法
            created_path = self.zk.create(
                path,
                value=data,
                ephemeral=ephemeral,
                sequence=sequence,
                makepath=makepath,
                acl=acl
            )
            logger.info(f"节点创建成功，路径: {created_path}")
            return created_path
        except NodeExistsError:
            raise KCZ_USE_ERROR.msg_format(f"节点 {path} 已存在")
        except NoNodeError:
            raise KCZ_USE_ERROR.msg_format(f"父节点不存在 {path} (makepath={makepath})")
        except ZookeeperError as e:
            raise KCZ_USE_ERROR.msg_format(f"创建节点时 Zookeeper 发生错误 {path}: {e}")
        except Exception as e:
            raise KCZ_USE_ERROR.msg_format(f"创建节点时发生未预期错误 {path}: {e}")

    # --- 新增：设置节点数据 ---
    def set_node_data(
        self,
        path: str,
        value: Union[str, bytes],
        version: int = -1
    ) -> Any: # Kazoo 返回一个 Stat 对象，类型可能需要根据具体版本调整
        """
        设置 Zookeeper 节点的数据。

        Args:
            path (str): 要设置数据的节点路径。
            value (Union[str, bytes]): 新的数据。如果为字符串，将被编码为 UTF-8 字节。
            version (int): 要设置的数据的预期版本。这用于实现乐观锁。
                           如果节点的当前版本与提供的版本不匹配，则操作失败。
                           设置为 -1 (默认值) 表示不检查版本，直接覆盖。

        Returns:
            Any: 一个包含节点状态信息的对象 (通常是 kazoo.protocol.states.ZnodeStat)。
                 可以从中获取更新后的版本号、数据长度、修改时间等。

        Raises:
            RuntimeError: 如果客户端未连接。
            NoNodeError: 如果指定路径的节点不存在。
            BadVersionError: 如果提供的 `version` 与节点的当前版本不匹配 (乐观锁)。
            ZookeeperError: 其他 Zookeeper 相关错误。
            ValueError: 如果 value 是不支持的类型。
        """
        if not self.zk or not self.zk.connected:
            raise KCZ_CONNECT_ERROR.msg_format("客户端未连接。请使用上下文管理器或先调用 'connect()'。")

        # 处理数据值
        if isinstance(value, str):
            data = value.encode('utf-8')
        elif isinstance(value, bytes):
            data = value
        else:
            raise KCZ_USE_ERROR.msg_format(f"值必须是 str 或 bytes 类型，但得到了 {type(value)}")

        try:
            # 调用 KazooClient 的 set 方法
            stat = self.zk.set(path, data, version=version)
            logger.info(f"节点数据设置成功 {path}")
            return stat # 返回更新后的状态信息
        except NoNodeError:
            raise KCZ_USE_ERROR.msg_format(f"节点 {path} 不存在")
        except BadVersionError as e:
            raise KCZ_USE_ERROR.msg_format(f"版本不匹配 {path} (期望版本: {version})")
        except ZookeeperError as e: # 这通常会捕获 BadVersionError 等
            raise KCZ_USE_ERROR.msg_format(f"设置节点数据时 Zookeeper 发生错误 {path}: {e}")
        except Exception as e:
            raise KCZ_USE_ERROR.msg_format(f"设置节点数据时发生未预期错误 {path}: {e}")
        
    # --- (保留) 辅助方法示例：获取数据 ---
    def get_node_data(self, path: str) -> Optional[bytes]:
        """
        获取指定路径的节点数据。

        Args:
            path (str): Zookeeper 节点路径。

        Returns:
            Optional[bytes]: 节点数据，如果节点不存在则返回 None。

        Raises:
            RuntimeError: 如果客户端未连接。
            ZookeeperError: 其他 Zookeeper 相关错误。
        """
        if not self.zk or not self.zk.connected:
            raise KCZ_CONNECT_ERROR.msg_format("客户端未连接。请使用上下文管理器或先调用 'connect()'。")

        try:
            # get() 返回一个元组 (data, stat)
            data, stat = self.zk.get(path)
            return data
        except NoNodeError:
            return KCZ_USE_ERROR.msg_format(f"节点 {path} 不存在")
        except ZookeeperError as e:
            raise KCZ_USE_ERROR.msg_format(f"获取节点 {path} 数据时 Zookeeper 发生错误: {e}")
        except Exception as e:
            raise KCZ_USE_ERROR.msg_format(f"获取节点 {path} 数据时发生未预期错误: {e}")



class AsyncZkClient:
    """
    异步 Zookeeper 客户端封装，基于 aiozk 库。
    """

    def __init__(self, hosts: Optional[str] = None):
        """
        初始化 AsyncZkClient 实例。

        Args:
            hosts (str, optional): Zookeeper 服务器地址列表，格式为 'host1:port1,host2:port2'。
                                   如果未提供，则从环境变量 'ZOOKEEPER_HOSTS' 读取，
                                   默认为 '127.0.0.1:2181'。
        """
        self.zk_hosts = hosts or os.getenv('ZOOKEEPER_HOSTS')
        if self.zk_hosts is None:
            raise KCZ_CONNECT_ERROR.msg_format("zookeeper客户端初始化失败: 未提供zookeeper服务地址")
        self.zk: Optional[aiozk.ZKClient] = None

    async def connect(self) -> None:
        """
        异步连接到 Zookeeper 集群。
        如果已经连接，则不执行任何操作。
        """
        if self.zk is None or not self.zk.connected:
            try:
                # aiozk.ZKClient 是异步客户端
                self.zk = aiozk.ZKClient(self.zk_hosts)
                await self.zk.start() # 异步启动连接
                logger.debug(f"zookeeper异步客户端已连接: {self.zk_hosts}")
            except Exception as e:
                logger.debug(f"zookeeper异步客户端连接失败: {str(e)}")
                # 可以选择重新抛出异常或处理它
                raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端连接失败: {str(e)}")

    async def disconnect(self) -> None:
        """
        异步断开与 Zookeeper 集群的连接。
        如果未连接或已关闭，则不执行任何操作。
        """
        if self.zk is not None and self.zk.connected:
            try:
                await self.zk.close() # 异步关闭连接
                logger.debug("zookeeper异步客户端已断开")
            except Exception as e:
                raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端断开连接失败: {str(e)}")
            finally:
                self.zk = None # 确保引用被清除

    @asynccontextmanager
    async def session(self) -> AsyncGenerator['AsyncZkClient', None]:
        """
        异步上下文管理器，用于管理 Zookeeper 会话的生命周期。
        自动处理连接和断开连接。

        Yields:
            AsyncZkClient: 当前的客户端实例，可在 with 代码块内使用。
        
        Example:
            async with client.session() as zk_client:
                data, stat = await zk_client.zk.get("/my/path")
                # ... perform other async zk operations ...
        """
        await self.connect()
        try:
            # 将当前实例（已连接）yield 出去供使用
            yield self 
        finally:
            # 无论 with 块内是否发生异常，都确保断开连接
            await self.disconnect() 

    async def get_data(self, path: str) -> Optional[bytes]:
        """
        异步获取指定路径的数据。

        Args:
            path (str): Zookeeper 节点路径。

        Returns:
            bytes: 节点数据，如果节点不存在则返回 None。
        """
        if not self.zk:
            raise KCZ_CONNECT_ERROR.msg_format("zookeeper异步客户端未连接，无法取值: {path}")
        try:
            data, stat = await self.zk.get(path)
            return data
        except aiozk.exc.NoNode:
            raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端取值失败, 节点不存在: {path}")
        except Exception as e:
            raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端获取数据失败: {path}")

    async def create_node(self, path: str, data: bytes = b'', ephemeral: bool = False, sequential: bool = False) -> str:
        """
        异步创建一个 Zookeeper 节点。

        Args:
            path (str): 要创建的节点路径。
            data (bytes): 节点关联的数据。
            ephemeral (bool): 是否为临时节点。
            sequential (bool): 是否为顺序节点。

        Returns:
            str: 实际创建的节点路径。
        """
        if not self.zk:
            raise KCZ_CONNECT_ERROR.msg_format("zookeeper异步客户端未连接，无法创建节点")
        try:
            acl = aiozk.acls.OPEN_ACL_UNSAFE
            created_path = await self.zk.create(path, data=data, acl=acl, ephemeral=ephemeral, sequential=sequential)
            return created_path
        except aiozk.exc.NodeExists:
            raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端创建节点失败: 节点已存在: {path}")
        except Exception as e:
            raise KCZ_CONNECT_ERROR.msg_format(f"zookeeper异步客户端创建节点失败: {str(e)}")


# --- 使用示例 同步 ---
# if __name__ == "__main__":
#     client = ZkClient(hosts="localhost:2181") # 或使用环境变量
#
#     try:
#         with client.session() as zk_client:
#             # --- 创建节点 ---
#             node_path = "/my_test_node"
#             created_path = zk_client.create_node(node_path, "初始数据字符串")
#             print(f"节点创建于: {created_path}")
#
#             # 创建一个顺序节点
#             seq_node_base_path = "/my_sequence_node/seq-"
#             # 确保父节点存在
#             zk_client.create_node("/my_sequence_node", makepath=True)
#             seq_created_path = zk_client.create_node(seq_node_base_path, b"顺序数据", sequence=True)
#             print(f"顺序节点创建于: {seq_created_path}")
#
#             # --- 获取数据 ---
#             data = zk_client.get_node_data(node_path)
#             if 
#                 print(f"从 {node_path} 检索到数据: {data.decode('utf-8')}")
#
#             # --- 设置数据 ---
#             new_data = "更新后的数据"
#             stat = zk_client.set_node_data(node_path, new_data)
#             print(f"{node_path} 的数据已更新。新版本: {stat.version}")
#
#             # 再次获取数据验证
#             updated_data = zk_client.get_node_data(node_path)
#             if updated_
#                 print(f"检索到更新后的数据: {updated_data.decode('utf-8')}")
#
#             # --- 使用锁 ---
#             with zk_client.acquire_lock("/my/sync/lock", "同步工作者_1"):
#                 print("同步: 锁已获取，执行任务...")
#                 # 模拟一些工作
#                 import time
#                 time.sleep(2)
#                 # ... critical section ...
#                 pass
#             print("同步: 锁已释放。")
#
#     except Exception as e:
#         print(f"主示例中发生错误: {e}")


# --- 使用示例 ---
# import asyncio
#
# async def main():
#     client = AsyncZkClient(hosts="localhost:2181") # 或使用环境变量
#     
#     # 方式一：使用 session 上下文管理器
#     try:
#         async with client.session() as zk_client:
#             data = await zk_client.get_data("/my_test_node")
#             print(f"Data: {data}")
#             await zk_client.create_node("/my_new_async_node", b"Hello Async ZK!")
#     except Exception as e:
#         print(f"An error occurred: {e}")
#
#     # 方式二：手动连接和断开 (不推荐，容易忘记断开)
#     # try:
#     #     await client.connect()
#     #     data = await client.get_data("/my_test_node")
#     #     print(f"Data: {data}")
#     # finally:
#     #     await client.disconnect()
#
# asyncio.run(main())