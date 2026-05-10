"""
Agent模块初始化

@file: agents/__init__.py
@date: 2026-04-29
@author: AI-Novels Team
@version: 2.0
@description: 导出Agent模块的公共接口
"""

from .base import BaseAgent, AgentConfig, AgentState, MessageType

# 新版核心组件（v2.0重构新增）
from .tool_enabled_agent import ToolEnabledAgent, ToolEnabledAgentConfig
from .prompt_composer import PromptComposer
from .tools.tool_registry import ToolRegistry, tool

# TaskOrchestrator / WorkflowOrchestrator 有复杂的内部依赖关系
# 为避免循环导入，请直接从子模块导入:
#   from deepnovel.agents.task_orchestrator import TaskOrchestrator
#   from deepnovel.agents.workflow_orchestrator import WorkflowOrchestrator

# 旧版Agent实现（向后兼容）
from .implementations import (
    CoordinatorAgent,
    TaskManagerAgent,
    ConfigEnhancerAgent,
    HealthCheckerAgent,
    OutlinePlannerAgent,
    ChapterSummaryAgent,
    CharacterGeneratorAgent,
    WorldBuilderAgent,
    HookGeneratorAgent,
    ConflictGeneratorAgent,
    ContentGeneratorAgent,
    QualityCheckerAgent,
    StorylineIntegratorAgent,
)

__all__ = [
    # 基础
    'BaseAgent',
    'AgentConfig',
    'AgentState',
    'MessageType',
    # 新版核心（v2.0）
    'ToolEnabledAgent',
    'ToolEnabledAgentConfig',
    'ToolRegistry',
    'tool',
    'PromptComposer',
    # TaskOrchestrator / WorkflowOrchestrator 请直接从子模块导入
    # 旧版实现（向后兼容）
    'CoordinatorAgent',
    'TaskManagerAgent',
    'ConfigEnhancerAgent',
    'HealthCheckerAgent',
    'OutlinePlannerAgent',
    'ChapterSummaryAgent',
    'CharacterGeneratorAgent',
    'WorldBuilderAgent',
    'HookGeneratorAgent',
    'ConflictGeneratorAgent',
    'ContentGeneratorAgent',
    'QualityCheckerAgent',
    'StorylineIntegratorAgent',
]
