from KairoCore import AsyncMysqlSession
from KairoCore import SqlTool
from typing import List, Dict, Optional

table_name = "user_info"

class UserDao:

    @staticmethod
    async def add(params: List[Dict], session: AsyncMysqlSession = None):
        """
            添加用户  
        """
        affect_rows = 0
        # 获取插入语句
        insert_sql, insert_params = SqlTool.generate_batch_insert_sql(table_name, params)
        if session is None:
            async with AsyncMysqlSession() as session:
                affect_rows = await session.batch_execute(insert_sql, insert_params)
        else:
            affect_rows = await session.batch_execute(insert_sql, insert_params)
        return affect_rows
    
    @staticmethod
    async def update(params: List[Dict], session: AsyncMysqlSession = None):
        """
            更新用户
        """
        affect_rows = 0
        # 获取更新语句
        update_sql, update_params = SqlTool.generate_batch_update_sql(table_name, params, ['id'])
        if session is None:
            async with AsyncMysqlSession() as session:
                affect_rows = await session.execute_one(update_sql, update_params)
        else:
            affect_rows = await session.execute_one(update_sql, update_params)
        return affect_rows
    
    @staticmethod
    async def delete(ids: List[int], is_hard: bool = False, session: Optional[AsyncMysqlSession] = None) -> int:
        """
            删除用户
        """
        affect_rows = 0
        delete_sql, delete_params = SqlTool.generate_hard_delete_sql(table_name, where_dict={"id": ids}, where_ops = {'id': 'IN'}) if is_hard else \
            SqlTool.generate_soft_delete_sql(table_name, param_dict={"is_del": 1}, where_dict={"id": ids}, where_ops = {'id': 'IN'})
        if session is None:
            async with AsyncMysqlSession() as session:
                affect_rows = await session.batch_execute(delete_sql, [delete_params])
        else:
            affect_rows = await session.batch_execute(delete_sql, [delete_params])
        return affect_rows
    
    @staticmethod
    async def query_by_pagination(query_params: dict, limit:int=1, offset:int=20):
        """
            分页查询
        """
        where_sqls = []
        where_params = {}
        like_keys = ['name', 'phone', 'location']
        daterange_keys = ['birthday']
        in_keys = ['sex']
        SqlTool.query_list_params_translate(query_params, where_sqls, where_params, like_keys, in_keys, daterange_keys)
        where_sql = f""" WHERE {' AND '.join(where_sqls)}""" if where_sqls else ''
        query_sql = f"""SELECT * FROM `{table_name}` {where_sql}"""
        query_results = []
        total = 0
        async with AsyncMysqlSession() as session:
            query_results, total = await session.query_with_pagination(query_sql, query_params, limit=limit, offset=offset)
        return query_results, total
        
    @staticmethod
    async def query_info_options(query_params: Dict):
        """
            查询用户信息options
        """
        where_sqls = []
        where_params = {}
        like_keys = ['name']
        daterange_keys = []
        in_keys = []
        SqlTool.query_list_params_translate(query_params, where_sqls, where_params, like_keys, in_keys, daterange_keys)
        where_sql = f""" WHERE {' AND '.join(where_sqls)}""" if where_sqls else ''
        query_sql = f"""SELECT * FROM `{table_name}` {where_sql}"""
        query_results = []
        total = 0
        async with AsyncMysqlSession() as session:
            query_results = await session.fetch_all(query_sql, query_params)
            total = len(query_results)
        return query_results, total
