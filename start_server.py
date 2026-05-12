"""
启动 FastAPI 服务器 - 使用现成 Python 模块运行
"""
import sys
import os

# 设置项目根目录
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.chdir(project_root)

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(project_root, "config", ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from {env_path}")
    else:
        print(f"Warning: .env file not found at {env_path}")
except ImportError:
    print("Warning: python-dotenv not installed, skipping .env loading")

# 强制不写入字节码
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import uvicorn


def load_server_config() -> dict:
    """从配置文件加载服务器配置"""
    config_path = os.path.join(project_root, "config", "server.json")
    if os.path.exists(config_path):
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_config_value(key: str, default=None):
    """获取配置值，优先使用环境变量"""
    # 环境变量优先
    env_value = os.environ.get(key)
    if env_value is not None:
        return env_value

    # 然后从配置文件读取
    config = load_server_config()
    server_config = config.get("server", {})

    # 支持嵌套键
    if "." in key:
        parts = key.split(".")
        value = server_config
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        return value

    return server_config.get(key, default)


if __name__ == "__main__":
    # 从配置文件或环境变量读取服务器配置
    host = get_config_value("host", "0.0.0.0")
    port = int(get_config_value("port", 8004))
    workers = int(get_config_value("workers", 1))
    reload = get_config_value("reload", False)
    timeout = int(get_config_value("timeout", 120))

    # 转换 reload 为布尔值
    if isinstance(reload, str):
        reload = reload.lower() in ("true", "1", "yes")

    # 使用 uvicorn.run() 直接启动
    uvicorn.run(
        "src.ai_novels.api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        timeout_keep_alive=timeout,
        log_level="debug",
        loop="asyncio",
    )
