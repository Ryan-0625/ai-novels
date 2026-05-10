"""
叙事记录工具 — Agent 可直接调用

功能：
1. 记录场景（单视角）
2. 记录多视角场景
3. 检查风格一致性
4. 叙事-事件映射验证

@file: agents/tools/narrative_record_tool.py
@date: 2026-04-29
"""

from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.models import Narrative, NarrativeType, POVType
from deepnovel.services import NarrativeService, EventService
from deepnovel.repositories import CharacterRepository


class NarrativeRecordTool:
    """叙事记录工具 — Agent 可直接调用"""

    def __init__(
        self,
        narrative_service: Optional[NarrativeService] = None,
        event_service: Optional[EventService] = None,
        character_repo: Optional[CharacterRepository] = None,
    ):
        self._narrative = narrative_service or NarrativeService()
        self._events = event_service or EventService()
        self._characters = character_repo or CharacterRepository()

    async def record_scene(
        self,
        session: AsyncSession,
        novel_id: str,
        chapter_id: str,
        content: str,
        events: List[str],
        *,
        pov_character: Optional[str] = None,
        pov_type: str = POVType.THIRD_LIMITED,
        style_profile: Optional[Dict[str, Any]] = None,
        pacing: str = "normal",
        plot_function: Optional[str] = None,
        generated_by: str = "agent",
    ) -> Dict[str, Any]:
        """记录场景（单视角）

        Args:
            events: 覆盖的模拟事件ID列表
            pacing: "fast" | "normal" | "slow"
        """
        # 获取事件详情用于元数据
        event_details = []
        for event_id in events:
            event = await self._events._repo.get_by_id(session, event_id)
            if event:
                event_details.append(event.to_dict())

        # 计算情感弧线
        emotional_arc = await self._compute_emotional_arc(session, events, pov_character)

        # 构建风格配置
        style = style_profile or {}
        style["pacing"] = pacing
        style["detail_level"] = {"fast": "low", "normal": "medium", "slow": "high"}[pacing]

        # 创建叙事
        narrative = await self._narrative.create_narrative(
            session,
            novel_id=novel_id,
            chapter_id=chapter_id,
            content=content,
            narrative_type=NarrativeType.SCENE,
            pov_character=pov_character,
            pov_type=pov_type,
            style_profile=style,
            covers_events=events,
            plot_function=plot_function,
            emotional_arc=emotional_arc,
            generated_by=generated_by,
        )

        # 验证事件覆盖
        coverage = await self._narrative.check_event_coverage(
            session, narrative.id, events
        )

        result = narrative.to_dict()
        result["event_coverage"] = coverage
        result["event_details"] = event_details
        return result

    async def record_multi_pov_scene(
        self,
        session: AsyncSession,
        novel_id: str,
        chapter_id: str,
        contents: Dict[str, str],
        events: List[str],
        *,
        transition_style: str = "sequential",
        style_profile: Optional[Dict[str, Any]] = None,
        generated_by: str = "agent",
    ) -> List[Dict[str, Any]]:
        """记录多视角场景

        Args:
            contents: {character_id: content}
            transition_style: "sequential" | "interleaved" | "parallel"
        """
        narratives = []

        if transition_style == "sequential":
            # 顺序叙述：每个角色一段
            for character_id, content in contents.items():
                result = await self.record_scene(
                    session,
                    novel_id=novel_id,
                    chapter_id=chapter_id,
                    content=content,
                    events=events,
                    pov_character=character_id,
                    generated_by=generated_by,
                )
                narratives.append(result)

        elif transition_style == "interleaved":
            # 交织叙述：合并为一个叙事，标注视角切换
            merged_content = self._generate_interleaved(contents)
            result = await self.record_scene(
                session,
                novel_id=novel_id,
                chapter_id=chapter_id,
                content=merged_content,
                events=events,
                pov_character=None,  # 多视角
                pov_type=POVType.THIRD_OMNISCIENT,
                style_profile={**(style_profile or {}), "transition_style": "interleaved"},
                generated_by=generated_by,
            )
            narratives.append(result)

        else:  # parallel
            # 并行叙述：同时展现多方视角
            merged_content = self._generate_parallel(contents)
            result = await self.record_scene(
                session,
                novel_id=novel_id,
                chapter_id=chapter_id,
                content=merged_content,
                events=events,
                pov_character=None,
                pov_type=POVType.THIRD_OMNISCIENT,
                style_profile={**(style_profile or {}), "transition_style": "parallel"},
                generated_by=generated_by,
            )
            narratives.append(result)

        return narratives

    def _generate_interleaved(self, contents: Dict[str, str]) -> str:
        """生成交织叙述（视角切换）"""
        parts = []
        # 简化：按角色分段，用分隔符标记视角切换
        for character_id, content in contents.items():
            parts.append(f"【{character_id}视角】\n{content}\n")
        return "\n---\n".join(parts)

    def _generate_parallel(self, contents: Dict[str, str]) -> str:
        """生成并行叙述（同时展现）"""
        parts = []
        # 简化：并列呈现各方视角
        for character_id, content in contents.items():
            parts.append(f"【{character_id}的感知】\n{content}")
        return "\n\n同时，\n\n".join(parts)

    async def _compute_emotional_arc(
        self,
        session: AsyncSession,
        events: List[str],
        pov_character: Optional[str],
    ) -> Dict[str, Any]:
        """计算情感弧线"""
        if not events or not pov_character:
            return {}

        # 获取角色的情感状态变化
        character = await self._characters.get_by_id(session, pov_character)
        if not character or not character.mental_state:
            return {}

        current_emotion = character.mental_state.get("current_emotion", {})

        # 简化：基于事件重要性计算情感变化
        start_emotion = dict(current_emotion)
        end_emotion = dict(current_emotion)

        for event_id in events:
            event = await self._events._repo.get_by_id(session, event_id)
            if event and event.effects:
                emotions = event.effects.get("emotions_triggered", [])
                for emo in emotions:
                    if emo.get("character") == pov_character:
                        emotion_type = emo.get("emotion", "joy")
                        intensity = emo.get("intensity", 0)
                        end_emotion[emotion_type] = end_emotion.get(emotion_type, 0) + intensity * 0.1

        # 归一化
        for key in end_emotion:
            end_emotion[key] = max(0.0, min(1.0, end_emotion[key]))

        return {
            "start": start_emotion,
            "end": end_emotion,
            "pov_character": pov_character,
        }

    async def check_style_consistency(
        self,
        session: AsyncSession,
        chapter_id: str,
        tolerance: float = 0.8,
    ) -> Dict[str, Any]:
        """检查章节内叙事风格一致性"""
        narratives = await self._narrative.get_chapter_narratives(session, chapter_id)

        if len(narratives) < 2:
            return {
                "is_consistent": True,
                "overall": 1.0,
                "metrics": {},
                "narrative_count": len(narratives),
            }

        # 计算各项一致性指标
        metrics = {}

        # 1. 视角一致性
        pov_types = [n.pov_type for n in narratives]
        pov_consistency = sum(1 for p in pov_types if p == pov_types[0]) / len(pov_types)
        metrics["pov_consistency"] = round(pov_consistency, 2)

        # 2. 风格一致性（基于风格配置）
        tones = []
        paces = []
        for n in narratives:
            style = n.style_profile or {}
            if "tone" in style:
                tones.append(style["tone"])
            if "pace" in style:
                paces.append(style["pace"])

        tone_consistency = 1.0 if len(set(tones)) <= 1 else 0.5
        pace_consistency = 1.0 if len(set(paces)) <= 1 else 0.7
        metrics["tone_consistency"] = round(tone_consistency, 2)
        metrics["pace_consistency"] = round(pace_consistency, 2)

        # 3. 叙事功能一致性
        functions = [n.plot_function for n in narratives if n.plot_function]
        function_consistency = 1.0 if len(set(functions)) == len(functions) else 0.8
        metrics["function_consistency"] = round(function_consistency, 2)

        # 4. 平均段落长度一致性
        avg_lengths = [len(n.content) for n in narratives]
        if avg_lengths:
            mean_length = sum(avg_lengths) / len(avg_lengths)
            variance = sum((l - mean_length) ** 2 for l in avg_lengths) / len(avg_lengths)
            std_dev = variance ** 0.5
            length_consistency = 1.0 - min(std_dev / mean_length if mean_length > 0 else 0, 0.5)
            metrics["length_consistency"] = round(length_consistency, 2)

        # 总体一致性
        overall = sum(metrics.values()) / len(metrics) if metrics else 1.0

        suggestions = []
        if overall < tolerance:
            if metrics.get("pov_consistency", 1.0) < tolerance:
                suggestions.append("视角切换过于频繁，建议保持统一的叙事视角")
            if metrics.get("tone_consistency", 1.0) < tolerance:
                suggestions.append("基调不一致，建议统一情感色彩")
            if metrics.get("pace_consistency", 1.0) < tolerance:
                suggestions.append("节奏变化过大，建议控制叙事速度")

        return {
            "metrics": metrics,
            "overall": round(overall, 2),
            "is_consistent": overall >= tolerance,
            "suggestions": suggestions,
            "narrative_count": len(narratives),
            "tolerance": tolerance,
        }

    async def get_narrative_timeline(
        self,
        session: AsyncSession,
        chapter_id: str,
    ) -> List[Dict[str, Any]]:
        """获取章节的叙事时间线（按创建时间排序）"""
        narratives = await self._narrative.get_chapter_narratives(session, chapter_id)
        return [
            {
                "narrative_id": n.id,
                "type": n.narrative_type,
                "pov_character": n.pov_character,
                "pov_type": n.pov_type,
                "covers_events": n.covers_events,
                "word_count": n.word_count,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "generated_by": n.generated_by,
            }
            for n in narratives
        ]
