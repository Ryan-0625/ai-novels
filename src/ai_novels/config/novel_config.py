"""
NovelConfig — 小说配置模型（Pydantic）

类型安全的小说生成配置，支持：
- 枚举约束（Genre/Tone/POV等）
- 层级嵌套（World → Character → Outline）
- 验证器（总字数合理性、主角存在性）
- 转换为生成上下文（Prompt模板使用）

@file: config/novel_config.py
@date: 2026-04-29
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenreType(str, Enum):
    """小说类型枚举"""
    ROMANCE = "romance"
    SCI_FI = "sci-fi"
    FANTASY = "fantasy"
    MYSTERY = "mystery"
    DRAMA = "drama"
    ADVENTURE = "adventure"
    HISTORY = "history"
    XIUXIA = "xianxia"
    WUXIA = "wuxia"
    URBAN_FANTASY = "urban_fantasy"
    HORROR = "horror"
    THRILLER = "thriller"
    OTHER = "other"


class ToneType(str, Enum):
    """基调类型"""
    DARK = "dark"
    LIGHT = "light"
    SERIOUS = "serious"
    HUMOROUS = "humorous"
    EPIC = "epic"
    INTIMATE = "intimate"
    MELANCHOLIC = "melancholic"
    HOPEFUL = "hopeful"


class PaceType(str, Enum):
    """节奏类型"""
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class POVType(str, Enum):
    """视角类型"""
    FIRST_PERSON = "first_person"
    THIRD_PERSON_LIMITED = "third_person_limited"
    THIRD_PERSON_OMNISCIENT = "third_person_omniscient"
    SECOND_PERSON = "second_person"


class TargetAudience(str, Enum):
    """目标受众"""
    CHILDREN = "children"
    YOUNG_ADULT = "young_adult"
    ADULT = "adult"
    ALL_AGES = "all_ages"


class StyleType(str, Enum):
    """叙事风格"""
    DESCRIPTIVE = "descriptive"
    CONCISE = "concise"
    POETIC = "poetic"
    DIALOGUE_HEAVY = "dialogue_heavy"
    STREAM_OF_CONSCIOUSNESS = "stream_of_consciousness"
    REPORTER = "reporter"


class PowerSystemType(str, Enum):
    """力量体系类型"""
    MAGIC = "magic"
    QI_CULTIVATION = "qi_cultivation"
    TECHNOLOGY = "technology"
    PSIONIC = "psionic"
    DIVINE = "divine"
    NONE = "none"


# ───────────────────────────────────────────────
# 嵌套配置模型
# ───────────────────────────────────────────────


class WorldConfig(BaseModel):
    """世界配置"""

    world_name: Optional[str] = Field(None, description="世界名称")
    world_description: Optional[str] = Field(None, description="世界描述")
    geography: Optional[str] = Field(None, description="地理环境")
    cultures: List[str] = Field(default_factory=list, description="文化体系")
    factions: List[str] = Field(default_factory=list, description="势力/门派")
    power_system: PowerSystemType = Field(
        PowerSystemType.NONE, description="力量体系"
    )
    power_system_details: Optional[str] = Field(None, description="力量体系详细设定")
    historical_events: List[str] = Field(default_factory=list, description="历史事件")
    rules: List[str] = Field(default_factory=list, description="世界规则")
    technology_level: Optional[str] = Field(None, description="科技水平")


class CharacterArcConfig(BaseModel):
    """角色弧线配置"""

    arc_type: Literal["growth", "fall", "circular", "flat"] = "growth"
    initial_state: Optional[str] = None
    turning_points: List[str] = Field(default_factory=list)
    final_state: Optional[str] = None


class CharacterConfig(BaseModel):
    """角色配置"""

    name: str = Field(..., min_length=1, max_length=50, description="角色名称")
    char_type: Literal[
        "protagonist", "antagonist", "supporting", "mentor", "foil"
    ] = "supporting"
    age: Optional[int] = Field(None, ge=0, le=1000)
    gender: Optional[Literal["male", "female", "non_binary", "unknown"]] = None
    appearance: Optional[str] = Field(None, description="外貌描述")
    personality: List[str] = Field(default_factory=list, description="性格特征")
    background: Optional[str] = Field(None, description="背景故事")
    goals: List[str] = Field(default_factory=list, description="目标")
    fears: List[str] = Field(default_factory=list, description="恐惧")
    secrets: List[str] = Field(default_factory=list, description="秘密")
    skills: List[str] = Field(default_factory=list, description="技能/能力")
    relationships: Dict[str, str] = Field(
        default_factory=dict, description="与其他角色的关系"
    )
    arc: Optional[CharacterArcConfig] = None
    voice_style: Optional[str] = Field(None, description="说话风格")


class ChapterConfig(BaseModel):
    """章节配置"""

    chapter_number: int = Field(..., ge=1)
    title: Optional[str] = None
    word_count_target: int = Field(3000, ge=500, le=50000)
    plot_points: List[str] = Field(default_factory=list)
    characters_present: List[str] = Field(default_factory=list)
    setting: Optional[str] = None
    tone_shift: Optional[str] = None
    cliffhanger: bool = False


class ThreeActStructure(BaseModel):
    """三幕结构"""

    act_1_chapters: int = Field(3, ge=1, description="第一幕章节数")
    act_2_chapters: int = Field(10, ge=1, description="第二幕章节数")
    act_3_chapters: int = Field(3, ge=1, description="第三幕章节数")
    inciting_incident_chapter: Optional[int] = None
    first_plot_point_chapter: Optional[int] = None
    midpoint_chapter: Optional[int] = None
    second_plot_point_chapter: Optional[int] = None
    climax_chapter: Optional[int] = None


class EmotionalArcConfig(BaseModel):
    """情感弧线配置"""

    stage_name: str
    intensity: int = Field(5, ge=1, le=10)
    description: Optional[str] = None


class OutlineConfig(BaseModel):
    """大纲配置"""

    three_act_structure: ThreeActStructure = Field(default_factory=ThreeActStructure)
    emotional_arc: List[EmotionalArcConfig] = Field(default_factory=list)
    chapters: List[ChapterConfig] = Field(default_factory=list)
    main_plot_threads: List[str] = Field(default_factory=list)
    subplot_threads: List[str] = Field(default_factory=list)
    foreshadowing_points: List[str] = Field(default_factory=list)
    twists: List[str] = Field(default_factory=list)


# ───────────────────────────────────────────────
# 主配置模型
# ───────────────────────────────────────────────


class NovelConfig(BaseModel):
    """
    小说完整配置

    所有小说生成任务的基础配置模型。
    """

    # 基础信息
    novel_id: Optional[str] = Field(None, description="小说唯一ID")
    title: str = Field(..., min_length=1, max_length=100, description="小说标题")
    genre: GenreType = Field(..., description="小说类型")
    subtitle: Optional[str] = Field(None, description="副标题")
    description: Optional[str] = Field(None, description="简介")

    # 叙事参数
    style: StyleType = Field(StyleType.DESCRIPTIVE, description="叙事风格")
    tone: ToneType = Field(ToneType.SERIOUS, description="基调")
    pace: PaceType = Field(PaceType.MEDIUM, description="节奏")
    pov: POVType = Field(POVType.THIRD_PERSON_LIMITED, description="视角")
    target_audience: TargetAudience = Field(TargetAudience.ADULT, description="目标受众")
    language: str = Field("zh-CN", description="语言")

    # 结构参数
    max_chapters: int = Field(50, ge=1, le=1000, description="最大章节数")
    word_count_per_chapter: int = Field(
        3000, ge=500, le=50000, description="每章目标字数"
    )
    total_word_count_target: Optional[int] = Field(None, description="总目标字数")

    # 世界观
    world: WorldConfig = Field(default_factory=WorldConfig)

    # 角色
    characters: List[CharacterConfig] = Field(default_factory=list)

    # 大纲
    outline: OutlineConfig = Field(default_factory=OutlineConfig)

    # 主题与标签
    themes: List[str] = Field(default_factory=list, description="主题")
    tags: List[str] = Field(default_factory=list, description="标签")
    tropes: List[str] = Field(default_factory=list, description="套路/桥段")

    # 写作约束
    writing_constraints: Dict[str, Any] = Field(
        default_factory=dict, description="写作约束"
    )
    forbidden_elements: List[str] = Field(default_factory=list, description="禁止元素")
    required_elements: List[str] = Field(default_factory=list, description="必须包含元素")

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: str = Field("1.0", description="配置版本")
    preset_name: Optional[str] = Field(None, description="使用的预设名称")

    # 运行时配置
    llm_override: Optional[Dict[str, Any]] = Field(None, description="LLM参数覆盖")
    rag_enabled: bool = Field(True, description="是否启用RAG")
    auto_save: bool = Field(True, description="是否自动保存")

    @field_validator("total_word_count_target")
    @classmethod
    def validate_total_word_count(cls, v: Optional[int], info) -> Optional[int]:
        """验证总字数目标是否合理"""
        if v is not None:
            data = info.data
            max_chapters = data.get("max_chapters", 50)
            word_per_ch = data.get("word_count_per_chapter", 3000)
            expected = max_chapters * word_per_ch
            if v > expected * 2 or v < expected * 0.5:
                raise ValueError(
                    f"总字数目标({v})与章节配置不匹配，"
                    f"预期范围: {expected * 0.5:.0f} - {expected * 2:.0f}"
                )
        return v

    @field_validator("characters")
    @classmethod
    def validate_protagonist_exists(cls, v: List[CharacterConfig]) -> List[CharacterConfig]:
        """验证至少有一个主角（如果有角色的话）"""
        if v and not any(c.char_type == "protagonist" for c in v):
            raise ValueError("至少需要一个主角(protagonist)")
        return v

    def get_protagonist(self) -> Optional[CharacterConfig]:
        """获取主角"""
        for char in self.characters:
            if char.char_type == "protagonist":
                return char
        return None

    def estimate_total_word_count(self) -> int:
        """估算总字数"""
        return self.max_chapters * self.word_count_per_chapter

    def _get_enum_value(self, field) -> str:
        """安全获取枚举值（兼容 use_enum_values 后的字符串存储）"""
        return field.value if hasattr(field, "value") else str(field)

    def to_generation_context(self) -> Dict[str, Any]:
        """转换为生成上下文（供Prompt模板使用）"""
        protagonist = self.get_protagonist()
        return {
            "title": self.title,
            "genre": self._get_enum_value(self.genre),
            "genre_display": self._get_genre_display(),
            "style": self._get_enum_value(self.style),
            "tone": self._get_enum_value(self.tone),
            "pace": self._get_enum_value(self.pace),
            "pov": self._get_enum_value(self.pov),
            "pov_display": self._get_pov_display(),
            "max_chapters": self.max_chapters,
            "word_count_per_chapter": self.word_count_per_chapter,
            "world_name": self.world.world_name,
            "world_description": self.world.world_description,
            "power_system": self._get_enum_value(self.world.power_system),
            "protagonist_name": protagonist.name if protagonist else "主角",
            "protagonist_background": protagonist.background if protagonist else "",
            "themes": ", ".join(self.themes) if self.themes else "未指定",
            "language": "中文" if self.language.startswith("zh") else "English",
        }

    def _get_genre_display(self) -> str:
        """获取类型显示名称"""
        genre_names = {
            GenreType.XIUXIA: "修仙",
            GenreType.WUXIA: "武侠",
            GenreType.ROMANCE: "言情",
            GenreType.FANTASY: "奇幻",
            GenreType.SCI_FI: "科幻",
            GenreType.MYSTERY: "悬疑",
            GenreType.HISTORY: "历史",
        }
        return genre_names.get(self.genre, self._get_enum_value(self.genre))

    def _get_pov_display(self) -> str:
        """获取视角显示名称"""
        pov_names = {
            POVType.FIRST_PERSON: "第一人称",
            POVType.THIRD_PERSON_LIMITED: "第三人称有限",
            POVType.THIRD_PERSON_OMNISCIENT: "第三人称全知",
        }
        return pov_names.get(self.pov, self._get_enum_value(self.pov))

    model_config = ConfigDict(
        use_enum_values=True,
        validate_assignment=True,
    )
