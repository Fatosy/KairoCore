import os
import time
import sqlite3
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union, Sequence
from collections import OrderedDict
from queue import Queue, Empty

from ..utils.log import get_logger
from ..utils.panic import Panic

logger = get_logger()

# ================================
#           异常常量定义
# ================================
SQLITE_INIT_ERROR = Panic(11010, "SQLite配置异常，请检查env配置！")
SQLITE_PARAM_KEY_MATCH_ERROR = Panic(11011, "SQLite语句未匹配到对应参数，请检查！")
SQLITE_EXEC_ERROR = Panic(11012, "SQLite执行异常，请检查！")


# ================================
#           配置定义
# ================================
@dataclass
class SqliteConfig:
    """
    SQLite 连接与性能配置
    
    Attributes:
        db_path (str): 数据库文件路径
        pool_size (int): 连接池大小（SQLite 允许多连接，推荐设置 WAL 模式）
        cache_size (int): 查询缓存容量（LRU）
        cache_ttl (float): 查询缓存条目有效期（秒）
        pragma_wal (bool): 是否启用 WAL 模式（提高并发读写性能）
        pragma_synchronous (str): 同步级别（OFF/NORMAL/FULL，性能与数据安全权衡）
    """
    db_path: str = os.getenv("SQLITE_DB_PATH", os.path.join(os.getcwd(), "db.sqlite3"))
    pool_size: int = int(os.getenv("SQLITE_POOL_SIZE", "4"))
    cache_size: int = int(os.getenv("SQLITE_QUERY_CACHE_SIZE", "128"))
    cache_ttl: float = float(os.getenv("SQLITE_QUERY_CACHE_TTL", "30"))
    pragma_wal: bool = os.getenv("SQLITE_PRAGMA_WAL", "true").lower() == "true"
    pragma_synchronous: str = os.getenv("SQLITE_PRAGMA_SYNCHRONOUS", "NORMAL").upper()


