"""
健康检查与指标端点

提供企业级可观测性接口：
- /health: 综合健康检查
- /health/live: Kubernetes liveness probe
- /health/ready: Kubernetes readiness probe
- /metrics: Prometheus 指标

@file: api/health_routes.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.api.dependencies import get_config_dep, get_config_hub_dep, get_db_session
from deepnovel.config.app_config import AppConfig
from deepnovel.config.hub import ConfigHub

router = APIRouter(tags=["health"])


@router.get("/health", summary="综合健康检查")
async def health_check(
    session: AsyncSession = Depends(get_db_session),
    config: AppConfig = Depends(get_config_dep),
    hub: ConfigHub = Depends(get_config_hub_dep),
) -> Dict[str, Any]:
    """返回系统各组件健康状态"""
    checks = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": config.app_version,
        "environment": config.environment,
        "checks": {},
    }

    # ConfigHub 状态（测试时 hub 可能是 MagicMock）
    try:
        checks["config_hub_ready"] = hub.is_initialized
    except AttributeError:
        checks["config_hub_ready"] = False

    # 数据库健康检查
    try:
        await session.execute(text("SELECT 1"))
        checks["checks"]["database"] = "ok"
    except Exception as e:
        checks["checks"]["database"] = f"error: {e}"
        checks["status"] = "degraded"

    return checks


@router.get("/health/live", summary="存活探针")
async def liveness_probe() -> Dict[str, str]:
    """Kubernetes liveness probe — 仅检查进程是否存活"""
    return {"status": "alive"}


@router.get("/health/ready", summary="就绪探针")
async def readiness_probe(
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Kubernetes readiness probe — 检查依赖是否就绪"""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": f"error: {e}"}


@router.get("/metrics", summary="Prometheus 指标")
async def metrics() -> Dict[str, Any]:
    """返回 Prometheus 格式的应用指标（简化版）"""
    try:
        import psutil

        process = psutil.Process()
        memory = process.memory_info()

        return {
            "app": {
                "uptime_seconds": int(datetime.now(timezone.utc).timestamp() - process.create_time()),
                "memory_rss_bytes": memory.rss,
                "memory_vms_bytes": memory.vms,
            },
            "system": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
            },
        }
    except ImportError:
        return {
            "app": {"uptime_seconds": 0, "note": "psutil not installed"},
            "system": {"note": "psutil not installed"},
        }
