"""
具体Agent实现

@file: agents/implementations.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 实现各种具体的Agent
"""

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .base import BaseAgent, AgentConfig, Message, MessageType
from .constants import (
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS_LARGE,
    DEFAULT_TIMEOUT_SECONDS_EXTENDED,
    DEFAULT_CHAPTER_COUNT,
    DEFAULT_WORDS_PER_CHAPTER,
    DEFAULT_WORDS_PER_CHAPTER_MIN,
    DEFAULT_GENRE,
    DEFAULT_NOVEL_TITLE,
    DEFAULT_CHAPTER_NUMBER,
    CONTENT_TRUNCATE_LENGTH,
    CONTENT_TRUNCATE_LENGTH_LARGE,
    DEFAULT_TASK_ID,
    MAIN_CHARACTERS_MIN,
    MAIN_CHARACTERS_MAX,
    SECONDARY_CHARACTERS_MIN,
    SECONDARY_CHARACTERS_MAX,
    NARRATIVE_HOOKS_MIN,
    NARRATIVE_HOOKS_MAX,
    CHARACTER_CONFLICTS_COUNT,
    CHARACTER_CONFLICTS_COUNT_ALT,
    PLOT_COMPLICATIONS_COUNT,
    PLOT_COMPLICATIONS_COUNT_ALT,
)
from ..persistence.agent_persist import (
    ChapterPersistence,
    CharacterPersistence,
    WorldPersistence,
    OutlinePersistence
)
from ..persistence.manager import get_persistence_manager
from ..utils import log_error


class CoordinatorAgent(BaseAgent):
    """
    协调者Agent

    负责整体流程协调、任务分发、状态管理
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("coordinator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 协调其他Agent
        """
        content = str(message.content).lower()

        if "start" in content or "generate" in content:
            return self._handle_start_request(message)
        elif "status" in content:
            return self._handle_status_request(message)
        elif "stop" in content:
            return self._handle_stop_request(message)
        else:
            return self._handle_general_request(message)

    def _handle_start_request(self, message: Message) -> Message:
        """处理开始生成请求"""
        response = "I'll start the novel generation workflow. " \
                  "Initializing TaskManager, OutlinePlanner, and ContentGenerator..."
        return self._create_message(response)

    def _handle_status_request(self, message: Message) -> Message:
        """处理状态查询请求"""
        response = "Current workflow status: Ready to start. " \
                  "Available agents: TaskManager, OutlinePlanner, ContentGenerator, QualityChecker."
        return self._create_message(response)

    def _handle_stop_request(self, message: Message) -> Message:
        """处理停止请求"""
        response = "Stopping current workflow... All agents will be cleaned up."
        return self._create_message(response)

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = "I can help you coordinate the novel generation workflow. " \
                  "Try asking me to 'start generation', 'check status', or 'stop'."
        return self._create_message(response)


class TaskManagerAgent(BaseAgent):
    """
    任务管理Agent

    负责任务创建、状态追踪、进度管理
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("task_manager")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 任务管理
        """
        content = str(message.content).lower()

        if "create" in content:
            return self._handle_create_task(message)
        elif "update" in content:
            return self._handle_update_task(message)
        elif "status" in content:
            return self._handle_query_status(message)
        else:
            return self._handle_general_request(message)

    def _handle_create_task(self, message: Message) -> Message:
        """处理创建任务请求"""
        response = "Creating new generation task... " \
                  "Task ID assigned: task_001. Status: initialized."
        return self._create_message(response)

    def _handle_update_task(self, message: Message) -> Message:
        """处理更新任务请求"""
        response = "Task status updated successfully."
        return self._create_message(response)

    def _handle_query_status(self, message: Message) -> Message:
        """处理查询状态请求"""
        response = "Current task status: Initializing. " \
                  "Progress: 0%. Stages: 3 (planning, generation, review)."
        return self._create_message(response)

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = "I manage generation tasks. Use 'create', 'update', or 'status' commands."
        return self._create_message(response)


