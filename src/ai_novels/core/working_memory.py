"""
工作记忆与注意力控制器 — 认知架构核心

基于认知心理学 Baddeley 工作记忆模型：
- 中央执行器（注意力控制器）：分配注意力资源
- 语音环路 / 视觉空间画板：信息暂存
- 情节缓冲器：整合多源信息

@file: core/working_memory.py
@date: 2026-04-29
"""

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


@dataclass
class WorkingMemoryEntry:
    """工作记忆条目 — 意识中的单个思维内容"""

    content: Any  # 条目内容
    entry_type: str = "generic"  # 类型: perception / goal / emotion / memory / inference
    activation: float = 1.0  # 激活度 (0-1)
    priority: float = 0.5  # 优先级 (0-1)
    source: str = ""  # 来源标识
    timestamp: float = field(default_factory=time.time)  # 进入时间
    maintenance_count: int = 0  # 维持次数
    tags: Set[str] = field(default_factory=set)  # 标签

    def decay(self, rate: float = 0.15) -> None:
        """衰减激活度（未维持时调用）"""
        self.activation = max(0.0, self.activation - rate)

    def maintain(self, boost: float = 0.2) -> None:
        """主动维持（增加激活度）"""
        self.activation = min(1.0, self.activation + boost)
        self.maintenance_count += 1
        self.timestamp = time.time()

    def is_active(self, threshold: float = 0.2) -> bool:
        """判断是否仍处于激活状态"""
        return self.activation >= threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "entry_type": self.entry_type,
            "activation": round(self.activation, 3),
            "priority": round(self.priority, 3),
            "source": self.source,
            "timestamp": self.timestamp,
            "maintenance_count": self.maintenance_count,
            "tags": list(self.tags),
        }


@dataclass
class AttentionFocus:
    """注意力焦点 — 当前意识的核心对象"""

    target_id: str = ""  # 焦点对象ID
    target_type: str = ""  # 焦点类型: character / event / location / concept
    intensity: float = 0.5  # 注意力强度 (0-1)
    start_time: float = field(default_factory=time.time)
    duration_limit: float = 30.0  # 最大持续时间(秒)

    def is_expired(self) -> bool:
        """检查注意力焦点是否过期"""
        return (time.time() - self.start_time) > self.duration_limit

    def elapsed(self) -> float:
        """获取已持续时间"""
        return time.time() - self.start_time


class WorkingMemory:
    """工作记忆 — 有限容量的意识暂存器

    特性:
    - 容量限制 (默认 7±2)
    - 条目随时间衰减
    - 主动维持可抵抗衰减
    - 高优先级条目可挤出低优先级条目
    """

    DEFAULT_CAPACITY: int = 7
    DECAY_RATE: float = 0.08  # 每秒衰减率
    REFRESH_INTERVAL: float = 1.0  # 刷新间隔(秒)

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        self._capacity = capacity
        self._entries: List[WorkingMemoryEntry] = []
        self._last_refresh = time.time()
        self._access_history: List[Tuple[float, str]] = []  # (时间, entry标识)

    def _force_decay(self) -> None:
        """强制衰减（用于测试）"""
        now = time.time()
        elapsed = now - self._last_refresh
        self._last_refresh = now
        decay_amount = self.DECAY_RATE * max(elapsed, self.REFRESH_INTERVAL)

        for entry in self._entries:
            entry.decay(decay_amount)

        # 移除已失效条目
        self._entries = [e for e in self._entries if e.is_active()]

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def occupancy(self) -> int:
        """当前占用数"""
        return len(self._entries)

    @property
    def load_ratio(self) -> float:
        """负载率 (0-1)"""
        return len(self._entries) / self._capacity

    @property
    def is_full(self) -> bool:
        return len(self._entries) >= self._capacity

    def _apply_decay(self) -> None:
        """应用时间衰减"""
        now = time.time()
        elapsed = now - self._last_refresh
        if elapsed < self.REFRESH_INTERVAL:
            return

        self._last_refresh = now
        decay_amount = self.DECAY_RATE * elapsed

        for entry in self._entries:
            entry.decay(decay_amount)

        # 移除已失效条目
        self._entries = [e for e in self._entries if e.is_active()]

    def add(
        self,
        content: Any,
        *,
        entry_type: str = "generic",
        priority: float = 0.5,
        source: str = "",
        tags: Optional[Set[str]] = None,
    ) -> Optional[WorkingMemoryEntry]:
        """添加条目到工作记忆

        Returns:
            成功返回条目，容量满且优先级不够时返回 None
        """
        self._apply_decay()

        new_entry = WorkingMemoryEntry(
            content=content,
            entry_type=entry_type,
            priority=priority,
            source=source,
            tags=tags or set(),
        )

        # 如果容量未满，直接添加
        if not self.is_full:
            self._entries.append(new_entry)
            self._access_history.append((time.time(), str(id(new_entry))))
            return new_entry

        # 容量满时，检查是否可以挤出低优先级条目
        min_entry = min(self._entries, key=lambda e: e.priority)
        if new_entry.priority > min_entry.priority:
            self._entries.remove(min_entry)
            self._entries.append(new_entry)
            self._access_history.append((time.time(), str(id(new_entry))))
            return new_entry

        # 优先级不够，无法进入工作记忆
        return None

    def maintain(self, predicate: Callable[[WorkingMemoryEntry], bool]) -> int:
        """主动维持符合条件的条目

        Returns:
            维持的条目数量
        """
        self._apply_decay()
        count = 0
        for entry in self._entries:
            if predicate(entry):
                entry.maintain()
                count += 1
        return count

    def maintain_by_type(self, entry_type: str) -> int:
        """按类型维持条目"""
        return self.maintain(lambda e: e.entry_type == entry_type)

    def maintain_by_tag(self, tag: str) -> int:
        """按标签维持条目"""
        return self.maintain(lambda e: tag in e.tags)

    def get_active_entries(
        self,
        entry_type: Optional[str] = None,
        min_activation: float = 0.0,
    ) -> List[WorkingMemoryEntry]:
        """获取激活条目（可选按类型过滤）"""
        self._apply_decay()
        entries = [e for e in self._entries if e.activation >= min_activation]
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        return sorted(entries, key=lambda e: (e.priority, e.activation), reverse=True)

    def clear(self) -> None:
        """清空工作记忆"""
        self._entries.clear()
        self._access_history.clear()

    def clear_by_type(self, entry_type: str) -> int:
        """按类型清空条目"""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.entry_type != entry_type]
        return before - len(self._entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity": self._capacity,
            "occupancy": self.occupancy,
            "load_ratio": round(self.load_ratio, 3),
            "entries": [e.to_dict() for e in self.get_active_entries()],
        }


