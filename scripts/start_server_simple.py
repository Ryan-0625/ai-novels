"""
启动 FastAPI 服务器 - 直接使用 uvicorn（非 reload 模式）
"""
import sys
import os

# 设置项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

from src.ai_novels.api.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "start_server_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 禁用 reload 以避免导入问题
        log_level="debug",
    )
