"""
多智能体工作流编排器

基于 agent-team-orchestration Skill 实现多 Agent 协作

@file: agents/workflow_orchestrator.py
@date: 2026-04-08
@author: AI-Novels Team
@version: 2.0
@description: 多智能体协作工作流编排
"""

import time
import uuid
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from ai_novels.utils import log_error, log_info, get_logger
from ai_novels.agents.base import BaseAgent, AgentConfig, Message, MessageType


class TaskState(Enum):
    """任务状态枚举"""
    INBOX = "inbox"           # 待分配
    ASSIGNED = "assigned"     # 已分配
    IN_PROGRESS = "in_progress"  # 执行中
    REVIEW = "review"         # 审查中
    DONE = "done"             # 已完成
    FAILED = "failed"         # 失败
    PAUSED = "paused"         # 已暂停
    CANCELLED = "cancelled"   # 已取消


class HandoffType(Enum):
    """交接类型"""
    SEQUENTIAL = "sequential"    # 顺序执行
    PARALLEL = "parallel"        # 并行执行
    CONDITIONAL = "conditional"  # 条件执行


@dataclass
class TaskComment:
    """任务评论"""
    id: str
    task_id: str
    author: str
    content: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "author": self.author,
            "content": self.content,
            "timestamp": self.timestamp
        }


@dataclass
class WorkflowTask:
    """工作流任务"""
    id: str
    name: str
    description: str
    agent_name: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.INBOX
    dependencies: List[str] = field(default_factory=list)
    next_tasks: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    comments: List[TaskComment] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent_name": self.agent_name,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "state": self.state.value,
            "dependencies": self.dependencies,
            "next_tasks": self.next_tasks,
            "condition": self.condition,
            "comments": [c.to_dict() for c in self.comments],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count
        }
    
    def add_comment(self, author: str, content: str):
        """添加评论"""
        comment = TaskComment(
            id=str(uuid.uuid4()),
            task_id=self.id,
            author=author,
            content=content
        )
        self.comments.append(comment)
    
    def transition_to(self, new_state: TaskState, reason: str = ""):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        
        if new_state == TaskState.IN_PROGRESS:
            self.started_at = time.time()
        elif new_state in [TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED]:
            self.completed_at = time.time()
        
        self.add_comment(
            author="system",
            content=f"状态转换: {old_state.value} → {new_state.value}. {reason}"
        )


@dataclass
class WorkflowStage:
    """工作流阶段"""
    name: str
    description: str
    agent_name: str
    input_mapping: Dict[str, str]  # 输入数据映射
    output_mapping: Dict[str, str]  # 输出数据映射
    next_stages: List[str] = field(default_factory=list)
    condition: Optional[str] = None  # 执行条件
    handoff_type: HandoffType = HandoffType.SEQUENTIAL


@dataclass
class WorkflowDefinition:
    """工作流定义"""
    name: str
    description: str
    stages: List[WorkflowStage]
    version: str = "1.0.0"
    
    def get_stage(self, name: str) -> Optional[WorkflowStage]:
        """获取阶段定义"""
        for stage in self.stages:
            if stage.name == name:
                return stage
        return None


