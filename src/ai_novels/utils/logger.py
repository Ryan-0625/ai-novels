"""
统一日志模块

@file: utils/logger.py
@date: 2026-03-12
@version: 2.1.0
@description: 统一日志记录器，支持分级、分类、分层日志记录
"""

import logging
import logging.handlers
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable


# 日志级别
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

# 日志分类（名称 → 文件名前缀）
LOG_CATEGORIES = {
    'SYSTEM': 'system',       # 系统级日志
    'CONFIG': 'config',       # 配置相关日志
    'LLM': 'llm',            # LLM调用日志
    'AGENT': 'agent',         # Agent执行日志
    'TASK': 'task',           # 任务执行日志
    'DATABASE': 'database',   # 数据库日志
    'MESSAGING': 'messaging', # 消息队列日志
    'API': 'api',             # API请求日志
    'PERFORMANCE': 'performance', # 性能日志
}

# 分类的显示名称（用于前端）
LOG_CATEGORY_LABELS = {
    'system': '系统',
    'config': '配置',
    'llm': 'LLM 调用',
    'agent': 'Agent',
    'task': '任务',
    'database': '数据库',
    'messaging': '消息队列',
    'api': 'API',
    'performance': '性能',
}

# 每个分类的默认日志级别
DEFAULT_CATEGORY_LEVELS = {
    'system': 'INFO',
    'config': 'INFO',
    'llm': 'INFO',
    'agent': 'DEBUG',
    'task': 'DEBUG',
    'database': 'INFO',
    'messaging': 'INFO',
    'api': 'INFO',
    'performance': 'INFO',
}


class LogContext:
    """日志上下文，用于跟踪请求/任务"""

    _context = {}

    @classmethod
    def set(cls, key: str, value: str):
        """设置上下文值"""
        cls._context[key] = value

    @classmethod
    def get(cls, key: str, default: str = '') -> str:
        """获取上下文值"""
        return cls._context.get(key, default)

    @classmethod
    def clear(cls):
        """清空上下文"""
        cls._context.clear()

    @classmethod
    def update_from_task(cls, task_id: str, agent_name: str = None):
        """从任务信息更新上下文"""
        cls._context['task_id'] = task_id
        if agent_name:
            cls._context['agent'] = agent_name


class JsonFormatter(logging.Formatter):
    """JSON日志格式化器 — 每行一个JSON对象"""

    def __init__(self):
        super().__init__()

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=datetime.now().astimezone().tzinfo).isoformat(),
            "level": record.levelname,
            "category": getattr(record, 'category', 'SYSTEM'),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


