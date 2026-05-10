"""
增强型多智能体工作流编排器

集成上下文传递和消息交流增强功能

@file: agents/enhanced_workflow_orchestrator.py
@date: 2026-04-08
@author: AI-Novels Team
@version: 3.0
@description: 增强的多智能体协作工作流编排，支持上下文传递
"""

import time
import uuid
import copy
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import threading

from deepnovel.utils import log_error, log_info, log_warn, get_logger
from deepnovel.agents.base import BaseAgent, AgentConfig, Message, MessageType
from deepnovel.agents.workflow_orchestrator import (
    WorkflowOrchestrator, WorkflowTask, WorkflowStage, 
    WorkflowDefinition, TaskState, HandoffType, TaskComment
)
from deepnovel.agents.enhanced_communicator import (
    EnhancedAgentCommunicator, MessageEnvelope, MessagePriority,
    Conversation, create_enhanced_communicator
)
from deepnovel.core.context_manager import (
    ContextManager, ContextScope, ContextPriority,
    shared_context_pool, create_context_manager
)


@dataclass
class ContextHandoffConfig:
    """上下文交接配置"""
    include_local: bool = False      # 是否包含本地上下文
    include_shared: bool = True      # 是否包含共享上下文
    include_global: bool = True      # 是否包含全局上下文
    keys_filter: List[str] = field(default_factory=list)  # 键过滤列表
    keys_exclude: List[str] = field(default_factory=list)  # 排除键列表
    transform_script: Optional[str] = None  # 转换脚本（可选）


@dataclass
class EnhancedWorkflowStage(WorkflowStage):
    """增强的工作流阶段"""
    # 上下文交接配置
    context_handoff: ContextHandoffConfig = field(default_factory=ContextHandoffConfig)
    # 是否创建上下文快照
    create_snapshot: bool = True
    # 是否等待上下文同步确认
    wait_context_sync: bool = False
    # 并行执行时的上下文合并策略
    parallel_merge_strategy: str = "merge"  # merge/override/append
    # 阶段特定的系统提示词增强
    system_prompt_addon: str = ""


@dataclass
class EnhancedWorkflowTask(WorkflowTask):
    """增强的工作流任务"""
    # 会话ID
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # 上下文快照ID列表
    context_snapshots: List[str] = field(default_factory=list)
    # 参与的Agent列表
    participating_agents: Set[str] = field(default_factory=set)
    # 对话ID列表
    conversation_ids: List[str] = field(default_factory=list)
    # 全局上下文数据（跨阶段共享）
    global_context: Dict[str, Any] = field(default_factory=dict)
    # 阶段执行历史
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_stage_execution(
        self,
        stage_name: str,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        context_snapshot_id: str = None
    ):
        """记录阶段执行"""
        self.stage_history.append({
            "stage_name": stage_name,
            "agent_name": agent_name,
            "timestamp": time.time(),
            "input_data": copy.deepcopy(input_data),
            "output_data": copy.deepcopy(output_data),
            "context_snapshot_id": context_snapshot_id
        })
        self.participating_agents.add(agent_name)


