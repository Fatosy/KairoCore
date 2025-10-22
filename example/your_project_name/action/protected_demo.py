"""
受保护接口示例：演示普通接口如何带上 token 校验进行请求

- 基础校验：只要求 access token（/ping）
- 多租户校验：要求 access token + 租户 tid（/tenant/ping）
- 角色校验：要求 access token + 具备 admin 角色（/admin/ping）
- 仅限 API_KEY：无需登录，持有永久有效 API_KEY 即可（/api-key/ping）

调用方式：
- 使用 Authorization 头：Authorization: Bearer <access_token>
- 或在浏览器场景使用 HttpOnly Cookie：access_token=<access_token>
- 使用 X-API-Key 头或查询参数 api_key=<key>

完整路径前缀（默认）：/example/api/protected_demo/*
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends

from KairoCore import kcRouter, kQuery, KairoAuth

# 文档分组到 "Token校验示例"
router = kcRouter(tags=["Token校验示例"]) 

# 1) 仅要求 access token
base_router = APIRouter(dependencies=[Depends(KairoAuth.require_access_token)])

@base_router.get("/ping")
async def ping() -> Dict[str, Any]:
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={
            "message": "pong",
            "user_id": principal.get("sub"),
            "roles": principal.get("roles") or [],
        },
        msg="ok",
    )

# 2) 要求存在租户 tid
tenant_router = APIRouter(dependencies=[Depends(KairoAuth.require_access_token), Depends(KairoAuth.require_tenant)])

@tenant_router.get("/tenant/ping")
async def tenant_ping() -> Dict[str, Any]:
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={
            "message": "pong-tenant",
            "tenant_id": principal.get("tid"),
        },
        msg="ok",
    )

# 3) 要求具有 admin 角色
admin_router = APIRouter(dependencies=[Depends(KairoAuth.require_access_token), Depends(KairoAuth.require_roles(["admin"]))])

@admin_router.get("/admin/ping")
async def admin_ping() -> Dict[str, Any]:
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={
            "message": "pong-admin",
            "roles": principal.get("roles") or [],
        },
        msg="ok",
    )

# 4) 仅限 API_KEY，无需 access token
api_key_router = APIRouter(dependencies=[Depends(KairoAuth.require_api_key)])

@api_key_router.get("/api-key/ping")
async def api_key_ping() -> Dict[str, Any]:
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={
            "message": "pong-api-key",
            "principal": principal,  # 对于 API_KEY 认证，principal 可能为 {"api_key": "...", "type": "api_key"}
        },
        msg="ok",
    )

# 将子路由挂载到主路由（最终路径会是 /example/api/protected_demo/...）
router.include_router(base_router, prefix="")
router.include_router(tenant_router, prefix="")
router.include_router(admin_router, prefix="")
router.include_router(api_key_router, prefix="")