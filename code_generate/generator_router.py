# /home/Coding/KairoCore/code_generate/generator_router.py

from fastapi import APIRouter as kcRouter
from fastapi.responses import HTMLResponse
from ..utils.panic import QueryResponse
from .code_generator import CodeGenerator
import os

kQuery = QueryResponse()

router = kcRouter(tags=["代码生成器"])

@router.post("/generate")
async def generate_code(route_name: str, route_name_cn: str = None, table_name: str = None):
    """
    生成路由代码文件
    
    Args:
        route_name: 路由名称（英文）
        route_name_cn: 路由中文名称
        table_name: 数据库表名
    """
    try:
        # 获取项目根目录
        project_path = os.getcwd()
        
        generator = CodeGenerator(project_path)
        code_blocks = generator.generate_code_blocks(route_name, route_name_cn, table_name)
        
        return kQuery.to_response(data=code_blocks)
    except Exception as e:
        return kQuery.to_response(code=500, msg=f"生成失败: {str(e)}")

@router.get("/generator", response_class=HTMLResponse)
async def generator_page():
    """
    代码生成器页面
    """
    try:
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建HTML文件路径
        html_file_path = os.path.join(current_dir, "generate_page.html")
        # 读取HTML文件内容
        with open(html_file_path, "r", encoding="utf-8") as file:
            html_content = file.read()
        
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>页面文件未找到</h1><p>generate_page.html 文件不存在</p>", status_code=500)
    except Exception as e:
        return HTMLResponse(content=f"<h1>读取页面文件时出错</h1><p>{str(e)}</p>", status_code=500)