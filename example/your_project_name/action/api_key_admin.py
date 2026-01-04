from typing import Any, Dict
import os
from fastapi import APIRouter, Depends

from KairoCore import kcRouter, kQuery, KairoAuth

# 文档分组到 "API_KEY管理"，路径前缀将由自动注册逻辑决定（通常为 /example/api/api_key_admin/*）
router = kcRouter(tags=["API_KEY管理"])

# 访问控制策略：
# - 若 KC_ENABLE_API_KEY_ADMIN=true 且 KC_ENV=development，则允许免登录访问管理端点（用于本地开发）
# - 否则（生产模式或未开启开关），要求 admin 角色 + access_token
ENABLE_ADMIN = os.getenv("KC_ENABLE_API_KEY_ADMIN", "false").lower() == "true"
ENV = os.getenv("KC_ENV", "development")

if ENABLE_ADMIN and ENV == "development":
    dependencies = []  # 开发环境免登录
else:
    dependencies = [Depends(KairoAuth.require_access_token), Depends(KairoAuth.require_roles(["admin"]))]

admin_router = APIRouter(dependencies=dependencies)

@admin_router.get("/api-key")
async def get_api_key() -> Dict[str, Any]:
    """查看当前 API_KEY（如果存在）。生产环境请谨慎暴露。"""
    key = KairoAuth.get_api_key()
    return kQuery.to_response(data={"api_key": key}, msg="ok")

@admin_router.post("/api-key/generate")
async def generate_api_key() -> Dict[str, Any]:
    """生成新的 API_KEY 并保存（覆盖旧值）。"""
    key = KairoAuth.generate_api_key()
    return kQuery.to_response(data={"api_key": key}, msg="generated")

@admin_router.delete("/api-key")
async def delete_api_key() -> Dict[str, Any]:
    """删除已存在的 API_KEY。"""
    KairoAuth.delete_api_key()
    return kQuery.to_response(data={"deleted": True}, msg="deleted")

# 将子路由挂载到主路由
router.include_router(admin_router, prefix="")