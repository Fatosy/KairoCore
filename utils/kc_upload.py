"""
KcUploader: 文件上传/下载/导入/导出工具类

提供四类能力：
- save_upload_file: 处理 FastAPI UploadFile（multipart/form-data）并流式写入磁盘
- save_base64: 处理 Base64 字符串并写入磁盘
- export_to_base64: 将本地文件内容导出为 Base64 字符串（便于前端或第三方传输）
- build_download_response: 构建用于浏览器下载的响应对象（FileResponse）

异常处理：统一使用 common.errors 中定义的 Panic 常量
日志：统一使用项目日志器
安全约束：所有保存操作使用 os.path.basename 规避路径穿越，仅允许纯文件名
"""
# 导入类型注解与标准库
from typing import Optional, Dict
import os  # 文件系统操作（目录创建、路径拼接、文件读写）
import base64  # Base64 编解码

# FastAPI 类型：用于接收前端上传的文件
from fastapi import UploadFile

# 项目内的错误常量与日志工具
from ..common.errors import (
    KCU_SAVE_DIR_EMPTY_ERROR,  # 保存目录为空
    KCU_MKDIR_ERROR,           # 目录创建失败
    KCU_FILENAME_EMPTY_ERROR,  # 文件名为空
    KCU_PARAM_MISSING_ERROR,   # 通用参数缺失错误
    KCU_BASE64_PARSE_ERROR,    # Base64 解析失败
    KCU_UPLOAD_SAVE_ERROR,     # 上传保存失败
    KCU_BASE64_SAVE_ERROR,     # Base64 保存失败
)
from ..utils.panic import Panic
from ..utils.log import get_logger
import mimetypes  # 推断 MIME 类型，用于下载响应的 Content-Type
from fastapi.responses import FileResponse  # 用于构建浏览器下载响应

logger = get_logger()

