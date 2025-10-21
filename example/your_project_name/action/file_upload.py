"""
文件上传接口示例：提供两种上传方式
- multipart 上传（UploadFile）：POST /upload
- Base64 上传（JSON）：POST /upload_base64

签名约束：仅使用 query/body/file 三类参数名，符合 utils/router.enforce_signature 的规则。
返回：统一使用 kQuery.to_response 结构化响应。
"""
from typing import Optional
from KairoCore import kcRouter, kQuery, Panic, KcUploader, exec_with_route_error
from KairoCore.common.errors import KCFU_UPLOAD_FAIL_ERROR, KCFU_BASE64_UPLOAD_FAIL_ERROR
from fastapi import UploadFile
from pydantic import BaseModel, Field

router = kcRouter(tags=["文件上传"])

# multipart 上传：文件 + 可选目标目录
class UploadQuery(BaseModel):
    target_dir: Optional[str] = Field(default="/tmp", description="文件保存目录")
    filename: Optional[str] = Field(default=None, description="保存的文件名")


@router.post("/upload")
async def upload_file(query: UploadQuery, file: UploadFile):
    """
    使用 KcUploader 保存 multipart/form-data 上传文件。
    """
    uploader = KcUploader(default_target_dir="/tmp")
    result = await exec_with_route_error(
        uploader.save_upload_file(file=file, target_dir=query.target_dir, filename=query.filename),
        KCFU_UPLOAD_FAIL_ERROR,
    )
    return kQuery.to_response(data=result, msg="上传成功")


# Base64 上传：通过 JSON 传递字符串
class Base64Body(BaseModel):
    content_base64: str = Field(description="Base64 编码的文件内容")
    filename: str = Field(description="保存的文件名")
    target_dir: Optional[str] = Field(default="/tmp", description="保存目录")

@router.post("/upload_base64")
async def upload_base64(body: Base64Body):
    """
    使用 KcUploader 保存 Base64 编码内容为文件。
    """
    uploader = KcUploader(default_target_dir="/tmp")
    result = await exec_with_route_error(
        uploader.save_base64(content_base64=body.content_base64, filename=body.filename, target_dir=body.target_dir),
        KCFU_BASE64_UPLOAD_FAIL_ERROR,
    )
    return kQuery.to_response(data=result, msg="上传成功")