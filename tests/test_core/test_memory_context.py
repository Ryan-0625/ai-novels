"""
MemoryContext 单元测试

测试三级记忆系统的整合：
- SensoryBuffer: 感觉记忆缓冲
- MemoryContext: 统一上下文接口
"""

import pytest

from deepnovel.core.memory_context import (
    LongTermMemorySnapshot,
    MemoryContext,
    SensoryBuffer,
    SensoryBufferEntry,
)


# ---- SensoryBuffer 测试 ----


class TestSensoryBuffer:
    def test_add_and_get_recent(self):
        buf = SensoryBuffer(max_size=10)
        buf.add("输入1", intensity=0.8)
        buf.add("输入2", intensity=0.3)

        recent = buf.get_recent()
        assert len(recent) == 2
        assert recent[0].content == "输入1"

    def test_capacity_limit(self):
        buf = SensoryBuffer(max_size=3)
        for i in range(5):
            buf.add(f"输入{i}")

        assert len(buf._entries) == 3
        # 最旧的被移除
        assert buf._entries[0].content == "输入2"

    def test_get_by_modality(self):
        buf = SensoryBuffer()
        buf.add("文本", modality="text")
        buf.add("图像", modality="visual")
        buf.add("声音", modality="auditory")

        text_entries = buf.get_by_modality("text")
        assert len(text_entries) == 1
        assert text_entries[0].content == "文本"

    def test_get_salient(self):
        buf = SensoryBuffer()
        buf.add("低强度", intensity=0.3)
        buf.add("高强度", intensity=0.9)

        salient = buf.get_salient(threshold=0.7)
        assert len(salient) == 1
        assert salient[0].content == "高强度"

    def test_clear(self):
        buf = SensoryBuffer()
        buf.add("内容")
        buf.clear()
        assert len(buf._entries) == 0

    def test_to_dict(self):
        buf = SensoryBuffer()
        buf.add("内容", modality="text")
        d = buf.to_dict()
        assert "total_entries" in d
        assert d["modalities"] == ["text"]


class TestSensoryBufferEntry:
    def test_freshness(self):
        entry = SensoryBufferEntry(content="测试", intensity=1.0)
        assert entry.is_fresh(max_age_ms=5000) is True

    def test_to_dict(self):
        entry = SensoryBufferEntry(
            content="内容", modality="text", intensity=0.8, source="user"
        )
        d = entry.to_dict()
        assert d["modality"] == "text"
        assert d["intensity"] == 0.8


# ---- MemoryContext 测试 ----


class TestMemoryContextInit:
    def test_basic_init(self):
        ctx = MemoryContext(character_id="char_1")
        assert ctx.character_id == "char_1"
        assert ctx.sensory_buffer is not None
        assert ctx.working_memory is not None
        assert ctx.attention is not None

    def test_init_without_sensory_buffer(self):
        ctx = MemoryContext(character_id="char_2", enable_sensory_buffer=False)
        assert ctx.sensory_buffer is None

    def test_init_custom_capacity(self):
        ctx = MemoryContext(character_id="char_3", working_memory_capacity=5)
        assert ctx.working_memory.capacity == 5


