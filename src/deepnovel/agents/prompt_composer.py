"""
PromptComposer — 模板引擎与动态 Prompt 组装

支持:
- 变量插值（Jinja2 风格）
- 工具 Schema 注入
- 工作记忆上下文注入
- 多级模板继承与组合
- 条件渲染与循环

@file: agents/prompt_composer.py
@date: 2026-04-29
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptTemplate:
    """Prompt 模板"""

    name: str
    template: str
    description: str = ""
    variables: List[str] = field(default_factory=list)
    required_variables: List[str] = field(default_factory=list)

    def render(self, variables: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """渲染模板

        Args:
            variables: 变量字典
            **kwargs: 额外变量

        Returns:
            渲染后的文本
        """
        ctx = dict(variables or {})
        ctx.update(kwargs)

        # 检查必填变量
        missing = [v for v in self.required_variables if v not in ctx]
        if missing:
            raise ValueError(f"模板 '{self.name}' 缺少必填变量: {missing}")

        result = self.template

        # 简单变量插值: {{variable}} 或 {{obj.attr}}
        def replace_var(match):
            var_expr = match.group(1).strip()
            parts = var_expr.split(".")
            value = ctx.get(parts[0], None)
            for part in parts[1:]:
                if value is None:
                    break
                if isinstance(value, dict):
                    value = value.get(part, None)
                elif hasattr(value, part):
                    value = getattr(value, part, None)
                else:
                    value = None
                    break
            if value is not None:
                if isinstance(value, list):
                    return "\n".join(str(v) for v in value)
                return str(value)
            # 未提供变量时保留占位符
            return match.group(0)

        result = re.sub(r"\{\{\s*([\w.]+)\s*\}\}", replace_var, result)

        # 条件渲染: {% if variable %}...{% endif %}
        result = self._render_conditionals(result, ctx)

        # 循环渲染: {% for item in items %}...{% endfor %}
        result = self._render_loops(result, ctx)

        return result

    def _render_conditionals(self, text: str, ctx: Dict[str, Any]) -> str:
        """渲染条件块"""
        pattern = r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}"

        def replace_cond(match):
            var_name = match.group(1)
            block = match.group(2)
            if ctx.get(var_name):
                return block
            return ""

        return re.sub(pattern, replace_cond, text, flags=re.DOTALL)

    def _render_loops(self, text: str, ctx: Dict[str, Any]) -> str:
        """渲染循环块，支持 {{item.attr}} 访问"""
        pattern = r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}"

        def _resolve_var(var_expr: str, context: Dict[str, Any]) -> Any:
            """解析变量表达式，支持点号访问如 item.name"""
            parts = var_expr.strip().split(".")
            value = context.get(parts[0], None)
            for part in parts[1:]:
                if value is None:
                    break
                if isinstance(value, dict):
                    value = value.get(part, None)
                elif hasattr(value, part):
                    value = getattr(value, part, None)
                else:
                    value = None
                    break
            return value

        def replace_loop(match):
            item_name = match.group(1)
            list_name = match.group(2)
            block = match.group(3)
            items = ctx.get(list_name, [])
            if not isinstance(items, list):
                return ""
            results = []
            for item in items:
                item_ctx = dict(ctx)
                item_ctx[item_name] = item
                rendered = re.sub(
                    r"\{\{\s*([\w.]+)\s*\}\}",
                    lambda m: str(
                        _resolve_var(m.group(1).strip(), item_ctx) or m.group(0)
                    ),
                    block,
                )
                results.append(rendered)
            return "\n".join(results)

        return re.sub(pattern, replace_loop, text, flags=re.DOTALL)

    @classmethod
    def from_string(cls, name: str, template: str, **metadata) -> "PromptTemplate":
        """从字符串创建模板"""
        # 自动提取变量（仅提取顶层变量名）
        var_pattern = r"\{\{\s*(\w+)(?:\.\w+)*\s*\}\}"
        variables = list(set(re.findall(var_pattern, template)))
        return cls(
            name=name,
            template=template,
            variables=variables,
            **metadata,
        )


class PromptComposer:
    """Prompt 组装器

    将多个模板组合成完整的 LLM Prompt，支持：
    - 系统提示组装
    - 工具 Schema 注入
    - 工作记忆上下文
    - 检索知识上下文
    """

    def __init__(self):
        self._templates: Dict[str, PromptTemplate] = {}
        self._system_defaults: Dict[str, str] = {}

    def register_template(self, template: PromptTemplate) -> "PromptComposer":
        """注册模板"""
        self._templates[template.name] = template
        return self

    def register_template_from_string(
        self,
        name: str,
        template: str,
        **metadata,
    ) -> "PromptComposer":
        """从字符串注册模板"""
        pt = PromptTemplate.from_string(name, template, **metadata)
        self._templates[name] = pt
        return self

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """获取模板"""
        return self._templates.get(name)

    def compose(
        self,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """组装 Prompt

        Args:
            template_name: 主模板名称
            variables: 变量字典
            **kwargs: 额外变量

        Returns:
            组装后的完整 Prompt
        """
        template = self._templates.get(template_name)
        if template is None:
            raise ValueError(f"模板 '{template_name}' 未注册")

        ctx = dict(variables or {})
        ctx.update(kwargs)
        return template.render(ctx)

    def compose_system_prompt(
        self,
        agent_role: str,
        task_description: str,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        working_memory: Optional[List[Dict[str, Any]]] = None,
        rag_context: Optional[str] = None,
        constraints: Optional[List[str]] = None,
    ) -> str:
        """组装系统 Prompt

        将角色定义、任务描述、工具说明、工作记忆和检索上下文
        组合成完整的系统提示。

        Args:
            agent_role: Agent 角色定义
            task_description: 任务描述
            tool_schemas: 工具 Schema 列表
            working_memory: 工作记忆条目
            rag_context: RAG 检索上下文
            constraints: 约束条件

        Returns:
            系统 Prompt 文本
        """
        parts = [
            f"# 角色定义\n{agent_role}",
            f"\n# 任务\n{task_description}",
        ]

        if constraints:
            parts.append(f"\n# 约束条件\n" + "\n".join(f"- {c}" for c in constraints))

        if tool_schemas:
            parts.append("\n# 可用工具\n")
            for schema in tool_schemas:
                parts.append(self._format_tool_schema(schema))

        if working_memory:
            parts.append("\n# 当前工作记忆\n")
            for entry in working_memory:
                parts.append(f"- [{entry.get('entry_type', 'note')}] {entry.get('content', '')}")

        if rag_context:
            parts.append(f"\n# 相关知识\n{rag_context}")

        parts.append(
            "\n# 输出格式\n"
            "请根据以上信息完成任务。如果需要调用工具，请使用以下格式:\n"
            "```tool\n"
            '{"tool": "工具名", "params": {...}}\n'
            "```"
        )

        return "\n".join(parts)

    def _format_tool_schema(self, schema: Dict[str, Any]) -> str:
        """格式化单个工具 Schema"""
        lines = [f"## {schema['name']}", f"{schema.get('description', '')}", ""]

        params = schema.get("parameters", [])
        if params:
            lines.append("参数:")
            for p in params:
                req = "(必填)" if p.get("required", True) else "(可选)"
                lines.append(f"  - {p['name']}: {p.get('type', 'Any')} {req}")
            lines.append("")

        return "\n".join(lines)

    def compose_with_history(
        self,
        template_name: str,
        history: List[Dict[str, str]],
        variables: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """组装带对话历史的 Prompt

        Args:
            template_name: 模板名称
            history: 对话历史 [{"role": "user", "content": "..."}, ...]
            variables: 变量
            **kwargs: 额外变量

        Returns:
            组装后的完整 Prompt
        """
        base = self.compose(template_name, variables, **kwargs)

        if history:
            history_text = "\n\n".join(
                f"**{h['role']}**: {h['content']}" for h in history
            )
            base += f"\n\n# 对话历史\n{history_text}"

        return base

    def list_templates(self) -> List[str]:
        """列出所有模板名称"""
        return list(self._templates.keys())

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "templates": {
                name: {
                    "name": t.name,
                    "description": t.description,
                    "variables": t.variables,
                    "required_variables": t.required_variables,
                }
                for name, t in self._templates.items()
            }
        }


# ---- 内置模板 ----

def get_default_templates() -> Dict[str, PromptTemplate]:
    """获取默认 Prompt 模板"""
    return {
        "novel_generation": PromptTemplate.from_string(
            name="novel_generation",
            template="""你是一位专业的网络小说作家，擅长创作{{genre}}类型的小说。

