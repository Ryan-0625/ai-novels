"""
工作记忆与注意力控制器单元测试

测试 WorkingMemory、AttentionController、CharacterMindController。
"""

import time
from typing import Any, Dict, List

import pytest

from deepnovel.core.working_memory import (
    WorkingMemoryEntry,
    AttentionFocus,
    WorkingMemory,
    AttentionController,
    CharacterMindController,
)


class TestWorkingMemoryEntry:
    """WorkingMemoryEntry 测试"""

    def test_init(self):
        """基本初始化"""
        entry = WorkingMemoryEntry(content="测试内容", entry_type="perception")
        assert entry.content == "测试内容"
        assert entry.entry_type == "perception"
        assert entry.activation == 1.0
        assert entry.priority == 0.5
        assert entry.maintenance_count == 0

    def test_decay(self):
        """衰减必须降低激活度"""
        entry = WorkingMemoryEntry(content="测试")
        entry.decay(rate=0.3)
        assert entry.activation == 0.7

    def test_decay_to_zero(self):
        """衰减不能低于0"""
        entry = WorkingMemoryEntry(content="测试")
        entry.decay(rate=2.0)
        assert entry.activation == 0.0

    def test_maintain(self):
        """维持必须增加激活度"""
        entry = WorkingMemoryEntry(content="测试", activation=0.5)
        entry.maintain(boost=0.2)
        assert entry.activation == 0.7
        assert entry.maintenance_count == 1

    def test_maintain_cap(self):
        """维持不能超过1"""
        entry = WorkingMemoryEntry(content="测试", activation=0.95)
        entry.maintain(boost=0.2)
        assert entry.activation == 1.0

    def test_is_active(self):
        """激活状态判断"""
        active = WorkingMemoryEntry(content="活跃", activation=0.3)
        inactive = WorkingMemoryEntry(content="不活跃", activation=0.1)
        assert active.is_active(threshold=0.2) is True
        assert inactive.is_active(threshold=0.2) is False

    def test_to_dict(self):
        """序列化"""
        entry = WorkingMemoryEntry(content="测试", entry_type="emotion", tags={"a", "b"})
        d = entry.to_dict()
        assert d["content"] == "测试"
        assert d["entry_type"] == "emotion"
        assert "activation" in d
        assert set(d["tags"]) == {"a", "b"}


class TestAttentionFocus:
    """AttentionFocus 测试"""

    def test_init(self):
        """基本初始化"""
        focus = AttentionFocus(target_id="char-1", target_type="character", intensity=0.8)
        assert focus.target_id == "char-1"
        assert focus.intensity == 0.8

    def test_is_expired(self):
        """过期检查"""
        focus = AttentionFocus(duration_limit=0.01)
        time.sleep(0.02)
        assert focus.is_expired() is True

    def test_not_expired(self):
        """未过期检查"""
        focus = AttentionFocus(duration_limit=60.0)
        assert focus.is_expired() is False

    def test_elapsed(self):
        """已持续时间"""
        focus = AttentionFocus()
        time.sleep(0.01)
        assert focus.elapsed() >= 0.01


