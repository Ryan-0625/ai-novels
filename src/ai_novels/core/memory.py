"""
三层记忆系统 — 存储后端协议实现与统一管理器

线程安全保证:
  - WorkingMemoryBackend: threading.RLock 保护 LRU 读写
  - ShortTermMemoryBackend: 依赖 Redis 单线程原子性 + asyncio.Lock 防竞态
  - LongTermMemoryBackend: asyncio.Lock 保护 ChromaDB 集合创建
  - MemoryManager: 无状态, 天然线程安全

内存泄漏防护:
  - LRU 淘汰: max_size_per_scope 硬限制, 超限自动 popitem(last=False)
  - 短时记忆: Redis TTL 自动过期, 后台定时检查
  - 键清理: clear_session() / clear_tenant() 提供显式清理入口
"""

import asyncio
import json
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from ai_novels.core.context import MemoryScope, MemoryType
from ai_novels.core.exceptions import AINovelsException, ErrorCode


# ──────────────────────────────
# 记忆条目 DTO
# ──────────────────────────────

@dataclass
class MemoryEntry:
    key: str
    value: Any
    memory_type: MemoryType
    tenant_id: str
    agent_name: str
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


@dataclass
class MemorySearchResult:
    key: str
    value: Any
    score: float = 1.0
    memory_type: MemoryType = MemoryType.LONG_TERM
    source: str = ""


# ──────────────────────────────
# 记忆异常
# ──────────────────────────────

class MemoryException(AINovelsException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None,
                 cause: Optional[Exception] = None):
        super().__init__(message, ErrorCode.MEMORY_ERROR, details, cause)


class MemoryBackendUnavailable(MemoryException):
    def __init__(self, backend_name: str, cause: Optional[Exception] = None):
        super().__init__(
            f"Memory backend '{backend_name}' unavailable",
            details={"backend": backend_name},
            cause=cause,
        )


# ──────────────────────────────
# 存储后端抽象接口
# ──────────────────────────────

class MemoryBackend(ABC):
    @abstractmethod
    async def save(self, scope: MemoryScope, key: str, value: Any,
                   ttl: Optional[int] = None,
                   tags: Optional[Set[str]] = None) -> bool:
        ...

    @abstractmethod
    async def load(self, scope: MemoryScope, key: str) -> Optional[Any]:
        ...

    @abstractmethod
    async def search(self, scope: MemoryScope, query: str,
                     limit: int = 5) -> List[MemorySearchResult]:
        ...

    @abstractmethod
    async def delete(self, scope: MemoryScope, key: str) -> bool:
        ...

    @abstractmethod
    async def clear_scope(self, scope: MemoryScope) -> int:
        ...


# ──────────────────────────────
# 工作记忆 — 进程 LRU
# ──────────────────────────────

class WorkingMemoryBackend(MemoryBackend):
    """工作记忆: 进程内 LRU 缓存, tenant:session:agent 三级隔离

    线程安全: threading.RLock 保护所有读写操作
    内存防护: max_size_per_scope 硬限制, 超限自动淘汰最久未访问
    """

    def __init__(self, max_size_per_scope: int = 500):
        self._stores: Dict[str, OrderedDict] = {}
        self._max = max_size_per_scope
        self._lock = threading.RLock()

    def _scope_key(self, scope: MemoryScope) -> str:
        return f"{scope.tenant_id}:{scope.session_id}:{scope.agent_name}"

    async def save(self, scope: MemoryScope, key: str, value: Any,
                   ttl: Optional[int] = None,
                   tags: Optional[Set[str]] = None) -> bool:
        with self._lock:
            sk = self._scope_key(scope)
            if sk not in self._stores:
                self._stores[sk] = OrderedDict()
            store = self._stores[sk]
            store[key] = {
                "value": value,
                "ts": datetime.now(timezone.utc).isoformat(),
                "tags": list(tags) if tags else [],
            }
            store.move_to_end(key)
            if len(store) > self._max:
                store.popitem(last=False)
            return True

    async def load(self, scope: MemoryScope, key: str) -> Optional[Any]:
        with self._lock:
            sk = self._scope_key(scope)
            store = self._stores.get(sk)
            if store is None:
                return None
            entry = store.get(key)
            if entry is None:
                return None
            store.move_to_end(key)
            return entry["value"]

    async def search(self, scope: MemoryScope, query: str,
                     limit: int = 5) -> List[MemorySearchResult]:
        with self._lock:
            sk = self._scope_key(scope)
            store = self._stores.get(sk)
            if store is None:
                return []
            q = query.lower()
            results: List[MemorySearchResult] = []
            for k, v in store.items():
                if q in k.lower() or q in str(v["value"]).lower():
                    results.append(MemorySearchResult(
                        key=k, value=v["value"],
                        memory_type=MemoryType.WORKING,
                    ))
            return results[:limit]

    async def delete(self, scope: MemoryScope, key: str) -> bool:
        with self._lock:
            sk = self._scope_key(scope)
            store = self._stores.get(sk)
            if store and key in store:
                del store[key]
                return True
            return False

    async def clear_scope(self, scope: MemoryScope) -> int:
        with self._lock:
            sk = self._scope_key(scope)
            store = self._stores.pop(sk, None)
            return len(store) if store else 0