当前任务：{{task}}

{% if world_setting %}
# 世界观设定
{{world_setting}}
{% endif %}

{% if characters %}
# 角色设定
{% for char in characters %}
## {{char.name}}
{{char.description}}
{% endfor %}
{% endif %}

{% if outline %}
# 大纲
{{outline}}
{% endif %}

请根据以上信息，创作高质量的小说内容。注意保持人物性格一致，情节合理，文笔流畅。
""",
            description="小说生成主模板",
            required_variables=["genre", "task"],
        ),
        "character_decision": PromptTemplate.from_string(
            name="character_decision",
            template="""# 角色决策

角色：{{character_name}}
性格：{{personality}}
当前情感：{{emotion}}
当前目标：{{goals}}

# 情境
{{situation}}

# 可选行动
{% for action in actions %}
- {{action}}
{% endfor %}

请基于角色性格和当前状态，选择最合理的行动并说明理由。
输出格式：{"choice": "选择的行动", "reasoning": "决策理由", "confidence": 0.8}
""",
            description="角色决策模板",
            required_variables=["character_name", "situation", "actions"],
        ),
        "world_state_query": PromptTemplate.from_string(
            name="world_state_query",
            template="""# 世界状态查询

查询目标：{{query_target}}
查询类型：{{query_type}}

{% if context %}
# 上下文
{{context}}
{% endif %}

请基于当前世界状态，回答查询问题。
""",
            description="世界状态查询模板",
            required_variables=["query_target"],
        ),
    }