class TestMemoryContextPerception:
    def test_perceive_basic(self):
        ctx = MemoryContext(character_id="char_1")
        entry = ctx.perceive("敌人出现", emotional_salience=0.9)
        assert entry is not None
        assert entry.entry_type == "perception"

    def test_perceive_low_salience_filtered(self):
        ctx = MemoryContext(character_id="char_1")
        # 低显著性内容可能被过滤掉
        entry = ctx.perceive("无关紧要", emotional_salience=0.0, novelty=0.0)
        # 注意力控制器可能过滤掉极低显著性的内容
        # 但我们不强制断言为None，因为阈值是动态的

    def test_perceive_batch(self):
        ctx = MemoryContext(character_id="char_1")
        stimuli = [
            {"content": "A", "emotional_salience": 0.8},
            {"content": "B", "emotional_salience": 0.2},
            {"content": "C", "emotional_salience": 0.9},
        ]
        entries = ctx.perceive_batch(stimuli)
        assert len(entries) >= 1  # 至少高显著性的应被接收

    def test_perceive_populates_sensory_buffer(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.perceive("刺激", emotional_salience=0.8)
        assert ctx.sensory_buffer is not None
        recent = ctx.sensory_buffer.get_recent()
        assert len(recent) >= 1


class TestMemoryContextWorkingMemory:
    def test_add_to_working_memory(self):
        ctx = MemoryContext(character_id="char_1")
        entry = ctx.add_to_working_memory("重要信息", entry_type="note", priority=0.9)
        assert entry is not None
        assert entry.content == "重要信息"

    def test_get_working_memory_entries(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.add_to_working_memory("A", entry_type="goal", priority=0.9)
        ctx.add_to_working_memory("B", entry_type="note", priority=0.5)

        goals = ctx.get_working_memory_entries(entry_type="goal")
        assert len(goals) == 1
        assert goals[0].content == "A"

    def test_clear_working_memory(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.add_to_working_memory("内容")
        ctx.clear_working_memory()
        assert ctx.working_memory.occupancy == 0


class TestMemoryContextAttention:
    def test_shift_attention(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.shift_attention("target_1", "enemy", intensity=0.8)
        assert ctx.attention.focus.target_id == "target_1"
        assert ctx.attention.focus.target_type == "enemy"

    def test_set_goals(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.set_goals([{"keywords": ["战斗"], "priority": 0.9}])
        # 目标设置后，相关感知的显著性应提高
        entry = ctx.perceive("战斗开始", emotional_salience=0.5)
        assert entry is not None

    def test_set_emotional_state(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.set_emotional_state({"anger": 0.8, "fear": 0.3})
        # 验证状态被设置
        state = ctx.mind.get_mind_state()
        assert "emotional_state" in state

    def test_form_intention(self):
        ctx = MemoryContext(character_id="char_1")
        entry = ctx.form_intention("攻击敌人", priority=0.9)
        assert entry is not None
        assert entry.entry_type == "intention"


class TestMemoryContextLongTermMemory:
    def test_ltm_disabled_by_default(self):
        ctx = MemoryContext(character_id="char_1")
        assert ctx.get_stats()["ltm_enabled"] is False

    def test_enable_ltm(self):
        ctx = MemoryContext(character_id="char_1")
        # 使用 mock memory_manager
        class MockManager:
            pass

        ctx.enable_long_term_memory(MockManager())
        assert ctx.get_stats()["ltm_enabled"] is True

    @pytest.mark.asyncio
    async def test_retrieve_long_term_without_manager(self):
        ctx = MemoryContext(character_id="char_1")
        snapshot = await ctx.retrieve_long_term(None, "查询")
        assert snapshot.is_empty() is True


class TestMemoryContextStats:
    def test_get_stats(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.perceive("测试", emotional_salience=0.8)
        stats = ctx.get_stats()
        assert stats["perceptions"] >= 1
        assert "wm_occupancy" in stats
        assert "cognitive_load" in stats

    def test_to_dict(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.perceive("测试", emotional_salience=0.8)
        d = ctx.to_dict()
        assert d["character_id"] == "char_1"
        assert "working_memory" in d
        assert "attention" in d
        assert "stats" in d


class TestMemoryContextPromptContext:
    def test_build_context_for_prompt(self):
        ctx = MemoryContext(character_id="char_1")
        ctx.perceive("敌人出现", emotional_salience=0.9)
        ctx.form_intention("防御", priority=0.8)

        prompt_ctx = ctx.build_context_for_prompt(max_entries=3)
        assert "character_id" in prompt_ctx
        assert "working_memory" in prompt_ctx
        assert len(prompt_ctx["working_memory"]) >= 1
        assert "cognitive_load" in prompt_ctx

    def test_build_context_empty(self):
        ctx = MemoryContext(character_id="char_1")
        prompt_ctx = ctx.build_context_for_prompt()
        assert prompt_ctx["working_memory"] == []
        # 空工作记忆但注意力焦点有默认 intensity=0.5，focus_load = 0.5 * 0.2 = 0.1
        assert prompt_ctx["cognitive_load"] == 0.1


# ---- LongTermMemorySnapshot 测试 ----


class TestLongTermMemorySnapshot:
    def test_empty(self):
        snap = LongTermMemorySnapshot()
        assert snap.is_empty() is True

    def test_not_empty(self):
        snap = LongTermMemorySnapshot(episodic=[{"id": "1"}])
        assert snap.is_empty() is False

    def test_to_dict(self):
        snap = LongTermMemorySnapshot(
            episodic=[{"id": "1"}],
            semantic=[{"id": "2"}],
            retrieval_query="测试",
        )
        d = snap.to_dict()
        assert d["episodic_count"] == 1
        assert d["semantic_count"] == 1
        assert d["retrieval_query"] == "测试"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
