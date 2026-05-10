"""
配置路由测试 (Step 11)

测试范围:
- GET /api/v2/config — 获取完整配置（脱敏）
- GET /api/v2/config/{key_path} — 获取指定配置项
- POST /api/v2/config/reload — 热加载配置
- GET /api/v2/config/novel/presets — 获取小说配置预设列表
- GET /api/v2/config/novel/presets/{preset_name} — 获取指定预设
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from deepnovel.api.routes.config_routes import router as config_router
from deepnovel.config.hub import ConfigHub


@pytest.fixture
def mock_hub():
    """创建 Mock ConfigHub"""
    hub = MagicMock(spec=ConfigHub)
    hub.to_safe_dict.return_value = {
        "app_name": "AI-Novels",
        "app_version": "2.0.0",
        "environment": "test",
        "database": {"url": "***"},  # 脱敏
    }
    hub.get.return_value = "test_value"
    hub.get_preset_names.return_value = ["xianxia", "wuxia"]

    # 模拟 NovelConfig
    mock_preset = MagicMock()
    mock_preset.title = "修仙之路"
    mock_preset.genre = "xianxia"
    mock_preset.description = "一段修仙传奇"
    mock_preset.model_dump.return_value = {
        "title": "修仙之路",
        "genre": "xianxia",
        "description": "一段修仙传奇",
    }
    hub.get_novel_config.return_value = mock_preset
    return hub


@pytest.fixture
def client(mock_hub):
    """创建带 mock ConfigHub 的 TestClient"""
    app = FastAPI()
    app.include_router(config_router, prefix="/api/v2")

    # 覆盖依赖
    async def get_mock_hub():
        return mock_hub

    app.dependency_overrides.clear()
    # 需要覆盖 config_routes 中的 get_config_hub_dep
    from deepnovel.api.routes.config_routes import get_config_hub_dep
    app.dependency_overrides[get_config_hub_dep] = get_mock_hub

    return TestClient(app)


class TestGetFullConfig:
    """GET /api/v2/config 测试"""

    def test_get_full_config(self, client, mock_hub):
        """获取完整脱敏配置"""
        response = client.get("/api/v2/config")

        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "AI-Novels"
        assert data["database"]["url"] == "***"
        mock_hub.to_safe_dict.assert_called_once()


class TestGetConfigItem:
    """GET /api/v2/config/{key_path} 测试"""

    def test_get_existing_key(self, client, mock_hub):
        """获取存在的配置项"""
        response = client.get("/api/v2/config/database/url")

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "database/url"
        assert data["value"] == "test_value"

    def test_get_nonexistent_key(self, client, mock_hub):
        """获取不存在的配置项返回 404"""
        mock_hub.get.return_value = None

        response = client.get("/api/v2/config/nonexistent/key")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestReloadConfig:
    """POST /api/v2/config/reload 测试"""

    def test_reload_success(self, client, mock_hub):
        """热加载成功"""
        response = client.post("/api/v2/config/reload")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reloaded" in data["message"].lower()
        mock_hub.reload.assert_called_once()

    def test_reload_failure(self, client, mock_hub):
        """热加载失败"""
        mock_hub.reload.side_effect = Exception("config file corrupted")

        response = client.post("/api/v2/config/reload")

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()


class TestListNovelPresets:
    """GET /api/v2/config/novel/presets 测试"""

    def test_list_presets(self, client, mock_hub):
        """列出小说配置预设"""
        response = client.get("/api/v2/config/novel/presets")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "xianxia"
        assert data[0]["title"] == "修仙之路"
        assert data[0]["genre"] == "xianxia"

    def test_list_presets_empty(self, client, mock_hub):
        """空预设列表"""
        mock_hub.get_preset_names.return_value = []

        response = client.get("/api/v2/config/novel/presets")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestGetNovelPreset:
    """GET /api/v2/config/novel/presets/{preset_name} 测试"""

    def test_get_existing_preset(self, client, mock_hub):
        """获取存在的预设"""
        response = client.get("/api/v2/config/novel/presets/xianxia")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "修仙之路"
        mock_hub.get_novel_config.assert_called_with("xianxia")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
