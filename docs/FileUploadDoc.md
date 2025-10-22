# 📦 文件上传功能使用说明

本说明文档介绍如何在 KairoCore 项目中使用文件上传功能，包含两种上传方式：multipart/form-data 上传和 Base64 字符串上传。内容简洁明了，开箱即用。😊

---

## ✨ 功能概览
- 支持两种上传方式：
  - multipart 上传（UploadFile）：POST `/example/api/file_upload/upload`
  - Base64 上传（JSON）：POST `/example/api/file_upload/upload_base64`
- 统一响应格式：`kQuery.to_response(...)`
- 签名约束：路由函数仅使用 `query/body/file` 参数名（由 `utils/router.enforce_signature` 强制），使接口更清晰规范。

---

## 📁 路径与入参

### 1) multipart 上传
- 路径：`POST /example/api/file_upload/upload`
- 请求类型：`multipart/form-data`
- 表单字段：
  - `file`：文件内容（必填）
  - `target_dir`：保存目录（选填，默认 `/tmp`）
  - `filename`：保存文件名（选填，默认使用原文件名）
- 代码片段：
```python
@router.post("/upload")
async def upload_file(query: UploadQuery, file: UploadFile):
    uploader = KcUploader(default_target_dir="/tmp")
    result = await exec_with_route_error(
        uploader.save_upload_file(file=file, target_dir=query.target_dir, filename=query.filename),
        KCFU_UPLOAD_FAIL_ERROR,
    )
    return kQuery.to_response(data=result, msg="上传成功")
```
- curl 示例：
```bash
curl -X POST http://localhost:9140/example/api/file_upload/upload \
  -F "file=@/path/to/local/file.png" \
  -F "target_dir=/tmp" \
  -F "filename=my_file.png"
```
- 典型响应：
```json
{
  "data": {
    "saved_path": "/tmp/my_file.png",
    "filename": "my_file.png",
    "size": 12345
  },
  "msg": "上传成功"
}
```

### 2) Base64 上传
- 路径：`POST /example/api/file_upload/upload_base64`
- 请求类型：`application/json`
- JSON 字段：
  - `content_base64`：Base64 编码的文件内容（必填）
  - `filename`：保存文件名（必填）
  - `target_dir`：保存目录（选填，默认 `/tmp`）
- 代码片段：
```python
@router.post("/upload_base64")
async def upload_base64(body: Base64Body):
    uploader = KcUploader(default_target_dir="/tmp")
    result = await exec_with_route_error(
        uploader.save_base64(content_base64=body.content_base64, filename=body.filename, target_dir=body.target_dir),
        KCFU_BASE64_UPLOAD_FAIL_ERROR,
    )
    return kQuery.to_response(data=result, msg="上传成功")
```
- curl 示例：
```bash
curl -X POST http://localhost:9140/example/api/file_upload/upload_base64 \
  -H "Content-Type: application/json" \
  -d '{
        "content_base64": "iVBORw0KGgoAAAANSUhEUg...", 
        "filename": "my_file.png",
        "target_dir": "/tmp"
      }'
```
- 典型响应：
```json
{
  "data": {
    "saved_path": "/tmp/my_file.png",
    "filename": "my_file.png",
    "size": 12345
  },
  "msg": "上传成功"
}
```

---

## 🧰 使用建议
- 大文件上传：根据实际场景调整 Nginx/网关的上传大小限制；后端也可设置合理的文件大小上限。
- 文件命名：建议前端传入明确的 `filename`，避免后端根据临时文件名生成不易识别的名称。
- 保存目录：默认 `/tmp`，可通过 `target_dir` 覆盖，请确保运行环境有写权限。
- 安全考虑：对上传内容进行扩展名/类型校验，避免执行型文件被误当资源保存；必要时放置到隔离目录并设置严格访问策略。

---

## 🚀 快速自测
1) 启动示例服务：
```bash
cd /home/Coding/KairoCore/example/your_project_name
python main.py
```
2) multipart 测试：
```bash
curl -X POST http://localhost:9140/example/api/file_upload/upload \
  -F "file=@/path/to/local/file.png" -F "target_dir=/tmp" -F "filename=test.png"
```
3) Base64 测试：
```bash
curl -X POST http://localhost:9140/example/api/file_upload/upload_base64 \
  -H "Content-Type: application/json" \
  -d '{"content_base64":"iVBORw0KG...","filename":"test.png","target_dir":"/tmp"}'
```
4) 下载接口测试：
- 浏览器访问：
  - `http://localhost:9140/example/api/file_upload/download?path=/tmp/test.png&name=my_download.png`
- curl（保存到本地并使用服务器文件名）：
```bash
curl -OJ "http://localhost:9140/example/api/file_upload/download?path=/tmp/test.png&name=my_download.png"
```
- 说明：
  - `path` 为服务器本地已保存的文件路径
  - `name` 为浏览器下载展示的文件名（可选）
  - 若需内联预览（如图片/PDF），可添加 `&inline=true`

---

## 📎 相关文件
- 路由：`example/your_project_name/action/file_upload.py`
- 上传工具：`utils/kc_upload.py`（KcUploader）
- 错误常量：`common/errors.py`（KCFU_UPLOAD_FAIL_ERROR、KCFU_BASE64_UPLOAD_FAIL_ERROR）
- 路由签名约束：`utils/router.py`（enforce_signature）

祝你上传顺利！📤✨