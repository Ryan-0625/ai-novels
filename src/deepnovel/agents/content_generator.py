"""
ContentGeneratorAgent - 内容生成智能体

@file: agents/content_generator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 上下文组装、混沌事件注入、风格约束
"""

import time
import json
import random
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from datetime import datetime

from .base import BaseAgent, AgentConfig, Message, MessageType
from .constants import (
    DEFAULT_WORDS_PER_CHAPTER,
    DEFAULT_GENRE,
)
from deepnovel.persistence import get_persistence_manager
from deepnovel.persistence.agent_persist import ChapterPersistence
from deepnovel.config import settings


class WritingMode(Enum):
    """写作模式"""
    FAST = "fast"        # 快速写作
    BALANCED = "balanced"  # 平衡模式
    DELIBERATE = "deliberate" # 精细写作
    POETIC = "poetic"    # 诗意模式


class StyleConstraint(Enum):
    """风格约束类型"""
    DIALOGUE = "dialogue"       # 对话风格
    NARRATIVE = "narrative"     # 叙述风格
    DESCRIPTION = "description" # 描写风格
    ACTION = "action"           # 动作场景
    INTERNAL = "internal"       # 内心独白


@dataclass
class ContentContext:
    """内容上下文"""
    chapter_id: str
    outline: str
    beats: List[Dict[str, Any]]
    characters: List[Dict[str, Any]]
    setting: Dict[str, Any]
    tone: str
    key_events: List[str]
    genre: str = "奇幻"  # 添加genre字段，默认为奇幻

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "outline": self.outline,
            "beats": self.beats,
            "characters": self.characters,
            "setting": self.setting,
            "tone": self.tone,
            "key_events": self.key_events,
            "genre": self.genre
        }


@dataclass
class StyleConfig:
    """风格配置"""
    vocabulary_level: int  # 1-10
    sentence_length: str   # short, medium, long, variable
    narrative_distance: str # close, moderate, distant
    metaphor_frequency: int  # 0-10
    pacing: str  # fast, normal, slow

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vocabulary_level": self.vocabulary_level,
            "sentence_length": self.sentence_length,
            "narrative_distance": self.narrative_distance,
            "metaphor_frequency": self.metaphor_frequency,
            "pacing": self.pacing
        }


@dataclass
class GeneratedContent:
    """生成的内容"""
    content_id: str
    chapter_id: str
    text: str
    sections: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    style_applied: StyleConfig
    timestamps: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_id": self.content_id,
            "chapter_id": self.chapter_id,
            "text": self.text,
            "sections": self.sections,
            "statistics": self.statistics,
            "style_applied": self.style_applied.to_dict(),
            "timestamps": self.timestamps
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ChaosEvent:
    """混沌事件"""
    event_id: str
    event_type: str
    description: str
    impact_level: int  # 0-100
    affected_characters: List[str]
    probability: float
    triggered: bool = False
    effect: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "description": self.description,
            "impact_level": self.impact_level,
            "affected_characters": self.affected_characters,
            "probability": self.probability,
            "triggered": self.triggered,
            "effect": self.effect
        }


