"""
消息模块初始化

@file: messaging/__init__.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 导出消息模块的公共接口
"""

from .rocketmq_producer import (
    RocketMQConfig,
    BaseProducer,
    RocketMQProducer,
    NovelGenerationMessage,
    notifyMessage
)

from .rocketmq_consumer import (
    ConsumerConfig,
    MessageHandler,
    BaseConsumer,
    RocketMQConsumer,
    NovelGenerationHandler,
    NotifyMessageHandler,
    TaskStatusHandler,
    ConsumerManager
)

__all__ = [
    # Producer
    'RocketMQConfig',
    'BaseProducer',
    'RocketMQProducer',
    'NovelGenerationMessage',
    'notifyMessage',
    # Consumer
    'ConsumerConfig',
    'MessageHandler',
    'BaseConsumer',
    'RocketMQConsumer',
    'NovelGenerationHandler',
    'NotifyMessageHandler',
    'TaskStatusHandler',
    'ConsumerManager'
]