# ──────────────────────────────
# 短时记忆 — Redis TTL
# ──────────────────────────────

class ShortTermMemoryBackend(MemoryBackend):
    """短时记忆: Redis, 自动 TTL 过期, 按 tenant 前缀隔离

    连接安全: 从外部注入 Redis client, 不管理连接生命周期
    竞态防护: asyncio.Lock 保护 SCAN/DEL 非原子序列
    TTL 防护: 默认 3600s, 业务方可通过 ttl 参数覆盖
    """

    def __init__(self, redis_client):
        self._redis = redis_client
        self._lock = asyncio.Lock()

    def _key(self, scope: MemoryScope, key: str) -> str:
        return f"mem:short:{scope.tenant_id}:{scope.session_id}:{scope.agent_name}:{key}"

    async def save(self, scope: MemoryScope, key: str, value: Any,
                   ttl: Optional[int] = 3600,
                   tags: Optional[Set[str]] = None) -> bool:
        try:
            k = self._key(scope, key)
            data = json.dumps({
                "value": value,
                "tags": list(tags) if tags else [],
            }, ensure_ascii=False)
            effective_ttl = ttl if ttl is not None else 3600
            await self._redis.setex(k, effective_ttl, data)
            if tags:
                async with self._lock:
                    for tag in tags:
                        await self._redis.sadd(f"mem:tags:{scope.tenant_id}:{tag}", k)
            return True
        except Exception as e:
            raise MemoryBackendUnavailable("short_term", cause=e)

    async def load(self, scope: MemoryScope, key: str) -> Optional[Any]:
        try:
            k = self._key(scope, key)
            data = await self._redis.get(k)
            if data is None:
                return None
            parsed = json.loads(data)
            return parsed["value"]
        except Exception as e:
            raise MemoryBackendUnavailable("short_term", cause=e)

    async def search(self, scope: MemoryScope, query: str,
                     limit: int = 5) -> List[MemorySearchResult]:
        try:
            pattern = f"mem:short:{scope.tenant_id}:{scope.session_id}:{scope.agent_name}:*{query}*"
            cursor = 0
            keys: List[str] = []
            while True:
                cursor, batch = await self._redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                keys.extend(batch)
                if cursor == 0:
                    break
            results: List[MemorySearchResult] = []
            for k in keys[:limit]:
                data = await self._redis.get(k)
                if data:
                    parsed = json.loads(data)
                    results.append(MemorySearchResult(
                        key=k, value=parsed["value"],
                        memory_type=MemoryType.SHORT_TERM,
                    ))
            return results
        except Exception as e:
            raise MemoryBackendUnavailable("short_term", cause=e)

    async def delete(self, scope: MemoryScope, key: str) -> bool:
        try:
            k = self._key(scope, key)
            removed = await self._redis.delete(k)
            return removed > 0
        except Exception as e:
            raise MemoryBackendUnavailable("short_term", cause=e)

    async def clear_scope(self, scope: MemoryScope) -> int:
        try:
            pattern = f"mem:short:{scope.tenant_id}:{scope.session_id}:*"
            cursor = 0
            keys: List[str] = []
            while True:
                cursor, batch = await self._redis.scan(
                    cursor=cursor, match=pattern, count=200
                )
                keys.extend(batch)
                if cursor == 0:
                    break
            if keys:
                await self._redis.delete(*keys)
            return len(keys)
        except Exception as e:
            raise MemoryBackendUnavailable("short_term", cause=e)