class ContentGeneratorAgent(BaseAgent):
    """
    内容生成智能体

    核心功能：
    - 上下文组装与分析
    - 混沌事件注入与管理
    - 风格约束应用
    - 分段生成与整合
    - 内容统计与优化
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="content_generator",
                description="Content generation with context and style",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=8192
            )
        super().__init__(config)

        # 生成内容存储
        self._generated_contents: Dict[str, GeneratedContent] = {}
        self._content_history: deque = deque(maxlen=100)

        # 混沌事件库
        self._chaos_library: Dict[str, ChaosEvent] = {}
        self._active_chaos_events: List[str] = []

        # 风格配置
        self._default_style = StyleConfig(
            vocabulary_level=5,
            sentence_length="variable",
            narrative_distance="moderate",
            metaphor_frequency=3,
            pacing="normal"
        )

        # 上下文模板
        self._context_templates: Dict[str, str] = {}

        # 统计
        self._total_words_generated = 0
        self._total_sections_generated = 0
        self._total_chaos_injected = 0

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "generate" in content and ("content" in content or "chapter" in content):
            return self._handle_generate_content(message)
        elif "style" in content or "风格" in content:
            return self._handle_style_command(message)
        elif "chaos" in content or "混沌" in content:
            return self._handle_chaos_command(message)
        elif "context" in content or "上下文" in content:
            return self._handle_context_command(message)
        elif "history" in content or "history" in content:
            return self._handle_history_command(message)

        return self._handle_generate_content(message)

    def _get_task_id_from_message(self, message: Message) -> str:
        """从消息中获取任务ID"""
        if hasattr(message, 'metadata') and message.metadata:
            return message.metadata.get("task_id", f"task_{uuid.uuid4().hex[:8]}")
        return f"task_{uuid.uuid4().hex[:8]}"

    def _handle_generate_content(self, message: Message) -> Message:
        """处理生成内容请求"""
        content = str(message.content)
        task_id = self._get_task_id_from_message(message)

        chapter_id = self._extract_param(content, "chapter_id", "chapter_1")
        outline = self._extract_param(content, "outline", "")
        beats_str = self._extract_param(content, "beats", "")
        target_words = int(self._extract_param(content, "words", "2000"))
        writing_mode = self._extract_param(content, "mode", "balanced")

        # 解析节拍
        beats = self._parse_beats(beats_str)

        # 解析上下文
        context = ContentContext(
            chapter_id=chapter_id,
            outline=outline,
            beats=beats,
            characters=[],
            setting={},
            tone="neutral",
            key_events=[]
        )

        # 生成内容
        result = self._generate_content(
            context=context,
            target_words=target_words,
            writing_mode=WritingMode(writing_mode.lower())
        )

        self._generated_contents[chapter_id] = result
        self._content_history.append(result)
        self._total_words_generated += result.statistics.get("word_count", 0)
        self._total_sections_generated += len(result.sections)

        # === 持久化到数据库 ===
        pm = get_persistence_manager()
        if pm.mongodb_client:
            # 提取章节号
            chapter_num = int(chapter_id.split('_')[-1]) if chapter_id.replace('_', '').isdigit() else 1
            ChapterPersistence.save_chapter(
                pm, task_id, chapter_num, context.outline or f"Chapter {chapter_num}",
                result.text, result.statistics.get("word_count", 0),
                {"generated_at": datetime.now().isoformat()}
            )

        response = f"Generated Content for {chapter_id}:\n\n"
        response += f"Word Count: {result.statistics.get('word_count', 0)}\n"
        response += f"Sections: {len(result.sections)}\n"
        response += f"Writing Mode: {writing_mode}\n\n"

        # 显示前几个段落
        response += "First 3 sections:\n"
        for i, section in enumerate(result.sections[:3]):
            preview = section.get("text", "")[:100]
            response += f"  [{i+1}] {preview}...\n"

        # 混沌事件统计
        response += f"\nChaos Events Injected: {result.statistics.get('chaos_events', 0)}\n"
        response += f"Generation Time: {result.timestamps.get('total_time', 0):.2f}s\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            chapter_id=chapter_id,
            word_count=result.statistics.get("word_count", 0),
            style_mode=writing_mode,
            task_id=task_id
        )

    def _handle_style_command(self, message: Message) -> Message:
        """处理风格命令"""
        content = str(message.content)

        content_lower = content.lower()

        # 注意: "preset" 包含 "set" 子串，必须先检查 preset
        if "preset" in content_lower:
            preset = self._extract_param(content, "preset", "balanced")
            return self._set_preset_style(preset)

        if "set" in content_lower:
            vocab = int(self._extract_param(content, "vocabulary", "5"))
            sentence = self._extract_param(content, "sentence", "variable")
            distance = self._extract_param(content, "distance", "moderate")
            metaphor = int(self._extract_param(content, "metaphor", "3"))
            pacing = self._extract_param(content, "pacing", "normal")

            style = StyleConfig(
                vocabulary_level=vocab,
                sentence_length=sentence,
                narrative_distance=distance,
                metaphor_frequency=metaphor,
                pacing=pacing
            )

            self._default_style = style

            response = "Style Config Updated:\n\n"
            response += f"Vocabulary: {style.vocabulary_level}\n"
            response += f"Sentence Length: {style.sentence_length}\n"
            response += f"Narrative Distance: {style.narrative_distance}\n"
            response += f"Metaphor Frequency: {style.metaphor_frequency}\n"
            response += f"Pacing: {style.pacing}\n"

            return self._create_message(response, MessageType.TEXT)

        if "show" in content_lower or "current" in content_lower:
            style = self._default_style
            response = "Current Style Config:\n\n"
            response += f"Vocabulary: {style.vocabulary_level}\n"
            response += f"Sentence Length: {style.sentence_length}\n"
            response += f"Narrative Distance: {style.narrative_distance}\n"
            response += f"Metaphor Frequency: {style.metaphor_frequency}\n"
            response += f"Pacing: {style.pacing}\n"

            return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_chaos_command(self, message: Message) -> Message:
        """处理混沌命令"""
        content = str(message.content)

        if "add" in content or "create" in content:
            event_id = self._extract_param(content, "event_id", "chaos_001")
            event_type = self._extract_param(content, "type", "subtle")
            description = self._extract_param(content, "description", "")
            impact = int(self._extract_param(content, "impact", "30"))
            characters = self._extract_param(content, "characters", "Protagonist").split(",")

            chaos_event = ChaosEvent(
                event_id=event_id,
                event_type=event_type,
                description=description or self._generate_chaos_description(event_type),
                impact_level=impact,
                affected_characters=characters,
                probability=impact / 100.0
            )

            self._chaos_library[event_id] = chaos_event

            response = f"Added Chaos Event: {event_id}\n"
            response += f"Type: {event_type}\n"
            response += f"Impact: {impact}\n"
            response += f"description: {description}\n"

            return self._create_message(response, MessageType.TEXT)

        elif "inject" in content:
            chapter_id = self._extract_param(content, "chapter_id", "chapter_1")
            max_events = int(self._extract_param(content, "max", "3"))

            events = self._inject_chaos_events(chapter_id, max_events)

            response = f"Injected Chaos Events for {chapter_id}:\n\n"
            for event_id in events:
                event = self._chaos_library.get(event_id)
                if event:
                    response += f"- {event.event_id}: {event.description[:50]}...\n"
                    response += f"  Impact: {event.impact_level}, Characters: {', '.join(event.affected_characters)}\n\n"

            self._total_chaos_injected += len(events)

            return self._create_message(
                response,
                MessageType.TEXT,
                events_injected=len(events)
            )

        elif "library" in content:
            if not self._chaos_library:
                return self._create_message("Chaos library is empty.", MessageType.TEXT)

            response = "Chaos Library:\n\n"
            for event_id, event in list(self._chaos_library.items())[:20]:
                response += f"{event_id}: {event.event_type} (Impact: {event.impact_level})\n"

            return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_context_command(self, message: Message) -> Message:
        """处理上下文命令"""
        content = str(message.content)

        if "template" in content:
            if "add" in content or "create" in content:
                name = self._extract_param(content, "name", "default")
                template = self._extract_param(content, "template", "")
                self._context_templates[name] = template

                return self._create_message(f"Added context template: {name}", MessageType.TEXT)

            elif "list" in content:
                if not self._context_templates:
                    return self._create_message("No context templates.", MessageType.TEXT)

                response = "Context Templates:\n\n"
                for name, template in self._context_templates.items():
                    preview = template[:50] + "..." if len(template) > 50 else template
                    response += f"[{name}] {preview}\n\n"

                return self._create_message(response, MessageType.TEXT)

        elif "show" in content:
            chapter_id = self._extract_param(content, "chapter_id", "chapter_1")
            content = self._generated_contents.get(chapter_id)

            if content:
                response = f"Content Context for {chapter_id}:\n\n"
                response += f"Word Count: {content.statistics.get('word_count', 0)}\n"
                response += f"Sections: {len(content.sections)}\n"
                response += f"Style: {content.style_applied.to_dict()}\n"
                response += f"Chaos Events: {content.statistics.get('chaos_events', 0)}\n"
                return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_history_command(self, message: Message) -> Message:
        """处理历史命令"""
        content = str(message.content)

        if "list" in content:
            count = int(self._extract_param(content, "count", "10"))

            response = f"Last {count} Generated Contents:\n\n"
            for i, content in enumerate(list(self._content_history)[-count:], 1):
                response += f"{i}. {content.chapter_id}: {content.statistics.get('word_count', 0)} words, {len(content.sections)} sections\n"

            return self._create_message(response, MessageType.TEXT)

        elif "stats" in content:
            response = "Content Generation Statistics:\n\n"
            response += f"Total Words: {self._total_words_generated}\n"
            response += f"Total Sections: {self._total_sections_generated}\n"
            response += f"Total Chaos Events: {self._total_chaos_injected}\n"
            response += f"Content History: {len(self._content_history)} entries\n"
            response += f"Chaos Library: {len(self._chaos_library)} events\n"

            return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Content Generator Agent available commands:\n"
            "- 'generate content chapter_id=X outline=X beats=X words=X mode=X' - 生成内容\n"
            "- 'set style vocabulary=X sentence=X distance=X metaphor=X pacing=X' - 设置风格\n"
            "- 'show style' - 显示当前风格\n"
            "- 'set style preset=X' - 设置预设风格 (fast/balanced/deliberate/poetic)\n"
            "- 'add chaos event event_id=X type=X description=X impact=X' - 添加混沌事件\n"
            "- 'inject chaos chapter_id=X max=X' - 注入混沌事件\n"
            "- 'show chaos library' - 显示混沌事件库\n"
            "- 'add context template name=X template=X' - 添加上下文模板\n"
            "- 'show context templates' - 显示上下文模板\n"
            "- 'show content history' - 显示生成历史\n"
            "- 'show generation stats' - 显示统计信息"
        )
        return self._create_message(response)

    def _generate_content(
        self,
        context: ContentContext,
        target_words: int = 2000,
        writing_mode: WritingMode = WritingMode.BALANCED
    ) -> GeneratedContent:
        """
        生成内容

        Args:
            context: 内容上下文
            target_words: 目标字数
            writing_mode: 写作模式

        Returns:
            GeneratedContent实例
        """
        start_time = time.time()

        content_id = f"content_{context.chapter_id}_{int(start_time)}"

        # 调整风格基于写作模式
        style = self._apply_writing_mode(writing_mode, self._default_style)

        # 注入混沌事件
        chaos_events = self._inject_chaos_events(
            context.chapter_id,
            max(1, target_words // 500)
        )

        # 分段生成
        sections = []
        current_words = 0
        section_targets = self._calculate_section_targets(target_words, writing_mode)

        for i, section_target in enumerate(section_targets):
            section_text = self._generate_section(
                context=context,
                section_index=i,
                target_words=section_target,
                style=style,
                chaos_events=chaos_events
            )

            sections.append({
                "section_id": f"section_{i+1}",
                "text": section_text,
                "word_count": len(section_text.split()),
                "chaos_events": []
            })

            current_words += len(section_text.split())

        # 生成完整文本
        full_text = self._assemble_content(sections, context)

        # 统计
        end_time = time.time()

        content = GeneratedContent(
            content_id=content_id,
            chapter_id=context.chapter_id,
            text=full_text,
            sections=sections,
            statistics={
                "word_count": len(full_text.split()),
                "section_count": len(sections),
                "chaos_events": len(chaos_events),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            },
            style_applied=style,
            timestamps={
                "start": start_time,
                "total_time": end_time - start_time
            }
        )

        return content

    def _generate_section(
        self,
        context: ContentContext,
        section_index: int,
        target_words: int,
        style: StyleConfig,
        chaos_events: List[ChaosEvent]
    ) -> str:
        """生成单个段落"""
        # 基于风格和上下文生成内容
        section_templates = {
            StyleConstraint.DIALOGUE: self._generate_dialogue,
            StyleConstraint.NARRATIVE: self._generate_narrative,
            StyleConstraint.DESCRIPTION: self._generate_description,
            StyleConstraint.ACTION: self._generate_action,
            StyleConstraint.INTERNAL: self._generate_internal,
        }

        # 选择合适的模板
        constraint = StyleConstraint.NARRATIVE

        template_func = section_templates.get(constraint, self._generate_narrative)

        # 注入混沌事件影响
        chaos_influence = ""
        if chaos_events and section_index % (len(context.beats) // max(1, len(chaos_events))) == 0:
            event = random.choice(chaos_events)
            chaos_influence = f"\n[Chaos Event: {event.event_type}] {event.description}\n"

        section_text = template_func(context, style, target_words)

        return section_text + chaos_influence

    def _generate_dialogue(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int
    ) -> str:
        """生成对话"""
        return self._generate_based_on_context(
            context,
            style,
            target_words,
            prompt_type="dialogue"
        )

    def _generate_narrative(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int
    ) -> str:
        """生成叙述"""
        return self._generate_based_on_context(
            context,
            style,
            target_words,
            prompt_type="narrative"
        )

    def _generate_description(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int
    ) -> str:
        """生成描写"""
        return self._generate_based_on_context(
            context,
            style,
            target_words,
            prompt_type="description"
        )

    def _generate_action(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int
    ) -> str:
        """生成动作场景"""
        return self._generate_based_on_context(
            context,
            style,
            target_words,
            prompt_type="action"
        )

    def _generate_internal(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int
    ) -> str:
        """生成内心独白"""
        return self._generate_based_on_context(
            context,
            style,
            target_words,
            prompt_type="internal"
        )

    def _generate_based_on_context(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int,
        prompt_type: str = "narrative"
    ) -> str:
        """基于上下文生成内容 - 使用LLM"""

        # 构建LLM提示词
        llm_prompt = self._build_generation_prompt(context, style, target_words, prompt_type)

        # 直接使用LLM生成（不使用system prompt，完全依赖prompt本身）
        llm_response = self._generate_with_llm(llm_prompt, None)

        if llm_response:
            # 清理LLM响应
            return self._clean_generated_content(llm_response)

        raise RuntimeError(
            f"LLM generation failed for context={context.prompt_context[:50] if context.prompt_context else 'empty'}, "
            f"style={style.name}. No fallback available — LLM must return valid content."
        )

    def _build_generation_prompt(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int,
        prompt_type: str
    ) -> str:
        """构建生成提示词 - 使用语言配置"""
        # 获取语言配置
        lang_name = getattr(settings, "language_name", None) or "English"
        lang_code = getattr(settings, "language_code", None) or "en-US"

        # 构建上下文信息字符串
        context_info = self._build_context_info(context)

        # 根据语言构建不同的提示词
        if lang_code.startswith("zh"):
            # 中文提示词 - 简单直接的格式
            prompt = self._build_chinese_prompt(context, style, target_words, prompt_type, context_info)
        else:
            # 英文提示词（默认）
            prompt = self._build_english_prompt(context, style, target_words, prompt_type, context_info, lang_name)

        return prompt

    def _build_chinese_prompt(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int,
        prompt_type: str,
        context_info: str
    ) -> str:
        """构建中文提示词"""
        prompt = """你是一个专业的中文小说作家，必须100%使用简体中文创作。

