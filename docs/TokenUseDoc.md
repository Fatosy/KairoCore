


          
# KairoCore 权限认证使用说明 📘🔐

本说明文档将指导你在 KairoCore 项目中使用已实现的“访问令牌 + 刷新令牌”的认证与授权功能，支持浏览器与 API 调用，并提供多租户与角色的扩展能力。文档包含环境配置、接口说明、调用示例、安全建议、路由集成示例等，力求清晰详细。

---

## 1. 功能概览 ✨

- 认证模型：短期 Access Token（JWT, HS256）+ 长期 Refresh Token
- 支持场景：
  - 浏览器：可通过 HttpOnly Cookie 携带 access_token
  - API/脚本：使用 Authorization: Bearer {access_token}
- 授权能力：
  - 多租户：令牌中携带租户 tid
  - 角色控制：令牌中携带 roles，实现路由级角色检查
- 额外支持：
  - API_KEY：永久有效的服务访问密钥，用于免登录的内部/集成接口；提供依赖 require_api_key 与 require_access_or_api_key（Access Token 或 API_KEY 二选一认证）
- 扩展位：
  - 刷新令牌存储目前为内存演示，生产建议切换为 Redis/DB
  - 登录示例可接入真实用户目录、密码校验、租户/角色加载

---

## 2. 项目结构与关键文件 📁

- 工具与依赖
  - JWT 工具与依赖：`/home/Coding/KairoCore/utils/auth.py`
  - 错误常量：`/home/Coding/KairoCore/common/errors.py`
  - 路由注册与签名强制：`/home/Coding/KairoCore/utils/router.py`
- 示例应用（认证相关）
  - 认证路由：`/home/Coding/KairoCore/example/your_project_name/action/auth.py`
  - 认证 DTO 模型：`/home/Coding/KairoCore/example/your_project_name/schema/auth.py`
  - 受保护接口示例：`/home/Coding/KairoCore/example/your_project_name/action/protected_demo.py`
  - API_KEY 管理路由：`/home/Coding/KairoCore/example/your_project_name/action/api_key_admin.py`
  - 应用启动：`/home/Coding/KairoCore/example/your_project_name/main.py`

---

## 3. 环境变量配置 🔧

请在 `.env`（参考 `.env.example`）中添加以下配置：

```
JWT_SECRET=your-strong-secret
JWT_ISS=KairoCore
JWT_AUD=KairoCoreClients
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=1209600

# API_KEY 支持（永久有效的服务访问密钥）
# 直接在环境变量中提供（优先级更高）或通过文件提供（更适合生产）
KC_API_KEY=your-api-key-here
KC_API_KEY_FILE=/path/to/your/api.key

# 管理路由开关与环境
KC_ENABLE_API_KEY_ADMIN=false
KC_ENV=development
```

说明：
- JWT_SECRET：必须设置为强随机密钥（生产环境必备）🔑
- ACCESS_TOKEN_TTL_SECONDS：访问令牌有效期（默认 15 分钟）
- REFRESH_TOKEN_TTL_SECONDS：刷新令牌有效期（默认 14 天）
- ISS/AUD：发行者与受众标识，可根据系统命名调整
- KC_API_KEY：提供服务级 API_KEY；生产不建议把真实值写入仓库
- KC_API_KEY_FILE：当 KC_API_KEY 未设置时从文件读取；默认路径可在 utils/auth.py 中调整
- KC_ENABLE_API_KEY_ADMIN & KC_ENV：控制是否启用 API_KEY 管理路由，以及在 development/production 下的访问策略

---

## 4. 接口前缀与路径 🛣️

示例应用的启动入口在 `example/your_project_name/main.py`，默认调用：
```
run_kairo("example", 9140, "0.0.0.0")
```

全局 API 前缀是：
```
/example/api/
```

认证相关路径：
- POST `/example/api/auth/login`
- POST `/example/api/auth/refresh`
- POST `/example/api/auth/logout`
- GET `/example/api/auth/me`（保护接口示例）

受保护接口演示路径：
- GET `/example/api/protected_demo/ping`（需要 access token）
- GET `/example/api/protected_demo/tenant/ping`（需要 access token + tenant）
- GET `/example/api/protected_demo/admin/ping`（需要 access token + admin 角色）
- GET `/example/api/protected_demo/api-key/ping`（仅需 API_KEY；使用请求头 X-API-Key 或查询参数 api_key）

如你修改了 `run_kairo` 的 app_name（如改为 `myapp`），上述前缀将随之变为 `/myapp/api/…`。

