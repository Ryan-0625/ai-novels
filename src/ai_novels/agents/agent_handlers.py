"""
智能体消息处理器

@file: agents/agent_handlers.py
@date: 2026-03-12
@version: 1.0.0
@description: 为各智能体提供RocketMQ消息处理支持
"""

import json
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import threading
from queue import Queue

from ai_novels.messaging.rocketmq_consumer import BaseConsumer, RocketMQConsumer, ConsumerConfig, MessageHandler
from ai_novels.message.message import AgentMessage, MessageType
from ai_novels.agents.agent_communicator import AgentCommunicator
from ai_novels.utils import log_info, log_warn, log_error


class AgentMessageType(Enum):
    """智能体消息类型"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_STATUS_UPDATE = "task_status_update"
    AGENT_QUERY = "agent_query"
    AGENT_RESPONSE = "agent_response"
    HEALTH_CHECK = "health_check"
    HEALTH_CHECK_RESPONSE = "health_check_response"
    CONFIG_REQUEST = "config_request"
    CONFIG_RESPONSE = "config_response"


@dataclass
class AgentMessageContext:
    """智能体消息上下文"""
    sender: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: str
    task_id: str = ""


class AgentMessageHandler(MessageHandler):
    """
    通用智能体消息处理器

    用于各智能体订阅和处理消息
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
            f"agent_{agent_name}_queue",
            "ai_novels_agent_communication",
            "ai_novels_task_execution"
        ]
        self._received_messages: Queue = Queue()
        self._running = False

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
            self._received_messages.put(message)

            # 调用回调函数
            if self._message_callback:
                return self._message_callback(message)

            log_info(f"[{self._agent_name}] Received message: {message.get('message_type', 'unknown')}")
            return True

        except Exception as e:
            log_error(f"[{self._agent_name}] Error handling message: {str(e)}")
            return False

    def process_all_messages(self) -> List[Dict[str, Any]]:
        """
        处理所有待处理消息

        Returns:
            List[Dict]: 处理的消息列表
        """
        processed = []
        while not self._received_messages.empty():
            try:
                message = self._received_messages.get_nowait()
                processed.append(message)
            except Exception:
                break
        return processed

    def clear_messages(self):
        """清空消息队列"""
        while not self._received_messages.empty():
            try:
                self._received_messages.get_nowait()
            except Exception:
                break

    def is_empty(self) -> bool:
        """检查队列是否为空"""
        return self._received_messages.empty()


class BaseAgentMessageProcessor:
    """
    基础智能体消息处理器

    提供智能体消息处理框架
    """

    def __init__(self, agent_name: str):
        self._agent_name = agent_name
        self._handler: Optional[AgentMessageHandler] = None
        self._consumer: Optional[RocketMQConsumer] = None
        self._running = False

    def setup_consumer(self, name_server: str = "localhost:9876", consumer_group: str = None) -> bool:
        """
        设置消费者

        Args:
            name_server: NameServer地址
            consumer_group: 消费者组名称

        Returns:
            bool: 设置成功返回True
        """
        try:
            if consumer_group is None:
                consumer_group = f"{self._agent_name}_consumer"

            self._consumer = RocketMQConsumer(ConsumerConfig(
                name_server=name_server,
                consumer_group=consumer_group,
                topic=f"agent_{self._agent_name}_queue",
                max_concurrency=5
            ))

            if not self._consumer.connect():
                return False

            # 创建并注册处理器
            self._handler = AgentMessageHandler(
                self._agent_name,
                self._on_message
            )
            self._consumer.subscribe(self._handler)

            return True

        except Exception as e:
            log_error(f"[{self._agent_name}] Setup consumer error: {str(e)}")
            return False

    def _on_message(self, message: Dict[str, Any]) -> bool:
        """
        消息接收回调

        Args:
            message: 消息数据

        Returns:
            bool: 处理成功返回True
        """
        message_type = message.get("message_type", "")

        if message_type == MessageType.TASK_REQUEST:
            return self._handle_task_request(message)
        elif message_type == MessageType.TASK_RESPONSE:
            return self._handle_task_response(message)
        elif message_type == MessageType.TASK_STATUS_UPDATE:
            return self._handle_status_update(message)
        elif message_type == MessageType.AGENT_QUERY:
            return self._handle_query(message)
        elif message_type == MessageType.HEALTH_CHECK:
            return self._handle_health_check(message)
        else:
            log_warn(f"[{self._agent_name}] Unknown message type: {message_type}")
            return True

    def _handle_task_request(self, message: Dict[str, Any]) -> bool:
        """处理任务请求"""
        log_info(f"[{self._agent_name}] Task request received")
        return True

    def _handle_task_response(self, message: Dict[str, Any]) -> bool:
        """处理任务响应"""
        log_info(f"[{self._agent_name}] Task response received")
        return True

    def _handle_status_update(self, message: Dict[str, Any]) -> bool:
        """处理状态更新"""
        log_info(f"[{self._agent_name}] Status update received")
        return True

    def _handle_query(self, message: Dict[str, Any]) -> bool:
        """处理查询请求"""
        log_info(f"[{self._agent_name}] Query received")
        return True

    def _handle_health_check(self, message: Dict[str, Any]) -> bool:
        """处理健康检查"""
        log_info(f"[{self._agent_name}] Health check received")
        return True

    def start(self) -> bool:
        """
        启动消息处理器

        Returns:
            bool: 启动成功返回True
        """
        if not self._consumer:
            return False

        self._running = True
        return self._consumer.start()

    def stop(self) -> bool:
        """
        停止消息处理器

        Returns:
            bool: 停止成功返回True
        """
        self._running = False
        if self._consumer:
            return self._consumer.stop()
        return True

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running and self._consumer.is_running() if self._consumer else False