【强制要求】语言指令
你必须100%使用简体中文撰写小说内容！这是绝对强制要求。

违反后果：
- 使用英文或其他语言会导致程序错误
- 你的输出将无法被系统正确处理
- 严重影响用户阅读体验

## 小说信息
体裁: {genre}
风格: {style}
目标字数: ~{target_words} 字

## 上下文信息
{context_info}

## 任务要求
请撰写引人入胜的{prompt_type}内容，必须：
1. 全文只允许使用简体中文
2. 使用中文标点符号（，。！？；：）
3. 禁止出现任何英文单词
4. 符合中文表达习惯
5. 匹配指定的风格和体裁
6. 推进故事情节发展
7. 字数控制在 {target_words} 字左右

## 输出要求
请直接输出小说内容正文，不要添加任何：
- 序言
- 说明文字
- Markdown格式
- 代码块标记
- 任何额外文本

现在开始创作：

"""
        return prompt.format(
            genre=context.genre or "奇幻",
            style=str(style.__dict__),
            target_words=target_words,
            context_info=context_info,
            prompt_type=prompt_type
        )

    def _build_english_prompt(
        self,
        context: ContentContext,
        style: StyleConfig,
        target_words: int,
        prompt_type: str,
        context_info: str,
        lang_name: str
    ) -> str:
        """构建英文提示词"""
        prompt = """## 【CRITICAL】Language Instruction