---

## 5. 令牌内容与校验逻辑 🔍

访问令牌（Access Token, JWT HS256）主要包含以下声明（claims）：
- sub：用户 ID
- tid：租户 ID（可选但常用）
- roles：角色列表（如 ["user","admin"]）
- iat：签发时间
- exp：过期时间
- iss：发行者
- aud：受众
- type：固定为 "access"

刷新令牌（Refresh Token, JWT HS256）包含：
- sub：用户 ID
- tid：租户 ID
- jti：刷新令牌唯一 ID
- iat/exp/iss/aud/type="refresh"

校验流程：
- require_access_token：
  - 优先读取请求头 Authorization: Bearer {token}
  - 若无，则读取 Cookie: access_token
  - 验证签名与 exp，不通过则返回 401
  - 验证通过后，将令牌主体注入上下文（ContextVar）
- require_tenant：
  - 从上下文读取令牌主体，检查是否包含 tid，否则返回 403
- require_roles(["roleA","roleB"])：
  - 从上下文读取 roles，要求至少包含其一，否则返回 403

---

## 6. 认证接口使用指南 🚀

1) 登录获取 access_token 与 refresh_token
- 请求：
  - POST `/example/api/auth/login`
  - JSON 体：
    ```
    {
      "username": "alice",
      "password": "123456",
      "tenant_id": "t1",
      "roles": ["user","admin"]
    }
    ```
- 响应示例：
  ```
  {
    "access_token": "eyJhbGciOi...",
    "access_expires_at": 1730000000,
    "refresh_token": "eyJhbGciOi...",
    "refresh_expires_at": 1731000000,
    "jti": "c1a2b3...",
    "token_type": "Bearer"
  }
  ```

2) 使用 access_token 访问受保护接口
- API 调用：
  ```
  curl http://localhost:9140/example/api/auth/me \
    -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
  ```
- 浏览器场景：
  - 在网关/前端设置 HttpOnly Cookie：`access_token=YOUR_ACCESS_TOKEN` ✅
  - 之后直接访问 GET `/example/api/auth/me`

3) 刷新令牌（access_token 过期时）
- 请求：
  - POST `/example/api/auth/refresh`
  - JSON 体：`{"refresh_token": "YOUR_REFRESH_TOKEN"}`
- 返回：新 access_token 与新 refresh_token（旧的 refresh 被撤销）

4) 登出（撤销 refresh_token）
- 请求：
  - POST `/example/api/auth/logout`
  - JSON 体：`{"refresh_token": "YOUR_REFRESH_TOKEN"}`
- 返回：`{"ok": true}`，之后该 refresh_token 将不可用于刷新

---

## 7. 普通业务路由如何启用 token 校验 🧩

由于框架对路由函数签名有约束（仅允许 query/body/file），认证上下文通过依赖与 ContextVar 注入，不改变处理函数签名。

示例：只要求 access token（类方法调用版）
```python
from fastapi import APIRouter, Depends
from KairoCore import kcRouter, kQuery, KairoAuth

router = kcRouter(tags=["示例"])

protected = APIRouter(dependencies=[Depends(KairoAuth.require_access_token)])

@protected.get("/hello")
async def hello():
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(
        data={"user_id": principal.get("sub")},
        msg="ok"
    )

router.include_router(protected, prefix="")
```

示例：要求租户 + 角色（类方法调用版）
```python
from fastapi import APIRouter, Depends
from KairoCore import KairoAuth

router_admin = APIRouter(dependencies=[
    Depends(KairoAuth.require_access_token),
    Depends(KairoAuth.require_tenant),
    Depends(KairoAuth.require_roles(["admin"]))
])

@router_admin.get("/admin/task")
async def admin_task():
    return {"msg": "admin ok"}

router.include_router(router_admin, prefix="")
```

示例：仅需 API_KEY（免登录）
```python
from fastapi import APIRouter, Depends
from KairoCore import KairoAuth, kcRouter, kQuery

router = kcRouter(tags=["示例"])
only_api_key = APIRouter(dependencies=[Depends(KairoAuth.require_api_key)])

@only_api_key.get("/ping")
async def ping():
    principal = KairoAuth.get_current_principal() or {}
    return kQuery.to_response(data={"msg": "pong-api-key", "principal": principal})

router.include_router(only_api_key, prefix="")
```

