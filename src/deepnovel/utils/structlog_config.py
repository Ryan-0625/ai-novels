"""
结构化日志配置 — Structlog

替代文本print风格日志，提供：
- JSON格式输出
- 结构化字段（service, trace_id, user_id等）
- 与OpenTelemetry兼容的上下文注入

@file: utils/structlog_config.py
@date: 2026-04-29
"""

import logging
import sys

import structlog


def configure_structlog(
    service_name: str = "deepnovel-ai",
    environment: str = "development",
    log_level: str = "INFO",
    json_format: bool = False,
):
    """配置结构化日志

    Args:
        service_name: 服务名称（用于标识日志来源）
        environment: 环境名称（development/staging/production）
        log_level: 日志级别
        json_format: 是否输出JSON格式（生产环境推荐）
    """
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
    ]

    if json_format:
        # 生产环境: JSON输出
        console_processor = structlog.processors.JSONRenderer()
    else:
        # 开发环境: 彩色控制台输出
        console_processor = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [console_processor],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 绑定全局字段
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=service_name,
        environment=environment,
    )


def configure_structlog_from_app():
    """从 AppConfig 自动配置 structlog"""
    from deepnovel.config.app_config import get_config

    cfg = get_config()
    log_cfg = cfg.log
    configure_structlog(
        service_name=log_cfg.service_name,
        environment=log_cfg.environment,
        log_level=log_cfg.level,
        json_format=log_cfg.json_format,
    )


def get_structlog_logger(name: str = None):
    """获取结构化日志记录器（兼容旧版 get_logger 接口）"""
    return structlog.get_logger(name)


class StructlogHandler(logging.Handler):
    """兼容标准库logging的Handler — 将标准日志转发到structlog"""

    def __init__(self):
        super().__init__()
        self._logger = structlog.get_logger("stdlib")

    def emit(self, record: logging.LogRecord):
        """转发日志记录"""
        level = record.levelname.lower()
        kwargs = {
            "logger_name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            kwargs["exc_info"] = record.exc_info

        getattr(self._logger, level, self._logger.info)(
            record.getMessage(),
            **kwargs,
        )
