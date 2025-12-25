import os
from typing import Dict, List
from jinja2 import Template

class CodeGenerator:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.templates = {
            'action': self._get_action_template(),
            'schema': self._get_schema_template(),
            'domain': self._get_domain_template(),
            'dao': self._get_dao_template()
        }
    
    def _get_action_template(self) -> str:
        return '''# action/{{route_name}}/{{route_name}}.py
# 导入自定义异常
from KairoCore import kcRouter, kQuery
from domain.{{route_name}} import {{RouteName}}Domain
from schema.{{route_name}} import (
    {{RouteName}}AddtorList,
    {{RouteName}}UpdatorList,
    {{RouteName}}Deletor,
    {{RouteName}}Query,
    {{RouteName}}QueryBody,
    {{RouteName}}InfoOptionsGettor
)

ENABLE_ROUTER = True

# 创建一个 APIRouter 实例
# tags 用于 API 文档分组
router = kcRouter(tags=["{{route_name_cn}}管理"])

# 新增接口用post方法
@router.post("/add")
async def add(body: {{RouteName}}AddtorList):
    """添加{{route_name_cn}}"""
    affect_rows = await {{RouteName}}Domain.add(body)
    return kQuery.to_response(msg="添加成功", total=affect_rows)

# 更新接口用put方法
@router.put("/update")
async def update(body: {{RouteName}}UpdatorList):
    """更新{{route_name_cn}}信息"""
    affect_rows = await {{RouteName}}Domain.update(body)
    return kQuery.to_response(msg="更新成功", total=affect_rows)

# 删除接口用delete方法
@router.delete("/delete")
async def delete(body: {{RouteName}}Deletor):
    """删除{{route_name_cn}}"""
    affect_rows = await {{RouteName}}Domain.delete(body)
    return kQuery.to_response(msg="删除成功", total=affect_rows)

# 查询接口用post方法
@router.post("/query")
async def query(query: {{RouteName}}Query, body: {{RouteName}}QueryBody):
    """
    获取{{route_name_cn}}信息

        - query: 代表通过查询参数传递的数据，通常用于 URL 查询字符串中的参数，以 ?key=value&key2=value2 的形式附加在 URL 后面
        - body: 代表通过请求体传递的数据，通常用于 POST 请求的 JSON 数据
    """
    rows, total = await {{RouteName}}Domain.query(query, body)
    return kQuery.to_response(rows, total, query.limit, query.offset, '查询成功')

# Options这类接口用get方法
@router.get("/info/options")
async def query_info_options(query: {{RouteName}}InfoOptionsGettor):
    """获取{{route_name_cn}}信息options"""
    rows, total = await {{RouteName}}Domian.query_info_options(query)
    return kQuery.to_response(rows, total, msg="查询成功")

'''

    def _get_schema_template(self) -> str:
        return '''# schema/{{route_name}}/{{route_name}}.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from KairoCore import KcReTool, Ktimer
from enum import IntEnum, Enum

from common.errors import (
    SCM_XXX_PARAM_VALIDATE_ERROR
)


# 性别
class Sex(str, Enum):
    MAN = "man"
    WOMAN = "woman"


# 会员
class Vip(IntEnum):
    YES = 1
    NO = 0



# 添加参数
class {{RouteName}}Addor(BaseModel):
    name: str = Field(description="用户名")
    phone: str = Field(description="手机号")
    location: Optional[str] = Field(default=None, description="地址， 非必填")
    birthday: Optional[str] = Field(default=None, description="生日， 非必填")
    sex: Optional[Sex] = Field(default=Sex.MAN, description="性别, 默认男，非必填")
    is_vip: Optional[Vip] = Field(default=Vip.NO, description="是否是会员，默认非会员，非必填")

    @field_validator('birthday')
    def validate_date_format(cls, v):
        if v is not None:
            if not KcReTool.validate_date_format(v):
                raise SCM_XXX_PARAM_VALIDATE_ERROR.msg_format("时间参数格式错误，请检查！")
            Ktimer.validate_date_format(v)
        return v

class {{RouteName}}AddtorList(BaseModel):
    items: List[{{RouteName}}Addor]

# 更新参数
class {{RouteName}}Updator({{RouteName}}Addor):
    id: int


class {{RouteName}}UpdatorList(BaseModel):
    items: List[{{RouteName}}Updator]

# 删除参数
class {{RouteName}}Deletor(BaseModel):
    ids: List[int]

# 查询参数
class {{RouteName}}Query(BaseQuery):
    limit: Optional[int] = Field(default=20, description="查询数量")
    offset: Optional[int] = Field(default=1, description="页码")

# 查询请求体
class {{RouteName}}QueryBody(BaseQueryBody):
    name: Optional[str] = Field(default=None, description="用户名")
    phone: Optional[str] = Field(default=None, description="手机号")
    sex: Optional[Sex] = Field(default=None, description="性别")
    is_vip: Optional[Vip] = Field(default=None, description="是否是会员，默认非会员，非必填")
    location: Optional[str] = Field(default=None, description="地址")
    birthday_start: Optional[str] = Field(default=None, description="生日起始")
    birthday_end: Optional[str] = Field(default=None, description="生日结束")

    @field_validator('birthday_start', 'birthday_end')
    def validate_date_format(cls, v):
        if v is not None:
            if not KcReTool.validate_date_format(v):
                raise SCM_XXX_PARAM_VALIDATE_ERROR.msg_format("时间参数格式错误，请检查！")
            Ktimer.validate_date_format(v)
        return v

# options
class UserInfoOptionsGettor(BaseModel):
    name: Optional[str] = Field(None, description="用户名称")

'''

    def _get_domain_template(self) -> str:
        return '''# domain/{{route_name}}/{{route_name}}.py
from typing import List, Dict
from dao.{{route_name}} import {{RouteName}}Dao
from common.consts import (
    IS_DEL_MAP
)
from schema.{{route_name}} import (
    {{RouteName}}AddtorList,
    {{RouteName}}UpdatorList,
    {{RouteName}}Deletor,
    {{RouteName}}Query,
    {{RouteName}}QueryBody
    {{RouteName}}InfoOptionsGettor
)

class {{RouteName}}Domain:

    @staticmethod
    async def query(query: {{RouteName}}Query, body: {{RouteName}}QueryBody):
        rows = []
        total = 0
        query_params = {
            "name": body.name,
            "phone": body.phone,
            "sex": [body.sex.value] if body.sex else None,
            "location": body.location,
            "birthday": [ body.birthday_start, body.birthday_end ] if body.birthday_start or body.birthday_end else None
        }
        rows, total = await {{RouteName}}Dao.query_by_pagination(query_params, query.limit, query.offset)
        {{RouteName}}DomainTool.translate_query_rows(rows)
        return rows, total
    
    @staticmethod
    async def add(body: {{RouteName}}AddtorList):
        add_params = [{
            "name": item.name,
            "phone": item.phone
        } for item in body.items]
        affect_rows = await {{RouteName}}Dao.add(add_params)
        return affect_rows

    @staticmethod
    async def update(body: {{RouteName}}UpdatorList):
        update_params = [{
            "id": item.id,
            "name": item.name,
            "phone": item.phone
        } for item in body.items]
        affect_rows = await {{RouteName}}Dao.update(update_params)
        return affect_rows
    
    @staticmethod
    async def delete(body: {{RouteName}}Deletor):
        affect_rows = await {{RouteName}}Dao.delete(body.ids, is_hard=True)
        return affect_rows

    @staticmethod
    async def query_info_options(query: {{RouteName}}InfoOptionsGettor):
        query_params = {
            "name": query.name
        }
        rows, total = await {{RouteName}}Dao.query_info_options(query_params)
        options = await {{RouteName}}DomainTool.translate_info_options(rows)
        return options, total

class {{RouteName}}DomainTool:

    @staticmethod
    async def translate_query_rows(query_rows: List[Dict]):
        """
            翻译查询结果
        """
        for row in query_rows:
            row['is_del_label'] = IS_DEL_MAP.get(row.get('is_del', 0), '未知')

    @staticmethod
    async def translate_info_options(query_rows: List[Dict]) -> List[Dict]:
        """
            获取options
        """
        return [{
            "label": row['name'], 
            "value": row['id']
        } for row in query_rows]

'''

    def _get_dao_template(self) -> str:
        return '''# dao/{{route_name}}/{{route_name}}.py
from KairoCore import AsyncMysqlSession
from KairoCore import SqlTool
from typing import List, Dict, Optional

table_name = "{{table_name}}"

class {{RouteName}}Dao:

    @staticmethod
    async def add(params: List[Dict], session: AsyncMysqlSession = None):
        """
            添加{{route_name_cn}}  
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
            更新{{route_name_cn}}
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
            删除{{route_name_cn}}
        """
        affect_rows = 0
        delete_sql, delete_params = SqlTool.generate_hard_delete_sql(table_name, where_dict={"id": ids}) if is_hard else \\
            SqlTool.generate_soft_delete_sql(table_name, param_dict={"is_del": 1}, where_dict={"id": ids})
        if session is None:
            async with AsyncMysqlSession() as session:
                affect_rows = await session.execute_one(delete_sql, delete_params)
        else:
            affect_rows = await session.execute_one(delete_sql, delete_params)
        return affect_rows
    
    @staticmethod
    async def query_by_pagination(query_params: dict, limit: int = 20, offset: int = 0):
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
            查询{{route_name_cn}}信息options
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

        
'''

    def generate_code_blocks(self, route_name: str, route_name_cn: str = None, table_name: str = None) -> Dict[str, str]:
        """
        生成路由对应的代码块
        
        Args:
            route_name: 路由名称（英文）
            route_name_cn: 路由中文名称
            table_name: 数据库表名
        """
        route_name_cn = route_name_cn or route_name
        table_name = table_name or f"{route_name}_info"
        
        code_blocks = {}
        
        # 生成各个模块的代码
        code_blocks[f"action/{route_name}/{route_name}.py"] = self._generate_action_code(route_name, route_name_cn)
        code_blocks[f"schema/{route_name}/{route_name}.py"] = self._generate_schema_code(route_name, route_name_cn)
        code_blocks[f"domain/{route_name}/{route_name}.py"] = self._generate_domain_code(route_name, route_name_cn)
        code_blocks[f"dao/{route_name}/{route_name}.py"] = self._generate_dao_code(route_name, route_name_cn, table_name)
        
        return code_blocks

    def _generate_action_code(self, route_name: str, route_name_cn: str) -> str:
        template = Template(self.templates['action'])
        return template.render(
            route_name=route_name,
            RouteName=route_name.capitalize(),
            route_name_cn=route_name_cn
        )

    def _generate_schema_code(self, route_name: str, route_name_cn: str) -> str:
        template = Template(self.templates['schema'])
        return template.render(
            route_name=route_name,
            RouteName=route_name.capitalize()
        )

    def _generate_domain_code(self, route_name: str, route_name_cn: str) -> str:
        template = Template(self.templates['domain'])
        return template.render(
            route_name=route_name,
            RouteName=route_name.capitalize()
        )
    
    def _generate_dao_code(self, route_name: str, route_name_cn: str, table_name: str) -> str:
        template = Template(self.templates['dao'])
        return template.render(
            route_name=route_name,
            RouteName=route_name.capitalize(),
            route_name_cn = route_name_cn,
            table_name = table_name
        )