class HierarchicalLogger:
    """分级日志记录器"""

    _instance: Optional['HierarchicalLogger'] = None
    _logger: Optional[logging.Logger] = None
    _file_handlers: dict = {}
    _log_dir: str = None

    def __new__(cls) -> 'HierarchicalLogger':
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger is not None:
            return

        # 获取日志目录 (项目根目录的 logs/ 文件夹)
        base_dir = Path(__file__).parent.parent.parent.parent
        self._log_dir = base_dir / 'logs'
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir = self._log_dir.resolve()

        # 从 AppConfig 读取配置
        self._json_format = False
        self._category_levels = dict(DEFAULT_CATEGORY_LEVELS)
        self._max_bytes = 100 * 1024 * 1024  # 100MB
        self._backup_count = 10
        try:
            from ai_novels.config.app_config import get_config
            cfg = get_config()
            log_cfg = cfg.log
            self._json_format = log_cfg.json_format
        except Exception:
            pass

        # 创建主logger
        self._logger = logging.getLogger('ai_novels')
        self._logger.setLevel(logging.DEBUG)

        # 控制台Handler（统一输出）
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self._logger.addHandler(console_handler)

        # 初始化分类日志
        self._init_category_handlers()

    def _init_category_handlers(self):
        """初始化分类日志处理器"""
        for category, cat_name in LOG_CATEGORIES.items():
            self._create_category_handler(cat_name)

    def _create_category_handler(self, category_name: str, level: str = None):
        """创建分类日志处理器（使用 RotatingFileHandler）"""
        log_file = self._log_dir / f'{category_name}.log'

        effective_level = level or self._category_levels.get(category_name, 'DEBUG')

        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self._max_bytes,
            backupCount=self._backup_count,
            encoding='utf-8',
        )
        handler.setLevel(LOG_LEVELS.get(effective_level, logging.DEBUG))

        if self._json_format:
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)-8s] [%(category)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        handler.setFormatter(formatter)

        self._file_handlers[category_name] = handler
        self._logger.addHandler(handler)

        return handler

    def _get_record_extra(self, category: str, context: dict = None) -> dict:
        """获取日志记录额外信息"""
        extra = {'category': category}
        if context:
            extra.update(context)
        return extra

    def _log(self, category: str, level: str, message: str, **kwargs):
        """
        记录分类日志

        Args:
            category: 日志分类
            level: 日志级别
            message: 日志消息
            **kwargs: 附加参数（会自动添加到日志中）
        """
        if self._logger is None:
            return

        # 获取上下文
        context = {
            'task_id': LogContext.get('task_id'),
            'agent': LogContext.get('agent'),
        }

        # 构建消息
        if context.get('task_id'):
            message = f"[Task:{context['task_id']}] {message}"
        if context.get('agent'):
            message = f"[Agent:{context['agent']}] {message}"

        # 附加参数
        if kwargs:
            params = ' '.join(f'{k}={v}' for k, v in kwargs.items())
            message = f'{message} [{params}]'

        # 记录到对应分类
        log_method = {
            'DEBUG': self._logger.debug,
            'INFO': self._logger.info,
            'WARNING': self._logger.warning,
            'ERROR': self._logger.error,
            'CRITICAL': self._logger.critical,
        }.get(level.upper(), self._logger.info)

        extra = self._get_record_extra(category, context)
        log_method(message, extra=extra)

    # ── 配置管理 ──────────────────────────────────

    def get_log_paths(self) -> Dict[str, str]:
        """获取所有分类日志文件的绝对路径"""
        return {
            cat_name: str(self._log_dir / f'{cat_name}.log')
            for cat_name in LOG_CATEGORIES.values()
        }

    def get_log_dir(self) -> str:
        """获取日志目录"""
        return str(self._log_dir)

    def get_category_level(self, category_name: str) -> str:
        """获取指定分类的日志级别"""
        return self._category_levels.get(category_name, 'INFO')

    def set_category_level(self, category_name: str, level: str):
        """动态调整指定分类的日志级别"""
        upper = level.upper()
        if upper not in LOG_LEVELS:
            return
        self._category_levels[category_name] = upper
        handler = self._file_handlers.get(category_name)
        if handler:
            handler.setLevel(LOG_LEVELS[upper])

    def reload_from_config(self):
        """从 AppConfig 重新加载日志配置"""
        try:
            from ai_novels.config.app_config import get_config
            cfg = get_config()
            log_cfg = cfg.log
            self._json_format = log_cfg.json_format
        except Exception:
            pass

    # 分类日志方法
    def system(self, message: str, **kwargs):
        """系统日志"""
        self._log('SYSTEM', 'INFO', message, **kwargs)

    def config(self, message: str, **kwargs):
        """配置日志"""
        self._log('CONFIG', 'INFO', message, **kwargs)

    def config_debug(self, message: str, **kwargs):
        """配置调试日志"""
        self._log('CONFIG', 'DEBUG', message, **kwargs)

    def config_error(self, message: str, **kwargs):
        """配置错误日志"""
        self._log('CONFIG', 'ERROR', message, **kwargs)

    def llm(self, message: str, **kwargs):
        """LLM日志"""
        self._log('LLM', 'INFO', message, **kwargs)

    def llm_debug(self, message: str, **kwargs):
        """LLM调试日志"""
        self._log('LLM', 'DEBUG', message, **kwargs)

    def agent(self, message: str, **kwargs):
        """Agent日志"""
        self._log('AGENT', 'INFO', message, **kwargs)

    def agent_debug(self, message: str, **kwargs):
        """Agent调试日志"""
        self._log('AGENT', 'DEBUG', message, **kwargs)

    def agent_error(self, message: str, **kwargs):
        """Agent错误日志"""
        self._log('AGENT', 'ERROR', message, **kwargs)

    def task(self, message: str, **kwargs):
        """任务日志"""
        self._log('TASK', 'INFO', message, **kwargs)

    def task_debug(self, message: str, **kwargs):
        """任务调试日志"""
        self._log('TASK', 'DEBUG', message, **kwargs)

    def task_error(self, message: str, **kwargs):
        """任务错误日志"""
        self._log('TASK', 'ERROR', message, **kwargs)

    def database(self, message: str, **kwargs):
        """数据库日志"""
        self._log('DATABASE', 'INFO', message, **kwargs)

    def database_debug(self, message: str, **kwargs):
        """数据库调试日志"""
        self._log('DATABASE', 'DEBUG', message, **kwargs)

    def database_error(self, message: str, **kwargs):
        """数据库错误日志"""
        self._log('DATABASE', 'ERROR', message, **kwargs)

    def messaging(self, message: str, **kwargs):
        """消息队列日志"""
        self._log('MESSAGING', 'INFO', message, **kwargs)

    def messaging_debug(self, message: str, **kwargs):
        """消息队列调试日志"""
        self._log('MESSAGING', 'DEBUG', message, **kwargs)

    def messaging_error(self, message: str, **kwargs):
        """消息队列错误日志"""
        self._log('MESSAGING', 'ERROR', message, **kwargs)

    def api(self, message: str, **kwargs):
        """API日志"""
        self._log('API', 'INFO', message, **kwargs)

    def api_debug(self, message: str, **kwargs):
        """API调试日志"""
        self._log('API', 'DEBUG', message, **kwargs)

    def performance(self, message: str, **kwargs):
        """性能日志"""
        self._log('PERFORMANCE', 'INFO', message, **kwargs)

    def performance_debug(self, message: str, **kwargs):
        """性能调试日志"""
        self._log('PERFORMANCE', 'DEBUG', message, **kwargs)

    def config_loading(self, config_file: str, status: str = 'loading', **kwargs):
        """配置加载日志"""
        self.config(f"Config {status}: {config_file}", **kwargs)

    def config_loaded(self, config_file: str, keys: list = None, **kwargs):
        """配置加载完成日志"""
        keys_str = ', '.join(keys) if keys else 'all'
        self.config(f"Config loaded: {config_file} [keys: {keys_str}]", **kwargs)

    def config_error_loading(self, config_file: str, error: str, **kwargs):
        """配置加载错误日志"""
        self.config_error(f"Config load error: {config_file} - {error}", **kwargs)

    def llm_call(self, provider: str, model: str, prompt_tokens: int,
                 completion_tokens: int, duration_ms: int, **kwargs):
        """LLM调用日志（规范要求）"""
        self.llm(f"LLM Call [Provider:{provider}, Model:{model}]",
                 prompt_tokens=prompt_tokens,
                 completion_tokens=completion_tokens,
                 duration_ms=duration_ms,
                 **kwargs)

    # 通用日志级别方法（兼容标准 logging API）
    def debug(self, message: str, **kwargs):
        """通用 DEBUG 日志"""
        self._log('SYSTEM', 'DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """通用 INFO 日志"""
        self._log('SYSTEM', 'INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """通用 WARNING 日志"""
        self._log('SYSTEM', 'WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """通用 ERROR 日志"""
        self._log('SYSTEM', 'ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        """通用 CRITICAL 日志"""
        self._log('SYSTEM', 'CRITICAL', message, **kwargs)

    def agent_exec_start(self, agent_name: str, task_id: str, **kwargs):
        """Agent执行开始日志"""
        LogContext.set('task_id', task_id)
        LogContext.set('agent', agent_name)
        self.agent(f"Agent execution started: {agent_name}", **kwargs)

    def agent_exec_complete(self, agent_name: str, status: str, duration_ms: int, **kwargs):
        """Agent执行完成日志"""
        self.agent(f"Agent execution completed: {agent_name} [Status:{status}, Duration:{duration_ms}ms]", **kwargs)

    def task_start(self, task_id: str, genre: str = None, **kwargs):
        """任务开始日志"""
        LogContext.set('task_id', task_id)
        self.task(f"Task started: {task_id}", genre=genre, **kwargs)

    def task_complete(self, task_id: str, status: str, progress: float, **kwargs):
        """任务完成日志"""
        self.task(f"Task completed: {task_id} [Status:{status}, Progress:{progress:.1%}]", **kwargs)

    def database_connect(self, db_type: str, host: str, port: int, **kwargs):
        """数据库连接日志"""
        self.database(f"Database connected: {db_type}://{host}:{port}", **kwargs)

    def database_query(self, db_type: str, query_type: str, duration_ms: int, **kwargs):
        """数据库查询日志"""
        self.database(f"Database query: {db_type} [{query_type}, {duration_ms}ms]", **kwargs)

    def message_send(self, queue: str, message_type: str, **kwargs):
        """消息发送日志"""
        self.messaging(f"Message sent: {message_type} -> {queue}", **kwargs)

    def message_receive(self, queue: str, message_type: str, **kwargs):
        """消息接收日志"""
        self.messaging(f"Message received: {message_type} <- {queue}", **kwargs)

    def api_request(self, method: str, path: str, status_code: int, duration_ms: int, **kwargs):
        """API请求日志"""
        self.api(f"{method} {path} -> {status_code} [{duration_ms}ms]", **kwargs)


# 全局实例
logger = HierarchicalLogger()

# 便捷函数（保持向后兼容）
def log_info(message: str, **kwargs):
    """信息日志"""
    logger._log('SYSTEM', 'INFO', message, **kwargs)


def log_warn(message: str, **kwargs):
    """警告日志"""
    logger._log('SYSTEM', 'WARNING', message, **kwargs)


def log_error(message: str, **kwargs):
    """错误日志"""
    logger._log('SYSTEM', 'ERROR', message, **kwargs)


def log_debug(message: str, **kwargs):
    """调试日志"""
    logger._log('SYSTEM', 'DEBUG', message, **kwargs)


def log_llm_call(provider: str, model: str, prompt_tokens: int,
                 completion_tokens: int, duration_ms: int):
    """记录LLM调用日志"""
    logger.llm_call(provider, model, prompt_tokens, completion_tokens, duration_ms)


def get_logger() -> HierarchicalLogger:
    """获取全局logger实例"""
    return logger
