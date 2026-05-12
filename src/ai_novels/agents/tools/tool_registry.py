"""
工具注册表与 @tool 装饰器

为 Agent 提供统一的工具发现、注册和调用接口。

@file: agents/tools/tool_registry.py
@date: 2026-04-29
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class ToolParameter:
    """工具参数描述"""

    name: str
    type: str
    description: str = ""
    required: bool = True
    default: Any = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "required": self.required,
        }
        if self.default is not None:
            d["default"] = self.default
        return d


@dataclass
class ToolSchema:
    """工具 Schema — 描述工具的元数据"""

    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    returns: str = "Any"
    category: str = "general"
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [p.to_dict() for p in self.parameters],
            "returns": self.returns,
            "category": self.category,
            "examples": self.examples,
        }

    def format_for_prompt(self) -> str:
        """格式化为 LLM Prompt 中的工具描述"""
        lines = [f"### {self.name}", f"{self.description}", ""]
        if self.parameters:
            lines.append("参数:")
            for p in self.parameters:
                req = "(必填)" if p.required else "(可选)"
                default = f", 默认: {p.default}" if p.default is not None else ""
                lines.append(f"  - {p.name}: {p.type} {req}{default} — {p.description}")
            lines.append("")
        if self.examples:
            lines.append("示例:")
            for ex in self.examples:
                lines.append(f"  {ex}")
            lines.append("")
        return "\n".join(lines)


class ToolRegistry:
    """工具注册表 — 统一管理所有 Agent 可用工具"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, ToolSchema] = {}
        self._instances: Dict[str, Any] = {}  # 工具实例（用于绑定方法）
        self._categories: Dict[str, List[str]] = {}  # category -> tool_names

    # ---- 注册 ----

    def register(
        self,
        name: str,
        func: Callable,
        schema: Optional[ToolSchema] = None,
        instance: Optional[Any] = None,
        category: str = "general",
    ) -> "ToolRegistry":
        """注册工具

        Args:
            name: 工具名称
            func: 工具函数/方法
            schema: 工具 schema（可选，自动推断）
            instance: 绑定的实例（用于方法调用）
            category: 工具类别
        """
        self._tools[name] = func
        self._instances[name] = instance

        if schema is None:
            schema = _infer_schema(func, name, category)
        schema.category = category
        self._schemas[name] = schema

        # 按类别索引
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)

        return self

    def register_from_instance(
        self,
        instance: Any,
        prefix: str = "",
        category: str = "general",
    ) -> "ToolRegistry":
        """从实例中注册所有带有 @tool 标记的方法

        Args:
            instance: 工具类实例
            prefix: 工具名前缀
            category: 工具类别
        """
        cls = instance.__class__
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name, None)
            if attr is None or not callable(attr):
                continue
            tool_meta = getattr(attr, "_tool_meta", None)
            if tool_meta is None:
                continue

            tool_name = prefix + tool_meta.get("name", attr_name)
            bound_method = getattr(instance, attr_name)
            schema = tool_meta.get("schema")
            self.register(tool_name, bound_method, schema=schema, instance=instance, category=category)

        return self

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name not in self._tools:
            return False
        del self._tools[name]
        del self._schemas[name]
        if name in self._instances:
            del self._instances[name]
        for cat_tools in self._categories.values():
            if name in cat_tools:
                cat_tools.remove(name)
        return True

    # ---- 查询 ----

    def get(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[ToolSchema]:
        """获取工具 schema"""
        return self._schemas.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """列出所有工具名"""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())

    def list_categories(self) -> List[str]:
        """列出所有类别"""
        return list(self._categories.keys())

    def list_schemas(self, category: Optional[str] = None) -> List[ToolSchema]:
        """列出所有工具 schema"""
        names = self.list_tools(category)
        return [self._schemas[n] for n in names if n in self._schemas]

    def format_tools_for_prompt(self, category: Optional[str] = None) -> str:
        """将所有工具格式化为 LLM Prompt"""
        schemas = self.list_schemas(category)
        if not schemas:
            return ""
        parts = ["## 可用工具", ""]
        for s in schemas:
            parts.append(s.format_for_prompt())
        return "\n".join(parts)

    # ---- 调用 ----

    async def call(self, name: str, **kwargs) -> Any:
        """调用工具

        Args:
            name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        func = self._tools.get(name)
        if func is None:
            raise ToolNotFoundError(f"工具 '{name}' 未注册")

        # 检查是否是协程函数
        if asyncio.iscoroutinefunction(func):
            return await func(**kwargs)
        else:
            return func(**kwargs)

    async def call_with_json(self, name: str, params_json: str) -> Any:
        """从 JSON 字符串调用工具"""
        import json

        params = json.loads(params_json)
        return await self.call(name, **params)

    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "tools": {n: s.to_dict() for n, s in self._schemas.items()},
            "categories": self._categories,
            "total": len(self._tools),
        }


class ToolNotFoundError(Exception):
    """工具未找到异常"""
    pass


# ---- @tool 装饰器 ----


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    examples: Optional[List[str]] = None,
    returns: str = "Any",
):
    """@tool 装饰器 — 标记方法为 Agent 可调用的工具

    Usage:
        class MyTool:
            @tool(description="查询天气")
            async def query_weather(self, city: str) -> Dict:
                ...
    """

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip().split("\n")[0]
        tool_examples = examples or []

        # 从函数签名推断参数
        sig = inspect.signature(func)
        params = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            param_type = _type_to_str(param.annotation)
            default = param.default if param.default is not inspect.Parameter.empty else None
            required = param.default is inspect.Parameter.empty
            params.append(
                ToolParameter(
                    name=param_name,
                    type=param_type,
                    required=required,
                    default=default,
                )
            )

        schema = ToolSchema(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            returns=returns,
            category=category,
            examples=tool_examples,
        )

        # 附加元数据到函数
        func._tool_meta = {
            "name": tool_name,
            "description": tool_desc,
            "schema": schema,
            "category": category,
        }
        func._is_tool = True

        return func

    return decorator


# ---- 辅助函数 ----


def _type_to_str(annotation: Any) -> str:
    """将类型注解转换为字符串"""
    if annotation is inspect.Parameter.empty:
        return "Any"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


def _infer_schema(func: Callable, name: str, category: str) -> ToolSchema:
    """从函数签名推断 ToolSchema"""
    sig = inspect.signature(func)
    params = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        param_type = _type_to_str(param.annotation)
        default = param.default if param.default is not inspect.Parameter.empty else None
        required = param.default is inspect.Parameter.empty
        params.append(
            ToolParameter(
                name=param_name,
                type=param_type,
                required=required,
                default=default,
            )
        )

    return ToolSchema(
        name=name,
        description=(func.__doc__ or "").strip().split("\n")[0],
        parameters=params,
        category=category,
    )


# ---- 全局注册表 ----

_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> ToolRegistry:
    """重置全局工具注册表"""
    global _global_registry
    _global_registry = ToolRegistry()
    return _global_registry