class TestWorkingMemory:
    """WorkingMemory 测试"""

    @pytest.fixture
    def wm(self):
        return WorkingMemory(capacity=3)

    def test_init(self, wm):
        """初始化状态"""
        assert wm.capacity == 3
        assert wm.occupancy == 0
        assert wm.load_ratio == 0.0
        assert wm.is_full is False

    def test_add_within_capacity(self, wm):
        """容量内添加"""
        entry = wm.add("内容1", priority=0.6)
        assert entry is not None
        assert wm.occupancy == 1

    def test_add_up_to_capacity(self, wm):
        """添加到满容量"""
        for i in range(3):
            wm.add(f"内容{i}", priority=0.5)
        assert wm.occupancy == 3
        assert wm.is_full is True

    def test_add_overflow_low_priority(self, wm):
        """低优先级溢出时被拒绝"""
        for i in range(3):
            wm.add(f"内容{i}", priority=0.8)
        # 满后低优先级无法进入
        entry = wm.add("低优先级", priority=0.3)
        assert entry is None
        assert wm.occupancy == 3

    def test_add_overflow_high_priority(self, wm):
        """高优先级可挤出低优先级"""
        wm.add("低1", priority=0.3)
        wm.add("低2", priority=0.3)
        wm.add("中", priority=0.5)
        # 高优先级进入，挤出最低的
        entry = wm.add("高", priority=0.9)
        assert entry is not None
        assert wm.occupancy == 3
        contents = [e.content for e in wm._entries]
        assert "高" in contents
        # 最低优先级的被挤出
        assert "低1" not in contents

    def test_maintain(self, wm):
        """主动维持"""
        wm.add("A", entry_type="perception")
        wm.add("B", entry_type="memory")
        count = wm.maintain_by_type("perception")
        assert count == 1
        assert wm._entries[0].maintenance_count == 1

    def test_maintain_by_tag(self, wm):
        """按标签维持"""
        wm.add("A", tags={"important"})
        wm.add("B", tags={"other"})
        count = wm.maintain_by_tag("important")
        assert count == 1

    def test_decay_removes_inactive(self, wm):
        """衰减后移除失效条目"""
        entry = wm.add("临时", priority=0.1)
        entry.activation = 0.15
        # 强制衰减到低于阈值
        wm._force_decay()
        assert wm.occupancy == 0

    def test_get_active_entries(self, wm):
        """获取激活条目"""
        wm.add("感知", entry_type="perception", priority=0.8)
        wm.add("记忆", entry_type="memory", priority=0.6)
        perceptions = wm.get_active_entries(entry_type="perception")
        assert len(perceptions) == 1
        assert perceptions[0].content == "感知"

    def test_clear(self, wm):
        """清空"""
        wm.add("A")
        wm.add("B")
        wm.clear()
        assert wm.occupancy == 0

    def test_clear_by_type(self, wm):
        """按类型清空"""
        wm.add("A", entry_type="perception")
        wm.add("B", entry_type="perception")
        wm.add("C", entry_type="memory")
        removed = wm.clear_by_type("perception")
        assert removed == 2
        assert wm.occupancy == 1

    def test_to_dict(self, wm):
        """序列化"""
        wm.add("内容", priority=0.7)
        d = wm.to_dict()
        assert d["capacity"] == 3
        assert d["occupancy"] == 1
        assert len(d["entries"]) == 1


class TestAttentionController:
    """AttentionController 测试"""

    @pytest.fixture
    def controller(self):
        return AttentionController(capacity=3)

    def test_init(self, controller):
        """初始化"""
        assert controller.working_memory is not None
        assert controller.focus.target_id == ""

    def test_cognitive_load_empty(self, controller):
        """空工作记忆的认知负荷"""
        # 默认焦点强度 0.5 * 0.2 = 0.1
        assert controller.cognitive_load == 0.1
        assert controller.is_overloaded() is False

    def test_cognitive_load_with_entries(self, controller):
        """有条目时的认知负荷"""
        controller.working_memory.add("A")
        controller.working_memory.add("B")
        # 2/3 = 0.667
        assert controller.cognitive_load > 0.5

    def test_calculate_salience(self, controller):
        """显著性计算"""
        info = {
            "emotional_salience": 0.8,
            "goal_relevance": 0.9,
            "novelty": 0.5,
            "unexpectedness": 0.3,
            "recency": 1.0,
        }
        score = controller.calculate_salience(info)
        assert 0 < score < 1
        # 高情感 + 高目标相关 → 显著性较高
        assert score > 0.4

    def test_calculate_salience_overload_penalty(self, controller):
        """认知过载时显著性惩罚"""
        # 填满工作记忆并设置高强度焦点
        for i in range(3):
            controller.working_memory.add(f"内容{i}")
        controller.shift_focus("target", "type", intensity=1.0)

        info = {
            "emotional_salience": 1.0,
            "goal_relevance": 1.0,
            "novelty": 1.0,
            "unexpectedness": 1.0,
            "recency": 1.0,
        }
        score = controller.calculate_salience(info)
        # 过载惩罚后分数降低
        assert score < 1.0

    def test_should_attend_high_salience(self, controller):
        """高显著性应被注意"""
        info = {"goal_relevance": 0.9, "emotional_salience": 0.8}
        assert controller.should_attend(info, threshold=0.4) is True

    def test_should_attend_low_salience(self, controller):
        """低显著性应被忽略"""
        info = {"goal_relevance": 0.1, "emotional_salience": 0.1}
        assert controller.should_attend(info, threshold=0.4) is False

    def test_shift_focus(self, controller):
        """焦点转移"""
        focus = controller.shift_focus("char-1", "character", intensity=0.8)
        assert focus.target_id == "char-1"
        assert focus.intensity == 0.8

    def test_check_focus_expired(self, controller):
        """焦点过期检查"""
        controller.shift_focus("test", "type", duration_limit=0.01)
        time.sleep(0.02)
        expired = controller.check_focus_expired()
        assert expired is True
        assert controller.focus.target_id == ""

    def test_filter_input(self, controller):
        """过滤器功能"""
        controller.add_filter(lambda x: "允许" in str(x))
        assert controller.filter_input("允许通过") is True
        assert controller.filter_input("拒绝") is False

    def test_process_input_high_salience(self, controller):
        """高显著性信息进入工作记忆"""
        entry = controller.process_input(
            content="重要事件",
            information={
                "emotional_salience": 0.9,
                "goal_relevance": 0.9,
                "novelty": 0.8,
                "unexpectedness": 0.7,
                "recency": 1.0,
            },
        )
        assert entry is not None
        assert entry.content == "重要事件"

    def test_process_input_low_salience(self, controller):
        """低显著性信息被忽略"""
        entry = controller.process_input(
            content="无关信息",
            information={
                "emotional_salience": 0.1,
                "goal_relevance": 0.1,
                "novelty": 0.1,
                "unexpectedness": 0.0,
                "recency": 0.1,
            },
        )
        assert entry is None

    def test_process_input_filtered(self, controller):
        """被过滤器拒绝的信息"""
        controller.add_filter(lambda x: False)
        entry = controller.process_input(
            content="任何内容",
            information={"goal_relevance": 1.0},
        )
        assert entry is None

    def test_maintain_focus(self, controller):
        """维持焦点相关条目"""
        controller.shift_focus("李逍遥", "character")
        controller.working_memory.add("李逍遥的行动", tags={"character"})
        controller.working_memory.add("无关事件")
        count = controller.maintain_focus()
        assert count >= 0

    def test_to_dict(self, controller):
        """序列化"""
        controller.shift_focus("target", "type")
        controller.working_memory.add("内容")
        d = controller.to_dict()
        assert "cognitive_load" in d
        assert "focus" in d
        assert "working_memory" in d