# ================================
#        连接池（同步）
# ================================
class SqliteSessionPool:
    """
    基于连接池的 SQLite 会话管理器 (单例，同步)
    
    - 管理多连接队列，支持 with 上下文使用
    - 进入会话默认开启事务，退出自动提交/回滚
    - 对连接执行必要的 PRAGMA 初始化
    """
    _instance: Optional["SqliteSessionPool"] = None

    def __init__(self, config: Optional[SqliteConfig] = None):
        """
        初始化连接池
        
        Args:
            config (Optional[SqliteConfig]): SQLite 配置对象，若不提供则从环境变量加载
        Raises:
            Panic: 当配置缺失或非法时抛出 SQLITE_INIT_ERROR
        """
        if SqliteSessionPool._instance is not None:
            return
        self.config = config or SqliteConfig()
        if not self.config.db_path or self.config.pool_size < 1:
            raise SQLITE_INIT_ERROR
            
        # 自动创建数据库文件所在的父目录
        db_dir = os.path.dirname(self.config.db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"已自动创建数据库目录: {db_dir}")
            except Exception as e:
                logger.warning(f"尝试创建数据库目录失败: {db_dir}, error: {e}")
                # 继续尝试连接，可能由其他权限或挂载机制处理

        self._pool: Queue[sqlite3.Connection] = Queue(maxsize=self.config.pool_size)
        self._init_pool()
        SqliteSessionPool._instance = self
        logger.info(f"SQLite连接池初始化完成，db={self.config.db_path}, size={self.config.pool_size}")

    def _init_pool(self) -> None:
        """
        创建连接并放入连接池队列
        """
        for _ in range(self.config.pool_size):
            conn = sqlite3.connect(self.config.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._init_pragmas(conn)
            self._pool.put(conn)

    def _init_pragmas(self, conn: sqlite3.Connection) -> None:
        """
        连接级初始化 PRAGMA 参数，提高性能与约束一致性
        
        Args:
            conn (sqlite3.Connection): 目标连接
        Raises:
            Panic: 当 PRAGMA 初始化失败时抛出 SQLITE_INIT_ERROR
        """
        try:
            cur = conn.cursor()
            if self.config.pragma_wal:
                cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute(f"PRAGMA synchronous={self.config.pragma_synchronous};")
            cur.execute("PRAGMA foreign_keys=ON;")
            cur.close()
        except Exception as e:
            logger.error(f"初始化 PRAGMA 失败: {e}", exc_info=True)
            raise SQLITE_INIT_ERROR.msg_format(str(e))

    @classmethod
    def get_instance(cls, config: Optional[SqliteConfig] = None) -> "SqliteSessionPool":
        """
        获取连接池单例
        
        Args:
            config (Optional[SqliteConfig]): 可选配置；首次调用时生效
        Returns:
            SqliteSessionPool: 连接池实例
        """
        if cls._instance is None:
            cls(config)
        return cls._instance

    @classmethod
    def close_all_connections(cls) -> None:
        """
        关闭连接池中的所有连接并重置单例
        """
        if cls._instance:
            while True:
                try:
                    conn = cls._instance._pool.get_nowait()
                    try:
                        conn.close()
                    except Exception:
                        pass
                except Empty:
                    break
            cls._instance = None
            logger.info("SQLite连接池已关闭")

    def acquire(self, timeout: Optional[float] = None) -> sqlite3.Connection:
        """
        从连接池获取一个连接
        
        Args:
            timeout (Optional[float]): 获取超时时间
        Returns:
            sqlite3.Connection: 连接实例
        Raises:
            Panic: 获取失败时抛出 SQLITE_EXEC_ERROR
        """
        try:
            conn = self._pool.get(timeout=timeout)
            return conn
        except Exception as e:
            logger.error(f"获取连接失败: {e}", exc_info=True)
            raise SQLITE_EXEC_ERROR.msg_format(str(e))

    def release(self, conn: sqlite3.Connection) -> None:
        """
        将连接归还到连接池
        
        Args:
            conn (sqlite3.Connection): 连接实例
        """
        try:
            self._pool.put(conn)
        except Exception as e:
            logger.error(f"释放连接失败: {e}", exc_info=True)
            try:
                conn.close()
            except Exception:
                pass


# ================================
#         LRU 查询缓存
# ================================
class _LRUCache:
    """
    简单的带 TTL 的 LRU 缓存，用于 SELECT 查询结果缓存
    """
    def __init__(self, capacity: int, ttl: float):
        """
        初始化缓存
        
        Args:
            capacity (int): 容量上限
            ttl (float): 条目过期时间（秒）
        """
        self.capacity = max(1, capacity)
        self.ttl = max(0.0, ttl)
        self._store: OrderedDict[Tuple[str, Tuple[Any, ...]], Tuple[float, Any]] = OrderedDict()

    def get(self, key: Tuple[str, Tuple[Any, ...]]) -> Optional[Any]:
        """
        读取缓存条目，若过期则删除并返回 None
        
        Args:
            key (Tuple[str, Tuple[Any, ...]]): 缓存键
        Returns:
            Optional[Any]: 命中返回值，否则 None
        """
        item = self._store.get(key)
        if not item:
            return None
        ts, val = item
        if self.ttl and (time.time() - ts) > self.ttl:
            # 过期则删除
            try:
                del self._store[key]
            except KeyError:
                pass
            return None
        # 移动到末尾标记为近期使用
        self._store.move_to_end(key)
        return val

    def set(self, key: Tuple[str, Tuple[Any, ...]], value: Any) -> None:
        """
        写入缓存并维护 LRU 顺序与容量
        """
        self._store[key] = (time.time(), value)
        self._store.move_to_end(key)
        if len(self._store) > self.capacity:
            self._store.popitem(last=False)

    def clear(self) -> None:
        """
        清空缓存
        """
        self._store.clear()


# ================================
#        同步会话管理器
# ================================
class SqliteSession:
    """
    同步 SQLite 上下文管理器，使用连接池获取连接
    
    - 所有用户输入通过命名参数 `:param` 转位置参数防注入
    - 支持 CRUD、批量操作、事务、分页、查询缓存
    """
    def __init__(self, config: Optional[SqliteConfig] = None):
        """
        初始化会话
        
        Args:
            config (Optional[SqliteConfig]): 配置对象
        """
        self._pool = SqliteSessionPool.get_instance(config)
        self.connection: Optional[sqlite3.Connection] = None
        self._cache = _LRUCache(self._pool.config.cache_size, self._pool.config.cache_ttl)

    def __enter__(self) -> "SqliteSession":
        """
        进入上下文，获取连接并开启事务
        
        Returns:
            SqliteSession: 自身
        """
        self.connection = self._pool.acquire()
        # 默认开启事务
        self.connection.execute("BEGIN")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """
        退出上下文，自动提交或回滚并归还连接
        """
        if self.connection:
            try:
                if exc_type is None:
                    try:
                        self.connection.commit()
                    except Exception as e:
                        logger.error(f"提交事务失败: {e}", exc_info=True)
                        self.connection.rollback()
                        raise SQLITE_EXEC_ERROR.msg_format(str(e))
                else:
                    self.connection.rollback()
            finally:
                self._pool.release(self.connection)
                self.connection = None

    # ---------- 参数转换 ----------
    def _convert_sql_params(self, query: str, params: Optional[Dict[str, Any]]) -> Tuple[str, Tuple[Any, ...]]:
        """
        将命名参数 (:param) 转换为 SQLite 位置参数 (?)，支持 IN 列表展开
        
        Args:
            query (str): 原始 SQL
            params (Optional[Dict[str, Any]]): 参数字典
        Returns:
            Tuple[str, Tuple[Any, ...]]: 转换后的 SQL 与参数元组
        Raises:
            Panic: 缺少必要参数时抛出 SQLITE_PARAM_KEY_MATCH_ERROR
        """
        if not params:
            return query, ()

        def is_sequence(val: Any) -> bool:
            return isinstance(val, Sequence) and not isinstance(val, (str, bytes))

        parts: List[str] = []
        values: List[Any] = []
        idx = 0
        while idx < len(query):
            ch = query[idx]
            if ch == ":":
                # 读取参数名
                j = idx + 1
                while j < len(query) and (query[j].isalnum() or query[j] == "_"):
                    j += 1
                name = query[idx + 1 : j]
                if name not in params:
                    raise SQLITE_PARAM_KEY_MATCH_ERROR.msg_format(f"缺少参数 - {name}")
                val = params[name]
                # 判断是否为序列（用于 IN 列表）
                if is_sequence(val):
                    if len(val) == 0:
                        # 空列表，构造一个永不命中的条件
                        parts.append("(NULL)")
                    else:
                        parts.append("(" + ",".join(["?"] * len(val)) + ")")
                        values.extend(list(val))
                else:
                    parts.append("?")
                    values.append(val)
                idx = j
            else:
                parts.append(ch)
                idx += 1
        return "".join(parts), tuple(values)

    # ---------- 执行核心 ----------
    def _execute_core(self, query: str, params: Tuple[Any, ...] = (), fetch: str = "none") -> Any:
        """
        执行核心（参数化查询）
        
        Args:
            query (str): 可执行 SQL
            params (Tuple[Any, ...]): 位置参数
            fetch (str): 结果模式：none/one/all/rowcount
        Returns:
            Any: 查询结果或影响行数
        Raises:
            Panic: 执行失败时抛出 SQLITE_EXEC_ERROR
        """
        if not self.connection:
            raise SQLITE_EXEC_ERROR.msg_format("数据库连接未获取")
        try:
            cur = self.connection.cursor()
            cur.execute(query, params)
            if fetch == "all":
                rows = cur.fetchall()
                res = [dict(r) for r in rows]
                cur.close()
                return res
            elif fetch == "one":
                row = cur.fetchone()
                cur.close()
                return dict(row) if row else None
            elif fetch == "rowcount":
                count = cur.rowcount
                cur.close()
                return count
            else:
                cur.close()
                return None
        except Exception as e:
            logger.error(f"SQLite执行失败: {e}", exc_info=True)
            raise SQLITE_EXEC_ERROR.msg_format(str(e))

    # ---------- 查询缓存包装 ----------
    def _cache_key(self, processed_query: str, processed_params: Tuple[Any, ...]) -> Tuple[str, Tuple[Any, ...]]:
        """
        生成缓存键
        """
        return processed_query, processed_params

    def _fetch_with_cache(self, processed_query: str, processed_params: Tuple[Any, ...], fetch: str) -> Any:
        """
        带缓存的查询执行
        """
        key = self._cache_key(processed_query, processed_params)
        cached = self._cache.get(key) if fetch in ("all", "one") else None
        if cached is not None:
            return cached
        res = self._execute_core(processed_query, processed_params, fetch=fetch)
        if fetch in ("all", "one"):
            self._cache.set(key, res)
        return res

    def _invalidate_cache(self) -> None:
        """
        失效所有查询缓存（在写操作后调用）
        """
        self._cache.clear()

    # ---------- CRUD ----------
    def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行 SELECT 查询，返回所有结果
        """
        processed_query, processed_params = self._convert_sql_params(query, params)
        return self._fetch_with_cache(processed_query, processed_params, fetch="all")

    def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        执行 SELECT 查询，返回单个结果
        """
        processed_query, processed_params = self._convert_sql_params(query, params)
        return self._fetch_with_cache(processed_query, processed_params, fetch="one")

    def execute_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        执行 INSERT/UPDATE/DELETE，返回影响行数
        """
        processed_query, processed_params = self._convert_sql_params(query, params)
        affected = self._execute_core(processed_query, processed_params, fetch="rowcount")
        self._invalidate_cache()
        return affected

    def batch_execute(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """
        批量执行 INSERT/UPDATE/DELETE
        """
        if not self.connection or not params_list:
            return 0
        processed_query, _ = self._convert_sql_params(query, params_list[0])
        all_params: List[Tuple[Any, ...]] = [
            self._convert_sql_params(query, p)[1] for p in params_list
        ]
        try:
            cur = self.connection.cursor()
            cur.executemany(processed_query, all_params)
            count = cur.rowcount
            cur.close()
            self._invalidate_cache()
            return count
        except Exception as e:
            logger.error(f"批量执行失败: {e}", exc_info=True)
            raise SQLITE_EXEC_ERROR.msg_format(str(e))

    # 便捷方法
    def insert(self, query: str, params: Dict[str, Any]) -> int:
        """
        语义化：插入单条记录
        """
        return self.execute_one(query, params)

    def update(self, query: str, params: Dict[str, Any]) -> int:
        """
        语义化：更新记录
        """
        return self.execute_one(query, params)

    def delete(self, query: str, params: Dict[str, Any]) -> int:
        """
        语义化：删除记录
        """
        return self.execute_one(query, params)

    def insert_many(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """
        语义化：批量插入记录
        """
        return self.batch_execute(query, params_list)

    # ---------- 分页 ----------
    def query_with_pagination(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        offset: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        执行分页查询，返回 (结果列表, 总数)
        """
        # 统计总数
        count_query = f"SELECT COUNT(*) as total FROM ({query}) AS t"
        processed_count_query, processed_count_params = self._convert_sql_params(count_query, params)
        count_row = self._execute_core(processed_count_query, processed_count_params, fetch="one")
        total = count_row["total"] if count_row else 0
        # 分页查询
        base_query, base_params = self._convert_sql_params(query, params)
        offset = 1 if offset <= 1 else offset
        new_offset = int(limit) * (offset - 1)
        paged_query = f"{base_query} LIMIT ? OFFSET ?"
        paged_params = base_params + (int(limit), int(new_offset))
        results = self._fetch_with_cache(paged_query, paged_params, fetch="all")
        return results, total

    # ---------- 表结构检查与自动创建 ----------
    def ensure_table(self, table_name: str, create_sql: str) -> bool:
        """
        检查并创建单表
        
        Args:
            table_name (str): 表名
            create_sql (str): 创建表 SQL
        Returns:
            bool: 若创建了新表返回 True，否则 False
        """
        row = self.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=:name",
            {"name": table_name},
        )
        if row:
            return False
        self.execute_one(create_sql, {})
        logger.info(f"已创建表: {table_name}")
        return True

    def ensure_tables(self, schema: Dict[str, str]) -> List[str]:
        """
        批量检查并创建表结构
        
        Args:
            schema (Dict[str, str]): {表名: 创建SQL}
        Returns:
            List[str]: 实际创建的表名列表
        """
        created: List[str] = []
        for t, sql in schema.items():
            if self.ensure_table(t, sql):
                created.append(t)
        return created