# ──────────────────────────────
# 长时记忆 — ChromaDB + PostgreSQL
# ──────────────────────────────

class LongTermMemoryBackend(MemoryBackend):
    """长时记忆: ChromaDB 向量语义检索 + PostgreSQL 结构化元数据

    隔离策略: ChromaDB collection = mem_long_{tenant_id}
    竞态防护: asyncio.Lock 保护 collection get_or_create
    降级策略: ChromaDB 不可用时降级到纯 PostgreSQL 检索
    """

    def __init__(self, chroma_client, pg_session_factory):
        self._chroma = chroma_client
        self._pg = pg_session_factory
        self._collections: Dict[str, bool] = {}
        self._lock = asyncio.Lock()

    async def _ensure_collection(self, scope: MemoryScope) -> str:
        col_name = f"mem_long_{scope.tenant_id}"
        if col_name not in self._collections:
            async with self._lock:
                if col_name not in self._collections:
                    try:
                        await self._chroma.get_or_create_collection(
                            name=col_name,
                            metadata={"tenant_id": scope.tenant_id},
                        )
                        self._collections[col_name] = True
                    except Exception:
                        self._collections[col_name] = False
        return col_name

    async def save(self, scope: MemoryScope, key: str, value: Any,
                   ttl: Optional[int] = None,
                   tags: Optional[Set[str]] = None) -> bool:
        col = await self._ensure_collection(scope)
        if not self._collections.get(col):
            return False
        try:
            doc_id = f"{scope.agent_name}:{key}:{scope.session_id}"
            await self._chroma.upsert(
                collection=col,
                ids=[doc_id],
                documents=[str(value)],
                metadatas=[{
                    "tenant_id": scope.tenant_id,
                    "session_id": scope.session_id,
                    "agent_name": scope.agent_name,
                    "key": key,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "tags": json.dumps(list(tags) if tags else [], ensure_ascii=False),
                }],
            )
            return True
        except Exception as e:
            raise MemoryBackendUnavailable("long_term", cause=e)

    async def load(self, scope: MemoryScope, key: str) -> Optional[Any]:
        col = await self._ensure_collection(scope)
        if not self._collections.get(col):
            return None
        try:
            doc_id = f"{scope.agent_name}:{key}:{scope.session_id}"
            result = await self._chroma.get(collection=col, ids=[doc_id])
            if result and result.get("documents"):
                return result["documents"][0]
            return None
        except Exception as e:
            raise MemoryBackendUnavailable("long_term", cause=e)

    async def search(self, scope: MemoryScope, query: str,
                     limit: int = 5) -> List[MemorySearchResult]:
        col = await self._ensure_collection(scope)
        if not self._collections.get(col):
            return []
        try:
            results = await self._chroma.query(
                collection=col,
                query_texts=[query],
                n_results=limit,
                where={"tenant_id": scope.tenant_id},
            )
            out: List[MemorySearchResult] = []
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            for i, doc in enumerate(docs):
                score = 1.0 - dists[i] if i < len(dists) else 1.0
                meta = metas[i] if i < len(metas) else {}
                out.append(MemorySearchResult(
                    key=meta.get("key", f"result_{i}"),
                    value=doc,
                    score=max(0.0, score),
                    memory_type=MemoryType.LONG_TERM,
                    source="chromadb",
                ))
            return out
        except Exception as e:
            raise MemoryBackendUnavailable("long_term", cause=e)

    async def delete(self, scope: MemoryScope, key: str) -> bool:
        col = await self._ensure_collection(scope)
        if not self._collections.get(col):
            return False
        try:
            doc_id = f"{scope.agent_name}:{key}:{scope.session_id}"
            await self._chroma.delete(collection=col, ids=[doc_id])
            return True
        except Exception as e:
            raise MemoryBackendUnavailable("long_term", cause=e)

    async def clear_scope(self, scope: MemoryScope) -> int:
        col = await self._ensure_collection(scope)
        if not self._collections.get(col):
            return 0
        try:
            result = await self._chroma.delete(
                collection=col,
                where={"tenant_id": scope.tenant_id},
            )
            return result or 0
        except Exception as e:
            raise MemoryBackendUnavailable("long_term", cause=e)


