"""
CharacterGeneratorAgent - 角色生成智能体

@file: agents/character_generator.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 角色生成/关系图谱/记忆初始化
"""

import json
import random
import uuid
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from .base import BaseAgent, AgentConfig, Message, MessageType
from ai_novels.utils import log_error
from ai_novels.persistence import PersistenceManager, get_persistence_manager
from ai_novels.persistence.agent_persist import CharacterPersistence


class CharacterType(Enum):
    """角色类型"""
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MENTOR = "mentor"
    LOVE_INTEREST = "love_interest"
    SIDE_CHARACTER = "side_character"


class RelationType(Enum):
    """关系类型"""
    FRIEND = "friend"
    ENEMY = "enemy"
    FAMILY = "family"
    ALLY = "ally"
    RIVAL = "rival"
    LOVER = "lover"
    MENTOR = "mentor"
    former = "former"
    UNKNOWN = "unknown"


@dataclass
class Character:
    """角色档案"""
    name: str
    char_type: CharacterType
    age: int
    gender: str
    personality: List[str]
    background: str
    goals: List[str]
    secrets: List[str]
    relations: Dict[str, RelationType] = field(default_factory=dict)
    memories: List[str] = field(default_factory=list)
    Traits: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class CharacterRelationship:
    """角色关系"""
    character1: str
    character2: str
    relation_type: RelationType
    strength: int  # 0-100
    history: str
    status: str = "active"


