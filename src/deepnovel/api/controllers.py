"""
API控制器 - 业务逻辑层

@file: api/controllers.py
@date: 2026-03-12
@version: 1.0.0
@description: API控制器实现，包含业务逻辑分层
"""

from fastapi import HTTPException, BackgroundTasks
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid
import time
import json
import logging
import os
import sys
import importlib

# 确保logs目录存在
os.makedirs('logs', exist_ok=True)

# 配置日志 - 保留向后兼容的logger配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/server.log', encoding='utf-8'),
        logging.StreamHandler()
    ],
    force=True  # Force reconfigure to apply changes
)
logger = logging.getLogger('deepnovel.api.controllers')
logger.setLevel(logging.INFO)
logger.addHandler(logging.FileHandler('logs/server.log', encoding='utf-8'))

# 导入 HierarchicalLogger 用于分类日志
from deepnovel.utils import get_logger
hierarchical_logger = get_logger()

# 导入数据模型
from deepnovel.message.message import TaskRequest, TaskStatusUpdate, TaskResponse
from deepnovel.agents.coordinator import CoordinatorAgent, WorkflowState
from deepnovel.agents.agent_communicator import AgentCommunicator
from deepnovel.config.manager import ConfigManager, settings
from deepnovel.core.llm_router import get_llm_router
from deepnovel.utils import log_info, log_error, get_logger, LogContext

# 导入健康检查服务
from deepnovel.services.health_service import get_health_service, HealthService

# 导入持久化
from deepnovel.persistence.agent_persist import TaskPersistence
from deepnovel.persistence.manager import get_persistence_manager as get_pm


