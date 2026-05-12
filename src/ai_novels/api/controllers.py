"""
API控制器 - 业务逻辑层

@file: api/controllers.py
@date: 2026-03-12
@version: 2.0.0
@description: API控制器实现，包含业务逻辑分层
"""

from fastapi import HTTPException, BackgroundTasks
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
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
logger = logging.getLogger('ai_novels.api.controllers')
logger.setLevel(logging.INFO)
logger.addHandler(logging.FileHandler('logs/server.log', encoding='utf-8'))

# 导入 HierarchicalLogger 用于分类日志
from ai_novels.utils import get_logger
hierarchical_logger = get_logger()

# 导入数据模型
from ai_novels.message.message import TaskRequest, TaskStatusUpdate, TaskResponse
from ai_novels.agents.coordinator import CoordinatorAgent, WorkflowState
from ai_novels.agents.agent_communicator import AgentCommunicator
from ai_novels.config.manager import ConfigManager, settings
from ai_novels.core.llm_router import get_llm_router
from ai_novels.utils import log_info, log_error, get_logger, LogContext

# 导入健康检查服务
from ai_novels.services.health_service import get_health_service, HealthService

# 导入持久化 (PostgreSQL via SQLModel)
from ai_novels.database.engine import get_session
from ai_novels.models.task import Task, TaskStatus
from ai_novels.repositories.task_repository import TaskRepository

from ai_novels.core.event_bus import event_bus, EventType