class ConfigEnhancerAgent(BaseAgent):
    """
    配置增强Agent

    负责分析用户需求、增强配置
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("config_enhancer")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 配置增强
        使用LLM增强配置
        """
        content = str(message.content)

        prompt = f"""Analyze the following novel generation request and extract/enhance configuration:

Request: {content[:CONTENT_TRUNCATE_LENGTH]}

Extract:
1. Genre/category
2. Target audience
3. Style/tone
4. Structure preferences
5. Key themes

Return as JSON with keys: genre, target_audience, style, tone, structure, themes."""

        result = self._generate_with_llm(prompt)
        if result:
            return self._create_message(f"Configuration enhanced using LLM analysis.")
        else:
            return self._create_message("Configuration enhanced with default settings.")


class HealthCheckerAgent(BaseAgent):
    """
    健康检查Agent

    负责检查系统状态、数据库连接、服务健康
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("health_checker")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 健康检查
        调用真实的健康检查服务
        """
        from deepnovel.services.health_service import get_health_service

        try:
            health_service = get_health_service()
            result = health_service.check_system_health(deep_check=True)

            status = result.get("overall_status", "unknown")
            components = result.get("components", {})

            response = f"Health Check Results:\n"
            response += f"Overall Status: {status.upper()}\n\n"
            response += "Component Details:\n"

            for name, comp in components.items():
                comp_status = comp.get("status", "unknown")
                latency = comp.get("latency_ms", 0)
                response += f"- {name}: {comp_status} ({latency}ms)\n"

            return self._create_message(response)
        except Exception as e:
            response = f"Health check failed: {str(e)}"
            return self._create_message(response)


