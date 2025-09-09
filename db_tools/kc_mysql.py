import pymysql
import os
from typing import Any, Dict, List, Optional, Tuple
from DBUtils.PooledDB import PooledDB # pip install DBUtils

# --- 基于连接池的 MysqlSessionPool ---
class MysqlSessionPool:
    """
    基于连接池的 MySQL 会话管理器 (单例)。
    """
    _pool = None

    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.user = os.getenv('DB_USER', 'root')
        self.password = os.getenv('DB_PASSWORD', '')
        self.db = os.getenv('DB_NAME', 'test_db')
        self.port = int(os.getenv('DB_PORT', 3306))
        
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

# --- 使用连接池的 MysqlSession ---
class MysqlSession:
    """
    简化版 MySQL 上下文管理器，使用连接池获取连接。
    *** 核心防注入机制：所有用户输入都通过参数化查询处理 ***
    """

    def __init__(self):
        self.connection = None
        self._pool = MysqlSessionPool._pool

    def __enter__(self):
        if not self._pool:
            raise RuntimeError("连接池未初始化")
        self.connection = self._pool.connection() # 从池中获取连接
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

    def _convert_named_params(self, query: str, params: Optional[Dict[str, Any]]) -> Tuple[str, Tuple]:
        """
        将命名参数 (:param) 转换为位置参数 (%s)，并准备参数元组。
        *** 防注入关键步骤 1：将用户输入与 SQL 结构分离 ***
        """
        if not params:
            return query, ()

        processed_query = query
        param_values = []
        # 替换所有出现的 :param 占位符为 %s
        for key, value in params.items():
            placeholder = f":{key}"
            processed_query = processed_query.replace(placeholder, "%s")
            param_values.append(value) # *** 防注入关键步骤 2：收集原始参数值 ***
            
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

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行 SELECT 查询，返回所有结果"""
        processed_query, processed_params = self._convert_named_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='all')

    def execute_single_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """执行 SELECT 查询，返回单个结果"""
        processed_query, processed_params = self._convert_named_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='one')

    def execute_update(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """执行 INSERT/UPDATE/DELETE，返回影响行数"""
        processed_query, processed_params = self._convert_named_params(query, params)
        return self._execute_core(processed_query, processed_params, fetch='rowcount')

    def execute_batch_update(self, query: str, params_list: List[Dict[str, Any]]) -> int:
        """执行批处理更新"""
        if not self.connection or not params_list:
            return 0

        # 转换第一个参数字典以获取查询结构
        processed_query, _ = self._convert_named_params(query, params_list[0])
        
        # 准备所有参数元组列表
        processed_params_list = [
            self._convert_named_params(query, params)[1] for params in params_list
        ]

        with self.connection.cursor() as cursor:
            # *** 防注入：executemany 同样安全处理参数 ***
            return cursor.executemany(processed_query, processed_params_list)

    def execute_paged_query(
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
        count_result = self.execute_single_query(count_query, params)
        total_count = count_result['total'] if count_result else 0

        # 2. 执行分页查询
        # *** 防注入关键：将 LIMIT 和 OFFSET 也作为参数处理 ***
        if not self.connection:
            raise RuntimeError("数据库连接未获取")

        # 转换主查询的命名参数
        base_query, base_params_tuple = self._convert_named_params(query, params)
        
        # 将 LIMIT 和 OFFSET 附加到参数元组末尾
        # *** 防注入：确保 offset 和 limit 是整数 ***
        paged_query = f"{base_query} LIMIT %s OFFSET %s"
        paged_params = base_params_tuple + (int(limit), int(offset)) # 强制转换为 int

        with self.connection.cursor() as cursor:
            # *** 防注入核心：所有参数（包括 limit/offset）都通过 execute 传递 ***
            cursor.execute(paged_query, paged_params)
            results = cursor.fetchall()
            
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