"""
WorldBuilderAgent - 世界观构建智能体

@file: agents/world_builder.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 世界实体/魔法系统/地理/势力
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
from ai_novels.persistence import get_persistence_manager
from ai_novels.persistence.agent_persist import WorldPersistence


class WorldElementType(Enum):
    """世界元素类型"""
    LOCATION = "location"
    CULTURE = "culture"
    FACTION = "faction"
    MAGIC_SYSTEM = "magic_system"
    HISTORICAL_EVENT = "historical_event"


@dataclass
class Location:
    """地理位置"""
    name: str
    type: str  # city, country, forest, mountain, etc.
    description: str
    features: List[str]
    significance: str
    danger_level: int  # 0-10


@dataclass
class Culture:
    """文化设定"""
    name: str
    values: List[str]
    customs: List[str]
    language_features: str
    religion: str
    art_and_music: str


@dataclass
class Faction:
    """势力设定"""
    name: str
    ideology: str
    goals: List[str]
    leader: str
    members: int
    influence: int  # 0-100
    enemies: List[str] = field(default_factory=list)
    allies: List[str] = field(default_factory=list)


@dataclass
class MagicSystem:
    """魔法系统"""
    name: str
    source: str  # mana, spirit, blood, etc.
    rules: List[str]
    limitations: List[str]
    schools: List[str]
    notable_practitioners: List[str] = field(default_factory=list)


@dataclass
class Historicalevent:
    """历史事件"""
    name: str
    date: str
    description: str
    consequences: List[str]
    relevant_factions: List[str] = field(default_factory=list)


class WorldBuilderAgent(BaseAgent):
    """
    世界观构建智能体

    核心功能：
    - 构建地理位置
    - 设定文化传统
    - 创造势力组织
    - 设计魔法系统
    - 记录历史事件
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="world_builder",
                description="World setting and culture building",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=16384
            )
        super().__init__(config)

        self._locations: Dict[str, Location] = {}
        self._cultures: Dict[str, Culture] = {}
        self._factions: Dict[str, Faction] = {}
        self._magic_systems: Dict[str, MagicSystem] = {}
        self._historical_events: List[Historicalevent] = []
        self._current_genre = "fantasy"
        self._world_name = "Unknown World"

    def process(self, message: Message) -> Message:
        """处理消息 - 世界观构建"""
        content = str(message.content).lower()

        if "build" in content or "create" in content or "world" in content:
            return self._handle_build_request(message)
        elif "location" in content or "place" in content:
            return self._handle_location_request(message)
        elif "culture" in content or "custom" in content:
            return self._handle_culture_request(message)
        elif "faction" in content or "group" in content or "organization" in content:
            return self._handle_faction_request(message)
        elif "magic" in content or "spell" in content or "power" in content:
            return self._handle_magic_request(message)
        elif "history" in content or "event" in content:
            return self._handle_history_request(message)
        elif "list" in content:
            return self._handle_list_request(message)
        else:
            return self._handle_build_request(message)

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

    def _handle_build_request(self, message: Message) -> Message:
        """处理构建请求"""
        config = self._parse_config(str(message.content))
        task_id = self._get_task_id_from_message(message)

        # 保存上下文
        self._current_genre = config.get("genre", "fantasy")
        self._world_name = config.get("title", "Unknown World")

        # 获取持久化管理器
        pm = get_persistence_manager()

        # 构建地理位置
        self._build_locations()

        # 构建文化
        self._build_cultures()

        # 构建势力
        self._build_factions()

        # 构建魔法系统
        self._build_magic_system()

        # 构建历史事件
        self._build_historical_events()

        # === 持久化到数据库 ===
        if pm.mongodb_client and pm.neo4j_client:
            # 保存地点
            for name, loc in self._locations.items():
                loc_data = {
                    "name": loc.name,
                    "type": loc.type,
                    "description": loc.description,
                    "features": loc.features,
                    "significance": loc.significance,
                    "danger_level": loc.danger_level
                }
                WorldPersistence.save_location(pm, task_id, loc_data)

            # 保存势力
            for name, faction in self._factions.items():
                fact_data = {
                    "name": faction.name,
                    "ideology": faction.ideology,
                    "goals": faction.goals,
                    "leader": faction.leader,
                    "members": faction.members,
                    "influence": faction.influence,
                    "enemies": faction.enemies,
                    "allies": faction.allies
                }
                WorldPersistence.save_faction(pm, task_id, fact_data)

        response = (
            f"World '{self._world_name}' built for genre: {self._current_genre}\n\n"
            f"Locations: {len(self._locations)}\n"
            f"Cultures: {len(self._cultures)}\n"
            f"Factions: {len(self._factions)}\n"
            f"Magic Systems: {len(self._magic_systems)}\n"
            f"Historical Events: {len(self._historical_events)}"
        )

        return self._create_message(
            response,
            MessageType.TEXT,
            locations_build=len(self._locations),
            cultures_build=len(self._cultures),
            factions_build=len(self._factions),
            task_id=task_id
        )

    def _handle_location_request(self, message: Message) -> Message:
        """处理地点请求"""
        content = str(message.content)

        if "list" in content:
            response = "Locations:\n"
            for name, loc in self._locations.items():
                response += f"  - {name} ({loc.type})\n"
            return self._create_message(
                response if self._locations else "No locations built yet.",
                MessageType.TEXT,
                location_count=len(self._locations)
            )
        else:
            return self._create_message(
                "Use 'list locations' to see all locations.",
                MessageType.TEXT
            )

    def _handle_culture_request(self, message: Message) -> Message:
        """处理文化请求"""
        content = str(message.content)

        if "list" in content:
            response = "Cultures:\n"
            for name, culture in self._cultures.items():
                response += f"  - {name}\n"
                response += f"    Values: {', '.join(culture.values[:3])}\n"
            return self._create_message(
                response if self._cultures else "No cultures built yet.",
                MessageType.TEXT,
                culture_count=len(self._cultures)
            )
        else:
            return self._create_message(
                "Use 'list cultures' to see all cultures.",
                MessageType.TEXT
            )

    def _handle_faction_request(self, message: Message) -> Message:
        """处理势力请求"""
        content = str(message.content)

        if "list" in content:
            response = "Factions:\n"
            for name, faction in self._factions.items():
                response += f"  - {name} ({faction.influence}/100 influence)\n"
                response += f"    Ideology: {faction.ideology}\n"
            return self._create_message(
                response if self._factions else "No factions built yet.",
                MessageType.TEXT,
                faction_count=len(self._factions)
            )
        else:
            return self._create_message(
                "Use 'list factions' to see all factions.",
                MessageType.TEXT
            )

    def _handle_magic_request(self, message: Message) -> Message:
        """处理魔法请求"""
        content = str(message.content)

        if "list" in content:
            response = "Magic Systems:\n"
            for name, magic in self._magic_systems.items():
                response += f"  - {name}\n"
                response += f"    Source: {magic.source}\n"
                response += f"    Schools: {', '.join(magic.schools)}\n"
            return self._create_message(
                response if self._magic_systems else "No magic systems built yet.",
                MessageType.TEXT,
                magic_system_count=len(self._magic_systems)
            )
        elif "rules" in content:
            response = "Magic Rules:\n"
            for magic in self._magic_systems.values():
                response += f"\n{magic.name}:\n"
                for rule in magic.rules:
                    response += f"  - {rule}\n"
            return self._create_message(
                response if self._magic_systems else "No magic rules available.",
                MessageType.TEXT
            )
        else:
            return self._create_message(
                "Use 'list magic' to see magic systems, or 'magic rules' for rules.",
                MessageType.TEXT
            )

    def _handle_history_request(self, message: Message) -> Message:
        """处理历史请求"""
        content = str(message.content)

        if "list" in content:
            response = "Historical Events:\n"
            for event in self._historical_events:
                response += f"  - {event.name} ({event.date})\n"
                response += f"    {event.description[:100]}...\n"
            return self._create_message(
                response if self._historical_events else "No historical events built yet.",
                MessageType.TEXT,
                event_count=len(self._historical_events)
            )
        else:
            return self._create_message(
                "Use 'list history' to see historical events.",
                MessageType.TEXT
            )

    def _handle_list_request(self, message: Message) -> Message:
        """处理列表请求"""
        response = (
            f"World '{self._world_name}' Summary:\n"
            f"Locations: {len(self._locations)}\n"
            f"Cultures: {len(self._cultures)}\n"
            f"Factions: {len(self._factions)}\n"
            f"Magic Systems: {len(self._magic_systems)}\n"
            f"Historical Events: {len(self._historical_events)}"
        )
        return self._create_message(
            response,
            MessageType.TEXT
        )

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "World Builder commands:\n"
            "- 'build world [genre]' - 构建世界\n"
            "- 'list locations' - 列出地点\n"
            "- 'list cultures' - 列出文化\n"
            "- 'list factions' - 列出势力\n"
            "- 'list magic' - 列出魔法系统\n"
            "- 'list history' - 列出历史事件"
        )
        return self._create_message(response)

    def _parse_config(self, content: str) -> Dict[str, Any]:
        """解析配置"""
        config = {
            "genre": "fantasy",
            "title": "Unknown World",
            "scale": "epic"
        }

        content_lower = content.lower()
        if " sci-fi" in content_lower or "科幻" in content:
            config["genre"] = "sci-fi"
        elif " mystery" in content_lower or "悬疑" in content:
            config["genre"] = "mystery"
        elif " historical" in content_lower or "历史" in content:
            config["genre"] = "historical"

        return config

    def _build_locations(self) -> None:
        """构建地理位置 - 使用LLM"""
        # 首先尝试使用LLM生成
        if self._generate_locations_with_llm():
            return

        # Fallback: 使用原有的随机生成方法
        self._build_locations_fallback()

    def _generate_locations_with_llm(self) -> bool:
        """使用LLM生成地理位置"""
        llm_prompt = f"""Create detailed locations for a {self._current_genre} world named "{self._world_name}".

Generate 10 unique locations with:
1. Name: Interesting, genre-appropriate name
2. Type: city, country, forest, mountain, desert, island, ruin, or town
3. Description: Brief evocative description
4. Features: 3-4 notable features
5. Significance: Why this location matters
6. Danger Level: 0-10

Return as JSON array of location objects.
Return ONLY valid JSON, no other text."""

        llm_response = self._generate_with_llm(llm_prompt, "You are a world builder.")

        if llm_response:
            try:
                import json as json_module
                start_idx = llm_response.find('[')
                end_idx = llm_response.rfind(']')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = llm_response[start_idx:end_idx + 1]
                    locations_data = json_module.loads(json_str)

                    for loc_data in locations_data:
                        name = loc_data.get("name", f"Location {len(self._locations) + 1}")
                        loc_type = loc_data.get("type", "city")
                        loc = Location(
                            name=name,
                            type=loc_type,
                            description=loc_data.get("description", f"A {loc_type} known as {name}."),
                            features=loc_data.get("features", ["Notable feature"]),
                            significance=loc_data.get("significance", f"Important in {self._world_name}"),
                            danger_level=loc_data.get("danger_level", 3)
                        )
                        self._locations[name] = loc

                    return True
            except Exception as e:
                log_error(f"Failed to parse LLM location response: {e}")

        return False

    def _build_locations_fallback(self) -> None:
        """fallback方法生成地理位置"""
        location_types = ["city", "country", "forest", "mountain", "desert", "island", "ruin", "town"]
        location_templates = {
            "fantasy": {
                "prefix": ["Ancient", "Lost", "Hidden", "Sacred", "Eternal", "Forgotten"],
                "root": ["Realms", "Kingdom", "Forest", "Peak", "Valley", "Lands", "City", "Empire"],
                "suffix": ["of the秋", "of Light", "of Darkness", "of Winds", "of Fire", "of Eternity"]
            },
            "sci-fi": {
                "prefix": ["Nova", "Stellar", "Cyber", "Void", "Neon", "Quantum"],
                "root": ["Sector", "Colony", "Station", "Planet", "System", "Outpost", "City", "Hub"],
                "suffix": ["Alpha", "Prime", "X", "XXX", "Omega", "Zero"]
            },
            "historical": {
                "prefix": ["Kingdom of", "Empire of", "Republic of", "Province of", "Duchy of"],
                "root": ["Land", "Realm", "Kingdom", "Empire", "Republic", "State"],
                "suffix": ["the Great", "the Wise", "the Eternal", "the Brave"]
            }
        }

        templates = location_templates.get(self._current_genre, location_templates["fantasy"])

        locations = [
            "Capital City", "Borderlands", "Sacred Grove", "(TMincing Mountain",
            "Shadow Forest", "Sunken City", "Dragon's Peak", "Kingdom of Eldoria",
            "The Wilds", "Merchant Road", "Old Ruins", "Temple of Lights"
        ]

        for name in locations:
            loc_type = random.choice(location_types)
            loc = Location(
                name=name,
                type=loc_type,
                description=f"A {loc_type} known as {name}.",
                features=self._generate_location_features(loc_type),
                significance=f"Important location in {self._world_name}",
                danger_level=random.randint(0, 8)
            )
            self._locations[name] = loc

    def _generate_location_features(self, loc_type: str) -> List[str]:
        """生成地点特征"""
        features_map = {
            "city": ["population: 100000", "政治 center", "Trade hub", "Cultural center", "Fortified walls"],
            "forest": ["Ancient trees", "Wildlife diverse", "Mysterious atmosphere", "Hidden paths", "Dangerous creatures"],
            "mountain": ["Treacherous cliffs", "Snow-capped peaks", "Ancient ruins", "Mineral rich", "Spiritual significance"],
            "desert": ["Endless dunes", "Scorching heat", "Oasis settlements", "Ancient relics", "Sand storms"],
            "island": ["Remote location", "Unique ecosystem", "Pirate Hideout", "Ancient ruins", "Treasure helm"]
        }
        return features_map.get(loc_type, features_map["city"])

    def _build_cultures(self) -> None:
        """构建文化设定"""
        cultures = [
            ("High Elves", "wisdom", "nature"), ("Dark Dwarves", "craft", " stone"),
            ("Human Kingdoms", "tradition", "order"), ("Nomadic Tribes", "freedom", "survival"),
            ("Merchant Guilds", "wealth", "commerce"), ("Mystic Orders", "knowledge", "spirit")
        ]

        values_map = {
            "wisdom": ["Knowledge", "Truth", "Enlightenment", "Learning"],
            "craft": ["Skill", "Creation", "Perfection", "Tradition"],
            "nature": ["Harmony", "Growth", "Balance", "Life"],
            "tradition": ["Heritage", "History", "Ritual", "Order"],
            "freedom": ["Independence", "Choice", "Self-determination", "Liberty"],
            "wealth": ["Prosperity", "Success", "Influence", "Comfort"]
        }

        for name, value1, value2 in cultures:
            culture = Culture(
                name=name,
                values=values_map.get(value1, ["Value 1", "Value 2"]) + values_map.get(value2, []),
                customs=self._generate_customs(name),
                language_features="Distinct accent and vocabulary",
                religion=self._generate_religion(name),
                art_and_music=f"Unique art style for {name}"
            )
            self._cultures[name] = culture

    def _generate_customs(self, culture_name: str) -> List[str]:
        """生成文化习俗"""
        customs_list = [
            "Welcome rituals", "Harvest festivals", "Coming-of-age ceremonies",
            "Marriage traditions", "Death rituals", "Seasonal celebrations"
        ]
        return random.sample(customs_list, 4)

    def _generate_religion(self, culture_name: str) -> str:
        """生成宗教设定"""
        religions = [
            "Polytheistic worship of nature deities",
            "Monotheistic faith in a single creator",
            "Ancestor veneration and spirit worship",
            "Philosophical school focusing on balance",
            "Mystical order practicing ancient rituals"
        ]
        return random.choice(religions)

    def _build_factions(self) -> None:
        """构建势力设定"""
        ideologies = [
            "Preserve traditional order and hierarchy",
            "Promote radical change and progress",
            "Seek knowledge at any cost",
            "Protect the weak and uphold justice",
            "Pursue personal power and influence",
            "Maintain balance between opposing forces"
        ]

        for i in range(5):
            faction = Faction(
                name=f"Faction {i + 1}",
                ideology=random.choice(ideologies),
                goals=[
                    f"Achieve dominance in {self._world_name}",
                    "Protect their beliefs and interests",
                    "Uncover ancient secrets",
                    "Overthrow the current regime"
                ],
                leader=f"Leader {i + 1}",
                members=random.randint(100, 10000),
                influence=random.randint(10, 100)
            )
            self._factions[faction.name] = faction

        # 添加敌对和盟友关系
        faction_names = list(self._factions.keys())
        for i, name in enumerate(faction_names):
            other = faction_names[(i + 1) % len(faction_names)]
            self._factions[name].enemies.append(other)
            self._factions[other].allies.append(name)

    def _build_magic_system(self) -> None:
        """构建魔法系统"""
        sources = ["Mana", "Spirit energy", "Bloodline power", "Divine blessing", "Ancient knowledge"]
        rules = [
            "Requires years of study and practice",
            "Limited by physical and mental stamina",
            "Potentially dangerous if misused",
            "Subject to natural laws and balance",
            "Requires rare components or rituals"
        ]

        schools = [
            "Elemental_magic", "Illusion", "Healing",
            "Necromancy", "Divination", "Enchantment"
        ]

        magic = MagicSystem(
            name=f"{self._world_name} Magic System",
            source=random.choice(sources),
            rules=rules,
            limitations=[
                "Cannot raise the dead permanently",
                "Cannot read thoughts without consent",
                "Limited range and duration"
            ],
            schools=schools[:4],
            notable_practitioners=["Gandalf", "Merlin", "Yoda", "Saruman"]
        )
        self._magic_systems[magic.name] = magic

    def _build_historical_events(self) -> None:
        """构建历史事件"""
        events = [
            Historicalevent(
                name="The Great War",
                date="1000 years ago",
                description="A cataclysmic war that reshaped the world.",
                consequences=[
                    "Drew the current political map",
                    "Led to the rise and fall of empires",
                    "Created ancient ruins scattered across the land"
                ]
            ),
            Historicalevent(
                name="The Golden Age",
                date="500 years ago",
                description="A time of prosperity and cultural flourishing.",
                consequences=[
                    "Established major cities and institutions",
                    "Advances in magic and technology",
                    "Height of cultural exchange"
                ]
            ),
            Historicalevent(
                name="The Dark Century",
                date="200 years ago",
                description="A period of chaos and suffering.",
                consequences=[
                    "Many ancient traditions were lost",
                    "S societies were formed for protection",
                    "Lasting scars on the world"
                ]
            )
        ]
        self._historical_events.extend(events)

    def get_location(self, name: str) -> Optional[Location]:
        """获取地点"""
        return self._locations.get(name)

    def get_culture(self, name: str) -> Optional[Culture]:
        """获取文化"""
        return self._cultures.get(name)

    def get_faction(self, name: str) -> Optional[Faction]:
        """获取势力"""
        return self._factions.get(name)

    def get_magic_system(self, name: str) -> Optional[MagicSystem]:
        """获取魔法系统"""
        return self._magic_systems.get(name)

    def get_all_locations(self) -> Dict[str, Location]:
        """获取所有地点"""
        return self._locations

    def get_all_cultures(self) -> Dict[str, Culture]:
        """获取所有文化"""
        return self._cultures

    def get_all_factions(self) -> Dict[str, Faction]:
        """获取所有势力"""
        return self._factions

    def get_all_magic_systems(self) -> Dict[str, MagicSystem]:
        """获取所有魔法系统"""
        return self._magic_systems

    def get_historical_events(self) -> List[Historicalevent]:
        """获取历史事件"""
        return self._historical_events

    def get_world_summary(self) -> Dict[str, Any]:
        """获取世界概要"""
        return {
            "world_name": self._world_name,
            "genre": self._current_genre,
            "locations": len(self._locations),
            "cultures": len(self._cultures),
            "factions": len(self._factions),
            "magic_systems": len(self._magic_systems),
            "historical_events": len(self._historical_events)
        }

    def reset(self) -> None:
        """重置世界观构建器"""
        self._locations.clear()
        self._cultures.clear()
        self._factions.clear()
        self._magic_systems.clear()
        self._historical_events.clear()
        self._current_genre = "fantasy"
        self._world_name = "Unknown World"
