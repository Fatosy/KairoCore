"""
KcUploader: 文件上传/保存工具类

提供两种保存方式：
- save_upload_file: 处理 FastAPI UploadFile（multipart/form-data）并流式写入磁盘
- save_base64: 处理 Base64 字符串并写入磁盘

异常处理：统一使用 common.errors 中定义的 Panic 常量
日志：统一使用项目日志器
"""
from typing import Optional, Dict
import os
import base64

from fastapi import UploadFile

from ..common.errors import (
    KCU_SAVE_DIR_EMPTY_ERROR,
    KCU_MKDIR_ERROR,
    KCU_FILENAME_EMPTY_ERROR,
    KCU_PARAM_MISSING_ERROR,
    KCU_BASE64_PARSE_ERROR,
    KCU_UPLOAD_SAVE_ERROR,
    KCU_BASE64_SAVE_ERROR,
)
from ..utils.panic import Panic
from ..utils.log import get_logger

logger = get_logger()

class KcUploader:
    """
    文件上传/保存工具类。
    """

    def __init__(self, default_target_dir: str = "/tmp"):
        self.default_target_dir = default_target_dir

    def _ensure_dir(self, dir_path: str) -> None:
        if not dir_path:
            raise KCU_SAVE_DIR_EMPTY_ERROR
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            raise KCU_MKDIR_ERROR.msg_format(str(e))

    def _safe_join(self, target_dir: Optional[str], filename: Optional[str]) -> str:
        dir_path = target_dir or self.default_target_dir
        self._ensure_dir(dir_path)
        name = os.path.basename(filename or "")
        if not name:
            raise KCU_FILENAME_EMPTY_ERROR
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
            if not file or not file.filename:
                raise KCU_FILENAME_EMPTY_ERROR
            save_path = self._safe_join(target_dir, filename or file.filename)
            size = 0
            with open(save_path, "wb") as f:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB/chunk
                    if not chunk:
                        break
                    size += len(chunk)
                    f.write(chunk)
            logger.info(f"文件上传保存成功: path={save_path}, size={size}")
            return {"saved": save_path, "size": str(size)}
        except Panic:
            raise
        except Exception as e:
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
            if not content_base64 or not filename:
                raise KCU_PARAM_MISSING_ERROR
            save_path = self._safe_join(target_dir, filename)
            try:
                file_bytes = base64.b64decode(content_base64)
            except Exception:
                raise KCU_BASE64_PARSE_ERROR
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            size = len(file_bytes)
            logger.info(f"Base64 文件保存成功: path={save_path}, size={size}")
            return {"saved": save_path, "size": str(size)}
        except Panic:
            raise
        except Exception as e:
            raise KCU_BASE64_SAVE_ERROR.msg_format(str(e))