# 各智能体的具体消息处理器

class CoordinatorMessageProcessor(BaseAgentMessageProcessor):
    """Coordinator智能体消息处理器"""

    def __init__(self):
        super().__init__("coordinator")
        self._task_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_task_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置任务回调"""
        self._task_callback = callback

    def _handle_task_request(self, message: Dict[str, Any]) -> bool:
        """处理任务请求"""
        payload = message.get("payload", {})
        log_info(f"[Coordinator] Handling task request: {payload.get('task_id', 'unknown')}")

        if self._task_callback:
            self._task_callback(payload)

        return True


class TaskManagerMessageProcessor(BaseAgentMessageProcessor):
    """TaskManager智能体消息处理器"""

    def __init__(self):
        super().__init__("task_manager")

    def _handle_task_request(self, message: Dict[str, Any]) -> bool:
        """处理任务请求"""
        payload = message.get("payload", {})
        task_id = payload.get("task_id", "")

        log_info(f"[TaskManager] Starting task: {task_id}")

        # 更新任务状态
        status_update = {
            "message_type": MessageType.TASK_STATUS_UPDATE,
            "task_id": task_id,
            "status": "executing",
            "progress": 0.0,
            "current_stage": "initializing",
            "timestamp": int(time.time() * 1000)
        }

        # 发送状态更新
        # request = TaskStatusUpdate.from_dict(status_update)
        return True


class HealthCheckerMessageProcessor(BaseAgentMessageProcessor):
    """HealthChecker智能体消息处理器"""

    def __init__(self):
        super().__init__("health_checker")
        self._last_check_time: float = 0
        self._health_status: Dict[str, Any] = {"status": "healthy", "components": {}}

    def _handle_health_check(self, message: Dict[str, Any]) -> bool:
        """处理健康检查"""
        current_time = time.time()

        # 简单的健康检查间隔限制
        if current_time - self._last_check_time < 5:
            return True

        self._last_check_time = current_time

        # 更新健康状态
        self._health_status = {
            "status": "healthy",
            "timestamp": int(current_time),
            "components": {
                "memory": "ok",
                "disk": "ok",
                "network": "ok"
            }
        }

        # 发送响应
        response = {
            "message_type": MessageType.HEALTH_CHECK_RESPONSE,
            "sender": "health_checker",
            "status": self._health_status
        }

        return True


class ConfigEnhancerMessageProcessor(BaseAgentMessageProcessor):
    """ConfigEnhancer智能体消息处理器"""

    def __init__(self):
        super().__init__("config_enhancer")

    def _handle_config_request(self, message: Dict[str, Any]) -> bool:
        """处理配置请求"""
        payload = message.get("payload", {})
        log_info(f"[ConfigEnhancer] Processing config request")

        # 这里应该调用ConfigEnhancer进行配置增强
        # enhanced_config = self._enhance_config(payload.get("config", {}))

        return True


# 消息处理器管理器
class AgentHandlerManager:
    """智能体处理器管理器"""

    def __init__(self):
        self._processors: Dict[str, BaseAgentMessageProcessor] = {}
        self._running = False

    def register_processor(self, processor: BaseAgentMessageProcessor) -> bool:
        """
        注册消息处理器

        Args:
            processor: 消息处理器

        Returns:
            bool: 注册成功返回True
        """
        self._processors[processor._agent_name] = processor
        return True

    def setup_all(self, name_server: str = "localhost:9876") -> bool:
        """
        设置所有处理器

        Args:
            name_server: NameServer地址

        Returns:
            bool: 全部设置成功返回True
        """
        success = True
        for name, processor in self._processors.items():
            if not processor.setup_consumer(name_server):
                log_error(f"Failed to setup consumer for {name}")
                success = False
        return success

    def start_all(self) -> bool:
        """
        启动所有处理器

        Returns:
            bool: 全部启动成功返回True
        """
        if self._running:
            return True

        self._running = True
        success = True

        for name, processor in self._processors.items():
            if not processor.start():
                log_error(f"Failed to start processor: {name}")
                success = False

        return success

    def stop_all(self) -> bool:
        """
        停止所有处理器

        Returns:
            bool: 全部停止成功返回True
        """
        self._running = False
        success = True

        for name, processor in self._processors.items():
            if not processor.stop():
                log_error(f"Failed to stop processor: {name}")
                success = False

        return success

    def get_status(self) -> Dict[str, Any]:
        """
        获取状态

        Returns:
            Dict: 状态信息
        """
        status = {}
        for name, processor in self._processors.items():
            status[name] = {
                "running": processor.is_running()
            }
        return status


# 使用示例
if __name__ == "__main__":
    # 创建处理器管理器
    manager = AgentHandlerManager()

    # 注册处理器
    coordinator_processor = CoordinatorMessageProcessor()
    manager.register_processor(coordinator_processor)

    health_processor = HealthCheckerMessageProcessor()
    manager.register_processor(health_processor)

    # 设置并启动
    if manager.setup_all("localhost:9876"):
        log_info("All consumers setup successfully")

    if manager.start_all():
        log_info("All processors started")

        try:
            while manager._running:
                time.sleep(1)
        except KeyboardInterrupt:
            manager.stop_all()
            log_info("All processors stopped")