class CharacterGeneratorAgent(BaseAgent):
    """
    角色生成智能体

    核心功能：
    - 生成角色档案
    - 构建关系图谱
    - 初始化角色记忆
    - 管理角色属性
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="character_generator",
                description="Character profile generation",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=16384
            )
        super().__init__(config)

        self._characters: Dict[str, Character] = {}
        self._relationships: List[CharacterRelationship] = []
        self._current_genre = "fantasy"
        self._current_novel_title = "Untitled Novel"

    def process(self, message: Message) -> Message:
        """处理消息 - 角色生成"""
        content = str(message.content).lower()

        if "generate" in content or "create" in content or "character" in content:
            return self._handle_generate_request(message)
        elif "relationship" in content or "relation" in content:
            return self._handle_relationship_request(message)
        elif "memory" in content or "memory" in content:
            return self._handle_memory_request(message)
        elif "list" in content:
            return self._handle_list_request(message)
        elif "status" in content:
            return self._handle_status_request(message)
        else:
            return self._handle_generate_request(message)

    def _get_task_id_from_message(self, message: Message) -> str:
        """从消息中获取任务ID"""
        # 优先级1: metadata
        if hasattr(message, 'metadata') and message.metadata:
            tid = message.metadata.get("task_id", "")
            if tid:
                return tid
        # 优先级2: 从消息文本解析 ("Task ID: xxx" 或 "task_id=xxx")
        content = str(message.content) if hasattr(message, 'content') else ""
        for marker in ("Task ID: ", "task_id="):
            idx = content.find(marker)
            if idx >= 0:
                start = idx + len(marker)
                end = start
                while end < len(content) and content[end] not in " \t\r\n,;":
                    end += 1
                tid = content[start:end]
                if tid:
                    return tid
        # 优先级3: 随机fallback
        return f"task_{uuid.uuid4().hex[:8]}"

    def _handle_generate_request(self, message: Message) -> Message:
        """处理生成请求"""
        config = self._parse_config(str(message.content))
        task_id = self._get_task_id_from_message(message)

        # 保存上下文
        self._current_genre = config.get("genre", "fantasy")
        self._current_novel_title = config.get("title", "Untitled Novel")

        # 获取持久化管理器
        pm = get_persistence_manager()

        # 生成主角
        protagonist = self._generate_character(
            name="Protagonist",
            char_type=CharacterType.PROTAGONIST,
            genre=self._current_genre
        )

        # 生成反派
        antagonist = self._generate_character(
            name="Antagonist",
            char_type=CharacterType.ANTAGONIST,
            genre=self._current_genre
        )

        # 生成配角
        side_characters = [
            self._generate_character(
                name=f"Side Character {i}",
                char_type=CharacterType.SIDE_CHARACTER,
                genre=self._current_genre
            )
            for i in range(1, 4)
        ]

        # 生成盟友/mentor
        allies = [
            self._generate_character(
                name=f"Allies {i}",
                char_type=CharacterType.SUPPORTING,
                genre=self._current_genre
            )
            for i in range(1, 3)
        ]

        # 存储角色
        all_characters = [protagonist, antagonist] + side_characters + allies
        for char in all_characters:
            self._characters[char.name] = char

        # 生成关系
        self._generate_relationships(all_characters)

        # 初始化记忆
        for char in all_characters:
            self._initialize_memories(char)

        # === 持久化到数据库 ===
        if pm.mongodb_client and pm.neo4j_client:
            for char in all_characters:
                # 保存角色到MongoDB
                char_type_str = char.char_type.value if hasattr(char.char_type, 'value') else str(char.char_type)
                character_data = {
                    "name": char.name,
                    "age": char.age,
                    "gender": char.gender,
                    "personality": char.personality,
                    "background": char.background,
                    "goals": char.goals,
                    "secrets": char.secrets,
                    "weaknesses": char.weaknesses,
                    "traits": char.Traits,
                    "memories": char.memories
                }
                CharacterPersistence.save_character(
                    pm, task_id, char.name, char_type_str, character_data
                )

            # 保存角色关系到Neo4j
            for rel in self._relationships:
                rel_type_str = rel.relation_type.value if hasattr(rel.relation_type, 'value') else str(rel.relation_type)
                CharacterPersistence.save_relationship(
                    pm, task_id, rel.character1, rel.character2, rel_type_str, rel.strength
                )

        response = (
            f"Generated {len(all_characters)} characters for '{self._current_novel_title}'\n"
            f"Genre: {self._current_genre}\n\n"
        )

        for char in all_characters:
            response += f"=== {char.name} ===\n"
            response += f"Type: {char.char_type.value}\n"
            response += f"Age: {char.age}, Gender: {char.gender}\n"
            response += f"Personality: {', '.join(char.personality[:5])}\n"
            response += f"Goals: {', '.join(char.goals[:2])}\n"
            response += f"Relations: {len(char.relations)}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            characters_generated=len(all_characters),
            genre=self._current_genre,
            task_id=task_id
        )

    def _handle_relationship_request(self, message: Message) -> Message:
        """处理关系请求"""
        content = str(message.content)

        if "add" in content:
            return self._handle_add_relationship(content)

        # 返回所有关系
        response = "Character Relationships:\n"
        for rel in self._relationships:
            response += (
                f"  {rel.character1} <-> {rel.character2}: "
                f"{rel.relation_type.value} (strength: {rel.strength}/100)\n"
            )

        return self._create_message(
            response if self._relationships else "No relationships defined yet.",
            MessageType.TEXT,
            relationship_count=len(self._relationships)
        )

    def _handle_memory_request(self, message: Message) -> Message:
        """处理记忆请求"""
        content = str(message.content)
        name = self._extract_name(content)

        if name and name in self._characters:
            char = self._characters[name]
            if char.memories:
                response = f"Memories for {name}:\n"
                for i, memory in enumerate(char.memories[:5], 1):
                    response += f"  {i}. {memory}\n"
                response += f"  ... and {len(char.memories) - 5} more memories" if len(char.memories) > 5 else ""
            else:
                response = f"No memories for {name} yet."
        else:
            # 列出所有角色的记忆
            response = "All Character Memories:\n"
            for name, char in self._characters.items():
                response += f"  {name}: {len(char.memories)} memories\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            memory_type="character"
        )

    def _handle_list_request(self, message: Message) -> Message:
        """处理列表请求"""
        content = str(message.content)

        if "character" in content or "all" in content:
            response = "Characters:\n"
            for name, char in self._characters.items():
                response += f"  - {name} ({char.char_type.value})\n"
            response += f"\nTotal: {len(self._characters)} characters"
        elif "relationship" in content or "relation" in content:
            return self._handle_relationship_request(message)
        else:
            response = "Use 'list characters' or 'list relationships'"

        return self._create_message(
            response,
            MessageType.TEXT,
            character_count=len(self._characters),
            relationship_count=len(self._relationships)
        )

    def _handle_status_request(self, message: Message) -> Message:
        """处理状态请求"""
        response = (
            f"Character Generator Status:\n"
            f"Characters: {len(self._characters)}\n"
            f"Relationships: {len(self._relationships)}\n"
            f"Genre: {self._current_genre}\n"
            f"Novel: {self._current_novel_title}"
        )
        return self._create_message(
            response,
            MessageType.TEXT
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Character Generator commands:\n"
            "- 'generate characters [genre]' - 生成角色\n"
            "- 'list characters' - 列出角色\n"
            "- 'list relationships' - 列出关系\n"
            "- 'relationship add [char1] [char2] [type]' - 添加关系\n"
            "- 'memories [name]' - 查看角色记忆"
        )
        return self._create_message(response)

    def _parse_config(self, content: str) -> Dict[str, Any]:
        """解析配置"""
        config = {
            "genre": "fantasy",
            "title": "Untitled Novel",
            "character_count": 5
        }

        content_lower = content.lower()
        if " romance" in content_lower:
            config["genre"] = "romance"
        elif " sci-fi" in content_lower or "科幻" in content:
            config["genre"] = "sci-fi"
        elif " mystery" in content_lower or "悬疑" in content:
            config["genre"] = "mystery"
        elif " historical" in content_lower or "历史" in content:
            config["genre"] = "historical"

        return config

    def _extract_name(self, content: str) -> Optional[str]:
        """从内容中提取角色名"""
        content_lower = content.lower()

        for name in self._characters.keys():
            if name.lower() in content_lower:
                return name

        return None

    def _generate_character(self, name: str, char_type: CharacterType, genre: str) -> Character:
        """生成单个角色 - 使用LLM生成中文角色名和档案"""
        # 使用LLM生成角色（含中文姓名）
        character = self._generate_character_with_llm(name, char_type, genre)

        if character:
            return character

        # Fallback: 使用原有的随机生成方法
        return self._generate_character_fallback(name, char_type, genre)

    def _generate_character_with_llm(self, name: str, char_type: CharacterType, genre: str) -> Optional[Character]:
        """使用LLM生成角色（含中文姓名）"""
        char_type_str = char_type.value if hasattr(char_type, 'value') else str(char_type)

        llm_prompt = f"""Create a detailed character profile for a Chinese {genre} novel.