# ================================
#        异步连接池与会话
# ================================
class AsyncSqliteSessionPool:
    """
    异步 SQLite 连接池管理器（基于线程转移方式实现异步接口）
    """
    _instance: Optional["AsyncSqliteSessionPool"] = None

    def __init__(self, config: Optional[SqliteConfig] = None):
        """
        初始化异步连接池包装（复用同步池）
        """
        if AsyncSqliteSessionPool._instance is not None:
            return
        self._sync_pool = SqliteSessionPool.get_instance(config)
        AsyncSqliteSessionPool._instance = self

    @classmethod
    def get_instance(cls, config: Optional[SqliteConfig] = None) -> "AsyncSqliteSessionPool":
        """
        获取异步连接池单例
        """
        if cls._instance is None:
            cls(config)
        return cls._instance

    @classmethod
    def close_all_connections(cls) -> None:
        """
        关闭所有连接（委托同步池）
        """
        SqliteSessionPool.close_all_connections()
        cls._instance = None


class AsyncSqliteSession:
    """
    异步 SQLite 上下文管理器
    
    - 使用 asyncio.to_thread 将同步 sqlite 调用转移到线程，避免阻塞事件循环
    - API 与同步版本保持一致（fetch_all/fetch_one/execute_one/batch_execute/query_with_pagination）
    """
    def __init__(self, config: Optional[SqliteConfig] = None):
        """
        初始化异步会话
        """
        self._pool = AsyncSqliteSessionPool.get_instance(config)
        self._sync_session = SqliteSession(config)
        self.connection: Optional[sqlite3.Connection] = None

    async def __aenter__(self) -> "AsyncSqliteSession":
        """
        异步进入上下文，获取连接并开启事务
        """
        # 在线程中获取连接并开启事务
        def _enter():
            self._sync_session.__enter__()
            self.connection = self._sync_session.connection
        await asyncio.to_thread(_enter)
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """
        异步退出上下文，自动提交或回滚并释放连接
        """
        def _exit():
            self._sync_session.__exit__(exc_type, exc_value, traceback)
        await asyncio.to_thread(_exit)
        self.connection = None

    # 异步封装（基于同步方法）
    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        异步查询所有
        """
        return await asyncio.to_thread(self._sync_session.fetch_all, query, params)

    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        异步查询单条
        """
        return await asyncio.to_thread(self._sync_session.fetch_one, query, params)

    async def execute_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        异步执行单条写操作
        """
        return await asyncio.to_thread(self._sync_session.execute_one, query, params)

    async def batch_execute(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """
        异步批量写操作
        """
        return await asyncio.to_thread(self._sync_session.batch_execute, query, params_list)

    async def query_with_pagination(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        offset: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        异步分页查询
        """
        return await asyncio.to_thread(self._sync_session.query_with_pagination, query, params, offset, limit)

    async def ensure_table(self, table_name: str, create_sql: str) -> bool:
        """
        异步检查并创建单表
        """
        return await asyncio.to_thread(self._sync_session.ensure_table, table_name, create_sql)

    async def ensure_tables(self, schema: Dict[str, str]) -> List[str]:
        """
        异步批量检查并创建表
        """
        return await asyncio.to_thread(self._sync_session.ensure_tables, schema)


# ================================
#             使用示例
# ================================
if __name__ == "__main__":
    # 简单自检示例（仅在本模块直接运行时）
    schema = {
        "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL
        );
        """
    }
    try:
        with SqliteSession() as s:
            s.ensure_tables(schema)
            s.insert("INSERT INTO users (name, age) VALUES (:name, :age)", {"name": "Alice", "age": 30})
            one = s.fetch_one("SELECT * FROM users WHERE name=:name", {"name": "Alice"})
            logger.info(f"查询结果: {one}")
    except Panic as e:
        logger.error(e.message)
