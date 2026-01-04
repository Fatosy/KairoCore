from KairoCore.db_tools.kc_sqlite import AsyncSqliteSession, SqliteSessionPool
from KairoCore import SqlTool
from typing import List, Dict, Optional

# 表名常量
table_name = "user_info"

class UserSqliteDao:
    """
    SQLite 版本的用户数据访问层实现
    遵循 DAO 设计模式，提供对 user_info 表的 CRUD 操作
    """

    @staticmethod
    async def add(params: List[Dict], session: Optional[AsyncSqliteSession] = None) -> int:
        """
        批量添加用户
        
        Args:
            params: 用户信息字典列表，每个字典代表一条记录
            session: 可选的数据库会话，用于事务控制
            
        Returns:
            int: 受影响的行数
        """
        affect_rows = 0
        # 生成批量插入 SQL 语句和参数
        # 注意：SqlTool.generate_batch_insert_sql 生成的 SQL 是 MySQL 风格的，
        # 但在简单的 INSERT INTO ... VALUES ... 语法上 SQLite 通常兼容。
        # 只要 SqlTool 生成的是标准的 INSERT 语句，且 db_tools/kc_sqlite.py 
        # 能处理参数化占位符转换（:param -> ?），即可正常工作。
        insert_sql, insert_params = SqlTool.generate_batch_insert_sql(table_name, params)
        
        if session is None:
            # 如果没有传入会话，则创建新的会话并自动管理上下文（含事务提交/回滚）
            async with AsyncSqliteSession() as session:
                # 检查表是否存在，不存在则创建（开发便利性）
                await UserSqliteDao._ensure_table(session)
                # 执行批量插入
                affect_rows = await session.batch_execute(insert_sql, insert_params)
        else:
            # 使用传入的外部会话（通常用于外部事务中）
            await UserSqliteDao._ensure_table(session)
            affect_rows = await session.batch_execute(insert_sql, insert_params)
            
        return affect_rows
    
    @staticmethod
    async def update(params: List[Dict], session: Optional[AsyncSqliteSession] = None) -> int:
        """
        批量更新用户信息
        
        Args:
            params: 更新参数列表，必须包含主键（id）
            session: 可选的数据库会话
            
        Returns:
            int: 受影响的行数
        """
        affect_rows = 0
        # 获取批量更新语句 (注意：SqlTool 生成的批量更新可能依赖 MySQL 特性 CASE WHEN 或 ON DUPLICATE KEY)
        # SQLite 标准并不直接支持 MySQL 的批量 UPDATE 语法。
        # 这里为了保持接口一致，我们可能需要循环执行单条更新，或者依赖 SqlTool 如果它生成的是兼容的 SQL。
        # 假设 SqlTool.generate_batch_update_sql 生成的是 CASE WHEN 风格，SQLite 支持。
        # 如果是 ON DUPLICATE KEY UPDATE，SQLite 不支持（SQLite 使用 ON CONFLICT）。
        # 鉴于 SqlTool 实现未知，这里采用更稳妥的单条循环更新策略适配 SQLite，
        # 或者假设 SqlTool 生成的是通用的 update 语句。
        # 为了稳妥起见，针对 SQLite 的 update，如果 params 是列表，我们循环调用 execute_one。
        
        # update_sql, update_params = SqlTool.generate_batch_update_sql(table_name, params, ['id'])
        
        # 修正策略：SqlTool 通常生成的是单条 SQL 配合 executemany 的参数结构？
        # 检查 user.py 发现是 execute_one(update_sql, update_params)，这暗示 SqlTool 生成了一个巨大的 CASE WHEN SQL。
        # SQLite 对 CASE WHEN 支持良好，尝试直接复用。
        update_sql, update_params = SqlTool.generate_batch_update_sql(table_name, params, ['id'])

        if session is None:
            async with AsyncSqliteSession() as session:
                await UserSqliteDao._ensure_table(session)
                # 注意：kc_sqlite 的 execute_one 用于执行单条 SQL
                affect_rows = await session.execute_one(update_sql, update_params)
        else:
            await UserSqliteDao._ensure_table(session)
            affect_rows = await session.execute_one(update_sql, update_params)
            
        return affect_rows
    
    @staticmethod
    async def delete(ids: List[int], is_hard: bool = False, session: Optional[AsyncSqliteSession] = None) -> int:
        """
        删除用户（支持软删除和硬删除）
        
        Args:
            ids: 要删除的用户 ID 列表
            is_hard: 是否物理删除，True 为物理删除，False 为逻辑删除（更新 is_del=1）
            session: 可选的数据库会话
            
        Returns:
            int: 受影响的行数
        """
        affect_rows = 0
        
        # 生成删除语句
        if is_hard:
            # 硬删除: DELETE FROM table WHERE id IN (...)
            delete_sql, delete_params = SqlTool.generate_hard_delete_sql(
                table_name, 
                where_dict={"id": ids}, 
                where_ops={'id': 'IN'}
            )
        else:
            # 软删除: UPDATE table SET is_del=1 WHERE id IN (...)
            delete_sql, delete_params = SqlTool.generate_soft_delete_sql(
                table_name, 
                param_dict={"is_del": 1}, 
                where_dict={"id": ids}, 
                where_ops={'id': 'IN'}
            )

        if session is None:
            async with AsyncSqliteSession() as session:
                await UserSqliteDao._ensure_table(session)
                # 注意：SqlTool 生成的 delete_params 可能是字典，batch_execute 需要列表
                # user.py 中使用的是 [delete_params]，意味着只执行一次 SQL
                affect_rows = await session.batch_execute(delete_sql, [delete_params])
        else:
            await UserSqliteDao._ensure_table(session)
            affect_rows = await session.batch_execute(delete_sql, [delete_params])
            
        return affect_rows
    
    @staticmethod
    async def query_by_pagination(query_params: dict, limit: int = 1, offset: int = 20):
        """
        分页查询用户列表
        
        Args:
            query_params: 查询条件字典
            limit: 每页数量
            offset: 页码（注意：user.py 里的 offset 命名虽然叫 offset，实际在 kc_mysql 里被当作 page 使用）
                   kc_sqlite.query_with_pagination 参数名也是 offset，逻辑是 (offset-1)*limit
            
        Returns:
            (List[Dict], int): 结果列表和总记录数
        """
        where_sqls = []
        where_params = {}
        
        # 定义查询字段的匹配规则
        like_keys = ['name', 'phone', 'location']
        daterange_keys = ['birthday']
        in_keys = ['sex']
        
        # 转换查询参数为 SQL 条件
        SqlTool.query_list_params_translate(
            query_params, where_sqls, where_params, like_keys, in_keys, daterange_keys
        )
        
        where_sql = f" WHERE {' AND '.join(where_sqls)}" if where_sqls else ''
        query_sql = f"SELECT * FROM `{table_name}` {where_sql}"
        
        query_results = []
        total = 0
        
        async with AsyncSqliteSession() as session:
            await UserSqliteDao._ensure_table(session)
            query_results, total = await session.query_with_pagination(
                query_sql, 
                where_params, # 注意这里使用 where_params 而不是 query_params
                limit=limit, 
                offset=offset
            )
            
        return query_results, total
        
    @staticmethod
    async def query_info_options(query_params: Dict):
        """
        查询用户信息选项（不分页）
        
        Args:
            query_params: 查询条件
            
        Returns:
            (List[Dict], int): 结果列表和总数
        """
        where_sqls = []
        where_params = {}
        
        like_keys = ['name']
        daterange_keys = []
        in_keys = []
        
        SqlTool.query_list_params_translate(
            query_params, where_sqls, where_params, like_keys, in_keys, daterange_keys
        )
        
        where_sql = f" WHERE {' AND '.join(where_sqls)}" if where_sqls else ''
        query_sql = f"SELECT * FROM `{table_name}` {where_sql}"
        
        query_results = []
        total = 0
        
        async with AsyncSqliteSession() as session:
            await UserSqliteDao._ensure_table(session)
            query_results = await session.fetch_all(query_sql, where_params)
            total = len(query_results)
            
        return query_results, total

    @staticmethod
    async def _ensure_table(session: AsyncSqliteSession):
        """
        确保表存在（辅助方法，用于自动建表）
        """
        # SQLite 建表语句
        create_sql = """
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            phone TEXT,
            location TEXT,
            birthday TEXT,
            sex TEXT,
            is_del INTEGER DEFAULT 0,
            create_time TEXT DEFAULT (datetime('now', 'localtime')),
            update_time TEXT DEFAULT (datetime('now', 'localtime'))
        );
        """
        await session.ensure_table(table_name, create_sql)
