"""
任务管理API路由

Step 11: 任务管理接口（列出任务/查询状态/暂停/恢复/取消）
基于 TaskOrchestrator 实现

@file: api/routes/task_routes.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ai_novels.agents.task_orchestrator import TaskPriority
from ai_novels.api.controllers import status_controller, task_controller
from ai_novels.api.dependencies import get_config_hub_dep
from ai_novels.config.hub import ConfigHub
from ai_novels.database.engine import get_session
from ai_novels.models.task import Task, TaskStatus
from ai_novels.repositories.task_repository import TaskRepository

_task_repo = TaskRepository()

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---- 请求/响应模型 ----


class TaskListItem(BaseModel):
    """任务列表项"""

    task_id: str
    agent_name: str
    status: str
    priority: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: List[TaskListItem]
    total: int


class TaskDetailResponse(BaseModel):
    """任务详情响应"""

    task_id: str
    agent_name: str
    status: str
    priority: str
    title: Optional[str] = None
    genre: Optional[str] = None
    style: Optional[str] = None
    target_audience: Optional[str] = None
    description: Optional[str] = None
    chapters: Optional[int] = None
    word_count_per_chapter: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    stage_statuses: Optional[Dict[str, Any]] = None


class TaskCreateRequest(BaseModel):
    """任务创建请求"""

    agent_name: str = Field(..., description="执行任务的 Agent 名称")
    payload: Dict[str, Any] = Field(default_factory=dict, description="任务负载")
    priority: str = Field(default="NORMAL", description="优先级: CRITICAL/HIGH/NORMAL/LOW/BACKGROUND")
    correlation_id: Optional[str] = Field(default=None, description="关联ID")
    timeout: int = Field(default=300, description="超时时间（秒）")


class TaskCreateResponse(BaseModel):
    """任务创建响应"""

    task_id: str
    agent_name: str
    status: str
    message: str


class TaskActionRequest(BaseModel):
    """任务操作请求"""

    action: str = Field(..., description="操作: pause/resume/cancel")


class TaskActionResponse(BaseModel):
    """任务操作响应"""

    task_id: str
    action: str
    success: bool
    message: str


class WorkflowDefResponse(BaseModel):
    """工作流定义响应"""

    name: str
    description: str
    stages: List[str]


# ---- 依赖注入 ----


def get_task_orchestrator(request: Request):
    """获取 TaskOrchestrator 实例"""
    orch = getattr(request.app.state, "task_orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not initialized")
    return orch


# ---- API 端点 ----


@router.post("", response_model=TaskCreateResponse, summary="创建任务")
async def create_task(
    req: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    orchestrator=Depends(get_task_orchestrator),
):
    """提交新任务

    当 agent_name='coordinator' 时使用完整的 DAG 小说生成工作流，
    否则通过 TaskOrchestrator 调度。
    """
    # coordinator 任务：使用 TaskController 的完整 DAG 工作流
    if req.agent_name == "coordinator":
        payload = req.payload or {}

        # 将新请求格式（payload 字典）转为兼容对象
        class SimpleRequest:
            user_id = payload.get("user_id", "default")
            task_type = payload.get("task_type", "novel")
            genre = payload.get("genre", "")
            title = payload.get("title", "")
            description = payload.get("description", "")
            chapters = payload.get("chapters", 5)
            word_count_per_chapter = payload.get("word_count_per_chapter", 2000)
            style = payload.get("style", "light")
            target_audience = payload.get("target_audience", "general")
            language = payload.get("language", "zh-CN")

        result = await task_controller.create_task(SimpleRequest(), background_tasks)
        return TaskCreateResponse(
            task_id=result["task_id"],
            agent_name="coordinator",
            status="accepted",
            message=result["message"],
        )

    # 普通任务：通过 TaskOrchestrator 调度
    try:
        priority = TaskPriority[req.priority.upper()]
    except KeyError:
        priority = TaskPriority.NORMAL

    task_id = await orchestrator.submit(
        agent_name=req.agent_name,
        payload=req.payload,
        priority=priority,
        correlation_id=req.correlation_id,
        timeout=req.timeout,
    )

    return TaskCreateResponse(
        task_id=task_id,
        agent_name=req.agent_name,
        status="submitted",
        message=f"Task submitted successfully to agent '{req.agent_name}'",
    )


@router.get("", response_model=TaskListResponse, summary="获取任务列表")
async def list_tasks(
    orchestrator=Depends(get_task_orchestrator),
):
    """列出所有任务状态"""
    tasks = []

    # 优先从队列获取真实任务
    try:
        all_tasks = orchestrator.list_tasks()
        for t in all_tasks:
            tasks.append(
                TaskListItem(
                    task_id=t["task_id"],
                    agent_name=t["agent_name"],
                    status=t.get("status", "pending"),
                    priority=str(t.get("priority", "normal")),
                    created_at=str(t.get("enqueue_time", "")),
                )
            )
    except Exception:
        pass

    # 补充 worker 当前执行的任务
    try:
        workers = orchestrator.list_workers()
        for w in workers:
            current = w.get("current_task")
            if current and current != "idle" and not any(t.task_id == current for t in tasks):
                tasks.append(
                    TaskListItem(
                        task_id=current,
                        agent_name=w["name"],
                        status="running",
                        priority="normal",
                        created_at="",
                    )
                )
    except Exception:
        pass

    # 合并 DB 中的任务（coordinator DAG 任务）
    try:
        async with get_session() as session:
            db_tasks = await _task_repo.get_all(session, limit=10000)
        for t in db_tasks:
            if not any(x.task_id == t.id for x in tasks):
                tasks.append(
                    TaskListItem(
                        task_id=t.id,
                        agent_name="coordinator",
                        status=t.status,
                        priority="normal",
                        created_at=str(t.created_at) if t.created_at else "",
                        started_at=str(t.started_at) if t.started_at else "",
                        completed_at=str(t.completed_at) if t.completed_at else "",
                    )
                )
    except Exception:
        pass

    return TaskListResponse(tasks=tasks, total=len(tasks))


@router.get("/{task_id}", response_model=TaskDetailResponse, summary="获取任务详情")
async def get_task_detail(
    task_id: str,
    orchestrator=Depends(get_task_orchestrator),
):
    """获取指定任务的详细信息"""
    # 先查 orchestator 结果
    result = orchestrator.get_result_nowait(task_id)
    if result is not None:
        return TaskDetailResponse(
            task_id=task_id,
            agent_name="",
            status="completed",
            priority="normal",
            result=result if isinstance(result, dict) else {"output": str(result)},
        )

    # 再查 DB 中的任务（coordinator DAG 任务）
    try:
        async with get_session() as session:
            db_task = await _task_repo.get_by_id(session, task_id)
        if db_task:
            stage_statuses = {}
            for idx, log_entry in enumerate(db_task.logs or []):
                stage = log_entry.get("stage", f"step_{idx}")
                stage_statuses[stage] = {"status": log_entry.get("status", "unknown")}
            return TaskDetailResponse(
                task_id=task_id,
                agent_name="coordinator",
                status=db_task.status,
                priority="normal",
                title=db_task.title,
                genre=db_task.genre,
                style=db_task.style,
                target_audience=db_task.target_audience,
                description=db_task.description,
                chapters=db_task.chapters,
                word_count_per_chapter=db_task.word_count_per_chapter,
                result={
                    "progress": db_task.progress,
                    "current_stage": db_task.current_stage,
                    "stage_statuses": stage_statuses,
                },
                error=db_task.error,
                created_at=str(db_task.created_at) if db_task.created_at else None,
                started_at=str(db_task.started_at) if db_task.started_at else None,
                completed_at=str(db_task.completed_at) if db_task.completed_at else None,
                stage_statuses=stage_statuses,
            )
    except Exception:
        pass

    # 任务仍在队列中
    return TaskDetailResponse(
        task_id=task_id,
        agent_name="",
        status="pending",
        priority="normal",
    )


@router.post("/{task_id}/action", response_model=TaskActionResponse, summary="执行任务操作")
async def task_action(
    task_id: str,
    req: TaskActionRequest,
    orchestrator=Depends(get_task_orchestrator),
):
    """对任务执行操作（暂停/恢复/取消）"""
    action = req.action.lower()

    if action == "cancel":
        # 先尝试 orchestator 取消
        success = await orchestrator.cancel(task_id)
        if not success:
            try:
                await task_controller.cancel_task(task_id)
                success = True
            except (HTTPException, Exception):
                success = False
        return TaskActionResponse(
            task_id=task_id,
            action=action,
            success=success,
            message="Task cancelled" if success else "Task not found or already completed",
        )

    if action == "pause":
        # 先尝试 orchestator 暂停
        success = await orchestrator.pause(task_id)
        if not success:
            try:
                async with get_session() as session:
                    t = await _task_repo.get_by_id(session, task_id)
                    if t and t.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        t.status = TaskStatus.PAUSED
                        await _task_repo.update(session, t)
                        success = True
            except Exception:
                pass
        return TaskActionResponse(
            task_id=task_id,
            action=action,
            success=success,
            message="Task paused" if success else "Task not found or already completed",
        )

    if action == "resume":
        # 先尝试 orchestator 恢复
        success = await orchestrator.resume(task_id)
        if not success:
            try:
                async with get_session() as session:
                    t = await _task_repo.get_by_id(session, task_id)
                    if t and t.status == TaskStatus.PAUSED:
                        t.status = TaskStatus.RUNNING
                        await _task_repo.update(session, t)
                        success = True
            except Exception:
                pass
        return TaskActionResponse(
            task_id=task_id,
            action=action,
            success=success,
            message="Task resumed" if success else "Task not paused or not found",
        )

    return TaskActionResponse(
        task_id=task_id,
        action=action,
        success=False,
        message=f"Unknown action '{action}'",
    )


@router.get("/{task_id}/generation/progress", summary="获取任务生成进度")
async def get_generation_progress(
    task_id: str,
    orchestrator=Depends(get_task_orchestrator),
):
    """获取小说生成任务的实时进度信息"""
    # 先查 orchestator 结果
    result = orchestrator.get_result_nowait(task_id)
    if result is not None and isinstance(result, dict):
        return {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
            "chapters": result.get("chapters", {}),
            "stage_statuses": result.get("stage_statuses", {}),
        }

    # 再查 DB 中的任务
    try:
        async with get_session() as session:
            db_task = await _task_repo.get_by_id(session, task_id)
        if db_task:
            stage_statuses = {}
            for idx, log_entry in enumerate(db_task.logs or []):
                stage = log_entry.get("stage", f"step_{idx}")
                stage_statuses[stage] = {"status": log_entry.get("status", "unknown")}
            elapsed_seconds = 0
            if db_task.started_at:
                elapsed_seconds = max(0, (datetime.now(timezone.utc) - db_task.started_at).total_seconds())
            speed_wpm = None
            eta_seconds = None
            target_words = (db_task.word_count_per_chapter or 2000) * (db_task.chapters or 5)
            current_progress = db_task.progress / 100.0
            total_words = int(target_words * current_progress) if current_progress > 0 else 0
            if elapsed_seconds > 5 and total_words > 0:
                speed_wpm = round((total_words / elapsed_seconds) * 60, 1)
                remaining = max(0, target_words - total_words)
                if speed_wpm > 0:
                    eta_seconds = int(remaining / (speed_wpm / 60))
            return {
                "task_id": task_id,
                "status": db_task.status,
                "progress": db_task.progress,
                "current_stage": db_task.current_stage,
                "stage_statuses": stage_statuses,
                "elapsed_seconds": elapsed_seconds,
                "speed_wpm": speed_wpm,
                "eta_seconds": eta_seconds,
                "target_words": target_words,
                "total_words": total_words,
            }
    except Exception:
        pass

    return {
        "task_id": task_id,
        "status": "running",
        "progress": 0,
        "chapters": {},
        "stage_statuses": {},
    }


@router.get("/{task_id}/chapters", summary="获取任务章节列表")
async def get_chapters(task_id: str):
    """获取指定任务的所有章节列表"""
    from fastapi import HTTPException
    try:
        result = await status_controller.get_chapters(task_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/chapters/{chapter_num}", summary="获取指定章节内容")
async def get_chapter_content(task_id: str, chapter_num: int):
    """获取指定任务的指定章节完整内容"""
    from fastapi import HTTPException
    try:
        result = await status_controller.get_chapter_content(task_id, chapter_num)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflows/definitions", response_model=List[WorkflowDefResponse], summary="获取工作流定义列表")
async def list_workflows(
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """列出所有已注册的工作流定义"""
    orch = getattr(hub, "_orchestrator", None)
    if orch is None:
        # 返回默认工作流
        return [
            WorkflowDefResponse(
                name="novel_generation",
                description="小说生成完整工作流",
                stages=["需求分析", "大纲规划", "角色生成", "世界构建", "内容生成", "质量检查", "文本润色"],
            )
        ]
    workflows = orch.list_workflows() if hasattr(orch, "list_workflows") else []
    return [
        WorkflowDefResponse(
            name=w.get("name", "unknown"),
            description=w.get("description", ""),
            stages=w.get("stages", []),
        )
        for w in workflows
    ]
