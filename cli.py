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
    """在 base_dir 下创建约定的 6 个目录。"""
    for name in ["action", "domain", "dao", "utils", "common", "schema"]:
        p = base_dir / name
        p.mkdir(parents=True, exist_ok=True)
        print(f"[完成] 创建目录: {p}")


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
    _write_main_py(base_dir, app_name, port, overwrite=overwrite)
    print("\n🎉 初始化完成！你可以运行：")
    print("   python main.py")


def _init_non_interactive(base_dir: Path, name: str, port: int, overwrite: bool = False) -> None:
    _make_dirs(base_dir)
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

