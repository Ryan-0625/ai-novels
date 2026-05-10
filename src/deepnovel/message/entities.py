"""
AI-Novels 实体模型定义

@file: src/deepnovel/model/entities.py
@date: 2026-03-12
@version: 1.0.0
@description: 定义业务实体数据模型
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Character:
    """角色实体"""
    char_id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    age_visual: int = 0
    age_real: Optional[int] = None
    gender: str = ""
    archetype: str = ""
    core_drive: str = ""
    core_wound: str = ""
    voice_style: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    profile: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "char_id": self.char_id,
            "name": self.name,
            "aliases": self.aliases,
            "age_visual": self.age_visual,
            "age_real": self.age_real,
            "gender": self.gender,
            "archetype": self.archetype,
            "core_drive": self.core_drive,
            "core_wound": self.core_wound,
            "voice_style": self.voice_style,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "profile": self.profile,
        }


@dataclass
class WorldEntity:
    """世界观实体"""
    world_id: str
    name: str
    category: str  # magic, geography, history, faction, technology
    public_description: str = ""
    secret_truth: str = ""
    unspoken_tension: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "world_id": self.world_id,
            "name": self.name,
            "category": self.category,
            "public_description": self.public_description,
            "secret_truth": self.secret_truth,
            "unspoken_tension": self.unspoken_tension,
            "tags": self.tags,
            "created_at": self.created_at,
        }


@dataclass
class OutlineNode:
    """大纲节点（卷或章）"""
    node_id: str
    node_type: str  # volume, chapter, scene
    title: str
    content: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "title": self.title,
            "content": self.content,
            "children": self.children,
            "metadata": self.metadata,
        }


@dataclass
class ChapterOutline:
    """章节大纲"""
    outline_id: str
    chapter_number: int
    title: str
    main_event: str = ""
    pacing: int = 5  # 1-10
    required_beats: List[str] = field(default_factory=list)
    emotional_trajectory: Dict[str, str] = field(default_factory=dict)  # start, end
    hooks: List[str] = field(default_factory=list)
    characters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "outline_id": self.outline_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "main_event": self.main_event,
            "pacing": self.pacing,
            "required_beats": self.required_beats,
            "emotional_trajectory": self.emotional_trajectory,
            "hooks": self.hooks,
            "characters": self.characters,
        }


@dataclass
class Conflict:
    """冲突实体"""
    conflict_id: str
    title: str
    type: str  # character, external, internal, moral
    intensity: int = 5  # 1-10
    status: str = "active"  # active, resolved, escalated
    involved_characters: List[str] = field(default_factory=list)
    escalate_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "conflict_id": self.conflict_id,
            "title": self.title,
            "type": self.type,
            "intensity": self.intensity,
            "status": self.status,
            "involved_characters": self.involved_characters,
            "escalate_count": self.escalate_count,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class NarrativeHook:
    """叙事钩子"""
    hook_id: str
    title: str
    type: str  # mystery, threat, cliffhanger, emotional_debt
    intensity: int = 5  # 1-10
    status: str = "open"  # open, active, resolved, ignored
    chapters_mentioned: List[int] = field(default_factory=list)
    resolved_in_chapter: Optional[int] = None
    associated_characters: List[str] = field(default_factory=list)
    associated_world_entities: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hook_id": self.hook_id,
            "title": self.title,
            "type": self.type,
            "intensity": self.intensity,
            "status": self.status,
            "chapters_mentioned": self.chapters_mentioned,
            "resolved_in_chapter": self.resolved_in_chapter,
            "associated_characters": self.associated_characters,
            "associated_world_entities": self.associated_world_entities,
            "created_at": self.created_at,
        }


# 实体类型常量
class EntityType:
    """实体类型常量"""
    CHARACTER = "character"
    WORLD_ENTITY = "world_entity"
    CONFLICT = "conflict"
    NARRATIVE_HOOK = "narrative_hook"
    OUTLINE = "outline"


# 冲突类型常量
class ConflictType:
    """冲突类型常量"""
    CHARACTER = "character"
    EXTERNAL = "external"
    INTERNAL = "internal"
    MORAL = "moral"


# 钩子类型常量
class HookType:
    """钩子类型常量"""
    MYSTERY = "mystery"
    THREAT = "threat"
    CLIFFHANGER = "cliffhanger"
    EMOTIONAL_DEBT = "emotional_debt"