class EnhancedWorkflowOrchestrator(WorkflowOrchestrator):
    """
    增强型工作流编排器
    
    新增功能：
    1. 跨Agent上下文自动传递
    2. 上下文快照和恢复
    3. 对话会话管理
    4. 并行阶段的上下文合并
    5. 增强的消息交流
    """
    
    def __init__(self):
        """初始化增强编排器"""
        super().__init__()
        
        # 增强通信器
        self._communicators: Dict[str, EnhancedAgentCommunicator] = {}
        
        # 上下文管理器
        self._context_managers: Dict[str, ContextManager] = {}
        
        # 会话管理
        self._session_contexts: Dict[str, ContextManager] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        self._logger.agent("EnhancedWorkflowOrchestrator initialized")
    
    def register_agent(
        self,
        agent: BaseAgent,
        enable_enhanced_communication: bool = True
    ) -> bool:
        """
        注册智能体（增强版）
        
        Args:
            agent: 智能体实例
            enable_enhanced_communication: 是否启用增强通信
            
        Returns:
            是否成功
        """
        # 先注册到基础编排器
        if not super().register_agent(agent):
            return False
        
        if enable_enhanced_communication:
            try:
                # 创建增强通信器
                communicator = create_enhanced_communicator(
                    agent_name=agent.name,
                    session_id=str(uuid.uuid4())
                )
                
                if communicator.initialize():
                    with self._lock:
                        self._communicators[agent.name] = communicator
                    
                    # 获取上下文管理器
                    context_manager = communicator.get_context_manager()
                    if context_manager:
                        with self._lock:
                            self._context_managers[agent.name] = context_manager
                    
                    self._logger.agent(f"Enhanced communication enabled for agent: {agent.name}")
                    return True
                else:
                    log_warn(f"Failed to initialize enhanced communicator for {agent.name}")
                    return True  # 基础注册成功
                    
            except Exception as e:
                log_error(f"Failed to setup enhanced communication for {agent.name}: {e}")
                return True  # 基础注册成功
        
        return True
    
    def create_task(
        self,
        workflow_name: str,
        initial_data: Dict[str, Any],
        task_name: str = "",
        session_id: str = None
    ) -> Optional[EnhancedWorkflowTask]:
        """
        创建增强任务
        
        Args:
            workflow_name: 工作流名称
            initial_data: 初始数据
            task_name: 任务名称
            session_id: 会话ID
            
        Returns:
            增强任务
        """
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            self._logger.agent_error(f"Workflow not found: {workflow_name}")
            return None
        
        # 创建会话上下文
        session_id = session_id or str(uuid.uuid4())
        session_context = create_context_manager(
            agent_name="orchestrator",
            session_id=session_id
        )
        
        with self._lock:
            self._session_contexts[session_id] = session_context
        
        # 设置初始上下文
        for key, value in initial_data.items():
            session_context.set(
                key=key,
                value=value,
                scope=ContextScope.SHARED,
                priority=ContextPriority.HIGH
            )
        
        # 创建增强任务
        task = EnhancedWorkflowTask(
            id=str(uuid.uuid4()),
            name=task_name or f"{workflow_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=workflow.description,
            agent_name="orchestrator",
            input_data={
                "workflow_name": workflow_name,
                "initial_data": initial_data,
                "current_stage": workflow.stages[0].name if workflow.stages else None,
                "session_id": session_id
            },
            session_id=session_id
        )
        
        # 存储任务（使用父类的存储）
        self._tasks[task.id] = task
        self._task_history.append(task.id)
        
        self._logger.agent(f"Enhanced task created: {task.id} for workflow {workflow_name}")
        return task
    
    def execute_task(self, task_id: str) -> bool:
        """
        执行任务（增强版）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not task or not isinstance(task, EnhancedWorkflowTask):
            return super().execute_task(task_id)
        
        workflow_name = task.input_data.get("workflow_name")
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            self._logger.agent_error(f"Workflow not found: {workflow_name}")
            return False
        
        # 开始执行
        task.transition_to(TaskState.IN_PROGRESS, "开始执行增强工作流")
        
        try:
            # 获取会话上下文
            session_context = self._session_contexts.get(task.session_id)
            
            # 获取当前阶段
            current_stage_name = task.input_data.get("current_stage")
            if not current_stage_name:
                task.transition_to(TaskState.DONE, "工作流完成")
                return True
            
            stage = workflow.get_stage(current_stage_name)
            if not stage:
                task.transition_to(TaskState.FAILED, f"Stage not found: {current_stage_name}")
                return False
            
            # 执行阶段（增强版）
            success = self._execute_stage_enhanced(task, stage, workflow, session_context)
            
            if success:
                # 处理下一阶段
                if stage.next_stages:
                    if isinstance(stage, EnhancedWorkflowStage) and stage.handoff_type == HandoffType.PARALLEL:
                        # 并行执行
                        success = self._execute_parallel_stages(task, stage, workflow, session_context)
                    else:
                        # 顺序执行
                        next_stage_name = self._determine_next_stage(task, stage)
                        if next_stage_name:
                            task.input_data["current_stage"] = next_stage_name
                            task.transition_to(TaskState.INBOX, f"进入下一阶段: {next_stage_name}")
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
            self._logger.agent_error(f"Enhanced task execution failed: {e}")
            task.transition_to(TaskState.FAILED, f"执行异常: {str(e)}")
            return False
    
    def _execute_stage_enhanced(
        self,
        task: EnhancedWorkflowTask,
        stage: WorkflowStage,
        workflow: WorkflowDefinition,
        session_context: ContextManager
    ) -> bool:
        """
        增强的阶段执行
        
        Args:
            task: 任务
            stage: 阶段定义
            workflow: 工作流定义
            session_context: 会话上下文
            
        Returns:
            是否成功
        """
        agent = self._agents.get(stage.agent_name)
        if not agent:
            self._logger.agent_error(f"Agent not found: {stage.agent_name}")
            return False
        
        # 准备输入数据
        input_data = self._prepare_stage_input(task, stage)
        
        # 添加上下文到输入
        if session_context:
            input_data["_context"] = session_context.get_all(ContextScope.SHARED)
            input_data["_session_id"] = task.session_id
        
        # 获取Agent的通信器
        communicator = self._communicators.get(stage.agent_name)
        
        # 创建上下文快照（执行前）
        pre_snapshot_id = None
        if isinstance(stage, EnhancedWorkflowStage) and stage.create_snapshot and session_context:
            pre_snapshot = session_context.create_snapshot(
                metadata={
                    "task_id": task.id,
                    "stage": stage.name,
                    "type": "pre_execution"
                }
            )
            pre_snapshot_id = pre_snapshot.snapshot_id
            task.context_snapshots.append(pre_snapshot_id)
        
        # 传递上下文给Agent
        if communicator and session_context:
            self._handoff_context_to_agent(
                task, stage, session_context, communicator
            )
        
        # 记录开始
        task.add_comment("orchestrator", f"开始执行增强阶段: {stage.name}")
        
        try:
            # 执行
            if communicator:
                # 使用增强通信
                response_envelope = communicator.send_request(
                    receiver=stage.agent_name,
                    request_type="execute_stage",
                    payload={
                        "stage_name": stage.name,
                        "input_data": input_data,
                        "task_id": task.id
                    },
                    timeout=300,  # 5分钟超时
                    include_context=True
                )
                
                if response_envelope:
                    output = response_envelope.payload.get("result")
                    
                    # 处理输出
                    self._process_stage_output(task, stage, output)
                    
                    # 从响应导入上下文
                    if response_envelope.context_data and session_context:
                        self._import_context_from_response(
                            task, stage, session_context, response_envelope.context_data
                        )
                    
                    # 创建执行后快照
                    post_snapshot_id = None
                    if isinstance(stage, EnhancedWorkflowStage) and stage.create_snapshot and session_context:
                        post_snapshot = session_context.create_snapshot(
                            metadata={
                                "task_id": task.id,
                                "stage": stage.name,
                                "type": "post_execution"
                            }
                        )
                        post_snapshot_id = post_snapshot.snapshot_id
                        task.context_snapshots.append(post_snapshot_id)
                    
                    # 记录执行历史
                    task.record_stage_execution(
                        stage_name=stage.name,
                        agent_name=stage.agent_name,
                        input_data=input_data,
                        output_data=output if isinstance(output, dict) else {"result": output},
                        context_snapshot_id=post_snapshot_id
                    )
                    
                    task.add_comment(stage.agent_name, f"增强阶段完成: {stage.name}")
                    return True
                else:
                    task.add_comment(stage.agent_name, f"增强阶段超时: {stage.name}")
                    return False
            else:
                # 回退到基础执行
                message = Message(
                    id=str(uuid.uuid4()),
                    type=MessageType.TEXT,
                    content=input_data,
                    sender="orchestrator",
                    receiver=stage.agent_name
                )
                
                response = agent.process(message)
                
                if response:
                    self._process_stage_output(task, stage, response.content)
                    task.add_comment(stage.agent_name, f"阶段完成: {stage.name}")
                    return True
                else:
                    task.add_comment(stage.agent_name, f"阶段执行无响应: {stage.name}")
                    return False
                    
        except Exception as e:
            task.add_comment(stage.agent_name, f"增强阶段执行异常: {str(e)}")
            return False
    
    def _execute_parallel_stages(
        self,
        task: EnhancedWorkflowTask,
        current_stage: EnhancedWorkflowStage,
        workflow: WorkflowDefinition,
        session_context: ContextManager
    ) -> bool:
        """
        并行执行多个阶段
        
        Args:
            task: 任务
            current_stage: 当前阶段
            workflow: 工作流定义
            session_context: 会话上下文
            
        Returns:
            是否成功
        """
        next_stages = current_stage.next_stages
        if not next_stages:
            task.transition_to(TaskState.DONE, "工作流完成")
            return True
        
        task.add_comment("orchestrator", f"开始并行执行阶段: {next_stages}")
        
        # 并行执行
        import concurrent.futures
        
        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(next_stages)) as executor:
            future_to_stage = {}
            
            for stage_name in next_stages:
                stage = workflow.get_stage(stage_name)
                if stage:
                    future = executor.submit(
                        self._execute_stage_enhanced,
                        task, stage, workflow, session_context
                    )
                    future_to_stage[future] = stage_name
            
            for future in concurrent.futures.as_completed(future_to_stage):
                stage_name = future_to_stage[future]
                try:
                    success = future.result()
                    results[stage_name] = success
                except Exception as e:
                    log_error(f"Parallel stage {stage_name} failed: {e}")
                    results[stage_name] = False
        
        # 合并结果
        all_success = all(results.values())
        
        if all_success:
            task.add_comment("orchestrator", f"并行阶段全部完成: {list(results.keys())}")
            
            # 确定下一阶段
            # 并行阶段后，找到共同的汇聚点
            next_stage_name = self._find_convergence_stage(workflow, next_stages)
            if next_stage_name:
                task.input_data["current_stage"] = next_stage_name
                task.transition_to(TaskState.INBOX, f"进入汇聚阶段: {next_stage_name}")
                return self.execute_task(task.id)
            else:
                task.transition_to(TaskState.DONE, "工作流完成")
        else:
            failed_stages = [s for s, r in results.items() if not r]
            task.add_comment("orchestrator", f"并行阶段部分失败: {failed_stages}")
            return False
        
        return all_success
    
    def _find_convergence_stage(
        self,
        workflow: WorkflowDefinition,
        parallel_stages: List[str]
    ) -> Optional[str]:
        """
        找到并行阶段的汇聚点
        
        Args:
            workflow: 工作流定义
            parallel_stages: 并行阶段列表
            
        Returns:
            汇聚阶段名称
        """
        # 简单策略：找到第一个依赖所有并行阶段的阶段
        for stage in workflow.stages:
            if hasattr(stage, 'dependencies') and stage.dependencies:
                if all(dep in parallel_stages for dep in stage.dependencies):
                    return stage.name
        
        # 如果没有找到，返回最后一个并行阶段的下一个阶段
        for stage_name in reversed(parallel_stages):
            stage = workflow.get_stage(stage_name)
            if stage and stage.next_stages:
                return stage.next_stages[0]
        
        return None
    
    def _handoff_context_to_agent(
        self,
        task: EnhancedWorkflowTask,
        stage: EnhancedWorkflowStage,
        session_context: ContextManager,
        communicator: EnhancedAgentCommunicator
    ):
        """
        将上下文交接给Agent
        
        Args:
            task: 任务
            stage: 阶段定义
            session_context: 会话上下文
            communicator: 通信器
        """
        if not isinstance(stage, EnhancedWorkflowStage):
            return
        
        config = stage.context_handoff
        
        # 准备要传递的上下文
        context_data = {}
        
        if config.include_shared:
            shared_context = session_context.get_all_items(ContextScope.SHARED)
            for key, item in shared_context.items():
                if self._should_include_key(key, config):
                    context_data[key] = item.value
        
        if config.include_global:
            global_context = session_context.get_all_items(ContextScope.GLOBAL)
            for key, item in global_context.items():
                if self._should_include_key(key, config):
                    context_data[key] = item.value
        
        # 传递给Agent的上下文管理器
        agent_context = communicator.get_context_manager()
        if agent_context:
            for key, value in context_data.items():
                agent_context.set(
                    key=f"workflow.{key}",
                    value=value,
                    scope=ContextScope.SHARED,
                    metadata={
                        "source": "workflow_handoff",
                        "task_id": task.id,
                        "stage": stage.name
                    }
                )
    
    def _should_include_key(self, key: str, config: ContextHandoffConfig) -> bool:
        """检查是否应该包含键"""
        # 检查排除列表
        for exclude in config.keys_exclude:
            if exclude in key:
                return False
        
        # 检查过滤列表
        if config.keys_filter:
            for include in config.keys_filter:
                if include in key:
                    return True
            return False
        
        return True
    
    def _import_context_from_response(
        self,
        task: EnhancedWorkflowTask,
        stage: EnhancedWorkflowStage,
        session_context: ContextManager,
        response_context: Dict[str, Any]
    ):
        """
        从响应导入上下文
        
        Args:
            task: 任务
            stage: 阶段定义
            session_context: 会话上下文
            response_context: 响应中的上下文
        """
        items = response_context.get("items", {})
        
        for key, item_data in items.items():
            # 只导入共享和全局上下文
            scope_str = item_data.get("scope", "local")
            if scope_str in ["shared", "global"]:
                value = item_data.get("value")
                session_context.set(
                    key=key.replace("msg.", "").replace("workflow.", ""),
                    value=value,
                    scope=ContextScope.SHARED,
                    metadata={
                        "source": f"agent_{stage.agent_name}",
                        "task_id": task.id,
                        "stage": stage.name
                    }
                )
    
    def get_task_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务的完整上下文
        
        Args:
            task_id: 任务ID
            
        Returns:
            上下文数据
        """
        task = self._tasks.get(task_id)
        if not isinstance(task, EnhancedWorkflowTask):
            return None
        
        session_context = self._session_contexts.get(task.session_id)
        if not session_context:
            return None
        
        return {
            "task_id": task_id,
            "session_id": task.session_id,
            "context": session_context.get_all(),
            "snapshots": session_context.list_snapshots(),
            "stage_history": task.stage_history,
            "participating_agents": list(task.participating_agents)
        }
    
    def restore_task_context(
        self,
        task_id: str,
        snapshot_id: str
    ) -> bool:
        """
        从快照恢复任务上下文
        
        Args:
            task_id: 任务ID
            snapshot_id: 快照ID
            
        Returns:
            是否成功
        """
        task = self._tasks.get(task_id)
        if not isinstance(task, EnhancedWorkflowTask):
            return False
        
        session_context = self._session_contexts.get(task.session_id)
        if not session_context:
            return False
        
        return session_context.restore_snapshot(snapshot_id)
    
    def create_conversation_for_task(
        self,
        task_id: str,
        participants: List[str]
    ) -> Optional[str]:
        """
        为任务创建对话
        
        Args:
            task_id: 任务ID
            participants: 参与者列表
            
        Returns:
            对话ID
        """
        task = self._tasks.get(task_id)
        if not isinstance(task, EnhancedWorkflowTask):
            return None
        
        # 使用编排器的通信器创建对话
        orchestrator_comm = self._get_orchestrator_communicator()
        if orchestrator_comm:
            conversation = orchestrator_comm.create_conversation(participants)
            task.conversation_ids.append(conversation.conversation_id)
            return conversation.conversation_id
        
        return None
    
    def _get_orchestrator_communicator(self) -> Optional[EnhancedAgentCommunicator]:
        """获取编排器的通信器"""
        if "orchestrator" not in self._communicators:
            comm = create_enhanced_communicator(agent_name="orchestrator")
            if comm.initialize():
                self._communicators["orchestrator"] = comm
        return self._communicators.get("orchestrator")
    
    def get_task_conversations(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取任务的所有对话
        
        Args:
            task_id: 任务ID
            
        Returns:
            对话列表
        """
        task = self._tasks.get(task_id)
        if not isinstance(task, EnhancedWorkflowTask):
            return []
        
        conversations = []
        orchestrator_comm = self._get_orchestrator_communicator()
        
        if orchestrator_comm:
            for conv_id in task.conversation_ids:
                conv = orchestrator_comm.get_conversation(conv_id)
                if conv:
                    conversations.append(conv.to_dict())
        
        return conversations
    
    def shutdown(self):
        """关闭编排器"""
        # 关闭所有通信器
        for comm in self._communicators.values():
            try:
                comm.shutdown()
            except Exception as e:
                log_error(f"Error shutting down communicator: {e}")
        
        # 销毁所有上下文管理器
        for ctx in self._context_managers.values():
            try:
                ctx.destroy()
            except Exception as e:
                log_error(f"Error destroying context manager: {e}")
        
        for ctx in self._session_contexts.values():
            try:
                ctx.destroy()
            except Exception as e:
                log_error(f"Error destroying session context: {e}")
        
        self._logger.agent("EnhancedWorkflowOrchestrator shutdown")


# 全局实例
_enhanced_orchestrator: Optional[EnhancedWorkflowOrchestrator] = None


def get_enhanced_workflow_orchestrator() -> EnhancedWorkflowOrchestrator:
    """获取增强型工作流编排器实例"""
    global _enhanced_orchestrator
    if _enhanced_orchestrator is None:
        _enhanced_orchestrator = EnhancedWorkflowOrchestrator()
    return _enhanced_orchestrator
