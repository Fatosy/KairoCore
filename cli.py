"""
KairoCore 命令行工具

用法示例：
1) 交互式初始化（推荐）
   python -m KairoCore init

2) 直接指定参数（无需交互）
   python -m KairoCore init --name my_app --port 9000 --force

说明：
- 若你希望在系统中直接使用 `kairo init` 命令，需要在打包配置中添加 console_scripts 入口。
  当前仓库未提供打包元数据，临时使用 `python -m KairoCore` 即可达到相同效果。

本工具将创建一个“最简洁的示例项目”结构：
- 目录：action/、domain/、dao/、utils/、common/、schema/
- 示例路由：action/hello.py（包含 GET/POST 接口与分层调用）
- 入口文件：main.py（调用 KairoCore.run_kairo）
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional


def _write_main_py(base_dir: Path, app_name: str, port: int, overwrite: bool = False) -> Path:
    """在 base_dir 下生成 main.py 文件。"""
    target = base_dir / "main.py"
    if target.exists() and not overwrite:
        # 简单的交互确认
        print(f"[提示] {target} 已存在。是否覆盖? [y/N]")
        ans = input().strip().lower()
        if ans not in {"y", "yes"}:
            print("[跳过] 未覆盖 main.py。")
            return target

    content = (
        "from KairoCore import run_kairo\n"
        "from dotenv import load_dotenv\n\n"
        "if __name__ == \"__main__\":\n"
        "    load_dotenv()\n"
        f"    run_kairo(\"{app_name}\", {port}, \"0.0.0.0\")\n"
    )
    target.write_text(content, encoding="utf-8")
    print(f"[完成] 生成文件: {target}")
    return target


def _make_dirs(base_dir: Path) -> None:
    """在 base_dir 下创建约定的 6 个目录，并写入 __init__.py。"""
    for name in ["action", "domain", "dao", "utils", "common", "schema"]:
        p = base_dir / name
        p.mkdir(parents=True, exist_ok=True)
        init_file = p / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")
        print(f"[完成] 创建目录: {p}")


def _write_common_files(base_dir: Path, overwrite: bool = False) -> None:
    """生成 common 目录中的最简示例文件。"""
    consts = base_dir / "common" / "consts.py"
    errors = base_dir / "common" / "errors.py"

    if (not consts.exists()) or overwrite:
        consts.write_text(
            "APP_DESCRIPTION = \"Demo project initialized by KairoCore CLI\"\n"
            "APP_VERSION = \"0.1.0\"\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {consts}")

    if (not errors.exists()) or overwrite:
        errors.write_text(
            "from KairoCore import Panic\n\n"
            "# User用户 异常 业务代码 20010 ~ 20021\n"
            "SCM_USER_PARAM_VALIDATE_ERROR = Panic(20010, \"用户参数验证失败，请检查！\")\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {errors}")


def _write_utils_demo(base_dir: Path, overwrite: bool = False) -> None:
    """生成 utils 目录中的最简工具函数示例。"""
    helpers = base_dir / "utils" / "helpers.py"
    if (not helpers.exists()) or overwrite:
        helpers.write_text(
            "def normalize_name(name: str) -> str:\n"
            "    \"\"\"将名字去空格并首字母大写\"\"\"\n"
            "    return name.strip().title()\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {helpers}")


def _write_schema_demo(base_dir: Path, overwrite: bool = False) -> None:
    """生成 schema 目录中的最简 Pydantic 数据结构示例。"""
    demo = base_dir / "schema" / "demo.py"
    if (not demo.exists()) or overwrite:
        demo.write_text(
            "from pydantic import BaseModel, Field\n\n"
            "class PingResponse(BaseModel):\n"
            "    message: str\n\n"
            "class GreetQuery(BaseModel):\n"
            "    name: str = Field(..., min_length=1, description=\"你的名字\")\n\n"
            "class GreetResponse(BaseModel):\n"
            "    greeting: str\n\n"
            "class EchoRequest(BaseModel):\n"
            "    text: str = Field(..., min_length=1, description=\"任意文本\")\n"
            "    times: int = Field(1, ge=1, le=10, description=\"重复次数（1-10）\")\n\n"
            "class EchoResponse(BaseModel):\n"
            "    items: list[str]\n\n"
            "class UserQuery(BaseModel):\n"
            "    user_id: int = Field(..., ge=1, description=\"用户ID\")\n\n"
            "class UserOut(BaseModel):\n"
            "    id: int\n"
            "    name: str\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {demo}")


def _write_dao_demo(base_dir: Path, overwrite: bool = False) -> None:
    """生成 dao 目录中的最简数据访问层示例。"""
    user = base_dir / "dao" / "user.py"
    if (not user.exists()) or overwrite:
        user.write_text(
            "from schema.demo import UserOut\n\n"
            "class UserDao:\n"
            "    \"\"\"用户数据访问层\"\"\"\n"
            "    @staticmethod\n"
            "    def get_user_by_id(user_id: int) -> UserOut:\n"
            "        \"\"\"模拟查询并返回用户信息\"\"\"\n"
            "        return UserOut(id=user_id, name=\"Alice\")\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {user}")


def _write_domain_demo(base_dir: Path, overwrite: bool = False) -> None:
    """生成 domain 目录中的最简业务逻辑层示例。"""
    user = base_dir / "domain" / "user.py"
    if (not user.exists()) or overwrite:
        user.write_text(
            "from dao.user import UserDao\n"
            "from utils.helpers import normalize_name\n"
            "from schema.demo import UserOut\n\n"
            "class UserDomain:\n"
            "    \"\"\"用户业务逻辑层\"\"\"\n"
            "    @staticmethod\n"
            "    def get_user_profile(user_id: int) -> UserOut:\n"
            "        \"\"\"业务逻辑：获取并格式化用户信息\"\"\"\n"
            "        u = UserDao.get_user_by_id(user_id)\n"
            "        return UserOut(id=u.id, name=normalize_name(u.name))\n",
            encoding="utf-8",
        )
        print(f"[完成] 生成: {user}")


def _write_example_router(base_dir: Path, overwrite: bool = False) -> Path:
    """在 action/ 下生成一个最简示例路由 hello.py，涵盖 GET/POST 与分层调用。"""
    target = base_dir / "action" / "hello.py"
    if target.exists() and not overwrite:
        print(f"[提示] {target} 已存在。是否覆盖? [y/N]")
        ans = input().strip().lower()
        if ans not in {"y", "yes"}:
            print("[跳过] 未覆盖示例路由。")
            return target

    content = (
        "from fastapi import APIRouter\n"
        "from common.consts import APP_DESCRIPTION\n"
        "from utils.helpers import normalize_name\n"
        "from schema.demo import (\n"
        "    PingResponse, GreetQuery, GreetResponse, EchoRequest, EchoResponse,\n"
        "    UserQuery, UserOut\n"
        ")\n"
        "from domain.user import get_user_profile\n\n"
        "router = APIRouter(tags=[\"示例\"])\n\n"
        "@router.get(\"/ping\", response_model=PingResponse)\n"
        "async def ping() -> PingResponse:\n"
        "    return PingResponse(message=\"pong\")\n\n"
        "@router.get(\"/greet\", response_model=GreetResponse)\n"
        "async def greet(query: GreetQuery) -> GreetResponse:\n"
        "    return GreetResponse(greeting=f\"你好，{normalize_name(query.name)}!\")\n\n"
        "@router.post(\"/echo\", response_model=EchoResponse)\n"
        "async def echo(body: EchoRequest) -> EchoResponse:\n"
        "    return EchoResponse(items=[body.text for _ in range(body.times)])\n\n"
        "@router.get(\"/user\", response_model=UserOut)\n"
        "async def user_info(query: UserQuery) -> UserOut:\n"
        "    return get_user_profile(query.user_id)\n"
    )
    target.write_text(content, encoding="utf-8")
    print(f"[完成] 生成示例路由: {target}")
    return target


def _init_interactive(base_dir: Path, overwrite: bool = False) -> None:
    print("请输入应用名称（例如：example）：")
    app_name = input().strip() or "example"

    print("请输入应用端口号（例如：9140）：")
    port_str = input().strip() or "9140"
    try:
        port = int(port_str)
    except ValueError:
        print("[警告] 端口号无效，使用默认 9140。")
        port = 9140

    _make_dirs(base_dir)
    _write_common_files(base_dir, overwrite=overwrite)
    _write_utils_demo(base_dir, overwrite=overwrite)
    _write_schema_demo(base_dir, overwrite=overwrite)
    _write_dao_demo(base_dir, overwrite=overwrite)
    _write_domain_demo(base_dir, overwrite=overwrite)
    _write_example_router(base_dir, overwrite=overwrite)
    _write_main_py(base_dir, app_name, port, overwrite=overwrite)
    print("\n🎉 初始化完成！你可以运行：")
    print("   python main.py")


def _init_non_interactive(base_dir: Path, name: str, port: int, overwrite: bool = False) -> None:
    _make_dirs(base_dir)
    _write_common_files(base_dir, overwrite=overwrite)
    _write_utils_demo(base_dir, overwrite=overwrite)
    _write_schema_demo(base_dir, overwrite=overwrite)
    _write_dao_demo(base_dir, overwrite=overwrite)
    _write_domain_demo(base_dir, overwrite=overwrite)
    _write_example_router(base_dir, overwrite=overwrite)
    _write_main_py(base_dir, name, port, overwrite=overwrite)
    print("\n🎉 初始化完成！你可以运行：")
    print("   python main.py")


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="kairo", description="KairoCore 项目初始化工具")
    subparsers = parser.add_subparsers(dest="command")

    p_init = subparsers.add_parser("init", help="初始化当前目录为 KairoCore 项目结构")
    p_init.add_argument("--name", "-n", type=str, help="应用名称，如 example")
    p_init.add_argument("--port", "-p", type=int, help="应用端口号，如 9140")
    p_init.add_argument("--force", "-f", action="store_true", help="覆盖已有 main.py")

    args = parser.parse_args(argv)
    if args.command != "init":
        parser.print_help()
        return

    base_dir = Path.cwd()
    if args.name and args.port:
        _init_non_interactive(base_dir, args.name, args.port, overwrite=args.force)
    else:
        _init_interactive(base_dir, overwrite=args.force)


if __name__ == "__main__":
    main()