class AttentionController:
    """注意力控制器 — 选择性注意与认知资源分配

    核心功能:
    - 计算信息的显著性得分
    - 管理注意力焦点转移
    - 认知负荷监控
    - 过滤无关信息
    """

    def __init__(
        self,
        working_memory: Optional[WorkingMemory] = None,
        capacity: int = WorkingMemory.DEFAULT_CAPACITY,
    ):
        self._wm = working_memory or WorkingMemory(capacity=capacity)
        self._focus = AttentionFocus()
        self._filters: List[Callable[[Any], bool]] = []
        self._default_weights = {
            "emotional_salience": 0.25,  # 情感显著性
            "goal_relevance": 0.30,     # 目标相关性
            "novelty": 0.20,            # 新奇性
            "unexpectedness": 0.15,     # 意外性
            "recency": 0.10,            # 新近性
        }

    @property
    def working_memory(self) -> WorkingMemory:
        return self._wm

    @property
    def focus(self) -> AttentionFocus:
        return self._focus

    @property
    def cognitive_load(self) -> float:
        """认知负荷 (0-1)"""
        base_load = self._wm.load_ratio
        # 注意力焦点强度增加负荷
        focus_load = self._focus.intensity * 0.2
        return min(1.0, base_load + focus_load)

    def is_overloaded(self, threshold: float = 0.85) -> bool:
        """检查是否认知过载"""
        return self.cognitive_load >= threshold

    def calculate_salience(
        self,
        information: Dict[str, Any],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """计算信息显著性得分

        Args:
            information: {
                "emotional_salience": float,  # 情感显著性 (0-1)
                "goal_relevance": float,      # 与当前目标的相关性 (0-1)
                "novelty": float,             # 新奇程度 (0-1)
                "unexpectedness": float,      # 意外程度 (0-1)
                "recency": float,             # 时间新近性 (0-1)
            }
            weights: 可自定义权重

        Returns:
            显著性得分 (0-1)
        """
        w = weights or self._default_weights

        score = 0.0
        for key, weight in w.items():
            score += information.get(key, 0.0) * weight

        # 认知负荷惩罚：高负荷时降低新信息的显著性
        if self.is_overloaded():
            score *= 0.7

        return min(1.0, max(0.0, score))

    def should_attend(self, information: Dict[str, Any], threshold: float = 0.4) -> bool:
        """判断是否应该注意此信息"""
        salience = self.calculate_salience(information)
        return salience >= threshold

    def shift_focus(
        self,
        target_id: str,
        target_type: str,
        intensity: float = 0.5,
        duration_limit: float = 30.0,
    ) -> AttentionFocus:
        """转移注意力焦点"""
        self._focus = AttentionFocus(
            target_id=target_id,
            target_type=target_type,
            intensity=intensity,
            duration_limit=duration_limit,
        )
        return self._focus

    def check_focus_expired(self) -> bool:
        """检查当前焦点是否过期，过期则重置"""
        if self._focus.is_expired():
            self._focus = AttentionFocus()
            return True
        return False

    def add_filter(self, filter_fn: Callable[[Any], bool]) -> None:
        """添加信息过滤器"""
        self._filters.append(filter_fn)

    def remove_filter(self, filter_fn: Callable[[Any], bool]) -> None:
        """移除信息过滤器"""
        if filter_fn in self._filters:
            self._filters.remove(filter_fn)

    def filter_input(self, data: Any) -> bool:
        """过滤输入信息

        Returns:
            True = 通过过滤，False = 被过滤掉
        """
        for filter_fn in self._filters:
            if not filter_fn(data):
                return False
        return True

    def process_input(
        self,
        content: Any,
        *,
        information: Dict[str, Any],
        entry_type: str = "perception",
        source: str = "",
        tags: Optional[Set[str]] = None,
        salience_threshold: float = 0.4,
    ) -> Optional[WorkingMemoryEntry]:
        """处理输入信息：评估显著性 → 过滤 → 进入工作记忆

        Returns:
            成功进入工作记忆的条目，或被过滤/忽略时返回 None
        """
        # 1. 检查自定义过滤器
        if not self.filter_input(content):
            return None

        # 2. 计算显著性
        salience = self.calculate_salience(information)

        # 3. 判断是否值得注意
        if salience < salience_threshold:
            return None

        # 4. 检查焦点转移
        self.check_focus_expired()

        # 5. 进入工作记忆
        return self._wm.add(
            content=content,
            entry_type=entry_type,
            priority=salience,
            source=source,
            tags=tags or set(),
        )

    def maintain_focus(self, boost: float = 0.15) -> int:
        """维持与当前焦点相关的条目"""
        if not self._focus.target_id:
            return 0

        return self._wm.maintain(
            lambda e: self._focus.target_id in str(e.content)
            or self._focus.target_type in e.tags
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cognitive_load": round(self.cognitive_load, 3),
            "is_overloaded": self.is_overloaded(),
            "focus": {
                "target_id": self._focus.target_id,
                "target_type": self._focus.target_type,
                "intensity": round(self._focus.intensity, 3),
                "elapsed": round(self._focus.elapsed(), 1),
                "is_expired": self._focus.is_expired(),
            },
            "working_memory": self._wm.to_dict(),
        }


class CharacterMindController:
    """角色心智控制器 — 整合工作记忆与注意力

    为每个角色维护独立的工作记忆和注意力状态，
    处理感知输入、记忆检索、决策支持。
    """

    def __init__(self, character_id: str, capacity: int = 7):
        self.character_id = character_id
        self._attention = AttentionController(capacity=capacity)
        self._current_goals: List[Dict[str, Any]] = []
        self._emotional_state: Dict[str, float] = {}

    @property
    def attention(self) -> AttentionController:
        return self._attention

    @property
    def working_memory(self) -> WorkingMemory:
        return self._attention.working_memory

    def set_goals(self, goals: List[Dict[str, Any]]) -> None:
        """设置当前目标（影响注意力分配）"""
        self._current_goals = goals

    def set_emotional_state(self, emotions: Dict[str, float]) -> None:
        """设置当前情感状态"""
        self._emotional_state = emotions

    def _calculate_goal_relevance(self, content: Any) -> float:
        """计算信息与当前目标的相关性"""
        if not self._current_goals:
            return 0.5

        # 简化实现：检查内容是否包含目标关键词
        content_str = str(content).lower()
        relevances = []
        for goal in self._current_goals:
            keywords = goal.get("keywords", [])
            if any(kw.lower() in content_str for kw in keywords):
                relevances.append(goal.get("priority", 0.5))

        return max(relevances) if relevances else 0.3

    def perceive(
        self,
        stimulus: Any,
        *,
        emotional_salience: float = 0.0,
        novelty: float = 0.5,
        unexpectedness: float = 0.0,
        recency: float = 1.0,
        source: str = "",
        tags: Optional[Set[str]] = None,
    ) -> Optional[WorkingMemoryEntry]:
        """角色感知输入处理

        流程:
        1. 计算目标相关性
        2. 组装显著性信息
        3. 通过注意力控制器处理
        """
        goal_relevance = self._calculate_goal_relevance(stimulus)

        information = {
            "emotional_salience": emotional_salience,
            "goal_relevance": goal_relevance,
            "novelty": novelty,
            "unexpectedness": unexpectedness,
            "recency": recency,
        }

        return self._attention.process_input(
            content=stimulus,
            information=information,
            entry_type="perception",
            source=source,
            tags=tags or set(),
        )

    def retrieve_to_working_memory(
        self,
        memory_content: Any,
        relevance: float,
    ) -> Optional[WorkingMemoryEntry]:
        """将长期记忆检索结果载入工作记忆"""
        return self._attention.process_input(
            content=memory_content,
            information={
                "emotional_salience": 0.0,
                "goal_relevance": relevance,
                "novelty": 0.5,
                "unexpectedness": 0.0,
                "recency": 1.0,
            },
            entry_type="memory",
            source="long_term_memory",
        )

    def form_intention(
        self,
        intention: Any,
        priority: float = 0.7,
    ) -> Optional[WorkingMemoryEntry]:
        """形成意图（进入工作记忆）"""
        return self.working_memory.add(
            content=intention,
            entry_type="intention",
            priority=priority,
        )

    def get_mind_state(self) -> Dict[str, Any]:
        """获取完整心智状态"""
        return {
            "character_id": self.character_id,
            "attention": self._attention.to_dict(),
            "goals": self._current_goals,
            "emotional_state": self._emotional_state,
            "cognitive_load": round(self._attention.cognitive_load, 3),
        }