Character Type: {char_type_str}

Important: Generate a proper CHINESE name (姓+名, e.g. 林清风, 苏暮雪, 萧逸尘) appropriate for a {genre} novel.
The genre is "{genre}", so pick names that fit the setting.

Please generate:
0. name: Chinese name (REQUIRED — 2-3 characters, surname + given name)
1. age: 16-60
2. gender: Male or Female
3. personality: 5 personality traits in English words
4. goals: 2-3 important goals (in Chinese)
5. background: Genre-appropriate backstory (in Chinese, 50-100 chars)
6. weaknesses: 3 flaws or fears (in Chinese)
7. secrets: 1-2 secrets (in Chinese)

Return as JSON with keys: name, age, gender, personality (array), goals (array), background, weaknesses (array), secrets (array).
Return ONLY valid JSON, no other text."""

        llm_response = self._generate_with_llm(llm_prompt, "You are a character creator for Chinese novels.")
        if llm_response:
            try:
                import json as json_module
                # 尝试解析JSON
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx + 1]
                    data = json_module.loads(json_str)

                    # 使用LLM生成的中文名（如有），否则使用占位名
                    chinese_name = data.get("name", "").strip()
                    if not chinese_name or len(chinese_name) < 2:
                        chinese_name = name

                    # 构建Character对象
                    return Character(
                        name=chinese_name,
                        char_type=char_type,
                        age=data.get("age", 25),
                        gender=data.get("gender", "Male"),
                        personality=data.get("personality", ["Curious", "Brave", "Determined", "Compassionate", "Flawed"]),
                        goals=data.get("goals", ["Find their place in the world"]),
                        background=data.get("background", "A mysterious past"),
                        weaknesses=data.get("weaknesses", ["Trust issues"]),
                        secrets=data.get("secrets", ["A dark secret"])
                    )
            except Exception as e:
                log_error(f"Failed to parse LLM character response: {e}")

        return None

    def _generate_character_fallback(self, name: str, char_type: CharacterType, genre: str) -> Character:
        """ fallback方法生成角色"""
        # 根据类型和风格生成属性
        if char_type == CharacterType.PROTAGONIST:
            age = random.randint(18, 35)
            gender = random.choice(["Male", "Female", "Non-binary"])
            personality = random.sample([
                "Brave", "Curious", "Determined", "Compassionate", "Flawed",
                "Intelligent", "Witty", "Skeptical", "Optimistic", "Stubborn"
            ], 5)
            goals = [
                f"Uncover the truth about {genre}",
                "Find their place in the world",
                "Protect their loved ones",
                "Achieve a specific goal related to genre"
            ]
        elif char_type == CharacterType.ANTAGONIST:
            age = random.randint(25, 50)
            gender = random.choice(["Male", "Female", "Non-binary"])
            personality = random.sample([
                "Manipulative", "Cruel", "Obsessed", "Charming", "Intelligent",
                "Selfish", "Vindictive", "Controlled", "Ruthless", "Complex"
            ], 5)
            goals = [
                "Achieve power at any cost",
                "Destroy the protagonist",
                "Maintain control over others",
                "Prove their philosophy"
            ]
        else:
            age = random.randint(16, 60)
            gender = random.choice(["Male", "Female", "Non-binary"])
            personality = random.sample([
                "Loyal", "Witty", "Careful", "Spontaneous", "Diligent",
                "Calm", "Passionate", "Pragmatic", "Idealistic", "Sarcastic"
            ], 4)
            goals = [
                "Support the protagonist",
                "Achieve their own goal",
                "Protect someone important",
                "Resolve a personal issue"
            ]

        # 生成背景故事
        backgrounds = {
            "fantasy": [
                "Born into a noble family",
                "Raised by unknown parents",
                "A member of a forbidden magic school",
                "A legendary hero reborn",
                "A cast-out member of a prestigious clan"
            ],
            "romance": [
                "Working in a unique profession",
                "Recently went through a breakup",
                "Running a family business",
                "Moving to a new city",
                "Reconnecting with an old friend"
            ],
            "sci-fi": [
                "A cybernetic enhancement subject",
                "A space trader with a mysterious past",
                "A hacker fighting the system",
                "A colonist on a hostile planet",
                "A scientist discovers a world-changing invention"
            ],
            "mystery": [
                "A detective with a traumatic past",
                "A journalist chasing a big story",
                "A witness to a crime",
                "A thief with a code of honor",
                "A lawyer taking on an impossible case"
            ]
        }

        char_backgrounds = backgrounds.get(genre, backgrounds["fantasy"])
        background = random.choice(char_backgrounds)

        # 弱点和秘密
        weaknesses = random.sample([
            "Fear of heights", "Trust issues", "Reckless when angry",
            "Overprotective", "Self-doubt", "Addiction", "Pride",
            "Insecurity", "Vengeful", "Impulsive"
        ], 3)

        secrets = [
            f"A dark secret from their past",
            f"An identity they're hiding",
            f"A betrayal they committed",
            f"A sacrifice they made"
        ]

        return Character(
            name=name,
            char_type=char_type,
            age=age,
            gender=gender,
            personality=personality,
            background=background,
            goals=random.sample(goals, 3),
            secrets=random.sample(secrets, 2),
            relations={},
            memories=[],
            Traits=personality,
            weaknesses=weaknesses
        )

    def _generate_relationships(self, characters: List[Character]) -> None:
        """生成角色关系"""
        for i, char1 in enumerate(characters):
            for char2 in characters[i + 1:]:
                # 随机决定关系
                relation = random.choice([
                    RelationType.FRIEND, RelationType.ALLY, RelationType.RIVAL,
                    RelationType.ENEMY, RelationType.FAMILY, RelationType.UNKNOWN
                ])

                # 创建关系
                rel = CharacterRelationship(
                    character1=char1.name,
                    character2=char2.name,
                    relation_type=relation,
                    strength=random.randint(30, 100),
                    history=f"The relationship between {char1.name} and {char2.name} has a complex history."
                )
                self._relationships.append(rel)

                # 更新角色的relations
                char1.relations[char2.name] = relation
                char2.relations[char1.name] = relation

    def _initialize_memories(self, character: Character) -> None:
        """初始化角色记忆"""
        # 基于背景生成记忆
        memory_templates = [
            f"A memory from childhood that shaped {character.name}",
            f"A pivotal moment in {character.name}'s past",
            f"A lesson learned the hard way",
            f"A promise made to someone important",
            f"A regret that haunts {character.name}"
        ]

        character.memories = random.sample(memory_templates, 3)

        # 基于关系添加记忆
        for related_char, relation in character.relations.items():
            character.memories.append(
                f"A {relation.value} memory with {related_char}"
            )

    def _handle_add_relationship(self, content: str) -> Message:
        """处理添加关系请求"""
        # 简单解析
        parts = content.split()
        if len(parts) >= 4:
            char1 = parts[parts.index("add") + 1] if "add" in parts else None
            char2 = parts[parts.index("add") + 2] if "add" in parts else None
            rel_type = parts[parts.index("add") + 3] if "add" in parts else None

            if char1 and char2 and rel_type in [r.value for r in RelationType]:
                # 创建关系
                rel = CharacterRelationship(
                    character1=char1,
                    character2=char2,
                    relation_type=RelationType(rel_type),
                    strength=75,
                    history=f"Relationship established: {rel_type}"
                )
                self._relationships.append(rel)

                # 更新角色关系
                if char1 in self._characters:
                    self._characters[char1].relations[char2] = RelationType(rel_type)
                if char2 in self._characters:
                    self._characters[char2].relations[char1] = RelationType(rel_type)

                return self._create_message(
                    f"Added relationship: {char1} <-> {char2} ({rel_type})",
                    MessageType.TEXT
                )

        return self._create_message(
            "Usage: relationship add [char1] [char2] [friend/enemy/rival/family]",
            MessageType.TEXT
        )

    def get_character(self, name: str) -> Optional[Character]:
        """获取角色"""
        return self._characters.get(name)

    def get_characters_by_type(self, char_type: CharacterType) -> List[Character]:
        """按类型获取角色"""
        return [c for c in self._characters.values() if c.char_type == char_type]

    def get_relationships(self, character_name: str) -> List[CharacterRelationship]:
        """获取角色的关系"""
        return [
            r for r in self._relationships
            if r.character1 == character_name or r.character2 == character_name
        ]

    def get_all_characters(self) -> Dict[str, Character]:
        """获取所有角色"""
        return self._characters

    def get_all_relationships(self) -> List[CharacterRelationship]:
        """获取所有关系"""
        return self._relationships

    def update_character_memories(self, name: str, memories: List[str]) -> bool:
        """更新角色记忆"""
        if name in self._characters:
            self._characters[name].memories.extend(memories)
            return True
        return False

    def reset(self) -> None:
        """重置角色生成器"""
        self._characters.clear()
        self._relationships.clear()
        self._current_genre = "fantasy"
        self._current_novel_title = "Untitled Novel"
