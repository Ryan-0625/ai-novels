"""
智能体通信模块

@file: agents/agent_communicator.py
@date: 2026-03-12
@version: 1.0.0
@description: 基于RocketMQ的智能体间通信实现
"""

import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
from queue import Queue

from ai_novels.messaging.rocketmq_producer import BaseProducer, RocketMQProducer, RocketMQConfig
from ai_novels.messaging.rocketmq_consumer import BaseConsumer, RocketMQConsumer, ConsumerConfig, MessageHandler
from ai_novels.message.message import (
    TaskRequest,
    TaskResponse,
    TaskStatusUpdate,
    AgentMessage,
    MessageType
)
from ai_novels.message.entities import Character, WorldEntity, OutlineNode, ChapterOutline, Conflict, NarrativeHook
from ai_novels.utils.id_utils import generate_id
from ai_novels.utils import log_info, log_warn, log_error


class AgentCommunicationState(Enum):
    """智能体通信状态"""
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentConfig:
    """智能体配置"""
    name: str = "agent"
    description: str = ""
    provider: str = "ollama"
    model: str = "qwen2.5-7b"
    system_prompt: str = ""
    max_tokens: int = 8192


class AgentMessageHandler(MessageHandler):
    """
    智能体消息处理器

    处理来自其他智能体的消息：
    - task_request: 任务请求
    - task_response: 任务响应
    - status_update: 状态更新
    - query: 查询请求
    - response: 查询响应
    """

    def __init__(self, agent_name: str, message_callback: Callable[[Dict[str, Any]], bool] = None):
        """
        初始化消息处理器

        Args:
            agent_name: 智能体名称
            message_callback: 消息回调函数
        """
        self._agent_name = agent_name
        self._message_callback = message_callback
        self._topics = [
            "ai_novels_agent_communication",
            "ai_novels_task_execution",
            f"agent_{agent_name}_queue"
        ]
        self._received_messages: Queue = Queue()

    def get_topics(self) -> List[str]:
        """获取监听的主题列表"""
        return self._topics

    def handle(self, message: Dict[str, Any]) -> bool:
        """
        处理消息

        Args:
            message: 消息数据

        Returns:
            bool: 处理成功返回True
        """
        try:
            # 检查消息类型
            message_type = message.get("message_type", "")
            sender = message.get("sender", "")

            # 将消息加入队列
            self._received_messages.put(message)

            # 调用回调函数
            if self._message_callback:
                return self._message_callback(message)

            log_info(f"[{self._agent_name}] Received message from {sender}: {message_type}")
            return True

        except Exception as e:
            log_error(f"[{self._agent_name}] Error handling message: {str(e)}")
            return False

    def get_received_messages(self, max_count: int = 10) -> List[Dict[str, Any]]:
        """
        获取接收到的消息

        Args:
            max_count: 最大返回数量

        Returns:
            List[Dict]: 消息列表
        """
        messages = []
        count = 0
        while not self._received_messages.empty() and count < max_count:
            messages.append(self._received_messages.get())
            count += 1
        return messages

    def clear_messages(self):
        """清空消息队列"""
        while not self._received_messages.empty():
            try:
                self._received_messages.get_nowait()
            except Exception:
                break


