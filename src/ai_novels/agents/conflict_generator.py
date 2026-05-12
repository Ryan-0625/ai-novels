"""
ConflictGeneratorAgent - 冲突生成智能体

@file: agents/conflict_generator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 冲突生成、升级、解决、关系更新
"""

import time
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .base import BaseAgent, AgentConfig, Message, MessageType


class ConflictType(Enum):
    """冲突类型"""
    INTERNAL = "internal"           # 内心冲突
    INTERPERSONAL = "interpersonal" # 人际冲突
    SOCIAL = "social"               # 社会冲突
    EXTERNAL = "external"           # 外部威胁
    ENVIRONMENTAL = "environmental" # 环境冲突
    MORAL = "moral"                 # 道德冲突
    PHILOSOPHICAL = "philosophical" # 哲学冲突


class ConflictStatus(Enum):
    """冲突状态"""
    DORMANT = "dormant"        # 潜伏
    EMERGING = "emerging"      # 出现
    INTENSIFYING = "intensifying" # 升级
    CRISIS = "crisis"          # 危机
    RESOLVING = "resolving"    # 解决中
    RESOLVED = "resolved"      # 已解决
    ESCALATED = "escalated"    # 升级


@dataclass
class Conflict:
    """冲突数据结构"""
    conflict_id: str
    conflict_type: ConflictType
    description: str
    participants: List[str]
    chapter_id: str
    status: ConflictStatus
    intensity: int  # 0-100
    created_at: float
    stages: List[Dict[str, Any]] = field(default_factory=list)
    resolution: Optional[str] = None
    resolved_at: Optional[float] = None
    consequences: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "type": self.conflict_type.value,
            "description": self.description,
            "participants": self.participants,
            "chapter_id": self.chapter_id,
            "status": self.status.value,
            "intensity": self.intensity,
            "created_at": self.created_at,
            "stages": self.stages,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at,
            "consequences": self.consequences
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ConflictArc:
    """冲突弧线"""
    arc_id: str
    conflicts: List[str]
    intensity_curve: List[Dict[str, Any]]
    resolution_pattern: str
    thematic_significance: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arc_id": self.arc_id,
            "conflicts": self.conflicts,
            "intensity_curve": self.intensity_curve,
            "resolution_pattern": self.resolution_pattern,
            "thematic_significance": self.thematic_significance
        }


@dataclass
class RelationshipChange:
    """关系变化"""
    change_id: str
    from_character: str
    to_character: str
    change_type: str  # increase, decrease, neutralize
    magnitude: int  # -100 to 100
    context: str
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_id": self.change_id,
            "from_character": self.from_character,
            "to_character": self.to_character,
            "change_type": self.change_type,
            "magnitude": self.magnitude,
            "context": self.context,
            "timestamp": self.timestamp
        }


