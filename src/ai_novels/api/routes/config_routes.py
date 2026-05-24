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
    # 风格标签 — 统一中文二字名称
    style_labels = {
        "light": "轻松",
        "serious": "严肃",
        "humor": "幽默",
        "passion": "热血",
        "suspense": "悬疑",
        "descriptive": "细腻",
        "concise": "简洁",
        "poetic": "诗意",
        "dialogue_heavy": "对话",
        "stream_of_consciousness": "意识流",
        "reporter": "纪实",
    }
    style_descs = {
        "light": "轻松愉快的叙事风格",
        "serious": "庄重严谨的叙事风格",
        "humor": "诙谐幽默的叙事风格",
        "passion": "激情澎湃的叙事风格",
        "suspense": "紧张刺激的叙事风格",
        "descriptive": "注重描写的叙事风格",
        "concise": "简洁明快的叙事风格",
        "poetic": "富有诗意的叙事风格",
        "dialogue_heavy": "以对话为主的叙事风格",
        "stream_of_consciousness": "意识流叙事风格",
        "reporter": "记者视角的叙事风格",
    }
    # 合并前端常用风格与后端 StyleType
    seen = set()
    result = []
    for st in StyleType:
        val = st.value
        if val in seen:
            continue
        seen.add(val)
        result.append({
            "value": val,
            "label": style_labels.get(val, val),
            "desc": style_descs.get(val, ""),
        })
    # 补充前端独有的风格（不在 StyleType 中）
    for val in ["light", "serious", "humor", "passion", "suspense"]:
        if val not in seen:
            seen.add(val)
            result.append({
                "value": val,
                "label": style_labels.get(val, val),
                "desc": style_descs.get(val, ""),
            })
    return result


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