class AgentCommunicator:
    """
    智能体通信器

    提供智能体间的通信能力：
    - 订阅消息主题
    - 发送消息给其他智能体
    - 处理消息回调
    """

    def __init__(self, agent_name: str, config: Dict[str, Any] = None):
        """
        初始化通信器

        Args:
            agent_name: 智能体名称
            config: 通信配置
        """
        self._agent_name = agent_name
        self._config = config or {}
        self._state = AgentCommunicationState.INITIALIZING

        # RocketMQ配置
        self._mq_config = self._config.get("rocketmq", {
            "name_server": "localhost:9876",
            "producer_group": f"{agent_name}_producer",
            "consumer_group": f"{agent_name}_consumer"
        })

        # 消息处理器
        self._handlers: List[AgentMessageHandler] = []

        # 回调注册
        self._message_callbacks: Dict[str, List[Callable]] = {
            MessageType.TASK_REQUEST: [],
            MessageType.TASK_RESPONSE: [],
            MessageType.TASK_STATUS_UPDATE: [],
            MessageType.AGENT_QUERY: [],
            MessageType.AGENT_RESPONSE: [],
            MessageType.HEALTH_CHECK: [],
            MessageType.HEALTH_CHECK_RESPONSE: [],
            MessageType.CONFIG_REQUEST: [],
            MessageType.CONFIG_RESPONSE: [],
        }

        # 通信组件
        self._producer: Optional[BaseProducer] = None
        self._consumer: Optional[BaseConsumer] = None
        self._consumer_thread: Optional[threading.Thread] = None
        self._running = False

    def register_callback(self, message_type: str, callback: Callable[[Dict[str, Any]], bool]):
        """
        注册消息回调

        Args:
            message_type: 消息类型
            callback: 回调函数
        """
        if message_type in self._message_callbacks:
            self._message_callbacks[message_type].append(callback)

    def connect(self) -> bool:
        """
        连接消息系统

        Returns:
            bool: 连接成功返回True
        """
        try:
            self._state = AgentCommunicationState.CONNECTING

            # 初始化生产者
            self._producer = RocketMQProducer(RocketMQConfig(
                name_server=self._mq_config.get("name_server", "localhost:9876"),
                producer_group=self._mq_config.get("producer_group", f"{self._agent_name}_producer")
            ))

            if not self._producer.connect():
                self._state = AgentCommunicationState.ERROR
                return False

            # 初始化消费者
            self._consumer = RocketMQConsumer(ConsumerConfig(
                name_server=self._mq_config.get("name_server", "localhost:9876"),
                consumer_group=self._mq_config.get("consumer_group", f"{self._agent_name}_consumer"),
                topic="ai_novels_agent_communication",
                max_concurrency=5
            ))

            if not self._consumer.connect():
                self._producer.disconnect()
                self._state = AgentCommunicationState.ERROR
                return False

            # 注册消息处理器
            handler = AgentMessageHandler(
                self._agent_name,
                self._on_message_received
            )
            self._consumer.subscribe(handler)
            self._handlers.append(handler)

            self._state = AgentCommunicationState.CONNECTED
            return True

        except Exception as e:
            self._state = AgentCommunicationState.ERROR
            log_error(f"[{self._agent_name}] Connect error: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """
        断开连接

        Returns:
            bool: 断开成功返回True
        """
        self._running = False

        try:
            if self._consumer:
                self._consumer.stop()
        except Exception:
            pass

        try:
            if self._producer:
                self._producer.close()
        except Exception:
            pass

        self._state = AgentCommunicationState.STOPPED
        return True

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._state == AgentCommunicationState.CONNECTED

    def _on_message_received(self, message: Dict[str, Any]) -> bool:
        """
        消息接收回调

        Args:
            message: 消息数据

        Returns:
            bool: 处理成功返回True
        """
        try:
            message_type = message.get("message_type", "")

            # 调用注册的回调
            callbacks = self._message_callbacks.get(message_type, [])
            for callback in callbacks:
                if not callback(message):
                    log_warn(f"[{self._agent_name}] Callback failed for message type: {message_type}")
                    return False

            return True

        except Exception as e:
            log_error(f"[{self._agent_name}] Error in message callback: {str(e)}")
            return False

    def send_task_request(
        self,
        target_agent: str,
        task_id: str,
        payload: Dict[str, Any],
        user_id: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """
        发送任务请求

        Args:
            target_agent: 目标智能体名称
            task_id: 任务ID
            payload: 任务负载
            user_id: 用户ID

        Returns:
            Dict: 发送结果
        """
        if not self._producer:
            return None

        task_request = TaskRequest(
            agent_name=target_agent,
            task_id=task_id,
            user_id=user_id,
            payload=payload,
            callback_queue=f"agent_{self._agent_name}_queue"
        )

        message = AgentMessage(
            sender=self._agent_name,
            receiver=target_agent,
            message_type=MessageType.TASK_REQUEST,
            payload=task_request.to_dict()
        )

        return self._send_message(target_agent, message)

    def send_task_response(
        self,
        task_id: str,
        agent_name: str,
        status: str,
        result: Dict[str, Any] = None,
        error_message: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        发送任务响应

        Args:
            task_id: 任务ID
            agent_name: 智能体名称
            status: 状态 (success/failed/pending)
            result: 结果数据
            error_message: 错误信息

        Returns:
            Dict: 发送结果
        """
        if not self._producer:
            return None

        task_response = TaskResponse(
            task_id=task_id,
            agent_name=agent_name,
            status=status,
            result=result,
            error_message=error_message
        )

        message = AgentMessage(
            sender=self._agent_name,
            receiver="coordinator",
            message_type=MessageType.TASK_RESPONSE,
            payload=task_response.to_dict()
        )

        return self._send_message("coordinator", message)

    def send_status_update(
        self,
        task_id: str,
        status: str,
        progress: float = 0.0,
        current_stage: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        发送状态更新

        Args:
            task_id: 任务ID
            status: 状态
            progress: 进度
            current_stage: 当前阶段

        Returns:
            Dict: 发送结果
        """
        if not self._producer:
            return None

        status_update = TaskStatusUpdate(
            task_id=task_id,
            status=status,
            progress=progress,
            current_stage=current_stage
        )

        message = AgentMessage(
            sender=self._agent_name,
            receiver="coordinator",
            message_type=MessageType.TASK_STATUS_UPDATE,
            payload=status_update.to_dict()
        )

        return self._send_message("coordinator", message)

    def send_query(
        self,
        target_agent: str,
        query_type: str,
        payload: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        发送查询请求

        Args:
            target_agent: 目标智能体名称
            query_type: 查询类型
            payload: 查询负载

        Returns:
            Dict: 发送结果
        """
        if not self._producer:
            return None

        message = AgentMessage(
            sender=self._agent_name,
            receiver=target_agent,
            message_type=MessageType.AGENT_QUERY,
            payload={
                "query_type": query_type,
                **payload
            }
        )

        return self._send_message(target_agent, message)

    def send_response(
        self,
        target_agent: str,
        query_id: str,
        result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        发送查询响应

        Args:
            target_agent: 目标智能体名称
            query_id: 查询ID
            result: 响应结果

        Returns:
            Dict: 发送结果
        """
        if not self._producer:
            return None

        message = AgentMessage(
            sender=self._agent_name,
            receiver=target_agent,
            message_type=MessageType.AGENT_RESPONSE,
            payload={
                "query_id": query_id,
                "result": result
            }
        )

        return self._send_message(target_agent, message)

    def _send_message(self, target_agent: str, message: AgentMessage) -> Optional[Dict[str, Any]]:
        """
        发送消息

        Args:
            target_agent: 目标智能体名称
            message: 消息对象

        Returns:
            Dict: 发送结果
        """
        try:
            if not self._producer or not self._producer.is_connected():
                return None

            topic = f"agent_{target_agent}_queue"
            result = self._producer.send_sync(
                topic=topic,
                message=message.to_dict(),
                tags=message.message_type
            )

            return result

        except Exception as e:
            log_error(f"[{self._agent_name}] Send message error: {str(e)}")
            return None

    def start(self) -> bool:
        """
        启动通信器

        Returns:
            bool: 启动成功返回True
        """
        if self._state != AgentCommunicationState.CONNECTED:
            if not self.connect():
                return False

        self._running = True

        # 启动消费者
        if self._consumer:
            self._consumer.start()

        return True

    def stop(self) -> bool:
        """
        停止通信器

        Returns:
            bool: 停止成功返回True
        """
        self._running = False
        return self.disconnect()

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            Dict: 健康检查结果
        """
        result = {
            "agent_name": self._agent_name,
            "state": self._state.value,
            "connected": self.is_connected(),
            "running": self._running,
            "handlers_count": len(self._handlers),
            "timestamp": time.time()
        }

        # 添加生产者和消费者状态
        if self._producer:
            producer_health = self._producer.health_check()
            result["producer"] = producer_health

        if self._consumer:
            consumer_health = self._consumer.health_check()
            result["consumer"] = consumer_health

        return result


# 使用示例和工具函数
def create_communicator(agent_name: str, config: Dict[str, Any] = None) -> AgentCommunicator:
    """
    创建智能体通信器

    Args:
        agent_name: 智能体名称
        config: 配置

    Returns:
        AgentCommunicator: 通信器实例
    """
    return AgentCommunicator(agent_name, config)


def broadcast_message(
    communicator: AgentCommunicator,
    message_type: str,
    payload: Dict[str, Any],
    targets: List[str]
) -> List[Optional[Dict[str, Any]]]:
    """
    广播消息给多个智能体

    Args:
        communicator: 通信器
        message_type: 消息类型
        payload: 消息负载
        targets: 目标列表

    Returns:
        List[Optional[Dict]]: 发送结果列表
    """
    results = []
    for target in targets:
        message = AgentMessage(
            sender=communicator._agent_name,
            receiver=target,
            message_type=message_type,
            payload=payload
        )
        result = communicator._send_message(target, message)
        results.append(result)
    return results
