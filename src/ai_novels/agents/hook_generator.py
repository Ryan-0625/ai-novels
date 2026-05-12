"""
HookGeneratorAgent - 钩子生成智能体

@file: agents/hook_generator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 钩子生成、状态管理、向量存储
"""

import time
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import hashlib

from .base import BaseAgent, AgentConfig, Message, MessageType
from ..vector_store.base import BaseVectorStore
from ..vector_store.chroma_store import ChromaVectorStore
from ai_novels.utils import log_error


class HookType(Enum):
    """钩子类型"""
    OPENING = "opening"          # 开篇钩子
    CHAPTER_END = "chapter_end"  # 章节结尾钩子
    PLOT_TWIST = "plot_twist"    # 情节转折钩子
    CHARACTER = "character"      # 角色钩子
    MYSTERY = "mystery"          # 谜题钩子
    THREAT = "threat"            # 威胁钩子
    PROMISE = "promise"          # 承诺钩子
    QUESTION = "question"        # 疑问钩子


class HookStatus(Enum):
    """钩子状态"""
    ACTIVE = "active"        # 激活状态
    RESOLVED = "resolved"    # 已解决
    TEMPORARY = "temporary"  # 临时钩子
    DROPPED = "dropped"      # 已丢弃


@dataclass
class Hook:
    """钩子数据结构"""
    hook_id: str
    hook_type: HookType
    content: str
    chapter_id: str
    status: HookStatus
    created_at: float
    resolved_at: Optional[float] = None
    resolution: Optional[str] = None
    impact_level: int = 50  # 0-100 影响力
    related_beats: List[str] = field(default_factory=list)
    related_characters: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "type": self.hook_type.value,
            "content": self.content,
            "chapter_id": self.chapter_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
            "impact_level": self.impact_level,
            "related_beats": self.related_beats,
            "related_characters": self.related_characters,
            "embedding": self.embedding
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class HookSequence:
    """钩子序列"""
    sequence_id: str
    hooks: List[Hook]
    total_impact: int
    retention_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "hooks": [h.to_dict() for h in self.hooks],
            "total_impact": self.total_impact,
            "retention_score": self.retention_score
        }


@dataclass
class ChapterHookState:
    """章节钩子状态"""
    chapter_id: str
    active_hooks: List[str]
    resolved_hooks: List[str]
    new_hooks: List[str]
    hook_score: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "active_hooks": self.active_hooks,
            "resolved_hooks": self.resolved_hooks,
            "new_hooks": self.new_hooks,
            "hook_score": self.hook_score
        }


