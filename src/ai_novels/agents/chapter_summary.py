"""
ChapterSummaryAgent - 章节摘要生成智能体

@file: agents/chapter_summary.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 节拍分解、事件序列、情感弧线生成
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import json

from .base import BaseAgent, AgentConfig, Message, MessageType


class BeatType(Enum):
    """节拍类型"""
    SETUP = "setup"           # 铺垫
    INCITING = "inciting"     # 激励事件
    RISING = "rising"         # 上升冲突
    TWIST = "twist"           # 扭转
    CLIMAX = "climax"         # 高潮
    RESOLUTION = "resolution" # 解决
    TRANSITION = "transition" # 过渡


class EmotionalArcType(Enum):
    """情感弧线类型"""
    NEUTRAL = "neutral"
    HOPEFUL = "hopeful"
    TENSE = "tense"
    SAD = "sad"
    JOYFUL = "joyful"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"


@dataclass
class Beat:
    """章节节拍"""
    beat_id: str
    beat_type: BeatType
    description: str
    location: str
    characters: List[str]
    emotional_tone: str
    duration: int  # 场景持续时间（页数）
    hooks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "type": self.beat_type.value,
            "description": self.description,
            "location": self.location,
            "characters": self.characters,
            "emotional_tone": self.emotional_tone,
            "duration": self.duration,
            "hooks": self.hooks
        }


@dataclass
class EventSequence:
    """事件序列"""
    sequence_id: str
    events: List[Beat]
    pacing: str  # 节奏_fast, _normal, _slow
    tension_level: int  # 0-100
    emotional_arc: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "events": [e.to_dict() for e in self.events],
            "pacing": self.pacing,
            "tension_level": self.tension_level,
            "emotional_arc": self.emotional_arc
        }


@dataclass
class ChapterSummary:
    """章节摘要"""
    chapter_id: str
    title: str
    outline: str
    beats: List[Beat]
    event_sequence: EventSequence
    character_arcs: Dict[str, Dict[str, Any]]
    emotional_arc: List[Dict[str, Any]]
    hooks: List[str]
    word_count_target: int
    keywords: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "outline": self.outline,
            "beats": [b.to_dict() for b in self.beats],
            "event_sequence": self.event_sequence.to_dict(),
            "character_arcs": self.character_arcs,
            "emotional_arc": self.emotional_arc,
            "hooks": self.hooks,
            "word_count_target": self.word_count_target,
            "keywords": self.keywords
        }


@dataclass
class ArcSegment:
    """情感弧线段"""
    segment_id: str
    start_chapter: int
    end_chapter: int
    arc_type: EmotionalArcType
    intensity: int  # 0-100
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_chapter": self.start_chapter,
            "end_chapter": self.end_chapter,
            "arc_type": self.arc_type.value,
            "intensity": self.intensity,
            "description": self.description
        }


class ChapterSummaryAgent(BaseAgent):
    """
    章节摘要生成智能体

    核心功能：
    - 节拍分解（Beats）
    - 事件序列生成
    - 情感弧线追踪
    - 钩子生成
    - 字符弧线追踪
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="chapter_summary",
                description="Chapter summary and beat breakdown",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=4096
            )
        super().__init__(config)

        # 存储生成的摘要
        self._chapter_summaries: Dict[str, ChapterSummary] = {}
        self._emotional_arcs: Dict[str, ArcSegment] = {}
        self._beat_library: Dict[str, List[Beat]] = {}  # 预生成的节拍库
        self._sequence_library: Dict[str, EventSequence] = {}

        # 统计信息
        self._total_chapters_generated = 0
        self._total_beats_generated = 0

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "chapter" in content or "summary" in content:
            if "generate" in content or "create" in content:
                return self._handle_generate_summary(message)
            elif "list" in content:
                return self._handle_list_summaries(message)
            elif "read" in content or "get" in content:
                return self._handle_get_summary(message)
        elif "beat" in content:
            if "generate" in content or "breakdown" in content:
                return self._handle_generate_beats(message)
            elif "library" in content:
                return self._handle_beat_library(message)
        elif "arc" in content:
            if "emotional" in content or "emotion" in content:
                return self._handle_emotional_arc(message)
        elif "sequence" in content:
            return self._handle_sequence_request(message)

        return self._handle_general_request(message)

    def _handle_generate_summary(self, message: Message) -> Message:
        """处理生成摘要请求"""
        content = str(message.content)

        # 获取参数
        chapter_id = self._extract_param(content, "chapter_id", "chapter")
        title = self._extract_param(content, "title", "Chapter " + chapter_id)
        outline = self._extract_param(content, "outline", "")
        word_count = int(self._extract_param(content, "word_count", "2000"))

        # 生成章节摘要
        summary = self._generate_chapter_summary(
            chapter_id=chapter_id,
            title=title,
            outline=outline,
            word_count_target=word_count
        )

        self._chapter_summaries[chapter_id] = summary

        response = f"Generated Summary for Chapter {chapter_id}:\n\n"
        response += f"Title: {summary.title}\n"
        response += f"Word Count Target: {summary.word_count_target}\n"
        response += f"Beats Count: {len(summary.beats)}\n"
        response += f"Keywords: {', '.join(summary.keywords)}\n"
        response += f"\nOutline:\n{summary.outline}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            chapter_id=chapter_id,
            beats_count=len(summary.beats),
            word_count_target=summary.word_count_target
        )

    def _handle_generate_beats(self, message: Message) -> Message:
        """处理生成节拍请求"""
        content = str(message.content)

        chapter_id = self._extract_param(content, "chapter_id", "default")
        beat_count = int(self._extract_param(content, "count", "6"))

        beats = self._generate_beats(
            chapter_id=chapter_id,
            count=beat_count
        )

        self._beat_library[chapter_id] = beats

        response = f"Generated {len(beats)} Beats for Chapter {chapter_id}:\n\n"
        for i, beat in enumerate(beats):
            response += f"{i+1}. [{beat.beat_type.value.upper()}] {beat.description}\n"
            response += f"   Characters: {', '.join(beat.characters)}\n"
            response += f"   Location: {beat.location}\n"
            response += f"   Duration: {beat.duration} pages\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            chapter_id=chapter_id,
            beats_count=len(beats)
        )

    def _handle_emotional_arc(self, message: Message) -> Message:
        """处理情感弧线请求"""
        content = str(message.content)

        if "create" in content or "generate" in content:
            arc_id = self._extract_param(content, "arc_id", "main_arc")
            arc_type = self._extract_param(content, "type", "hopeful")
            intensity = int(self._extract_param(content, "intensity", "50"))
            chapters = int(self._extract_param(content, "chapters", "10"))

            arc_segment = self._create_emotional_arc_segment(
                arc_id=arc_id,
                arc_type=EmotionalArcType(arc_type.lower()),
                intensity=intensity,
                start_chapter=1,
                end_chapter=chapters
            )

            self._emotional_arcs[arc_id] = arc_segment

            response = f"Created Emotional Arc {arc_id}:\n"
            response += f"Type: {arc_segment.arc_type.value}\n"
            response += f"Intensity: {arc_segment.intensity}\n"
            response += f"Chapters: {arc_segment.start_chapter} - {arc_segment.end_chapter}\n"
            response += f"Description: {arc_segment.description}\n"

            return self._create_message(
                response,
                MessageType.TEXT,
                arc_id=arc_id,
                arc_type=arc_segment.arc_type.value
            )

        elif "list" in content or "show" in content:
            if not self._emotional_arcs:
                return self._create_message("No emotional arcs generated yet.", MessageType.TEXT)

            response = "Emotional Arcs:\n"
            for arc_id, arc in self._emotional_arcs.items():
                response += f"- {arc_id}: {arc.arc_type.value} (Intensity: {arc.intensity})\n"

            return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_sequence_request(self, message: Message) -> Message:
        """处理事件序列请求"""
        content = str(message.content)

        if "generate" in content or "create" in content:
            sequence_id = self._extract_param(content, "sequence_id", "seq_001")
            beats = self._extract_param(content, "beats", "").split(",")
            pacing = self._extract_param(content, "pacing", "normal")

            beat_list = self._beat_library.get(beats[0].strip(), []) if beats[0].strip() in self._beat_library else []

            sequence = self._create_event_sequence(
                sequence_id=sequence_id,
                beats=beat_list,
                pacing=pacing
            )

            self._sequence_library[sequence_id] = sequence

            response = f"Created Event Sequence {sequence_id}:\n"
            response += f"Pacing: {sequence.pacing}\n"
            response += f"Tension Level: {sequence.tension_level}\n"
            response += f"Events: {len(sequence.events)}\n"

            return self._create_message(
                response,
                MessageType.TEXT,
                sequence_id=sequence_id,
                event_count=len(sequence.events)
            )

        return self._handle_general_request(message)

    def _handle_list_summaries(self, message: Message) -> Message:
        """处理列出摘要请求"""
        if not self._chapter_summaries:
            return self._create_message("No chapter summaries generated yet.", MessageType.TEXT)

        response = "Chapter Summaries:\n"
        for chapter_id, summary in self._chapter_summaries.items():
            response += f"- Chapter {chapter_id}: {summary.title} ({len(summary.beats)} beats)\n"

        response += f"\nTotal: {len(self._chapter_summaries)} chapters"

        return self._create_message(response, MessageType.TEXT)

    def _handle_get_summary(self, message: Message) -> Message:
        """处理获取摘要请求"""
        content = str(message.content)
        chapter_id = self._extract_param(content, "chapter_id", "")

        if chapter_id and chapter_id in self._chapter_summaries:
            summary = self._chapter_summaries[chapter_id]

            response = f"=== Chapter {chapter_id} Summary ===\n\n"
            response += f"Title: {summary.title}\n"
            response += f"Outline: {summary.outline}\n\n"
            response += f"Keywords: {', '.join(summary.keywords)}\n"
            response += f"Word Count Target: {summary.word_count_target}\n\n"

            response += "Beats:\n"
            for beat in summary.beats:
                response += f"  - [{beat.beat_type.value}] {beat.description}\n"

            response += f"\nEmotional Arc:\n"
            for point in summary.emotional_arc[:5]:  # show first 5
                response += f"  - Chapter {point.get('chapter', '?')}: {point.get('emotion', '?')} ({point.get('intensity', '?')})\n"

            return self._create_message(response, MessageType.TEXT)

        return self._create_message(f"Chapter {chapter_id} not found.", MessageType.TEXT)

    def _handle_beat_library(self, message: Message) -> Message:
        """处理节拍库请求"""
        if not self._beat_library:
            return self._create_message("Beat library is empty.", MessageType.TEXT)

        response = "Beat Library:\n"
        for chapter_id, beats in self._beat_library.items():
            response += f"\nChapter {chapter_id} ({len(beats)} beats):\n"
            for beat in beats:
                response += f"  - [{beat.beat_type.value}] {beat.description[:50]}...\n"

        return self._create_message(response, MessageType.TEXT)

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Chapter Summary Agent available commands:\n"
            "- 'generate summary chapter_id=X title=X outline=X' - 生成章节摘要\n"
            "- 'generate beats chapter_id=X count=X' - 生成节拍\n"
            "- 'create emotional arc arc_id=X type=X chapters=X' - 创建情感弧线\n"
            "- 'create sequence sequence_id=X beats=X pacing=X' - 创建事件序列\n"
            "- 'list summaries' - 列出摘要\n"
            "- 'get summary chapter_id=X' - 获取摘要详情\n"
            "- 'list beats' - 列出节拍库\n"
            "- 'list arcs' - 列出情感弧线"
        )
        return self._create_message(response)

    def _generate_chapter_summary(
        self,
        chapter_id: str,
        title: str,
        outline: str,
        word_count_target: int,
        beats: List[Beat] = None
    ) -> ChapterSummary:
        """
        生成章节摘要

        Args:
            chapter_id: 章节ID
            title: 章节标题
            outline: 章节大纲
            word_count_target: 目标字数
            beats: 预生成的节拍（可选）

        Returns:
            ChapterSummary实例
        """
        # 如果没有提供节拍，自动生成
        if not beats:
            beats = self._generate_beats(chapter_id, 6)

        # 生成事件序列
        event_sequence = self._create_event_sequence(
            sequence_id=f"seq_{chapter_id}",
            beats=beats,
            pacing="normal"
        )

        # 生成情感弧线
        emotional_arc = self._generate_emotional_arc(chapter_id, beats)

        # 提取字符弧线
        character_arcs = self._extract_character_arcs(chapter_id, beats)

        # 提取关键词
        keywords = self._extract_keywords(title, outline, beats)

        summary = ChapterSummary(
            chapter_id=chapter_id,
            title=title,
            outline=outline,
            beats=beats,
            event_sequence=event_sequence,
            character_arcs=character_arcs,
            emotional_arc=emotional_arc,
            hooks=self._generate_hooks(chapter_id, beats),
            word_count_target=word_count_target,
            keywords=keywords
        )

        self._total_chapters_generated += 1
        self._total_beats_generated += len(beats)

        return summary

    def _generate_beats(self, chapter_id: str, count: int = 6) -> List[Beat]:
        """
        生成节拍序列

        Args:
            chapter_id: 章节ID
            count: 节拍数量

        Returns:
            Beat列表
        """
        beats = []

        # 默认节拍模板（6节拍结构）
        beat_templates = [
            (BeatType.SETUP, "Introduction and setup of current situation", 1),
            (BeatType.INCITING, "Inciting incident disrupts the status quo", 1),
            (BeatType.RISING, "Rising tension and challenges emerge", 2),
            (BeatType.TWIST, "Plot twist or major development", 1),
            (BeatType.CLIIMAX, "Chapter climax with high intensity", 2),
            (BeatType.RESOLUTION, "Resolution and setup for next chapter", 1),
        ]

        # 如果count不是标准值，调整模板
        if count != 6:
            beat_templates = self._adjust_beat_template(count)

        character_names = ["Protagonist", "Antagonist", "Supporting Character"]
        locations = ["Castle", "Forest", "Village", "Battlefield", "Sanctuary", "City"]

        for i, (beat_type, description, duration) in enumerate(beat_templates):
            beat = Beat(
                beat_id=f"beat_{chapter_id}_{i+1}",
                beat_type=beat_type,
                description=description,
                location=locations[i % len(locations)],
                characters=character_names[:min(i+1, 3)],
                emotional_tone=self._get_emotional_tone(beat_type),
                duration=duration,
                hooks=[]
            )
            beats.append(beat)

        return beats

    def _adjust_beat_template(self, count: int) -> List[tuple]:
        """调整节拍模板"""
        templates = {
            3: [
                (BeatType.SETUP, "Setup", 2),
                (BeatType.CLIIMAX, "Major Development", 3),
                (BeatType.RESOLUTION, "Resolution", 2),
            ],
            5: [
                (BeatType.SETUP, "Setup", 1),
                (BeatType.INCITING, "Inciting Incident", 1),
                (BeatType.RISING, "Rising Tension", 2),
                (BeatType.CLIIMAX, "Cliffhanger", 2),
                (BeatType.RESOLUTION, "Resolution", 1),
            ],
            7: [
                (BeatType.SETUP, "Setup", 1),
                (BeatType.INCITING, "Inciting Incident", 1),
                (BeatType.RISING, "Rising Tension 1", 1),
                (BeatType.TWIST, "First Twist", 1),
                (BeatType.RISING, "Rising Tension 2", 1),
                (BeatType.CLIIMAX, "Climax", 2),
                (BeatType.RESOLUTION, "Resolution", 1),
            ],
        }
        return templates.get(count, templates[6])

    def _create_event_sequence(
        self,
        sequence_id: str,
        beats: List[Beat],
        pacing: str = "normal"
    ) -> EventSequence:
        """
        创建事件序列

        Args:
            sequence_id: 序列ID
            beats: 节拍列表
            pacing: 节奏

        Returns:
            EventSequence实例
        """
        # 计算紧张度
        tension_level = self._calculate_tension_level(beats)

        # 生成情感弧线
        emotional_arc = [
            {
                "beat_id": b.beat_id,
                "emotion": b.emotional_tone,
                "intensity": min(100, 30 + len(b.description))
            }
            for b in beats
        ]

        return EventSequence(
            sequence_id=sequence_id,
            events=beats,
            pacing=pacing,
            tension_level=tension_level,
            emotional_arc=emotional_arc
        )

    def _generate_emotional_arc(
        self,
        chapter_id: str,
        beats: List[Beat]
    ) -> List[Dict[str, Any]]:
        """
        生成章节情感弧线

        Args:
            chapter_id: 章节ID
            beats: 节拍列表

        Returns:
            情感弧线数据
        """
        arc = []
        current_intensity = 50

        for beat in beats:
            intensity_change = {
                BeatType.SETUP: -10,
                BeatType.INCITING: 20,
                BeatType.RISING: 15,
                BeatType.TWIST: 30,
                BeatType.CLIIMAX: 40,
                BeatType.RESOLUTION: -20,
            }

            change = intensity_change.get(beat.beat_type, 0)
            current_intensity = max(0, min(100, current_intensity + change))

            arc.append({
                "chapter": chapter_id,
                "beat": beat.beat_id,
                "emotion": beat.emotional_tone,
                "intensity": current_intensity,
                "beat_type": beat.beat_type.value
            })

        return arc

    def _extract_character_arcs(
        self,
        chapter_id: str,
        beats: List[Beat]
    ) -> Dict[str, Dict[str, Any]]:
        """
        提取字符弧线

        Args:
            chapter_id: 章节ID
            beats: 节拍列表

        Returns:
            字符弧线字典
        """
        character_arcs = {}

        for beat in beats:
            for character in beat.characters:
                if character not in character_arcs:
                    character_arcs[character] = {
                        "name": character,
                        "chapter_appearances": [],
                        "development": [],
                        "emotional_state": "neutral"
                    }

                character_arcs[character]["chapter_appearances"].append(chapter_id)
                character_arcs[character]["development"].append({
                    "chapter": chapter_id,
                    "beat": beat.beat_id,
                    "change": beat.beat_type.value,
                    "emotion": beat.emotional_tone
                })

        return character_arcs

    def _extract_keywords(
        self,
        title: str,
        outline: str,
        beats: List[Beat]
    ) -> List[str]:
        """
        提取关键词

        Args:
            title: 标题
            outline: 大纲
            beats: 节拍列表

        Returns:
            关键词列表
        """
        keywords = set()

        # 从标题提取
        keywords.update(title.lower().split())

        # 从大纲提取
        keywords.update(outline.lower().split())

        # 从节拍提取
        for beat in beats:
            keywords.update(beat.description.lower().split())

        # 移除停用词
        stop_words = {"the", "and", "of", "in", "to", "a", "for", "is", "on"}
        keywords = [k for k in keywords if k not in stop_words and len(k) > 2]

        return keywords[:10]  # 返回前10个

    def _generate_hooks(self, chapter_id: str, beats: List[Beat]) -> List[str]:
        """
        生成钩子

        Args:
            chapter_id: 章节ID
            beats: 节拍列表

        Returns:
            钩子列表
        """
        hooks = []

        for beat in beats:
            if beat.beat_type == BeatType.TWIST or beat.beat_type == BeatType.CLIIMAX:
                hooks.append(f"What happens next? [{beat.beat_id}]")
            elif beat.beat_type == BeatType.INCITING:
                hooks.append(f"How will this change everything? [{beat.beat_id}]")

        if not hooks:
            hooks.append("Keep reading to discover what happens...")

        return hooks

    def _create_emotional_arc_segment(
        self,
        arc_id: str,
        arc_type: EmotionalArcType,
        intensity: int,
        start_chapter: int,
        end_chapter: int,
        description: str = ""
    ) -> ArcSegment:
        """
        创建情感弧线段

        Args:
            arc_id: 弧线ID
            arc_type: 弧线类型
            intensity: 强度
            start_chapter: 起始章节
            end_chapter: 结束章节
            description: 描述

        Returns:
            ArcSegment实例
        """
        if not description:
            description = f"{arc_type.value} emotional journey from chapter {start_chapter} to {end_chapter}"

        return ArcSegment(
            segment_id=arc_id,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            arc_type=arc_type,
            intensity=intensity,
            description=description
        )

    def _calculate_tension_level(self, beats: List[Beat]) -> int:
        """计算紧张度 (0-100)"""
        if not beats:
            return 0

        total = 0
        for beat in beats:
            intensity = {
                BeatType.SETUP: 20,
                BeatType.INCITING: 40,
                BeatType.RISING: 60,
                BeatType.TWIST: 80,
                BeatType.CLIIMAX: 95,
                BeatType.RESOLUTION: 30,
            }
            total += intensity.get(beat.beat_type, 50)

        return int(total / len(beats))

    def _get_emotional_tone(self, beat_type: BeatType) -> str:
        """获取节拍的情感基调"""
        tones = {
            BeatType.SETUP: "平静",
            BeatType.INCITING: "惊讶",
            BeatType.RISING: "紧张",
            BeatType.TWIST: "震惊",
            BeatType.CLIIMAX: "激动",
            BeatType.RESOLUTION: "平静",
        }
        return tones.get(beat_type, "中性")

    def _extract_param(self, content: str, param: str, default: str = "") -> str:
        """从内容提取参数"""
        pattern = f"{param}="
        if pattern in content:
            try:
                start = content.index(pattern) + len(pattern)
                end = start
                while end < len(content) and content[end] not in " ,;":
                    end += 1
                return content[start:end]
            except ValueError:
                return default
        return default

    def get_summary(self, chapter_id: str) -> Optional[ChapterSummary]:
        """获取章节摘要"""
        return self._chapter_summaries.get(chapter_id)

    def get_all_summaries(self) -> Dict[str, ChapterSummary]:
        """获取所有摘要"""
        return self._chapter_summaries

    def get_emotional_arc(self, arc_id: str) -> Optional[ArcSegment]:
        """获取情感弧线"""
        return self._emotional_arcs.get(arc_id)

    def get_beat_library(self) -> Dict[str, List[Beat]]:
        """获取节拍库"""
        return self._beat_library

    def export_summaries(self) -> Dict[str, Any]:
        """导出所有摘要为JSON"""
        return {
            "chapter_summaries": {
                k: v.to_dict() for k, v in self._chapter_summaries.items()
            },
            "emotional_arcs": {
                k: v.to_dict() for k, v in self._emotional_arcs.items()
            },
            "statistics": {
                "total_chapters": self._total_chapters_generated,
                "total_beats": self._total_beats_generated
            }
        }

    def reset(self) -> None:
        """重置智能体"""
        self._chapter_summaries.clear()
        self._emotional_arcs.clear()
        self._beat_library.clear()
        self._sequence_library.clear()
        self._total_chapters_generated = 0
        self._total_beats_generated = 0
