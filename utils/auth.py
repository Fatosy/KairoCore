"""
KairoAuth 认证与授权工具模块

该模块提供：
- JWT 编解码与签名（HS256）
- Access Token / Refresh Token 的签发、校验与轮换
- 请求上下文主体注入（基于 ContextVar）
- API_KEY 的生成、读取、校验与删除（用于简单的永久密钥接入）
- FastAPI 路由依赖：基于 Access Token、API_KEY、角色、租户等的访问控制

设计理念：全部使用静态方法，调用方无需实例化，便于在项目各处直接引用。
"""

import os
import hmac
import json
import time
import base64
import uuid
import hashlib
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from typing import Any, Dict, List, Optional, Tuple
from contextvars import ContextVar
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fastapi import Request
from ..utils.panic import Panic
from ..common.errors import (
    KCAUTH_TOKEN_INVALID,
    KCAUTH_TOKEN_EXPIRED,
    KCAUTH_REFRESH_INVALID,
    KCAUTH_REFRESH_EXPIRED,
    KCAUTH_TOKEN_REVOKED,
    KCAUTH_PERMISSION_DENIED,
    KCAUTH_TENANT_REQUIRED,
    KCAUTH_ROLE_REQUIRED,
    KCAUTH_CONFIG_ERROR,
    KCAUTH_LOGIN_FAILED,
    KCAUTH_X_KEY_ERROR,
)
from ..utils.log import get_logger
import secrets

logger = get_logger()


