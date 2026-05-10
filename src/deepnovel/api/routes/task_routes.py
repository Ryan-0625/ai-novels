"""
任务管理API路由

Step 11: 任务管理接口（列出任务/查询状态/暂停/恢复/取消）
基于 TaskOrchestrator 实现

@file: api/routes/task_routes.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deepnovel.agents.task_orchestrator import TaskPriority
from deepnovel.api.dependencies import get_config_hub_dep
from deepnovel.config.hub import ConfigHub

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
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


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
    orchestrator=Depends(get_task_orchestrator),
):
    """提交新任务到 TaskOrchestrator"""
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

    # 兜底：从 stats 获取（向后兼容旧 mock）
    if not tasks:
        try:
            stats = orchestrator.get_stats()
            for name, info in stats.get("workers", {}).items():
                tasks.append(
                    TaskListItem(
                        task_id=info.get("current_task") or "idle",
                        agent_name=name,
                        status="running" if not info.get("idle", True) else "idle",
                        priority="normal",
                        created_at="",
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
    result = orchestrator.get_result_nowait(task_id)
    if result is not None:
        return TaskDetailResponse(
            task_id=task_id,
            agent_name="",
            status="completed",
            priority="normal",
            result=result if isinstance(result, dict) else {"output": str(result)},
        )

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
        success = await orchestrator.cancel(task_id)
        return TaskActionResponse(
            task_id=task_id,
            action=action,
            success=success,
            message="Task cancelled" if success else "Task not found or already completed",
        )

    # pause/resume 暂未实现
    return TaskActionResponse(
        task_id=task_id,
        action=action,
        success=False,
        message=f"Action '{action}' not yet supported in this version",
    )


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
