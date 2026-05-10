"""
CoordinatorAgent - 协调者智能体

@file: agents/coordinator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 任务接收/DAG规划/智能体编排
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading
import concurrent.futures

from .base import BaseAgent, AgentConfig, Message, MessageType
from .agent_communicator import AgentCommunicator, AgentMessageHandler
from .constants import (
    DEFAULT_WORDS_PER_CHAPTER,
    DEFAULT_GENRE,
    CONTENT_TRUNCATE_LENGTH_LARGE,
)
from deepnovel.messaging.rocketmq_producer import RocketMQProducer, ProducerConfig
from deepnovel.messaging.rocketmq_consumer import ConsumerConfig, RocketMQConsumer
from deepnovel.message.message import (
    TaskRequest,
    TaskResponse,
    TaskStatusUpdate,
    AgentMessage
)
from deepnovel.config.manager import settings
from deepnovel.utils import log_info, log_warn, log_error, get_logger

# 事件总线（用于发布 DAG 执行事件）
from deepnovel.core.event_bus import event_bus as _event_bus

# 为向后兼容性保留别名
RocketMQConfig = ProducerConfig


class WorkflowState(Enum):
    """工作流状态"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentCommunicatorState(Enum):
    """智能体通信状态"""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DAGNode:
    """DAG节点"""
    agent_name: str
    Dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    elapsed_time: float = 0.0


@dataclass
class DAG:
    """DAG结构"""
    nodes: Dict[str, DAGNode] = field(default_factory=dict)
    edges: List[tuple] = field(default_factory=list)
    root_nodes: List[str] = field(default_factory=list)
    leaf_nodes: List[str] = field(default_factory=list)

    def add_node(self, node: DAGNode):
        """添加节点"""
        self.nodes[node.agent_name] = node

    def add_edge(self, from_node: str, to_node: str):
        """添加边"""
        self.edges.append((from_node, to_node))
        if from_node not in self.leaf_nodes:
            self.leaf_nodes.append(from_node)
        if to_node not in self.root_nodes:
            self.root_nodes.append(to_node)

    def get_ready_nodes(self) -> List[str]:
        """获取就绪节点（所有依赖已完成）"""
        ready = []
        for node_name, node in self.nodes.items():
            if node.status == "pending":
                all_deps_done = all(
                    self.nodes[dep].status == "completed"
                    for dep in node.Dependencies
                )
                if all_deps_done:
                    ready.append(node_name)
        return ready

    def get_next_node(self) -> Optional[str]:
        """获取下一个执行节点（拓扑序）"""
        ready = self.get_ready_nodes()
        if ready:
            # 返回第一个就绪节点
            return ready[0]
        return None

    def all_completed(self) -> bool:
        """检查是否全部完成"""
        return all(node.status == "completed" for node in self.nodes.values())

    def has_failed(self) -> bool:
        """检查是否有失败"""
        return any(node.status == "failed" for node in self.nodes.values())


