# action/user/user.py
# 导入自定义异常
from fastapi import APIRouter as zRouter
from utils.panic import QueryResponse


# 必须创建一个 APIRouter 实例，变量名必须为 'router'
router = zRouter(tags=["用户管理"]) # tags 用于 API 文档分组

# --- 定义路由处理函数 ---
# 注意：函数签名必须遵循规范，只使用 'query' 和 'body' 作为参数名，
# 且它们必须是 Pydantic BaseModel 或 None。

@router.get("/info")
async def get_user_info():
    """获取用户信息"""
    rs = QueryResponse()
    return rs.to_response([], 0)


