"""
Agent管理API路由

Step 11: Agent管理接口（列出Agent/获取详情/更新配置/查看指标）

@file: api/routes/agent_routes.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from deepnovel.api.dependencies import get_config_hub_dep
from deepnovel.config.hub import ConfigHub

router = APIRouter(prefix="/agents", tags=["agents"])


# ---- 请求/响应模型 ----


class AgentInfoResponse(BaseModel):
    """Agent信息响应"""

    name: str
    description: str
    status: str
    version: str = "1.0"
    capabilities: List[str] = []


class AgentConfigUpdateRequest(BaseModel):
    """Agent配置更新请求"""

    config: Dict[str, Any]


class AgentConfigUpdateResponse(BaseModel):
    """Agent配置更新响应"""

    agent_name: str
    success: bool
    message: str


class AgentMetricsResponse(BaseModel):
    """Agent指标响应"""

    agent_name: str
    total_tasks: int = 0
    success_rate: float = 0.0
    avg_response_time_ms: Optional[float] = None
    error_count: int = 0
    last_active: Optional[str] = None


# ---- 依赖注入 ----


def get_task_orchestrator(request: Request):
    """获取 TaskOrchestrator 实例"""
    orch = getattr(request.app.state, "task_orchestrator", None)
    if orch is None:
        raise HTTPException(status_code=503, detail="TaskOrchestrator not initialized")
    return orch


# ---- API 端点 ----


@router.get("", response_model=List[AgentInfoResponse], summary="列出所有Agent")
async def list_agents(
    orchestrator=Depends(get_task_orchestrator),
):
    """列出所有已注册的Agent"""
    workers = orchestrator.list_workers()
    return [
        AgentInfoResponse(
            name=w["name"],
            description=f"Agent {w['name']}",
            status="idle" if w.get("idle", True) else "busy",
            capabilities=["text_generation"],
        )
        for w in workers
    ]


@router.get("/{agent_name}", response_model=AgentInfoResponse, summary="获取Agent详情")
async def get_agent_detail(
    agent_name: str,
    orchestrator=Depends(get_task_orchestrator),
):
    """获取指定Agent的详细信息"""
    workers = orchestrator.list_workers()
    for w in workers:
        if w["name"] == agent_name:
            return AgentInfoResponse(
                name=w["name"],
                description=f"Agent {w['name']}",
                status="idle" if w.get("idle", True) else "busy",
                capabilities=["text_generation"],
            )
    raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")


@router.patch("/{agent_name}/config", response_model=AgentConfigUpdateResponse, summary="更新Agent配置")
async def update_agent_config(
    agent_name: str,
    req: AgentConfigUpdateRequest,
    hub: ConfigHub = Depends(get_config_hub_dep),
):
    """更新Agent配置"""
    try:
        for key, value in req.config.items():
            hub.set(f"agent.{agent_name}.{key}", value)
        return AgentConfigUpdateResponse(
            agent_name=agent_name,
            success=True,
            message=f"Config updated for agent '{agent_name}'",
        )
    except Exception as e:
        return AgentConfigUpdateResponse(
            agent_name=agent_name,
            success=False,
            message=str(e),
        )


@router.get("/{agent_name}/metrics", response_model=AgentMetricsResponse, summary="获取Agent运行指标")
async def get_agent_metrics(
    agent_name: str,
    orchestrator=Depends(get_task_orchestrator),
):
    """获取Agent的运行时指标"""
    stats = orchestrator.get_stats()
    workers = orchestrator.list_workers()
    total_tasks = stats.get("submitted", 0)
    completed = stats.get("completed", 0)
    failed = stats.get("failed", 0)
    success_rate = completed / max(total_tasks, 1)

    # 查找对应worker
    worker_metrics = {}
    for w in workers:
        if w["name"] == agent_name:
            worker_metrics = w.get("metrics", {})
            break

    return AgentMetricsResponse(
        agent_name=agent_name,
        total_tasks=worker_metrics.get("total_tasks", total_tasks),
        success_rate=worker_metrics.get("success_rate", success_rate),
        avg_response_time_ms=worker_metrics.get("avg_response_time_ms"),
        error_count=worker_metrics.get("error_count", failed),
        last_active=worker_metrics.get("last_active"),
    )