class TaskController:
    """任务控制器 - 处理任务创建、取消、查询等"""

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._task_stages: Dict[str, List[Dict[str, Any]]] = {}

    async def create_task(self, request, background_tasks: BackgroundTasks):
        """
        创建新任务

        Args:
            request: 创建任务请求
            background_tasks: 后台任务

        Returns:
            TaskCreateResponse: 任务创建响应
        """
        # 生成任务ID
        task_id = f"task_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

        # 创建任务记录
        task_record = {
            "task_id": task_id,
            "user_id": request.user_id,
            "task_type": request.task_type,
            "genre": request.genre,
            "title": request.title,
            "description": request.description,
            "chapters": request.chapters,
            "word_count_per_chapter": request.word_count_per_chapter,
            "style": request.style,
            "target_audience": request.target_audience,
            "status": "pending",
            "progress": 0.0,
            "current_stage": "initializing",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "error": None
        }

        # 保存任务
        self._tasks[task_id] = task_record
        self._task_stages[task_id] = []

        # 记录初始化阶段
        self._task_stages[task_id].append({
            "stage": "initializing",
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        })

        # 后台启动任务
        logger.info(f"Adding background task for {task_id}")
        hierarchical_logger.api(f"Adding background task for {task_id}", task_id=task_id)
        background_tasks.add_task(self._execute_task, task_id, request)
        logger.info(f"Background task added for {task_id}")
        hierarchical_logger.api(f"Background task added for {task_id}", task_id=task_id)

        return {
            "task_id": task_id,
            "status": "accepted",
            "message": f"Task {task_id} accepted and processing"
        }

    async def cancel_task(self, task_id: str, request):
        """
        取消任务

        Args:
            task_id: 任务ID
            request: 取消任务请求

        Returns:
            TaskCancelResponse: 任务取消响应
        """
        if task_id not in self._tasks:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        task = self._tasks[task_id]
        if task["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel task in {task['status']} state"
            )

        # 更新任务状态
        task["status"] = "cancelled"
        task["cancelled_at"] = datetime.now().isoformat()
        task["error"] = "Task cancelled by user"

        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": f"Task {task_id} has been cancelled"
        }

    async def list_tasks(self, user_id: Optional[str], status: Optional[str], page: int, page_size: int):
        """
        获取任务列表

        Args:
            user_id: 用户ID（可选）
            status: 任务状态（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            List[Dict]: 任务列表
        """
        tasks = list(self._tasks.values())

        # 过滤
        if user_id:
            tasks = [t for t in tasks if t["user_id"] == user_id]
        if status:
            tasks = [t for t in tasks if t["status"] == status]

        # 分页
        total = len(tasks)
        start = (page - 1) * page_size
        end = start + page_size
        tasks = tasks[start:end]

        return {
            "tasks": tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": end < total
        }

    async def _execute_task(self, task_id: str, request):
        """
        后台执行任务

        Args:
            task_id: 任务ID
            request: 任务请求
        """
        import asyncio
        import os

        # 确保logs目录存在
        os.makedirs('logs', exist_ok=True)

        # 更新任务状态
        logger.info(f"Starting _execute_task for {task_id}")
        hierarchical_logger.task(f"Starting _execute_task for {task_id}", task_id=task_id)
        self._tasks[task_id]["status"] = "running"
        self._tasks[task_id]["started_at"] = datetime.now().isoformat()

        try:
            # 初始化配置管理器和LLM路由
            logger.info(f"{task_id}: Initializing ConfigManager")
            hierarchical_logger.config(f"{task_id}: Initializing ConfigManager", task_id=task_id)
            config_manager = ConfigManager()
            config_paths = [
                "config/system.json",
                "config/database.json",
                "config/llm.json",
                "config/novel_settings.json",
                "config/agents.json",
                "config/messaging.json"
            ]
            logger.info(f"{task_id}: Loading config paths: {config_paths}")
            hierarchical_logger.config(f"{task_id}: Loading config paths", paths=config_paths)

            # 使用统一日志记录配置加载
            log_info(f"{task_id}: Loading configuration files")
            for config_file in config_paths:
                log_info(f"{task_id}: Loading config: {config_file}")

            config_manager.initialize(config_paths)
            log_info(f"{task_id}: All configuration files loaded successfully")

            # 初始化全局设置
            settings.initialize(config_manager)
            logger.info(f"{task_id}: Settings initialized")
            hierarchical_logger.config(f"{task_id}: Settings initialized", task_id=task_id)

            # 初始化LLM路由
            logger.info(f"{task_id}: Initializing LLM router")
            hierarchical_logger.llm(f"{task_id}: Initializing LLM router", task_id=task_id)
            llm_router = get_llm_router(config_manager)
            if not llm_router.is_initialized():
                hierarchical_logger.llm_error(f"{task_id}: Failed to initialize LLM router", task_id=task_id)
                log_error("Failed to initialize LLM router")
                # 继续执行但不使用LLM
            else:
                log_info(f"{task_id}: LLM router initialized with provider: {llm_router._default_provider}")
                hierarchical_logger.llm(f"{task_id}: LLM router initialized", task_id=task_id, provider=llm_router._default_provider)

            log_info(f"Task {task_id} initialized with LLM provider: {llm_router._default_provider if llm_router else 'none'}")
            logger.info(f"{task_id}: Starting workflow execution")
            hierarchical_logger.task(f"{task_id}: Starting workflow execution", task_id=task_id)

            # 初始化Coordinator
            coordinator = CoordinatorAgent()
            # 为可选字段提供默认值
            chapters = request.chapters or 5
            word_count = request.word_count_per_chapter or 2000
            style = request.style or "light"
            # 设置当前任务信息，供Agent获取task_id等参数
            coordinator._current_task = {
                "task_id": task_id,
                "title": request.title,
                "genre": request.genre,
                "chapters": chapters,
                "word_count_per_chapter": word_count,
                "style": style,
                "description": request.description,
                "user_id": request.user_id
            }
            logger.info(f"Coordinator initialized, workflow state: {coordinator._workflow_state.value}")
            hierarchical_logger.agent("Coordinator initialized", workflow_state=coordinator._workflow_state.value)

            # 构建用户请求
            user_request = {
                "timestamp": datetime.now().isoformat(),
                "original_request": request.description or f"Generate a {request.genre} novel",
                "intent": "generate_novel",
                "parameters": {
                    "genre": request.genre,
                    "length": "long" if chapters and chapters > 10 else "short",
                    "style": style,
                    "theme": request.title,
                    "chapters": chapters,
                    "word_count_per_chapter": request.word_count_per_chapter,
                }
            }

            # 开始工作流
            coordinator._workflow_state = WorkflowState.EXECUTING
            logger.info(f"Workflow state set to: {coordinator._workflow_state.value}")
            hierarchical_logger.agent("Workflow state set", state=coordinator._workflow_state.value)

            # DAG规划
            dag_plan = coordinator._plan_workflow(user_request)
            logger.info(f"DAG plan created: {dag_plan is not None}")
            hierarchical_logger.task("DAG plan created", has_plan=dag_plan is not None)
            if dag_plan.get("error"):
                logger.error(f"DAG planning error: {dag_plan.get('error')}")
                hierarchical_logger.task_error("DAG planning error", error=dag_plan.get('error'))
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = dag_plan["error"]
                return

            # 创建DAG
            dag = coordinator._build_dag(dag_plan)
            coordinator._dag = dag  # 设置coordinator的_dag属性
            coordinator._total_nodes = len(dag.nodes)
            logger.info(f"DAG built with {len(dag.nodes)} nodes")
            logger.info(f"DAG nodes: {list(dag.nodes.keys())}")
            hierarchical_logger.task("DAG built", node_count=len(dag.nodes), nodes=list(dag.nodes.keys()))

            # 执行DAG节点（使用异步循环避免阻塞）
            while not dag.all_completed():
                if self._tasks[task_id].get("status") == "cancelled":
                    break

                # 更新进度
                progress = coordinator._calculate_progress()
                self._tasks[task_id]["progress"] = progress

                # 获取下一个节点
                next_node = dag.get_next_node()
                logger.info(f"Task {task_id}: next_node={next_node}, dag.all_completed()={dag.all_completed()}")
                hierarchical_logger.task("Task next node", task_id=task_id, next_node=next_node, all_completed=dag.all_completed())
                if not next_node:
                    logger.info(f"Task {task_id}: no next node available, breaking")
                    hierarchical_logger.task("Task no next node", task_id=task_id)
                    break

                # 执行节点（在线程池中运行以免阻塞事件循环）
                logger.info(f"Task {task_id}: Calling coordinator.execute_next_node(), coordinator id={id(coordinator)}")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, coordinator.execute_next_node)
                logger.info(f"Task {task_id}: execute_next_node result={result}")
                hierarchical_logger.task("Task execute result", task_id=task_id, result=result)

                if result:
                    # 处理返回列表的情况（并行执行多个节点）
                    results_list = result if isinstance(result, list) else [result]

                    for single_result in results_list:
                        if single_result:
                            # 记录阶段完成
                            self._task_stages[task_id].append({
                                "stage": single_result.get("node", next_node),
                                "status": single_result.get("status"),
                                "timestamp": datetime.now().isoformat()
                            })
                            # 更新当前阶段
                            self._tasks[task_id]["current_stage"] = single_result.get("node", next_node)

                # 释放事件循环以便处理其他请求
                await asyncio.sleep(0.5)

            # 任务完成
            logger.info(f"Task {task_id} completed, status={self._tasks[task_id].get('status')}")
            hierarchical_logger.task("Task completed", task_id=task_id, status=self._tasks[task_id].get('status'))
            if self._tasks[task_id].get("status") != "cancelled":
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
                logger.info(f"Task {task_id} set to completed")
                hierarchical_logger.task("Task set to completed", task_id=task_id)

            # 持久化保存任务状态
            try:
                pm = get_pm()
                TaskPersistence.save_task(pm, task_id, self._tasks[task_id])
            except Exception as e:
                logger.warning(f"Failed to persist task {task_id}: {e}")

        except Exception as e:
            logger.error(f"Task {task_id} execution failed: {e}", exc_info=True)
            hierarchical_logger.task_error("Task execution failed", task_id=task_id, error=str(e))
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)
            # 持久化保存失败状态
            try:
                pm = get_pm()
                TaskPersistence.save_task(pm, task_id, self._tasks[task_id])
            except Exception as e2:
                logger.warning(f"Failed to persist failed task {task_id}: {e2}")


