from fastapi import APIRouter, Depends
from typing import Any, Dict

from ...schema.auth import LoginBody, RefreshBody, LogoutBody
from KairoCore import exec_with_route_error, kcRouter, kQuery, KairoAuth
from KairoCore.common.errors import (
    KCAUTH_LOGIN_FAILED,
    KCAUTH_REFRESH_INVALID,
)

router = kcRouter(tags=["认证"])

@router.get("/login_public_key")
async def login_public_key() -> Dict[str, Any]:
    """返回用于前端加密登录密码的 RSA 公钥（如已配置）。"""
    pem = KairoAuth.get_rsa_public_key_pem()
    if not pem:
        return kQuery.to_response(data=None, msg="RSA 未配置")
    return kQuery.to_response(data={"public_key_pem": pem}, msg="ok")

@router.post("/login")
async def login(body: LoginBody) -> Dict[str, Any]:
    async def _do():
        # 解密加密上传的密码（如启用 RSA 或以前缀标识）。未配置则原样返回。
        decrypted_password = KairoAuth.decrypt_password_if_encrypted(body.password)

        # 演示用途：这里应替换为真实的用户校验与租户/角色加载
        if not body.username or not decrypted_password:
            raise KCAUTH_LOGIN_FAILED

        roles = body.roles or ["user"]
        access_token, access_exp = KairoAuth.issue_access_token(
            user_id=body.username, tenant_id=body.tenant_id, roles=roles
        )
        refresh_token, jti, refresh_exp = KairoAuth.issue_refresh_token(
            user_id=body.username, tenant_id=body.tenant_id
        )
        return {
            "access_token": access_token,
            "access_expires_at": access_exp,
            "refresh_token": refresh_token,
            "refresh_expires_at": refresh_exp,
            "jti": jti,
            "token_type": "Bearer",
        }
    return await exec_with_route_error(_do(), KCAUTH_LOGIN_FAILED)


@router.post("/refresh")
async def refresh(body: RefreshBody) -> Dict[str, Any]:
    async def _do():
        payload = KairoAuth.verify_refresh_token(body.refresh_token)
        old_jti = payload.get("jti")
        user_id = payload.get("sub")
        tenant_id = payload.get("tid")
        if not old_jti or not user_id:
            raise KCAUTH_REFRESH_INVALID
        # 轮换 refresh，重新签发 access
        new_refresh_token, new_jti, refresh_exp = KairoAuth.rotate_refresh_token(old_jti, user_id, tenant_id)
        roles = payload.get("roles") or ["user"]  # 如需在 refresh 中携带角色，可在登录时回填
        access_token, access_exp = KairoAuth.issue_access_token(user_id=user_id, tenant_id=tenant_id, roles=roles)
        return {
            "access_token": access_token,
            "access_expires_at": access_exp,
            "refresh_token": new_refresh_token,
            "refresh_expires_at": refresh_exp,
            "jti": new_jti,
            "token_type": "Bearer",
        }
    return await exec_with_route_error(_do(), KCAUTH_REFRESH_INVALID)


@router.post("/logout")
async def logout(body: LogoutBody) -> Dict[str, Any]:
    async def _do():
        payload = KairoAuth.verify_refresh_token(body.refresh_token)
        # 撤销当前 refresh token（登出）
        jti = payload.get("jti")
        if jti:
            KairoAuth.revoke_refresh_token(jti)
        return {"ok": True}
    return await exec_with_route_error(_do(), KCAUTH_REFRESH_INVALID)


# 保护接口：需要 access token；并演示租户与角色要求
protected_router = APIRouter(
    dependencies=[Depends(KairoAuth.require_access_token), Depends(KairoAuth.require_tenant), Depends(KairoAuth.require_roles(["user"]))]
)

@protected_router.get("/me")
async def me() -> Dict[str, Any]:
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={
            "user_id": principal.get("sub"),
            "tenant_id": principal.get("tid"),
            "roles": principal.get("roles") or [],
            "exp": principal.get("exp"),
            "iat": principal.get("iat"),
        },
        msg="ok"
    )

# 将受保护路由挂载到主路由（例如 /auth/me）
router.include_router(protected_router, prefix="")