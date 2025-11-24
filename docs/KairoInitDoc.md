# KairoCore CLI：`kairo init` 快速指南 🚀

像 Vite 一样一键初始化，几秒钟搭好项目骨架。适合从零开始，快速创建可运行的 KairoCore 应用。🎯

## ✅ 准备工作
- 已安装 Python（建议 3.9 及以上）
- 当前环境中可使用 KairoCore（本仓库已内置命令入口）

## 🪄 交互式初始化（推荐）
在目标目录执行：

```bash
python -m KairoCore init
```

根据提示输入：
- 应用名称（如：`example`）
- 端口号（如：`9140`）

完成后自动生成：
- 📁 目录：`action/`、`domain/`、`dao/`、`utils/`、`common/`、`schema/`
- 📄 文件：`main.py`

`main.py` 示例：
```python
from KairoCore import run_kairo
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    run_kairo("example", 9140, "0.0.0.0")
```

运行项目：
```bash
python main.py
```

## ⚡ 非交互式（直接指定参数）
无需输入，直接生成：
```bash
python -m KairoCore init --name my_app --port 9000 --force
```

参数说明：
- `--name/-n` 指定应用名称
- `--port/-p` 指定端口号
- `--force/-f` 若已有 `main.py` 则覆盖

## 🔌 可选：系统级脚本入口（`kairo` 命令）
如果你希望直接使用 `kairo init`（无需 `python -m`），在 `pyproject.toml` 中添加：
```toml
[project.scripts]
kairo = "KairoCore.cli:main"
```

开发安装：
```bash
pip install -e .
```

随后即可：
```bash
kairo init
```

## ❓常见问题（FAQ）
- `main.py` 已存在怎么办？
  - 交互式模式会提示是否覆盖；非交互式可用 `--force` 强制覆盖。
- 环境变量如何加载？
  - `main.py` 默认使用 `python-dotenv` 的 `load_dotenv()`，会自动读取 `.env` 文件。
- 端口输入错误？
  - 会回退到默认端口（示例为 `9140`）。你也可以自己指定。

---


祝你开发愉快！💡
