"""
OutlinePlannerAgent - 大纲规划智能体

@file: agents/outline_planner.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 三幕结构/卷-章规划/DAG构建
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .base import BaseAgent, AgentConfig, Message, MessageType
from ai_novels.persistence import get_persistence_manager
from ai_novels.persistence.agent_persist import OutlinePersistence


class OutlinePhase(Enum):
    """大纲阶段"""
    INITIALIZATION = "initialization"
    STRUCTURE = "structure"
    CHAPTERS = "chapters"
    PLOT_POINTS = "plot_points"
    CHARACTER_ARCS = "character_arcs"
    COMPLETED = "completed"


@dataclass
class Act:
    """故事幕结构"""
    number: int
    title: str
    purpose: str
    chapter_range: range
    key_events: List[str] = field(default_factory=list)


@dataclass
class Chapter:
    """章节结构"""
    number: int
    title: str
    word_count_target: int
    perspective: str
    points_of_interest: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)


@dataclass
class Outline:
    """完整大纲"""
    title: str
    genre: str
    theme: str
    acts: List[Act] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    plot_points: Dict[str, str] = field(default_factory=dict)
    character_arcs: Dict[str, List[str]] = field(default_factory=dict)
    world_elements: List[str] = field(default_factory=list)


class OutlinePlannerAgent(BaseAgent):
    """
    大纲规划智能体

    核心功能：
    - 三幕结构规划
    - 卷-章结构设计
    - 剧情点序列生成
    - 角色弧线规划
    - DAG节点构建
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="outline_planner",
                description="Novel outline planning",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=16384
            )
        super().__init__(config)

        self._current_phase = OutlinePhase.INITIALIZATION
        self._current_outline: Optional[Outline] = None
        self._config_context: Dict[str, Any] = {}

    def process(self, message: Message) -> Message:
        """处理消息 - 大纲规划"""
        content = str(message.content).lower()

        if "plan" in content or "create" in content or "outline" in content:
            return self._handle_plan_request(message)
        elif "structure" in content:
            return self._handle_structure_request(message)
        elif "chapter" in content:
            return self._handle_chapter_request(message)
        elif "plot" in content or "beat" in content:
            return self._handle_plot_request(message)
        elif "status" in content:
            return self._handle_status_request(message)
        else:
            return self._handle_plan_request(message)

    def _get_task_id_from_message(self, message: Message) -> str:
        """从消息中获取任务ID"""
        # 优先级1: metadata
        if hasattr(message, 'metadata') and message.metadata:
            tid = message.metadata.get("task_id", "")
            if tid:
                return tid
        # 优先级2: 从消息文本解析 ("Task ID: xxx" 或 "task_id=xxx")
        content = str(message.content) if hasattr(message, 'content') else ""
        for marker in ("Task ID: ", "task_id="):
            idx = content.find(marker)
            if idx >= 0:
                start = idx + len(marker)
                end = start
                while end < len(content) and content[end] not in " \t\r\n,;":
                    end += 1
                tid = content[start:end]
                if tid:
                    return tid
        # 优先级3: 随机fallback
        return f"task_{uuid.uuid4().hex[:8]}"

    def _handle_plan_request(self, message: Message) -> Message:
        """处理大纲规划请求"""
        self._current_phase = OutlinePhase.INITIALIZATION
        task_id = self._get_task_id_from_message(message)

        # 解析配置
        config = self._parse_config(str(message.content))

        # 保存上下文
        self._config_context = config

        # 阶段1: 初始化
        self._current_phase = OutlinePhase.INITIALIZATION
        self._initialize_outline(config)

        # 阶段2: 结构规划
        self._current_phase = OutlinePhase.STRUCTURE
        self._plan_structure(config)

        # 阶段3: 章节规划
        self._current_phase = OutlinePhase.CHAPTERS
        self._plan_chapters(config)

        # 阶段4: 剧情点规划
        self._current_phase = OutlinePhase.PLOT_POINTS
        self._plan_plot_points(config)

        # 阶段5: 角色弧线规划
        self._current_phase = OutlinePhase.CHARACTER_ARCS
        self._plan_character_arcs(config)

        # 完成
        self._current_phase = OutlinePhase.COMPLETED

        # 获取持久化管理器
        pm = get_persistence_manager()

        # 持久化大纲
        if pm.mongodb_client and self._current_outline:
            for chapter in self._current_outline.chapters:
                chapter_num = chapter.number
                outline_data = {
                    "title": chapter.title,
                    "word_count_target": chapter.word_count_target,
                    "perspective": chapter.perspective,
                    "points_of_interest": chapter.points_of_interest,
                    "foreshadowing": chapter.foreshadowing,
                    "structure": {
                        "acts": [
                            {
                                "number": act.number,
                                "title": act.title,
                                "purpose": act.purpose,
                                "chapter_range": list(act.chapter_range)
                            }
                            for act in self._current_outline.acts
                        ] if self._current_outline.acts else []
                    }
                }
                OutlinePersistence.save_outline(pm, task_id, chapter_num, outline_data)

        return self._create_message(
            self._format_outline_result(),
            MessageType.TEXT,
            phase=self._current_phase.value,
            chapters_planned=len(self._current_outline.chapters) if self._current_outline else 0,
            task_id=task_id
        )

    def _handle_structure_request(self, message: Message) -> Message:
        """处理结构请求"""
        if not self._current_outline:
            return self._create_message(
                "No outline created yet. Use 'plan outline' first.",
                MessageType.TEXT
            )

        structure = self._format_structure()
        return self._create_message(
            structure,
            MessageType.TEXT,
            structure_type="three_act"
        )

    def _handle_chapter_request(self, message: Message) -> Message:
        """处理章节请求"""
        if not self._current_outline:
            return self._create_message(
                "No outline created yet. Use 'plan outline' first.",
                MessageType.TEXT
            )

        chapters = self._format_chapters()
        return self._create_message(
            chapters,
            MessageType.TEXT,
            chapter_count=len(self._current_outline.chapters)
        )

    def _handle_plot_request(self, message: Message) -> Message:
        """处理剧情点请求"""
        if not self._current_outline:
            return self._create_message(
                "No outline created yet. Use 'plan outline' first.",
                MessageType.TEXT
            )

        plot_points = json.dumps(self._current_outline.plot_points, indent=2, ensure_ascii=False)
        return self._create_message(
            f"Key Plot Points:\n```json\n{plot_points}\n```",
            MessageType.TEXT
        )

    def _handle_status_request(self, message: Message) -> Message:
        """处理状态请求"""
        if not self._current_outline:
            return self._create_message(
                "No outline created yet.",
                MessageType.TEXT
            )

        status = (
            f"Outline Phase: {self._current_phase.value}\n"
            f"Title: {self._current_outline.title}\n"
            f"Genre: {self._current_outline.genre}\n"
            f"Acts: {len(self._current_outline.acts)}\n"
            f"Chapters: {len(self._current_outline.chapters)}\n"
            f"Plot Points: {len(self._current_outline.plot_points)}\n"
            f"Characters with Arcs: {len(self._current_outline.character_arcs)}"
        )
        return self._create_message(
            status,
            MessageType.TEXT,
            phase=self._current_phase.value
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Outline Planner available commands:\n"
            "- 'plan outline [config]' - 创建大纲\n"
            "- 'structure' - 查看结构\n"
            "- 'chapters' - 查看章节列表\n"
            "- 'plot' - 查看剧情点\n"
            "- 'status' - 查看状态"
        )
        return self._create_message(response)

    def _parse_config(self, content: str) -> Dict[str, Any]:
        """解析配置"""
        config = {
            "title": None,
            "genre": "fantasy",
            "max_chapters": 50,
            "word_count_per_chapter": 3000,
            "target_audience": "adult",
            "tone": "epic",
            "pace": "medium",
            "language": "zh-CN"
        }

        # 尝试解析JSON
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                parsed = json.loads(json_str)
                for key in config:
                    if key in parsed:
                        config[key] = parsed[key]
                return config
        except json.JSONDecodeError:
            pass

        # 从 Task Context 文本中解析 "Key: Value" 格式
        # Coordinator 发送的格式: "Chapters: 5\nWord Count per Chapter: 2000\nGenre: fantasy\n..."
        for line in content.split('\n'):
            line = line.strip()
            if ':' not in line:
                continue
            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip()
            if not value:
                continue
            if key == 'chapters' and value.isdigit():
                config['max_chapters'] = int(value)
            elif key in ('word count per chapter', 'word_count_per_chapter') and value.replace('.', '').isdigit():
                config['word_count_per_chapter'] = int(float(value))
            elif key == 'genre':
                config['genre'] = value.lower().strip()
            elif key == 'style':
                config['style'] = value
            elif key in ('target audience', 'target_audience'):
                config['target_audience'] = value
            elif key == 'title':
                config['title'] = value

        # 简单关键词解析（作为 Task Context 解析的补充）
        content_lower = content.lower()
        if " long" in content_lower or "长篇" in content:
            config["max_chapters"] = 100
        elif " short" in content_lower or "短篇" in content:
            config["max_chapters"] = 10

        return config

    def _initialize_outline(self, config: Dict[str, Any]) -> None:
        """初始化大纲"""
        self._current_outline = Outline(
            title=config.get("title", "Untitled Novel"),
            genre=config.get("genre", "fantasy"),
            theme=config.get("theme", "A journey of self-discovery"),
            acts=[],
            chapters=[],
            plot_points={},
            character_arcs={},
            world_elements=[]
        )

    def _plan_structure(self, config: Dict[str, Any]) -> None:
        """规划三幕结构"""
        max_chapters = config.get("max_chapters", 50)

        # 计算各幕页数
        act_1_end = max(3, max_chapters // 10)
        act_2_end = max(int(max_chapters * 0.75), act_1_end + 5)

        lang = config.get("language", "zh-CN")
        if lang.startswith("zh"):
            act_titles = ["开端", "发展", "高潮"]
            act_purposes = ["世界观与角色引入，激励事件", "矛盾升级、障碍与转折", "高潮与结局"]
            act_events = [["引入", "激励事件"], ["第一转折点", "中点", "第二转折点"], ["高潮", "结局"]]
        else:
            act_titles = ["Inciting Incident", "Confrontation", "Resolution"]
            act_purposes = ["Introduction of world, characters, and inciting incident",
                           "Rising action, obstacles, midpoint reversal",
                           "Climax and resolution"]
            act_events = [["Introduction", "Inciting Incident"],
                         ["First Plot Point", "Midpoint", "Second Plot Point"],
                         ["Climax", "Resolution"]]

        self._current_outline.acts = [
            Act(
                number=1,
                title=act_titles[0],
                purpose=act_purposes[0],
                chapter_range=range(1, act_1_end + 1),
                key_events=act_events[0]
            ),
            Act(
                number=2,
                title=act_titles[1],
                purpose=act_purposes[1],
                chapter_range=range(act_1_end + 1, act_2_end + 1),
                key_events=act_events[1]
            ),
            Act(
                number=3,
                title=act_titles[2],
                purpose=act_purposes[2],
                chapter_range=range(act_2_end + 1, max_chapters + 1),
                key_events=act_events[2]
            )
        ]

    def _plan_chapters(self, config: Dict[str, Any]) -> None:
        """规划章节"""
        max_chapters = config.get("max_chapters", 50)
        target_word_count = config.get("word_count_per_chapter", 3000)

        # 生成章节标题和要点
        titles = self._generate_chapter_titles(max_chapters, config.get("genre", "fantasy"), config.get("language", "zh-CN"))

        for i in range(1, max_chapters + 1):
            chapter = Chapter(
                number=i,
                title=titles.get(i, f"Chapter {i}"),
                word_count_target=target_word_count,
                perspective="third_person_limited",
                points_of_interest=[f"Key event in chapter {i}"],
                foreshadowing=[f"Hint about future events in chapter {i}"]
            )
            self._current_outline.chapters.append(chapter)

    def _plan_plot_points(self, config: Dict[str, Any]) -> None:
        """规划剧情点"""
        max_chapters = config.get("max_chapters", 50)
        act_1_end = max(3, max_chapters // 10)
        act_2_end = max(int(max_chapters * 0.75), act_1_end + 5)

        self._current_outline.plot_points = {
            "inciting_incident": f"Chapter {max(1, act_1_end // 2)}: The event that sets the story in motion",
            "first_plot_point": f"Chapter {act_1_end}: The protagonist commits to the journey",
            "good_turn_1": f"Chapter {act_1_end // 2 + 3}: First major success or revelation",
            "midpoint": f"Chapter {max(15, max_chapters // 2)}: Major revelation or reversal",
            "bad_turn_1": f"Chapter {max(15, max_chapters // 2) + 5}: Major setback",
            "second_plot_point": f"Chapter {act_2_end}: New plan or final push",
            "climax": f"Chapter {max_chapters}: Final confrontation",
            "resolution": f"Chapter {max_chapters}: Epilogue and consequences"
        }

    def _plan_character_arcs(self, config: Dict[str, Any]) -> None:
        """规划角色弧线"""
        # 默认主角弧线
        self._current_outline.character_arcs = {
            "protagonist": [
                "Initial state - Normal world",
                "Call to adventure",
                "Refusal of the call",
                "Meeting the mentor",
                "Crossing the threshold",
                "Tests, allies, enemies",
                "Approach to the inmost cave",
                "Ordeal ( near death experience)",
                "Reward (seizing the sword)",
                "The road back",
                "Resurrection",
                "Return with the elixir"
            ]
        }

    def _generate_chapter_titles(self, count: int, genre: str, language: str = "zh-CN") -> Dict[int, str]:
        """生成章节标题"""
        titles = {}
        import random
        random.seed(42)

        if language and language.startswith("zh"):
            # 中文标题
            cn_templates = [
                "风云起", "暗流涌", "新篇章", "遇故人",
                "迷雾中", "转折点", "危机现", "寻真相",
                "决战前", "终章"
            ]
            for i in range(1, count + 1):
                tpl = cn_templates[(i - 1) % len(cn_templates)]
                titles[i] = tpl
            return titles

        # 英文标题
        if genre == "fantasy":
            title_templates = [
                "A New Beginning", "The Journey Begins", "The Discovery",
                "Meeting the Unknown", "The Challenge", "A Fork in the Road",
                "The Revelation", "Memories", "The Warning",
                "The Final Battle"
            ]
        elif genre == "romance":
            title_templates = [
                "A New Encounter", "First Impressions", "Growing Closer",
                "The Confession", "Heartbreak", "A Glimmer of Hope",
                "The Reunion", "Love Tested", "The Final Choice",
                "Happy Ending"
            ]
        else:
            title_templates = [
                "A New Beginning", "The Unexpected", "A Turning Point",
                "The Discovery", "The Confrontation", "The Aftermath",
                "A New Development", "The Revelation", "Approaching the End",
                "The Final Chapter"
            ]

        for i in range(1, count + 1):
            template = title_templates[(i - 1) % len(title_templates)]
            titles[i] = template

        return titles

    def _format_outline_result(self) -> str:
        """格式化大纲结果"""
        if not self._current_outline:
            return "No outline generated."

        lines = [f"=== Outline for '{self._current_outline.title}' ===", ""]

        # 概述
        lines.append(f"Genre: {self._current_outline.genre}")
        lines.append(f"Theme: {self._current_outline.theme}")
        lines.append("")

        # 三幕结构
        lines.append("Three-Act Structure:")
        for act in self._current_outline.acts:
            lines.append(f"  Act {act.number}: {act.title}")
            lines.append(f"    Chapters: {act.chapter_range.start} - {act.chapter_range.stop - 1}")
            lines.append(f"    Purpose: {act.purpose}")
            lines.append(f"    Key Events: {', '.join(act.key_events)}")
        lines.append("")

        # 剧情点
        lines.append("Key Plot Points:")
        for point, description in self._current_outline.plot_points.items():
            lines.append(f"  • {point}: {description}")
        lines.append("")

        # 章节列表
        lines.append(f"Chapters ({len(self._current_outline.chapters)}):")
        for chapter in self._current_outline.chapters[:10]:
            lines.append(f"  {chapter.number}. {chapter.title}")
        if len(self._current_outline.chapters) > 10:
            lines.append(f"  ... and {len(self._current_outline.chapters) - 10} more chapters")
        lines.append("")

        # 角色弧线
        lines.append("Character Arcs:")
        for character, arc in self._current_outline.character_arcs.items():
            lines.append(f"  {character}: {len(arc)} growth stages")
        lines.append("")

        return "\n".join(lines)

    def _format_structure(self) -> str:
        """格式化结构"""
        if not self._current_outline:
            return "No outline available."

        return (
            f"Three-Act Structure:\n"
            f"Act 1 (Introduction): Chapters 1-{self._current_outline.acts[0].chapter_range.stop - 1}\n"
            f"  - Purpose: {self._current_outline.acts[0].purpose}\n"
            f"  - Key Events: {', '.join(self._current_outline.acts[0].key_events)}\n"
            f"Act 2 (Confrontation): Chapters {self._current_outline.acts[0].chapter_range.stop}-{self._current_outline.acts[1].chapter_range.stop - 1}\n"
            f"  - Purpose: {self._current_outline.acts[1].purpose}\n"
            f"  - Key Events: {', '.join(self._current_outline.acts[1].key_events)}\n"
            f"Act 3 (Resolution): Chapters {self._current_outline.acts[1].chapter_range.stop}-{self._current_outline.acts[2].chapter_range.stop - 1}\n"
            f"  - Purpose: {self._current_outline.acts[2].purpose}\n"
            f"  - Key Events: {', '.join(self._current_outline.acts[2].key_events)}\n"
        )

    def _format_chapters(self) -> str:
        """格式化章节"""
        if not self._current_outline:
            return "No outline available."

        lines = []
        for chapter in self._current_outline.chapters:
            lines.append(f"Chapter {chapter.number}: {chapter.title}")
            lines.append(f"  Target Word Count: {chapter.word_count_target}")
            lines.append(f"  Perspective: {chapter.perspective}")

        return "\n".join(lines)

    def get_outline(self) -> Optional[Outline]:
        """获取完整大纲"""
        return self._current_outline

    def get_chapter(self, number: int) -> Optional[Chapter]:
        """获取特定章节"""
        for chapter in self._current_outline.chapters if self._current_outline else []:
            if chapter.number == number:
                return chapter
        return None

    def reset(self) -> None:
        """重置大纲规划器"""
        self._current_phase = OutlinePhase.INITIALIZATION
        self._current_outline = None
        self._config_context = {}