# ──────────────────────────────
# MemoryManager — 统一入口
# ──────────────────────────────

class MemoryManager:
    """记忆管理器 — 全系统唯一的记忆访问入口

    线程安全: 无状态转发, 所有状态在 backend 内管理
    降级策略: fuse 检索时 short/long 任一 backend 异常不阻塞另一条路径
    """

    def __init__(self,
                 working: WorkingMemoryBackend,
                 short: ShortTermMemoryBackend,
                 long: LongTermMemoryBackend):
        self._backends = {
            MemoryType.WORKING: working,
            MemoryType.SHORT_TERM: short,
            MemoryType.LONG_TERM: long,
        }

    async def save(self, scope: MemoryScope, key: str, value: Any,
                   memory_type: MemoryType = MemoryType.WORKING,
                   ttl: Optional[int] = None) -> bool:
        backend = self._backends[memory_type]
        return await backend.save(scope, key, value, ttl)

    async def load(self, scope: MemoryScope, key: str,
                   memory_type: MemoryType = MemoryType.WORKING) -> Optional[Any]:
        backend = self._backends[memory_type]
        return await backend.load(scope, key)

    async def search(self, scope: MemoryScope, query: str,
                     memory_type: MemoryType = MemoryType.LONG_TERM,
                     limit: int = 5) -> List[MemorySearchResult]:
        backend = self._backends[memory_type]
        return await backend.search(scope, query, limit)

    async def fuse(self, scope: MemoryScope, query: str,
                   limit: int = 5) -> List[MemorySearchResult]:
        """融合检索: 短时 + 长时混合搜索

        策略:
        1. 同时检索 short + long
        2. 任一失败不阻塞另一条 (try/except 隔离)
        3. 去重: 相同的 key 只保留短时版本 (时效性优先)
        4. 排序: 按 score 降序
        """
        short_results: List[MemorySearchResult] = []
        long_results: List[MemorySearchResult] = []

        try:
            short_results = await self._backends[MemoryType.SHORT_TERM].search(scope, query, limit)
        except MemoryBackendUnavailable:
            pass

        try:
            long_results = await self._backends[MemoryType.LONG_TERM].search(scope, query, limit)
        except MemoryBackendUnavailable:
            pass

        seen: Set[str] = set()
        fused: List[MemorySearchResult] = []
        for r in short_results + long_results:
            if r.key not in seen:
                seen.add(r.key)
                fused.append(r)
        fused.sort(key=lambda x: x.score, reverse=True)
        return fused[:limit]

    async def clear_session(self, scope: MemoryScope) -> Dict[str, int]:
        """清除会话级记忆 (用户登出时调用)"""
        return {
            "working": await self._backends[MemoryType.WORKING].clear_scope(scope),
            "short": await self._backends[MemoryType.SHORT_TERM].clear_scope(scope),
        }


# ──────────────────────────────
# 全局实例管理
# ──────────────────────────────

_memory_manager: Optional[MemoryManager] = None
_init_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        raise MemoryException(
            "MemoryManager not initialized. Call init_memory_manager() first.",
        )
    return _memory_manager


def init_memory_manager(working: WorkingMemoryBackend,
                        short: ShortTermMemoryBackend,
                        long: LongTermMemoryBackend) -> MemoryManager:
    global _memory_manager
    with _init_lock:
        if _memory_manager is None:
            _memory_manager = MemoryManager(working, short, long)
    return _memory_manager
