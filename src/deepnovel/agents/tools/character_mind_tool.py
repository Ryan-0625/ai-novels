"""
角色心智工具 — Agent 可直接调用

功能：
1. 记忆检索（语义+时序+情感）
2. 信念推理（链式推理）
3. 情感预测（假设事件）
4. 人格一致性检查

@file: agents/tools/character_mind_tool.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Character
from deepnovel.repositories import CharacterRepository
from deepnovel.services import WorldStateService


class CharacterMindTool:
    """角色心智工具 — Agent 可直接调用"""

    def __init__(
        self,
        character_repo: Optional[CharacterRepository] = None,
        world_service: Optional[WorldStateService] = None,
    ):
        self._character_repo = character_repo or CharacterRepository()
        self._world = world_service or WorldStateService()

    async def get_mind(
        self,
        session: AsyncSession,
        character_id: str,
    ) -> Optional[Dict[str, Any]]:
        """获取角色心智状态"""
        character = await self._character_repo.get_by_id(session, character_id)
        if not character:
            return None

        return {
            "character_id": character_id,
            "name": character.name,
            "mental_state": character.mental_state,
            "profile": character.profile,
            "archetype": character.archetype,
        }

    async def retrieve_memories(
        self,
        session: AsyncSession,
        character_id: str,
        query: str,
        retrieval_type: str = "mixed",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索记忆（多策略）

        Args:
            retrieval_type: "semantic" | "temporal" | "emotional" | "mixed"
        """
        mind = await self.get_mind(session, character_id)
        if not mind:
            return []

        mental_state = mind.get("mental_state", {})
        memories = mental_state.get("episodic_memory", [])

        if retrieval_type == "temporal":
            # 时间排序（最近优先）
            return sorted(memories, key=lambda m: m.get("timestamp", 0), reverse=True)[:top_k]

        elif retrieval_type == "emotional":
            # 情感匹配（返回情感强度最高的）
            return sorted(
                memories,
                key=lambda m: m.get("emotion_intensity", 0),
                reverse=True,
            )[:top_k]

        elif retrieval_type == "semantic":
            # 语义匹配（简化版：关键词匹配）
            query_terms = set(query.lower().split())
            scored = []
            for memory in memories:
                content = memory.get("content", "")
                score = len(query_terms & set(content.lower().split()))
                scored.append((score, memory))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored[:top_k]]

        else:  # mixed
            # 混合评分：语义 0.4 + 时序 0.3 + 情感 0.3
            now = 0  # 简化：使用相对时间戳
            query_terms = set(query.lower().split())
            current_emotion = mental_state.get("current_emotion", {})

            scored = []
            for memory in memories:
                # 语义分
                content = memory.get("content", "")
                semantic_score = len(query_terms & set(content.lower().split())) / max(len(query_terms), 1)

                # 时序分（越近越高）
                timestamp = memory.get("timestamp", 0)
                temporal_score = 1.0 / (1.0 + abs(now - timestamp) / 3600)  # 小时衰减

                # 情感分
                emotion = memory.get("emotion", "")
                emotion_intensity = memory.get("emotion_intensity", 0.5)
                emotional_score = emotion_intensity if emotion in current_emotion else 0.3

                score = semantic_score * 0.4 + temporal_score * 0.3 + emotional_score * 0.3
                scored.append((score, memory))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in scored[:top_k]]

    async def update_belief(
        self,
        session: AsyncSession,
        character_id: str,
        belief_category: str,
        belief_key: str,
        new_evidence: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """更新角色信念（贝叶斯更新）"""
        mind = await self.get_mind(session, character_id)
        if not mind:
            return None

        mental_state = mind.get("mental_state", {})
        beliefs = mental_state.get("beliefs", {})
        category_beliefs = beliefs.get(belief_category, {})

        old_belief = category_beliefs.get(belief_key, {"value": 0.5, "evidence": []})

        # 贝叶斯更新：加权平均
        old_value = old_belief["value"]
        new_value = new_evidence.get("value", 0.5)
        confidence = new_evidence.get("confidence", 0.5)
        evidence_count = len(old_belief.get("evidence", []))
        weight = min(evidence_count / 10, 0.9)

        updated_value = old_value * weight + new_value * confidence * (1 - weight)
        updated_value = max(0.0, min(1.0, updated_value))

        # 更新证据链
        evidence = old_belief.get("evidence", [])
        evidence.append(new_evidence.get("source", "unknown"))
        evidence = evidence[-10:]  # 只保留最近10条

        updated_belief = {
            "value": updated_value,
            "evidence": evidence,
            "last_updated": "now",
        }

        category_beliefs[belief_key] = updated_belief
        beliefs[belief_category] = category_beliefs
        mental_state["beliefs"] = beliefs

        # 更新角色
        character = await self._character_repo.get_by_id(session, character_id)
        if character:
            character.mental_state = mental_state
            await self._character_repo.update(session, character)

        return updated_belief

    async def compute_emotion(
        self,
        session: AsyncSession,
        character_id: str,
        appraisal: Dict[str, float],
    ) -> Optional[Dict[str, float]]:
        """计算情感反应（基于简化 OCC 模型）"""
        mind = await self.get_mind(session, character_id)
        if not mind:
            return None

        mental_state = mind.get("mental_state", {})
        personality = mind.get("profile", {}).get("personality", {})
        baseline = mental_state.get("emotional_baseline", {})

        emotions = {}

        # 1. 愉悦度
        desirability = appraisal.get("desirability", 0)
        if desirability > 0:
            emotions["joy"] = desirability * (1 + personality.get("extraversion", 0.5))
        else:
            emotions["sadness"] = abs(desirability) * (1 + personality.get("neuroticism", 0.5))

        # 2. 控制感
        controllability = appraisal.get("controllability", 0.5)
        if controllability < 0.3:
            emotions["fear"] = (1 - controllability) * appraisal.get("importance", 0.5)

        # 3. 公平感
        blame = appraisal.get("blame", 0)
        if blame > 0:
            emotions["anger"] = blame * appraisal.get("importance", 0.5)

        # 4. 新奇感
        novelty = appraisal.get("novelty", 0)
        if novelty > 0.7:
            emotions["surprise"] = novelty

        # 应用基线调节
        for emotion, value in emotions.items():
            baseline_value = baseline.get(emotion, 0.5)
            emotions[emotion] = value * 0.7 + baseline_value * 0.3

        # 情感调节
        regulation = mental_state.get("emotional_regulation", 0.5)
        for emotion in emotions:
            emotions[emotion] *= (1 - regulation * 0.3)

        # 归一化到 0-1
        for emotion in emotions:
            emotions[emotion] = max(0.0, min(1.0, emotions[emotion]))

        # 更新当前情感
        mental_state["current_emotion"] = emotions
        character = await self._character_repo.get_by_id(session, character_id)
        if character:
            character.mental_state = mental_state
            await self._character_repo.update(session, character)

        return emotions

    async def check_consistency(
        self,
        session: AsyncSession,
        character_id: str,
        proposed_action: str,
    ) -> Dict[str, Any]:
        """检查行动与人格的一致性"""
        mind = await self.get_mind(session, character_id)
        if not mind:
            return {"consistent": False, "reason": "角色不存在"}

        profile = mind.get("profile", {})
        personality = profile.get("personality", {})
        values = profile.get("values", [])
        archetype = mind.get("archetype", "")

        # 简化的一致性检查
        consistency_score = 0.5
        conflicts = []

        # 基于原型的一致性
        archetype_consistency = {
            "hero": ["勇敢", "正义", "保护"],
            "villain": ["权力", "控制", "报复"],
            "mentor": ["智慧", "教导", "指引"],
            "sidekick": ["忠诚", "协助", "支持"],
        }

        if archetype in archetype_consistency:
            traits = archetype_consistency[archetype]
            matched = sum(1 for t in traits if t in proposed_action)
            consistency_score = 0.3 + (matched / len(traits)) * 0.7

        # 基于价值观的一致性
        if values:
            value_conflicts = []
            for value in values:
                # 简化：检查价值观关键词是否出现在行动中
                if value in proposed_action:
                    consistency_score += 0.1
                else:
                    value_conflicts.append(value)

            if value_conflicts and consistency_score < 0.5:
                conflicts.append(f"行动未体现价值观: {', '.join(value_conflicts)}")

        consistency_score = min(1.0, consistency_score)

        return {
            "consistent": consistency_score >= 0.5,
            "consistency_score": round(consistency_score, 2),
            "conflicts": conflicts,
            "archetype": archetype,
            "personality_match": personality,
        }