class ConflictGeneratorAgent(BaseAgent):
    """
    冲突生成智能体

    核心功能：
    - 多类型冲突生成（内心/人际/社会/外部/环境/道德/哲学）
    - 冲突升级系统（潜伏->出现->升级->危机）
    - 冲突解决机制
    - 关系动态更新
    - 冲突弧线追踪
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="conflict_generator",
                description="Conflict generation and management",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=4096
            )
        super().__init__(config)

        # 冲突存储
        self._conflicts: Dict[str, Conflict] = {}
        self._conflict_arcs: Dict[str, ConflictArc] = {}

        # 关系存储
        self._relationships: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._relationship_changes: List[RelationshipChange] = []

        # 状态
        self._last_conflict_id = 0
        self._last_change_id = 0
        self._conflict_count = 0

        # 冲突升级模板
        self._intensity_stages = [
            ("dormant", 0, 20, "潜伏状态，冲突隐藏中"),
            ("emerging", 21, 40, "开始显现，小摩擦出现"),
            ("intensifying", 41, 60, "矛盾加剧，言辞冲突"),
            ("crisis", 61, 80, "危机状态，激烈对抗"),
            ("resolving", 81, 90, "解决尝试，寻求妥协"),
            ("resolved", 91, 100, "冲突解决，新平衡建立"),
            ("escalated", 95, 100, "完全升级，无法挽回"),
        ]

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "conflict" in content:
            if "generate" in content or "create" in content:
                return self._handle_generate_conflict(message)
            elif "resolve" in content:
                return self._handle_resolve_conflict(message)
            elif "upgrade" in content or "intensify" in content:
                return self._handle_intensify_conflict(message)
            elif "arc" in content:
                return self._handle_conflict_arc(message)
            elif "relationship" in content or "relation" in content:
                return self._handle_relationship(message)
            elif "list" in content or "status" in content:
                return self._handle_list_conflicts(message)

        return self._handle_general_request(message)

    def _handle_generate_conflict(self, message: Message) -> Message:
        """处理生成冲突请求"""
        content = str(message.content)

        conflict_type = self._extract_param(content, "type", "interpersonal")
        participants = self._extract_param(content, "participants", "Protagonist,Antagonist").split(",")
        chapter_id = self._extract_param(content, "chapter_id", "chapter_1")
        intensity = int(self._extract_param(content, "intensity", "40"))
        context = self._extract_param(content, "context", "")

        conflict = self._generate_conflict(
            conflict_type=ConflictType(conflict_type.lower()),
            participants=participants,
            chapter_id=chapter_id,
            intensity=intensity,
            context=context
        )

        self._conflicts[conflict.conflict_id] = conflict
        self._conflict_count += 1

        # 更新关系
        for i, p1 in enumerate(participants):
            for p2 in participants[i+1:]:
                self._update_relationship(p1, p2, -intensity // 2, f"Conflict: {conflict.conflict_id}")

        response = f"Generated Conflict: {conflict.conflict_id}\n\n"
        response += f"Type: {conflict.conflict_type.value}\n"
        response += f"Participants: {', '.join(conflict.participants)}\n"
        response += f"Intensity: {conflict.intensity}\n"
        response += f"Chapter: {conflict.chapter_id}\n"
        response += f"Status: {conflict.status.value}\n\n"
        response += f"Description:\n{conflict.description}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            conflict_id=conflict.conflict_id,
            conflict_type=conflict.conflict_type.value,
            intensity=conflict.intensity
        )

    def _handle_resolve_conflict(self, message: Message) -> Message:
        """处理解决冲突请求"""
        content = str(message.content)

        conflict_id = self._extract_param(content, "conflict_id", "")
        resolution = self._extract_param(content, "resolution", "")

        if conflict_id and conflict_id in self._conflicts:
            conflict = self._conflicts[conflict_id]
            old_intensity = conflict.intensity

            conflict.status = ConflictStatus.RESOLVED
            conflict.resolution = resolution
            conflict.resolved_at = time.time()

            # 添加解决阶段
            conflict.stages.append({
                "stage": "resolved",
                "intensity": conflict.intensity,
                "description": resolution,
                "timestamp": conflict.resolved_at
            })

            # 计算后果
            conflict.consequences = self._generate_consequences(
                conflict.conflict_type,
                conflict.participants,
                old_intensity,
                "resolved"
            )

            # 更新关系
            for i, p1 in enumerate(conflict.participants):
                for p2 in conflict.participants[i+1:]:
                    # 关系可能被修复或完全破裂
                    change = -50 if old_intensity > 70 else 30
                    self._update_relationship(p1, p2, change, f"Conflict resolution: {conflict_id}")

            response = f"Resolved Conflict: {conflict_id}\n\n"
            response += f"Resolution: {resolution}\n"
            response += f"Consequences: {len(conflict.consequences)}\n\n"
            for i, cons in enumerate(conflict.consequences):
                response += f"{i+1}. {cons}\n"

            return self._create_message(
                response,
                MessageType.TEXT,
                conflict_id=conflict_id,
                status=conflict.status.value
            )

        return self._create_message(f"Conflict {conflict_id} not found.", MessageType.TEXT)

    def _handle_intensify_conflict(self, message: Message) -> Message:
        """处理升级冲突请求"""
        content = str(message.content)

        conflict_id = self._extract_param(content, "conflict_id", "")
        increase = int(self._extract_param(content, "increase", "15"))
        trigger = self._extract_param(content, "trigger", "New event occurs")

        if conflict_id and conflict_id in self._conflicts:
            conflict = self._conflicts[conflict_id]

            old_intensity = conflict.intensity
            new_intensity = min(100, old_intensity + increase)

            # 添加升级阶段
            conflict.stages.append({
                "stage": "intensified",
                "previous_intensity": old_intensity,
                "new_intensity": new_intensity,
                "trigger": trigger,
                "timestamp": time.time()
            })

            conflict.intensity = new_intensity

            # 更新状态
            if new_intensity >= 80:
                conflict.status = ConflictStatus.ESCALATED
            elif new_intensity >= 60:
                conflict.status = ConflictStatus.CRISIS
            elif new_intensity >= 40:
                conflict.status = ConflictStatus.INTENSIFYING

            # 更新关系
            for i, p1 in enumerate(conflict.participants):
                for p2 in conflict.participants[i+1:]:
                    self._update_relationship(p1, p2, -increase // 2, f"Conflict escalation: {conflict_id}")

            response = f"Intensified Conflict: {conflict_id}\n\n"
            response += f"Previous Intensity: {old_intensity}\n"
            response += f"New Intensity: {new_intensity}\n"
            response += f"Trigger: {trigger}\n"
            response += f"New Status: {conflict.status.value}\n\n"

            # 潜在升级路径
            if new_intensity < 80:
                response += "Potential Upgrades:\n"
                response += f"- Add complication: +{min(20, 100-new_intensity)} intensity\n"
                response += f"- Introduce third party: Potential alliance against one participant\n"
                response += f"- External factor: New environmental challenge\n"

            return self._create_message(
                response,
                MessageType.TEXT,
                conflict_id=conflict_id,
                old_intensity=old_intensity,
                new_intensity=new_intensity
            )

        return self._create_message(f"Conflict {conflict_id} not found.", MessageType.TEXT)

    def _handle_conflict_arc(self, message: Message) -> Message:
        """处理冲突弧线请求"""
        content = str(message.content)

        if "create" in content or "generate" in content:
            arc_id = self._extract_param(content, "arc_id", "arc_001")
            conflict_ids = self._extract_param(content, "conflicts", "").split(",")
            resolution_pattern = self._extract_param(content, "pattern", "catharsis")

            # 过滤有效的冲突ID
            valid_conflicts = [cid for cid in conflict_ids if cid in self._conflicts]

            # 计算强度曲线
            intensity_curve = []
            for cid in valid_conflicts:
                conflict = self._conflicts[cid]
                intensity_curve.append({
                    "conflict_id": cid,
                    "intensity": conflict.intensity,
                    "chapter": conflict.chapter_id,
                    "stage": conflict.status.value
                })

            arc = ConflictArc(
                arc_id=arc_id,
                conflicts=valid_conflicts,
                intensity_curve=intensity_curve,
                resolution_pattern=resolution_pattern,
                thematic_significance=f"Thematic exploration through {len(valid_conflicts)} conflicts"
            )

            self._conflict_arcs[arc_id] = arc

            response = f"Created Conflict Arc {arc_id}:\n\n"
            response += f"Conflicts: {len(valid_conflicts)}\n"
            response += f"Pattern: {resolution_pattern}\n\n"
            response += "Intensity Curve:\n"
            for point in intensity_curve[:10]:
                response += f"  - {point['conflict_id']}: Intensity {point['intensity']} ({point['stage']})\n"

            return self._create_message(
                response,
                MessageType.TEXT,
                arc_id=arc_id,
                conflict_count=len(valid_conflicts)
            )

        elif "list" in content:
            if not self._conflict_arcs:
                return self._create_message("No conflict arcs generated.", MessageType.TEXT)

            response = "Conflict Arcs:\n"
            for arc_id, arc in self._conflict_arcs.items():
                response += f"- {arc_id}: {len(arc.conflicts)} conflicts, Pattern: {arc.resolution_pattern}\n"

            return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_relationship(self, message: Message) -> Message:
        """处理关系请求"""
        content = str(message.content)

        if "list" in content:
            response = "Relationship Overview:\n\n"
            chars = set()
            for c1 in self._relationships.values():
                chars.update(c1.keys())

            relationships_list = []
            for c1 in sorted(chars):
                for c2 in sorted(chars):
                    if c1 < c2 and c2 in self._relationships.get(c1, {}):
                        score = self._relationships[c1][c2]
                        rel_type = self._get_relationship_type(score)
                        relationships_list.append((c1, c2, score, rel_type))

            for c1, c2, score, rel_type in relationships_list[:20]:
                response += f"{c1} <-> {c2}: {score:+d} ({rel_type})\n"

            return self._create_message(response, MessageType.TEXT)

        elif "check" in content:
            c1 = self._extract_param(content, "character1", "")
            c2 = self._extract_param(content, "character2", "")

            if c1 and c2:
                score = self._relationships.get(c1, {}).get(c2, 0)
                rel_type = self._get_relationship_type(score)

                response = f"Relationship: {c1} <-> {c2}\n"
                response += f"Score: {score:+d}\n"
                response += f"Type: {rel_type}\n"

                # 历史变化
                changes = [c for c in self._relationship_changes
                          if (c.from_character == c1 and c.to_character == c2) or
                             (c.from_character == c2 and c.to_character == c1)]

                if changes:
                    response += f"\nRecent Changes: {len(changes)}\n"
                    for change in changes[-5:]:
                        response += f"  - {change.change_type}: {change.magnitude:+d} ({change.context})\n"

                return self._create_message(response, MessageType.TEXT)

        return self._handle_general_request(message)

    def _handle_list_conflicts(self, message: Message) -> Message:
        """处理列出冲突请求"""
        content = str(message.content)

        status_filter = self._extract_param(content, "status", "").lower()
        type_filter = self._extract_param(content, "type", "").lower()

        conflicts = list(self._conflicts.values())

        if status_filter:
            conflicts = [c for c in conflicts if c.status.value == status_filter]
        if type_filter:
            conflicts = [c for c in conflicts if c.conflict_type.value == type_filter]

        response = f"Conflicts ({len(conflicts)} total):\n\n"
        for conflict in conflicts:
            intensity_bar = self._get_intensity_bar(conflict.intensity)
            response += f"{conflict.conflict_id} [{conflict.conflict_type.value}] {intensity_bar} ({conflict.intensity})\n"
            response += f"  {', '.join(conflict.participants)}\n"
            response += f"  Status: {conflict.status.value}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            conflict_count=len(conflicts)
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Conflict Generator Agent available commands:\n"
            "- 'generate conflict type=X participants=X chapter_id=X intensity=X' - 生成冲突\n"
            "- 'resolve conflict conflict_id=X resolution=X' - 解决冲突\n"
            "- 'intensify conflict conflict_id=X increase=X trigger=X' - 升级冲突\n"
            "- 'create arc arc_id=X conflicts=X pattern=X' - 创建冲突弧线\n"
            "- 'list relationships' - 列出关系\n"
            "- 'check relationship character1=X character2=X' - 检查关系\n"
            "- 'list conflicts [status=X] [type=X]' - 列出冲突"
        )
        return self._create_message(response)

    def _generate_conflict(
        self,
        conflict_type: ConflictType,
        participants: List[str],
        chapter_id: str,
        intensity: int,
        context: str = ""
    ) -> Conflict:
        """
        生成冲突

        Args:
            conflict_type: 冲突类型
            participants: 参与者
            chapter_id: 章节ID
            intensity: 强度
            context: 上下文

        Returns:
            Conflict实例
        """
        self._last_conflict_id += 1
        conflict_id = f"conflict_{chapter_id}_{self._last_conflict_id:04d}"

        # 生成冲突描述
        description = self._create_conflict_description(conflict_type, participants, intensity, context)

        # 确定初始阶段
        if intensity < 20:
            status = ConflictStatus.DORMANT
        elif intensity < 40:
            status = ConflictStatus.EMERGING
        elif intensity < 60:
            status = ConflictStatus.INTENSIFYING
        elif intensity < 80:
            status = ConflictStatus.CRISIS
        else:
            status = ConflictStatus.RESOLVING

        conflict = Conflict(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            description=description,
            participants=participants,
            chapter_id=chapter_id,
            status=status,
            intensity=intensity,
            created_at=time.time(),
            stages=[{
                "stage": status.value,
                "intensity": intensity,
                "timestamp": time.time()
            }]
        )

        return conflict

    def _create_conflict_description(
        self,
        conflict_type: ConflictType,
        participants: List[str],
        intensity: int,
        context: str
    ) -> str:
        """创建冲突描述"""
        templates = {
            ConflictType.INTERNAL: (
                "{context} struggles with {participant}'s conflicting desires. "
                "The internal battle intensifies as {context} faces the consequences "
                "of their own decisions."
            ),
            ConflictType.INTERPERSONAL: (
                "{context} between {participants} reaches a breaking point. "
                "Words turn to accusations as {context} reveals hidden truths."
            ),
            ConflictType.SOCIAL: (
                "{context} the social order as {participants} challenge established norms. "
                "Factions form and alliances shift in the turmoil."
            ),
            ConflictType.EXTERNAL: (
                "{context} from outside forces puts {participants} to the test. "
                "Survival instincts take over as the threat approaches."
            ),
            ConflictType.ENVIRONMENTAL: (
                "{context} the harsh environment threatens {participants}. "
                "Resources dwindle and tensions rise in the struggle to survive."
            ),
            ConflictType.MORAL: (
                "{context} the moral dilemma as {participants} face an impossible choice. "
                "The cost of their decisions will echo for years to come."
            ),
            ConflictType.PHILOSOPHICAL: (
                "{context} fundamental beliefs collide as {participants} question "
                "the nature of reality and their place in it."
            ),
        }

        template = templates.get(conflict_type, templates[ConflictType.INTERPERSONAL])
        participants_str = ", ".join(participants[:2]) if len(participants) > 1 else participants[0]
        description = template.format(
            context=context or "Tension builds",
            participants=participants_str,
            participant=participants[0] if participants else "the character"
        )

        # 基于强度调整描述
        if intensity > 70:
            description += " The situation threatens to spiral completely out of control."
        elif intensity < 30:
            description += " Subtle signs of discord begin to show."

        return description

    def _generate_consequences(
        self,
        conflict_type: ConflictType,
        participants: List[str],
        intensity: int,
        resolution_type: str
    ) -> List[str]:
        """生成冲突后果"""
        consequences = []

        # 基于冲突类型生成后果
        if conflict_type == ConflictType.INTERNAL:
            consequences.append(
                f"{participants[0]} experiences lasting psychological impact from the internal struggle"
            )
            consequences.append(
                f"Decision-making capacity may be compromised in future situations"
            )
        elif conflict_type == ConflictType.INTERPERSONAL:
            consequences.append(
                f"Trust between {participants[0]} and {participants[1]} is permanently damaged"
            )
            if intensity > 60:
                consequences.append(
                    f"Physical separation becomes necessary for safety"
                )
        elif conflict_type == ConflictType.SOCIAL:
            consequences.append(
                "Social standing affected; factions form around opposing viewpoints"
            )
            consequences.append(
                "Community privileges may be revoked or granted based on stance"
            )
        elif conflict_type == ConflictType.EXTERNAL:
            consequences.append(
                "Survival strategies must change in response to the threat"
            )
            consequences.append(
                "New alliances formed out of necessity"
            )

        # 基于强度调整后果
        if intensity > 80:
            consequences.append("Catalyst for major plot转折; everything changes")

        # 基于解决类型调整
        if resolution_type == "resolved":
            if intensity > 70:
                consequences.append("Temporary truce, but underlying issues remain")
            else:
                consequences.append("Mutual understanding achieved; relationship strengthened")

        return consequences[:5]  # 限制返回数量

    def _update_relationship(
        self,
        character1: str,
        character2: str,
        change: int,
        context: str
    ) -> RelationshipChange:
        """
        更新关系

        Args:
            character1: 角色1
            character2: 角色2
            change: 变化值（-100到100）
            context: 上下文

        Returns:
            RelationshipChange实例
        """
        self._last_change_id += 1
        change_id = f"rel_change_{self._last_change_id:06d}"

        # 更新分数
        current = self._relationships[character1][character2]
        new_score = max(-100, min(100, current + change))

        # 记录变化
        relationship_change = RelationshipChange(
            change_id=change_id,
            from_character=character1,
            to_character=character2,
            change_type="increase" if change > 0 else "decrease" if change < 0 else "neutral",
            magnitude=change,
            context=context,
            timestamp=time.time()
        )

        self._relationship_changes.append(relationship_change)
        self._relationships[character1][character2] = new_score
        self._relationships[character2][character1] = new_score  # 对称更新

        return relationship_change

    def _get_relationship_type(self, score: float) -> str:
        """获取关系类型"""
        if score >= 70:
            return "allies"
        elif score >= 40:
            return "friends"
        elif score >= 10:
            return "acquaintances"
        elif score >= -20:
            return "neutral"
        elif score >= -50:
            return "rivals"
        elif score >= -80:
            return "enemies"
        else:
            return "fierce enemies"

    def _get_intensity_bar(self, intensity: int) -> str:
        """获取强度条"""
        bar_length = 20
        filled = int(intensity / 5)
        empty = bar_length - filled
        return f"[{'#' * filled}{'-' * empty}]"

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

    def generate_conflict(
        self,
        conflict_type: str,
        participants: List[str],
        chapter_id: str,
        intensity: int = 40,
        context: str = ""
    ) -> Optional[Conflict]:
        """生成冲突（外部接口）"""
        try:
            conflict = self._generate_conflict(
                conflict_type=ConflictType(conflict_type.lower()),
                participants=participants,
                chapter_id=chapter_id,
                intensity=intensity,
                context=context
            )
            self._conflicts[conflict.conflict_id] = conflict
            self._conflict_count += 1
            return conflict
        except Exception:
            return None

    def resolve_conflict(self, conflict_id: str, resolution: str = "") -> bool:
        """解决冲突（外部接口）"""
        if conflict_id in self._conflicts:
            conflict = self._conflicts[conflict_id]
            conflict.status = ConflictStatus.RESOLVED
            conflict.resolution = resolution
            conflict.resolved_at = time.time()
            return True
        return False

    def intensify_conflict(self, conflict_id: str, increase: int = 15) -> bool:
        """升级冲突（外部接口）"""
        if conflict_id in self._conflicts:
            conflict = self._conflicts[conflict_id]
            conflict.intensity = min(100, conflict.intensity + increase)
            conflict.stages.append({
                "stage": "intensified",
                "previous_intensity": conflict.intensity - increase,
                "new_intensity": conflict.intensity,
                "timestamp": time.time()
            })
            return True
        return False

    def get_conflict(self, conflict_id: str) -> Optional[Conflict]:
        """获取冲突"""
        return self._conflicts.get(conflict_id)

    def get_conflicts_by_status(self, status: ConflictStatus) -> List[Conflict]:
        """按状态获取冲突"""
        return [c for c in self._conflicts.values() if c.status == status]

    def get_conflicts_by_type(self, conflict_type: ConflictType) -> List[Conflict]:
        """按类型获取冲突"""
        return [c for c in self._conflicts.values() if c.conflict_type == conflict_type]

    def get_conflicts_by_chapter(self, chapter_id: str) -> List[Conflict]:
        """按章节获取冲突"""
        return [c for c in self._conflicts.values() if c.chapter_id == chapter_id]

    def get_relationship(self, character1: str, character2: str) -> float:
        """获取关系分值"""
        return self._relationships.get(character1, {}).get(character2, 0)

    def get_all_relationships(self) -> Dict[str, Dict[str, float]]:
        """获取所有关系"""
        return dict(self._relationships)

    def get_conflict_arcs(self) -> Dict[str, ConflictArc]:
        """获取所有冲突弧线"""
        return self._conflict_arcs

    def export_conflicts(self) -> Dict[str, Any]:
        """导出冲突数据"""
        return {
            "conflicts": {k: v.to_dict() for k, v in self._conflicts.items()},
            "arcs": {k: v.to_dict() for k, v in self._conflict_arcs.items()},
            "relationships": {
                k: dict(v) for k, v in self._relationships.items()
            },
            "relationship_changes": [c.to_dict() for c in self._relationship_changes[-50:]],
            "statistics": {
                "total_conflicts": len(self._conflicts),
                "total_arcs": len(self._conflict_arcs),
                "total_changes": len(self._relationship_changes),
                "conflict_count": self._conflict_count
            }
        }

    def reset(self) -> None:
        """重置智能体"""
        self._conflicts.clear()
        self._conflict_arcs.clear()
        self._relationships.clear()
        self._relationship_changes.clear()
        self._last_conflict_id = 0
        self._last_change_id = 0
        self._conflict_count = 0
