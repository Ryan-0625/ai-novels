"""
API路由定义

@file: api/routes.py
@date: 2026-03-12
@version: 1.0.0
@description: API路由定义
"""

import sys
import os

# 添加src目录到路径 - 用于支持 uvicorn reload 模式
cwd = os.getcwd()
src_dir = os.path.join(cwd, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import uuid
import time
from deepnovel.utils import log_error

# 导入控制器
from .controllers import (
    task_controller,
    status_controller,
    config_controller,
    health_controller
)

router = APIRouter()

# ============================================================================
# 请求/响应模型 (Step 48)
# ============================================================================

class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    user_id: str = Field(..., description="用户ID")
    task_type: str = Field(..., description="任务类型: novel/generation/short")
    genre: Optional[str] = Field(None, description="类型: romance/sci-fi/fantasy")
    title: Optional[str] = Field(None, description="小说标题")
    description: Optional[str] = Field(None, description="小说描述")
    chapters: Optional[int] = Field(None, description="章节数量")
    word_count_per_chapter: Optional[int] = Field(None, description="每章字数")
    style: Optional[str] = Field(None, description="写作风格")
    target_audience: Optional[str] = Field(None, description="目标受众")

class TaskCreateResponse(BaseModel):
    """创建任务响应"""
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    progress: float
    current_stage: str
    completed_agents: List[str]
    total_agents: int
    start_time: str
    estimated_end_time: Optional[str]
    # Additional task details
    user_id: Optional[str] = None
    task_type: Optional[str] = None
    genre: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    chapters: Optional[int] = None
    word_count_per_chapter: Optional[int] = None
    style: Optional[str] = None
    target_audience: Optional[str] = None

class TaskLogResponse(BaseModel):
    """任务日志响应"""
    task_id: str
    logs: List[Dict[str, Any]]

class TaskCancelRequest(BaseModel):
    """取消任务请求"""
    task_id: str

class TaskCancelResponse(BaseModel):
    """取消任务响应"""
    task_id: str
    status: str
    message: str

class ChapterListResponse(BaseModel):
    """章节列表响应"""
    task_id: str
    chapters: List[Dict[str, Any]]
    total: int

class ChapterContentResponse(BaseModel):
    """章节内容响应"""
    chapter_id: str
    task_id: str
    chapter_num: int
    title: str
    content: str
    word_count: int
    created_at: str

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str
    components: Dict[str, Dict[str, Any]]

class ConfigUpdateRequest(BaseModel):
    """更新配置请求"""
    config_key: str
    config_value: Dict[str, Any]

class ConfigUpdateResponse(BaseModel):
    """更新配置响应"""
    success: bool
    message: str

class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    has_more: bool

# ============================================================================
# API端点 (Step 48)
# ============================================================================

@router.post("/tasks", response_model=TaskCreateResponse, summary="创建小说生成任务")
async def create_task(
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks
):
    """
    创建一个新的小说生成任务

    - **user_id**: 用户ID
    - **task_type**: 任务类型 (novel/generation/short)
    - **genre**: 小说类型 ( romance/sci-fi/fantasy)
    - **title**: 小说标题
    - **description**: 小说描述
    - **chapters**: 预期章节数
    """
    result = await task_controller.create_task(request, background_tasks)
    return result

@router.get("/tasks/{task_id}", response_model=TaskStatusResponse, summary="获取任务状态")
async def get_task_status(task_id: str):
    """
    获取指定任务的详细状态

    - **task_id**: 任务ID
    """
    result = await status_controller.get_task_status(task_id)
    return result

@router.get("/tasks/{task_id}/health", response_model=HealthCheckResponse, summary="获取任务组件健康状态")
async def get_task_health(task_id: str):
    """
    获取任务相关组件的健康状态

    - **task_id**: 任务ID
    """
    result = await health_controller.get_task_health(task_id)
    return result

@router.get("/tasks/{task_id}/logs", response_model=TaskLogResponse, summary="获取任务日志")
async def get_task_logs(task_id: str, page: int = 1, page_size: int = 50):
    """
    获取任务执行日志

    - **task_id**: 任务ID
    - **page**: 页码
    - **page_size**: 每页数量
    """
    result = await status_controller.get_task_logs(task_id, page, page_size)
    return result

@router.get("/tasks/{task_id}/chapters", response_model=ChapterListResponse, summary="获取任务章节列表")
async def get_chapters(task_id: str):
    """
    获取指定任务的所有章节列表

    - **task_id**: 任务ID
    """
    try:
        result = await status_controller.get_chapters(task_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"get_chapters error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/{task_id}/chapters/{chapter_num}", response_model=ChapterContentResponse, summary="获取指定章节内容")
async def get_chapter_content(task_id: str, chapter_num: int):
    """
    获取指定任务的指定章节完整内容

    - **task_id**: 任务ID
    - **chapter_num**: 章节号
    """
    try:
        result = await status_controller.get_chapter_content(task_id, chapter_num)
        return result
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"get_chapter_content error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/cancel", response_model=TaskCancelResponse, summary="取消任务")
async def cancel_task(task_id: str, request: TaskCancelRequest):
    """
    取消指定的生成任务

    - **task_id**: 任务ID
    """
    result = await task_controller.cancel_task(task_id, request)
    return result