class KcUploader:
    """
    文件上传/下载相关的通用工具类。

    方法总览：
    - save_upload_file(file, target_dir, filename): 保存 multipart/form-data 上传的文件
    - save_base64(content_base64, filename, target_dir): 保存 Base64 字符串为文件
    - export_to_base64(src_path): 将本地文件导出为 Base64 字符串
    - build_download_response(src_path, download_name, media_type, inline): 构建浏览器下载响应

    使用建议：
    - 实例化时可指定 default_target_dir（默认 /tmp），也可在方法调用时传入 target_dir 覆盖
    - 建议在路由层对可下载/可保存的目录做白名单限制
    """

    def __init__(self, default_target_dir: str = "/tmp"):
        # 默认保存目录，可在具体调用时覆盖
        self.default_target_dir = default_target_dir

    def _ensure_dir(self, dir_path: str) -> None:
        # 校验目录参数
        if not dir_path:
            raise KCU_SAVE_DIR_EMPTY_ERROR
        try:
            # 确保目录存在（不存在则创建）
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            # 创建目录失败时抛出统一错误
            raise KCU_MKDIR_ERROR.msg_format(str(e))

    def _safe_join(self, target_dir: Optional[str], filename: Optional[str]) -> str:
        # 取调用传入目录或默认目录
        dir_path = target_dir or self.default_target_dir
        # 确保目录存在与可写
        self._ensure_dir(dir_path)
        # 仅使用纯文件名，防止路径穿越
        name = os.path.basename(filename or "")
        if not name:
            raise KCU_FILENAME_EMPTY_ERROR
        # 拼接安全的保存路径
        return os.path.join(dir_path, name)

    async def save_upload_file(self, file: UploadFile, target_dir: Optional[str] = None, filename: Optional[str] = None) -> Dict[str, str]:
        """
        保存 multipart/form-data 上传的文件。

        Args:
            file (UploadFile): FastAPI UploadFile 对象
            target_dir (str, optional): 保存目录，默认使用初始化的 default_target_dir
            filename (str, optional): 自定义文件名（仅文件名，不含路径）。不提供则使用原始文件名

        Returns:
            Dict[str, str]: {"saved": 保存路径, "size": 写入字节数}
        """
        try:
            # 校验上传文件与文件名
            if not file or not file.filename:
                raise KCU_FILENAME_EMPTY_ERROR
            # 生成安全的保存路径
            save_path = self._safe_join(target_dir, filename or file.filename)
            size = 0
            # 以流式方式写入，避免一次性加载大文件至内存
            with open(save_path, "wb") as f:
                while True:
                    # 1MB/chunk 读取上传内容
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)
            logger.info(f"文件上传保存成功: path={save_path}, size={size}")
            return {"saved": save_path, "size": str(size)}
        except Panic:
            # 上层已定义的业务中断异常，直接抛出以便统一处理
            raise
        except Exception as e:
            # 其他异常统一包装为上传保存失败
            raise KCU_UPLOAD_SAVE_ERROR.msg_format(str(e))

    async def save_base64(self, content_base64: str, filename: str, target_dir: Optional[str] = None) -> Dict[str, str]:
        """
        保存 Base64 编码的文件内容。

        Args:
            content_base64 (str): Base64 字符串
            filename (str): 保存文件名（仅文件名，不含路径）
            target_dir (str, optional): 保存目录

        Returns:
            Dict[str, str]: {"saved": 保存路径, "size": 写入字节数}
        """
        try:
            # 基本参数校验
            if not content_base64 or not filename:
                raise KCU_PARAM_MISSING_ERROR
            # 生成安全的保存路径
            save_path = self._safe_join(target_dir, filename)
            try:
                # Base64 → bytes
                file_bytes = base64.b64decode(content_base64)
            except Exception:
                # Base64 内容不合法
                raise KCU_BASE64_PARSE_ERROR
            # 写入文件
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            size = len(file_bytes)
            logger.info(f"Base64 文件保存成功: path={save_path}, size={size}")
            return {"saved": save_path, "size": str(size)}
        except Panic:
            raise
        except Exception as e:
            # 其他异常统一包装为 Base64 保存失败
            raise KCU_BASE64_SAVE_ERROR.msg_format(str(e))

    async def export_to_base64(self, src_path: str) -> Dict[str, str]:
        """
        将本地文件内容导出为 Base64 字符串（便于通过 JSON 接口或第三方传输）。
        """
        try:
            # 校验源文件路径
            if not src_path:
                raise KCU_PARAM_MISSING_ERROR
            if not os.path.exists(src_path):
                raise KCU_UPLOAD_SAVE_ERROR.msg_format("file not exist")
            # 读取二进制并编码为 Base64
            with open(src_path, "rb") as f:
                data = f.read()
            content_b64 = base64.b64encode(data).decode("ascii")
            logger.info(f"文件导出为 Base64 成功: path={src_path}, size={len(data)}")
            return {"path": src_path, "size": str(len(data)), "content_base64": content_b64}
        except Panic:
            raise
        except Exception as e:
            # 统一包装为上传保存错误（文件访问/IO 异常等）
            raise KCU_UPLOAD_SAVE_ERROR.msg_format(str(e))

    # 新增：构建用于浏览器下载的响应
    async def build_download_response(
        self,
        src_path: str,
        download_name: Optional[str] = None,
        media_type: Optional[str] = None,
        inline: bool = False,
    ) -> FileResponse:
        """
        构建使浏览器触发下载的响应对象（支持设置文件名、Content-Type 与是否内联）。

        Args:
            src_path (str): 本地文件路径
            download_name (str, optional): 下载时展示的文件名，默认取源文件名
            media_type (str, optional): MIME 类型，不传则根据扩展名推断
            inline (bool, optional): 是否内联显示（默认 False，即作为附件下载）

        Returns:
            FileResponse: 可直接在路由中 return 的响应
        """
        try:
            # 基本校验：路径存在且可读
            if not src_path:
                raise KCU_PARAM_MISSING_ERROR
            if not os.path.exists(src_path):
                raise KCU_UPLOAD_SAVE_ERROR.msg_format("file not exist")
            # 下载文件名：优先使用调用者指定，否则取源文件名
            name = download_name or os.path.basename(src_path)
            # 推断 Content-Type：不传则根据扩展名推断，兜底为 application/octet-stream
            ctype = media_type
            if not ctype:
                guessed, _ = mimetypes.guess_type(name)
                ctype = guessed or "application/octet-stream"
            # Content-Disposition: attachment 触发下载；inline 尝试预览显示（如图片/PDF）
            disposition = "inline" if inline else "attachment"
            headers = {"Content-Disposition": f'{disposition}; filename="{name}"'}
            logger.info(f"构建下载响应: path={src_path}, name={name}, inline={inline}")
            return FileResponse(src_path, media_type=ctype, headers=headers)
        except Panic:
            raise
        except Exception as e:
            # 统一包装为上传保存错误（路径/IO 异常等）
            raise KCU_UPLOAD_SAVE_ERROR.msg_format(str(e))
