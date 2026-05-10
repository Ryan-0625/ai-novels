"""
世界状态机工具 — Agent 可直接调用

功能：
1. 查询实体状态（支持时间点）
2. 批量状态设置（事务）
3. 效果传播
4. 反事实分支管理
5. 状态快照/恢复

@file: agents/tools/world_state_tool.py
@date: 2026-04-29
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Fact
from deepnovel.services import WorldStateService, EventService
from deepnovel.services.world_rule_service import WorldRuleService


class WorldStateTool:
    """世界状态机工具 — Agent 可直接调用"""

    def __init__(
        self,
        world_service: Optional[WorldStateService] = None,
        event_service: Optional[EventService] = None,
        rule_service: Optional[WorldRuleService] = None,
    ):
        self._world = world_service or WorldStateService()
        self._events = event_service or EventService()
        self._rules = rule_service or WorldRuleService()

    async def query_state(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
    ) -> Optional[Dict[str, Any]]:
        """查询实体当前状态"""
        fact = await self._world.get_current_state(session, subject_id, predicate)
        return fact.to_dict() if fact else None

    async def query_state_at_time(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: str,
        timestamp: datetime,
    ) -> Optional[Dict[str, Any]]:
        """时间旅行查询 — 查询指定时间点的状态"""
        fact = await self._world.get_state_at_time(session, subject_id, predicate, timestamp)
        return fact.to_dict() if fact else None

    async def query_entity_facts(
        self,
        session: AsyncSession,
        subject_id: str,
        predicate: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询实体的所有事实"""
        facts = await self._world.get_entity_facts(session, subject_id, predicate)
        return [f.to_dict() for f in facts]

    async def set_state(
        self,
        session: AsyncSession,
        novel_id: str,
        subject_id: str,
        predicate: str,
        value: Dict[str, Any],
        *,
        confidence: float = 1.0,
        source: str = "simulation",
        chapter_id: Optional[str] = None,
        inference_chain: Optional[List[str]] = None,
        auto_propagate: bool = True,
    ) -> Dict[str, Any]:
        """设置实体状态（原子操作）"""
        fact = await self._world.set_fact(
            session,
            novel_id=novel_id,
            subject_id=subject_id,
            predicate=predicate,
            value=value,
            confidence=confidence,
            source=source,
            chapter_id=chapter_id,
            inference_chain=inference_chain,
        )

        # 自动传播效果
        propagated = []
        if auto_propagate:
            propagated = await self._propagate_effects(session, novel_id, fact)

        result = fact.to_dict()
        result["propagated"] = [p.to_dict() for p in propagated]
        return result

    async def batch_set_state(
        self,
        session: AsyncSession,
        novel_id: str,
        changes: List[Dict[str, Any]],
        source: str = "simulation",
    ) -> List[Dict[str, Any]]:
        """批量设置状态"""
        results = []
        for change in changes:
            result = await self.set_state(
                session,
                novel_id=novel_id,
                subject_id=change["subject_id"],
                predicate=change["predicate"],
                value=change["value"],
                source=source,
                auto_propagate=False,  # 延迟传播
            )
            results.append(result)

        # 批量传播
        for i, change in enumerate(changes):
            fact = await self._world.get_current_state(
                session, change["subject_id"], change["predicate"]
            )
            if fact:
                propagated = await self._propagate_effects(session, novel_id, fact)
                results[i]["propagated"] = [p.to_dict() for p in propagated]

        return results

    async def _propagate_effects(
        self,
        session: AsyncSession,
        novel_id: str,
        fact: Fact,
        depth: int = 3,
        visited: Optional[Set[str]] = None,
    ) -> List[Fact]:
        """传播事实效果（连锁反应）"""
        if visited is None:
            visited = set()

        if fact.id in visited or depth <= 0:
            return []

        visited.add(fact.id)
        propagated = []

        # 1. 应用世界规则
        rules = await self._rules.find_applicable_rules(
            session, novel_id, fact.predicate
        )
        for rule in rules:
            actions = await self._rules.evaluate_rules(
                session, novel_id, fact.predicate, {"predicate": fact.predicate, "value": fact.object_value}
            )
            for action in actions:
                action_def = action.get("action", {})
                if "set_fact" in action_def:
                    sf = action_def["set_fact"]
                    new_fact = await self._world.set_fact(
                        session,
                        novel_id=novel_id,
                        subject_id=sf.get("subject", fact.subject_id),
                        predicate=sf["predicate"],
                        value=sf["value"],
                        source="rule",
                        inference_chain=[f"rule:{action['rule_id']}"],
                    )
                    propagated.append(new_fact)

        # 2. 递归传播
        for new_fact in propagated:
            sub_propagated = await self._propagate_effects(
                session, novel_id, new_fact, depth - 1, visited
            )
            propagated.extend(sub_propagated)

        return propagated

    async def create_branch(
        self,
        session: AsyncSession,
        novel_id: str,
        base_branch: str,
        changes: List[Dict[str, Any]],
        name: str = "假设分析",
    ) -> str:
        """创建反事实分支"""
        return await self._world.create_counterfactual_branch(
            session, novel_id, base_branch, changes, name
        )

    async def get_branch_facts(
        self,
        session: AsyncSession,
        branch_id: str,
    ) -> List[Dict[str, Any]]:
        """获取反事实分支的所有事实"""
        facts = await self._world.get_branch_facts(session, branch_id)
        return [f.to_dict() for f in facts]

    async def compare_branches(
        self,
        session: AsyncSession,
        branch_a: str,
        branch_b: str,
    ) -> Dict[str, Any]:
        """比较两个反事实分支的差异"""
        facts_a = await self._world.get_branch_facts(session, branch_a)
        facts_b = await self._world.get_branch_facts(session, branch_b)

        # 构建状态映射
        state_a = {f"{f.subject_id}:{f.predicate}": f for f in facts_a}
        state_b = {f"{f.subject_id}:{f.predicate}": f for f in facts_b}

        all_keys = set(state_a.keys()) | set(state_b.keys())
        differences = []

        for key in all_keys:
            fa = state_a.get(key)
            fb = state_b.get(key)
            if fa and fb:
                if fa.object_value != fb.object_value:
                    differences.append({
                        "key": key,
                        "branch_a": fa.object_value,
                        "branch_b": fb.object_value,
                    })
            elif fa:
                differences.append({
                    "key": key,
                    "branch_a": fa.object_value,
                    "branch_b": None,
                })
            elif fb:
                differences.append({
                    "key": key,
                    "branch_a": None,
                    "branch_b": fb.object_value,
                })

        return {
            "branch_a": branch_a,
            "branch_b": branch_b,
            "differences": differences,
            "difference_count": len(differences),
        }
