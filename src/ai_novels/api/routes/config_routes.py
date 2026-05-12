"""
配置管理API路由

Step 11: 配置管理接口（获取配置/热加载/验证/健康检查）
基于 ConfigHub 实现

@file: api/routes/config_routes.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ai_novels.api.dependencies import get_config_hub_dep
from ai_novels.config.hub import ConfigHub
from ai_novels.config.novel_config import GenreType, NovelConfig, StyleType

router = APIRouter(prefix="/config", tags=["config"])


# ---- 请求/响应模型 ----


class ConfigReloadResponse(BaseModel):
    """配置热加载响应"""

    success: bool
    message: str
    timestamp: str


class ConfigValidateResponse(BaseModel):
    """配置验证响应"""

    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class NovelPresetResponse(BaseModel):
    """小说预设响应"""

    name: str
    title: str
    genre: str
    description: str


# ---- API 端点 ----


@router.get("", summary="获取完整配置（脱敏）")
async def get_full_config(
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """获取当前完整配置（API密钥已脱敏）"""
    return hub.to_safe_dict()


@router.get("/novel/presets", response_model=List[NovelPresetResponse], summary="获取小说配置预设")
async def list_novel_presets(
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """列出所有可用的小说配置预设"""
    presets = []
    for name in hub.get_preset_names():
        preset: NovelConfig = hub.get_novel_config(name)
        presets.append(
            NovelPresetResponse(
                name=name,
                title=preset.title,
                genre=str(preset.genre),
                description=preset.description or "",
            )
        )
    return presets


@router.get("/novel/presets/{preset_name}", summary="获取指定预设配置")
async def get_novel_preset(
    preset_name: str,
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """获取指定名称的小说配置预设"""
    config = hub.get_novel_config(preset_name)
    return config.model_dump()


@router.post("/reload", response_model=ConfigReloadResponse, summary="热加载配置")
async def reload_config(
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """重新加载配置（从环境变量和 .env 文件）"""
    try:
        hub.reload()
        import datetime

        return ConfigReloadResponse(
            success=True,
            message="Configuration reloaded successfully",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {e}")


@router.get("/novel/genres", summary="获取可用小说类型")
async def list_novel_genres():
    """返回所有可用的小说类型列表"""
    genre_names = {
        GenreType.FANTASY: "奇幻",
        GenreType.SCI_FI: "科幻",
        GenreType.WUXIA: "武侠",
        GenreType.XIUXIA: "修仙",
        GenreType.ROMANCE: "言情",
        GenreType.MYSTERY: "悬疑",
        GenreType.HORROR: "灵异",
        GenreType.THRILLER: "惊悚",
        GenreType.HISTORY: "历史",
        GenreType.ADVENTURE: "冒险",
        GenreType.DRAMA: "剧情",
        GenreType.URBAN_FANTASY: "都市",
        GenreType.OTHER: "其他",
    }
    return [
        {"value": gt.value, "label": genre_names.get(gt, gt.value)}
        for gt in GenreType
    ]


@router.get("/novel/styles", summary="获取可用写作风格")
async def list_novel_styles():
    """返回所有可用的写作风格列表"""
    style_descs = {
        StyleType.DESCRIPTIVE: "注重描写的叙事风格",
        StyleType.CONCISE: "简洁明快的叙事风格",
        StyleType.POETIC: "富有诗意的叙事风格",
        StyleType.DIALOGUE_HEAVY: "对话为主的叙事风格",
        StyleType.STREAM_OF_CONSCIOUSNESS: "意识流叙事风格",
        StyleType.REPORTER: "记者视角的叙事风格",
    }
    return [
        {"value": st.value, "label": st.value.replace("_", " ").title(), "desc": style_descs.get(st, "")}
        for st in StyleType
    ]


@router.get("/{key_path:path}", summary="获取指定配置项")
async def get_config_item(
    key_path: str,
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """通过点分隔路径获取配置项，如 database/url"""
    value = hub.get(key_path)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Config key '{key_path}' not found")
    return {"key": key_path, "value": value}
