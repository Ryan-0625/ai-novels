"""
AI-Novels 消息格式定义

@file: src/deepnovel/model/message.py
@date: 2026-03-12
@version: 1.0.0
@description: 定义RocketMQ消息格式的数据类
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime


@dataclass
class TaskRequest:
    """任务请求消息"""
    agent_name: str
    task_id: str
    user_id: str
    payload: Dict[str, Any]
    callback_queue: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "payload": self.payload,
            "callback_queue": self.callback_queue,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRequest":
        """从字典创建"""
        return cls(
            agent_name=data.get("agent_name", ""),
            task_id=data.get("task_id", ""),
            user_id=data.get("user_id", ""),
            payload=data.get("payload", {}),
            callback_queue=data.get("callback_queue", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class TaskResponse:
    """任务响应消息"""
    task_id: str
    agent_name: str
    status: str  # success|failed|pending
    result: Optional[Dict[str, Any]] = None
    error_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "result": self.result,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResponse":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", ""),
            agent_name=data.get("agent_name", ""),
            status=data.get("status", "pending"),
            result=data.get("result"),
            error_message=data.get("error_message", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class TaskStatusUpdate:
    """任务状态更新消息"""
    task_id: str
    status: str
    progress: float = 0.0
    current_stage: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskStatusUpdate":
        """从字典创建"""
        return cls(
            task_id=data.get("task_id", ""),
            status=data.get("status", ""),
            progress=float(data.get("progress", 0.0)),
            current_stage=data.get("current_stage", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class AgentMessage:
    """智能体间通信消息"""
    sender: str
    receiver: str
    message_type: str  # task_request, task_response, status_update, query, response
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """从字典创建"""
        return cls(
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            message_type=data.get("message_type", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


# 消息类型常量
class MessageType:
    """消息类型常量"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_STATUS_UPDATE = "task_status_update"
    AGENT_QUERY = "agent_query"
    AGENT_RESPONSE = "agent_response"
    HEALTH_CHECK = "health_check"
    HEALTH_CHECK_RESPONSE = "health_check_response"
    CONFIG_REQUEST = "config_request"
    CONFIG_RESPONSE = "config_response"
