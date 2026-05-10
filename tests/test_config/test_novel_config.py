"""
NovelConfig 单元测试

测试 Pydantic 配置模型的验证、转换和便捷方法。
"""

import pytest
from pydantic import ValidationError

from deepnovel.config.novel_config import (
    ChapterConfig,
    CharacterConfig,
    GenreType,
    NovelConfig,
    POVType,
    PowerSystemType,
    StyleType,
    ToneType,
    WorldConfig,
)


# ---- NovelConfig 基础测试 ----


class TestNovelConfigCreation:
    def test_minimal_valid(self):
        config = NovelConfig(title="测试小说", genre="xianxia")
        assert config.title == "测试小说"
        assert config.genre == GenreType.XIUXIA
        assert config.max_chapters == 50
        assert config.word_count_per_chapter == 3000

    def test_full_config(self):
        config = NovelConfig(
            title="修仙之路",
            genre="xianxia",
            style=StyleType.DESCRIPTIVE,
            tone=ToneType.EPIC,
            max_chapters=100,
            word_count_per_chapter=5000,
            world=WorldConfig(
                world_name="青云界",
                power_system=PowerSystemType.QI_CULTIVATION,
            ),
            themes=["成长", "逆天改命"],
        )
        assert config.world.world_name == "青云界"
        assert config.world.power_system == PowerSystemType.QI_CULTIVATION
        assert config.themes == ["成长", "逆天改命"]

    def test_invalid_genre(self):
        with pytest.raises(ValidationError):
            NovelConfig(title="测试", genre="invalid_genre")

    def test_title_too_long(self):
        with pytest.raises(ValidationError):
            NovelConfig(title="x" * 101, genre="fantasy")

    def test_title_empty(self):
        with pytest.raises(ValidationError):
            NovelConfig(title="", genre="fantasy")


class TestNovelConfigValidation:
    def test_total_word_count_valid(self):
        config = NovelConfig(
            title="测试",
            genre="fantasy",
            max_chapters=10,
            word_count_per_chapter=1000,
            total_word_count_target=12000,  # 在合理范围内
        )
        assert config.total_word_count_target == 12000

    def test_total_word_count_too_high(self):
        with pytest.raises(ValidationError):
            NovelConfig(
                title="测试",
                genre="fantasy",
                max_chapters=10,
                word_count_per_chapter=1000,
                total_word_count_target=50000,  # 超出预期范围
            )

    def test_total_word_count_too_low(self):
        with pytest.raises(ValidationError):
            NovelConfig(
                title="测试",
                genre="fantasy",
                max_chapters=10,
                word_count_per_chapter=1000,
                total_word_count_target=1000,  # 低于预期范围
            )

    def test_protagonist_validation_pass(self):
        config = NovelConfig(
            title="测试",
            genre="fantasy",
            characters=[
                CharacterConfig(name="主角", char_type="protagonist"),
                CharacterConfig(name="反派", char_type="antagonist"),
            ],
        )
        assert len(config.characters) == 2

    def test_protagonist_validation_fail(self):
        with pytest.raises(ValidationError):
            NovelConfig(
                title="测试",
                genre="fantasy",
                characters=[
                    CharacterConfig(name="配角", char_type="supporting"),
                ],
            )

    def test_no_characters_no_validation(self):
        # 没有角色时不验证主角存在性
        config = NovelConfig(title="测试", genre="fantasy", characters=[])
        assert config.characters == []


class TestNovelConfigMethods:
    def test_get_protagonist(self):
        config = NovelConfig(
            title="测试",
            genre="fantasy",
            characters=[
                CharacterConfig(name="张三", char_type="protagonist"),
            ],
        )
        protag = config.get_protagonist()
        assert protag is not None
        assert protag.name == "张三"

    def test_get_protagonist_none(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.get_protagonist() is None

    def test_estimate_total_word_count(self):
        config = NovelConfig(
            title="测试", genre="fantasy", max_chapters=10, word_count_per_chapter=2000
        )
        assert config.estimate_total_word_count() == 20000

    def test_to_generation_context(self):
        config = NovelConfig(
            title="修仙传",
            genre="xianxia",
            characters=[
                CharacterConfig(
                    name="林凡", char_type="protagonist", background="孤儿"
                ),
            ],
            themes=["修仙", "成长"],
        )
        ctx = config.to_generation_context()
        assert ctx["title"] == "修仙传"
        assert ctx["genre"] == "xianxia"
        assert ctx["genre_display"] == "修仙"
        assert ctx["protagonist_name"] == "林凡"
        assert ctx["protagonist_background"] == "孤儿"
        assert ctx["themes"] == "修仙, 成长"
        assert ctx["language"] == "中文"

    def test_pov_display(self):
        config = NovelConfig(
            title="测试", genre="fantasy", pov=POVType.FIRST_PERSON
        )
        ctx = config.to_generation_context()
        assert ctx["pov_display"] == "第一人称"

    def test_genre_display_fallback(self):
        config = NovelConfig(title="测试", genre="horror")
        assert config._get_genre_display() == "horror"


class TestNovelConfigDefaults:
    def test_default_style(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.style == StyleType.DESCRIPTIVE

    def test_default_tone(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.tone == ToneType.SERIOUS

    def test_default_pace(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.pace == "medium"

    def test_default_language(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.language == "zh-CN"

    def test_default_world(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.world.power_system == PowerSystemType.NONE

    def test_default_outline(self):
        config = NovelConfig(title="测试", genre="fantasy")
        assert config.outline.three_act_structure.act_1_chapters == 3


class TestCharacterConfig:
    def test_valid_character(self):
        char = CharacterConfig(name="张三", char_type="protagonist", age=20)
        assert char.name == "张三"
        assert char.age == 20

    def test_character_defaults(self):
        char = CharacterConfig(name="李四")
        assert char.char_type == "supporting"
        assert char.personality == []
        assert char.goals == []

    def test_invalid_age(self):
        with pytest.raises(ValidationError):
            CharacterConfig(name="测试", age=-1)

    def test_invalid_age_too_high(self):
        with pytest.raises(ValidationError):
            CharacterConfig(name="测试", age=1001)


class TestWorldConfig:
    def test_world_creation(self):
        world = WorldConfig(
            world_name="魔法大陆",
            power_system=PowerSystemType.MAGIC,
            cultures=["精灵", "矮人"],
        )
        assert world.world_name == "魔法大陆"
        assert len(world.cultures) == 2


class TestChapterConfig:
    def test_chapter_defaults(self):
        ch = ChapterConfig(chapter_number=1)
        assert ch.word_count_target == 3000
        assert ch.cliffhanger is False

    def test_invalid_chapter_number(self):
        with pytest.raises(ValidationError):
            ChapterConfig(chapter_number=0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