@router.get("/tasks", response_model=TaskListResponse, summary="获取任务列表")
async def list_tasks(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
):
    """
    获取任务列表（支持分页和过滤）

    - **user_id**: 用户ID（可选）
    - **status**: 任务状态（可选）
    - **page**: 页码
    - **page_size**: 每页数量
    """
    try:
        result = await task_controller.list_tasks(user_id, status, page, page_size)
        # 确保返回Pydantic模型
        return TaskListResponse(**result)
    except Exception as e:
        log_error(f"list_tasks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/update", response_model=ConfigUpdateResponse, summary="更新配置")
async def update_config(request: ConfigUpdateRequest):
    """
    更新系统配置

    - **config_key**: 配置键
    - **config_value**: 配置值
    """
    result = await config_controller.update_config(request)
    return result

@router.get("/config/{config_key}", response_model=Dict[str, Any], summary="获取配置")
async def get_config(config_key: str):
    """
    获取指定配置

    - **config_key**: 配置键
    """
    result = await config_controller.get_config(config_key)
    return result

@router.get("/stats", response_model=Dict[str, Any], summary="获取统计信息")
async def get_stats():
    """
    获取系统统计信息
    """
    result = await status_controller.get_stats()
    return result

@router.get("/agents", response_model=List[Dict[str, Any]], summary="获取智能体列表")
async def list_agents():
    """
    获取可用智能体列表
    """
    result = await status_controller.list_agents()
    return result


@router.get("/health", summary="获取系统健康状态")
async def get_system_health(deep_check: bool = False):
    """
    获取系统整体健康状态

    - **deep_check**: 是否执行深度检查（实际连接测试）
    """
    result = await health_controller.get_system_health(deep_check)
    return result


@router.get("/health/component/{component_name}", summary="获取单个组件健康状态")
async def get_component_health(component_name: str):
    """
    获取单个组件的健康状态

    - **component_name**: 组件名称 (mysql, neo4j, mongodb, chromadb, rocketmq_producer, rocketmq_consumer, ollama)
    """
    result = await health_controller.get_component_health(component_name)
    return result


@router.get("/health/check", summary="执行紧急健康检查")
async def immediate_health_check():
    """
    立即执行完整的健康检查（绕过缓存）
    """
    result = await health_controller.get_system_health(deep_check=True)
    return result


@router.get("/system-health", response_model=Dict[str, Any], summary="获取系统组件健康状态（完整信息）")
async def get_system_health_full(deep_check: bool = False):
    """
    获取系统组件健康状态的完整信息（用于监控页面）

    包含所有数据库、消息队列、LLM服务的详细连接信息和状态

    - **deep_check**: 是否执行深度检查（实际连接测试）
    """
    result = await health_controller.get_system_health(deep_check)

    # 添加连接信息到每个组件
    from deepnovel.config.manager import settings

    # 获取数据库配置
    db_config = settings.get_database("mysql")
    result["connections"] = {
        "mysql": {
            "host": db_config.get("host", "localhost"),
            "port": db_config.get("port", 3307),
            "database": db_config.get("database", "ai_novels"),
        } if db_config else {},
        "neo4j": settings.get_database("neo4j"),
        "mongodb": settings.get_database("mongodb"),
        "chromadb": settings.get_database("chromadb"),
        "rocketmq": settings.get("messaging", {}).get("producer", {}),
    }

    return result
