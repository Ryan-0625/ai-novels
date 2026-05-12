"""
直接运行 FastAPI 服务器 - 用于调试
"""
import sys
import os
import traceback

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:5]}")

try:
    from src.ai_novels.api.main import app
    print("App imported successfully")
except Exception as e:
    print(f"Failed to import app: {e}")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    import uvicorn
    import logging

    # 配置详细日志
    logging.basicConfig(level=logging.DEBUG)
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.DEBUG)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug",
    )
    server = uvicorn.Server(config)
    print("Starting server...")
    server.run()
