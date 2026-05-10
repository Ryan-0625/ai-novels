"""
MemoryContext — 三级记忆上下文

将三级记忆系统整合为Agent可用的统一上下文：
- 感觉记忆 (Sensory): 原始感知输入的短暂缓冲
- 工作记忆 (Working): 意识暂存器，注意力调控
- 长期记忆 (Long-term): 情节/语义/情感/程序记忆

@file: core/memory_context.py
@date: 2026-04-29
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from deepnovel.core.working_memory import (
    AttentionController,
    CharacterMindController,
    WorkingMemory,
    WorkingMemoryEntry,
)


@dataclass
class SensoryBufferEntry:
    """感觉记忆条目 — 原始感知数据的短暂保留"""

    content: Any
    modality: str = "text"  # text / visual / auditory / emotional
    timestamp: float = field(default_factory=time.time)
    intensity: float = 1.0  # 刺激强度
    source: str = ""

    def is_fresh(self, max_age_ms: float = 500.0) -> bool:
        """检查是否仍新鲜（默认500ms）"""
        return (time.time() - self.timestamp) * 1000 < max_age_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": str(self.content)[:200],
            "modality": self.modality,
            "timestamp": self.timestamp,
            "intensity": self.intensity,
            "source": self.source,
        }


class SensoryBuffer:
    """感觉记忆 — 感知输入的毫秒级缓冲

    特点:
    - 容量大但保留时间短（数百毫秒）
    - 未经处理的原始数据
    - 高显著性的内容会被筛选进入工作记忆
    """

    DEFAULT_MAX_SIZE: int = 100
    DEFAULT_MAX_AGE_MS: float = 500.0

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._max_size = max_size
        self._entries: List[SensoryBufferEntry] = []

    def add(
        self,
        content: Any,
        modality: str = "text",
        intensity: float = 1.0,
        source: str = "",
    ) -> SensoryBufferEntry:
        """添加感知输入"""
        entry = SensoryBufferEntry(
            content=content,
            modality=modality,
            intensity=intensity,
            source=source,
        )
        self._entries.append(entry)

        # 容量限制：移除最旧的
        if len(self._entries) > self._max_size:
            self._entries = self._entries[-self._max_size :]

        return entry

    def get_recent(self, max_age_ms: Optional[float] = None) -> List[SensoryBufferEntry]:
        """获取近期未过期的条目"""
        max_age = max_age_ms or self.DEFAULT_MAX_AGE_MS
        return [e for e in self._entries if e.is_fresh(max_age)]

    def get_by_modality(self, modality: str) -> List[SensoryBufferEntry]:
        """按感知模态获取"""
        return [e for e in self._entries if e.modality == modality]

    def get_salient(self, threshold: float = 0.7) -> List[SensoryBufferEntry]:
        """获取高显著性条目（可能进入工作记忆）"""
        return [e for e in self.get_recent() if e.intensity >= threshold]

    def clear(self) -> None:
        """清空缓冲区"""
        self._entries.clear()

    def to_dict(self) -> Dict[str, Any]:
        recent = self.get_recent()
        return {
            "total_entries": len(self._entries),
            "recent_entries": len(recent),
            "salient_entries": len(self.get_salient()),
            "modalities": list({e.modality for e in recent}),
        }


@dataclass
class LongTermMemorySnapshot:
    """长期记忆快照 — 从长期记忆检索到的相关信息"""

    episodic: List[Dict[str, Any]] = field(default_factory=list)
    semantic: List[Dict[str, Any]] = field(default_factory=list)
    emotional: List[Dict[str, Any]] = field(default_factory=list)
    procedural: List[Dict[str, Any]] = field(default_factory=list)
    retrieval_query: str = ""
    retrieval_time_ms: float = 0.0

    def is_empty(self) -> bool:
        return (
            not self.episodic
            and not self.semantic
            and not self.emotional
            and not self.procedural
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episodic_count": len(self.episodic),
            "semantic_count": len(self.semantic),
            "emotional_count": len(self.emotional),
            "procedural_count": len(self.procedural),
            "retrieval_query": self.retrieval_query,
            "retrieval_time_ms": self.retrieval_time_ms,
        }


class MemoryContext:
    """记忆上下文 — 三级记忆的统一接口

    为Agent提供完整的记忆栈：
    1. 感觉缓冲 → 原始感知输入
    2. 工作记忆 → 当前意识内容（注意力调控）
    3. 长期记忆 → 持久存储（通过MemoryManager异步访问）

    使用方式:
        context = MemoryContext(character_id="char_1")
        # 感知输入
        context.perceive("敌人出现", emotional_salience=0.9)
        # 工作记忆自动接收高显著性信息
        # 长期记忆检索（异步）
        snapshot = await context.retrieve_long_term(session, "战斗技能")
    """

    def __init__(
        self,
        character_id: str,
        working_memory_capacity: int = 7,
        enable_sensory_buffer: bool = True,
    ):
        self._character_id = character_id

        # 感觉记忆
        self._sensory = SensoryBuffer() if enable_sensory_buffer else None

        # 工作记忆 + 注意力
        self._mind = CharacterMindController(
            character_id=character_id,
            capacity=working_memory_capacity,
        )

        # 长期记忆服务（可选，延迟初始化）
        self._memory_manager = None
        self._ltm_enabled = False

        # 统计
        self._stats = {
            "perceptions": 0,
            "wm_entries_added": 0,
            "ltm_queries": 0,
            "ltm_retrievals": 0,
        }

    # ---- 属性 ----

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def sensory_buffer(self) -> Optional[SensoryBuffer]:
        return self._sensory

    @property
    def working_memory(self) -> WorkingMemory:
        return self._mind.working_memory

    @property
    def attention(self) -> AttentionController:
        return self._mind.attention

    @property
    def mind(self) -> CharacterMindController:
        return self._mind

    # ---- 感知输入（感觉记忆 → 工作记忆） ----

    def perceive(
        self,
        stimulus: Any,
        *,
        emotional_salience: float = 0.0,
        novelty: float = 0.5,
        unexpectedness: float = 0.0,
        source: str = "",
        tags: Optional[Set[str]] = None,
    ) -> Optional[WorkingMemoryEntry]:
        """处理感知输入

        流程:
        1. 进入感觉缓冲区
        2. 通过注意力控制器评估显著性
        3. 显著的内容进入工作记忆

        Returns:
            成功进入工作记忆的条目，或被过滤时返回 None
        """
        self._stats["perceptions"] += 1

        # 1. 感觉缓冲
        if self._sensory is not None:
            intensity = max(emotional_salience, novelty, unexpectedness)
            self._sensory.add(
                content=stimulus,
                modality="text",
                intensity=intensity,
                source=source,
            )

        # 2. 注意力处理 → 工作记忆
        entry = self._mind.perceive(
            stimulus=stimulus,
            emotional_salience=emotional_salience,
            novelty=novelty,
            unexpectedness=unexpectedness,
            source=source,
            tags=tags,
        )

        if entry:
            self._stats["wm_entries_added"] += 1

        return entry

    def perceive_batch(
        self,
        stimuli: List[Dict[str, Any]],
    ) -> List[WorkingMemoryEntry]:
        """批量处理感知输入"""
        entries = []
        for stimulus in stimuli:
            entry = self.perceive(
                stimulus=stimulus.get("content"),
                emotional_salience=stimulus.get("emotional_salience", 0.0),
                novelty=stimulus.get("novelty", 0.5),
                unexpectedness=stimulus.get("unexpectedness", 0.0),
                source=stimulus.get("source", ""),
                tags=set(stimulus.get("tags", [])),
            )
            if entry:
                entries.append(entry)
        return entries

    # ---- 工作记忆操作 ----

    def add_to_working_memory(
        self,
        content: Any,
        entry_type: str = "generic",
        priority: float = 0.5,
        source: str = "",
        tags: Optional[Set[str]] = None,
    ) -> Optional[WorkingMemoryEntry]:
        """直接添加内容到工作记忆"""
        entry = self._mind.working_memory.add(
            content=content,
            entry_type=entry_type,
            priority=priority,
            source=source,
            tags=tags,
        )
        if entry:
            self._stats["wm_entries_added"] += 1
        return entry

    def get_working_memory_entries(
        self,
        entry_type: Optional[str] = None,
        min_activation: float = 0.0,
    ) -> List[WorkingMemoryEntry]:
        """获取工作记忆条目"""
        return self._mind.working_memory.get_active_entries(entry_type, min_activation)

    def maintain_focus(self) -> int:
        """维持与当前注意力焦点相关的条目"""
        return self._mind.attention.maintain_focus()

    def shift_attention(
        self,
        target_id: str,
        target_type: str,
        intensity: float = 0.5,
    ) -> None:
        """转移注意力焦点"""
        self._mind.attention.shift_focus(target_id, target_type, intensity)

    def set_goals(self, goals: List[Dict[str, Any]]) -> None:
        """设置当前目标（影响注意力分配）"""
        self._mind.set_goals(goals)

    def set_emotional_state(self, emotions: Dict[str, float]) -> None:
        """设置当前情感状态"""
        self._mind.set_emotional_state(emotions)

    def form_intention(self, intention: Any, priority: float = 0.7) -> Optional[WorkingMemoryEntry]:
        """形成意图（进入工作记忆）"""
        return self._mind.form_intention(intention, priority)

    def clear_working_memory(self) -> None:
        """清空工作记忆"""
        self._mind.working_memory.clear()

    # ---- 长期记忆接口（需要异步session） ----

    def enable_long_term_memory(self, memory_manager: Any) -> None:
        """启用长期记忆（注入MemoryManager）"""
        self._memory_manager = memory_manager
        self._ltm_enabled = True

    async def retrieve_long_term(
        self,
        session: Any,
        query: str,
        strategy: str = "adaptive",
        top_k: int = 5,
    ) -> LongTermMemorySnapshot:
        """从长期记忆检索信息

        Args:
            session: 数据库session
            query: 查询内容
            strategy: 检索策略
            top_k: 返回数量

        Returns:
            长期记忆快照
        """
        import time as time_module

        start = time_module.time()
        self._stats["ltm_queries"] += 1

        snapshot = LongTermMemorySnapshot(retrieval_query=query)

        if not self._ltm_enabled or self._memory_manager is None:
            snapshot.retrieval_time_ms = (time_module.time() - start) * 1000
            return snapshot

        try:
            # 情节记忆
            episodic = await self._memory_manager.retrieval.recall_episodic(
                session, self._character_id, strategy, top_k=top_k
            )
            snapshot.episodic = [m.to_dict() for m in episodic]
        except Exception:
            pass

        try:
            # 语义记忆
            semantic = await self._memory_manager.retrieval.recall_semantic(
                session, self._character_id, top_k=top_k
            )
            snapshot.semantic = [m.to_dict() for m in semantic]
        except Exception:
            pass

        try:
            # 情感记忆
            # 从query提取情感关键词（简化实现）
            emotional = await self._memory_manager.retrieval.recall_by_emotion(
                session, self._character_id, query, top_k=top_k
            )
            snapshot.emotional = [m.to_dict() for m in emotional]
        except Exception:
            pass

        try:
            # 程序记忆
            skills = await self._memory_manager.retrieval.recall_skills(
                session, self._character_id, top_k=top_k
            )
            snapshot.procedural = [m.to_dict() for m in skills]
        except Exception:
            pass

        snapshot.retrieval_time_ms = (time_module.time() - start) * 1000
        self._stats["ltm_retrievals"] += 1

        # 将检索结果载入工作记忆（如果相关）
        if not snapshot.is_empty():
            self._mind.retrieve_to_working_memory(
                memory_content=f"检索到记忆: {query}",
                relevance=0.6,
            )

        return snapshot

    async def encode_experience(
        self,
        session: Any,
        scene_description: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """编码经历到长期记忆"""
        if not self._ltm_enabled or self._memory_manager is None:
            return None

        try:
            memory = await self._memory_manager.record_experience(
                session, self._character_id, scene_description, **kwargs
            )
            return memory.to_dict()
        except Exception:
            return None

    async def learn_fact(
        self,
        session: Any,
        concept_key: str,
        concept_value: str,
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """学习知识到语义记忆"""
        if not self._ltm_enabled or self._memory_manager is None:
            return None

        try:
            memory = await self._memory_manager.learn_fact(
                session, self._character_id, concept_key, concept_value, **kwargs
            )
            return memory.to_dict()
        except Exception:
            return None

    # ---- 上下文构建（供Prompt使用） ----

    def build_context_for_prompt(self, max_entries: int = 5) -> Dict[str, Any]:
        """构建用于Prompt生成的记忆上下文"""
        # 工作记忆条目
        wm_entries = self._mind.working_memory.get_active_entries(min_activation=0.2)
        wm_entries = sorted(wm_entries, key=lambda e: (e.priority, e.activation), reverse=True)

        # 注意力焦点
        focus = self._mind.attention.focus

        # 情感状态
        emotional_state = getattr(self._mind, "_emotional_state", {})

        # 目标
        goals = getattr(self._mind, "_current_goals", [])

        return {
            "character_id": self._character_id,
            "working_memory": [
                {
                    "type": e.entry_type,
                    "content": str(e.content)[:300],
                    "activation": round(e.activation, 2),
                    "priority": round(e.priority, 2),
                }
                for e in wm_entries[:max_entries]
            ],
            "attention_focus": {
                "target": focus.target_id,
                "type": focus.target_type,
                "intensity": round(focus.intensity, 2),
            }
            if focus.target_id
            else None,
            "emotional_state": emotional_state,
            "goals": goals,
            "cognitive_load": round(self._mind.attention.cognitive_load, 2),
            "is_overloaded": self._mind.attention.is_overloaded(),
        }

    # ---- 状态与统计 ----

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "wm_occupancy": self._mind.working_memory.occupancy,
            "wm_capacity": self._mind.working_memory.capacity,
            "wm_load_ratio": round(self._mind.working_memory.load_ratio, 3),
            "cognitive_load": round(self._mind.attention.cognitive_load, 3),
            "focus": {
                "target": self._mind.attention.focus.target_id,
                "type": self._mind.attention.focus.target_type,
            },
            "ltm_enabled": self._ltm_enabled,
        }

    def to_dict(self) -> Dict[str, Any]:
        """导出完整状态"""
        return {
            "character_id": self._character_id,
            "sensory_buffer": self._sensory.to_dict() if self._sensory else None,
            "working_memory": self._mind.working_memory.to_dict(),
            "attention": self._mind.attention.to_dict(),
            "stats": self.get_stats(),
        }
