"""
Agent 实现 — 统一导出入口

所有 Agent 优先从独立文件导入（它们包含完整的业务逻辑和状态管理）
仅保留没有独立文件的 Agent 实现内联

@file: agents/implementations.py
"""

import json
import re
from typing import Any, Dict

from .base import BaseAgent, AgentConfig, Message, MessageType
from .constants import CONTENT_TRUNCATE_LENGTH

# ───────────────────────────────────────────────
# 从独立文件导入（包含完整的业务逻辑）
# ───────────────────────────────────────────────
from .coordinator import CoordinatorAgent  # noqa: F401 — DAG 编排
from .health_checker import HealthCheckerAgent  # noqa: F401 — 真实 TCP/HTTP 健康检查（已废弃）
from .task_manager import TaskManagerAgent  # noqa: F401 — 完整任务状态机
from .outline_planner import OutlinePlannerAgent  # noqa: F401 — 大纲规划
from .character_generator import CharacterGeneratorAgent  # noqa: F401 — 角色生成
from .world_builder import WorldBuilderAgent  # noqa: F401 — 世界观构建
from .hook_generator import HookGeneratorAgent  # noqa: F401 — 叙事钩子
from .content_generator import ContentGeneratorAgent  # noqa: F401 — 内容生成
from .quality_checker import QualityCheckerAgent  # noqa: F401 — 质量检查
from .humanizer import HumanizerAgent  # noqa: F401 — 文本润色


# ───────────────────────────────────────────────
# 内联实现（无独立文件的 Agent，保持向后兼容）
# ───────────────────────────────────────────────


class ConfigEnhancerAgent(BaseAgent):
    """配置增强 Agent — 使用 LLM 分析用户需求"""

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("config_enhancer")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        content = str(message.content)

        prompt = f"""You are a novel configuration enhancer. Analyze the following request and extract ALL details:

Request: {content[:CONTENT_TRUNCATE_LENGTH]}

You MUST extract and return a comprehensive JSON config. Include ALL of the following:

1. **protagonist_name** — main character's name (if mentioned, in Chinese)
2. **genre** — novel genre/category (in Chinese, e.g. 武侠/奇幻/科幻/都市/仙侠/言情/悬疑)
3. **style** — writing style (e.g. 热血/沉重/轻松/幽默/写实/唯美)
4. **description** — 2-3 sentence novel concept/summary in Chinese
5. **target_audience** — target readers (e.g. 青年读者/成年读者/全年龄)
6. **language** — language code (zh-CN/en)
7. **tone** — overall tone (e.g. epic/light/dark/serious/humorous)
8. **themes** — key themes array
9. **characters** — array of character objects with name and role (主角/配角/反派)
10. **world_setting** — brief world setting description if applicable

Return ONLY valid JSON. No other text. Example:
{{"protagonist_name": "林清风", "genre": "仙侠", "style": "热血", "description": "少年林清风踏上修仙之路的故事", "target_audience": "青年读者", "language": "zh-CN", "tone": "epic", "themes": ["成长", "友情", "冒险"], "characters": [{{"name": "林清风", "role": "主角"}}], "world_setting": "修仙世界"}}"""

        result = self._generate_with_llm(prompt)
        if result:
            return self._create_message(f"Configuration enhanced using LLM analysis: {result}")
        return self._create_message("Configuration enhanced with default settings.")


class ChapterSummaryAgent(BaseAgent):
    """章节摘要 Agent — 使用 LLM 生成"""

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("chapter_summary")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        content = str(message.content)
        user_request = self._extract_user_request(content)
        chapters = user_request.get("chapters", 20)

        prompt = f"""Generate detailed chapter summaries for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Total Chapters: {chapters}

For each chapter, provide: title, key events, character developments, cliffhangers.
Return as JSON array."""

        summaries = self._generate_with_llm(prompt)
        if summaries:
            return self._create_message(f"Chapter summaries generated for {chapters} chapters.")
        return self._create_message("Chapter summary generation completed (LLM returned empty).")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        result = {}
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        task_id_match = re.search(r"Task ID:\s*(\S+)", content)
        if task_id_match:
            result["task_id"] = task_id_match.group(1)
        title_match = re.search(r"Title:\s*(.+?)(?:\n|$)", content)
        if title_match:
            result["title"] = title_match.group(1).strip()
        genre_match = re.search(r"Genre:\s*(\S+)", content)
        if genre_match:
            result["genre"] = genre_match.group(1)
        return result


class ConflictGeneratorAgent(BaseAgent):
    """冲突生成 Agent — 使用 LLM 生成人物和情节冲突"""

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("conflict_generator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        content = str(message.content)
        user_request = self._extract_user_request(content)

        prompt = f"""Generate character and plot conflicts for a {user_request.get('genre', 'fantasy')} novel.

Novel Title: {user_request.get('title', 'Untitled Novel')}
Requirements:
1. Generate 3-4 main character conflicts
2. Generate 2-3 major plot complications
3. Include internal and external conflicts

Return as JSON array."""

        conflicts = self._generate_with_llm(prompt)
        if conflicts:
            return self._create_message(f"Conflicts generated: {conflicts[:200]}")
        return self._create_message("Conflict generation completed (LLM returned empty).")

    def _extract_user_request(self, content: str) -> Dict[str, Any]:
        result = {}
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                result = json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
        task_id_match = re.search(r"Task ID:\s*(\S+)", content)
        if task_id_match:
            result["task_id"] = task_id_match.group(1)
        title_match = re.search(r"Title:\s*(.+?)(?:\n|$)", content)
        if title_match:
            result["title"] = title_match.group(1).strip()
        genre_match = re.search(r"Genre:\s*(\S+)", content)
        if genre_match:
            result["genre"] = genre_match.group(1)
        return result


class StorylineIntegratorAgent(BaseAgent):
    """剧情整合 Agent — 使用 LLM 整合剧情线"""

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig.from_config("storyline_integrator")
        super().__init__(config)

    def process(self, message: Message) -> Message:
        content = str(message.content)
        prompt = f"""Integrate various storylines for a cohesive novel narrative.

Story Elements: {content[:2000]}

Check consistency across all plotlines, identify contradictions, ensure satisfying conclusion.
Return integration results with improvements."""

        integration = self._generate_with_llm(prompt)
        if integration:
            return self._create_message(f"Storyline integration completed: {integration[:200]}")
        return self._create_message("Storyline integration completed (LLM returned empty).")
