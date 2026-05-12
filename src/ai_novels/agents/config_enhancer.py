"""
ConfigEnhancerAgent - 配置增强智能体

@file: agents/config_enhancer.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 配置解析/LLM增强/Schema验证
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from .base import BaseAgent, AgentConfig, Message, MessageType


class EnhancementStage(Enum):
    """增强阶段"""
    PARSING = "parsing"
    EXPANDING = "expanding"
    VALIDATING = "validating"
    FINALIZING = "finalizing"


@dataclass
class EnhancedConfig:
    """增强后的配置"""
    original_config: Dict[str, Any]
    enhanced_config: Dict[str, Any]
    schema_validation: Dict[str, Any]
    enhancement_details: Dict[str, Any]
    warnings: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "original": self.original_config,
            "enhanced": self.enhanced_config,
            "validation": self.schema_validation,
            "details": self.enhancement_details,
            "warnings": self.warnings,
            "errors": self.errors
        }


class ConfigEnhancerAgent(BaseAgent):
    """
    配置增强智能体

    核心功能：
    - 解析用户需求配置
    - 使用LLM增强配置细节
    - Schema验证
    - 配置完整性检查
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="config_enhancer",
                description="Configuration analysis and enhancement",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=8192
            )
        super().__init__(config)

        # Schema定义
        self._base_schema = {
            "type": "object",
            "required": ["genre", "title", "max_chapters"],
            "properties": {
                "genre": {"type": "string", "enum": ["romance", "sci-fi", "fantasy", "mystery", "drama", "adventure", "history", "other"]},
                "title": {"type": "string", "minLength": 1},
                "max_chapters": {"type": "integer", "minimum": 1, "maximum": 1000},
                "word_count_per_chapter": {"type": "integer", "minimum": 1000, "maximum": 50000},
                "style": {"type": "string"},
                "theme": {"type": "string"},
                "target_audience": {"type": "string", "enum": ["children", "yOUNG_ADULT", "adult", "all"]},
                "tone": {"type": "string", "enum": ["dark", "light", "serious", "humorous", "epic", "intimate"]},
                "pace": {"type": "string", "enum": ["slow", "medium", "fast"]},
                " POV": {"type": "string", "enum": ["first_person", "third_person_limited", "third_person_omniscient"]},
                "setting": {"type": "string"},
                ".override_llm_config": {"type": "object"}
            }
        }

        self._current_stage = EnhancementStage.PARSING
        self._last_enhancement: Optional[EnhancedConfig] = None

    def process(self, message: Message) -> Message:
        """处理消息 - 配置增强"""
        content = str(message.content)

        if "enhance" in content.lower():
            return self._handle_enhance_request(message)
        elif "validate" in content.lower():
            return self._handle_validate_request(message)
        elif "parse" in content.lower():
            return self._handle_parse_request(message)
        elif "schema" in content.lower():
            return self._handle_schema_request(message)
        else:
            return self._handle_general_request(message)

    def _handle_enhance_request(self, message: Message) -> Message:
        """处理增强请求"""
        self._current_stage = EnhancementStage.PARSING

        # 解析输入
        config = self._parse_config_input(str(message.content))

        # 阶段1: 解析
        self._current_stage = EnhancementStage.PARSING
        parsed = self._parse_config(config)

        # 阶段2: 扩展
        self._current_stage = EnhancementStage.EXPANDING
        expanded = self._expand_config(parsed)

        # 阶段3: 验证
        self._current_stage = EnhancementStage.VALIDATING
        validated = self._validate_config(expanded)

        # 阶段4: 完成
        self._current_stage = EnhancementStage.FINALIZING

        # 创建增强配置
        enhancement = EnhancedConfig(
            original_config=config,
            enhanced_config=validated,
            schema_validation={
                "valid": len(validated.get("errors", [])) == 0,
                "errors": validated.get("errors", []),
                "warnings": validated.get("warnings", [])
            },
            enhancement_details={
                "stages": [s.value for s in EnhancementStage],
                "expanded_fields": list(set(expanded.keys()) - set(config.keys()))
                if isinstance(expanded, dict) and isinstance(config, dict) else [],
                "validation_result": "passed" if len(validated.get("errors", [])) == 0 else "failed"
            },
            warnings=validated.get("warnings", []),
            errors=validated.get("errors", [])
        )

        self._last_enhancement = enhancement

        return self._create_message(
            self._format_enhancement_result(enhancement),
            MessageType.TEXT,
            stage=self._current_stage.value,
            task_id=str(self._hash_config(config))
        )

    def _handle_validate_request(self, message: Message) -> Message:
        """处理验证请求"""
        config = self._parse_config_input(str(message.content))

        validation = self._validate_config(config)

        if validation.get("errors"):
            response = (
                "Configuration validation FAILED:\n"
                f"Errors: {len(validation['errors'])}\n"
                f"Warnings: {len(validation['warnings'])}\n\n"
            )
            for error in validation["errors"]:
                response += f"  ✗ {error}\n"
        else:
            response = (
                "Configuration validation PASSED! ✓\n"
                f"Warnings: {len(validation['warnings'])}\n\n"
            )
            for warning in validation["warnings"]:
                response += f"  ⚠ {warning}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            validation_passed=len(validation.get("errors", [])) == 0
        )

    def _handle_parse_request(self, message: Message) -> Message:
        """处理解析请求"""
        config = self._parse_config_input(str(message.content))

        parsed = self._parse_config(config)

        response = "Configuration Parsed:\n"
        response += f"  Genre: {parsed.get('genre', 'N/A')}\n"
        response += f"  Title: {parsed.get('title', 'N/A')}\n"
        response += f"  Max Chapters: {parsed.get('max_chapters', 'N/A')}\n"
        response += f"  Style: {parsed.get('style', 'N/A')}\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            parsed_keys=list(parsed.keys())
        )

    def _handle_schema_request(self, message: Message) -> Message:
        """处理Schema请求"""
        schema_str = json.dumps(self._base_schema, indent=2, ensure_ascii=False)

        return self._create_message(
            f"Available Configuration Schema:\n```json\n{schema_str}\n```",
            MessageType.TEXT,
            schema_fields=list(self._base_schema.get("properties", {}).keys())
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Config Enhancer available commands:\n"
            "- 'enhance [config]' - 增强配置\n"
            "- 'validate [config]' - 验证配置\n"
            "- 'parse [config]' - 解析配置\n"
            "- 'schema' - 显示Schema定义"
        )
        return self._create_message(response)

    def _parse_config_input(self, content: str) -> Dict[str, Any]:
        """解析配置输入"""
        # 尝试解析JSON
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 简单的键值对解析
        config = {}
        for line in content.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                config[key.strip().lower()] = value.strip()

        return config

    def _parse_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """解析配置"""
        parsed = {}

        # 解析 genre
        genre_map = {
            "爱情": "romance", " romance": "romance",
            "科幻": "sci-fi", " sci-fi": "sci-fi", "科幻小说": "sci-fi",
            "玄幻": "fantasy", "奇幻": "fantasy", " fantasy": "fantasy",
            "悬疑": "mystery", " mystery": "mystery",
            " drama": "drama", "剧情": "drama",
            "冒险": "adventure", " adventure": "adventure",
            "历史": "history", " history": "history"
        }

        genre = config.get("genre") or config.get("类型")
        if genre:
            genre_lower = str(genre).lower()
            parsed["genre"] = genre_map.get(genre_lower, genre_lower)
        else:
            parsed["genre"] = "other"

        # 解析标题
        title = config.get("title") or config.get("标题") or config.get("name") or "Untitled Novel"
        parsed["title"] = title

        # 解析章节数
        max_chapters = config.get("max_chapters") or config.get("章节数") or config.get(" chapters")
        if max_chapters:
            try:
                parsed["max_chapters"] = int(max_chapters)
            except ValueError:
                parsed["max_chapters"] = 50  # 默认值
        else:
            parsed["max_chapters"] = 50

        # 解析风格
        style = config.get("style") or config.get("风格") or config.get("文风")
        if style:
            parsed["style"] = style
        else:
            parsed["style"] = "descriptive"

        # 解析主题
        theme = config.get("theme") or config.get("主题")
        if theme:
            parsed["theme"] = theme

        # 解析其他可选字段
        optional_fields = {
            "target_audience": ["目标受众", "audience"],
            "tone": ["语气", "语调", "tone"],
            "pace": ["节奏", " pace"],
            "POV": ["视角", " PO", "人称"],
            "setting": ["背景", " world", "世界观"],
            "word_count_per_chapter": ["字数", "章节字数"]
        }

        for field, aliases in optional_fields.items():
            value = config.get(field)
            if not value:
                for alias in aliases:
                    if alias in config:
                        value = config[alias]
                        break
            if value:
                parsed[field] = value

        return parsed

    def _expand_config(self, parsed_config: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM扩展配置"""
        expanded = parsed_config.copy()

        # 如果缺少说明，添加默认说明
        if "description" not in expanded:
            expanded["description"] = f"A {expanded.get('genre', 'generic')} novel titled '{expanded.get('title', 'Untitled')}' with {expanded.get('max_chapters', 50)} chapters."

        # 添加风格细节
        style_details = self._get_style_details(expanded.get("style", "descriptive"))
        expanded["style_details"] = style_details

        # 添加建议的章节数
        if "chapter_structure" not in expanded:
            expanded["chapter_structure"] = self._suggest_chapter_structure(
                expanded.get("max_chapters", 50),
                expanded.get("genre", "other")
            )

        # 添加情感弧线建议
        expanded["emotional_arc"] = self._suggest_emotional_arc(
            expanded.get("genre", "other"),
            expanded.get("tone", "neutral")
        )

        return expanded

    def _get_style_details(self, style: str) -> Dict[str, Any]:
        """获取风格细节"""
        styles = {
            "descriptive": {
                "word_count_range": [3000, 5000],
                "sentence_structure": "complex",
                "description_level": "detailed"
            },
            "concise": {
                "word_count_range": [2000, 3500],
                "sentence_structure": "simple",
                "description_level": "moderate"
            },
            "poetic": {
                "word_count_range": [2500, 4000],
                "sentence_structure": "lyrical",
                "description_level": "evocative"
            },
            "dialogue_heavy": {
                "word_count_range": [2500, 4500],
                "sentence_structure": "conversational",
                "description_level": "minimal"
            }
        }
        return styles.get(style, styles["descriptive"])

    def _suggest_chapter_structure(self, max_chapters: int, genre: str) -> Dict[str, Any]:
        """建议章节目录结构"""
        # 三幕结构
        ACT_1_END = max(3, max_chapters // 10)
        ACT_2_END = max(int(max_chapters * 0.75), ACT_1_END + 5)

        structure = {
            "three_act_structure": {
                "act_1": {"chapters": f"1-{ACT_1_END}", "purpose": "Introduction"},
                "act_2": {"chapters": f"{ACT_1_END + 1}-{ACT_2_END}", "purpose": "Confrontation"},
                "act_3": {"chapters": f"{ACT_2_END + 1}-{max_chapters}", "purpose": "Resolution"}
            },
            "章节点": {
                "inciting_incident": f"Chapter {ACT_1_END}",
                "first_plot_point": f"Chapter {ACT_1_END}",
                "midpoint": f"Chapter {max(15, max_chapters // 2)}",
                "second_plot_point": f"Chapter {ACT_2_END}",
                "climax": f"Chapter {max_chapters}"
            }
        }

        return structure

    def _suggest_emotional_arc(self, genre: str, tone: str) -> List[Dict[str, Any]]:
        """建议情感弧线"""
        arcs = {
            "romance": [
                {"stage": "Initial Attraction", "intensity": 3},
                {"stage": "Obstacles", "intensity": 6},
                {"stage": "Crisis", "intensity": 9},
                {"stage": "Resolution", "intensity": 7}
            ],
            "fantasy": [
                {"stage": "Call to Adventure", "intensity": 4},
                {"stage": "Training/Tests", "intensity": 5},
                {"stage": "Major Battle", "intensity": 9},
                {"stage": "Return", "intensity": 6}
            ],
            "mystery": [
                {"stage": "Incident", "intensity": 5},
                {"stage": "Investigation", "intensity": 6},
                {"stage": "Clues/Red Herrings", "intensity": 7},
                {"stage": "Revelation", "intensity": 10}
            ]
        }

        return arcs.get(genre, [
            {"stage": "Introduction", "intensity": 3},
            {"stage": "Development", "intensity": 5},
            {"stage": "Climax", "intensity": 9},
            {"stage": "Conclusion", "intensity": 6}
        ])

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证配置"""
        errors = []
        warnings = []

        # 要求字段验证
        required_fields = ["title", "genre", "max_chapters"]
        for field in required_fields:
            if field not in config or not config[field]:
                errors.append(f"Missing required field: {field}")

        # 字段值验证
        if "max_chapters" in config:
            try:
                chapters = int(config["max_chapters"])
                if chapters < 1:
                    warnings.append("Chapter count is very low (less than 1)")
                elif chapters > 1000:
                    warnings.append("Chapter count is very high (over 1000)")
            except ValueError:
                errors.append("max_chapters must be a number")

        if "genre" in config:
            valid_genres = ["romance", "sci-fi", "fantasy", "mystery", "drama", "adventure", "history", "other"]
            if config["genre"] not in valid_genres:
                warnings.append(f"Genre '{config['genre']}' is not in the standard list")

        if "title" in config and config["title"]:
            if len(config["title"]) > 100:
                warnings.append("Title is very long (over 100 characters)")

        return {
            "errors": errors,
            "warnings": warnings,
            "valid": len(errors) == 0
        }

    def _format_enhancement_result(self, enhancement: EnhancedConfig) -> str:
        """格式化增强结果"""
        lines = ["=== Configuration Enhancement Result ===", ""]

        # 状态
        status = "✓ VALID" if enhancement.schema_validation["valid"] else "✗ INVALID"
        lines.append(f"Status: {status}")
        lines.append("")

        # 原始配置
        lines.append("Original Configuration:")
        for key, value in enhancement.original_config.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

        # 增强后的配置
        lines.append("Enhanced Configuration:")
        for key, value in enhancement.enhanced_config.items():
            if key not in enhancement.original_config:
                lines.append(f" 新增: {key}: {value}")
        lines.append("")

        # 验证结果
        lines.append("Validation:")
        if enhancement.schema_validation["warnings"]:
            for warning in enhancement.schema_validation["warnings"]:
                lines.append(f"  ⚠ {warning}")
        if enhancement.schema_validation["errors"]:
            for error in enhancement.schema_validation["errors"]:
                lines.append(f"  ✗ {error}")
        lines.append("")

        # 增强详情
        lines.append("Enhancement Details:")
        lines.append(f"  Stages: {', '.join(enhancement.enhancement_details.get('stages', []))}")
        lines.append(f"  Validation: {enhancement.enhancement_details.get('validation_result', 'N/A')}")

        return "\n".join(lines)

    def _hash_config(self, config: Dict[str, Any]) -> int:
        """计算配置hash"""
        return hash(json.dumps(config, sort_keys=True))

    def get_last_enhancement(self) -> Optional[EnhancedConfig]:
        """获取最后一次增强结果"""
        return self._last_enhancement

    def reset(self) -> None:
        """重置增强器"""
        self._current_stage = EnhancementStage.PARSING
        self._last_enhancement = None
