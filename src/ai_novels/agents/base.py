"""
Agent基类定义

@file: agents/base.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 定义所有Agent的基础接口和类
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from ai_novels.utils import log_error, log_info, get_logger

logger = get_logger()
from ai_novels.core.llm_router import LLMRouter, get_llm_router
from ai_novels.core.event_bus import event_bus, EventType
from ai_novels.config.manager import settings


class AgentState(Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    STOPPED = "stopped"


class MessageType(Enum):
    """消息类型枚举"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"
    COMMAND = "command"
    SYSTEM = "system"


@dataclass
class Message:
    """消息类"""
    id: str
    type: MessageType
    content: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    sender: Optional[str] = None
    receiver: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "sender": self.sender,
            "receiver": self.receiver
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建"""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            type=MessageType(data.get("type", "text")),
            content=data.get("content"),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", time.time()),
            sender=data.get("sender"),
            receiver=data.get("receiver")
        )


@dataclass
class AgentConfig:
    """Agent配置"""
    name: str
    description: str = ""
    provider: str = "ollama"
    model: str = "qwen2.5-7b"
    temperature: float = 0.7
    max_tokens: int = 8192
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    retry_times: int = 3
    timeout: int = 60

    @classmethod
    def from_config(cls, name: str, config: Dict[str, Any] = None) -> 'AgentConfig':
        """
        从配置字典创建 AgentConfig

        Args:
            name: Agent名称
            config: 配置字典

        Returns:
            AgentConfig实例
        """
        if config is None:
            # 从全局配置管理器读取
            config = settings.get_agent(name)

        return cls(
            name=name,
            description=config.get("description", ""),
            provider=config.get("provider", "ollama"),
            model=config.get("model", "qwen2.5-7b"),
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 8192),
            system_prompt=config.get("system_prompt", ""),
            tools=config.get("tools", []),
            retry_times=config.get("retry_times", 3),
            timeout=config.get("timeout", 60)
        )


class BaseAgent(ABC):
    """
    Agent基类

    所有Agent应继承此类并实现抽象方法
    """

    def __init__(self, config: AgentConfig):
        """
        初始化Agent

        Args:
            config: Agent配置
        """
        self.config = config
        self._state = AgentState.IDLE
        self._name = config.name
        self._description = config.description
        self._last_message: Optional[Message] = None
        self._history: List[Message] = []
        self._additional_context: Dict[str, Any] = {}

        # LLM客户端配置
        self._llm_router: Optional[LLMRouter] = None
        self._llm_provider: str = config.provider
        self._llm_model: str = config.model
        self._llm_temperature: float = config.temperature
        self._llm_max_tokens: int = config.max_tokens
        self._initialized_llm = False

    def _initialize_llm(self):
        """
        初始化LLM客户端
        """
        if self._initialized_llm:
            return

        try:
            self._llm_router = get_llm_router()
            if self._llm_router and self._llm_router.is_initialized():
                log_info(f"Agent {self._name} using LLM: {self._llm_provider}/{self._llm_model}")
                self._initialized_llm = True
            else:
                log_error(f"Agent {self._name} LLM router not initialized")
        except Exception as e:
            log_error(f"Failed to initialize LLM for agent {self._name}: {e}")

    def _generate_with_llm(self, prompt: str, system_prompt: str = None, timeout: int = None) -> Optional[str]:
        """
        使用LLM生成文本

        Args:
            prompt: 提示词
            system_prompt: 系统提示
            timeout: 超时时间（秒），None则使用配置的timeout

        Returns:
            生成的文本
        """
        if not self._initialized_llm:
            self._initialize_llm()

        if self._llm_router is None:
            return None

        # 使用传入的timeout，否则使用配置的timeout
        effective_timeout = timeout if timeout is not None else self.config.timeout

        # 发布 LLM 请求事件
        self._emit_llm_event(EventType.LLM_REQUEST, {
            "agent_name": self._name,
            "provider": self._llm_provider,
            "model": self._llm_model,
            "prompt_length": len(prompt),
        })

        try:
            result = self._llm_router.generate(
                prompt=prompt,
                provider=self._llm_provider,
                system_prompt=system_prompt,
                temperature=self._llm_temperature,
                max_tokens=self._llm_max_tokens,
                timeout=effective_timeout
            )
            # 发布 LLM 响应事件
            self._emit_llm_event(EventType.LLM_RESPONSE, {
                "agent_name": self._name,
                "provider": self._llm_provider,
                "model": self._llm_model,
                "result_length": len(result) if result else 0,
            })
            return result
        except Exception as e:
            log_error(f"LLM generate error for {self._name}: {e}")
            # 发布 LLM 错误事件
            self._emit_llm_event(EventType.LLM_ERROR, {
                "agent_name": self._name,
                "provider": self._llm_provider,
                "model": self._llm_model,
                "error": str(e),
            })
            return None

    @property
    def name(self) -> str:
        """获取Agent名称"""
        return self._name

    @property
    def description(self) -> str:
        """获取Agent描述"""
        return self._description

    @property
    def state(self) -> AgentState:
        """获取Agent状态"""
        return self._state

    @property
    def last_message(self) -> Optional[Message]:
        """获取最后一条消息"""
        return self._last_message

    @property
    def history(self) -> List[Message]:
        """获取对话历史"""
        return self._history.copy()

    def initialize(self) -> bool:
        """
        初始化Agent

        Returns:
            是否成功
        """
        try:
            self._state = AgentState.INITIALIZING
            self._on_initialize()
            # 初始化LLM客户端
            self._initialize_llm()
            self._state = AgentState.READY
            return True
        except Exception as e:
            self._state = AgentState.ERROR
            log_error(f"Failed to initialize agent {self._name}: {e}")
            return False

    def _on_initialize(self):
        """初始化回调（子类实现）"""
        pass

    def _emit_llm_event(self, event_type: EventType, payload: Dict[str, Any]) -> None:
        """发射 LLM 相关事件（异步非阻塞）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    event_bus.publish_type(event_type, payload=payload, source=self._name)
                )
        except RuntimeError:
            logger.debug("No running event loop for LLM event emission")

    def _emit_agent_event(self, event_type: EventType, stage: str = "", progress: float = 0.0) -> None:
        """发射 Agent 执行事件（异步非阻塞）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(
                    event_bus.publish_type(
                        event_type,
                        payload={"agent_name": self._name, "stage": stage, "progress": progress},
                        source=self._name,
                    )
                )
        except RuntimeError:
            logger.debug("No running event loop for agent event emission")

    def cleanup(self) -> bool:
        """
        清理资源

        Returns:
            是否成功
        """
        try:
            self._state = AgentState.STOPPED
            self._on_cleanup()
            return True
        except Exception as e:
            log_error(f"Failed to cleanup agent {self._name}: {e}")
            return False

    def _on_cleanup(self):
        """清理回调（子类实现）"""
        pass

    def set_context(self, key: str, value: Any):
        """
        设置上下文

        Args:
            key: 上下文键
            value: 上下文值
        """
        self._additional_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        获取上下文

        Args:
            key: 上下文键
            default: 默认值

        Returns:
            上下文值
        """
        return self._additional_context.get(key, default)

    def clear_context(self):
        """清空上下文"""
        self._additional_context.clear()

    @abstractmethod
    def process(self, message: Message) -> Message:
        """
        处理消息（必须实现）

        Args:
            message: 输入消息

        Returns:
            输出消息
        """
        pass

    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        生成响应（辅助方法）

        Args:
            prompt: 提示词
            system_prompt: 系统提示
            **kwargs: 其他参数

        Returns:
            生成的响应
        """
        return self._generate_with_llm(prompt, system_prompt)

    def add_message(self, message: Message):
        """
        添加消息到历史

        Args:
            message: 消息
        """
        self._history.append(message)
        self._last_message = message
        if len(self._history) > 100:  # 限制历史长度
            self._history = self._history[-100:]

    def execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        执行工具（基类提供默认实现，子类可重写）

        Args:
            tool_name: 工具名称
            params: 参数

        Returns:
            工具执行结果
        """
        if tool_name in self.config.tools:
            return self._execute_tool(tool_name, params)
        return None

    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        执行工具回调（基类提供默认工具实现）

        支持的工具：
        - database_query: 数据库查询
        - database_insert: 数据库插入
        - database_update: 数据库更新
        - database_delete: 数据库删除
        - file_read: 读取文件
        - file_write: 写入文件
        - calculation: 计算表达式
        - format_text: 格式化文本
        """
        logger = get_logger()
        logger.agent_debug("Executing tool", tool=tool_name, params=params)

        if tool_name == "database_query":
            # 简单的数据库查询工具（需要子类提供数据库连接）
            return {"error": "database_query requires database connection", "implemented": False}

        elif tool_name == "database_insert":
            return {"error": "database_insert requires database connection", "implemented": False}

        elif tool_name == "database_update":
            return {"error": "database_update requires database connection", "implemented": False}

        elif tool_name == "database_delete":
            return {"error": "database_delete requires database connection", "implemented": False}

        elif tool_name == "file_read":
            # 读取文件工具
            file_path = params.get("path", "")
            if not file_path:
                return {"error": "file_read requires 'path' parameter"}
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return {"content": f.read(), "success": True}
            except Exception as e:
                return {"error": str(e), "success": False}

        elif tool_name == "file_write":
            # 写入文件工具
            file_path = params.get("path", "")
            content = params.get("content", "")
            if not file_path:
                return {"error": "file_write requires 'path' parameter"}
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {"success": True, "bytes_written": len(content)}
            except Exception as e:
                return {"error": str(e), "success": False}

        elif tool_name == "calculation":
            # 计算表达式工具（使用eval，安全起见限制仅基本运算）
            expression = params.get("expression", "")
            if not expression:
                return {"error": "calculation requires 'expression' parameter"}
            try:
                # 限制仅允许基本数学运算
                allowed_chars = set("0123456789+-*/()., ")
                if not all(c in allowed_chars for c in expression):
                    return {"error": "Invalid characters in expression"}
                result = eval(expression)
                return {"result": result, "success": True}
            except Exception as e:
                return {"error": str(e), "success": False}

        elif tool_name == "format_text":
            # 格式化文本工具
            text = params.get("text", "")
            format_type = params.get("type", "upper")
            if format_type == "upper":
                return {"result": text.upper()}
            elif format_type == "lower":
                return {"result": text.lower()}
            elif format_type == "title":
                return {"result": text.title()}
            elif format_type == "strip":
                return {"result": text.strip()}
            else:
                return {"error": f"Unknown format type: {format_type}"}

        elif tool_name == "echo":
            # 回显工具（用于测试）
            return {"echo": params}

        else:
            return {"error": f"Tool '{tool_name}' not implemented"}

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康检查结果
        """
        return {
            "name": self._name,
            "state": self._state.value,
            "last_message": self._last_message.id if self._last_message else None,
            "history_length": len(self._history)
        }

    def _create_message(
        self,
        content: Any,
        message_type: MessageType = MessageType.TEXT,
        **metadata
    ) -> Message:
        """
        创建消息（辅助方法）

        Args:
            content: 消息内容
            message_type: 消息类型
            **metadata: 元数据

        Returns:
            Message对象
        """
        return Message(
            id=str(uuid.uuid4()),
            type=message_type,
            content=content,
            metadata=metadata,
            sender=self._name
        )


