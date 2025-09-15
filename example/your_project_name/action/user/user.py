# action/user/user.py
# 导入自定义异常
from KairoCore import kcRouter, kQuery

# 创建一个 APIRouter 实例
# tags 用于 API 文档分组
router = kcRouter(tags=["用户管理"])

@router.get("/info")
async def get_user_info():
    """获取用户信息"""
    async with AsyncMysqlSession() as session:
        users = await session.fetch_all(
            "SELECT * FROM user_info WHERE name = :name OR phone = :phone", 
            {'phone': 18, 'name': "zz"} # 安全处理
        )
    return kQuery.to_response(users, 0)


