from typing import List, Dict, Optional
from dao.user import UserDao
from common.consts import (
    IS_DEL_MAP
)
from schema.user import (
    UserAddtorList,
    UserUpdatorList,
    UserDeletor,
    UserQuery,
    UserQueryBody,
    UserInfoOptionsGettor
)



class UserDomian:

    @staticmethod
    async def query(query: UserQuery, body: UserQueryBody):
        rows = []
        total = 0
        query_params = {
            "name": body.name,
            "phone": body.phone,
            "sex": [body.sex.value] if body.sex else None,
            "location": body.location,
            "birthday": [ body.birthday_start, body.birthday_end ] if body.birthday_start or body.birthday_end else None
        }
        rows, total = await UserDao.query_by_pagination(query_params, query.limit, query.offset)
        UserDomainTool.translate_query_rows(rows)
        return rows, total
    
    @staticmethod
    async def add(body: UserAddtorList):
        add_params = [{
            "name": item.name,
            "phone": item.phone
        } for item in body.items]
        affect_rows = await UserDao.add(add_params)
        return affect_rows

    @staticmethod
    async def update(body: UserUpdatorList):
        update_params = [{
            "id": item.id,
            "name": item.name,
            "phone": item.phone
        } for item in body.items]
        affect_rows = await UserDao.update(update_params)
        return affect_rows
    
    @staticmethod
    async def delete(body: UserDeletor):
        affect_rows = await UserDao.delete(body.ids, is_hard=True)
        return affect_rows
    
    @staticmethod
    async def query_info_options(query: UserInfoOptionsGettor):
        query_params = {
            "name": query.name
        }
        rows, total = await UserDao.query_info_options(query_params)
        options = await UserDomainTool.translate_info_options(rows)
        return options, total

    

class UserDomainTool:

    @staticmethod
    async def translate_query_rows(query_rows: List[Dict]):
        """
            翻译查询结果
        """
        for row in query_rows:
            row['is_del_label'] = IS_DEL_MAP[row['is_del']]
    
    @staticmethod
    async def translate_info_options(query_rows: List[Dict]) -> List[Dict]:
        """
            获取options
        """
        return [{
            "label": row['name'], 
            "value": row['id']
        } for row in query_rows]

    