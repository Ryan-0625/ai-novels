"""
文档分块器 — 多种分块策略

支持:
- fixed: 固定大小分块
- paragraph: 段落分块
- sentence: 句子分块
- semantic: 语义分块（基于句子边界+重叠窗口）

@file: rag/chunker.py
@date: 2026-04-29
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, List, Optional


class ChunkStrategy(Enum):
    """分块策略"""

    FIXED = "fixed"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"


@dataclass
class Chunk:
    """文本块"""

    content: str
    index: int = 0
    start_pos: int = 0
    end_pos: int = 0
    metadata: Optional[dict] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def word_count(self) -> int:
        return len(self.content.split())

    @property
    def char_count(self) -> int:
        return len(self.content)

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "index": self.index,
            "start_pos": self.start_pos,
            "end_pos": self.end_pos,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "metadata": self.metadata,
        }


class TextChunker:
    """文本分块器"""

    # 句子分隔符模式
    SENTENCE_DELIMITERS = re.compile(r"[。！？.!?;；]\s*")
    # 段落分隔符
    PARAGRAPH_DELIMITERS = re.compile(r"\n\s*\n")

    def __init__(
        self,
        strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 50,
    ):
        self.strategy = strategy
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, text: str, **metadata) -> List[Chunk]:
        """分块入口"""
        if self.strategy == ChunkStrategy.FIXED:
            return self._chunk_fixed(text, **metadata)
        elif self.strategy == ChunkStrategy.PARAGRAPH:
            return self._chunk_paragraph(text, **metadata)
        elif self.strategy == ChunkStrategy.SENTENCE:
            return self._chunk_sentence(text, **metadata)
        elif self.strategy == ChunkStrategy.SEMANTIC:
            return self._chunk_semantic(text, **metadata)
        else:
            return self._chunk_fixed(text, **metadata)

    def _chunk_fixed(self, text: str, **metadata) -> List[Chunk]:
        """固定大小分块"""
        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # 尝试在单词边界截断
            if end < len(text):
                while end > start and text[end - 1] not in " \n":
                    end -= 1
                if end == start:
                    end = min(start + self.chunk_size, len(text))

            content = text[start:end].strip()
            if len(content) >= self.min_chunk_size:
                chunks.append(
                    Chunk(
                        content=content,
                        index=index,
                        start_pos=start,
                        end_pos=end,
                        metadata=metadata.copy(),
                    )
                )
                index += 1

            if end < len(text):
                # 限制 overlap 不超过 chunk_size 的一半，确保窗口滑动前进
                effective_overlap = min(self.chunk_overlap, self.chunk_size // 2)
                start = max(0, end - effective_overlap)
            else:
                start = end

        return chunks

    def _chunk_paragraph(self, text: str, **metadata) -> List[Chunk]:
        """段落分块"""
        paragraphs = self.PARAGRAPH_DELIMITERS.split(text)
        chunks = []

        current = ""
        start_pos = 0
        index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current) + len(para) > self.chunk_size and current:
                chunks.append(
                    Chunk(
                        content=current.strip(),
                        index=index,
                        start_pos=start_pos,
                        end_pos=start_pos + len(current),
                        metadata=metadata.copy(),
                    )
                )
                index += 1
                start_pos += len(current)
                current = para
            else:
                current = (current + "\n\n" + para).strip() if current else para

        if current and len(current) >= self.min_chunk_size:
            chunks.append(
                Chunk(
                    content=current,
                    index=index,
                    start_pos=start_pos,
                    end_pos=start_pos + len(current),
                    metadata=metadata.copy(),
                )
            )

        return chunks

    def _chunk_sentence(self, text: str, **metadata) -> List[Chunk]:
        """句子分块"""
        sentences = self.SENTENCE_DELIMITERS.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]
        chunks = []

        current = ""
        start_pos = 0
        index = 0

        for sent in sentences:
            if len(current) + len(sent) > self.chunk_size and current:
                chunks.append(
                    Chunk(
                        content=current.strip(),
                        index=index,
                        start_pos=start_pos,
                        end_pos=start_pos + len(current),
                        metadata=metadata.copy(),
                    )
                )
                index += 1
                start_pos += len(current)
                current = sent
            else:
                current = (current + sent + "。") if current else sent + "。"

        if current and len(current) >= self.min_chunk_size:
            chunks.append(
                Chunk(
                    content=current,
                    index=index,
                    start_pos=start_pos,
                    end_pos=start_pos + len(current),
                    metadata=metadata.copy(),
                )
            )

        return chunks

    def _chunk_semantic(self, text: str, **metadata) -> List[Chunk]:
        """语义分块：句子边界 + 重叠窗口"""
        sentences = self.SENTENCE_DELIMITERS.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        chunks = []
        current_sentences: List[str] = []
        current_length = 0
        start_pos = 0
        index = 0

        for sent in sentences:
            sent_len = len(sent)

            if current_length + sent_len > self.chunk_size and current_sentences:
                content = "。".join(current_sentences) + "。"
                if len(content) >= self.min_chunk_size:
                    chunks.append(
                        Chunk(
                            content=content,
                            index=index,
                            start_pos=start_pos,
                            end_pos=start_pos + len(content),
                            metadata=metadata.copy(),
                        )
                    )
                    index += 1

                # 保留重叠部分
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_sentences):
                    if overlap_length + len(s) > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_length += len(s)

                current_sentences = overlap_sentences + [sent]
                current_length = overlap_length + sent_len
                start_pos += len(content) - overlap_length
            else:
                current_sentences.append(sent)
                current_length += sent_len

        # 处理剩余
        if current_sentences:
            content = "。".join(current_sentences) + "。"
            if len(content) >= self.min_chunk_size:
                chunks.append(
                    Chunk(
                        content=content,
                        index=index,
                        start_pos=start_pos,
                        end_pos=start_pos + len(content),
                        metadata=metadata.copy(),
                    )
                )

        return chunks

    def chunk_batch(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> List[List[Chunk]]:
        """批量分块"""
        metadatas = metadatas or [{}] * len(texts)
        return [self.chunk(t, **m) for t, m in zip(texts, metadatas)]