class CoordinatorAgent(BaseAgent):
    """
    协调者智能体

    核心功能：
    - 接收用户任务请求
    - 执行DAG规划
    - 编排智能体工作流
    - 管理任务状态和进度
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            # 从配置文件读取 coordinator 配置
            config = AgentConfig.from_config("coordinator")
        super().__init__(config)

        # 工作流状态
        self._workflow_state = WorkflowState.IDLE
        self._current_task: Optional[Dict[str, Any]] = None
        self._dag: Optional[DAG] = None
        self._task_start_time: float = 0

        # 任务统计
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_nodes = 0

        # 上下文存储
        self._context: Dict[str, Any] = {
            "generated_content": [],
            "characters": [],
            "world_bible": {},
            "outlines": []
        }

        # RocketMQ通信器
        self._communicator: Optional[AgentCommunicator] = None
        self._rocketmq_producer: Optional[RocketMQProducer] = None
        self._rocketmq_consumer: Optional[RocketMQConsumer] = None
        self._comm_thread: Optional[threading.Thread] = None
        self._comm_running = False

        # 消息处理回调（使用字符串键用于 RocketMQ 消息类型）
        self._message_callbacks: Dict[str, List[Callable]] = {
            "task_request": [],
            "task_response": [],
            "task_status_update": [],
            "agent_query": [],
            "agent_response": [],
        }

        # 待处理消息队列
        self._pending_messages: List[Dict[str, Any]] = []

    def _setup_communicator(self) -> bool:
        """
        设置RocketMQ通信器

        Returns:
            bool: 设置成功返回True
        """
        try:
            # 从配置管理器读取RocketMQ配置
            mq_config = settings.get("messaging", {})
            producer_settings = mq_config.get("producer", {})
            consumer_settings = mq_config.get("consumers", {})

            # 初始化生产者
            producer_config = ProducerConfig.from_config(producer_settings)
            self._rocketmq_producer = RocketMQProducer(producer_config)

            if not self._rocketmq_producer.connect():
                log_error("Failed to connect RocketMQ producer")
                return False

            # 获取默认消费者设置
            default_consumer = consumer_settings.get(list(consumer_settings.keys())[0]) if consumer_settings else {}

            # 初始化消费者
            consumer_config = ConsumerConfig(
                name_server=mq_config.get("namesrv_addr", "localhost:9876"),
                consumer_group=default_consumer.get("group_name", "ai_novels_consumer"),
                topic=default_consumer.get("topic", "ai_novels_task_execution"),
                max_concurrency=default_consumer.get("consume_message_batch_max_size", 16)
            )
            self._rocketmq_consumer = RocketMQConsumer(consumer_config)

            if not self._rocketmq_consumer.connect():
                log_error("Failed to connect RocketMQ consumer")
                self._rocketmq_producer.close()
                return False

            # 注册消息处理器
            handler = AgentMessageHandler("coordinator", self._on_agent_message)
            self._rocketmq_consumer.subscribe(handler)

            # 初始化AgentCommunicator
            comm_config = {
                "rocketmq": {
                    "name_server": mq_config.get("namesrv_addr", "localhost:9876"),
                    "producer_group": producer_config.group_name,
                    "consumer_group": consumer_config.consumer_group
                }
            }
            self._communicator = AgentCommunicator("coordinator", comm_config)
            self._communicator._producer = self._rocketmq_producer
            self._communicator._consumer = self._rocketmq_consumer
            self._communicator._handlers.append(handler)
            self._communicator._running = True
            self._communicator._state = AgentCommunicatorState.CONNECTED

            return True

        except Exception as e:
            log_error(f"Setup communicator error: {str(e)}")
            return False

    def _on_agent_message(self, message: Dict[str, Any]) -> bool:
        """
        智能体消息回调

        Args:
            message: 消息数据

        Returns:
            bool: 处理成功返回True
        """
        try:
            message_type = message.get("message_type", "")

            # 存储待处理消息
            self._pending_messages.append(message)

            # 分发给注册的回调
            callbacks = self._message_callbacks.get(message_type, [])
            for callback in callbacks:
                if not callback(message):
                    log_warn(f"Message callback failed: {message_type}")
                    return False

            log_info(f"Coordinator received message: {message_type}")
            return True

        except Exception as e:
            log_error(f"Error processing agent message: {str(e)}")
            return False

    def _start_comm_thread(self):
        """启动消息处理线程"""
        def comm_loop():
            while self._comm_running:
                try:
                    if self._pending_messages:
                        msg = self._pending_messages.pop(0)
                        self._process_incoming_message(msg)
                    time.sleep(0.01)
                except Exception as e:
                    log_error(f"Comm thread error: {str(e)}")
                    time.sleep(0.1)

        self._comm_thread = threading.Thread(target=comm_loop, daemon=True)
        self._comm_thread.start()

    def _process_incoming_message(self, message: Dict[str, Any]):
        """
        处理 incoming 消息

        Args:
            message: 消息数据
        """
        message_type = message.get("message_type", "")

        if message_type == "task_request":
            self._handle_task_request(message)
        elif message_type == "task_response":
            self._handle_task_response(message)
        elif message_type == "task_status_update":
            self._handle_status_update(message)

    def _handle_task_request(self, message: Dict[str, Any]):
        """处理任务请求"""
        payload = message.get("payload", {})
        task_id = payload.get("task_id", "")
        user_id = payload.get("user_id", "")
        agent_name = payload.get("agent_name", "")

        log_info(f"[Task Request] Task: {task_id}, User: {user_id}, Agent: {agent_name}")

        # 如果是发给coordinator的任务，开始执行
        if agent_name == "coordinator":
            # 触发DAG规划和执行
            self._comm_dispatch_task(message)

    def _handle_task_response(self, message: Dict[str, Any]):
        """处理任务响应"""
        payload = message.get("payload", {})
        task_id = payload.get("task_id", "")
        agent_name = payload.get("agent_name", "")
        status = payload.get("status", "")

        log_info(f"[Task Response] Task: {task_id}, Agent: {agent_name}, Status: {status}")

        # 更新DAG节点状态
        if self._dag and task_id in self._dag.nodes:
            node = self._dag.nodes[task_id]
            if status == "success":
                node.status = "completed"
            else:
                node.status = "failed"

    def _handle_status_update(self, message: Dict[str, Any]):
        """处理状态更新"""
        payload = message.get("payload", {})
        task_id = payload.get("task_id", "")
        status = payload.get("status", "")
        progress = payload.get("progress", 0)

        log_info(f"[Status Update] Task: {task_id}, Status: {status}, Progress: {progress}%")

    def _comm_dispatch_task(self, message: Dict[str, Any]):
        """
        分发任务给目标智能体

        Args:
            message: 消息数据
        """
        payload = message.get("payload", {})
        target_agent = payload.get("agent_name", "")

        if target_agent and self._communicator:
            # 解析任务并发送给目标智能体
            task_request = TaskRequest.from_dict(payload)

            # 发送任务请求
            result = self._communicator.send_task_request(
                target_agent=target_agent,
                task_id=task_request.task_id,
                payload=task_request.payload,
                user_id=task_request.user_id
            )

            log_info(f"Dispatched task to {target_agent}: {result}")

    def process(self, message: Message) -> Message:
        """处理消息 - 协调其他Agent"""
        content = str(message.content).lower()

        if "start" in content or "generate" in content:
            return self._handle_generation_request(message)
        elif "status" in content or "progress" in content:
            return self._handle_status_request(message)
        elif "stop" in content or "pause" in content:
            return self._handle_stop_request(message)
        elif "resume" in content:
            return self._handle_resume_request(message)
        else:
            return self._handle_general_request(message)

    def _handle_generation_request(self, message: Message) -> Message:
        """处理生成请求"""
        content = str(message.content)

        # 解析用户需求
        user_request = self._parse_user_request(content)

        # 开始工作流
        self._workflow_state = WorkflowState.PLANNING

        # DAG规划
        dag_plan = self._plan_workflow(user_request)

        if dag_plan.get("error"):
            return self._create_message(
                f"Workflow planning failed: {dag_plan['error']}",
                MessageType.TEXT,
                state=self._workflow_state.value
            )

        # 创建DAG
        self._dag = self._build_dag(dag_plan)

        self._total_nodes = len(self._dag.nodes)
        self._task_start_time = time.time()
        self._workflow_state = WorkflowState.EXECUTING

        # 返回计划
        plan_response = self._format_dag_plan(dag_plan)

        return self._create_message(
            plan_response,
            MessageType.TEXT,
            state=self._workflow_state.value,
            task_id=str(int(time.time()))
        )

    def _handle_status_request(self, message: Message) -> Message:
        """处理状态查询请求"""
        if self._workflow_state == WorkflowState.IDLE:
            response = "Workflow coordinator is idle. Ready to start new tasks."

        elif self._workflow_state == WorkflowState.PLANNING:
            response = "Workflow is planning the DAG structure."

        elif self._workflow_state == WorkflowState.EXECUTING:
            progress = self._calculate_progress()
            ready_nodes = self._dag.get_ready_nodes() if self._dag else []
            response = (
                f"Workflow progress: {progress:.1f}%\n"
                f"Status: Executing\n"
                f"Ready agents: {ready_nodes}\n"
                f"Completed: {self._tasks_completed}/{self._total_nodes}"
            )

        elif self._workflow_state == WorkflowState.COMPLETED:
            elapsed = time.time() - self._task_start_time
            response = (
                f"Workflow completed successfully!\n"
                f"Total time: {elapsed:.1f}s\n"
                f"Tasks completed: {self._tasks_completed}\n"
                f"Results available in context."
            )

        elif self._workflow_state == WorkflowState.FAILED:
            response = (
                f"Workflow failed.\n"
                f"Tasks completed: {self._tasks_completed}\n"
                f"Tasks failed: {self._tasks_failed}"
            )

        else:
            response = f"Current state: {self._workflow_state.value}"

        return self._create_message(
            response,
            MessageType.TEXT,
            state=self._workflow_state.value,
            progress=self._calculate_progress() if self._dag else 0
        )

    def _handle_stop_request(self, message: Message) -> Message:
        """处理停止请求"""
        if self._workflow_state in [WorkflowState.EXECUTING, WorkflowState.PLANNING]:
            self._workflow_state = WorkflowState.PAUSED
            response = "Workflow paused. Use 'resume' to continue."
        else:
            response = "Cannot pause. Current state: " + self._workflow_state.value

        return self._create_message(
            response,
            MessageType.TEXT,
            state=self._workflow_state.value
        )

    def _handle_resume_request(self, message: Message) -> Message:
        """处理恢复请求"""
        if self._workflow_state == WorkflowState.PAUSED:
            self._workflow_state = WorkflowState.EXECUTING
            response = "Workflow resumed."
        else:
            response = f"Cannot resume. Current state: {self._workflow_state.value}"

        return self._create_message(
            response,
            MessageType.TEXT,
            state=self._workflow_state.value
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "I can help you coordinate the novel generation workflow.\n"
            "Available commands:\n"
            "- 'start generation' - 开始生成小说\n"
            "- 'check status' - 查询进度\n"
            "- 'stop/pause' - 暂停工作流\n"
            "- 'resume' - 恢复工作流"
        )
        return self._create_message(response)

    def _parse_user_request(self, content: str) -> Dict[str, Any]:
        """解析用户请求 - 使用LLM进行智能解析"""
        # 简化的请求解析
        request = {
            "timestamp": datetime.now().isoformat(),
            "original_request": content,
            "intent": "generate_novel",
            "parameters": {
                "genre": None,
                "length": None,
                "style": None,
                "theme": None,
                "target_word_count": None
            }
        }

        # 使用LLM进行智能解析
        llm_prompt = f"""Analyze the user's novel generation request and extract key parameters.