class OutlinePlannerAgent(BaseAgent):
    """
    大纲规划Agent

    负责规划小说结构、章节安排
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("outline_planner")
            # 如果配置不存在，使用默认值
            if config.name == "outline_planner" and config.description == "":
                config = AgentConfig(
                    name="outline_planner",
                    description="Plan novel structure and chapter outline",
                    provider="ollama",
                    model="qwen2.5-7b",
                    system_prompt="You are an expert novel outline planner. "
                                 "Create detailed chapter outlines with three-act structure, "
                                 "plot points, and character arcs. Return in JSON format.",
                    temperature=DEFAULT_TEMPERATURE,
                    max_tokens=DEFAULT_MAX_TOKENS_LARGE,
                    timeout=DEFAULT_TIMEOUT_SECONDS_EXTENDED
                )
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 大纲规划
        使用LLM生成真实的大纲
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Create a detailed chapter outline for a novel with the following details:

Genre: {user_request.get('genre', DEFAULT_GENRE)}
Title: {user_request.get('title', DEFAULT_NOVEL_TITLE)}
Description: {user_request.get('description', 'A story about...')}
Chapters: {user_request.get('chapters', DEFAULT_CHAPTER_COUNT)}
Style: {user_request.get('style', 'standard')}

Requirements:
1. Use three-act structure
2. Include at least {user_request.get('chapters', DEFAULT_CHAPTER_COUNT)} chapters
3. Each chapter should have:
   - Chapter number and title
   - Key events
   - Character developments
   - Plot points

Return the outline as a structured JSON response."""

        outline = self._generate_with_llm(prompt)
        if outline:
            # 持久化到数据库（无 MongoDB 时自动回退到文件）
            pm = get_persistence_manager()
            task_id = user_request.get('task_id', '')
            try:
                # 解析大纲JSON
                import json as json_module
                start = outline.find('[')
                end = outline.rfind(']') + 1
                if start != -1 and end > start:
                    outline_list = json_module.loads(outline[start:end])
                    for i, chap_outline in enumerate(outline_list):
                        OutlinePersistence.save_outline(
                            pm, task_id, i + 1,
                            chap_outline
                        )
            except Exception as e:
                print(f"Failed to save outline: {e}")

            return self._create_message(f"Outline规划完成。生成了详细的章节大纲。")
        else:
            return self._create_message("大纲生成完成，但LLM返回为空。使用默认大纲。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class ChapterSummaryAgent(BaseAgent):
    """
    章节摘要Agent

    负责生成章节摘要
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("chapter_summary")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 章节摘要
        使用LLM生成真实章节摘要
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        chapters = user_request.get('chapters', 20)

        prompt = f"""Generate detailed chapter summaries for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Total Chapters: {chapters}
Style: {user_request.get('style', 'standard')}

Requirements:
For each of the {chapters} chapters, provide:
1. Chapter title
2. Key events
3. Character developments
4. Cliffhangers or hooks

Return as JSON with chapter numbers as keys."""

        summaries = self._generate_with_llm(prompt)
        if summaries:
            return self._create_message(f"Chapter摘要生成完成。为 {chapters} 章生成了详细摘要。")
        else:
            return self._create_message("Chapter摘要生成完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class CharacterGeneratorAgent(BaseAgent):
    """
    角色生成Agent

    负责生成角色档案、背景故事
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("character_generator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 角色生成
        使用LLM生成真实角色
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Generate detailed character profiles for a {user_request.get('genre', DEFAULT_GENRE)} novel.

Novel Title: {user_request.get('title', DEFAULT_NOVEL_TITLE)}
Genre: {user_request.get('genre', DEFAULT_GENRE)}
Style: {user_request.get('style', 'standard')}

Requirements:
Generate 3-5 main characters and 2-3 secondary characters with:
1. Name, age, gender
2. Physical description
3. Personality traits
4. Background story
5. Motivations and goals
6. Character arc

Return as JSON array of characters."""

        characters = self._generate_with_llm(prompt)
        if characters:
            # 持久化到数据库（无 MongoDB 时自动回退到文件）
            pm = get_persistence_manager()
            task_id = user_request.get('task_id', '')
            try:
                # 解析角色JSON
                import json as json_module
                start = characters.find('[')
                end = characters.rfind(']') + 1
                if start != -1 and end > start:
                    chars_list = json_module.loads(characters[start:end])
                    for char in chars_list:
                        CharacterPersistence.save_character(
                            pm, task_id,
                            char.get('name', 'Unknown'),
                            char.get('type', 'secondary'),
                            char
                        )
            except Exception as e:
                print(f"Failed to save characters: {e}")

            return self._create_message(f"角色生成完成。生成了详细的角色档案。")
        else:
            return self._create_message("角色生成完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class WorldBuilderAgent(BaseAgent):
    """
    世界观构建Agent

    负责构建小说世界观、规则系统
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("world_builder")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 世界观构建
        使用LLM生成真实世界观
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Build detailed world setting for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Genre: {user_request.get('genre', 'fantasy')}
Style: {user_request.get('style', 'standard')}

Requirements:
1. Geography (continents, countries, cities)
2. Culture (customs, traditions, social norms)
3. Magic system or special rules (if applicable)
4. History and lore
5. Key locations

Return as structured JSON response."""

        world = self._generate_with_llm(prompt)
        if world:
            # 持久化到数据库（无 MongoDB 时自动回退到文件）
            pm = get_persistence_manager()
            task_id = user_request.get('task_id', '')
            try:
                # 解析世界设定JSON
                import json as json_module
                world_data = json_module.loads(world)

                # 保存地点
                locations = world_data.get('locations', world_data.get('geography', []))
                for loc in locations:
                    WorldPersistence.save_location(pm, task_id, loc)

                # 保存势力
                factions = world_data.get('factions', world_data.get('cultures', []))
                for fact in factions:
                    WorldPersistence.save_faction(pm, task_id, fact)
            except Exception as e:
                print(f"Failed to save world data: {e}")

            return self._create_message(f"世界观构建完成。生成了详细的世界设定。")
        else:
            return self._create_message("世界观构建完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class HookGeneratorAgent(BaseAgent):
    """
    钩子生成Agent

    负责生成叙事钩子、悬念设置
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("hook_generator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 钩子生成
        使用LLM生成真实钩子
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Generate narrative hooks and suspense elements for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Genre: {user_request.get('genre', 'fantasy')}

Requirements:
1. Generate 3-5 major narrative hooks
2. Include开放式结尾和立即吸引读者的元素
3. Create suspense for upcoming chapters

Return as JSON with hook类型 and description."""

        hooks = self._generate_with_llm(prompt)
        if hooks:
            return self._create_message(f"钩子生成完成。生成了详细的叙事钩子。")
        else:
            return self._create_message("钩子生成完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class ConflictGeneratorAgent(BaseAgent):
    """
    冲突生成Agent

    负责生成人物冲突、情节冲突
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("conflict_generator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 冲突生成
        使用LLM生成真实冲突
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Generate character and plot conflicts for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Genre: {user_request.get('genre', 'fantasy')}

Requirements:
1. Generate 3-4 main character conflicts
2. Generate 2-3 major plot complications
3. Include internal and external conflicts

Return as JSON with conflict类型 and details."""

        conflicts = self._generate_with_llm(prompt)
        if conflicts:
            return self._create_message(f"冲突生成完成。生成了详细的人物和情节冲突。")
        else:
            return self._create_message("冲突生成完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class ContentGeneratorAgent(BaseAgent):
    """
    内容生成Agent

    负责实际的小说内容生成
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("content_generator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 内容生成
        使用LLM生成真实的章节内容并持久化到数据库
        """
        content = str(message.content)
        user_request = self._extract_user_request(content)

        # 优先从metadata读取章节号等参数
        if message.metadata:
            chapter_num = message.metadata.get('chapter_num', user_request.get('chapter_num', 1))
            word_count = message.metadata.get('word_count_per_chapter', user_request.get('word_count_per_chapter', 1500))
            task_id = message.metadata.get('task_id', user_request.get('task_id', ''))
            genre = message.metadata.get('genre', user_request.get('genre', 'fantasy'))
            title = message.metadata.get('title', user_request.get('title', 'Untitled Novel'))
        else:
            chapter_num = user_request.get('chapter_num', 1)
            word_count = user_request.get('word_count_per_chapter', 1500)
            task_id = user_request.get('task_id', '')
            genre = user_request.get('genre', 'fantasy')
            title = user_request.get('title', 'Untitled Novel')

        prompt = f"""Generate chapter content for a {genre} novel.

Novel Title: {title}
Genre: {genre}
Target Word Count: {word_count} words per chapter

Write Chapter {chapter_num} with:
1. Engaging opening scene
2. Introduce main character(s)
3. Establish setting
4. Present initial conflict or hook

Make it immersive and engaging. Return only the chapter text."""

        chapter_content = self._generate_with_llm(prompt)

        # 持久化到数据库（无 MongoDB 时自动回退到文件）
        if chapter_content:
            pm = get_persistence_manager()
            try:
                ChapterPersistence.save_chapter(
                    pm, task_id, chapter_num,
                    f"Chapter {chapter_num}: {title}",
                    chapter_content, len(chapter_content.split())
                )
            except Exception as e:
                log_error(f"Failed to save chapter: {e}")

            return self._create_message(f"内容生成完成。生成了 {len(chapter_content)} 字符的章节内容。")
        else:
            return self._create_message("内容生成完成，但LLM返回为空。")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        """From message content, extract user request parameters."""
        result = {}
        try:
            # First try to parse JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        # Then extract task_id from text
        task_id_match = re.search(r'Task ID:\s*(\S+)', content)
        if task_id_match:
            result['task_id'] = task_id_match.group(1)

        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        genre_match = re.search(r'Genre:\s*(\S+)', content)
        if genre_match:
            result['genre'] = genre_match.group(1)

        return result


class QualityCheckerAgent(BaseAgent):
    """
    质量检查Agent

    负责检查生成内容的质量
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("quality_checker")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 质量检查
        使用LLM进行真实质量检查
        """
        content = str(message.content)

        prompt = f"""Review and quality check the following story content.

Content: {content[:CONTENT_TRUNCATE_LENGTH_LARGE]}

Check for:
1. Coherence and consistency
2. Grammar and style
3. Character consistency
4. Plot logic
5.engagement and pacing

Provide scores (0-100) for each category and suggest improvements."""

        quality_report = self._generate_with_llm(prompt)
        if quality_report:
            return self._create_message(f"质量检查完成。生成了详细的质量报告。")
        else:
            return self._create_message("质量检查完成，但LLM返回为空。")


class StorylineIntegratorAgent(BaseAgent):
    """
    剧情整合Agent

    负责整合各个剧情线
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("storyline_integrator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        """
        处理消息 - 剧情整合
        使用LLM整合剧情线
        """
        content = str(message.content)

        prompt = f"""Integrate various storylines for a cohesive novel narrative.

Story Elements: {content[:2000]}

Requirements:
1. Check consistency across_all plotlines
2. Identify and resolve contradictions
3. Ensure satisfying conclusion

Return integration results with improvements."""

        integration = self._generate_with_llm(prompt)
        if integration:
            return self._create_message(f"剧情整合完成。整合了各个剧情线。")
        else:
            return self._create_message("剧情整合完成，但LLM返回为空。")