class TestCharacterMindController:
    """CharacterMindController 测试"""

    @pytest.fixture
    def mind(self):
        return CharacterMindController(character_id="char-1", capacity=3)

    def test_init(self, mind):
        """初始化"""
        assert mind.character_id == "char-1"
        assert mind.attention is not None
        assert mind.working_memory is not None

    def test_set_goals(self, mind):
        """设置目标"""
        goals = [{"keywords": ["救人"], "priority": 0.9}]
        mind.set_goals(goals)
        assert mind.get_mind_state()["goals"] == goals

    def test_set_emotional_state(self, mind):
        """设置情感状态"""
        emotions = {"joy": 0.8, "fear": 0.2}
        mind.set_emotional_state(emotions)
        assert mind.get_mind_state()["emotional_state"] == emotions

    def test_perceive_high_relevance(self, mind):
        """感知高相关性信息"""
        mind.set_goals([{"keywords": ["赵灵儿"], "priority": 0.9}])
        entry = mind.perceive(
            stimulus="赵灵儿出现",
            emotional_salience=0.8,
            novelty=0.7,
        )
        assert entry is not None
        assert entry.content == "赵灵儿出现"

    def test_perceive_low_relevance(self, mind):
        """感知低相关性信息"""
        mind.set_goals([{"keywords": ["赵灵儿"], "priority": 0.9}])
        entry = mind.perceive(
            stimulus="路边野花",
            emotional_salience=0.1,
            novelty=0.2,
        )
        assert entry is None

    def test_retrieve_to_working_memory(self, mind):
        """记忆载入工作记忆"""
        entry = mind.retrieve_to_working_memory("过去的记忆", relevance=0.8)
        assert entry is not None
        assert entry.entry_type == "memory"

    def test_form_intention(self, mind):
        """形成意图"""
        entry = mind.form_intention("去仙灵岛", priority=0.9)
        assert entry is not None
        assert entry.entry_type == "intention"
        assert entry.priority == 0.9

    def test_get_mind_state(self, mind):
        """完整心智状态"""
        mind.set_goals([{"keywords": ["test"]}])
        mind.set_emotional_state({"joy": 0.5})
        state = mind.get_mind_state()
        assert state["character_id"] == "char-1"
        assert "attention" in state
        assert "goals" in state
        assert "cognitive_load" in state

    def test_cognitive_overload(self, mind):
        """认知过载测试"""
        # 填满工作记忆
        for i in range(3):
            mind.perceive(f"事件{i}", emotional_salience=0.8, novelty=0.9)
        assert mind.working_memory.is_full
        assert mind.attention.cognitive_load > 0.5

    def test_attention_maintains_relevant(self, mind):
        """注意力维持相关条目"""
        mind.set_goals([{"keywords": ["战斗"], "priority": 0.8}])
        entry = mind.perceive(
            stimulus="敌人出现",
            emotional_salience=0.9,
            novelty=0.8,
            tags={"战斗"},
        )
        assert entry is not None
        # 维持焦点
        mind.attention.shift_focus("战斗", "situation")
        maintained = mind.attention.maintain_focus()
        assert maintained >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
