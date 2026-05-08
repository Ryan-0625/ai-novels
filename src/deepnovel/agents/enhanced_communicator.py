"""
增强型Agent通信模块

@file: agents/enhanced_communicator.py
@date: 2026-04-08
@author: AI-Novels Team
@version: 2.0
@description: 提供强大的Agent间消息交流和上下文传递能力
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Callable, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import threading
import asyncio
from concurrent.futures import Future, TimeoutError as FutureTimeoutError

from deepnovel.agents.agent_communicator import AgentCommunicator, AgentMessageHandler
from deepnovel.message.message import (
    TaskRequest, TaskResponse, TaskStatusUpdate,
    AgentMessage, MessageType
)
from deepnovel.core.context_manager import (
    ContextManager, ContextScope, ContextPriority,
    shared_context_pool, create_context_manager
)
from deepnovel.utils import log_info, log_error, log_warn, get_logger


class MessagePriority(Enum):
    """消息优先级"""
    CRITICAL = 0    # 关键消息，立即处理
    HIGH = 1        # 高优先级
    NORMAL = 2      # 普通优先级
    LOW = 3         # 低优先级


class ConversationState(Enum):
    """对话状态"""
    PENDING = "pending"         # 等待响应
    RESPONDED = "responded"     # 已响应
    TIMEOUT = "timeout"         # 超时
    ERROR = "error"             # 错误
    CLOSED = "closed"           # 已关闭


@dataclass
class Conversation:
    """对话会话"""
    conversation_id: str
    initiator: str                      # 发起者
    participants: Set[str]              # 参与者
    created_at: float
    last_activity: float
    state: ConversationState = ConversationState.PENDING
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context_snapshot: Optional[str] = None  # 关联的上下文快照ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, sender: str, content: Any, message_type: str = "text"):
        """添加消息"""
        self.messages.append({
            "id": str(uuid.uuid4()),
            "sender": sender,
            "content": content,
            "type": message_type,
            "timestamp": time.time()
        })
        self.last_activity = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "conversation_id": self.conversation_id,
            "initiator": self.initiator,
            "participants": list(self.participants),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "state": self.state.value,
            "messages": self.messages,
            "context_snapshot": self.context_snapshot,
            "metadata": self.metadata
        }


@dataclass
class MessageEnvelope:
    """消息信封（包装消息，添加元数据）"""
    message_id: str
    sender: str
    receiver: str
    message_type: str
    payload: Dict[str, Any]
    priority: MessagePriority
    timestamp: float
    context_data: Optional[Dict[str, Any]] = None  # 附带的上下文数据
    reply_to: Optional[str] = None                 # 回复的消息ID
    correlation_id: Optional[str] = None           # 关联ID（用于追踪）
    ttl: Optional[int] = None                      # 生存时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "context_data": self.context_data,
            "reply_to": self.reply_to,
            "correlation_id": self.correlation_id,
            "ttl": self.ttl
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageEnvelope':
        """从字典创建"""
        return cls(
            message_id=data["message_id"],
            sender=data["sender"],
            receiver=data["receiver"],
            message_type=data["message_type"],
            payload=data["payload"],
            priority=MessagePriority(data.get("priority", 2)),
            timestamp=data["timestamp"],
            context_data=data.get("context_data"),
            reply_to=data.get("reply_to"),
            correlation_id=data.get("correlation_id"),
            ttl=data.get("ttl")
        )
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl


class EnhancedAgentCommunicator:
    """
    增强型Agent通信器
    
    功能增强：
    1. 消息优先级队列
    2. 请求-响应模式（同步/异步）
    3. 对话会话管理
    4. 上下文自动传递
    5. 消息持久化和重试
    6. 消息路由和广播
    """
    
    def __init__(
        self,
        agent_name: str,
        session_id: str = None,
        enable_context_sync: bool = True,
        default_timeout: int = 30
    ):
        """
        初始化增强通信器
        
        Args:
            agent_name: Agent名称
            session_id: 会话ID
            enable_context_sync: 是否启用上下文同步
            default_timeout: 默认超时时间（秒）
        """
        self._agent_name = agent_name
        self._session_id = session_id or str(uuid.uuid4())
        self._enable_context_sync = enable_context_sync
        self._default_timeout = default_timeout
        
        # 基础通信器
        self._base_communicator: Optional[AgentCommunicator] = None
        
        # 上下文管理器
        self._context_manager: Optional[ContextManager] = None
        
        # 消息队列（按优先级）
        self._message_queues: Dict[MessagePriority, List[MessageEnvelope]] = {
            MessagePriority.CRITICAL: [],
            MessagePriority.HIGH: [],
            MessagePriority.NORMAL: [],
            MessagePriority.LOW: []
        }
        self._queue_lock = threading.Lock()
        
        # 等待响应的请求
        self._pending_requests: Dict[str, Future] = {}
        self._request_lock = threading.Lock()
        
        # 对话管理
        self._conversations: Dict[str, Conversation] = {}
        self._conversation_lock = threading.Lock()
        
        # 消息处理器
        self._message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._handler_lock = threading.Lock()
        
        # 消息历史
        self._message_history: List[Dict[str, Any]] = []
        self._max_history = 1000
        
        # 统计信息
        self._stats = {
            "sent": 0,
            "received": 0,
            "failed": 0,
            "timeout": 0
        }
        
        # 运行状态
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        
        log_info(f"EnhancedAgentCommunicator initialized for {agent_name}")
    
    def initialize(self, base_communicator: AgentCommunicator = None) -> bool:
        """
        初始化
        
        Args:
            base_communicator: 基础通信器（可选）
            
        Returns:
            是否成功
        """
        try:
            # 初始化上下文管理器
            self._context_manager = create_context_manager(
                agent_name=self._agent_name,
                session_id=self._session_id
            )
            
            # 初始化基础通信器
            if base_communicator:
                self._base_communicator = base_communicator
            else:
                self._base_communicator = AgentCommunicator(self._agent_name)
                if not self._base_communicator.connect():
                    log_error(f"Failed to connect base communicator for {self._agent_name}")
                    return False
            
            # 注册消息回调
            self._register_handlers()
            
            # 启动消息处理器
            self._running = True
            self._processor_thread = threading.Thread(target=self._message_processor_loop, daemon=True)
            self._processor_thread.start()
            
            log_info(f"EnhancedAgentCommunicator initialized successfully for {self._agent_name}")
            return True
            
        except Exception as e:
            log_error(f"Failed to initialize EnhancedAgentCommunicator: {e}")
            return False
    
    def _register_handlers(self):
        """注册消息处理器"""
        if self._base_communicator:
            # 注册各类消息的处理回调
            self._base_communicator.register_callback(
                MessageType.TASK_REQUEST,
                self._handle_task_request
            )
            self._base_communicator.register_callback(
                MessageType.TASK_RESPONSE,
                self._handle_task_response
            )
            self._base_communicator.register_callback(
                MessageType.AGENT_QUERY,
                self._handle_query
            )
            self._base_communicator.register_callback(
                MessageType.AGENT_RESPONSE,
                self._handle_response
            )
    
    def _message_processor_loop(self):
        """消息处理循环"""
        while self._running:
            try:
                message = self._dequeue_message()
                if message:
                    self._process_message(message)
                else:
                    time.sleep(0.1)
            except Exception as e:
                log_error(f"Message processor error: {e}")
    
    def _dequeue_message(self) -> Optional[MessageEnvelope]:
        """从队列取出消息（按优先级）"""
        with self._queue_lock:
            for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                           MessagePriority.NORMAL, MessagePriority.LOW]:
                if self._message_queues[priority]:
                    return self._message_queues[priority].pop(0)
        return None
    
    def _enqueue_message(self, envelope: MessageEnvelope):
        """将消息加入队列"""
        with self._queue_lock:
            self._message_queues[envelope.priority].append(envelope)
    
    def _process_message(self, envelope: MessageEnvelope):
        """处理消息"""
        # 检查过期
        if envelope.is_expired():
            log_warn(f"Discarded expired message: {envelope.message_id}")
            return
        
        # 导入上下文（如果包含）
        if envelope.context_data and self._enable_context_sync:
            self._import_context_from_message(envelope.context_data)
        
        # 调用处理器
        handlers = self._message_handlers.get(envelope.message_type, [])
        for handler in handlers:
            try:
                handler(envelope)
            except Exception as e:
                log_error(f"Message handler error: {e}")
        
        # 处理回复
        if envelope.reply_to:
            self._handle_reply(envelope)
        
        # 记录历史
        self._record_message(envelope, "received")
        self._stats["received"] += 1
    
    def _handle_reply(self, envelope: MessageEnvelope):
        """处理回复消息"""
        with self._request_lock:
            future = self._pending_requests.get(envelope.reply_to)
            if future and not future.done():
                future.set_result(envelope)
    
    def _handle_task_request(self, message: Dict[str, Any]) -> bool:
        """处理任务请求"""
        envelope = MessageEnvelope.from_dict(message.get("payload", {}))
        self._enqueue_message(envelope)
        return True
    
    def _handle_task_response(self, message: Dict[str, Any]) -> bool:
        """处理任务响应"""
        envelope = MessageEnvelope.from_dict(message.get("payload", {}))
        self._enqueue_message(envelope)
        return True
    
    def _handle_query(self, message: Dict[str, Any]) -> bool:
        """处理查询"""
        envelope = MessageEnvelope.from_dict(message.get("payload", {}))
        self._enqueue_message(envelope)
        return True
    
    def _handle_response(self, message: Dict[str, Any]) -> bool:
        """处理响应"""
        envelope = MessageEnvelope.from_dict(message.get("payload", {}))
        self._enqueue_message(envelope)
        return True
    
    def _import_context_from_message(self, context_data: Dict[str, Any]):
        """从消息导入上下文"""
        if self._context_manager:
            try:
                self._context_manager.import_context(
                    context_data,
                    merge=True,
                    prefix="msg."
                )
            except Exception as e:
                log_error(f"Failed to import context from message: {e}")
    
    def _export_context_for_message(self) -> Optional[Dict[str, Any]]:
        """导出上下文用于消息传递"""
        if self._context_manager and self._enable_context_sync:
            try:
                return self._context_manager.export_context(scope=ContextScope.SHARED)
            except Exception as e:
                log_error(f"Failed to export context for message: {e}")
        return None
    
    def _record_message(self, envelope: MessageEnvelope, direction: str):
        """记录消息历史"""
        record = {
            "direction": direction,
            "timestamp": time.time(),
            **envelope.to_dict()
        }
        self._message_history.append(record)
        
        # 限制历史大小
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
    
    def send_message(
        self,
        receiver: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        include_context: bool = True,
        correlation_id: str = None,
        ttl: int = None
    ) -> Optional[str]:
        """
        发送消息
        
        Args:
            receiver: 接收者
            message_type: 消息类型
            payload: 负载
            priority: 优先级
            include_context: 是否包含上下文
            correlation_id: 关联ID
            ttl: 生存时间
            
        Returns:
            消息ID或None
        """
        try:
            message_id = str(uuid.uuid4())
            
            # 准备上下文数据
            context_data = None
            if include_context:
                context_data = self._export_context_for_message()
            
            envelope = MessageEnvelope(
                message_id=message_id,
                sender=self._agent_name,
                receiver=receiver,
                message_type=message_type,
                payload=payload,
                priority=priority,
                timestamp=time.time(),
                context_data=context_data,
                correlation_id=correlation_id,
                ttl=ttl
            )
            
            # 通过基础通信器发送
            if self._base_communicator:
                result = self._base_communicator._send_message(
                    receiver,
                    AgentMessage(
                        sender=self._agent_name,
                        receiver=receiver,
                        message_type=message_type,
                        payload=envelope.to_dict()
                    )
                )
                
                if result:
                    self._record_message(envelope, "sent")
                    self._stats["sent"] += 1
                    return message_id
            
            self._stats["failed"] += 1
            return None
            
        except Exception as e:
            log_error(f"Failed to send message: {e}")
            self._stats["failed"] += 1
            return None
    
    def send_request(
        self,
        receiver: str,
        request_type: str,
        payload: Dict[str, Any],
        timeout: int = None,
        include_context: bool = True
    ) -> Optional[MessageEnvelope]:
        """
        发送请求并等待响应（同步）
        
        Args:
            receiver: 接收者
            request_type: 请求类型
            payload: 负载
            timeout: 超时时间
            include_context: 是否包含上下文
            
        Returns:
            响应信封或None
        """
        timeout = timeout or self._default_timeout
        message_id = str(uuid.uuid4())
        
        # 创建Future
        future = Future()
        with self._request_lock:
            self._pending_requests[message_id] = future
        
        try:
            # 发送请求
            context_data = self._export_context_for_message() if include_context else None
            
            envelope = MessageEnvelope(
                message_id=message_id,
                sender=self._agent_name,
                receiver=receiver,
                message_type=request_type,
                payload=payload,
                priority=MessagePriority.HIGH,
                timestamp=time.time(),
                context_data=context_data
            )
            
            if self._base_communicator:
                result = self._base_communicator._send_message(
                    receiver,
                    AgentMessage(
                        sender=self._agent_name,
                        receiver=receiver,
                        message_type=request_type,
                        payload=envelope.to_dict()
                    )
                )
                
                if result:
                    self._record_message(envelope, "sent")
                    self._stats["sent"] += 1
                    
                    # 等待响应
                    try:
                        response = future.result(timeout=timeout)
                        return response
                    except FutureTimeoutError:
                        log_warn(f"Request timeout: {message_id}")
                        self._stats["timeout"] += 1
                        return None
            
            return None
            
        except Exception as e:
            log_error(f"Request failed: {e}")
            return None
        finally:
            with self._request_lock:
                self._pending_requests.pop(message_id, None)
    
    def send_async_request(
        self,
        receiver: str,
        request_type: str,
        payload: Dict[str, Any],
        callback: Callable[[MessageEnvelope], None],
        timeout: int = None,
        include_context: bool = True
    ) -> str:
        """
        发送异步请求
        
        Args:
            receiver: 接收者
            request_type: 请求类型
            payload: 负载
            callback: 回调函数
            timeout: 超时时间
            include_context: 是否包含上下文
            
        Returns:
            请求ID
        """
        message_id = str(uuid.uuid4())
        
        def on_response(envelope: MessageEnvelope):
            try:
                callback(envelope)
            except Exception as e:
                log_error(f"Async callback error: {e}")
        
        # 注册临时处理器
        self.register_handler(request_type + "_response", on_response)
        
        # 发送请求
        self.send_message(
            receiver=receiver,
            message_type=request_type,
            payload=payload,
            priority=MessagePriority.HIGH,
            include_context=include_context,
            correlation_id=message_id
        )
        
        return message_id
    
    def reply_to(
        self,
        original_envelope: MessageEnvelope,
        payload: Dict[str, Any],
        include_context: bool = True
    ) -> Optional[str]:
        """
        回复消息
        
        Args:
            original_envelope: 原消息信封
            payload: 回复内容
            include_context: 是否包含上下文
            
        Returns:
            消息ID或None
        """
        return self.send_message(
            receiver=original_envelope.sender,
            message_type=original_envelope.message_type + "_response",
            payload=payload,
            priority=original_envelope.priority,
            include_context=include_context,
            correlation_id=original_envelope.correlation_id
        )
    
    def broadcast(
        self,
        targets: List[str],
        message_type: str,
        payload: Dict[str, Any],
        include_context: bool = True
    ) -> Dict[str, Optional[str]]:
        """
        广播消息
        
        Args:
            targets: 目标列表
            message_type: 消息类型
            payload: 负载
            include_context: 是否包含上下文
            
        Returns:
            发送结果字典
        """
        results = {}
        for target in targets:
            message_id = self.send_message(
                receiver=target,
                message_type=message_type,
                payload=payload,
                include_context=include_context
            )
            results[target] = message_id
        return results
    
    def create_conversation(
        self,
        participants: List[str],
        initial_context: Dict[str, Any] = None
    ) -> Conversation:
        """
        创建对话
        
        Args:
            participants: 参与者列表
            initial_context: 初始上下文
            
        Returns:
            Conversation对象
        """
        conversation_id = str(uuid.uuid4())
        
        # 创建上下文快照
        context_snapshot = None
        if self._context_manager and initial_context:
            for key, value in initial_context.items():
                self._context_manager.set(
                    key=key,
                    value=value,
                    scope=ContextScope.SHARED
                )
            snapshot = self._context_manager.create_snapshot(
                metadata={"conversation_id": conversation_id}
            )
            context_snapshot = snapshot.snapshot_id
        
        conversation = Conversation(
            conversation_id=conversation_id,
            initiator=self._agent_name,
            participants=set(participants),
            created_at=time.time(),
            last_activity=time.time(),
            context_snapshot=context_snapshot
        )
        
        with self._conversation_lock:
            self._conversations[conversation_id] = conversation
        
        # 通知参与者
        for participant in participants:
            if participant != self._agent_name:
                self.send_message(
                    receiver=participant,
                    message_type="conversation_invite",
                    payload={
                        "conversation_id": conversation_id,
                        "initiator": self._agent_name,
                        "participants": list(participants)
                    }
                )
        
        log_info(f"Conversation created: {conversation_id} with {len(participants)} participants")
        return conversation
    
    def send_to_conversation(
        self,
        conversation_id: str,
        content: Any,
        message_type: str = "text"
    ) -> bool:
        """
        发送消息到对话
        
        Args:
            conversation_id: 对话ID
            content: 内容
            message_type: 消息类型
            
        Returns:
            是否成功
        """
        with self._conversation_lock:
            conversation = self._conversations.get(conversation_id)
        
        if not conversation:
            log_error(f"Conversation not found: {conversation_id}")
            return False
        
        # 添加到对话历史
        conversation.add_message(self._agent_name, content, message_type)
        
        # 广播给参与者
        for participant in conversation.participants:
            if participant != self._agent_name:
                self.send_message(
                    receiver=participant,
                    message_type="conversation_message",
                    payload={
                        "conversation_id": conversation_id,
                        "sender": self._agent_name,
                        "content": content,
                        "type": message_type
                    }
                )
        
        return True
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """获取对话"""
        with self._conversation_lock:
            return self._conversations.get(conversation_id)
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """列出所有对话"""
        with self._conversation_lock:
            return [
                {
                    "conversation_id": c.conversation_id,
                    "participants": list(c.participants),
                    "state": c.state.value,
                    "message_count": len(c.messages),
                    "last_activity": c.last_activity
                }
                for c in self._conversations.values()
            ]
    
    def register_handler(self, message_type: str, handler: Callable[[MessageEnvelope], None]):
        """注册消息处理器"""
        with self._handler_lock:
            self._message_handlers[message_type].append(handler)
    
    def unregister_handler(self, message_type: str, handler: Callable[[MessageEnvelope], None]):
        """注销消息处理器"""
        with self._handler_lock:
            if message_type in self._message_handlers:
                if handler in self._message_handlers[message_type]:
                    self._message_handlers[message_type].remove(handler)
    
    def get_context_manager(self) -> Optional[ContextManager]:
        """获取上下文管理器"""
        return self._context_manager
    
    def get_message_history(
        self,
        limit: int = 100,
        message_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取消息历史
        
        Args:
            limit: 限制数量
            message_type: 过滤消息类型
            
        Returns:
            消息历史列表
        """
        history = self._message_history
        if message_type:
            history = [h for h in history if h.get("message_type") == message_type]
        return history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "pending_requests": len(self._pending_requests),
            "conversations": len(self._conversations),
            "message_history": len(self._message_history),
            "queue_sizes": {
                p.name: len(q) for p, q in self._message_queues.items()
            }
        }
    
    def shutdown(self):
        """关闭通信器"""
        self._running = False
        
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=5)
        
        # 取消所有等待的请求
        with self._request_lock:
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()
            self._pending_requests.clear()
        
        # 断开基础通信器
        if self._base_communicator:
            self._base_communicator.disconnect()
        
        # 销毁上下文管理器
        if self._context_manager:
            self._context_manager.destroy()
        
        log_info(f"EnhancedAgentCommunicator shutdown for {self._agent_name}")


def create_enhanced_communicator(
    agent_name: str,
    session_id: str = None,
    **kwargs
) -> EnhancedAgentCommunicator:
    """
    创建增强型通信器
    
    Args:
        agent_name: Agent名称
        session_id: 会话ID
        **kwargs: 其他参数
        
    Returns:
        EnhancedAgentCommunicator实例
    """
    return EnhancedAgentCommunicator(agent_name, session_id, **kwargs)