class HookGeneratorAgent(BaseAgent):
    """
    钩子生成智能体

    核心功能：
    - 多类型钩子生成（开篇/章节结尾/转折/角色/谜题/威胁/承诺/疑问）
    - 钩子状态管理（激活/解决/丢弃）
    - 向量存储与相似度搜索
    - 钩子序列生成
    - 阅读留存率预测
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="hook_generator",
                description="Hook generation and management",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=4096
            )
        super().__init__(config)

        # 钩子存储
        self._hooks: Dict[str, Hook] = {}
        self._hook_sequences: Dict[str, HookSequence] = {}
        self._chapter_states: Dict[str, ChapterHookState] = {}

        # 状态管理
        self._active_hooks: List[str] = []
        self._resolved_hooks: List[str] = []
        self._dropped_hooks: List[str] = []

        # 向量存储
        self._vector_store: Optional[BaseVectorStore] = None
        self._embedding_model = "all-MiniLM-L6-v2"

        # 状态
        self._last_hook_id = 0
        self._hook_generation_count = 0
        self._resolution_rate = 0.0

    def initialize(self) -> bool:
        """初始化智能体"""
        try:
            # 初始化向量存储
            self._vector_store = ChromaVectorStore(
                collection_name="hooks",
                embedding_model=self._embedding_model
            )
            return True
        except Exception as e:
            log_error(f"Failed to initialize HookGeneratorAgent: {e}")
            return False

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "hook" in content:
            if "generate" in content or "create" in content:
                return self._handle_generate_hook(message)
            elif "sequence" in content:
                return self._handle_generate_sequence(message)
            elif "resolve" in content:
                return self._handle_resolve_hook(message)
            elif "check" in content or "status" in content:
                return self._handle_check_hooks(message)
            elif "search" in content:
                return self._handle_search_hooks(message)
            elif "analyze" in content:
                return self._handle_analyze_hooks(message)
        elif "chapter" in content and "state" in content:
            return self._handle_get_state(message)

        return self._handle_generate_hook(message)

    def _handle_generate_hook(self, message: Message) -> Message:
        """处理生成钩子请求"""
        content = str(message.content)

        hook_type = self._extract_param(content, "type", "chapter_end")
        chapter_id = self._extract_param(content, "chapter_id", "chapter_1")
        context = self._extract_param(content, "context", "")
        impact = int(self._extract_param(content, "impact", "50"))

        generated_hook = self._generate_hook(
            hook_type=HookType(hook_type.lower()),
            chapter_id=chapter_id,
            context=context,
            impact_level=impact
        )

        self._hooks[generated_hook.hook_id] = generated_hook
        self._active_hooks.append(generated_hook.hook_id)
        self._hook_generation_count += 1

        # 存储到向量库
        if self._vector_store:
            try:
                self._vector_store.add(
                    docs=[generated_hook.content],
                    metadatas=[{
                        "hook_id": generated_hook.hook_id,
                        "type": generated_hook.hook_type.value,
                        "chapter_id": generated_hook.chapter_id,
                        "status": generated_hook.status.value
                    }],
                    ids=[generated_hook.hook_id]
                )
            except Exception as e:
                log_error(f"Failed to store hook in vector store: {e}")

        response = f"Generated Hook: {generated_hook.hook_id}\n\n"
        response += f"Type: {generated_hook.hook_type.value}\n"
        response += f"Content: {generated_hook.content}\n"
        response += f"Impact: {generated_hook.impact_level}\n"
        response += f"Chapter: {generated_hook.chapter_id}\n"

        # 生成相关字符和节拍
        response += f"\nRelated Characters: {', '.join(generated_hook.related_characters) or 'None'}\n"
        response += f"Related Beats: {', '.join(generated_hook.related_beats) or 'None'}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            hook_id=generated_hook.hook_id,
            hook_type=generated_hook.hook_type.value,
            chapter_id=chapter_id
        )

    def _handle_generate_sequence(self, message: Message) -> Message:
        """处理生成钩子序列请求"""
        content = str(message.content)

        sequence_id = self._extract_param(content, "sequence_id", "seq_001")
        chapter_range = self._extract_param(content, "chapter_range", "1-5")
        min_hooks = int(self._extract_param(content, "min", "3"))
        max_hooks = int(self._extract_param(content, "max", "6"))

        # 生成序列
        sequence = self._generate_hook_sequence(
            sequence_id=sequence_id,
            start_chapter=int(chapter_range.split("-")[0]),
            end_chapter=int(chapter_range.split("-")[1]),
            min_hooks=min_hooks,
            max_hooks=max_hooks
        )

        self._hook_sequences[sequence_id] = sequence

        response = f"Generated Hook Sequence {sequence_id}:\n\n"
        response += f"Chapters: {chapter_range}\n"
        response += f"Total Hooks: {len(sequence.hooks)}\n"
        response += f"Total Impact: {sequence.total_impact}\n"
        response += f"Retention Score: {sequence.retention_score:.2f}\n\n"

        for i, hook in enumerate(sequence.hooks):
            response += f"{i+1}. [{hook.hook_type.value}] {hook.content[:60]}... (Impact: {hook.impact_level})\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            sequence_id=sequence_id,
            hook_count=len(sequence.hooks)
        )

    def _handle_resolve_hook(self, message: Message) -> Message:
        """处理解决钩子请求"""
        content = str(message.content)

        hook_id = self._extract_param(content, "hook_id", "")
        resolution = self._extract_param(content, "resolution", "")

        if hook_id and hook_id in self._hooks:
            hook = self._hooks[hook_id]
            hook.status = HookStatus.RESOLVED
            hook.resolved_at = time.time()
            hook.resolution = resolution

            if hook_id in self._active_hooks:
                self._active_hooks.remove(hook_id)
            self._resolved_hooks.append(hook_id)

            # 更新向量存储
            if self._vector_store:
                try:
                    self._vector_store.update(
                        ids=[hook_id],
                        metadatas=[{
                            "status": hook.status.value,
                            "resolved_at": hook.resolved_at
                        }]
                    )
                except Exception as e:
                    log_error(f"Failed to update hook in vector store: {e}")

            response = f"Resolved Hook: {hook_id}\n\n"
            response += f"Resolution: {resolution}\n"
            response += f"Timestamp: {time.ctime(hook.resolved_at)}\n"

            # 计算分辨率
            self._calculate_resolution_rate()

            return self._create_message(
                response,
                MessageType.TEXT,
                hook_id=hook_id,
                status=hook.status.value
            )

        return self._create_message(f"Hook {hook_id} not found.", MessageType.TEXT)

    def _handle_check_hooks(self, message: Message) -> Message:
        """处理检查钩子请求"""
        content = str(message.content)

        status_filter = self._extract_param(content, "status", "")
        type_filter = self._extract_param(content, "type", "")

        hooks = list(self._hooks.values())

        if status_filter:
            hooks = [h for h in hooks if h.status.value == status_filter.lower()]
        if type_filter:
            hooks = [h for h in hooks if h.hook_type.value == type_filter.lower()]

        response = "Hook Checklist:\n\n"
        for hook in hooks:
            response += f"ID: {hook.hook_id}\n"
            response += f"  Type: {hook.hook_type.value}\n"
            response += f"  Status: {hook.status.value}\n"
            response += f"  Chapter: {hook.chapter_id}\n"
            response += f"  Impact: {hook.impact_level}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            hook_count=len(hooks)
        )

    def _handle_search_hooks(self, message: Message) -> Message:
        """处理搜索钩子请求"""
        content = str(message.content)

        query = self._extract_param(content, "query", "")
        top_k = int(self._extract_param(content, "top", "5"))

        if not query:
            return self._create_message("Please provide a search query.", MessageType.TEXT)

        # 生成查询向量（模拟）
        query_vector = self._generate_embedding(query)

        # 简单相似度搜索
        results = self._similarity_search(query_vector, top_k)

        response = f"Search Results for: '{query}'\n\n"
        for i, (hook, score) in enumerate(results):
            response += f"{i+1}. [{hook.hook_type.value}] Impact: {hook.impact_level}\n"
            response += f"   {hook.content[:100]}...\n"
            response += f"   Score: {score:.3f}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            query=query,
            results_count=len(results)
        )

    def _handle_analyze_hooks(self, message: Message) -> Message:
        """处理分析钩子请求"""
        # 分析所有钩子
        total = len(self._hooks)
        active = sum(1 for h in self._hooks.values() if h.status == HookStatus.ACTIVE)
        resolved = sum(1 for h in self._hooks.values() if h.status == HookStatus.RESOLVED)

        avg_impact = sum(h.impact_level for h in self._hooks.values()) / max(total, 1)

        type_counts = {}
        for h in self._hooks.values():
            type_key = h.hook_type.value
            type_counts[type_key] = type_counts.get(type_key, 0) + 1

        response = "Hook Analysis:\n\n"
        response += f"Total Hooks: {total}\n"
        response += f"Active: {active}\n"
        response += f"Resolved: {resolved}\n"
        response += f"Average Impact: {avg_impact:.1f}\n\n"
        response += "By Type:\n"
        for t, c in type_counts.items():
            response += f"  {t}: {c}\n"

        # 预测留存率
        retention = self._predict_retention(total, active, avg_impact)
        response += f"\nPredicted Retention Rate: {retention:.1f}%\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            total_hooks=total,
            active_hooks=active,
            resolved_hooks=resolved,
            avg_impact=avg_impact,
            retention_rate=retention
        )

    def _handle_get_state(self, message: Message) -> Message:
        """处理获取章节状态请求"""
        content = str(message.content)
        chapter_id = self._extract_param(content, "chapter_id", "chapter_1")

        if chapter_id not in self._chapter_states:
            # 生成新的章节状态
            self._chapter_states[chapter_id] = self._generate_chapter_state(chapter_id)

        state = self._chapter_states[chapter_id]

        response = f"Chapter {chapter_id} Hook State:\n\n"
        response += f"Active Hooks: {len(state.active_hooks)}\n"
        response += f"Resolved Hooks: {len(state.resolved_hooks)}\n"
        response += f"New Hooks: {len(state.new_hooks)}\n"
        response += f"Hook Score: {state.hook_score}\n\n"
        response += "Active:\n"
        for hook_id in state.active_hooks[:5]:
            response += f"  - {hook_id}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            chapter_id=chapter_id,
            hook_score=state.hook_score
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Hook Generator Agent available commands:\n"
            "- 'generate hook type=X chapter_id=X context=X' - 生成钩子\n"
            "- 'generate sequence sequence_id=X chapter_range=X' - 生成钩子序列\n"
            "- 'resolve hook hook_id=X resolution=X' - 解决钩子\n"
            "- 'check hooks [status=X] [type=X]' - 检查钩子\n"
            "- 'search hooks query=X [top=X]' - 搜索钩子\n"
            "- 'analyze hooks' - 分析钩子\n"
            "- 'state chapter_id=X' - 获取章节状态"
        )
        return self._create_message(response)

    def _generate_hook(
        self,
        hook_type: HookType,
        chapter_id: str,
        context: str = "",
        impact_level: int = 50
    ) -> Hook:
        """
        生成单个钩子

        Args:
            hook_type: 钩子类型
            chapter_id: 章节ID
            context: 上下文
            impact_level: 影响力

        Returns:
            Hook实例
        """
        self._last_hook_id += 1
        hook_id = f"hook_{chapter_id}_{self._last_hook_id:04d}"

        # 生成钩子内容
        content = self._create_hook_content(hook_type, context, impact_level)

        # 生成相关字符和节拍
        related_characters = self._extract_characters_from_context(context)
        related_beats = self._extract_beats_from_context(context)

        # 生成嵌入
        embedding = self._generate_embedding(content)

        hook = Hook(
            hook_id=hook_id,
            hook_type=hook_type,
            content=content,
            chapter_id=chapter_id,
            status=HookStatus.ACTIVE,
            created_at=time.time(),
            impact_level=impact_level,
            related_beats=related_beats,
            related_characters=related_characters,
            embedding=embedding
        )

        return hook

    def _generate_hook_sequence(
        self,
        sequence_id: str,
        start_chapter: int,
        end_chapter: int,
        min_hooks: int = 3,
        max_hooks: int = 6
    ) -> HookSequence:
        """
        生成钩子序列

        Args:
            sequence_id: 序列ID
            start_chapter: 起始章节
            end_chapter: 结束章节
            min_hooks: 最小钩子数
            max_hooks: 最大钩子数

        Returns:
            HookSequence实例
        """
        num_hooks = min(max_hooks, max(min_hooks, (end_chapter - start_chapter) + 2))

        hooks = []
        total_impact = 0

        hook_types = [
            HookType.OPENING,
            HookType.CHAPTER_END,
            HookType.PLOT_TWIST,
            HookType.MYSTERY,
            HookType.THREAT
        ]

        for i in range(num_hooks):
            chapter_num = start_chapter + (i * (end_chapter - start_chapter) // num_hooks)
            chapter_id = f"chapter_{chapter_num:03d}"
            hook_type = hook_types[i % len(hook_types)]
            impact = 50 + (i * 10) % 30

            hook = self._generate_hook(
                hook_type=hook_type,
                chapter_id=chapter_id,
                impact_level=impact
            )

            hooks.append(hook)
            total_impact += hook.impact_level

        # 计算留存率分数
        retention_score = self._calculate_retention_score(hooks)

        return HookSequence(
            sequence_id=sequence_id,
            hooks=hooks,
            total_impact=total_impact,
            retention_score=retention_score
        )

    def _generate_chapter_state(self, chapter_id: str) -> ChapterHookState:
        """
        生成章节钩子状态

        Args:
            chapter_id: 章节ID

        Returns:
            ChapterHookState实例
        """
        # 获取该章节的钩子
        chapter_hooks = [h for h in self._hooks.values() if h.chapter_id == chapter_id]

        active = [h.hook_id for h in chapter_hooks if h.status == HookStatus.ACTIVE]
        resolved = [h.hook_id for h in chapter_hooks if h.status == HookStatus.RESOLVED]
        new = [h.hook_id for h in chapter_hooks if h.status == HookStatus.ACTIVE and len(h.related_characters) > 0]

        # 计算分数
        hook_score = self._calculate_hook_score(active, resolved)

        return ChapterHookState(
            chapter_id=chapter_id,
            active_hooks=active,
            resolved_hooks=resolved,
            new_hooks=new,
            hook_score=hook_score
        )

    def _create_hook_content(
        self,
        hook_type: HookType,
        context: str,
        impact_level: int
    ) -> str:
        """创建钩子内容"""
        templates = {
            HookType.OPENING: (
                "在一个平静的早晨，{context} seemingly normal surface hides a dark secret "
                "that will change everything. But no one could have predicted what was coming..."
            ),
            HookType.CHAPTER_END: (
                "As the dust settled, {context} stood at a crossroads. "
                "The truth was within reach, but at what cost? The decision would echo for years to come."
            ),
            HookType.PLOT_TWIST: (
                "Just when it seemed like all was lost, {context} revealed a hidden truth. "
                "Everything they thought they knew was a lie, and the real battle was about to begin."
            ),
            HookType.MYSTERY: (
                "Deep in the shadows, {context} discovered something that shouldn't exist. "
                "The clue was tiny, but it could unravel the entire truth. Who was really behind it all?"
            ),
            HookType.THREAT: (
                "The warning came too late. {context} had walked into a trap, "
                "and now the clock was ticking. Would they escape, or become just another victim?"
            ),
            HookType.CHARACTER: (
                "The crowd stared as {context} stepped forward, revealing a scar that told a story "
                "no one could have guessed. This was more than just a moment - it was a turning point."
            ),
            HookType.PROMISE: (
                "The ancient prophecy had spoken of this moment. {context} now held the key to everything. "
                "But the path ahead was darker than anyone could imagine..."
            ),
            HookType.QUESTION: (
                "{context} stared at the letter, the words burning in their mind. "
                "How could this be? And more importantly - what would they do now?"
            ),
        }

        template = templates.get(hook_type, templates[HookType.CHAPTER_END])
        content = template.format(context=context or "the protagonist")

        # 调整长度基于impact_level
        if impact_level < 30:
            content = content[:80] + "..."
        elif impact_level > 70:
            content += " The consequences would ripple across the entire world!"

        return content

    def _extract_characters_from_context(self, context: str) -> List[str]:
        """从上下文提取字符"""
        # 简单实现：查找大写单词作为角色名
        words = context.split()
        characters = [w.strip(',') for w in words if w[0].isupper() and len(w) > 2]
        return list(set(characters))[:3]

    def _extract_beats_from_context(self, context: str) -> List[str]:
        """从上下文提取节拍"""
        return [f"beat_{len(context) % 100}"]

    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入（使用 EmbeddingAdapter）"""
        try:
            from ai_novels.llm.embedding_adapter import EmbeddingAdapter, EmbeddingConfig
            adapter = EmbeddingAdapter(EmbeddingConfig(
                provider="ollama",
                model="qwen2.5",
                dimension=768,
                normalize=True,
            ))
            return adapter.embed(text)
        except Exception:
            # 如果 EmbeddingAdapter 不可用，返回空向量（而非模拟数据）
            return []

    def _similarity_search(self, query_vector: List[float], top_k: int = 5) -> List[tuple]:
        """相似度搜索（简化实现）"""
        results = []
        for hook in self._hooks.values():
            if hook.embedding:
                # 简单余弦相似度
                score = self._cosine_similarity(query_vector, hook.embedding)
                results.append((hook, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        """计算余弦相似度"""
        if len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        if norm1 < 0.001 or norm2 < 0.001:
            return 0.0
        return dot / (norm1 * norm2)

    def _calculate_retention_score(self, hooks: List[Hook]) -> float:
        """计算留存率分数"""
        if not hooks:
            return 0.0

        # 基于钩子数量、平均影响力和类型多样性
        avg_impact = sum(h.impact_level for h in hooks) / len(hooks)
        type_diversity = len(set(h.hook_type for h in hooks))
        type_factor = min(type_diversity / 5.0, 1.0)

        score = (len(hooks) * 5) + (avg_impact * 0.3) + (type_diversity * 2)
        return min(100.0, score)

    def _predict_retention(self, total: int, active: int, avg_impact: float) -> float:
        """预测阅读留存率"""
        if total == 0:
            return 50.0

        base_rate = 50.0
        active_factor = min(active / max(total, 1), 1.0) * 20
        impact_factor = min(avg_impact / 100.0, 1.0) * 30

        return base_rate + active_factor + impact_factor

    def _calculate_hook_score(self, active: List[str], resolved: List[str]) -> int:
        """计算钩子分数"""
        active_score = len(active) * 10
        resolved_score = len(resolved) * 5
        return active_score + resolved_score

    def _calculate_resolution_rate(self) -> None:
        """计算钩子解决率"""
        total = len(self._hooks)
        resolved = len(self._resolved_hooks)
        if total > 0:
            self._resolution_rate = resolved / total

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

    def generate_hook(
        self,
        hook_type: str,
        chapter_id: str,
        context: str = "",
        impact_level: int = 50
    ) -> Optional[Hook]:
        """生成钩子（外部接口）"""
        try:
            hook = self._generate_hook(
                hook_type=HookType(hook_type.lower()),
                chapter_id=chapter_id,
                context=context,
                impact_level=impact_level
            )
            self._hooks[hook.hook_id] = hook
            self._active_hooks.append(hook.hook_id)
            return hook
        except Exception:
            return None

    def resolve_hook(self, hook_id: str, resolution: str = "") -> bool:
        """解决钩子（外部接口）"""
        if hook_id in self._hooks:
            hook = self._hooks[hook_id]
            hook.status = HookStatus.RESOLVED
            hook.resolved_at = time.time()
            hook.resolution = resolution
            if hook_id in self._active_hooks:
                self._active_hooks.remove(hook_id)
            self._resolved_hooks.append(hook_id)
            self._calculate_resolution_rate()
            return True
        return False

    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取钩子"""
        return self._hooks.get(hook_id)

    def get_active_hooks(self, chapter_id: str = None) -> List[Hook]:
        """获取激活的钩子"""
        hooks = [h for h in self._hooks.values() if h.status == HookStatus.ACTIVE]
        if chapter_id:
            hooks = [h for h in hooks if h.chapter_id == chapter_id]
        return hooks

    def get_resolved_hooks(self) -> List[Hook]:
        """获取已解决的钩子"""
        return [h for h in self._hooks.values() if h.status == HookStatus.RESOLVED]

    def get_all_hooks(self) -> Dict[str, Hook]:
        """获取所有钩子"""
        return self._hooks

    def get_hook_sequence(self, sequence_id: str) -> Optional[HookSequence]:
        """获取钩子序列"""
        return self._hook_sequences.get(sequence_id)

    def get_chapter_state(self, chapter_id: str) -> Optional[ChapterHookState]:
        """获取章节钩子状态"""
        return self._chapter_states.get(chapter_id)

    def export_hooks(self) -> Dict[str, Any]:
        """导出钩子数据"""
        return {
            "hooks": {k: v.to_dict() for k, v in self._hooks.items()},
            "sequences": {k: v.to_dict() for k, v in self._hook_sequences.items()},
            "chapter_states": {k: v.to_dict() for k, v in self._chapter_states.items()},
            "statistics": {
                "total": len(self._hooks),
                "active": len(self._active_hooks),
                "resolved": len(self._resolved_hooks),
                "generation_count": self._hook_generation_count,
                "resolution_rate": self._resolution_rate
            }
        }

    def reset(self) -> None:
        """重置智能体"""
        self._hooks.clear()
        self._hook_sequences.clear()
        self._chapter_states.clear()
        self._active_hooks.clear()
        self._resolved_hooks.clear()
        self._dropped_hooks.clear()
        self._last_hook_id = 0
        self._hook_generation_count = 0
        self._resolution_rate = 0.0
