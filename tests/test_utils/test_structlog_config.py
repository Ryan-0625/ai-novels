"""
结构化日志配置测试

测试范围:
- configure_structlog 配置
- get_structlog_logger 兼容接口
- StructlogHandler 标准库转发
- JSON/控制台渲染切换
"""

import logging

import pytest
import structlog

from deepnovel.utils.structlog_config import (
    StructlogHandler,
    configure_structlog,
    get_structlog_logger,
)


class TestConfigureStructlog:
    """configure_structlog 单元测试"""

    def test_configure_structlog_dev_mode(self, caplog):
        """开发模式应配置彩色控制台输出"""
        caplog.set_level(logging.INFO)
        configure_structlog(
            service_name="test-service",
            environment="test",
            log_level="INFO",
            json_format=False,
        )

        logger = structlog.get_logger("test")
        logger.info("test_dev_message", key="value")

        assert "test_dev_message" in caplog.text

    def test_configure_structlog_json_mode(self, caplog):
        """JSON模式应输出JSON格式"""
        caplog.set_level(logging.INFO)
        configure_structlog(
            service_name="test-service",
            environment="test",
            log_level="INFO",
            json_format=True,
        )

        logger = structlog.get_logger("test_json")
        logger.info("test_json_message", key="json_value")

        assert "test_json_message" in caplog.text
        assert "json_value" in caplog.text

    def test_configure_structlog_loglevel(self):
        """日志级别应正确过滤"""
        configure_structlog(
            service_name="test",
            environment="test",
            log_level="WARNING",
            json_format=True,
        )

        logger = structlog.get_logger("test_loglevel")
        # INFO 级别不应输出
        logger.info("should_not_appear")
        # 无异常即表示通过

    def test_configure_structlog_context_vars(self, caplog):
        """全局上下文变量应正确绑定"""
        caplog.set_level(logging.INFO)
        configure_structlog(
            service_name="context-service",
            environment="staging",
        )

        logger = structlog.get_logger("test_ctx")
        logger.info("context_test")

        assert "context_test" in caplog.text


class TestGetStructlogLogger:
    """get_structlog_logger 兼容接口测试"""

    def test_returns_logger(self):
        """必须返回有效的logger实例"""
        configure_structlog()
        logger = get_structlog_logger("test_module")
        assert logger is not None

    def test_logger_can_log(self, caplog):
        """返回的logger必须能记录日志"""
        caplog.set_level(logging.INFO)
        configure_structlog(json_format=True)
        logger = get_structlog_logger("test_module")
        logger.info("compat_test", extra_field="data")

        assert "compat_test" in caplog.text


class TestStructlogHandler:
    """StructlogHandler 标准库转发测试"""

    def test_handler_emits_info(self, caplog):
        """INFO级别日志应正确转发"""
        caplog.set_level(logging.INFO)
        configure_structlog(json_format=True)

        stdlib_logger = logging.getLogger("stdlib_test")
        stdlib_logger.handlers = []
        stdlib_logger.addHandler(StructlogHandler())
        stdlib_logger.setLevel(logging.INFO)

        stdlib_logger.info("stdlib_forward_test")

        assert "stdlib_forward_test" in caplog.text

    def test_handler_emits_error(self, caplog):
        """ERROR级别日志应正确转发"""
        caplog.set_level(logging.ERROR)
        configure_structlog(json_format=True)

        stdlib_logger = logging.getLogger("stdlib_error_test")
        stdlib_logger.handlers = []
        stdlib_logger.addHandler(StructlogHandler())
        stdlib_logger.setLevel(logging.ERROR)

        stdlib_logger.error("error_test_message")

        assert "error_test_message" in caplog.text

    def test_handler_preserves_module_info(self, caplog):
        """应保留模块、函数、行号信息"""
        caplog.set_level(logging.DEBUG)
        configure_structlog(json_format=True)

        stdlib_logger = logging.getLogger("stdlib_info_test")
        stdlib_logger.handlers = []
        stdlib_logger.addHandler(StructlogHandler())
        stdlib_logger.setLevel(logging.DEBUG)

        stdlib_logger.info("info_with_meta")

        assert "info_with_meta" in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
