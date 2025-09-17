import pymysql
import aiomysql
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
from dbutils.pooled_db import PooledDB, PooledSharedDBConnection

from ..common.errors import (
    MQSN_INIT_ERROR,
    MQSN_PARAM_KEY_PATCH_ERROR
)


# --- 基于连接池的 MysqlSessionPool 同步 ---
class MysqlSessionPool:
    """
    基于连接池的 MySQL 会话管理器 (单例)。
    """
    _pool = None

    def __init__(self):
        self.host = os.getenv('DB_HOST')
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.db = os.getenv('DB_NAME')
        self.port = int(os.getenv('DB_PORT'))
        if not self.host or not self.user or not self.password or not self.db or not self.port:
            raise MQSN_INIT_ERROR

        # 连接池配置
        self.min_cached = int(os.getenv('DB_MIN_CACHED', 1))
        self.max_cached = int(os.getenv('DB_MAX_CACHED', 5))
        self.max_shared = int(os.getenv('DB_MAX_SHARED', 5))
        self.max_connections = int(os.getenv('DB_MAX_CONNECTIONS', 10))

        if MysqlSessionPool._pool is None:
            # *** 防注入：PooledDB 内部使用 pymysql，它支持安全的参数化查询 ***
            MysqlSessionPool._pool = PooledDB(
                creator=pymysql,
                mincached=self.min_cached,
                maxcached=self.max_cached,
                maxshared=self.max_shared,
                maxconnections=self.max_connections,
                blocking=True,
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.db,
                port=self.port,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=False
            )

    @classmethod
    def close_all_connections(cls):
        """关闭连接池中的所有连接"""
        if cls._pool:
            cls._pool.close()
            cls._pool = None

