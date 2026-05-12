"""
Health checker utility — wraps HealthService for direct use.

Replaces HealthCheckerAgent (deprecated). API and Coordinator
should call these functions directly instead of routing through
the agent layer.

@file: utils/health_checker.py
"""

from ai_novels.services.health_service import get_health_service
from ai_novels.utils import log_info, log_warn


def check_component_health(name: str) -> dict:
    """Check a single component's health via HealthService."""
    service = get_health_service()
    health = service.check_single(name)
    return health.to_dict() if hasattr(health, 'to_dict') else {"name": name, "status": str(health)}


def check_system_health() -> dict:
    """Run full system health check and return aggregated status."""
    service = get_health_service()
    return service.check_all()
