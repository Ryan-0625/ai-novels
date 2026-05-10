"""
世界规则服务 — 约束引擎管理

@file: services/world_rule_service.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import WorldRule
from deepnovel.repositories import WorldRuleRepository


class WorldRuleService:
    """世界规则服务 — 管理世界运行法则和约束检查

    核心能力：
    1. 规则创建与管理
    2. 规则适用性判断
    3. 规则优先级排序
    4. 规则触发与执行
    """

    def __init__(self, repository: Optional[WorldRuleRepository] = None):
        self._repo = repository or WorldRuleRepository()

    async def create_rule(
        self,
        session: AsyncSession,
        novel_id: str,
        rule_name: str,
        rule_type: str,
        condition: Dict[str, Any],
        action: Dict[str, Any],
        *,
        priority: int = 100,
        description: Optional[str] = None,
    ) -> WorldRule:
        """创建世界规则"""
        rule = WorldRule(
            novel_id=novel_id,
            rule_name=rule_name,
            rule_type=rule_type,
            condition=condition,
            action=action,
            priority=priority,
            is_active=True,
            description=description,
        )
        return await self._repo.create(session, rule)

    async def get_active_rules(
        self,
        session: AsyncSession,
        novel_id: str,
    ) -> List[WorldRule]:
        """获取小说的所有活跃规则（按优先级排序）"""
        return await self._repo.get_by_novel(session, novel_id, active_only=True)

    async def get_rules_by_type(
        self,
        session: AsyncSession,
        novel_id: str,
        rule_type: str,
    ) -> List[WorldRule]:
        """按类型获取规则"""
        return await self._repo.get_by_type(session, novel_id, rule_type)

    async def deactivate_rule(
        self,
        session: AsyncSession,
        rule_id: str,
    ) -> Optional[WorldRule]:
        """停用规则"""
        rule = await self._repo.get_by_id(session, rule_id)
        if not rule:
            return None
        rule.is_active = False
        return await self._repo.update(session, rule)

    async def activate_rule(
        self,
        session: AsyncSession,
        rule_id: str,
    ) -> Optional[WorldRule]:
        """激活规则"""
        rule = await self._repo.get_by_id(session, rule_id)
        if not rule:
            return None
        rule.is_active = True
        return await self._repo.update(session, rule)

    async def find_applicable_rules(
        self,
        session: AsyncSession,
        novel_id: str,
        predicate: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[WorldRule]:
        """查找适用于指定谓语的规则

        Args:
            context: 额外上下文用于进一步过滤
        """
        rules = await self._repo.get_applicable_rules(session, novel_id, predicate)

        if context:
            # 进一步根据上下文过滤
            filtered = []
            for rule in rules:
                if self._match_condition(rule.condition, context):
                    filtered.append(rule)
            rules = filtered

        return rules

    def _match_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any],
    ) -> bool:
        """检查条件是否匹配上下文（简单实现）"""
        for key, expected in condition.items():
            actual = context.get(key)
            if actual is None:
                return False
            if isinstance(expected, dict):
                # 操作符匹配
                op = expected.get("operator", "==")
                value = expected.get("value")
                if op == "==" and actual != value:
                    return False
                elif op == "!=" and actual == value:
                    return False
                elif op == "<" and not (actual < value):
                    return False
                elif op == ">" and not (actual > value):
                    return False
                elif op == "<=" and not (actual <= value):
                    return False
                elif op == ">=" and not (actual >= value):
                    return False
                elif op == "in" and actual not in value:
                    return False
            elif actual != expected:
                return False
        return True

    async def evaluate_rules(
        self,
        session: AsyncSession,
        novel_id: str,
        predicate: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """评估所有适用规则并返回执行动作

        Returns:
            动作列表，每项包含 rule_id, rule_name, action
        """
        rules = await self.find_applicable_rules(session, novel_id, predicate, context)

        actions = []
        for rule in rules:
            if self._match_condition(rule.condition, context):
                actions.append({
                    "rule_id": rule.id,
                    "rule_name": rule.rule_name,
                    "priority": rule.priority,
                    "action": rule.action,
                })

        # 按优先级排序（数字越小优先级越高）
        actions.sort(key=lambda x: x["priority"])
        return actions