# --- 使用连接池的 MysqlSession 同步 ---
class MysqlSession:
    """
    简化版 MySQL 上下文管理器，使用连接池获取连接。
    *** 核心防注入机制：所有用户输入都通过参数化查询处理 ***
    """

    def __init__(self):
        self.connection: PooledSharedDBConnection = None
        # 如果连接池未初始化，则初始化它
        if MysqlSessionPool._pool is None:
            MysqlSessionPool()
        self._pool = MysqlSessionPool._pool

    def __enter__(self):
        if not self._pool:
            raise RuntimeError("连接池未初始化")
        self.connection = self._pool.connection() # 从池中获取连接
        # 默认开始事务
        self.connection.begin()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.connection:
            try:
                if exc_type is None:
                    self.connection.commit()
                else:
                    self.connection.rollback()
            finally:
                # 将连接返回给连接池
                self.connection.close() 

    def _convert_sql_params(self, query: str, params: Optional[Dict[str, Any]]) -> Tuple[str, Tuple]:
        """
        将命名参数 (:param) 转换为位置参数 (%s)，并准备参数元组。
        *** 防注入关键步骤 1：将用户输入与 SQL 结构分离 ***
        """
        if not params:
            return query, ()

        # 使用正则表达式查找所有 :param 格式的参数占位符
        pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)'
        placeholders = re.findall(pattern, query)
        
        # 根据查询中占位符的顺序构建参数元组
        param_values = []
        for placeholder in placeholders:
            if placeholder in params:
                param_values.append(params[placeholder])
            else:
                raise MQSN_PARAM_KEY_PATCH_ERROR.msg_format(f'缺少参数 - {placeholder}')
        
        # 使用正则表达式替换所有占位符为 %s
        processed_query = re.sub(pattern, '%s', query)
        
        return processed_query, tuple(param_values)

    def _execute_core(self, query: str, params: Tuple = (), fetch: str = 'none') -> Any:
        """
        核心执行方法，使用参数化查询。
        *** 防注入核心：cursor.execute/query 处理参数转义 ***
        """
        if not self.connection:
            raise RuntimeError("数据库连接未获取")

        with self.connection.cursor() as cursor:
            # *** 防注入关键：pymysql 安全地处理 params 元组 ***
            cursor.execute(query, params) 
            if fetch == 'all':
                return cursor.fetchall()
            elif fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'rowcount':
                return cursor.rowcount
            else:
                pass

    def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行 SELECT 查询，返回所有结果"""
        processed_query, processed_params = self._convert_sql_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='all')

    def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """执行 SELECT 查询，返回单个结果"""
        processed_query, processed_params = self._convert_sql_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='one')

    def execute_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        processed_query, processed_params = self._convert_sql_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='rowcount')

    def batch_execute(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """执行批处理更新"""
        if not self.connection or not params_list:
            return 0

        # 转换第一个参数字典以获取查询结构
        processed_query, _ = self._convert_sql_params(query, params_list[0])
        
        # 准备所有参数元组列表
        processed_params_list = [
            self._convert_sql_params(query, params)[1] for params in params_list
        ]
        
        with self.connection.cursor() as cursor:
            # *** 防注入：executemany 同样安全处理参数 ***
            return cursor.executemany(processed_query, processed_params_list)

    def query_with_pagination(
        self, 
        query: str, 
        params: Optional[Dict[str, Any]] = None, 
        offset: int = 1, 
        limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """执行分页查询，返回 (结果列表, 总数)"""
        
        # 1. 获取总数 (注意：子查询可能影响性能，复杂查询建议优化)
        # *** 防注入：count 查询也使用参数化 ***
        count_query = "SELECT COUNT(*) as total FROM (" + query + ") AS t"
        count_result = self.execute_single_query(count_query, params)
        total_count = count_result['total'] if count_result else 0

        # 2. 执行分页查询
        # *** 防注入关键：将 LIMIT 和 OFFSET 也作为参数处理 ***
        if not self.connection:
            raise RuntimeError("数据库连接未获取")

        # 转换主查询的命名参数
        base_query, base_params_tuple = self._convert_sql_params(query, params)
        
        # 将 LIMIT 和 OFFSET 附加到参数元组末尾
        # *** 防注入：确保 offset 和 limit 是整数 ***
        paged_query = f"{base_query} LIMIT %s OFFSET %s"
        if offset <= 1:
            offset = 1
        new_offset = int(limit) * (offset -1)
        paged_params = base_params_tuple + (int(limit), int(new_offset)) # 强制转换为 int

        with self.connection.cursor() as cursor:
            # *** 防注入核心：所有参数（包括 limit/offset）都通过 execute 传递 ***
            cursor.execute(paged_query, paged_params)
            results = cursor.fetchall()
            
        return results, total_count


# --- 异步 MySQL 连接池管理器 (单例) ---
class AsyncMysqlSessionPool:
    """
    基于 aiomysql 的异步 MySQL 连接池管理器 (单例)。
    """
    _pool: Optional[aiomysql.Pool] = None

    def __init__(self):
        if AsyncMysqlSessionPool._pool is not None:
            # 如果池已存在，则不重复初始化
            return

        self.host = os.getenv('DB_HOST')
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.db = os.getenv('DB_NAME')
        self.port = int(os.getenv('DB_PORT', 3306)) # 默认端口 3306

        if not all([self.host, self.user, self.password, self.db]):
            raise MQSN_INIT_ERROR("数据库连接参数缺失")

        # 连接池配置
        self.min_size = int(os.getenv('DB_MIN_CACHED', 1))
        self.max_size = int(os.getenv('DB_MAX_CACHED', 10)) # aiomysql 使用 minsize/maxsize

        # 注意：这里没有直接初始化池，因为 __init__ 是同步的。
        # 池的初始化将在首次 await get_pool() 时进行。

    @classmethod
    async def get_pool(cls) -> aiomysql.Pool:
        """获取或创建连接池实例 (异步)"""
        if cls._pool is None:
            instance = cls() # 触发参数检查
            # 使用 aiomysql.create_pool 创建连接池 [[9]]
            cls._pool = await aiomysql.create_pool(
                host=instance.host,
                port=instance.port,
                user=instance.user,
                password=instance.password,
                db=instance.db,
                minsize=instance.min_size,
                maxsize=instance.max_size,
                charset='utf8mb4',
                autocommit=False,
                echo=False # 可设置为 True 查看 SQL 日志
            )
        return cls._pool

    @classmethod
    async def close_all_connections(cls):
        """关闭连接池中的所有连接"""
        if cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed() # 等待所有连接关闭
            cls._pool = None

# --- 异步 MySQL 会话管理器 ---
class AsyncMysqlSession:
    """
    异步 MySQL 上下文管理器，用于获取和管理连接。
    *** 核心防注入机制：所有用户输入都通过参数化查询处理 ***
    """

    def __init__(self):
        self.pool: Optional[aiomysql.Pool] = None
        self.connection: Optional[aiomysql.Connection] = None
        self.transaction_conn: Optional[aiomysql.Connection] = None # 用于事务

    async def __aenter__(self):
        self.pool = await AsyncMysqlSessionPool.get_pool()
        if not self.pool:
            raise RuntimeError("异步连接池未初始化")
        # 从池中获取连接
        self.connection = await self.pool.acquire()
        # 默认开始事务
        await self.connection.begin()
        self.transaction_conn = self.connection # 标记事务已开始
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.connection:
            try:
                if exc_type is None:
                    # 如果没有异常，提交事务（如果在事务中）
                    if self.transaction_conn:
                         await self.connection.commit()
                else:
                    # 如果有异常，回滚事务（如果在事务中）
                    if self.transaction_conn:
                        await self.connection.rollback()
            finally:
                # 将连接返回给连接池
                await self.pool.release(self.connection)
                self.connection = None
                self.transaction_conn = None

    async def begin(self):
        """开始一个事务"""
        if not self.connection:
             raise RuntimeError("数据库连接未获取")
        if self.transaction_conn:
             raise RuntimeError("事务已处于活动状态")
        await self.connection.begin()
        self.transaction_conn = self.connection # 标记事务已开始

    async def _convert_sql_params(self, query: str, params: Optional[Dict[str, Any]]) -> Tuple[str, Tuple]:
        """
        将命名参数 (:param) 转换为位置参数 (%s)，并准备参数元组。
        *** 防注入关键步骤 1：将用户输入与 SQL 结构分离 ***
        """
        if not params:
            return query, ()

        # 使用正则表达式查找所有 :param 格式的参数占位符
        pattern = r':([a-zA-Z_][a-zA-Z0-9_]*)'
        placeholders = re.findall(pattern, query)

        # 根据查询中占位符的顺序构建参数元组
        param_values = []
        for placeholder in placeholders:
            if placeholder in params:
                param_values.append(params[placeholder])
            else:
                raise MQSN_PARAM_KEY_PATCH_ERROR.msg_format(f'缺少参数 - {placeholder}')

        # 使用正则表达式替换所有占位符为 %s
        processed_query = re.sub(pattern, '%s', query)

        return processed_query, tuple(param_values)

    async def _execute_core(self, query: str, params: Tuple = (), fetch: str = 'none') -> Any:
        """
        核心执行方法，使用参数化查询。
        *** 防注入核心：aiomysql 安全地处理 params 元组 ***
        """
        if not self.connection:
            raise RuntimeError("数据库连接未获取")

        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            # *** 防注入关键：aiomysql 安全地处理 params 元组 ***
            await cursor.execute(query, params)
            if fetch == 'all':
                return await cursor.fetchall()
            elif fetch == 'one':
                return await cursor.fetchone()
            elif fetch == 'rowcount':
                return cursor.rowcount
            else:
                return None

    async def fetch_all(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行 SELECT 查询，返回所有结果"""
        processed_query, processed_params = await self._convert_sql_params(query, params)
        return await self._execute_core(processed_query, processed_params, fetch='all')

    async def fetch_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """执行 SELECT 查询，返回单个结果"""
        processed_query, processed_params = await self._convert_sql_params(query, params)
        return await self._execute_core(processed_query, processed_params, fetch='one')

    async def execute_one(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        processed_query, processed_params = await self._convert_sql_params(query, params)
        return await self._execute_core(processed_query, processed_params, fetch='rowcount')

    async def batch_execute(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """执行批处理更新"""
        if not self.connection or not params_list:
            return 0

        # 转换第一个参数字典以获取查询结构
        processed_query, _ = await self._convert_sql_params(query, params_list[0])

        # 准备所有参数元组列表
        processed_params_list = [
            (await self._convert_sql_params(query, params))[1] for params in params_list
        ]

        async with self.connection.cursor() as cursor:
            # *** 防注入：executemany 同样安全处理参数 ***
            res = await cursor.executemany(processed_query, processed_params_list)
            return res # executemany 返回成功执行的语句数

    async def query_with_pagination(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """执行分页查询，返回 (结果列表, 总数)"""

        # 1. 获取总数 (注意：子查询可能影响性能，复杂查询建议优化)
        # *** 防注入：count 查询也使用参数化 ***
        count_query = "SELECT COUNT(*) as total FROM (" + query + ") AS t"
        # 注意：这里调用的是同步版本的 _convert_sql_params，因为它不涉及 IO
        count_processed_query, count_processed_params = await self._convert_sql_params(count_query, params)
        count_result = await self._execute_core(count_processed_query, count_processed_params, fetch='one')
        total_count = count_result['total'] if count_result else 0

        # 2. 执行分页查询
        if not self.connection:
            raise RuntimeError("数据库连接未获取")

        # 转换主查询的命名参数
        base_query, base_params_tuple = await self._convert_sql_params(query, params)

        # 将 LIMIT 和 OFFSET 附加到参数元组末尾
        # *** 防注入：确保 offset 和 limit 是整数 ***
        paged_query = f"{base_query} LIMIT %s OFFSET %s"
        offset = 1 if offset <= 1 else offset
        new_offset = limit * (offset - 1)
        paged_params = base_params_tuple + (int(limit), int(new_offset)) # 强制转换为 int

        async with self.connection.cursor(aiomysql.DictCursor) as cursor:
            # *** 防注入核心：所有参数（包括 limit/offset）都通过 execute 传递 ***
            await cursor.execute(paged_query, paged_params)
            results = await cursor.fetchall()

        return results, total_count


# --- 使用示例 ---
if __name__ == "__main__":
    # 模拟使用示例 (需要真实数据库才能运行)
    """
    try:
        with MysqlSession() as session:
            # --- 安全的参数化查询示例 ---
            
            # 1. 基本查询 (防注入)
            user_input_name = "Alice'; DROP TABLE users; --" # 恶意输入
            users = session.execute_query(
                "SELECT * FROM users WHERE name = :name OR age > :min_age", 
                {'name': user_input_name, 'min_age': 18} # 安全处理
            )
            # 实际执行的 SQL 类似于: SELECT * FROM users WHERE name = ? OR age > ?
            # 参数被安全转义，不会执行 DROP TABLE
            
            # 2. 更新操作 (防注入)
            session.execute_update(
                "UPDATE users SET email = :email WHERE id = :user_id",
                {'email': 'new@example.com', 'user_id': 1}
            )
            
            # 3. 分页查询 (防注入)
            # 即使 offset 或 limit 来自用户输入，也会被安全处理
            user_offset = "10; DELETE FROM users;" # 恶意 offset (字符串)
            user_limit = 5
            paged_users, total = session.execute_paged_query(
                "SELECT * FROM users WHERE status = :status ORDER BY id",
                {'status': 'active'},
                offset=int(user_offset.split(';')[0]), # 应用层确保是整数
                limit=user_limit
            )
            # LIMIT 和 OFFSET 值通过参数化安全传递
            
            print("操作成功完成")

    except Exception as e:
        print(f"数据库操作出错: {e}")
    finally:
        # 程序结束前关闭连接池 (可选)
        # MysqlSessionPool.close_all_connections()
    """

    # --- 使用示例 ---
# async def main():
#     try:
#         async with AsyncMysqlSession() as session:
#             # 示例 1: 查询所有
#             users = await session.fetch_all("SELECT * FROM users WHERE age > :age", {"age": 18})
#             print("Users over 18:", users)
#
#             # 示例 2: 查询单个
#             user = await session.fetch_one("SELECT * FROM users WHERE id = :id", {"id": 1})
#             print("User with id 1:", user)
#
#             # 示例 3: 插入/更新/删除
#             affected_rows = await session.execute_one(
#                 "INSERT INTO users (name, age) VALUES (:name, :age)",
#                 {"name": "Alice", "age": 30}
#             )
#             print(f"Inserted {affected_rows} row(s)")
#
#             # 示例 4: 分页查询
#             page_results, total = await session.query_with_pagination(
#                 "SELECT * FROM users WHERE active = :active",
#                 {"active": 1},
#                 offset=0,
#             )
#             print(f"Page 1 (20 items): {page_results}")
#             print(f"Total active users: {total}")
#
#             # 示例 5: 事务
#             try:
#                 await session.begin()
#                 await session.execute_one("UPDATE accounts SET balance = balance - :amount WHERE id = :id", {"id": 1, "amount": 100})
#                 await session.execute_one("UPDATE accounts SET balance = balance + :amount WHERE id = :id", {"id": 2, "amount": 100})
#                 # 如果一切顺利，__aexit__ 会提交事务
#             except Exception as e:
#                 # 如果有异常，__aexit__ 会回滚事务
#                 print(f"Transaction failed: {e}")
#                 raise
#
#         # 关闭连接池 (通常在应用关闭时调用一次)
#         # await AsyncMysqlSessionPool.close_all_connections()
#
#     except Exception as e:
#         print(f"Database error: {e}")