class WorkflowOrchestrator:
    """
    工作流编排器
    
    管理多智能体协作的工作流执行
    """
    
    def __init__(self):
        """初始化编排器"""
        self._agents: Dict[str, BaseAgent] = {}
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._tasks: Dict[str, WorkflowTask] = {}
        self._task_history: List[str] = []
        self._logger = get_logger()
        
        # 注册默认工作流
        self._register_default_workflows()
    
    def register_agent(self, agent: BaseAgent) -> bool:
        """
        注册智能体
        
        Args:
            agent: 智能体实例
            
        Returns:
            是否成功
        """
        try:
            agent.initialize()
            self._agents[agent.name] = agent
            self._logger.agent(f"Agent registered: {agent.name}")
            return True
        except Exception as e:
            self._logger.agent_error(f"Failed to register agent {agent.name}: {e}")
            return False
    
    def register_workflow(self, workflow: WorkflowDefinition):
        """
        注册工作流
        
        Args:
            workflow: 工作流定义
        """
        self._workflows[workflow.name] = workflow
        self._logger.agent(f"Workflow registered: {workflow.name}")
    
    def create_task(
        self,
        workflow_name: str,
        initial_data: Dict[str, Any],
        task_name: str = ""
    ) -> Optional[WorkflowTask]:
        """
        创建任务
        
        Args:
            workflow_name: 工作流名称
            initial_data: 初始数据
            task_name: 任务名称
            
        Returns:
            创建的任务
        """
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            self._logger.agent_error(f"Workflow not found: {workflow_name}")
            return None
        
        # 创建任务
        task = WorkflowTask(
            id=str(uuid.uuid4()),
            name=task_name or f"{workflow_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=workflow.description,
            agent_name="orchestrator",
            input_data={
                "workflow_name": workflow_name,
                "initial_data": initial_data,
                "current_stage": workflow.stages[0].name if workflow.stages else None
            }
        )
        
        self._tasks[task.id] = task
        self._task_history.append(task.id)
        
        self._logger.agent(f"Task created: {task.id} for workflow {workflow_name}")
        return task
    
    def execute_task(self, task_id: str) -> bool:
        """
        执行任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not task:
            self._logger.agent_error(f"Task not found: {task_id}")
            return False
        
        workflow_name = task.input_data.get("workflow_name")
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            self._logger.agent_error(f"Workflow not found: {workflow_name}")
            return False
        
        # 开始执行
        task.transition_to(TaskState.IN_PROGRESS, "开始执行工作流")
        
        try:
            # 获取当前阶段
            current_stage_name = task.input_data.get("current_stage")
            if not current_stage_name:
                task.transition_to(TaskState.DONE, "工作流完成")
                return True
            
            stage = workflow.get_stage(current_stage_name)
            if not stage:
                task.transition_to(TaskState.FAILED, f"Stage not found: {current_stage_name}")
                return False
            
            # 执行阶段
            success = self._execute_stage(task, stage, workflow)
            
            if success:
                # 检查是否有下一阶段
                if stage.next_stages:
                    next_stage_name = self._determine_next_stage(task, stage)
                    if next_stage_name:
                        task.input_data["current_stage"] = next_stage_name
                        task.transition_to(TaskState.INBOX, f"进入下一阶段: {next_stage_name}")
                        # 递归执行
                        return self.execute_task(task_id)
                    else:
                        task.transition_to(TaskState.DONE, "工作流完成")
                else:
                    task.transition_to(TaskState.DONE, "工作流完成")
            else:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.transition_to(TaskState.IN_PROGRESS, f"重试第{task.retry_count}次")
                    return self.execute_task(task_id)
                else:
                    task.transition_to(TaskState.FAILED, "达到最大重试次数")
            
            return success
            
        except Exception as e:
            self._logger.agent_error(f"Task execution failed: {e}")
            task.transition_to(TaskState.FAILED, f"执行异常: {str(e)}")
            return False
    
    def _execute_stage(
        self,
        task: WorkflowTask,
        stage: WorkflowStage,
        workflow: WorkflowDefinition
    ) -> bool:
        """
        执行阶段
        
        Args:
            task: 任务
            stage: 阶段定义
            workflow: 工作流定义
            
        Returns:
            是否成功
        """
        # 获取智能体
        agent = self._agents.get(stage.agent_name)
        if not agent:
            self._logger.agent_error(f"Agent not found: {stage.agent_name}")
            return False
        
        # 准备输入数据
        input_data = self._prepare_stage_input(task, stage)
        
        # 创建消息
        message = Message(
            id=str(uuid.uuid4()),
            type=MessageType.TEXT,
            content=input_data,
            sender="orchestrator",
            receiver=stage.agent_name
        )
        
        # 记录开始
        task.add_comment("orchestrator", f"开始执行阶段: {stage.name}")
        
        try:
            # 执行
            response = agent.process(message)
            
            if response:
                # 处理输出
                self._process_stage_output(task, stage, response.content)
                task.add_comment(stage.agent_name, f"阶段完成: {stage.name}")
                return True
            else:
                task.add_comment(stage.agent_name, f"阶段执行无响应: {stage.name}")
                return False
                
        except Exception as e:
            task.add_comment(stage.agent_name, f"阶段执行异常: {str(e)}")
            return False
    
    def _prepare_stage_input(
        self,
        task: WorkflowTask,
        stage: WorkflowStage
    ) -> Dict[str, Any]:
        """
        准备阶段输入
        
        Args:
            task: 任务
            stage: 阶段定义
            
        Returns:
            输入数据
        """
        input_data = {}
        
        # 根据映射准备输入
        for key, source in stage.input_mapping.items():
            if source.startswith("task."):
                # 从任务数据中获取
                path = source.replace("task.", "").split(".")
                value = task.input_data
                for p in path:
                    value = value.get(p, {}) if isinstance(value, dict) else {}
                input_data[key] = value
            elif source.startswith("output."):
                # 从输出数据中获取
                path = source.replace("output.", "").split(".")
                value = task.output_data
                for p in path:
                    value = value.get(p, {}) if isinstance(value, dict) else {}
                input_data[key] = value
        
        return input_data
    
    def _process_stage_output(
        self,
        task: WorkflowTask,
        stage: WorkflowStage,
        output: Any
    ):
        """
        处理阶段输出
        
        Args:
            task: 任务
            stage: 阶段定义
            output: 输出数据
        """
        # 根据映射存储输出
        for key, target in stage.output_mapping.items():
            if target.startswith("output."):
                path = target.replace("output.", "").split(".")
                current = task.output_data
                for p in path[:-1]:
                    if p not in current:
                        current[p] = {}
                    current = current[p]
                current[path[-1]] = output.get(key) if isinstance(output, dict) else output
    
    def _determine_next_stage(
        self,
        task: WorkflowTask,
        current_stage: WorkflowStage
    ) -> Optional[str]:
        """
        确定下一阶段
        
        Args:
            task: 任务
            current_stage: 当前阶段
            
        Returns:
            下一阶段名称
        """
        if not current_stage.next_stages:
            return None
        
        # 如果有条件，评估条件
        if current_stage.condition:
            # 简单条件评估（可以扩展为更复杂的逻辑）
            condition_met = self._evaluate_condition(task, current_stage.condition)
            if condition_met and current_stage.next_stages:
                return current_stage.next_stages[0]
            elif len(current_stage.next_stages) > 1:
                return current_stage.next_stages[1]
            else:
                return None
        
        # 默认返回第一个下一阶段
        return current_stage.next_stages[0] if current_stage.next_stages else None
    
    def _evaluate_condition(self, task: WorkflowTask, condition: str) -> bool:
        """
        评估条件
        
        Args:
            task: 任务
            condition: 条件表达式
            
        Returns:
            条件是否满足
        """
        # 简单条件评估
        # 例如: "quality_score > 7"
        try:
            # 从任务数据中获取变量
            context = {
                "output": task.output_data,
                "input": task.input_data
            }
            
            # 安全评估（简化版）
            if ">" in condition:
                parts = condition.split(">")
                var_path = parts[0].strip()
                threshold = float(parts[1].strip())
                
                # 获取变量值
                value = self._get_nested_value(context, var_path)
                if value is not None:
                    return float(value) > threshold
            
            return True
        except Exception as e:
            self._logger.agent_error(f"Condition evaluation failed: {e}")
            return True
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """获取嵌套字典值"""
        parts = path.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current
    
    def pause_task(self, task_id: str) -> bool:
        """
        暂停任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if task and task.state == TaskState.IN_PROGRESS:
            task.transition_to(TaskState.PAUSED, "用户请求暂停")
            return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """
        恢复任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if task and task.state == TaskState.PAUSED:
            task.transition_to(TaskState.IN_PROGRESS, "用户请求恢复")
            return self.execute_task(task_id)
        return False
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if task and task.state not in [TaskState.DONE, TaskState.FAILED, TaskState.CANCELLED]:
            task.transition_to(TaskState.CANCELLED, "用户请求取消")
            return True
        return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态
        """
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def list_tasks(self, state: Optional[TaskState] = None) -> List[Dict[str, Any]]:
        """
        列出任务
        
        Args:
            state: 过滤状态
            
        Returns:
            任务列表
        """
        tasks = []
        for task in self._tasks.values():
            if state is None or task.state == state:
                tasks.append(task.to_dict())
        return tasks
    
    def _register_default_workflows(self):
        """注册默认工作流"""
        # 小说生成工作流
        novel_workflow = WorkflowDefinition(
            name="novel_generation",
            description="小说生成完整工作流",
            stages=[
                WorkflowStage(
                    name="需求分析",
                    description="分析用户需求，生成详细配置",
                    agent_name="config_enhancer",
                    input_mapping={
                        "user_requirements": "task.initial_data.requirements",
                        "genre_hint": "task.initial_data.genre"
                    },
                    output_mapping={
                        "config": "output.generation_config"
                    },
                    next_stages=["大纲规划"]
                ),
                WorkflowStage(
                    name="大纲规划",
                    description="创建小说大纲和章节结构",
                    agent_name="outline_planner",
                    input_mapping={
                        "config": "output.generation_config"
                    },
                    output_mapping={
                        "outline": "output.outline",
                        "chapters": "output.chapter_list"
                    },
                    next_stages=["角色生成", "世界构建"],
                    handoff_type=HandoffType.PARALLEL
                ),
                WorkflowStage(
                    name="角色生成",
                    description="创建详细角色档案",
                    agent_name="character_generator",
                    input_mapping={
                        "outline": "output.outline",
                        "config": "output.generation_config"
                    },
                    output_mapping={
                        "characters": "output.character_profiles"
                    },
                    next_stages=["内容生成"]
                ),
                WorkflowStage(
                    name="世界构建",
                    description="构建世界观和背景设定",
                    agent_name="world_builder",
                    input_mapping={
                        "outline": "output.outline",
                        "config": "output.generation_config"
                    },
                    output_mapping={
                        "world": "output.world_setting"
                    },
                    next_stages=["内容生成"]
                ),
                WorkflowStage(
                    name="内容生成",
                    description="生成小说章节内容",
                    agent_name="content_generator",
                    input_mapping={
                        "outline": "output.outline",
                        "characters": "output.character_profiles",
                        "world": "output.world_setting",
                        "config": "output.generation_config"
                    },
                    output_mapping={
                        "chapters": "output.generated_chapters"
                    },
                    next_stages=["质量检查"]
                ),
                WorkflowStage(
                    name="质量检查",
                    description="检查生成内容质量",
                    agent_name="quality_checker",
                    input_mapping={
                        "chapters": "output.generated_chapters"
                    },
                    output_mapping={
                        "report": "output.quality_report"
                    },
                    next_stages=["文本润色", "内容生成"],
                    condition="quality_score > 7"
                ),
                WorkflowStage(
                    name="文本润色",
                    description="去除AI痕迹，增加人性化",
                    agent_name="humanizer",
                    input_mapping={
                        "chapters": "output.generated_chapters"
                    },
                    output_mapping={
                        "final_chapters": "output.final_content"
                    },
                    next_stages=[]
                )
            ]
        )
        
        self.register_workflow(novel_workflow)


# 全局实例
_orchestrator: Optional[WorkflowOrchestrator] = None


def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """获取工作流编排器实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = WorkflowOrchestrator()
    return _orchestrator
