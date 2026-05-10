"""
PromptComposer 单元测试
"""

import pytest

from deepnovel.agents.prompt_composer import PromptComposer, PromptTemplate, get_default_templates


class TestPromptTemplate:
    def test_render_simple(self):
        t = PromptTemplate(
            name="test",
            template="Hello, {{name}}!",
            variables=["name"],
        )
        result = t.render({"name": "World"})
        assert result == "Hello, World!"

    def test_render_missing_optional(self):
        t = PromptTemplate(
            name="test",
            template="Hello, {{name}}!",
            variables=["name"],
        )
        # 未提供变量时保留占位符
        result = t.render({})
        assert "{{name}}" in result

    def test_render_required_missing(self):
        t = PromptTemplate(
            name="test",
            template="Hello, {{name}}!",
            required_variables=["name"],
        )
        with pytest.raises(ValueError):
            t.render({})

    def test_render_none_value(self):
        t = PromptTemplate(name="test", template="Value: {{x}}")
        result = t.render({"x": None})
        assert "Value:" in result
        assert "None" not in result

    def test_render_list_value(self):
        t = PromptTemplate(name="test", template="Items: {{items}}")
        result = t.render({"items": ["a", "b", "c"]})
        assert result == "Items: a\nb\nc"

    def test_render_conditional_true(self):
        t = PromptTemplate(
            name="test",
            template="{% if show %}Secret{% endif %}",
        )
        result = t.render({"show": True})
        assert "Secret" in result

    def test_render_conditional_false(self):
        t = PromptTemplate(
            name="test",
            template="{% if show %}Secret{% endif %}",
        )
        result = t.render({"show": False})
        assert "Secret" not in result

    def test_render_loop(self):
        t = PromptTemplate(
            name="test",
            template="{% for item in items %}- {{item}}{% endfor %}",
        )
        result = t.render({"items": ["a", "b"]})
        assert "- a" in result
        assert "- b" in result

    def test_render_loop_with_dict_items(self):
        template = """{% for char in characters %}
Name: {{char.name}}
{% endfor %}"""
        t = PromptTemplate(name="test", template=template)
        result = t.render({"characters": [{"name": "Alice"}, {"name": "Bob"}]})
        assert "Name: Alice" in result
        assert "Name: Bob" in result

    def test_from_string_auto_variables(self):
        t = PromptTemplate.from_string("test", "Hello {{name}}, age {{age}}")
        assert "name" in t.variables
        assert "age" in t.variables


class TestPromptComposer:
    def test_register_and_compose(self):
        composer = PromptComposer()
        composer.register_template_from_string(
            "greeting", "Hello, {{name}}!"
        )
        result = composer.compose("greeting", {"name": "AI"})
        assert result == "Hello, AI!"

    def test_compose_unregistered(self):
        composer = PromptComposer()
        with pytest.raises(ValueError):
            composer.compose("nonexistent")

    def test_compose_system_prompt_basic(self):
        composer = PromptComposer()
        result = composer.compose_system_prompt(
            agent_role="助手",
            task_description="回答问题",
        )
        assert "# 角色定义" in result
        assert "助手" in result
        assert "# 任务" in result
        assert "回答问题" in result

    def test_compose_system_prompt_with_constraints(self):
        composer = PromptComposer()
        result = composer.compose_system_prompt(
            agent_role="助手",
            task_description="回答",
            constraints=["不要编造", "保持简洁"],
        )
        assert "# 约束条件" in result
        assert "不要编造" in result
        assert "保持简洁" in result

    def test_compose_system_prompt_with_tools(self):
        composer = PromptComposer()
        schemas = [
            {
                "name": "search",
                "description": "搜索",
                "parameters": [
                    {"name": "query", "type": "str", "required": True},
                ],
            }
        ]
        result = composer.compose_system_prompt(
            agent_role="助手",
            task_description="回答",
            tool_schemas=schemas,
        )
        assert "# 可用工具" in result
        assert "search" in result
        assert "query" in result

    def test_compose_system_prompt_with_working_memory(self):
        composer = PromptComposer()
        entries = [
            {"entry_type": "note", "content": "用户喜欢科幻"},
            {"entry_type": "goal", "content": "完成小说大纲"},
        ]
        result = composer.compose_system_prompt(
            agent_role="助手",
            task_description="写小说",
            working_memory=entries,
        )
        assert "# 当前工作记忆" in result
        assert "用户喜欢科幻" in result
        assert "完成小说大纲" in result

    def test_compose_system_prompt_with_rag(self):
        composer = PromptComposer()
        result = composer.compose_system_prompt(
            agent_role="助手",
            task_description="回答",
            rag_context="参考: 修仙世界有天道规则",
        )
        assert "# 相关知识" in result
        assert "修仙世界有天道规则" in result

    def test_compose_with_history(self):
        composer = PromptComposer()
        composer.register_template_from_string("base", "Prompt: {{task}}")
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        result = composer.compose_with_history("base", history, {"task": "写小说"})
        assert "Prompt: 写小说" in result
        assert "# 对话历史" in result
        assert "user" in result
        assert "assistant" in result

    def test_list_templates(self):
        composer = PromptComposer()
        composer.register_template_from_string("a", "A")
        composer.register_template_from_string("b", "B")
        assert set(composer.list_templates()) == {"a", "b"}

    def test_to_dict(self):
        composer = PromptComposer()
        composer.register_template_from_string("t", "T")
        d = composer.to_dict()
        assert "templates" in d
        assert "t" in d["templates"]


class TestDefaultTemplates:
    def test_novel_generation_template(self):
        templates = get_default_templates()
        assert "novel_generation" in templates
        t = templates["novel_generation"]
        assert "genre" in t.required_variables
        assert "task" in t.required_variables

    def test_character_decision_template(self):
        templates = get_default_templates()
        assert "character_decision" in templates
        t = templates["character_decision"]
        assert "character_name" in t.required_variables

    def test_world_state_query_template(self):
        templates = get_default_templates()
        assert "world_state_query" in templates
        t = templates["world_state_query"]
        assert "query_target" in t.required_variables

    def test_novel_generation_render(self):
        templates = get_default_templates()
        t = templates["novel_generation"]
        result = t.render(
            genre="修仙",
            task="写第一章",
            world_setting="天道规则完整",
        )
        assert "修仙" in result
        assert "写第一章" in result
        assert "天道规则完整" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
