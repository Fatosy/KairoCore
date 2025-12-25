# action/user/user.py
# 导入自定义异常
from KairoCore import kcRouter, kQuery
from domain.user import UserDomian
from schema.user import (
    UserAddtorList,
    UserUpdatorList,
    UserDeletor,
    UserQuery,
    UserQueryBody,
    UserInfoOptionsGettor
)

# 禁用路由
ENABLE_ROUTER = False

# 创建一个 APIRouter 实例
# tags 用于 API 文档分组
router = kcRouter(tags=["用户管理"])

# 新增接口用post方法
@router.post("/add")
async def add(body: UserAddtorList):
    """添加用户"""
    affect_rows = await UserDomian.add(body)
    return kQuery.to_response(msg="添加成功", total=affect_rows)

# 更新接口用put方法
@router.put("/update")
async def update(body: UserUpdatorList):
    """更新用户信息"""
    affect_rows = await UserDomian.update(body)
    return kQuery.to_response(msg="更新成功", total=affect_rows)

# 删除接口用delete方法
@router.delete("/delete")
async def delete(body: UserDeletor):
    """删除用户"""
    affect_rows = await UserDomian.delete(body)
    return kQuery.to_response(msg="删除成功", total=affect_rows)

# 查询接口用post方法，
@router.post("/query")
async def query(query: UserQuery, body: UserQueryBody):
    """
    获取用户信息

        - query: 代表通过查询参数传递的数据，通常用于 URL 查询字符串中的参数，以 ?key=value&key2=value2 的形式附加在 URL 后面
        - body: 代表通过请求体传递的数据，通常用于 POST 请求的 JSON 数据
    """
    rows, total = await UserDomian.query(query, body)
    return kQuery.to_response(rows, total, query.limit, query.offset, '查询成功')

# Options这类接口用get方法
@router.get("/info/options")
async def query_info_options(query: UserInfoOptionsGettor):
    """获取用户信息options"""
    rows, total = await UserDomian.query_info_options(query)
    return kQuery.to_response(rows, total, msg="查询成功")

