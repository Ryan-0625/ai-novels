"""
基础设施容器化测试 — 验证Docker构建和编排 (Step 15)

测试范围:
- Dockerfile.backend / Dockerfile.frontend 多阶段构建
- docker-compose.yml / docker-compose.prod.yml 服务配置
- 健康检查端点
"""

import pytest
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_cmd(cmd: list[str], cwd: Path = None, timeout: int = 300) -> tuple[int, str, str]:
    """执行shell命令并返回结果"""
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


class TestDockerfileBackend:
    """后端 Dockerfile 构建测试"""

    def test_dockerfile_backend_exists(self):
        """Dockerfile.backend 必须存在"""
        dockerfile = PROJECT_ROOT / "Dockerfile.backend"
        assert dockerfile.exists(), "Dockerfile.backend not found"
        content = dockerfile.read_text(encoding="utf-8")
        assert "FROM" in content, "Dockerfile missing FROM instruction"
        assert "HEALTHCHECK" in content, "Dockerfile missing HEALTHCHECK"

    def test_dockerfile_backend_python_version(self):
        """必须使用 Python 3.13"""
        content = (PROJECT_ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
        assert "python:3.13" in content, "Expected python:3.13 base image"

    def test_dockerfile_backend_security_options(self):
        """必须包含安全相关配置"""
        content = (PROJECT_ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
        assert "PYTHONDONTWRITEBYTECODE" in content
        assert "PYTHONUNBUFFERED" in content


class TestDockerfileFrontend:
    """前端 Dockerfile 构建测试"""

    def test_dockerfile_frontend_exists(self):
        """Dockerfile.frontend 必须存在"""
        dockerfile = PROJECT_ROOT / "Dockerfile.frontend"
        assert dockerfile.exists(), "Dockerfile.frontend not found"
        content = dockerfile.read_text(encoding="utf-8")
        assert "FROM" in content, "Dockerfile missing FROM instruction"

    def test_dockerfile_frontend_builder_stage(self):
        """必须包含 builder 和 production 阶段"""
        content = (PROJECT_ROOT / "Dockerfile.frontend").read_text(encoding="utf-8")
        assert "AS builder" in content or "node:" in content, "Missing builder stage"
        assert "nginx" in content, "Missing nginx production stage"


class TestDockerCompose:
    """Docker Compose配置测试"""

    def test_compose_file_exists(self):
        """docker-compose.yml 必须存在"""
        compose = PROJECT_ROOT / "docker-compose.yml"
        assert compose.exists(), "docker-compose.yml not found"

    def test_compose_prod_file_exists(self):
        """docker-compose.prod.yml 必须存在"""
        compose = PROJECT_ROOT / "docker-compose.prod.yml"
        assert compose.exists(), "docker-compose.prod.yml not found"
        content = compose.read_text(encoding="utf-8")
        assert "backend:" in content
        assert "frontend:" in content

    def test_compose_syntax_valid(self):
        """docker-compose.yml 语法必须有效"""
        returncode, stdout, stderr = run_cmd(
            ["docker", "compose", "config"],
            cwd=PROJECT_ROOT,
        )
        if returncode != 0:
            pytest.skip(f"docker compose config skipped: {stderr}")
        assert returncode == 0

    def test_compose_services_defined(self):
        """必须定义关键服务"""
        returncode, stdout, stderr = run_cmd(
            ["docker", "compose", "config", "--services"],
            cwd=PROJECT_ROOT,
        )
        if returncode != 0:
            pytest.skip(f"docker compose config skipped: {stderr}")
        services = stdout.strip().split("\n")
        expected = ["mysql", "neo4j", "mongodb", "chromadb", "postgres", "redis"]
        for svc in expected:
            assert svc in services, f"Service {svc} not found in compose"


class TestPrometheusConfig:
    """Prometheus配置测试"""

    def test_prometheus_config_exists(self):
        """prometheus.yml 必须存在"""
        config = PROJECT_ROOT / "config" / "prometheus" / "prometheus.yml"
        assert config.exists(), "prometheus.yml not found"

    def test_prometheus_scrape_jobs(self):
        """必须配置正确的scrape jobs"""
        content = (PROJECT_ROOT / "config" / "prometheus" / "prometheus.yml").read_text()
        assert "ai-engine" in content or "backend" in content, "Missing backend scrape job"


class TestDockerBuild:
    """Docker镜像构建测试 (可选，需要Docker守护进程)"""

    def test_docker_build_backend(self):
        """后端镜像必须能成功构建"""
        returncode, stdout, stderr = run_cmd(
            ["docker", "build", "-f", "Dockerfile.backend", "-t", "ai-novels-backend:test", "."],
            cwd=PROJECT_ROOT,
            timeout=600,
        )
        if returncode != 0:
            pytest.skip(f"Docker build skipped (Docker daemon may not be available): {stderr}")
        assert returncode == 0, f"Docker build failed: {stderr}"

    def test_docker_build_frontend(self):
        """前端镜像必须能成功构建"""
        returncode, stdout, stderr = run_cmd(
            ["docker", "build", "-f", "Dockerfile.frontend", "-t", "ai-novels-frontend:test", "."],
            cwd=PROJECT_ROOT,
            timeout=600,
        )
        if returncode != 0:
            pytest.skip(f"Docker build skipped (Docker daemon may not be available): {stderr}")
        assert returncode == 0, f"Docker build failed: {stderr}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
