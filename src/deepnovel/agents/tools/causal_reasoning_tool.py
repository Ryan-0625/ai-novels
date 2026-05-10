"""
因果推理工具 — Agent 可直接调用

功能：
1. 追溯原因（多策略）
2. 预测后果
3. 生成因果解释
4. 反事实分析（如果...会怎样）

@file: agents/tools/causal_reasoning_tool.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Event
from deepnovel.services import EventService, WorldStateService


class CausalReasoningTool:
    """因果推理工具 — Agent 可直接调用"""

    def __init__(
        self,
        event_service: Optional[EventService] = None,
        world_service: Optional[WorldStateService] = None,
    ):
        self._events = event_service or EventService()
        self._world = world_service or WorldStateService()

    async def trace_causes(
        self,
        session: AsyncSession,
        event_id: str,
        depth: int = 3,
        strategy: str = "primary",
    ) -> Dict[str, Any]:
        """追溯原因（多策略）

        Args:
            strategy: "primary" | "all" | "necessary" | "sufficient"
        """
        event = await self._events._repo.get_by_id(session, event_id)
        if not event:
            return {"error": "事件不存在", "event_id": event_id}

        # 获取因果链
        chain = await self._events.trace_causes(session, event_id, depth=depth)

        # 根据策略处理
        if strategy == "primary":
            # 主路径：最强因果链
            chain = self._filter_primary_chain(chain, event)
        elif strategy == "necessary":
            # 必要条件：筛选高 causal_strength 的
            chain = [c for c in chain if c.causal_strength >= 0.8]
        elif strategy == "sufficient":
            # 充分条件：筛选直接导致目标的
            chain = [c for c in chain if event_id in c.causes]

        return {
            "event_id": event_id,
            "event_description": event.description,
            "strategy": strategy,
            "depth": depth,
            "causes": [c.to_dict() for c in chain],
            "cause_count": len(chain),
            "root_causes": [c.to_dict() for c in chain if not c.caused_by],
        }

    def _filter_primary_chain(
        self,
        chain: List[Event],
        target_event: Event,
    ) -> List[Event]:
        """筛选主因果链（最强路径）"""
        if not chain:
            return []

        # 按 causal_strength 排序，取最强路径
        sorted_chain = sorted(chain, key=lambda e: e.causal_strength, reverse=True)

        # 构建主链：从目标事件回溯到根因
        primary = []
        current_ids = {target_event.id}
        visited = set()

        for event in sorted_chain:
            if event.id in visited:
                continue
            # 如果该事件是当前链中某个事件的直接原因
            if any(eid in current_ids for eid in event.causes):
                primary.append(event)
                visited.add(event.id)
                current_ids.add(event.id)

        return primary

    async def predict_consequences(
        self,
        session: AsyncSession,
        event_id: str,
        steps: int = 5,
        model: str = "rule_based",
    ) -> Dict[str, Any]:
        """预测后果（多模型）

        Args:
            model: "rule_based" | "pattern" | "hybrid"
        """
        event = await self._events._repo.get_by_id(session, event_id)
        if not event:
            return {"error": "事件不存在", "event_id": event_id}

        # 获取已有的后果链
        chain = await self._events.predict_consequences(session, event_id, depth=steps)

        predictions = []

        if model == "rule_based":
            # 基于规则快速预测
            predictions = self._rule_based_prediction(event, chain)
        elif model == "pattern":
            # 基于历史模式预测
            predictions = self._pattern_based_prediction(event, chain)
        else:  # hybrid
            # 规则 + 模式混合
            rule_based = self._rule_based_prediction(event, chain)
            pattern_based = self._pattern_based_prediction(event, chain)
            # 合并去重
            seen = set()
            for p in rule_based + pattern_based:
                key = p.get("description", "")
                if key not in seen:
                    seen.add(key)
                    predictions.append(p)

        return {
            "event_id": event_id,
            "event_description": event.description,
            "model": model,
            "steps": steps,
            "predictions": predictions,
            "prediction_count": len(predictions),
            "confidence": self._calculate_prediction_confidence(predictions),
        }

    def _rule_based_prediction(
        self,
        event: Event,
        chain: List[Event],
    ) -> List[Dict[str, Any]]:
        """基于规则的快速预测"""
        predictions = []

        # 基于事件类型推断可能后果
        event_type_rules = {
            "action": [
                {"description": "行动产生直接效果", "probability": 0.9, "delay": 0},
                {"description": "相关角色做出反应", "probability": 0.7, "delay": 1},
            ],
            "decision": [
                {"description": "决策影响未来选择", "probability": 0.8, "delay": 0},
                {"description": "决策产生长期后果", "probability": 0.6, "delay": 2},
            ],
            "change": [
                {"description": "状态变化持续影响", "probability": 0.85, "delay": 0},
                {"description": "引发连锁反应", "probability": 0.5, "delay": 1},
            ],
            "interaction": [
                {"description": "关系发生变化", "probability": 0.8, "delay": 0},
                {"description": "影响多方立场", "probability": 0.6, "delay": 1},
            ],
        }

        rules = event_type_rules.get(event.event_type, [])
        for rule in rules:
            predictions.append({
                "description": rule["description"],
                "probability": rule["probability"],
                "delay_steps": rule["delay"],
                "source": "rule_based",
            })

        # 添加已有因果链中的事件作为预测
        for i, e in enumerate(chain[:3]):
            predictions.append({
                "description": e.description,
                "probability": e.causal_strength,
                "delay_steps": i + 1,
                "source": "existing_chain",
            })

        return predictions

    def _pattern_based_prediction(
        self,
        event: Event,
        chain: List[Event],
    ) -> List[Dict[str, Any]]:
        """基于历史模式的预测（简化版）"""
        predictions = []

        # 基于事件效果推断
        effects = event.effects or {}
        facts_changed = effects.get("facts_changed", [])

        for fact_change in facts_changed:
            predictions.append({
                "description": f"{fact_change.get('predicate', '属性')}变为{fact_change.get('new', '新值')}",
                "probability": 0.75,
                "delay_steps": 0,
                "source": "pattern",
                "affected_entity": fact_change.get("subject"),
            })

        return predictions

    def _calculate_prediction_confidence(
        self,
        predictions: List[Dict[str, Any]],
    ) -> float:
        """计算预测置信度"""
        if not predictions:
            return 0.0

        avg_prob = sum(p.get("probability", 0) for p in predictions) / len(predictions)
        # 预测数量越多，置信度适度降低（不确定性增加）
        count_penalty = min(len(predictions) * 0.02, 0.2)
        return round(max(0.0, min(1.0, avg_prob - count_penalty)), 2)

    async def generate_explanation(
        self,
        session: AsyncSession,
        event_id: str,
        audience: str = "reader",
        depth: str = "simple",
    ) -> Dict[str, Any]:
        """生成因果解释（自然语言）"""
        event = await self._events._repo.get_by_id(session, event_id)
        if not event:
            return {"error": "事件不存在", "event_id": event_id}

        # 获取原因和后果
        causes = await self._events.trace_causes(session, event_id, depth=2)
        consequences = await self._events.predict_consequences(session, event_id, depth=2)

        # 根据受众调整解释风格
        style_prefix = {
            "reader": "",
            "character": "（角色视角）",
            "author": "【作者笔记】",
        }.get(audience, "")

        # 根据深度调整详细程度
        detail_level = {
            "simple": 1,
            "detailed": 2,
            "technical": 3,
        }.get(depth, 1)

        # 构建解释
        parts = []
        if style_prefix:
            parts.append(style_prefix)

        parts.append(f"事件：{event.description}")

        if causes:
            if detail_level >= 2:
                parts.append(f"\n深层原因：")
                for i, cause in enumerate(causes[:detail_level * 2]):
                    indent = "  " * (i + 1)
                    parts.append(f"{indent}→ {cause.description}")
            else:
                parts.append(f"\n原因：{causes[0].description}")

        if consequences:
            parts.append(f"\n预期后果：")
            for c in consequences[:detail_level * 2]:
                parts.append(f"  → {c.description}")

        explanation = "\n".join(parts)

        return {
            "event_id": event_id,
            "audience": audience,
            "depth": depth,
            "explanation": explanation,
            "cause_count": len(causes),
            "consequence_count": len(consequences),
        }

    async def analyze_what_if(
        self,
        session: AsyncSession,
        novel_id: str,
        event_id: str,
        modification: Dict[str, Any],
        compare_depth: int = 5,
    ) -> Dict[str, Any]:
        """反事实分析 — "如果...会怎样"

        Args:
            modification: {"subject_id": str, "predicate": str, "new_value": Any}
        """
        event = await self._events._repo.get_by_id(session, event_id)
        if not event:
            return {"error": "事件不存在", "event_id": event_id}

        # 1. 创建反事实分支
        branch_id = await self._world.create_counterfactual_branch(
            session,
            novel_id=novel_id,
            base_branch="main",
            changes=[modification],
            name=f"what_if_{event_id}",
        )

        # 2. 获取分支事实
        branch_facts = await self._world.get_branch_facts(session, branch_id)

        # 3. 对比原始状态和分支状态
        original_fact = await self._world.get_current_state(
            session,
            modification["subject_id"],
            modification["predicate"],
        )

        key_differences = []
        for fact in branch_facts:
            if fact.subject_id == modification["subject_id"] and fact.predicate == modification["predicate"]:
                key_differences.append({
                    "subject_id": fact.subject_id,
                    "predicate": fact.predicate,
                    "original_value": original_fact.object_value if original_fact else None,
                    "counterfactual_value": fact.object_value,
                })

        return {
            "original_event": event_id,
            "event_description": event.description,
            "modification": modification,
            "branch_id": branch_id,
            "branch_fact_count": len(branch_facts),
            "key_differences": key_differences,
            "compare_depth": compare_depth,
        }
