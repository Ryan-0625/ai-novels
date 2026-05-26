"""
Tests: Structured logging — get_log_context, log_structured, buffer flush
Covers UT-71 ~ UT-75
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from ai_novels.utils.logger import (
    get_log_context, log_structured, flush_all_logs,
    _flush_buffer, _structured_log_buffer,
)
from ai_novels.core.context import (
    WorkflowContext, set_current_context, get_current_tenant_id,
)


# ── UT-71: get_log_context with context ──

class TestGetLogContextWithContext:
    def test_returns_context_values(self):
        from ai_novels.core.context import TenantIdentity, UserIdentity, IdentityContext
        import dataclasses
        base = WorkflowContext.default()
        new_identity = IdentityContext(
            tenant=TenantIdentity(tenant_id="t_log"),
            user=UserIdentity(user_id="u_log"),
        )
        ctx = dataclasses.replace(base, identity=new_identity)
        set_current_context(ctx)
        try:
            log_ctx = get_log_context()
            assert log_ctx["tenant_id"] == "t_log"
            assert log_ctx["user_id"] == "u_log"
        finally:
            set_current_context(None)


# ── UT-72: get_log_context without context ──

class TestGetLogContextWithoutContext:
    def test_returns_empty_dict(self):
        set_current_context(None)
        ctx = get_log_context()
        assert isinstance(ctx, dict)


# ── UT-73: log_structured output format ──

class TestLogStructuredFormat:
    @patch("ai_novels.utils.logger._buffer_write")
    def test_output_is_valid_json(self, mock_buffer_write):
        log_structured("INFO", "test message", extra_field="extra")
        assert mock_buffer_write.called
        args = mock_buffer_write.call_args[0]
        assert len(args) == 2
        assert args[0] == "_structured"

    @patch("ai_novels.utils.logger._buffer_write")
    def test_contains_required_fields(self, mock_buffer_write):
        log_structured("ERROR", "something failed", error_code=500)
        args = mock_buffer_write.call_args[0]
        line = args[1]
        record = json.loads(line)
        assert record["level"] == "ERROR"
        assert record["message"] == "something failed"
        assert "timestamp" in record
        assert "error_code" in record
        assert record["error_code"] == 500


# ── UT-74: buffer flush on limit ──

class TestBufferFlush:
    @pytest.fixture(autouse=True)
    def setup(self):
        _structured_log_buffer.clear()
        yield
        _structured_log_buffer.clear()

    @patch("ai_novels.utils.logger._flush_buffer")
    def test_flush_on_limit(self, mock_flush):
        for i in range(101):
            log_structured("INFO", f"msg {i}")
        assert mock_flush.called

    def test_buffer_contains_entries(self):
        log_structured("INFO", "test")
        assert len(_structured_log_buffer.get("_structured", [])) == 1

    def test_no_flush_below_limit(self):
        for i in range(50):
            log_structured("INFO", f"msg {i}")
        # Should not have flushed
        assert len(_structured_log_buffer.get("_structured", [])) == 50


# ── UT-75: flush_all_logs ──

class TestFlushAllLogs:
    @pytest.fixture(autouse=True)
    def setup(self):
        _structured_log_buffer.clear()
        yield
        _structured_log_buffer.clear()

    def test_flush_all_empties_buffer(self):
        log_structured("INFO", "test")
        log_structured("WARN", "warn")
        assert len(_structured_log_buffer) > 0
        flush_all_logs()
        assert all(len(v) == 0 for v in _structured_log_buffer.values())

    @patch("ai_novels.utils.logger._flush_buffer")
    def test_flush_all_called_for_all_categories(self, mock_flush):
        _structured_log_buffer["cat_a"] = ["line1"]
        _structured_log_buffer["cat_b"] = ["line2"]
        flush_all_logs()
        assert mock_flush.call_count == 2

    def test_flush_idempotent(self):
        flush_all_logs()  # should not raise
        flush_all_logs()  # should not raise