class AgentRouter:
    """
    Agent路由管理器

    根据请求类型路由到不同的Agent
    """

    def __init__(self):
        """初始化路由"""
        self._agents: Dict[str, BaseAgent] = {}
        self._routes: Dict[str, str] = {}  # keyword -> agent_name

    def register_agent(self, agent: BaseAgent, keywords: List[str] = None) -> bool:
        """
        注册Agent

        Args:
            agent: Agent实例
            keywords: 关键词列表

        Returns:
            是否成功
        """
        try:
            agent.initialize()
            self._agents[agent.name] = agent

            if keywords:
                for keyword in keywords:
                    self._routes[keyword] = agent.name

            return True
        except Exception as e:
            log_error(f"Failed to register agent {agent.name}: {e}")
            return False

    def unregister_agent(self, name: str) -> bool:
        """
        注销Agent

        Args:
            name: Agent名称

        Returns:
            是否成功
        """
        try:
            if name in self._agents:
                self._agents[name].cleanup()
                del self._agents[name]
            return True
        except Exception as e:
            log_error(f"Failed to unregister agent {name}: {e}")
            return False

    def route(self, message: Message) -> Optional[BaseAgent]:
        """
        路由消息到Agent

        Args:
            message: 消息

        Returns:
            对应的Agent
        """
        content = str(message.content).lower()

        # 根据关键词路由
        for keyword, agent_name in self._routes.items():
            if keyword in content:
                return self._agents.get(agent_name)

        # 默认路由到第一个可用Agent
        for agent in self._agents.values():
            return agent

        return None

    def process(self, message: Message) -> Optional[Message]:
        """
        处理消息（路由+处理）

        Args:
            message: 消息

        Returns:
            处理结果
        """
        agent = self.route(message)
        if agent is None:
            return None

        try:
            return agent.process(message)
        except Exception as e:
            log_error(f"Failed to process message: {e}")
            return None

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """
        获取Agent

        Args:
            name: Agent名称

        Returns:
            Agent实例
        """
        return self._agents.get(name)

    def list_agents(self) -> List[str]:
        """
        列出所有Agent

        Returns:
            Agent名称列表
        """
        return list(self._agents.keys())