class TaskController:
    """任务控制器 - 处理任务创建、取消、查询等"""

    def __init__(self):
        self._repo = TaskRepository()

    async def create_task(self, request, background_tasks: BackgroundTasks):
        """
        创建新任务

        Args:
            request: 创建任务请求
            background_tasks: 后台任务

        Returns:
            dict: 任务创建响应
        """
        # 创建 ORM 实体
        task = Task(
            user_id=getattr(request, 'user_id', 'default'),
            task_type=getattr(request, 'task_type', 'novel'),
            genre=getattr(request, 'genre', ''),
            title=getattr(request, 'title', ''),
            description=getattr(request, 'description', ''),
            chapters=getattr(request, 'chapters', 5),
            word_count_per_chapter=getattr(request, 'word_count_per_chapter', 2000),
            style=getattr(request, 'style', 'light'),
            target_audience=getattr(request, 'target_audience', 'general'),
            language=getattr(request, 'language', 'zh-CN'),
            status=TaskStatus.PENDING,
            progress=0.0,
            current_stage='initializing',
            logs=[{
                'stage': 'initializing',
                'status': 'completed',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }],
        )

        # 持久化到 PostgreSQL
        async with get_session() as session:
            task = await self._repo.create(session, task)
            task_id = task.id

        # 后台启动任务
        logger.info(f"Adding background task for {task_id}")
        hierarchical_logger.api(f"Adding background task for {task_id}", task_id=task_id)
        background_tasks.add_task(self._execute_task, task_id, request)
        logger.info(f"Background task added for {task_id}")
        hierarchical_logger.api(f"Background task added for {task_id}", task_id=task_id)

        return {
            'task_id': task_id,
            'status': 'accepted',
            'message': f'Task {task_id} accepted and processing'
        }

    async def cancel_task(self, task_id: str, request=None):
        """
        取消任务

        Args:
            task_id: 任务ID
            request: 取消任务请求（可选）

        Returns:
            dict: 任务取消响应
        """
        async with get_session() as session:
            task = await self._repo.get_by_id(session, task_id)
            if not task:
                raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel task in {task.status} state"
                )

            task.status = TaskStatus.CANCELLED
            task.cancelled_at = datetime.now(timezone.utc)
            task.error = 'Task cancelled by user'
            await self._repo.update(session, task)

        return {
            'task_id': task_id,
            'status': 'cancelled',
            'message': f'Task {task_id} has been cancelled'
        }

    async def list_tasks(
        self,
        user_id: Optional[str],
        status: Optional[str],
        page: int,
        page_size: int,
    ):
        """
        获取任务列表

        Args:
            user_id: 用户ID（可选）
            status: 任务状态（可选）
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 任务列表
        """
        async with get_session() as session:
            if status:
                tasks = await self._repo.get_by_status(session, status)
            else:
                tasks = await self._repo.get_all(session, limit=10000)

        # 过滤 user_id（内存过滤，数据量不大）
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]

        # 排序：按创建时间倒序
        tasks.sort(key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # 转换为 dict 以保持向后兼容
        task_dicts = [_task_to_dict(t) for t in tasks]

        # 分页
        total = len(task_dicts)
        start = (page - 1) * page_size
        end = start + page_size
        page_tasks = task_dicts[start:end]

        return {
            'tasks': page_tasks,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_more': end < total,
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

        # 更新任务状态为 running
        logger.info(f"Starting _execute_task for {task_id}")
        hierarchical_logger.task(f"Starting _execute_task for {task_id}", task_id=task_id)
        async with get_session() as session:
            task_obj = await self._repo.get_by_id(session, task_id)
            if task_obj:
                task_obj.status = TaskStatus.RUNNING
                task_obj.started_at = datetime.now(timezone.utc)
                await self._repo.update(session, task_obj)
        task_start_time = time.time()

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
                "target_audience": request.target_audience,
                "description": request.description,
                "user_id": request.user_id,
                "language": getattr(request, 'language', 'zh-CN'),
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
                    "language": getattr(request, 'language', 'zh-CN'),
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
                async with get_session() as session:
                    task_obj = await self._repo.get_by_id(session, task_id)
                    if task_obj:
                        task_obj.status = TaskStatus.FAILED
                        task_obj.error = dag_plan["error"]
                        await self._repo.update(session, task_obj)
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
                # 从DB检查任务状态（cancelled / paused）
                async with get_session() as session:
                    task_obj = await self._repo.get_by_id(session, task_id)
                    if not task_obj:
                        logger.error(f"Task {task_id} disappeared from DB, aborting")
                        break
                    if task_obj.status == TaskStatus.CANCELLED:
                        logger.info(f"Task {task_id} cancelled, breaking DAG loop")
                        break
                    if task_obj.status == TaskStatus.PAUSED:
                        task_obj.current_stage = "paused"
                        await self._repo.update(session, task_obj)
                        await asyncio.sleep(1)
                        continue

                # 更新进度
                progress = coordinator._calculate_progress()
                async with get_session() as session:
                    task_obj = await self._repo.get_by_id(session, task_id)
                    if task_obj:
                        task_obj.progress = float(progress)
                        await self._repo.update(session, task_obj)

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
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, coordinator.execute_next_node),
                    timeout=600,
                )
                logger.info(f"Task {task_id}: execute_next_node result={result}")
                hierarchical_logger.task("Task execute result", task_id=task_id, result=result)

                if result:
                    # 处理返回列表的情况（并行执行多个节点）
                    results_list = result if isinstance(result, list) else [result]

                    for single_result in results_list:
                        if single_result:
                            stage_name = single_result.get("node", next_node)

                            # 记录阶段到 DB
                            async with get_session() as session:
                                task_obj = await self._repo.get_by_id(session, task_id)
                                if task_obj:
                                    task_obj.logs.append({
                                        "stage": stage_name,
                                        "status": single_result.get("status"),
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                    })
                                    task_obj.current_stage = stage_name
                                    await self._repo.update(session, task_obj)

                    # 同步 config_enhancer 节点更新到 DB
                    if next_node == "config_enhancer":
                        async with get_session() as session:
                            task_obj = await self._repo.get_by_id(session, task_id)
                            if task_obj:
                                for k in ["description", "style", "genre", "target_audience"]:
                                    v = coordinator._current_task.get(k)
                                    if v:
                                        setattr(task_obj, k, v)
                                await self._repo.update(session, task_obj)

                    # 发射 task.progress SSE 事件
                    try:
                        progress = coordinator._calculate_progress()
                        stage_statuses = {}
                        if coordinator._dag:
                            for nname, nnode in coordinator._dag.nodes.items():
                                stage_statuses[nname] = {
                                    "status": nnode.status.value if hasattr(nnode.status, 'value') else str(nnode.status),
                                    "elapsed": getattr(nnode, 'elapsed_time', 0) or 0,
                                }
                        chapters_info = {"total": request.chapters or 20, "completed": 0, "generating": 0}
                        if hasattr(coordinator, '_chapter_results'):
                            chapters_info["completed"] = len([c for c in coordinator._chapter_results.values() if c.get("status") == "completed"])
                            chapters_info["generating"] = len([c for c in coordinator._chapter_results.values() if c.get("status") == "running"])

                        progress_payload = {
                            "task_id": task_id,
                            "progress": float(progress),
                            "current_stage": coordinator._current_task.get("description", ""),
                            "stage_statuses": stage_statuses,
                            "chapters": chapters_info,
                            "elapsed_seconds": time.time() - task_start_time,
                        }
                        # 估算生成速度和 ETA
                        elapsed = time.time() - task_start_time
                        target_wc = (request.word_count_per_chapter or 2000) * (request.chapters or 5)
                        pct = float(progress) / 100.0 if progress else 0
                        total_wc = int(target_wc * pct) if pct > 0 else 0
                        if elapsed > 5 and total_wc > 0:
                            progress_payload["speed_wpm"] = round((total_wc / elapsed) * 60, 1)
                            remaining = max(0, target_wc - total_wc)
                            if progress_payload["speed_wpm"] > 0:
                                progress_payload["eta_seconds"] = int(remaining / (progress_payload["speed_wpm"] / 60))
                        progress_payload["total_words"] = total_wc
                        progress_payload["target_words"] = target_wc
                        if loop.is_running():
                            loop.create_task(
                                event_bus.publish_type(EventType.TASK_PROGRESS, payload=progress_payload, source="task_controller")
                            )
                    except Exception:
                        pass  # progress event emission is best-effort

                # 释放事件循环以便处理其他请求
                await asyncio.sleep(0.5)

            # 任务完成
            async with get_session() as session:
                task_obj = await self._repo.get_by_id(session, task_id)
                if task_obj:
                    logger.info(f"Task {task_id} completed, status={task_obj.status}")
                    hierarchical_logger.task("Task completed", task_id=task_id, status=task_obj.status)
                    if task_obj.status != TaskStatus.CANCELLED:
                        task_obj.status = TaskStatus.COMPLETED
                        task_obj.completed_at = datetime.now(timezone.utc)
                        await self._repo.update(session, task_obj)
                        logger.info(f"Task {task_id} set to completed")
                        hierarchical_logger.task("Task set to completed", task_id=task_id)

        except Exception as e:
            logger.error(f"Task {task_id} execution failed: {e}", exc_info=True)
            hierarchical_logger.task_error("Task execution failed", task_id=task_id, error=str(e))
            async with get_session() as session:
                task_obj = await self._repo.get_by_id(session, task_id)
                if task_obj:
                    task_obj.status = TaskStatus.FAILED
                    task_obj.error = str(e)
                    await self._repo.update(session, task_obj)


