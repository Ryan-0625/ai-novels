"""
HumanizerAgent - 文本润色智能体

去除AI痕迹，增加人性化表达，使生成文本更自然

@file: agents/humanizer.py
"""

import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .base import BaseAgent, AgentConfig, Message, MessageType
from ai_novels.persistence import get_persistence_manager


@dataclass
class PolishResult:
    """润色结果"""
    chapter_num: int
    original_word_count: int
    polished_word_count: int
    changes_made: List[Dict[str, str]]
    quality_score: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "original_word_count": self.original_word_count,
            "polished_word_count": self.polished_word_count,
            "changes_made": self.changes_made[:10],
            "quality_score": self.quality_score,
            "timestamp": self.timestamp,
        }


class HumanizerAgent(BaseAgent):
    """
    文本润色智能体

    核心功能：
    - 去除AI生成痕迹（重复模式、生硬过渡）
    - 增加人性化表达（情感深度、口语化）
    - 优化句式多样性
    - 保持原文风格一致性
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="humanizer",
                description="Text polishing - remove AI痕迹, increase humanity",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=8192
            )
        super().__init__(config)

        self._results: Dict[str, List[PolishResult]] = {}
        # 缓存 Task Context（genre/style），由 process 解析
        self._task_genre: str = ""
        self._task_style: str = ""

    def _parse_task_context(self, content: str) -> None:
        """从消息内容中提取 Task Context 的 genre/style"""
        for line in content.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip()
            if key == 'genre' and value:
                self._task_genre = value
            elif key == 'style' and value:
                self._task_style = value

    def _task_context_section(self) -> str:
        """构建 Task Context 文本段供 LLM 提示词使用"""
        parts = []
        if self._task_genre:
            parts.append(f"体裁: {self._task_genre}")
        if self._task_style:
            parts.append(f"风格: {self._task_style}")
        return "，".join(parts)

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "polish" in content or "润色" in content or "humanize" in content:
            if "chapter" in content or "章节" in content:
                return self._handle_polish_chapters(message)
            return self._handle_polish_all(message)

        return self._handle_polish_all(message)

    def _handle_polish_all(self, message: Message) -> Message:
        """处理全文润色请求"""
        content = str(message.content)

        # 解析 Task Context
        self._parse_task_context(content)

        task_id = self._extract_param(content, "task_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        chapters = self._parse_chapters(chapters_str)
        results = []

        for ch in chapters:
            result = self._polish_chapter(task_id, ch)
            if result:
                results.append(result)

        if task_id:
            self._results[task_id] = results

        response = f"Polishing complete for {len(results)} chapters:\n\n"
        for r in results:
            response += f"Chapter {r.chapter_num}: {r.original_word_count} → {r.polished_word_count} words (score: {r.quality_score:.1f})\n"
            if r.changes_made:
                response += "  Changes:\n"
                for c in r.changes_made[:3]:
                    response += f"  - {c.get('type', '')}: {c.get('description', '')[:60]}...\n"
            response += "\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            chapters_polished=len(results),
            results=[r.to_dict() for r in results],
        )

    def _handle_polish_chapters(self, message: Message) -> Message:
        """处理指定章节润色请求"""
        content = str(message.content)

        # 解析 Task Context
        self._parse_task_context(content)

        task_id = self._extract_param(content, "task_id", "")
        chapter_nums_str = self._extract_param(content, "chapter_nums", "")

        chapter_nums = [int(x.strip()) for x in chapter_nums_str.split(",") if x.strip().isdigit()]
        results = []

        for num in chapter_nums:
            result = self._polish_chapter(task_id, f"chapter_{num}")
            if result:
                results.append(result)

        response = f"Polishing complete for chapters {chapter_nums}:\n\n"
        for r in results:
            response += f"Chapter {r.chapter_num}: {r.original_word_count} → {r.polished_word_count} words\n"

        return self._create_message(response, MessageType.TEXT, results=[r.to_dict() for r in results])

    def _polish_chapter(self, task_id: str, chapter_ref: str) -> Optional[PolishResult]:
        """润色单个章节"""
        chapter_num = None
        for prefix in ["chapter_", "Chapter ", "第"]:
            if prefix in chapter_ref:
                digits = "".join(filter(str.isdigit, chapter_ref.split(prefix)[-1]))
                if digits:
                    chapter_num = int(digits)
                    break

        if chapter_num is None:
            return None

        # 从数据库读取章节内容
        pm = get_persistence_manager()
        content = ""
        if pm.mongodb_client:
            try:
                cursor = pm.mongodb_client.read(
                    collection="chapters",
                    query={"task_id": task_id, "chapter_num": chapter_num},
                    limit=1,
                )
                docs = list(cursor) if hasattr(cursor, "__iter__") else [cursor]
                for doc in docs if isinstance(docs, list) else [docs]:
                    content = doc.get("content", "") if isinstance(doc, dict) else ""
            except Exception:
                pass

        if not content:
            return None

        original_word_count = len(content)

        # 使用LLM润色
        task_ctx = self._task_context_section()
        ctx_section = f"\n小说信息：{task_ctx}\n" if task_ctx else ""
        prompt = (
            f"你是一个专业的小说文本润色专家。请润色以下小说章节内容，要求：\n\n"
            f"1. 去除AI生成痕迹（如重复句式、机械过渡、模板化表达）\n"
            f"2. 增加人性化表达（情感深度、自然对话）\n"
            f"3. 优化句式多样性（长短句结合）\n"
            f"4. 保持原文情节和角色特征不变\n"
            f"5. 不改变总长度（可增减10%以内）\n"
            f"{ctx_section}"
            f"\n章节 {chapter_num} 内容：\n\n{content[:6000]}\n\n"
            f"请返回JSON格式：{{\"polished_text\": \"润色后的文本\", \"changes\": [{{\"type\": \"修改类型\", \"description\": \"具体修改说明\"}}], \"quality_score\": 总体质量评分(0-100)}}"
            f"请确保polished_text是完整的章节内容。"
        )
        llm_response = self._generate_with_llm(prompt)

        # 解析结果
        polished_text = content
        changes = []
        quality_score = 85.0

        try:
            data = json.loads(llm_response)
            if isinstance(data, dict):
                polished_text = data.get("polished_text", content)
                changes = data.get("changes", [])
                quality_score = float(data.get("quality_score", 85.0))
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

        # 保存润色后的内容回数据库
        if pm.mongodb_client and polished_text != content:
            try:
                pm.mongodb_client.update(
                    collection="chapters",
                    query={"task_id": task_id, "chapter_num": chapter_num},
                    data={"content": polished_text, "polished": True, "polished_at": time.time()},
                )
            except Exception:
                pass

        return PolishResult(
            chapter_num=chapter_num,
            original_word_count=original_word_count,
            polished_word_count=len(polished_text),
            changes_made=changes,
            quality_score=quality_score,
        )

    def _parse_chapters(self, chapters_str: str) -> List[str]:
        """解析章节字符串"""
        if not chapters_str:
            return ["chapter_1", "chapter_2", "chapter_3"]
        chapters = [c.strip() for c in chapters_str.split(",")]
        return chapters[:20]

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

    def polish_chapter(self, task_id: str, chapter_num: int) -> Optional[PolishResult]:
        """润色章节（外部接口）"""
        return self._polish_chapter(task_id, f"chapter_{chapter_num}")

    def get_results(self, task_id: str) -> List[PolishResult]:
        """获取润色结果"""
        return self._results.get(task_id, [])
