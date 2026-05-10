"""
DeepNovel - AI-powered novel generation framework

@file: __init__.py
@date: 2026-04-29
@version: 2.0
@description: Main package initialization
"""

__version__ = "2.0.0"
__author__ = "AI-Novels Team"

# 注意：为避免循环导入，顶层不直接导入深层子模块。
# 各组件请直接从子模块导入，例如：
#   from deepnovel.agents.base import BaseAgent
#   from deepnovel.config import ConfigHub
#   from deepnovel.core.memory_context import MemoryContext

__all__ = ["__version__", "__author__"]