class StatusController:
    """状态控制器 - 处理任务状态、日志、统计等"""

    def __init__(self):
        self._repo = TaskRepository()

    async def get_chapters(self, task_id: str):
        """
        获取任务的所有章节列表

        Args:
            task_id: 任务ID

        Returns:
            List[Dict]: 章节列表
        """
        from ai_novels.persistence.manager import get_persistence_manager

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

                total_wc = sum(
                    ch.get("word_count", 0) for ch in chapter_list
                    if isinstance(ch.get("word_count"), (int, float))
                )
                return {
                    "task_id": task_id,
                    "chapters": chapter_list,
                    "total": len(chapter_list),
                    "total_word_count": total_wc,
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
            total_wc = sum(
                ch.get("word_count", 0) for ch in chapter_list
                if isinstance(ch.get("word_count"), (int, float))
            )
            return {
                "task_id": task_id,
                "chapters": chapter_list,
                "total": len(chapter_list),
                "total_word_count": total_wc,
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
        from ai_novels.persistence.manager import get_persistence_manager

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
            dict: 任务状态
        """
        async with get_session() as session:
            task = await self._repo.get_by_id(session, task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # 计算完成的智能体数量
        completed_agents = [
            log.get("stage") for log in task.logs
            if log.get("status") == "completed"
        ]

        return {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "current_stage": task.current_stage,
            "completed_agents": completed_agents,
            "total_agents": 10,
            "start_time": task.started_at.isoformat() if task.started_at else None,
            "estimated_end_time": self._estimate_end_time(task),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
            "error": task.error,
            "user_id": task.user_id,
            "task_type": task.task_type,
            "genre": task.genre,
            "title": task.title,
            "description": task.description,
            "chapters": task.chapters,
            "word_count_per_chapter": task.word_count_per_chapter,
            "style": task.style,
            "target_audience": task.target_audience,
        }

    async def get_task_logs(self, task_id: str, page: int, page_size: int):
        """
        获取任务日志

        Args:
            task_id: 任务ID
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 任务日志
        """
        async with get_session() as session:
            task = await self._repo.get_by_id(session, task_id)

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        logs = task.logs or []

        # 分页
        total = len(logs)
        start = (page - 1) * page_size
        end = start + page_size
        page_logs = logs[start:end]

        return {
            "task_id": task_id,
            "logs": page_logs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_stats(self):
        """
        获取统计信息

        Returns:
            Dict: 统计信息
        """
        async with get_session() as session:
            tasks = await self._repo.get_all(session, limit=10000)

        stats = {
            "total_tasks": len(tasks),
            "pending_tasks": len([t for t in tasks if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            "completed_tasks": len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            "failed_tasks": len([t for t in tasks if t.status == TaskStatus.FAILED]),
            "cancelled_tasks": len([t for t in tasks if t.status == TaskStatus.CANCELLED]),
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

    def _estimate_end_time(self, task: Task) -> Optional[str]:
        """
        估计任务结束时间

        Args:
            task: Task ORM 对象

        Returns:
            Optional[str]: 预计结束时间（ISO格式）
        """
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            dt = task.completed_at or task.cancelled_at
            return dt.isoformat() if dt else None

        if not task.started_at or task.progress <= 0:
            return None

        elapsed = (datetime.now(timezone.utc) - task.started_at).total_seconds()
        estimated_total = elapsed / task.progress * 100
        end_ts = task.started_at.timestamp() + estimated_total
        return datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()


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


def _task_to_dict(task: Task) -> Dict[str, Any]:
    """将 Task ORM 对象转换为 dict（向后兼容）"""
    return {
        "task_id": task.id,
        "user_id": task.user_id,
        "task_type": task.task_type,
        "genre": task.genre,
        "title": task.title,
        "description": task.description,
        "chapters": task.chapters,
        "word_count_per_chapter": task.word_count_per_chapter,
        "style": task.style,
        "target_audience": task.target_audience,
        "language": task.language,
        "status": task.status,
        "progress": task.progress,
        "current_stage": task.current_stage,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
        "error": task.error,
    }


# 创建单例实例
task_controller = TaskController()
status_controller = StatusController()
config_controller = ConfigController()
health_controller = HealthController()
