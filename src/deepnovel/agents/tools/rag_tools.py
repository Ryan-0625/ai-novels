"""
RAG Agent 工具

Agent 可直接调用的检索增强生成工具集：
- DocumentIndexTool: 文档索引（添加知识到知识库）
- DocumentRetrieveTool: 文档检索（从知识库查询相关知识）
- KnowledgeBaseTool: 知识库管理（统计、清空等）

@file: agents/tools/rag_tools.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from deepnovel.agents.tools.tool_registry import tool
from deepnovel.llm.embedding_adapter import EmbeddingAdapter, EmbeddingConfig, EmbeddingProvider
from deepnovel.rag import RAGEngine, RAGConfig
from deepnovel.rag.chunker import Chunk, TextChunker
from deepnovel.vector_store import VectorStore
from deepnovel.vector_store.memory_store import InMemoryVectorStore


class DocumentIndexTool:
    """文档索引工具 — 将文本知识添加到知识库"""

    def __init__(self, rag_engine: Optional[RAGEngine] = None):
        self._rag = rag_engine or self._default_engine()

    def _default_engine(self) -> RAGEngine:
        """创建默认 RAG 引擎（使用 Mock embedding，适合测试）"""
        return RAGEngine(
            config=RAGConfig(
                embedding_provider=EmbeddingProvider.MOCK.value,
                embedding_model="mock-model",
                embedding_dimension=128,
            ),
            vector_store=InMemoryVectorStore(),
        )

    @tool(description="索引单篇文档到知识库，自动分块")
    async def index_document(
        self,
        text: str,
        *,
        source_id: Optional[str] = None,
        novel_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """索引单篇文档

        Args:
            text: 文档文本
            source_id: 来源标识
            novel_id: 小说标识
            metadata: 额外元数据

        Returns:
            {"chunk_ids": List[str], "chunk_count": int}
        """
        chunk_ids = await self._rag.add_document(
            text,
            source_id=source_id,
            novel_id=novel_id,
            metadata=metadata,
        )
        return {
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids),
            "source_id": source_id,
        }

    @tool(description="批量索引多篇文档")
    async def index_documents(
        self,
        texts: List[str],
        *,
        source_ids: Optional[List[str]] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """批量索引文档

        Returns:
            {"results": List[dict], "total_chunks": int}
        """
        results = await self._rag.add_documents(
            texts,
            source_ids=source_ids,
            novel_id=novel_id,
        )
        total = sum(len(r) for r in results)
        return {
            "results": [
                {"chunk_ids": r, "chunk_count": len(r)}
                for r in results
            ],
            "total_chunks": total,
        }

    @tool(description="直接索引预分块文档")
    async def index_chunks(
        self,
        chunks: List[Chunk],
        *,
        source_id: Optional[str] = None,
        novel_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """直接索引预分块文档

        Returns:
            {"chunk_ids": List[str], "chunk_count": int}
        """
        chunk_ids = await self._rag.add_chunks(
            chunks,
            source_id=source_id,
            novel_id=novel_id,
        )
        return {
            "chunk_ids": chunk_ids,
            "chunk_count": len(chunk_ids),
        }

    @tool(description="索引世界观设定文本")
    async def index_world_lore(
        self,
        lore_text: str,
        world_id: str,
        *,
        category: str = "general",
    ) -> Dict[str, Any]:
        """索引世界观设定文本

        专为世界观知识设计的索引方法。

        Args:
            lore_text: 设定文本
            world_id: 世界标识
            category: 设定类别

        Returns:
            {"chunk_ids": List[str], "chunk_count": int}
        """
        return await self.index_document(
            lore_text,
            source_id=f"world_lore:{world_id}:{category}",
            novel_id=world_id,
            metadata={"category": category, "type": "world_lore"},
        )

    @tool(description="索引角色设定文本")
    async def index_character_profile(
        self,
        profile_text: str,
        character_id: str,
        novel_id: str,
    ) -> Dict[str, Any]:
        """索引角色设定文本

        Args:
            profile_text: 角色设定文本
            character_id: 角色标识
            novel_id: 小说标识

        Returns:
            {"chunk_ids": List[str], "chunk_count": int}
        """
        return await self.index_document(
            profile_text,
            source_id=f"character:{character_id}",
            novel_id=novel_id,
            metadata={
                "character_id": character_id,
                "type": "character_profile",
            },
        )


class DocumentRetrieveTool:
    """文档检索工具 — 从知识库查询相关知识"""

    def __init__(self, rag_engine: Optional[RAGEngine] = None):
        self._rag = rag_engine or self._default_engine()

    def _default_engine(self) -> RAGEngine:
        return RAGEngine(
            config=RAGConfig(
                embedding_provider=EmbeddingProvider.MOCK.value,
                embedding_model="mock-model",
                embedding_dimension=128,
            ),
            vector_store=InMemoryVectorStore(),
        )

    @tool(description="检索知识库，返回相关知识")
    async def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        strategy: str = "vector",
        filters: Optional[Dict[str, Any]] = None,
        keywords: Optional[List[str]] = None,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """检索知识库

        Args:
            query: 查询文本
            top_k: 返回结果数
            strategy: "vector" | "hybrid" | "diverse"
            filters: 元数据过滤条件
            keywords: 混合检索关键词
            min_score: 最低分数

        Returns:
            RAGResult 字典
        """
        result = await self._rag.query(
            query,
            top_k=top_k,
            strategy=strategy,
            filters=filters,
            keywords=keywords,
            min_score=min_score,
        )
        return result.to_dict()

    @tool(description="多查询检索，融合多个相关查询的结果")
    async def search_multi_query(
        self,
        queries: List[str],
        *,
        top_k_per_query: int = 3,
        final_top_k: int = 5,
    ) -> Dict[str, Any]:
        """多查询检索

        适合复杂问题分解为多个子查询。

        Args:
            queries: 多个查询文本
            top_k_per_query: 每个查询返回数
            final_top_k: 最终返回数

        Returns:
            RAGResult 字典
        """
        result = await self._rag.query_multi(
            queries,
            top_k_per_query=top_k_per_query,
            final_top_k=final_top_k,
        )
        return result.to_dict()

    @tool(description="检索世界观设定")
    async def search_world_lore(
        self,
        query: str,
        world_id: str,
        *,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """检索世界观设定

        Args:
            query: 查询文本
            world_id: 世界标识
            top_k: 返回结果数
            category: 可选类别过滤

        Returns:
            RAGResult 字典
        """
        filters = {"novel_id": world_id, "type": "world_lore"}
        if category:
            filters["category"] = category

        return await self.search(
            query,
            top_k=top_k,
            filters=filters,
        )

    @tool(description="检索角色相关知识")
    async def search_character_knowledge(
        self,
        query: str,
        character_id: str,
        novel_id: str,
        *,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """检索角色相关知识

        Args:
            query: 查询文本
            character_id: 角色标识
            novel_id: 小说标识
            top_k: 返回结果数

        Returns:
            RAGResult 字典
        """
        filters = {
            "novel_id": novel_id,
            "type": "character_profile",
            "character_id": character_id,
        }
        return await self.search(
            query,
            top_k=top_k,
            filters=filters,
        )

    @tool(description="构建 LLM 上下文，返回格式化文本")
    async def build_context(
        self,
        query: str,
        *,
        top_k: int = 5,
        max_tokens: int = 2000,
        include_sources: bool = False,
    ) -> str:
        """构建 LLM 上下文

        直接返回格式化后的上下文文本，可直接插入 Prompt。

        Args:
            query: 查询文本
            top_k: 返回结果数
            max_tokens: 最大 token 数
            include_sources: 是否包含来源标注

        Returns:
            格式化上下文文本
        """
        result = await self._rag.query(query, top_k=top_k)
        return self._rag.build_prompt_context(
            result,
            max_tokens=max_tokens,
            include_sources=include_sources,
        )


class KnowledgeBaseTool:
    """知识库管理工具 — 统计、清空、配置"""

    def __init__(self, rag_engine: Optional[RAGEngine] = None):
        self._rag = rag_engine or self._default_engine()

    def _default_engine(self) -> RAGEngine:
        return RAGEngine(
            config=RAGConfig(
                embedding_provider=EmbeddingProvider.MOCK.value,
                embedding_model="mock-model",
                embedding_dimension=128,
            ),
            vector_store=InMemoryVectorStore(),
        )

    @tool(description="获取知识库统计信息")
    async def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计"""
        return await self._rag.get_stats()

    @tool(description="清空知识库")
    async def clear(self) -> bool:
        """清空知识库"""
        return await self._rag.clear()

    @tool(description="按来源删除文档")
    async def delete_by_source(self, source_id: str) -> int:
        """按来源删除"""
        return await self._rag.delete_by_source(source_id)

    @tool(description="获取当前配置")
    async def get_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return self._rag.config.to_dict()
