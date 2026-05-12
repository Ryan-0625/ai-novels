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

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai_novels.api.dependencies import get_config_dep, get_config_hub_dep, get_db_session
from ai_novels.config.app_config import AppConfig
from ai_novels.config.hub import ConfigHub
from ai_novels.services.health_service import HealthService, get_health_service


def _find_config_dir() -> str:
    """从多个候选路径中查找 config 目录"""
    candidates = [
        os.path.join(os.getcwd(), "config"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "config"),
    ]
    for p in candidates:
        resolved = os.path.realpath(p)
        if os.path.isdir(resolved):
            return resolved
    return os.path.join(os.getcwd(), "config")


def _load_connections() -> Dict[str, Dict[str, Any]]:
    """从 config 文件加载组件连接信息"""
    base_dir = _find_config_dir()
    connections: Dict[str, Dict[str, Any]] = {}

    # 加载数据库连接
    db_path = os.path.join(base_dir, "database.json")
    try:
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                db_cfg = json.load(f).get("database", {})
            for key in ["mysql", "neo4j", "mongodb", "chromadb"]:
                conn = db_cfg.get(key, {})
                # 过滤掉 password 等敏感字段
                safe = {k: v for k, v in conn.items() if k != "password"}
                if safe:
                    connections[key] = safe
    except Exception:
        pass

    # 加载消息队列连接
    msg_path = os.path.join(base_dir, "messaging.json")
    try:
        if os.path.exists(msg_path):
            with open(msg_path, "r", encoding="utf-8") as f:
                msg_cfg = json.load(f).get("messaging", {})
            rmq = msg_cfg.get("rocketmq", {})
            safe = {k: v for k, v in rmq.items() if k != "password"}
            connections["rocketmq"] = safe
    except Exception:
        pass

    return connections

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


@router.get("/system-health", summary="获取系统组件健康状态（完整信息）")
async def system_health(
    health_service: HealthService = Depends(get_health_service),
) -> Dict[str, Any]:
    """返回系统各组件的详细健康状态"""
    result = {
        "overall_status": "healthy",
        "components": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": _load_connections(),
    }
    for name in ["mysql", "neo4j", "mongodb", "chromadb", "rocketmq_producer", "rocketmq_consumer", "ollama"]:
        try:
            health = health_service.check_single(name)
            comp_dict = health.to_dict() if hasattr(health, 'to_dict') else {"status": health.value if hasattr(health, 'value') else health}
            result["components"][name] = comp_dict
            if comp_dict.get("status") in ("unhealthy", "error"):
                result["overall_status"] = "degraded"
        except Exception as e:
            result["components"][name] = {"name": name, "status": "error", "detail": str(e)}
            result["overall_status"] = "degraded"
    return result


@router.get("/health/component/{component_name}", summary="获取单个组件健康状态")
async def component_health(
    component_name: str = Path(..., description="组件名称"),
    health_service: HealthService = Depends(get_health_service),
) -> Dict[str, Any]:
    """返回指定组件的健康状态"""
    try:
        health = health_service.check_single(component_name)
        comp_dict = health.to_dict() if hasattr(health, 'to_dict') else {"status": health.value if hasattr(health, 'value') else health}
        comp_dict["component"] = component_name
        return comp_dict
    except Exception as e:
        return {"component": component_name, "status": "error", "detail": str(e)}


@router.get("/health/check", summary="执行紧急健康检查")
async def immediate_health_check(
    health_service: HealthService = Depends(get_health_service),
) -> Dict[str, Any]:
    """对系统所有组件执行即时健康检查"""
    results = {}
    overall = "healthy"
    for name in ["database", "messaging", "llm", "vector_store"]:
        try:
            health = health_service.check_single(name)
            comp_dict = health.to_dict() if hasattr(health, 'to_dict') else {"status": health.value if hasattr(health, 'value') else health}
            results[name] = comp_dict
            if comp_dict.get("status") in ("unhealthy", "error"):
                overall = "degraded"
        except Exception as e:
            results[name] = {"name": name, "status": "error", "detail": str(e)}
            overall = "degraded"
    return {"status": overall, "checks": results, "timestamp": datetime.now(timezone.utc).isoformat()}
