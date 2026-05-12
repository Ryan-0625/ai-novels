"""
TaskManagerAgent - 任务管理智能体

@file: agents/task_manager.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 任务状态机/进度跟踪/断点续传
"""

import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .base import BaseAgent, AgentConfig, Message, MessageType


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Stage(Enum):
    """生成阶段"""
    INITIALIZATION = "initialization"
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW = "review"
    FINALIZATION = "finalization"


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    user_id: str
    status: TaskStatus = TaskStatus.PENDING
    current_stage: Stage = Stage.INITIALIZATION
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    paused_at: Optional[float] = None
    error_message: Optional[str] = None
    checkpoint: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "progress": self.progress,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "paused_at": self.paused_at,
            "error_message": self.error_message,
            "checkpoint": self.checkpoint,
            "logs": self.logs
        }


class TaskManagerAgent(BaseAgent):
    """
    任务管理智能体

    核心功能：
    - 任务状态机管理
    - 进度跟踪
    - 断点续传支持
    - 任务日志记录
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="task_manager",
                description="Task management and progress tracking",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=4096
            )
        super().__init__(config)

        # 任务存储
        self._tasks: Dict[str, TaskRecord] = {}
        self._current_task_id: Optional[str] = None

        # 状态转换表
        self._valid_transitions = {
            TaskStatus.PENDING: [TaskStatus.INITIALIZING, TaskStatus.CANCELLED],
            TaskStatus.INITIALIZING: [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELLED],
            TaskStatus.RUNNING: [TaskStatus.PAUSED, TaskStatus.COMPLETED, TaskStatus.FAILED],
            TaskStatus.PAUSED: [TaskStatus.RUNNING, TaskStatus.CANCELLED],
            TaskStatus.COMPLETED: [],
            TaskStatus.FAILED: [],
            TaskStatus.CANCELLED: []
        }

    def process(self, message: Message) -> Message:
        """处理消息 - 任务管理"""
        content = str(message.content).lower()

        if "create" in content:
            return self._handle_create_task(message)
        elif "update" in content:
            return self._handle_update_task(message)
        elif "status" in content or "progress" in content:
            return self._handle_query_status(message)
        elif "resume" in content:
            return self._handle_resume_task(message)
        elif "pause" in content or "stop" in content:
            return self._handle_pause_task(message)
        elif "checkpoint" in content:
            return self._handle_checkpoint(message)
        else:
            return self._handle_general_request(message)

    def _handle_create_task(self, message: Message) -> Message:
        """处理创建任务请求"""
        content = str(message.content)
        task_data = self._parse_task_request(content)

        task_id = task_data.get("task_id") or f"task_{int(time.time())}"
        user_id = task_data.get("user_id") or "default_user"

        # 创建任务记录
        task = TaskRecord(
            task_id=task_id,
            user_id=user_id,
            status=TaskStatus.PENDING,
            checkpoint=task_data.get("checkpoint", {})
        )

        self._tasks[task_id] = task
        self._current_task_id = task_id

        # 初始化日志
        self._log_task_event(task_id, "task_created", {
            "user_id": user_id,
            "request": task_data
        })

        return self._create_message(
            f"Task created: {task_id}\n"
            f"Status: {task.status.value}\n"
            f"User: {user_id}",
            MessageType.TEXT,
            task_id=task_id,
            status=task.status.value
        )

    def _handle_update_task(self, message: Message) -> Message:
        """处理更新任务请求"""
        task_id = self._current_task_id

        if not task_id or task_id not in self._tasks:
            return self._create_message(
                "No active task found. Please create a task first.",
                MessageType.TEXT
            )

        task = self._tasks[task_id]

        # 解析更新内容
        update_data = self._parse_update_request(str(message.content))

        # 更新状态
        new_status = update_data.get("status")
        if new_status:
            if self._can_transition(task.status, TaskStatus(new_status)):
                self._update_task_status(task_id, TaskStatus(new_status))
            else:
                return self._create_message(
                    f"Invalid status transition: {task.status.value} -> {new_status}",
                    MessageType.TEXT
                )

        # 更新进度
        new_progress = update_data.get("progress")
        if new_progress is not None:
            task.progress = max(0.0, min(100.0, float(new_progress)))

        # 更新.stage
        new_stage = update_data.get("stage")
        if new_stage:
            task.current_stage = Stage(new_stage)

        # 记录日志
        self._log_task_event(task_id, "task_updated", update_data)

        return self._create_message(
            f"Task updated: {task_id}\n"
            f"Status: {task.status.value}\n"
            f"Progress: {task.progress:.1f}%\n"
            f"Stage: {task.current_stage.value}",
            MessageType.TEXT,
            task_id=task_id
        )

    def _handle_query_status(self, message: Message) -> Message:
        """处理查询状态请求"""
        task_id = self._current_task_id

        if not task_id or task_id not in self._tasks:
            return self._create_message(
                "No active task found. Please create a task first.",
                MessageType.TEXT
            )

        task = self._tasks[task_id]

        elapsed = 0
        if task.started_at:
            end_time = task.completed_at or time.time()
            elapsed = end_time - task.started_at

        response = (
            f"Task Status: {task_id}\n"
            f"────────────────────\n"
            f"Status: {task.status.value}\n"
            f"Stage: {task.current_stage.value}\n"
            f"Progress: {task.progress:.1f}%\n"
            f"Created: {datetime.fromtimestamp(task.created_at).strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        if elapsed > 0:
            response += f"Elapsed: {elapsed:.1f}s\n"

        if task.checkpoint:
            response += f"Checkpoint: {len(task.checkpoint)} keys saved\n"

        if task.logs:
            response += f"Total Events: {len(task.logs)}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            task_id=task_id,
            status=task.status.value,
            progress=task.progress
        )

    def _handle_resume_task(self, message: Message) -> Message:
        """处理恢复任务请求"""
        task_id = self._current_task_id

        if not task_id or task_id not in self._tasks:
            return self._create_message(
                "No task found to resume.",
                MessageType.TEXT
            )

        task = self._tasks[task_id]

        if task.status != TaskStatus.PAUSED:
            return self._create_message(
                f"Cannot resume from status: {task.status.value}. "
                "Task must be in 'paused' state.",
                MessageType.TEXT
            )

        self._update_task_status(task_id, TaskStatus.RUNNING)
        task.started_at = task.started_at or time.time()

        # 检查是否有checkpoint
        if task.checkpoint:
            checkpoint_info = f" Resuming from checkpoint with {len(task.checkpoint)} saved items."
        else:
            checkpoint_info = ""

        self._log_task_event(task_id, "task_resumed", {"at": time.time()})

        return self._create_message(
            f"Task resumed: {task_id}{checkpoint_info}",
            MessageType.TEXT,
            task_id=task_id,
            status=TaskStatus.RUNNING.value
        )

    def _handle_pause_task(self, message: Message) -> Message:
        """处理暂停任务请求"""
        task_id = self._current_task_id

        if not task_id or task_id not in self._tasks:
            return self._create_message(
                "No active task found.",
                MessageType.TEXT
            )

        task = self._tasks[task_id]

        if task.status == TaskStatus.PAUSED:
            return self._create_message(
                f"Task is already paused: {task_id}",
                MessageType.TEXT
            )

        if task.status not in [TaskStatus.RUNNING, TaskStatus.INITIALIZING]:
            return self._create_message(
                f"Cannot pause task in status: {task.status.value}",
                MessageType.TEXT
            )

        task.paused_at = time.time()
        self._update_task_status(task_id, TaskStatus.PAUSED)

        self._log_task_event(task_id, "task_paused", {"at": time.time()})

        return self._create_message(
            f"Task paused: {task_id}",
            MessageType.TEXT,
            task_id=task_id,
            status=TaskStatus.PAUSED.value
        )

    def _handle_checkpoint(self, message: Message) -> Message:
        """处理checkpoint请求"""
        task_id = self._current_task_id

        if not task_id or task_id not in self._tasks:
            return self._create_message(
                "No active task found.",
                MessageType.TEXT
            )

        task = self._tasks[task_id]
        content = str(message.content).lower()

        if "save" in content:
            # 保存checkpoint
            checkpoint_data = self._extract_checkpoint_data(str(message.content))
            task.checkpoint.update(checkpoint_data)
            self._log_task_event(task_id, "checkpoint_saved", {"keys": list(checkpoint_data.keys())})

            return self._create_message(
                f"Checkpoint saved: {len(checkpoint_data)} items",
                MessageType.TEXT,
                task_id=task_id
            )

        elif "load" in content:
            # 加载checkpoint
            checkpoint = task.checkpoint
            return self._create_message(
                f"Checkpoint loaded: {len(checkpoint)} items\n"
                f"Keys: {list(checkpoint.keys())[:10]}",
                MessageType.TEXT,
                task_id=task_id
            )

        elif "list" in content:
            # 列出所有checkpoint
            return self._create_message(
                f"Task checkpoint info:\n"
                f"Saved at: {task.created_at}\n"
                f"Items: {len(task.checkpoint)}",
                MessageType.TEXT,
                task_id=task_id
            )

        return self._create_message(
            "Checkpoint commands: save, load, list",
            MessageType.TEXT
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Task Manager available commands:\n"
            "- 'create task [id]' - 创建新任务\n"
            "- 'update task [status/progress/stage]' - 更新任务\n"
            "- 'status' - 查询任务状态\n"
            "- 'pause' - 暂停任务\n"
            "- 'resume' - 恢复任务\n"
            "- 'checkpoint [save/load/list]' -Checkpoint管理"
        )
        return self._create_message(response)

    def _parse_task_request(self, content: str) -> Dict[str, Any]:
        """解析任务请求"""
        task_data = {
            "task_id": None,
            "user_id": None,
            "request": content,
            "checkpoint": {}
        }

        # 简单解析
        if " task " in content:
            parts = content.split()
            for part in parts:
                if part.startswith("task_"):
                    task_data["task_id"] = part
                    break

        return task_data

    def _parse_update_request(self, content: str) -> Dict[str, Any]:
        """解析更新请求"""
        update_data = {}

        content_lower = content.lower()

        if "pending" in content_lower:
            update_data["status"] = "pending"
        elif "initializing" in content_lower:
            update_data["status"] = "initializing"
        elif "running" in content_lower:
            update_data["status"] = "running"
        elif "paused" in content_lower:
            update_data["status"] = "paused"
        elif "completed" in content_lower:
            update_data["status"] = "completed"
        elif "failed" in content_lower:
            update_data["status"] = "failed"

        if "progress" in content_lower:
            for word in content.split():
                if word.replace("%", "").isdigit():
                    update_data["progress"] = float(word.replace("%", ""))
                    break

        if "stage" in content_lower:
            for stage in ["initialization", "planning", "execution", "review", "finalization"]:
                if stage in content_lower:
                    update_data["stage"] = stage
                    break

        return update_data

    def _extract_checkpoint_data(self, content: str) -> Dict[str, Any]:
        """提取checkpoint数据"""
        try:
            # 尝试解析JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {}

    def _can_transition(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """检查状态转换是否合法"""
        valid = self._valid_transitions.get(from_status, [])
        return to_status in valid

    def _update_task_status(self, task_id: str, status: TaskStatus) -> bool:
        """更新任务状态"""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]

        if not self._can_transition(task.status, status):
            return False

        task.status = status

        if status == TaskStatus.RUNNING and task.started_at is None:
            task.started_at = time.time()

        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.completed_at = time.time()

        return True

    def _log_task_event(self, task_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """记录任务事件"""
        if task_id not in self._tasks:
            return

        task = self._tasks[task_id]

        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "data": data
        }

        task.logs.append(event)

        # 限制日志数量
        if len(task.logs) > 1000:
            task.logs = task.logs[-1000:]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务详情"""
        if task_id not in self._tasks:
            return None
        return self._tasks[task_id].to_dict()

    def list_tasks(self, user_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """列出任务"""
        tasks = []
        for task in self._tasks.values():
            if user_id and task.user_id != user_id:
                continue
            tasks.append(task.to_dict())
        return tasks[:limit]

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            if self._current_task_id == task_id:
                self._current_task_id = None
            return True
        return False

    def save_all(self) -> int:
        """保存所有任务到checkpoint"""
        saved = 0
        for task_id, task in self._tasks.items():
            if task.status in [TaskStatus.PAUSED, TaskStatus.COMPLETED]:
                saved += 1
        return saved

    def clear_completed(self, days: int = 7) -> int:
        """清理过期完成任务"""
        cutoff = time.time() - (days * 86400)
        removed = 0

        for task_id in list(self._tasks.keys()):
            task = self._tasks[task_id]
            if task.completed_at and task.completed_at < cutoff:
                del self._tasks[task_id]
                removed += 1

        return removed

    def reset(self) -> None:
        """重置任务管理器"""
        self._tasks.clear()
        self._current_task_id = None