You must 100% write novel content in {lang_name}!

### Consequences of violating this instruction:
- If you use another language, it will cause program errors
- Your output will not be processed correctly by the system
- It will seriously affect subsequent user reading experience

### Language requirements (must be strictly followed):
1. Only {lang_name} is allowed throughout the text
2. All punctuation marks must be in {lang_name} punctuation (.,?!;:)
3. No English words, Pinyin or foreign characters are allowed
4. Keep {lang_name} expression smooth and natural
5. Use standard {lang_name} grammar and vocabulary

## Novel Information
Genre: {genre}
Style: {style}
Target word count: ~{target_words} words

## Context Information
{context_info}

## Task Requirements
Please write engaging {prompt_type} content that must:
1. Be written entirely in {lang_name}
2. Fit the {lang_name} expression habits
3. Match the specified style and genre
4. Advance the plot
5. Keep the word count around {target_words} words

## 【CRITICAL】Output Format Requirements
Please directly output the novel content itself, without adding any:
- Introduction
- Explanatory text
- Markdown format
- Code block markers
- Any extra text

The content you output will be presented directly to readers, please ensure 100% use of {lang_name}!"""

        return prompt.format(
            genre=context.genre or "fantasy",
            style=str(style.__dict__),
            target_words=target_words,
            context_info=context_info,
            prompt_type=prompt_type,
            lang_name=lang_name
        )

    def _build_context_info(self, context: ContentContext) -> str:
        """构建上下文信息字符串"""
        info_parts = []

        # 章节概要
        info_parts.append(f"### 章节概要")
        info_parts.append(context.outline)
        info_parts.append("")

        # 节拍信息
        if context.beats:
            info_parts.append("### 节拍分解")
            for beat in context.beats:
                info_parts.append(f"- {beat.get('description', 'N/A')}")
            info_parts.append("")

        # 角色信息
        if context.characters:
            info_parts.append("### 角色")
            for char in context.characters:
                char_name = char.get('name', 'N/A')
                role = char.get('role', 'N/A')
                info_parts.append(f"- {char_name} ({role})")
            info_parts.append("")

        # 环境设置
        if context.setting:
            info_parts.append("### 环境设置")
            setting_text = ", ".join(f"{k}: {v}" for k, v in context.setting.items())
            info_parts.append(setting_text)
            info_parts.append("")

        # 情感基调
        if context.tone:
            info_parts.append(f"### 情感基调: {context.tone}")
            info_parts.append("")

        return "\n".join(info_parts)

    def _clean_generated_content(self, content: str) -> str:
        """清理生成的内容"""
        # 移除可能的前缀标记
        prefixes = ["narrative:", "description:", "action:", "dialogue:", "internal:"]
        content_lower = content.lower().strip()
        for prefix in prefixes:
            if content_lower.startswith(prefix):
                content = content[len(prefix):].strip()
                break

        # 移除编号列表前缀 (1. , 1) , etc.
        import re
        content = re.sub(r'^\d+[\.\)]\s*', '', content.strip())

        return content.strip()

    def _apply_style_modifiers(
        self,
        text: str,
        style: StyleConfig,
        vocab_modifier: int,
        metaphor_modifier: int
    ) -> str:
        """应用风格修饰"""
        # 简化实现：基于风格调整文本长度和复杂度

        # 句子长度变化
        if style.sentence_length == "short":
            sentences = text.split(". ")
            text = ". ".join(s[:50] for s in sentences)
        elif style.sentence_length == "long":
            sentences = text.split(". ")
            combined = []
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    combined.append(sentences[i] + ". " + sentences[i+1])
                else:
                    combined.append(sentences[i])
            text = ". ".join(combined)

        # 隐喻频率
        metaphors = [
            " like a storm approaching",
            " as fragile as glass",
            " in the blink of an eye",
            " like a river flowing downstream"
        ]

        if metaphor_modifier > 5:
            for metaphor in metaphors[:min(metaphor_modifier, len(metaphors))]:
                if random.random() < 0.3:
                    text += metaphor

        return text

    def _assemble_content(
        self,
        sections: List[Dict[str, Any]],
        context: ContentContext
    ) -> str:
        """组装完整内容"""
        parts = []

        # 开头
        parts.append(f"Chapter {context.chapter_id.split('_')[-1]}: {context.outline[:30]}...")

        # 主体
        for section in sections:
            parts.append(section.get("text", ""))

        # 结尾过渡
        parts.append("\nTo be continued...")

        return "\n\n".join(parts)

    def _inject_chaos_events(
        self,
        chapter_id: str,
        max_events: int
    ) -> List[str]:
        """注入混沌事件"""
        available = [
            event_id for event_id in self._chaos_library.keys()
            if event_id not in self._active_chaos_events
        ]

        if not available:
            return []

        # 随机选择
        num_events = min(max_events, len(available))
        selected = random.sample(available, num_events)

        self._active_chaos_events.extend(selected)

        return selected

    def _generate_chaos_description(self, event_type: str) -> str:
        """生成混沌事件描述"""
        descriptions = {
            "subtle": "A minor discrepancy appears, hinting at larger issues.",
            "sudden": "Something unexpected disrupts the status quo immediately.",
            "gradual": "Subtle signs accumulate, building tension steadily.",
            "dramatic": "A dramatic event shockingly alters the course of action.",
            "mysterious": "An unexplained phenomenon raises new questions.",
        }
        return descriptions.get(event_type, descriptions["subtle"])

    def _apply_writing_mode(
        self,
        mode: WritingMode,
        base_style: StyleConfig
    ) -> StyleConfig:
        """应用写作模式到风格"""
        mode_settings = {
            WritingMode.FAST: StyleConfig(
                vocabulary_level=3,
                sentence_length="short",
                narrative_distance="distant",
                metaphor_frequency=1,
                pacing="fast"
            ),
            WritingMode.BALANCED: StyleConfig(
                vocabulary_level=5,
                sentence_length="variable",
                narrative_distance="moderate",
                metaphor_frequency=3,
                pacing="normal"
            ),
            WritingMode.DELIBERATE: StyleConfig(
                vocabulary_level=7,
                sentence_length="long",
                narrative_distance="close",
                metaphor_frequency=5,
                pacing="slow"
            ),
            WritingMode.POETIC: StyleConfig(
                vocabulary_level=8,
                sentence_length="variable",
                narrative_distance="close",
                metaphor_frequency=8,
                pacing="slow"
            ),
        }

        setting = mode_settings.get(mode, mode_settings[WritingMode.BALANCED])

        # 基于基础风格调整
        return StyleConfig(
            vocabulary_level=base_style.vocabulary_level,
            sentence_length=setting.sentence_length,
            narrative_distance=setting.narrative_distance,
            metaphor_frequency=setting.metaphor_frequency,
            pacing=setting.pacing
        )

    def _calculate_section_targets(
        self,
        total_words: int,
        mode: WritingMode
    ) -> List[int]:
        """计算段落目标字数"""
        # 根据模式计算段落数
        if mode == WritingMode.FAST:
            num_sections = max(3, total_words // 500)
        elif mode == WritingMode.DELIBERATE:
            num_sections = max(5, total_words // 300)
        else:
            num_sections = max(4, total_words // 400)

        base_section_size = total_words // num_sections

        return [base_section_size] * (num_sections - 1) + [total_words - base_section_size * (num_sections - 1)]

    def _set_preset_style(self, preset: str) -> Message:
        """设置预设风格"""
        presets = {
            "fast": StyleConfig(3, "short", "distant", 1, "fast"),
            "balanced": StyleConfig(5, "variable", "moderate", 3, "normal"),
            "deliberate": StyleConfig(7, "long", "close", 5, "slow"),
            "poetic": StyleConfig(8, "variable", "close", 8, "slow"),
        }

        if preset in presets:
            self._default_style = presets[preset]
            return self._create_message(f"Style set to preset: {preset}", MessageType.TEXT)

        return self._create_message(f"Unknown preset: {preset}", MessageType.TEXT)

    def _parse_beats(self, beats_str: str) -> List[Dict[str, Any]]:
        """解析节拍字符串"""
        if not beats_str:
            return []

        # 简化实现
        beats = []
        for i, beat in enumerate(beats_str.split(";")):
            beats.append({
                "beat_id": f"beat_{i+1}",
                "description": beat.strip(),
                "type": "narrative"
            })
        return beats

    def _generate_chaos_event(self, event_type: str, impact: int) -> ChaosEvent:
        """生成混沌事件"""
        self._last_chaos_id = getattr(self, '_last_chaos_id', 0) + 1
        event_id = f"chaos_{self._last_chaos_id:04d}"

        return ChaosEvent(
            event_id=event_id,
            event_type=event_type,
            description=self._generate_chaos_description(event_type),
            impact_level=impact,
            affected_characters=["Protagonist"],
            probability=impact / 100.0
        )

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

    def generate_content(
        self,
        chapter_id: str,
        outline: str,
        target_words: int = DEFAULT_WORDS_PER_CHAPTER,
        writing_mode: str = "balanced",
        beats: List[Dict[str, Any]] = None,
        characters: List[Dict[str, Any]] = None,
        setting: Dict[str, Any] = None
    ) -> Optional[GeneratedContent]:
        """生成内容（外部接口）"""
        try:
            context = ContentContext(
                chapter_id=chapter_id,
                outline=outline,
                beats=beats or [],
                characters=characters or [],
                setting=setting or {},
                tone="neutral",
                key_events=[]
            )

            content = self._generate_content(
                context=context,
                target_words=target_words,
                writing_mode=WritingMode(writing_mode.lower())
            )

            self._generated_contents[chapter_id] = content
            self._content_history.append(content)

            return content
        except Exception:
            return None

    def inject_chaos(self, chapter_id: str, max_events: int = 3) -> List[str]:
        """注入混沌事件（外部接口）"""
        return self._inject_chaos_events(chapter_id, max_events)

    def set_style(
        self,
        vocabulary_level: int = 5,
        sentence_length: str = "variable",
        narrative_distance: str = "moderate",
        metaphor_frequency: int = 3,
        pacing: str = "normal"
    ) -> StyleConfig:
        """设置风格（外部接口）"""
        self._default_style = StyleConfig(
            vocabulary_level=vocabulary_level,
            sentence_length=sentence_length,
            narrative_distance=narrative_distance,
            metaphor_frequency=metaphor_frequency,
            pacing=pacing
        )
        return self._default_style

    def get_content(self, chapter_id: str) -> Optional[GeneratedContent]:
        """获取生成的内容"""
        return self._generated_contents.get(chapter_id)

    def get_all_contents(self) -> Dict[str, GeneratedContent]:
        """获取所有生成的内容"""
        return self._generated_contents

    def get_content_history(self, count: int = 10) -> List[GeneratedContent]:
        """获取生成历史"""
        return list(self._content_history)[-count:]

    def get_style(self) -> StyleConfig:
        """获取当前风格"""
        return self._default_style

    def get_chaos_library(self) -> Dict[str, ChaosEvent]:
        """获取混沌事件库"""
        return self._chaos_library

    def export_contents(self) -> Dict[str, Any]:
        """导出内容数据"""
        return {
            "contents": {k: v.to_dict() for k, v in self._generated_contents.items()},
            "history": [c.to_dict() for c in self._content_history],
            "chaos_library": {k: v.to_dict() for k, v in self._chaos_library.items()},
            "statistics": {
                "total_words": self._total_words_generated,
                "total_sections": self._total_sections_generated,
                "total_chaos": self._total_chaos_injected,
                "content_count": len(self._generated_contents)
            },
            "style": self._default_style.to_dict()
        }

    def reset(self) -> None:
        """重置智能体"""
        self._generated_contents.clear()
        self._content_history.clear()
        self._chaos_library.clear()
        self._active_chaos_events.clear()
        self._total_words_generated = 0
        self._total_sections_generated = 0
        self._total_chaos_injected = 0
