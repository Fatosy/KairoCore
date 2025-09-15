from KairoCore import AsyncMysqlSession
from KairoCore import SqlTool
from typing import List, Dict

TableName = "user_info"

class UserDao:

    @staticmethod
    async def add(user: List[Dict], session: AsyncMysqlSession = None):
        """
            添加用户  
        """
        # 获取插入语句
        insert_sql, insert_params = SqlTool.generate_batch_insert_sql(TableName, user)
        if session is None:
            async with AsyncMysqlSession() as session:
                await session.batch_execute(insert_sql, insert_params)
        else:
            await session.batch_execute(insert_sql, insert_params)
    
    @staticmethod
    async def update(user: Dict, session: AsyncMysqlSession = None):
        """
            更新用户
        """
        # 获取更新语句
        update_sql, update_params, where_params = SqlTool.generate_update_sql(TableName, user, {"id": user["id"]})
        all_params = {**update_params, **where_params}
        if session is None:
            async with AsyncMysqlSession() as session:
                await session.execute_one(update_sql, all_params)
        else:
            await session.execute_one(update_sql, all_params)