示例：access token 或 API_KEY 二选一
```python
from fastapi import APIRouter, Depends
from KairoCore import KairoAuth

router = kcRouter(tags=["示例"])
flex = APIRouter(dependencies=[Depends(KairoAuth.require_access_or_api_key)])

@flex.get("/ping")
async def ping():
    principal = KairoAuth.get_current_principal() or {}
    return {"msg": "pong", "principal": principal}

router.include_router(flex, prefix="")
```

官方示例文件：
- `/example/your_project_name/action/protected_demo.py`

---

## 8. 错误码与返回约定 🧾

统一使用 `exec_with_route_error(awaitable, PanicConst)` 包装错误，常见错误：
- 401 Unauthorized：
  - KCAUTH_TOKEN_INVALID（令牌无效）
  - KCAUTH_TOKEN_EXPIRED（令牌过期）
  - KCAUTH_TOKEN_REVOKED（令牌被撤销）
  - KCAUTH_REFRESH_INVALID（刷新令牌无效）
  - KCAUTH_REFRESH_EXPIRED（刷新令牌过期）
- 403 Forbidden：
  - KCAUTH_TENANT_REQUIRED（需要租户信息）
  - KCAUTH_ROLE_REQUIRED（需要角色权限）
  - KCAUTH_PERMISSION_DENIED（权限不足）
- 500 Internal Server Error：
  - KCAUTH_CONFIG_ERROR（认证配置错误，如缺少必要环境变量）

返回数据统一使用 `kQuery.to_response(...)`，包含 data、msg 等字段，便于前端消费。

---

## 9. 安全建议与最佳实践 🛡️

- 使用 HttpOnly Cookie 存储 access_token（浏览器场景），并设置：
  - Secure（仅 HTTPS）
  - SameSite（Lax/Strict，依据跨站策略）
- 将 refresh_token 仅用于后端通道，不在前端暴露（后端刷新流程）🔒
- 切换刷新令牌存储为 Redis/DB，并启用刷新轮换与黑名单
- 配置合理的 TTL：
  - access_token 15–30 分钟
  - refresh_token 7–30 天（视安全策略）
- 严格校验 ISS/AUD 与签名秘钥
- 管理角色分配，避免过宽权限（如滥发 admin）

---

## 10. 常见问题与排查 🧰

- 登录成功，但访问 /me 返回 403？
  - 检查是否缺少租户 tid（require_tenant）
  - 检查是否缺少必要角色（require_roles）
- 刷新失败返回 401？
  - 可能刷新令牌已撤销或过期；检查 refresh_token 是否正确且仍有效
- 开发阶段需快捷获取 access_token？
  - 可通过 login 接口获取；如需“直接发放”临时接口，请明确说明需求与安全边界（建议在 dev 环境开启，生产禁用）

---

## 11. 端到端测试步骤 ✅

1) 启动服务：
```
cd /home/Coding/KairoCore/example/your_project_name
python main.py
```

2) 登录获取令牌：
```
curl -X POST http://localhost:9140/example/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"123456","tenant_id":"t1","roles":["user","admin"]}'
```

3) 访问保护接口（示例）：
```
curl http://localhost:9140/example/api/protected_demo/ping \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

4) 刷新令牌：
```
curl -X POST http://localhost:9140/example/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

5) 登出：
```
curl -X POST http://localhost:9140/example/api/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN"}'
```

6) 仅 API_KEY 访问示例：
```
curl http://localhost:9140/example/api/protected_demo/api-key/ping \
  -H "X-API-Key: YOUR_API_KEY"
```
或：
```
curl "http://localhost:9140/example/api/protected_demo/api-key/ping?api_key=YOUR_API_KEY"
```

7) 管理 API_KEY（仅在 KC_ENABLE_API_KEY_ADMIN=true 且 KC_ENV=development 时免登录，否则需 admin 角色 + access token）：
- 生成：
```
curl -X POST http://localhost:9140/example/api/api_key_admin/api-key/generate
```
- 获取：
```
curl http://localhost:9140/example/api/api_key_admin/api-key
```
- 删除：
```
curl -X DELETE http://localhost:9140/example/api/api_key_admin/api-key
```

---

## 12. 后续扩展与建议 🧱➡️

- 将刷新令牌存储迁移至 Redis/DB，并提供封装适配层
- 登录接入真实用户目录（数据库/LDAP），并加载租户与角色
- 提供登录接口的浏览器版本（返回 Set-Cookie），用于前端直接写入 HttpOnly Cookie
- 增加更细粒度的租户资源权限模型与策略评估
- 单点登出（注销所有会话），以及设备/会话管理

---