class KairoAuth:
    """认证与授权工具类（全部为静态方法）。

    用途：
    - 对外提供 JWT 相关能力与访问控制的依赖函数
    - 通过 ContextVar 保存当前请求主体（principal），避免显式传递

    使用方式：
    - 直接调用 KairoAuth.issue_access_token(...) / verify_access_token(...)
    - 在路由依赖中使用 KairoAuth.require_access_token / require_access_or_api_key 等
    """

    # 当前请求主体上下文（在依赖中写入，在业务处理函数中读取）
    _current_principal: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
        "_current_principal", default=None
    )

    # 简易的 refresh token 存储（示例用途；生产环境建议换为 Redis/DB）
    _REFRESH_STORE: Dict[str, Dict[str, Any]] = {}

    # --- 上下文 ---
    @staticmethod
    def set_current_principal(principal: Dict[str, Any]) -> None:
        """将主体信息写入上下文，供后续业务读取。"""
        KairoAuth._current_principal.set(principal)

    @staticmethod
    def get_current_principal() -> Optional[Dict[str, Any]]:
        """获取当前请求的主体信息，如果尚未注入则返回 None。"""
        return KairoAuth._current_principal.get()

    # --- JWT 基础 ---
    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        """以 URL 安全的 Base64 方式编码，并去除尾部的'='填充。"""
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        """解码 URL 安全的 Base64 字符串，自动补齐缺失的'='填充。"""
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode((data + padding).encode())

    @staticmethod
    def _sign_hs256(secret: str, signing_input: bytes) -> str:
        """使用 HS256 计算签名并返回 base64url 编码的签名串。"""
        sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        return KairoAuth._b64url_encode(sig)

    @staticmethod
    def _jwt_encode(payload: Dict[str, Any], secret: str) -> str:
        """将负载编码为 JWT 字符串（header+payload+signature）。"""
        header = {"alg": "HS256", "typ": "JWT"}
        # 使用无空格的紧凑 JSON 以减小长度
        header_b64 = KairoAuth._b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = KairoAuth._b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature_b64 = KairoAuth._sign_hs256(secret, signing_input)
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    @staticmethod
    def _jwt_decode(token: str, secret: str) -> Dict[str, Any]:
        """解析并校验 JWT，返回 payload。

        - 校验签名是否匹配（使用固定时间比较防止时序攻击）
        - 校验 exp 是否过期（如果存在 exp 字段）
        - 解析 payload JSON 并返回
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise KCAUTH_TOKEN_INVALID
            header_b64, payload_b64, signature_b64 = parts
            signing_input = f"{header_b64}.{payload_b64}".encode()
            expected_sig = KairoAuth._sign_hs256(secret, signing_input)
            # 固定时间比较，避免泄露签名匹配时长差异
            if not hmac.compare_digest(signature_b64, expected_sig):
                raise KCAUTH_TOKEN_INVALID
            payload = json.loads(KairoAuth._b64url_decode(payload_b64))
            # exp 校验（单位秒）
            now = KairoAuth._now()
            if "exp" in payload and now >= int(payload["exp"]):
                raise KCAUTH_TOKEN_EXPIRED
            return payload
        except Panic:
            raise
        except Exception as e:
            # 包括 JSON 解析或 base64 解析异常
            raise KCAUTH_TOKEN_INVALID.msg_format(str(e)) from e

    @staticmethod
    def _env(name: str, default: Optional[str] = None) -> str:
        """读取环境变量，若缺失且未提供默认值则抛出配置错误。"""
        val = os.getenv(name, default)
        if val is None:
            raise KCAUTH_CONFIG_ERROR.msg_format(f"缺少环境变量 {name}")
        return val

    @staticmethod
    def _now() -> int:
        """返回当前时间戳（秒）。"""
        return int(time.time())

    @staticmethod
    def _gen_jti() -> str:
        """生成刷新令牌的唯一 ID（jti）。"""
        return uuid.uuid4().hex

    @staticmethod
    def _refresh_put(jti: str, user_id: str, tenant_id: Optional[str], exp_ts: int) -> None:
        """将刷新令牌信息写入内存存储。
        字段说明：uid 用户ID、tid 租户ID、exp 过期时间戳、revoked 是否已撤销。
        """
        KairoAuth._REFRESH_STORE[jti] = {"uid": user_id, "tid": tenant_id, "exp": exp_ts, "revoked": False}

    @staticmethod
    def _refresh_get(jti: str) -> Optional[Dict[str, Any]]:
        """读取指定 jti 的刷新令牌记录，不存在则返回 None。"""
        return KairoAuth._REFRESH_STORE.get(jti)

    @staticmethod
    def _refresh_revoke(jti: str) -> None:
        """撤销指定 jti 的刷新令牌（标记 revoked=True）。"""
        item = KairoAuth._REFRESH_STORE.get(jti)
        if item:
            item["revoked"] = True

    # --- 签发 ---
    @staticmethod
    def issue_access_token(
        user_id: str,
        tenant_id: Optional[str],
        roles: List[str],
        extra: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, int]:
        """签发访问令牌（access token）。

        参数：
        - user_id: 用户唯一标识
        - tenant_id: 租户标识（可以为空）
        - roles: 用户角色列表
        - extra: 额外的负载字段（会写入 JWT payload）

        返回：
        - (token, exp_ts) 二元组，其中 exp_ts 为过期时间戳（秒）
        """
        secret = KairoAuth._env("JWT_SECRET", "dev-secret")
        iss = os.getenv("JWT_ISS", "KairoCore")
        aud = os.getenv("JWT_AUD", "KairoCoreClients")
        ttl = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))  # 默认 15 分钟

        now = KairoAuth._now()
        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "roles": roles or [],
            "iat": now,
            "exp": now + ttl,
            "iss": iss,
            "aud": aud,
            "type": "access",
        }
        if extra:
            payload.update(extra)

        token = KairoAuth._jwt_encode(payload, secret)
        return token, payload["exp"]

    @staticmethod
    def issue_refresh_token(user_id: str, tenant_id: Optional[str]) -> Tuple[str, str, int]:
        """签发刷新令牌（refresh token）并存储其 jti 记录。

        返回：(token, jti, exp_ts)
        """
        secret = KairoAuth._env("JWT_SECRET", "dev-secret")
        iss = os.getenv("JWT_ISS", "KairoCore")
        aud = os.getenv("JWT_AUD", "KairoCoreClients")
        ttl = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "1209600"))  # 默认 14 天

        now = KairoAuth._now()
        jti = KairoAuth._gen_jti()
        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "iat": now,
            "exp": now + ttl,
            "iss": iss,
            "aud": aud,
            "type": "refresh",
            "jti": jti,
        }
        token = KairoAuth._jwt_encode(payload, secret)
        KairoAuth._refresh_put(jti, user_id, tenant_id, payload["exp"])
        return token, jti, payload["exp"]

    # --- 校验 ---
    @staticmethod
    def verify_access_token(token: str) -> Dict[str, Any]:
        """校验访问令牌（类型必须为 access），返回 payload。"""
        secret = KairoAuth._env("JWT_SECRET", "dev-secret")
        payload = KairoAuth._jwt_decode(token, secret)
        if payload.get("type") != "access":
            raise KCAUTH_TOKEN_INVALID
        return payload

    @staticmethod
    def verify_refresh_token(token: str) -> Dict[str, Any]:
        """校验刷新令牌并核验其 jti 的有效性/未撤销/未过期。"""
        secret = KairoAuth._env("JWT_SECRET", "dev-secret")
        payload = KairoAuth._jwt_decode(token, secret)
        if payload.get("type") != "refresh":
            raise KCAUTH_REFRESH_INVALID
        jti = payload.get("jti")
        if not jti:
            raise KCAUTH_REFRESH_INVALID
        record = KairoAuth._refresh_get(jti)
        if record is None:
            raise KCAUTH_REFRESH_INVALID
        now = KairoAuth._now()
        if record.get("revoked"):
            raise KCAUTH_TOKEN_REVOKED
        if now >= int(record.get("exp", 0)):
            raise KCAUTH_REFRESH_EXPIRED
        return payload

    @staticmethod
    def rotate_refresh_token(old_jti: str, user_id: str, tenant_id: Optional[str]) -> Tuple[str, str, int]:
        """刷新令牌轮换：撤销旧 jti 并签发新的刷新令牌。"""
        # 撤销旧的，生成新的
        KairoAuth._refresh_revoke(old_jti)
        return KairoAuth.issue_refresh_token(user_id, tenant_id)

    @staticmethod
    def revoke_refresh_token(jti: str) -> None:
        """撤销指定的刷新令牌（登出或安全事件场景）。"""
        KairoAuth._refresh_revoke(jti)

    # --- 依赖 ---
    @staticmethod
    async def require_access_token(request: Request) -> None:
        """依赖函数：要求请求提供有效的 Access Token。

        读取顺序：
        - 优先读取 Header: Authorization: Bearer <token>
        - 回退读取 Cookie: access_token（浏览器场景）
        校验通过后将 payload 注入当前上下文。
        """
        # 从 Authorization: Bearer xxx 或 Cookie: access_token 获取 access token 并验证，注入上下文
        token: Optional[str] = None
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
        else:
            # 浏览器场景下，支持从 Cookie 读取（如果已由前端或网关设置）
            token = request.cookies.get("access_token")
        if not token:
            raise KCAUTH_TOKEN_INVALID
        payload = KairoAuth.verify_access_token(token)
        KairoAuth.set_current_principal(payload)

    @staticmethod
    def require_api_key(request: Request) -> None:
        """依赖函数：要求请求提供有效的永久 API_KEY。

        从 Header: X-API-Key 或 Query: api_key 读取并校验；
        校验通过后注入一个基于 API_KEY 的主体信息到上下文。
        """
        # 仅允许使用永久 API_KEY 访问（不校验 Access Token）
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not KairoAuth.check_api_key(api_key):
            raise KCAUTH_TOKEN_INVALID
        principal = {
            "sub": "api_key",
            "roles": ["api_key"],
            "tid": None,
            "type": "api_key",
            "iat": KairoAuth._now(),
            "exp": 2**31 - 1,
        }
        KairoAuth.set_current_principal(principal)
        return

    @staticmethod
    def require_roles(required: List[str]) -> Any:
        """依赖工厂：要求当前主体具备指定角色之一。

        用法：在路由中 `Depends(KairoAuth.require_roles(["admin"]))`
        """
        # 路由级角色校验依赖（不向处理函数传值，使用上下文）
        async def _inner() -> None:
            principal = KairoAuth.get_current_principal()
            if principal is None:
                raise KCAUTH_TOKEN_INVALID
            roles = principal.get("roles") or []
            if not any(r in roles for r in required):
                raise KCAUTH_ROLE_REQUIRED.msg_format(f"需要角色: {required}")
        return _inner

    @staticmethod
    async def require_tenant() -> None:
        """依赖函数：要求当前主体包含租户标识（tid）。"""
        principal = KairoAuth.get_current_principal()
        if principal is None:
            raise KCAUTH_TOKEN_INVALID
        if not principal.get("tid"):
            raise KCAUTH_TENANT_REQUIRED

    # API_KEY 文件路径：默认位于项目根目录（utils 的上级目录）的 .api_key
    _API_KEY_FILE: str = os.getenv(
        "KC_API_KEY_FILE",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".api_key")
    )

    @staticmethod
    def generate_api_key() -> str:
        """生成并持久化一个永久有效的 API_KEY。
        
        优先写入 KC_API_KEY_FILE 指定的文件；如果未配置，则写入项目根目录下 .api_key 文件。
        返回生成的 API_KEY 字符串（即使写入失败也会返回，调用方可自行保存）。
        """
        key = secrets.token_urlsafe(32)
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(KairoAuth._API_KEY_FILE), exist_ok=True)
            with open(KairoAuth._API_KEY_FILE, "w", encoding="utf-8") as f:
                f.write(key)
            # 将文件权限设为 600（仅属主可读写），忽略异常以兼容部分环境
            try:
                os.chmod(KairoAuth._API_KEY_FILE, 0o600)
            except Exception:
                pass
            logger.info(f"API_KEY 已写入: {KairoAuth._API_KEY_FILE}")
        except Exception as e:
            logger.error(f"写入 API_KEY 文件失败: {e}")
            # 写入失败仍返回 key，调用方可自行保存
        return key

    @staticmethod
    def get_api_key() -> Optional[str]:
        """获取当前生效的永久 API_KEY。
        
        读取顺序：
        - 优先读取环境变量 KC_API_KEY
        - 其次读取 KC_API_KEY_FILE 指定文件或默认文件
        返回：匹配到的 key 字符串或 None。
        """
        env_key = os.getenv("KC_API_KEY")
        if env_key:
            return env_key.strip()
        try:
            if os.path.exists(KairoAuth._API_KEY_FILE):
                with open(KairoAuth._API_KEY_FILE, "r", encoding="utf-8") as f:
                    key = f.read().strip()
                    return key or None
        except Exception as e:
            logger.error(f"读取 API_KEY 文件失败: {e}")
        return None

    @staticmethod
    def delete_api_key() -> bool:
        """删除持久化的 API_KEY 文件（不影响环境变量 KC_API_KEY）。
        返回是否删除成功或文件不存在（True）。
        """
        try:
            if os.path.exists(KairoAuth._API_KEY_FILE):
                os.remove(KairoAuth._API_KEY_FILE)
                logger.info("API_KEY 文件已删除")
            return True
        except Exception as e:
            logger.error(f"删除 API_KEY 文件失败: {e}")
            return False

    @staticmethod
    def check_api_key(key: Optional[str]) -> bool:
        """校验传入的 API_KEY 是否匹配当前生效的 API_KEY。"""
        if not key:
            return False
        current = KairoAuth.get_api_key()
        return bool(current) and secrets.compare_digest(current, key.strip())

    @staticmethod
    async def require_access_or_api_key(request: Request) -> None:
        """依赖函数：允许使用 Access Token 或永久 API_KEY 访问。

        - 从 Header: X-API-Key 或 Query: api_key 读取 API_KEY；如匹配则放行并注入一个 API_KEY 主体。
        - 否则按原 require_access_token 流程校验 Access Token。
        """
        # 先尝试 API_KEY
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if KairoAuth.check_api_key(api_key):
            principal = {
                "sub": "api_key",
                "roles": ["api_key"],
                "tid": None,
                "type": "api_key",
                "iat": KairoAuth._now(),
                "exp": 2**31 - 1,  # 逻辑上近似永久，不用于过期判断
            }
            KairoAuth.set_current_principal(principal)
            return
        # 回退到 Access Token 校验
        await KairoAuth.require_access_token(request)

    # =========================
    # 登录口令加密上传与后端解密支持
    # =========================
    @staticmethod
    def _load_rsa_private_key():
        """加载 RSA 私钥用于密码解密。
        
        支持两种配置方式：
        - AUTH_RSA_PRIVATE_KEY_FILE：指向私钥 PEM 文件路径
        - AUTH_RSA_PRIVATE_KEY：环境变量直接存放 PEM 字符串
        可选：AUTH_RSA_PRIVATE_KEY_PASSPHRASE 指定私钥口令
        返回 cryptography 的私钥对象；如未配置或加载失败，返回 None。
        """
        pem_path = os.getenv("AUTH_RSA_PRIVATE_KEY_FILE")
        pem_inline = os.getenv("AUTH_RSA_PRIVATE_KEY")
        passphrase = os.getenv("AUTH_RSA_PRIVATE_KEY_PASSPHRASE")
        pem_bytes = None
        try:
            if pem_path and os.path.exists(pem_path):
                with open(pem_path, "rb") as f:
                    pem_bytes = f.read()
            elif pem_inline:
                pem_bytes = pem_inline.encode()
            if not pem_bytes:
                return None
            key = serialization.load_pem_private_key(
                pem_bytes,
                password=(passphrase.encode() if passphrase else None)
            )
            return key
        except Exception as e:
            logger.warning(f"加载 RSA 私钥失败: {e}")
            return None

    @staticmethod
    def get_rsa_public_key_pem() -> Optional[str]:
        """返回 RSA 公钥 PEM（SubjectPublicKeyInfo），用于前端加密。
        
        依赖私钥存在以派生公钥；如未配置或失败，返回 None。
        """
        try:
            private_key = KairoAuth._load_rsa_private_key()
            if private_key is None:
                return None
            public_key = private_key.public_key()
            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return pem.decode("utf-8")
        except Exception as e:
            logger.warning(f"生成 RSA 公钥失败: {e}")
            return None

    @staticmethod
    def _load_aes_secret_key() -> Optional[bytes]:
        """加载 AES-GCM 的共享密钥（Base64 编码）。
        
        环境变量：LOGIN_PASSWORD_SECRET_KEY（Base64）
        要求密钥长度为 16/24/32 字节（分别对应 AES-128/192/256）。
        返回 bytes；无或错误时返回 None。
        """
        k_b64 = os.getenv("LOGIN_PASSWORD_SECRET_KEY")
        if not k_b64:
            return None
        try:
            key = base64.b64decode(k_b64)
            if len(key) not in (16, 24, 32):
                logger.warning("LOGIN_PASSWORD_SECRET_KEY 长度非法，需 16/24/32 字节（Base64）")
                return None
            return key
        except Exception as e:
            logger.warning(f"解析 LOGIN_PASSWORD_SECRET_KEY 失败: {e}")
            return None

    @staticmethod
    def decrypt_password_if_encrypted(cipher_text: str) -> str:
        """解密前端加密上传的密码（支持 RSA 或 AES-GCM），否则原样返回。
        
        配置：
        - LOGIN_PASSWORD_ENCRYPTION=rsa|aes|none（默认 none）
        - LOGIN_PASSWORD_REQUIRE_ENCRYPTION=true|false（默认 false；true 时解密失败直接拒绝登录）
        - RSA：AUTH_RSA_PRIVATE_KEY_FILE / AUTH_RSA_PRIVATE_KEY / AUTH_RSA_PRIVATE_KEY_PASSPHRASE
        - AES-GCM：LOGIN_PASSWORD_SECRET_KEY（Base64，16/24/32 字节）
        输入：
        - cipher_text：密码字符串；若以 "rsa:" 或 "aes:" 前缀或配置指定模式，则尝试解密
        返回：明文密码字符串；严格模式下失败抛出 KCAUTH_LOGIN_FAILED。
        """
        if not isinstance(cipher_text, str):
            return cipher_text
        enc_mode = os.getenv("LOGIN_PASSWORD_ENCRYPTION", "none").lower()
        require_enc = os.getenv("LOGIN_PASSWORD_REQUIRE_ENCRYPTION", "false").lower() in ("1", "true", "yes", "on")
        force_rsa = enc_mode == "rsa" or cipher_text.startswith("rsa:") or cipher_text.startswith("RSA:")
        force_aes = enc_mode == "aes" or cipher_text.startswith("aes:") or cipher_text.startswith("AES:")

        # AES-GCM 分支（共享密钥）
        if force_aes:
            # 去除前缀
            remain = cipher_text.split(":", 1)[1] if cipher_text.lower().startswith("aes:") else cipher_text
            # 支持两种格式：
            # 1) 聚合 Base64：base64(nonce(12) + ciphertext + tag(16))
            # 2) 分段：nonce_b64:cipher_b64:tag_b64
            nonce = ct = tag = None
            try:
                if ":" in remain:
                    parts = remain.split(":")
                    if len(parts) != 3:
                        raise ValueError("AES 密文格式错误，期望 3 段：nonce:cipher:tag")
                    nonce = base64.b64decode(parts[0])
                    ct = base64.b64decode(parts[1])
                    tag = base64.b64decode(parts[2])
                else:
                    agg = base64.b64decode(remain)
                    if len(agg) < 12 + 16:
                        raise ValueError("AES 聚合密文过短")
                    nonce = agg[:12]
                    tag = agg[-16:]
                    ct = agg[12:-16]
            except Exception as e:
                if require_enc:
                    raise KCAUTH_LOGIN_FAILED.msg_format(f"AES 密文解析失败, {str(e)}")
                logger.warning(f"AES 密文解析失败: {e}")
                return cipher_text

            key = KairoAuth._load_aes_secret_key()
            if key is None:
                if require_enc:
                    raise KCAUTH_LOGIN_FAILED.msg_format("未配置 AES 密钥，无法解密密码")
                logger.warning("未配置 AES 密钥，无法解密密码，回退原文")
                return cipher_text

            try:
                decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
                plain_bytes = decryptor.update(ct) + decryptor.finalize()
                return plain_bytes.decode("utf-8", errors="strict")
            except Exception as e:
                if require_enc:
                    raise KCAUTH_LOGIN_FAILED.msg_format(f"AES 密码解密失败, {str(e)}")
                logger.warning(f"AES 密码解密失败: {e}")
                return cipher_text

        # RSA-OAEP 分支（公私钥）
        if force_rsa:
            # 去除可选前缀
            if cipher_text.lower().startswith("rsa:"):
                cipher_b64 = cipher_text.split(":", 1)[1]
            else:
                cipher_b64 = cipher_text
            private_key = KairoAuth._load_rsa_private_key()
            if private_key is None:
                if require_enc:
                    raise KCAUTH_LOGIN_FAILED.msg_format("未配置 RSA 私钥，无法解密密码")
                logger.warning("未配置 RSA 私钥，无法解密密码，回退为原文")
                return cipher_text
            try:
                try:
                    cipher_bytes = base64.b64decode(cipher_b64)
                except Exception:
                    padding_len = (-len(cipher_b64)) % 4
                    cipher_bytes = base64.urlsafe_b64decode(cipher_b64 + ("=" * padding_len))
                plain_bytes = private_key.decrypt(
                    cipher_bytes,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None,
                    ),
                )
                return plain_bytes.decode("utf-8", errors="strict")
            except Exception as e:
                if require_enc:
                    raise KCAUTH_LOGIN_FAILED.msg_format(f"RSA 密码解密失败, {str(e)}")
                logger.warning(f"RSA 密码解密失败: {e}")
                return cipher_text

        # 未触发任何加密模式
        if require_enc:
            raise KCAUTH_LOGIN_FAILED.msg_format("必须使用加密密码上传")
        return cipher_text

    @staticmethod
    async def require_no_login_x_key(request: Request) -> None:
        """依赖函数：允许使用无登录场景下的 X-Key 访问。

        - 从 Header: X-Key 或 Query: x_key 读取 X-Key；如匹配则放行并注入一个 X-Key 主体。
        - 否则按原 require_access_token 流程校验 Access Token。
        """
        # 先尝试 X-Key
        x_key = request.headers.get("X-Key") or request.query_params.get("x_key")
        no_login_x_key = os.getenv("NO_LOGIN_X_KEY")
        no_login_x_pwd = os.getenv("NO_LOGIN_X_PWD")
        if no_login_x_key is None or no_login_x_pwd is None or x_key is None:
            raise KCAUTH_X_KEY_ERROR.msg_format("未配置X-Key")
        try:
            decrypt_no_login_x_key = KairoAuth.decrypt_no_login_x_key(x_key, no_login_x_pwd)
        except Exception as e:
            raise KCAUTH_X_KEY_ERROR.msg_format(f"X-Key 解密失败, {str(e)}")
        if decrypt_no_login_x_key != no_login_x_key:
            raise KCAUTH_X_KEY_ERROR.msg_format("X-Key 校验失败")


    @staticmethod
    def decrypt_no_login_x_key(cipher_text: str, password: str) -> str:
        """ 
            解密无登录场景下的 X-Key 
            :param combined_data_b64: Base64 encoded combined data (salt + iv + ciphertext).
            :param password: The original password used for encryption.
            :return: Decrypted plaintext string.
        """
        # Decode the Base64 input
        combined_data = base64.b64decode(cipher_text)

        # Extract components
        SALT_LENGTH = 16
        IV_LENGTH = 12
        salt = combined_data[:SALT_LENGTH]
        iv = combined_data[SALT_LENGTH:SALT_LENGTH + IV_LENGTH]
        ciphertext_with_tag = combined_data[SALT_LENGTH + IV_LENGTH:]

        # Derive the same key using PBKDF2 (same parameters as frontend)
        # 前端逻辑：const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer);
        # 因此后端也需要先对密码进行 SHA-256 哈希
        password_hash = hashlib.sha256(password.encode()).digest()
        key_material = hashlib.pbkdf2_hmac('sha256', password_hash, salt, 100000, dklen=32)
        
        # Create AES-GCM cipher and decrypt
        aesgcm = AESGCM(key_material)
        try:
            plaintext_bytes = aesgcm.decrypt(iv, ciphertext_with_tag, None)
            plaintext = plaintext_bytes.decode('utf-8')
            
            # 验证有效期 (1分钟)
            try:
                data = json.loads(plaintext)
                if isinstance(data, dict) and "t" in data and "v" in data:
                    timestamp = data["t"]
                    value = data["v"]
                    
                    # 当前时间 (ms)
                    now = time.time() * 1000
                    # 检查是否过期 (60000ms = 1min)
                    if now - timestamp > 60000:
                        raise ValueError(f"X-Key 已过期 (server_time={now}, client_time={timestamp})")
                    
                    # 可选：防止未来时间过大 (例如允许 1 分钟的时钟偏差)
                    if timestamp - now > 60000:
                         raise ValueError("X-Key 时间戳异常 (时间偏移超过 1 分钟)")

                    return value
                else:
                    raise ValueError("X-Key 格式错误 (缺少 t 或 v 字段)")
            except json.JSONDecodeError:
                raise ValueError("X-Key 格式错误 (JSON 格式错误)")

        except Exception as e:
            raise ValueError(f"{str(e)}") 
