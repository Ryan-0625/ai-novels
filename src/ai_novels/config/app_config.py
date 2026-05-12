"""
统一应用配置 — Pydantic Settings v2

单⼀配置入口：同时加载 .env 和 config/*.json 文件。
所有模块通过 get_config_hub() 获取配置，不再分两套系统。

分层覆盖优先级（低 → 高）：Pydantic 默认值 < JSON 文件 < .env 文件 < 系统环境变量
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ai_novels.config.novel_config import NovelConfig


class DatabaseConfig(BaseSettings):
    """数据库配置"""

    model_config = SettingsConfigDict(env_prefix="DB_")

    url: str = Field(
        default="postgresql+asyncpg://ai_novels:ai_novels_pass@localhost:5432/ai_novels",
        description="数据库连接URL",
    )
    pool_size: int = Field(default=10, ge=1, description="连接池大小")
    max_overflow: int = Field(default=20, ge=0, description="连接池溢出")
    pool_pre_ping: bool = Field(default=True, description="连接前ping检测")
    pool_recycle: int = Field(default=300, ge=0, description="连接回收时间(秒)")
    echo: bool = Field(default=False, description="SQL语句回显")


class RedisConfig(BaseSettings):
    """Redis配置"""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis连接URL",
    )
    stream_key: str = Field(default="ai_novels:events", description="事件流键名")
    consumer_group: str = Field(default="ai_novels:consumers", description="消费者组名")


class LLMProviderConfig(BaseSettings):
    """单个LLM提供商配置"""

    provider: str = Field(..., description="提供商标识")
    model: str = Field(..., description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    base_url: Optional[str] = Field(default=None, description="自定义Base URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(default=4096, ge=1, description="最大生成token数")
    timeout: float = Field(default=30.0, ge=1.0, description="请求超时（秒）")
    retry_times: int = Field(default=3, ge=0, description="重试次数")
    enabled: bool = Field(default=True, description="是否启用")


class LLMConfig(BaseSettings):
    """LLM全局配置"""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    default_provider: str = Field(default="ollama", description="默认提供商")
    providers: Dict[str, LLMProviderConfig] = Field(
        default_factory=dict, description="提供商列表"
    )
    fallback_enabled: bool = Field(default=True, description="是否启用降级")
    embedding_provider: Optional[str] = Field(default=None, description="默认嵌入提供商")


class LogConfig(BaseSettings):
    """日志配置"""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = Field(default="INFO", description="日志级别")
    json_format: bool = Field(default=False, description="JSON格式输出")
    service_name: str = Field(default="ai-novels-ai", description="服务名称")
    environment: str = Field(default="development", description="环境名称")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"日志级别必须是其中之一: {valid}")
        return upper


class AppConfig(BaseSettings):
    """应用统一配置根模型

    所有配置通过此类统一管理，支持：
    - 环境变量自动映射（前缀见各子配置）
    - .env 文件加载
    - 类型安全验证
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="APP_",
        env_nested_delimiter="__",
    )

    # 应用基础
    app_name: str = Field(default="ai-novels-ai", description="应用名称")
    app_version: str = Field(default="2.0.0", description="应用版本")
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")

    # 服务器
    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, ge=1, le=65535, description="监听端口")

    # 子配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    novel: NovelConfig = Field(default_factory=lambda: NovelConfig(
        title="未命名小说",
        genre="other",
    ))

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid = {"development", "test", "staging", "production"}
        if v not in valid:
            raise ValueError(f"环境必须是其中之一: {valid}")
        return v

    def to_safe_dict(self) -> Dict[str, Any]:
        """导出脱敏后的配置字典（用于日志/监控）"""
        data = self.model_dump()
        # 脱敏所有 api_key
        self._mask_api_keys(data)
        return data

    def _mask_api_keys(self, data: Dict[str, Any]) -> None:
        """递归脱敏 API 密钥"""
        for key, value in data.items():
            if isinstance(value, dict):
                self._mask_api_keys(value)
            elif key == "api_key" and isinstance(value, str) and value:
                data[key] = f"{value[:4]}****{value[-4:]}" if len(value) > 8 else "****"

    def __repr__(self) -> str:
        return f"AppConfig(env={self.environment}, debug={self.debug}, port={self.port})"


# ── JSON 配置加载（与 .env 合并） ──────────────────────────

_CONFIG_FILES = [
    "config/database.json",
    "config/llm.json",
    "config/agents.json",
    "config/generation.json",
    "config/messaging.json",
]


def _load_json_configs() -> Dict[str, Any]:
    """加载所有 JSON 配置文件并深度合并"""
    merged: Dict[str, Any] = {}
    base = os.getcwd()
    for path in _CONFIG_FILES:
        full = os.path.join(base, path)
        if not os.path.exists(full):
            continue
        try:
            with open(full, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            for key, value in data.items():
                if key in ("version", "description"):
                    continue
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
        except Exception:
            continue
    return merged


def _build_init_kwargs(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """从 JSON 数据提取 AppConfig 初始化参数（会被 .env 覆盖）"""
    kwargs: Dict[str, Any] = {}

    # LLM 配置
    llm_json = json_data.get("llm", {})
    if isinstance(llm_json, dict):
        llm_kwargs: Dict[str, Any] = {}
        provider_name = llm_json.get("provider") or llm_json.get("default", "ollama")
        llm_kwargs["default_provider"] = provider_name

        # 构建 providers 字典
        providers = {}
        for prov_name in ("ollama", "qwen", "openai", "gemini", "minimax", "deepseek"):
            prov = llm_json.get(prov_name)
            if isinstance(prov, dict):
                try:
                    providers[prov_name] = LLMProviderConfig(
                        provider=prov_name,
                        model=prov.get("model", "qwen2.5-7b"),
                        api_key=prov.get("api_key"),
                        base_url=prov.get("base_url"),
                        temperature=prov.get("temperature", 0.7),
                        max_tokens=prov.get("max_tokens", 8192),
                        timeout=prov.get("timeout", 600),
                    )
                except Exception:
                    pass
        if providers:
            llm_kwargs["providers"] = providers

        kwargs["llm"] = llm_kwargs

    return kwargs


@lru_cache
def get_config() -> AppConfig:
    """获取全局配置单例

    从 .env 文件和 config/*.json 统一加载配置。
    优先级（低 → 高）：Pydantic 默认值 < JSON 文件 < .env 文件 < 系统环境变量
    """
    json_data = _load_json_configs()
    init_kwargs = _build_init_kwargs(json_data)

    # AppConfig() 自动读取 .env 和系统环境变量，覆盖 init_kwargs
    config = AppConfig(**init_kwargs)

    # 存储原始 JSON 数据供旧版 ConfigManager 使用
    object.__setattr__(config, "_raw", json_data)

    return config


def reload_config() -> AppConfig:
    """重新加载配置（用于热更新场景）"""
    get_config.cache_clear()
    return get_config()