class StatusController:
    """状态控制器 - 处理任务状态、日志、统计等"""

    def __init__(self, task_controller: TaskController):
        self._task_controller = task_controller

    async def get_chapters(self, task_id: str):
        """
        获取任务的所有章节列表

        Args:
            task_id: 任务ID

        Returns:
            List[Dict]: 章节列表
        """
        from deepnovel.persistence.manager import get_persistence_manager

        pm = get_persistence_manager()

        # 尝试从MongoDB读取
        if pm.mongodb_client:
            try:
                chapters = pm.mongodb_client.read(
                    collection="chapters",
                    query={"task_id": task_id}
                )

                # 转换为列表并处理数据
                chapter_list = []
                for chapter in chapters:
                    chapter_list.append({
                        "chapter_id": chapter.get("chapter_id"),
                        "chapter_num": chapter.get("chapter_num"),
                        "title": chapter.get("title"),
                        "content": chapter.get("content", ""),
                        "word_count": chapter.get("word_count", 0),
                        "created_at": chapter.get("created_at", datetime.now()).isoformat() if hasattr(chapter.get("created_at"), 'isoformat') else str(chapter.get("created_at"))
                    })

                # 按章节号排序
                chapter_list.sort(key=lambda x: x.get("chapter_num", 0))

                return {
                    "task_id": task_id,
                    "chapters": chapter_list,
                    "total": len(chapter_list)
                }
            except Exception as e:
                logger.warning(f"MongoDB read failed, falling back to file: {e}")

        # 文件回退：扫描 output/chapters/ 目录
        import glob as _glob
        chapters_dir = os.path.join("output", "chapters", task_id)
        if os.path.isdir(chapters_dir):
            chapter_list = []
            for fpath in sorted(_glob.glob(os.path.join(chapters_dir, "chapter_*.json"))):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        chapter_list.append(data)
                except Exception:
                    continue
            chapter_list.sort(key=lambda x: x.get("chapter_num", 0))
            return {
                "task_id": task_id,
                "chapters": chapter_list,
                "total": len(chapter_list)
            }

        raise HTTPException(status_code=404, detail=f"No chapters found for task {task_id}")

    async def get_chapter_content(self, task_id: str, chapter_num: int):
        """
        获取指定章节的完整内容

        Args:
            task_id: 任务ID
            chapter_num: 章节号

        Returns:
            Dict: 章节内容
        """
        from deepnovel.persistence.manager import get_persistence_manager

        pm = get_persistence_manager()

        # 尝试从MongoDB读取
        if pm.mongodb_client:
            try:
                chapter = pm.mongodb_client.find_one(
                    collection="chapters",
                    query={"task_id": task_id, "chapter_num": chapter_num}
                )

                if chapter:
                    return {
                        "chapter_id": chapter.get("chapter_id"),
                        "task_id": task_id,
                        "chapter_num": chapter.get("chapter_num"),
                        "title": chapter.get("title"),
                        "content": chapter.get("content", ""),
                        "word_count": chapter.get("word_count", 0),
                        "created_at": chapter.get("created_at", datetime.now()).isoformat() if hasattr(chapter.get("created_at"), 'isoformat') else str(chapter.get("created_at"))
                    }
            except Exception as e:
                logger.warning(f"MongoDB read failed, falling back to file: {e}")

        # 文件回退
        filepath = os.path.join("output", "chapters", task_id, f"chapter_{chapter_num}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    "chapter_id": data.get("chapter_id"),
                    "task_id": task_id,
                    "chapter_num": data.get("chapter_num"),
                    "title": data.get("title"),
                    "content": data.get("content", ""),
                    "word_count": data.get("word_count", 0),
                    "created_at": data.get("created_at", "")
                }
            except Exception as e:
                logger.error(f"Failed to read chapter file {filepath}: {e}")

        raise HTTPException(status_code=404, detail=f"Chapter {chapter_num} not found for task {task_id}")

    async def get_task_status(self, task_id: str):
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            TaskStatusResponse: 任务状态
        """
        if task_id not in self._task_controller._tasks:
            # 尝试从持久化存储加载
            try:
                pm = get_pm()
                persisted = TaskPersistence.load_task(pm, task_id)
                if persisted:
                    self._task_controller._tasks[task_id] = persisted
                else:
                    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        task = self._task_controller._tasks[task_id]

        # 计算完成的智能体数量
        completed_agents = [
            s.get("stage") for s in self._task_controller._task_stages.get(task_id, [])
            if s.get("status") == "completed"
        ]

        return {
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "current_stage": task["current_stage"],
            "completed_agents": completed_agents,
            "total_agents": 10,  # 预设的智能体数量
            "start_time": task.get("started_at"),
            "estimated_end_time": self._estimate_end_time(task),
            # Additional task details
            "user_id": task.get("user_id"),
            "task_type": task.get("task_type"),
            "genre": task.get("genre"),
            "title": task.get("title"),
            "description": task.get("description"),
            "chapters": task.get("chapters"),
            "word_count_per_chapter": task.get("word_count_per_chapter"),
            "style": task.get("style"),
            "target_audience": task.get("target_audience"),
        }

    async def get_task_logs(self, task_id: str, page: int, page_size: int):
        """
        获取任务日志

        Args:
            task_id: 任务ID
            page: 页码
            page_size: 每页数量

        Returns:
            TaskLogResponse: 任务日志
        """
        if task_id not in self._task_controller._tasks:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        stages = self._task_controller._task_stages.get(task_id, [])

        # 分页
        total = len(stages)
        start = (page - 1) * page_size
        end = start + page_size
        logs = stages[start:end]

        return {
            "task_id": task_id,
            "logs": logs,
            "total": total,
            "page": page,
            "page_size": page_size
        }

    async def get_stats(self):
        """
        获取统计信息

        Returns:
            Dict: 统计信息
        """
        tasks = self._task_controller._tasks

        stats = {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks.values() if t["status"] == "pending"]),
            "running_tasks": len([t for t in tasks.values() if t["status"] == "running"]),
            "completed_tasks": len([t for t in tasks.values() if t["status"] == "completed"]),
            "failed_tasks": len([t for t in tasks.values() if t["status"] == "failed"]),
            "cancelled_tasks": len([t for t in tasks.values() if t["status"] == "cancelled"]),
            "total_agents": 10,
            "available_agents": [
                "coordinator", "task_manager", "config_enhancer",
                "health_checker", "outline_planner", "character_generator",
                "world_builder", "chapter_summary", "hook_generator",
                "conflict_generator", "content_generator", "quality_checker"
            ]
        }

        return stats

    async def list_agents(self):
        """
        获取智能体列表

        Returns:
            List[Dict]: 智能体列表
        """
        agents = [
            {"name": "coordinator", "description": "Workflow coordinator", "type": "orchestrator"},
            {"name": "task_manager", "description": "Task status manager", "type": "manager"},
            {"name": "config_enhancer", "description": "Configuration enhancer", "type": "preprocessor"},
            {"name": "health_checker", "description": "System health checker", "type": "monitor"},
            {"name": "outline_planner", "description": "Chapter outline planner", "type": "planner"},
            {"name": "character_generator", "description": "Character profile generator", "type": "creator"},
            {"name": "world_builder", "description": "World setting builder", "type": "creator"},
            {"name": "chapter_summary", "description": "Chapter summary generator", "type": "creator"},
            {"name": "hook_generator", "description": "Narrative hook generator", "type": "creator"},
            {"name": "conflict_generator", "description": "Conflict generator", "type": "creator"},
            {"name": "content_generator", "description": "Content writer", "type": "generator"},
            {"name": "quality_checker", "description": "Quality reviewer", "type": "reviewer"}
        ]

        return agents

    def _estimate_end_time(self, task: Dict[str, Any]) -> Optional[str]:
        """
        估计任务结束时间

        Args:
            task: 任务记录

        Returns:
            Optional[str]: 预计结束时间（ISO格式）
        """
        if task["status"] in ["completed", "failed", "cancelled"]:
            return task.get("completed_at") or task.get("cancelled_at")

        if not task.get("started_at") or task["progress"] <= 0:
            return None

        started = datetime.fromisoformat(task["started_at"])
        elapsed = (datetime.now() - started).total_seconds()
        estimated_total = elapsed / task["progress"] * 100

        end_time = started.timestamp() + estimated_total
        return datetime.fromtimestamp(end_time).isoformat()


class ConfigController:
    """配置控制器 - 处理系统配置"""

    def __init__(self):
        self._config: Dict[str, Any] = {
            "database": {
                "mysql": {"host": "localhost", "port": 3306},
                "neo4j": {"host": "localhost", "port": 7687},
                "mongodb": {"host": "localhost", "port": 27017},
                "chromadb": {"host": "localhost", "port": 8000}
            },
            "llm": {
                "provider": "ollama",
                "model": "qwen2.5-7b",
                "max_tokens": 8192
            },
            "messaging": {
                "rocketmq": {"name_server": "localhost:9876"}
            },
            "agents": {
                "coordinator": {"model": "qwen2.5-7b"},
                "default": {"model": "qwen2.5-7b"}
            }
        }

    async def get_config(self, config_key: str):
        """
        获取配置

        Args:
            config_key: 配置键

        Returns:
            Dict: 配置数据
        """
        if config_key not in self._config:
            raise HTTPException(status_code=404, detail=f"Config key {config_key} not found")

        return {config_key: self._config[config_key]}

    async def update_config(self, request):
        """
        更新配置

        Args:
            request: 更新配置请求

        Returns:
            ConfigUpdateResponse: 更新响应
        """
        config_key = request.config_key
        config_value = request.config_value

        if config_key not in self._config:
            raise HTTPException(status_code=404, detail=f"Config key {config_key} not found")

        self._config[config_key] = config_value
        return {
            "success": True,
            "message": f"Config {config_key} updated successfully"
        }


class HealthController:
    """健康检查控制器"""

    def __init__(self):
        self._health_service: Optional[HealthService] = None
        self._components: Dict[str, Dict[str, Any]] = {
            "database": {"status": "unknown", "checked_at": None},
            "llm": {"status": "unknown", "checked_at": None},
            "messaging": {"status": "unknown", "checked_at": None},
            "containers": {"status": "unknown", "checked_at": None}
        }

    def _get_health_service(self) -> HealthService:
        """获取健康检查服务实例"""
        if self._health_service is None:
            self._health_service = get_health_service()
        return self._health_service

    async def get_system_health(self, deep_check: bool = False):
        """
        获取系统整体健康状态

        Args:
            deep_check: 是否执行深度检查（实际连接测试）

        Returns:
            Dict: 健康检查结果
        """
        service = self._get_health_service()

        if deep_check:
            result = service.check_all()
        else:
            # 快速检查，直接返回缓存结果
            result = service._get_result()

        return {
            "overall_status": result["overall_status"],
            "overall_status_code": result["overall_status_code"],
            "last_check": datetime.now().isoformat(),
            "components": result["components"],
            "summary": {
                "total": result["component_count"],
                "healthy": result["healthy_count"],
                "degraded": result["degraded_count"],
                "unhealthy": result["unhealthy_count"]
            }
        }

    async def get_component_health(self, component_name: str):
        """
        获取单个组件健康状态

        Args:
            component_name: 组件名称

        Returns:
            Dict: 组件健康状态
        """
        service = self._get_health_service()
        health = service.check_single(component_name)
        return health.to_dict()

    async def get_task_health(self, task_id: str):
        """
        获取任务组件健康状态

        Args:
            task_id: 任务ID

        Returns:
            HealthCheckResponse: 健康检查响应
        """
        # 检查组件
        self._check_database()
        self._check_messaging()

        return {
            "status": "healthy" if all(c["status"] != "unhealthy" for c in self._components.values()) else "degraded",
            "components": self._components
        }

    def _check_database(self):
        """检查数据库组件"""
        try:
            service = self._get_health_service()
            db_health = service.check_single("mongodb")
            self._components["database"] = {
                "status": db_health.status.value,
                "latency_ms": db_health.latency_ms,
                "details": db_health.details,
                "checked_at": datetime.now().isoformat()
            }
        except Exception as e:
            self._components["database"] = {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }

    def _check_messaging(self):
        """检查消息组件"""
        try:
            service = self._get_health_service()
            mq_health = service.check_single("rocketmq")
            self._components["messaging"] = {
                "status": mq_health.status.value,
                "latency_ms": mq_health.latency_ms,
                "details": mq_health.details,
                "checked_at": datetime.now().isoformat()
            }
        except Exception as e:
            self._components["messaging"] = {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }

    def _check_llm(self):
        """检查LLM组件"""
        try:
            service = self._get_health_service()
            llm_health = service.check_single("ollama")
            self._components["llm"] = {
                "status": llm_health.status.value,
                "latency_ms": llm_health.latency_ms,
                "details": llm_health.details,
                "checked_at": datetime.now().isoformat()
            }
        except Exception as e:
            self._components["llm"] = {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.now().isoformat()
            }


# 创建单例实例
task_controller = TaskController()
status_controller = StatusController(task_controller)
config_controller = ConfigController()
health_controller = HealthController()