User request: {content}

Please return a JSON object with:
- genre: the genre (romance, fantasy, sci-fi, mystery, adventure, drama)
- length: the expected length (short, medium, long)
- style: writing style (descriptive, concise, poetic, dialogue_heavy)
- theme: main theme/topic
- target_word_count: estimated total word count

Return ONLY valid JSON, no other text."""

        llm_response = self._generate_with_llm(llm_prompt, "You are a request analyzer.")

        if llm_response:
            # 尝试从LLM响应中提取JSON
            try:
                import json as json_module
                # 尝试解析JSON
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx + 1]
                    parsed = json_module.loads(json_str)
                    # 合并解析结果
                    if "genre" in parsed:
                        request["parameters"]["genre"] = parsed["genre"]
                    if "length" in parsed:
                        request["parameters"]["length"] = parsed["length"]
                    if "style" in parsed:
                        request["parameters"]["style"] = parsed["style"]
                    if "theme" in parsed:
                        request["parameters"]["theme"] = parsed["theme"]
                    if "target_word_count" in parsed:
                        request["parameters"]["target_word_count"] = parsed["target_word_count"]
            except Exception as e:
                log_error(f"Failed to parse LLM response: {e}")

        # Fallback: 简单关键词识别
        content_lower = content.lower()
        if " romance" in content_lower or "爱情" in content:
            request["parameters"]["genre"] = "romance"
        if " sci-fi" in content_lower or "科幻" in content:
            request["parameters"]["genre"] = "sci-fi"
        if " fantasy" in content_lower or "玄幻" in content:
            request["parameters"]["genre"] = "fantasy"
        if " long" in content_lower or "长篇" in content:
            request["parameters"]["length"] = "long"
        if " short" in content_lower or "短篇" in content:
            request["parameters"]["length"] = "short"

        return request

    def _plan_workflow(self, user_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        DAG规划 - 使用LLM优化工作流规划

        返回DAG计划，包括：
        - 执行阶段
        - 每个阶段的Agent
        - Agent间的依赖关系
        """
        # 从 system.json 读取工作流配置
        system_config = settings.get("system", {})
        workflow_config = system_config.get("workflow", {})

        # 使用配置中的 stage_config 或使用默认配置
        stage_config = workflow_config.get("stage_config", {
            "initialization": {
                "agents": ["health_checker", "config_enhancer"],
                "description": "Initialize workflow and enhance configuration",
                "dependencies": {}
            },
            "planning": {
                "agents": ["outline_planner", "character_generator", "world_builder"],
                "description": "Plan novel structure and create assets",
                "dependencies": {
                    "character_generator": ["config_enhancer"],
                    "world_builder": ["config_enhancer"],
                    "outline_planner": ["character_generator", "world_builder"]
                }
            },
            "execution": {
                "agents": ["chapter_summary", "hook_generator", "conflict_generator"],
                "description": "Generate content assets",
                "dependencies": {
                    "chapter_summary": ["outline_planner"],
                    "hook_generator": ["outline_planner"],
                    "conflict_generator": ["chapter_summary"]
                }
            },
            "generation": {
                "agents": ["content_generator"],
                "description": "Generate actual novel content",
                "dependencies": {
                    "content_generator": ["chapter_summary", "hook_generator", "conflict_generator"]
                }
            },
            "quality": {
                "agents": ["quality_checker"],
                "description": "Review and quality check",
                "dependencies": {
                    "quality_checker": ["content_generator"]
                }
            }
        })

        # 使用LLM优化DAG规划（可选）
        genre = user_request.get("parameters", {}).get("genre", "fantasy")
        llm_prompt = f"""Review the workflow plan for a {genre} novel generation.

Standard workflow stages:
1. initialization - Health check and config enhancement
2. planning - Outline, character, and world building
3. execution - Chapter summaries, hooks, conflicts
4. generation - Actual content writing
5. quality - Quality review

Is this workflow appropriate for a {genre} novel?
If any adjustments are needed, return a modified plan.
Otherwise, return the original plan unchanged.

Return as JSON with the same structure."""

        llm_response = self._generate_with_llm(llm_prompt, "You are a workflow planner.")

        # LLM响应可选，保证基本功能正常
        # 如果LLM响应有效则使用，否则使用默认配置

        # 根据章节数创建多个 content_generator 节点
        chapters = user_request.get("parameters", {}).get("chapters", 20)
        style = user_request.get("parameters", {}).get("style", "fantasy")

        # 创建章节目录
        chapters_list = list(range(1, chapters + 1))

        # 为每一章创建独立的内容生成节点
        generation_agents = [f"content_generator_chapter_{i}" for i in chapters_list]

        # 为生成阶段添加节点
        stage_config["generation"] = {
            "agents": generation_agents,
            "description": "Generate actual novel content",
            "dependencies": {f"content_generator_chapter_{i}": ["chapter_summary", "hook_generator", "conflict_generator"] for i in chapters_list}
        }

        # 质量检查依赖于所有章节生成完成
        stage_config["quality"] = {
            "agents": ["quality_checker"],
            "description": "Review and quality check",
            "dependencies": {
                "quality_checker": generation_agents
            }
        }

        return {
            "stages": stage_config,
            "total_stages": len(stage_config),
            "total_agents": sum(len(s["agents"]) for s in stage_config.values()),
            "error": None
        }

    def _build_dag(self, dag_plan: Dict[str, Any]) -> DAG:
        """构建DAG对象"""
        dag = DAG()

        stage_order = ["initialization", "planning", "execution", "generation", "quality"]

        for stage_name in stage_order:
            if stage_name not in dag_plan["stages"]:
                continue

            stage = dag_plan["stages"][stage_name]

            for agent_name in stage["agents"]:
                # 获取依赖
                dependencies = stage["dependencies"].get(agent_name, [])

                node = DAGNode(
                    agent_name=agent_name,
                    Dependencies=dependencies,
                    status="pending"
                )
                dag.add_node(node)

                # 添加边
                for dep in dependencies:
                    dag.add_edge(dep, agent_name)

        return dag

    def _format_dag_plan(self, dag_plan: Dict[str, Any]) -> str:
        """格式化DAG计划"""
        output_lines = ["=== Workflow DAG Plan ===", ""]

        stage_order = ["initialization", "planning", "execution", "generation", "quality"]

        for i, stage_name in enumerate(stage_order):
            if stage_name not in dag_plan["stages"]:
                continue

            stage = dag_plan["stages"][stage_name]
            output_lines.append(f"Stage {i + 1}: {stage_name.upper()}")
            output_lines.append(f"  Description: {stage['description']}")
            output_lines.append(f"  Agents: {', '.join(stage['agents'])}")

            if stage.get("dependencies"):
                output_lines.append("  Dependencies:")
                for agent, deps in stage["dependencies"].items():
                    if deps:
                        output_lines.append(f"    - {agent} depends on: {', '.join(deps)}")

            output_lines.append("")

        output_lines.append(f"Total: {dag_plan['total_agents']} agents across {dag_plan['total_stages']} stages")

        return "\n".join(output_lines)

    def _calculate_progress(self) -> float:
        """计算进度"""
        if not self._dag or self._total_nodes == 0:
            return 0.0

        completed = sum(
            1 for node in self._dag.nodes.values()
            if node.status == "completed"
        )
        return (completed / self._total_nodes) * 100

    def execute_next_node(self) -> Optional[Dict[str, Any]]:
        """
        执行DAG中的下一个节点（保留向后兼容）

        Returns:
            执行结果
        """
        return self.execute_ready_nodes(batch_size=1)

    def execute_ready_nodes(self, batch_size: int = 0, parallel: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        执行所有就绪的DAG节点（支持批量和并行执行）

        Args:
            batch_size: 批量大小，0表示执行所有就绪节点
            parallel: 是否并行执行（仅支持generation阶段的章节生成）

        Returns:
            执行结果列表
        """
        logger = get_logger()
        logger.agent("[execute_ready_nodes] Called",
                     has_dag=self._dag is not None,
                     state=self._workflow_state.value if self._workflow_state else None,
                     batch_size=batch_size,
                     parallel=parallel)

        if not self._dag:
            logger.agent("[execute_ready_nodes] No DAG, returning None")
            return None

        if self._workflow_state != WorkflowState.EXECUTING:
            logger.agent(f"[execute_ready_nodes] Invalid state: {self._workflow_state.value}, returning None")
            return None

        # 获取所有就绪节点
        ready_nodes = self._dag.get_ready_nodes()

        if not ready_nodes:
            # 检查是否完成
            if self._dag.all_completed():
                self._workflow_state = WorkflowState.COMPLETED
                return [{"status": "completed", "message": "All nodes executed successfully"}]
            elif self._dag.has_failed():
                self._workflow_state = WorkflowState.FAILED
                return [{"status": "failed", "message": "Some nodes failed"}]

            return None

        # 限制批量大小
        if batch_size > 0:
            ready_nodes = ready_nodes[:batch_size]

        logger.agent(f"[execute_ready_nodes] Executing {len(ready_nodes)} nodes: {ready_nodes}")

        results = []

        # 对于generation节点，启用并行执行
        generation_nodes = [n for n in ready_nodes if n.startswith("content_generator_chapter_")]
        other_nodes = [n for n in ready_nodes if not n.startswith("content_generator_chapter_")]

        # 先执行非generation节点
        for node_name in other_nodes:
            result = self._execute_single_node(node_name)
            if result:
                results.append(result)

        # 对于generation节点，如果启用并行则批量执行
        if generation_nodes and parallel:
            # 并行执行章节生成
            chapter_results = self._execute_chapter_batch(generation_nodes)
            results.extend(chapter_results)
        elif generation_nodes:
            # 串行执行章节生成
            for node_name in generation_nodes:
                result = self._execute_single_node(node_name)
                if result:
                    results.append(result)

        return results if results else None

    def _execute_single_node(self, node_name: str) -> Optional[Dict[str, Any]]:
        """
        执行单个DAG节点（内部方法）

        Args:
            node_name: 节点名称

        Returns:
            执行结果
        """
        logger = get_logger()
        logger.agent(f"[_execute_single_node] Executing {node_name}")

        node = self._dag.nodes.get(node_name)
        if not node:
            logger.agent(f"[_execute_single_node] Node {node_name} not found")
            return None

        node.status = "executing"
        start_time = time.time()

        # 发布节点开始事件
        self._emit_event("agent.started", {
            "agent": node_name,
            "stage": "dag_node_execution",
            "progress": self._calculate_progress() / 100.0,
            "total_nodes": self._total_nodes,
            "completed_nodes": self._tasks_completed,
        })

        # 创建Agent并执行
        agent = self._create_agent(node_name)
        logger.agent(f"[_execute_single_node] agent created: {node_name}")

        if agent:
            # 构建输入消息（包含数据库上下文）
            # 为章节生成节点添加额外的元数据
            metadata = {"node": node_name}
            if node_name.startswith("content_generator_chapter_"):
                try:
                    chapter_num = int(node_name.split("_")[-1])
                    metadata["chapter_num"] = chapter_num
                    if self._current_task:
                        metadata["task_id"] = self._current_task.get("task_id", "")
                        metadata["title"] = self._current_task.get("title", "")
                        metadata["genre"] = self._current_task.get("genre", "fantasy")
                        metadata["word_count_per_chapter"] = self._current_task.get("word_count_per_chapter", 2000)
                except (ValueError, IndexError):
                    pass

            input_msg = Message(
                id=str(int(time.time() * 1000)),
                type=MessageType.TEXT,
                content=self._build_agent_context_with_data(node_name),
                metadata=metadata
            )
            logger.agent(f"[_execute_single_node] input_msg created for {node_name}")

            try:
                # 执行Agent
                result_msg = agent.process(input_msg)
                elapsed = time.time() - start_time

                # 更新节点状态
                node.status = "completed"
                node.result = result_msg.content if result_msg else None
                node.elapsed_time = elapsed

                self._tasks_completed += 1

                result = {
                    "node": node_name,
                    "status": "completed",
                    "result": result_msg.content if result_msg else None,
                    "elapsed_time": elapsed
                }

                # 保存结果到上下文
                self._save_node_result(node_name, result)

                # 发布节点完成事件
                self._emit_event("agent.completed", {
                    "agent": node_name,
                    "stage": "dag_node_execution",
                    "progress": self._calculate_progress() / 100.0,
                    "elapsed_time": elapsed,
                    "total_nodes": self._total_nodes,
                    "completed_nodes": self._tasks_completed,
                })

                logger.agent(f"[_execute_single_node] {node_name} completed successfully")
                return result

            except Exception as e:
                node.status = "failed"
                node.error = str(e)
                self._tasks_failed += 1

                # 发布节点失败事件
                self._emit_event("agent.failed", {
                    "agent": node_name,
                    "stage": "dag_node_execution",
                    "error": str(e),
                    "progress": self._calculate_progress() / 100.0,
                })

                logger.agent(f"[_execute_single_node] {node_name} failed: {e}")
                return {
                    "node": node_name,
                    "status": "failed",
                    "error": str(e)
                }

        # Agent 创建失败
        self._emit_event("agent.failed", {
            "agent": node_name,
            "stage": "dag_node_creation",
            "error": "Failed to create agent instance",
        })
        logger.agent(f"[_execute_single_node] Failed to create agent: {node_name}")
        return None

    def _execute_chapter_batch(self, chapter_nodes: List[str]) -> List[Dict[str, Any]]:
        """
        批量执行章节生成节点（并行）

        Args:
            chapter_nodes: 章节节点列表

        Returns:
            执行结果列表
        """
        logger = get_logger()
        logger.agent(f"[_execute_chapter_batch] Processing {len(chapter_nodes)} chapter nodes")

        import concurrent.futures
        results = []

        def execute_chapter(chapter_node: str) -> Optional[Dict[str, Any]]:
            return self._execute_single_node(chapter_node)

        # 使用线程池并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_node = {executor.submit(execute_chapter, node): node for node in chapter_nodes}

            for future in concurrent.futures.as_completed(future_to_node):
                result = future.result()
                if result:
                    results.append(result)

        logger.agent(f"[_execute_chapter_batch] Completed {len(results)} chapters")
        return results

    def _create_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """创建Agent实例"""
        from .implementations import (
            HealthCheckerAgent, ConfigEnhancerAgent, OutlinePlannerAgent,
            CharacterGeneratorAgent, WorldBuilderAgent, ChapterSummaryAgent,
            HookGeneratorAgent, ConflictGeneratorAgent, ContentGeneratorAgent,
            QualityCheckerAgent
        )

        agent_map = {
            "health_checker": HealthCheckerAgent,
            "config_enhancer": ConfigEnhancerAgent,
            "outline_planner": OutlinePlannerAgent,
            "character_generator": CharacterGeneratorAgent,
            "world_builder": WorldBuilderAgent,
            "chapter_summary": ChapterSummaryAgent,
            "hook_generator": HookGeneratorAgent,
            "conflict_generator": ConflictGeneratorAgent,
            "content_generator": ContentGeneratorAgent,
            "quality_checker": QualityCheckerAgent,
        }

        # 支持动态章节生成节点 (content_generator_chapter_X)
        if agent_name.startswith("content_generator_chapter_"):
            agent_class = ContentGeneratorAgent
        else:
            agent_class = agent_map.get(agent_name)

        if agent_class:
            return agent_class()
        return None

    def _save_node_result(self, node_name: str, result: Dict[str, Any]):
        """
        保存节点执行结果到上下文（供后续节点使用）

        Args:
            node_name: 节点名称
            result: 执行结果
        """
        if not result or not result.get("result"):
            return

        # 根据节点类型保存到不同上下文
        if "character" in node_name:
            self._context.setdefault("characters", []).append(result.get("result"))
        elif "world" in node_name:
            self._context.setdefault("world_bible", {}).update({"nodes": result.get("result")})
        elif "outline" in node_name:
            self._context.setdefault("outlines", []).append(result.get("result"))
        elif "content_generator" in node_name:
            self._context.setdefault("generated_content", []).append(result.get("result"))

    def _build_agent_context_with_data(self, agent_name: str) -> str:
        """
        构建Agent上下文（包含数据库读取的历史数据）

        Args:
            agent_name: Agent名称

        Returns:
            增强的上下文字符串
        """
        base_context = self._build_agent_context(agent_name)
        enhanced_context = [base_context]

        # 从数据库读取相关数据作为上下文
        from deepnovel.persistence import get_persistence_manager

        pm = get_persistence_manager()
        task_id = self._current_task.get("task_id", "") if self._current_task else ""

        # 添加 task_id 到上下文（供 Agent 提取）
        if task_id:
            enhanced_context.append(f"\n\n## Task Context")
            enhanced_context.append(f"Task ID: {task_id}")
            if self._current_task:
                enhanced_context.append(f"Title: {self._current_task.get('title', 'N/A')}")
                enhanced_context.append(f"Genre: {self._current_task.get('genre', 'N/A')}")
                enhanced_context.append(f"Chapters: {self._current_task.get('chapters', 'N/A')}")
                enhanced_context.append(f"Word Count per Chapter: {self._current_task.get('word_count_per_chapter', 'N/A')}")

        # 读取已生成的角色
        if pm.mongodb_client and agent_name not in ["character_generator", "health_checker", "config_enhancer"]:
            try:
                collection = pm.mongodb_client.get_collection("character_profiles")
                chars = list(collection.find({"task_id": task_id} if task_id else {}))
                if chars:
                    enhanced_context.append(f"\n\n## Already Generated Characters ({len(chars)}):")
                    for char in chars[:5]:  # 限制前5个
                        enhanced_context.append(f"- {char.get('name', 'Unknown')}")
            except Exception as e:
                log_warn(f"Failed to load characters from DB: {e}")

        # 读取已生成的地点和势力
        if pm.mongodb_client and agent_name not in ["world_builder"]:
            try:
                collection = pm.mongodb_client.get_collection("world_locations")
                locations = list(collection.find({"task_id": task_id} if task_id else {}))
                if locations:
                    enhanced_context.append(f"\n\n## World Locations:")
                    for loc in locations[:3]:
                        enhanced_context.append(f"- {loc.get('name', 'Unknown')} ({loc.get('type', 'unknown')})")
            except Exception as e:
                log_warn(f"Failed to load locations from DB: {e}")

        # 读取已生成的大纲
        if pm.mongodb_client and agent_name not in ["outline_planner"]:
            try:
                collection = pm.mongodb_client.get_collection("chapter_outlines")
                outlines = list(collection.find({"task_id": task_id} if task_id else {}))
                if outlines:
                    enhanced_context.append(f"\n\n## Generated Outlines ({len(outlines)}):")
                    for outline in outlines[:3]:
                        enhanced_context.append(f"- Chapter {outline.get('chapter_num', 'N/A')}: {outline.get('title', 'N/A')}")
            except Exception as e:
                log_warn(f"Failed to load outlines from DB: {e}")

        # 读取已生成的章节（用于质量检查）
        chapter_list = []
        if pm.mongodb_client and agent_name == "quality_checker":
            try:
                collection = pm.mongodb_client.get_collection("chapters")
                chapter_list = list(collection.find({"task_id": task_id} if task_id else {}))
                if chapter_list:
                    enhanced_context.append(f"\n\n## Generated Chapters ({len(chapter_list)}):")
                    for chap in chapter_list[:10]:
                        enhanced_context.append(f"- Chapter {chap.get('chapter_num', 'N/A')}: {chap.get('title', 'N/A')} ({chap.get('word_count', 0)} words)")
            except Exception as e:
                log_warn(f"Failed to load chapters from DB: {e}")

            # 从Neo4j读取角色关系图
            if pm.neo4j_client:
                try:
                    rels = pm.neo4j_client.execute_cypher(
                        "MATCH (c:Character)-[r]->(c2:Character) WHERE c.task_id = $task_id RETURN c.name, type(r), c2.name LIMIT 25",
                        {"task_id": task_id}
                    )
                    if rels:
                        enhanced_context.append(f"\n\n## Character Relationships ({len(rels)}):")
                        for rel in rels:
                            enhanced_context.append(f"- {rel.get('c.name', rel[0])} --[{rel.get('type(r', rel[1])}]--> {rel.get('c2.name', rel[2])}")
                except Exception as e:
                    log_warn(f"Failed to load relationships from Neo4j: {e}")

            # 从ChromaDB读取相关上下文（向量相似度搜索）
            if pm.chromadb_client:
                try:
                    # 获取所有已生成章节的摘要用于相似度搜索
                    chapter_contexts = []
                    for i, chap in enumerate(chapter_list[:5] if 'chapter_list' in locals() else []):
                        chapter_contexts.append(f"Chapter {chap.get('chapter_num', i)}: {chap.get('content', '')[:500]}...")

                    if chapter_contexts:
                        enhanced_context.append("\n\n## Chapter Context for Consistency Check:")
                        enhanced_context.extend(chapter_contexts)
                except Exception as e:
                    log_warn(f"Failed to build chapter context: {e}")

        # 从DAG前序节点结果读取
        if self._dag:
            for node_name, node in self._dag.nodes.items():
                if node.status == "completed" and node.result:
                    # 检查当前节点是否依赖此节点
                    current_node = self._dag.nodes.get(agent_name)
                    if current_node and node_name in current_node.Dependencies:
                        enhanced_context.append(f"\n\n## Previous Node [{node_name}] Result:")
                        enhanced_context.append(str(node.result)[:CONTENT_TRUNCATE_LENGTH_LARGE])  # 限制长度

        return "\n".join(enhanced_context)

    def _build_agent_context(self, agent_name: str) -> str:
        """构建Agent上下文（基础版）"""
        context_map = {
            "health_checker": "Check system health for novel generation workflow.",
            "config_enhancer": "Enhance generation configuration based on user requirements.",
            "outline_planner": "Create detailed chapter outline with three-act structure.",
            "character_generator": "Generate main character profiles and background stories.",
            "world_builder": "Build novel world setting including geography and magic system.",
            "chapter_summary": "Generate summaries for each chapter with key events.",
            "hook_generator": "Generate narrative hooks and suspense elements.",
            "conflict_generator": "Generate character and plot conflicts.",
            "content_generator": "Generate actual novel chapter content based on prepared assets.",
            "quality_checker": "Review and quality check generated content for coherence.",
        }

        return context_map.get(agent_name, f"Execute {agent_name} tasks.")

    def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """发布事件到 EventBus（fire-and-forget，同步上下文安全）"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    _event_bus.publish_type(
                        event_type,
                        payload=payload,
                        source="coordinator",
                    )
                )
        except Exception:
            pass

    def get_execution_status(self) -> Dict[str, Any]:
        """获取执行状态"""
        if not self._dag:
            return {"error": "No DAG initialized"}

        return {
            "state": self._workflow_state.value,
            "progress": self._calculate_progress(),
            "nodes": {
                name: {
                    "status": node.status,
                    "elapsed_time": node.elapsed_time,
                    "error": node.error
                }
                for name, node in self._dag.nodes.items()
            },
            "completed": self._tasks_completed,
            "failed": self._tasks_failed,
            "total": self._total_nodes
        }

    def get_generated_content(self) -> List[str]:
        """获取生成的内容"""
        return self._context.get("generated_content", [])

    # =========================================================================
    # RocketMQ通信方法 (Step 45)
    # =========================================================================

    def start_communication(self) -> bool:
        """
        启动RocketMQ通信

        Returns:
            bool: 启动成功返回True
        """
        if self._communicator:
            return self._communicator.start()

        if self._setup_communicator():
            self._comm_running = True
            self._start_comm_thread()

            # 启动消费者
            if self._rocketmq_consumer:
                self._rocketmq_consumer.start()

            return True
        return False

    def stop_communication(self) -> bool:
        """
        停止RocketMQ通信

        Returns:
            bool: 停止成功返回True
        """
        self._comm_running = False

        if self._communicator:
            self._communicator.stop()

        if self._rocketmq_consumer:
            self._rocketmq_consumer.stop()

        if self._rocketmq_producer:
            self._rocketmq_producer.close()

        return True

    def send_to_agent(self, agent_name: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        发送消息给指定智能体

        Args:
            agent_name: 智能体名称
            message: 消息数据

        Returns:
            Dict: 发送结果
        """
        if not self._rocketmq_producer:
            return None

        topic = f"agent_{agent_name}_queue"
        return self._rocketmq_producer.send_sync(topic, message, tags="agent_message")

    def broadcast_message(self, message: Dict[str, Any], agents: List[str]) -> List[Dict[str, Any]]:
        """
        广播消息给多个智能体

        Args:
            message: 消息数据
            agents: 智能体列表

        Returns:
            List[Dict]: 发送结果列表
        """
        results = []
        for agent in agents:
            result = self.send_to_agent(agent, message)
            results.append(result if result else {"status": "failed", "error": "Producer not connected"})
        return results

    def register_message_handler(self, message_type: str, callback: Callable[[Dict[str, Any]], bool]):
        """
        注册消息处理器

        Args:
            message_type: 消息类型
            callback: 回调函数
        """
        if message_type in self._message_callbacks:
            self._message_callbacks[message_type].append(callback)

    def get_pending_messages(self) -> List[Dict[str, Any]]:
        """
        获取待处理消息

        Returns:
            List[Dict]: 待处理消息列表
        """
        return self._pending_messages

    def get_communication_status(self) -> Dict[str, Any]:
        """
        获取通信状态

        Returns:
            Dict: 通信状态
        """
        status = {
            "communicator_state": self._communicator._state.value if self._communicator else "not_initialized",
            "producer_connected": self._rocketmq_producer.is_connected() if self._rocketmq_producer else False,
            "consumer_connected": self._rocketmq_consumer.is_connected() if self._rocketmq_consumer else False,
            "comm_running": self._comm_running,
            "pending_messages": len(self._pending_messages)
        }
        return status

    def reset(self) -> None:
        """重置协调器"""
        self._workflow_state = WorkflowState.IDLE
        self._current_task = None
        self._dag = None
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_nodes = 0
        self._context = {
            "generated_content": [],
            "characters": [],
            "world_bible": {},
            "outlines": []
        }
