"""
ToolRegistry 与 @tool 装饰器单元测试
"""

import pytest

from deepnovel.agents.tools.tool_registry import (
    ToolNotFoundError,
    ToolParameter,
    ToolRegistry,
    ToolSchema,
    _infer_schema,
    _type_to_str,
    tool,
)


# ---- ToolParameter ----

class TestToolParameter:
    def test_to_dict_basic(self):
        p = ToolParameter(name="city", type="str", description="城市名")
        d = p.to_dict()
        assert d["name"] == "city"
        assert d["type"] == "str"
        assert d["required"] is True
        assert "default" not in d

    def test_to_dict_with_default(self):
        p = ToolParameter(name="top_k", type="int", default=5, required=False)
        d = p.to_dict()
        assert d["default"] == 5
        assert d["required"] is False


# ---- ToolSchema ----

class TestToolSchema:
    def test_to_dict(self):
        schema = ToolSchema(
            name="query_weather",
            description="查询天气",
            parameters=[
                ToolParameter(name="city", type="str", description="城市"),
            ],
        )
        d = schema.to_dict()
        assert d["name"] == "query_weather"
        assert len(d["parameters"]) == 1

    def test_format_for_prompt(self):
        schema = ToolSchema(
            name="search",
            description="搜索知识库",
            parameters=[
                ToolParameter(name="query", type="str", required=True),
                ToolParameter(name="top_k", type="int", default=5, required=False),
            ],
            examples=['search("天气")'],
        )
        text = schema.format_for_prompt()
        assert "search" in text
        assert "query" in text
        assert "(必填)" in text
        assert "(可选)" in text
        assert "默认: 5" in text
        assert 'search("天气")' in text


# ---- @tool decorator ----

class TestToolDecorator:
    def test_decorator_basic(self):
        class MyTool:
            @tool(description="查询天气")
            async def query_weather(self, city: str) -> dict:
                """查询指定城市的天气"""
                return {"city": city, "weather": "sunny"}

        t = MyTool()
        assert hasattr(t.query_weather, "_is_tool")
        assert t.query_weather._is_tool is True
        meta = t.query_weather._tool_meta
        assert meta["name"] == "query_weather"
        # description 参数优先于 docstring
        assert meta["description"] == "查询天气"

    def test_decorator_custom_name(self):
        class MyTool:
            @tool(name="get_temp", description="获取温度")
            async def fetch(self, city: str) -> dict:
                return {}

        t = MyTool()
        assert t.fetch._tool_meta["name"] == "get_temp"

    def test_schema_inference(self):
        class MyTool:
            @tool(description="测试工具")
            async def test_tool(
                self,
                required_param: str,
                optional_param: int = 10,
            ) -> dict:
                return {}

        t = MyTool()
        schema = t.test_tool._tool_meta["schema"]
        params = {p.name: p for p in schema.parameters}
        assert "required_param" in params
        assert params["required_param"].required is True
        assert "optional_param" in params
        assert params["optional_param"].required is False
        assert params["optional_param"].default == 10


# ---- ToolRegistry ----

class TestToolRegistry:
    @pytest.fixture
    def registry(self):
        return ToolRegistry()

    def test_register_and_get(self, registry):
        def my_func(x: int) -> int:
            return x * 2

        registry.register("double", my_func)
        assert registry.get("double") is my_func

    def test_register_with_schema(self, registry):
        schema = ToolSchema(name="test", description="测试")

        def my_func():
            pass

        registry.register("test", my_func, schema=schema)
        got = registry.get_schema("test")
        assert got.name == "test"

    def test_register_from_instance(self, registry):
        class MyTool:
            @tool(description="方法A")
            async def method_a(self, x: str) -> str:
                return x

            @tool(description="方法B")
            async def method_b(self, y: int) -> int:
                return y

            def not_a_tool(self):
                pass

        instance = MyTool()
        registry.register_from_instance(instance, prefix="my_")

        assert "my_method_a" in registry.list_tools()
        assert "my_method_b" in registry.list_tools()
        assert "my_not_a_tool" not in registry.list_tools()

    def test_unregister(self, registry):
        def f():
            pass

        registry.register("f", f)
        assert registry.unregister("f") is True
        assert registry.get("f") is None
        assert registry.unregister("f") is False

    def test_list_by_category(self, registry):
        def f1():
            pass

        def f2():
            pass

        registry.register("f1", f1, category="cat_a")
        registry.register("f2", f2, category="cat_b")

        assert registry.list_tools("cat_a") == ["f1"]
        assert registry.list_tools("cat_b") == ["f2"]
        assert set(registry.list_tools()) == {"f1", "f2"}

    def test_format_tools_for_prompt(self, registry):
        class Tool:
            @tool(description="搜索")
            async def search(self, query: str) -> dict:
                return {}

        registry.register_from_instance(Tool())
        text = registry.format_tools_for_prompt()
        assert "搜索" in text
        assert "query" in text

    @pytest.mark.asyncio
    async def test_call_async(self, registry):
        async def async_func(greeting: str) -> str:
            return f"hello {greeting}"

        registry.register("greet", async_func)
        result = await registry.call("greet", greeting="world")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_call_sync(self, registry):
        def sync_func(x: int, y: int) -> int:
            return x + y

        registry.register("add", sync_func)
        result = await registry.call("add", x=1, y=2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_call_not_found(self, registry):
        with pytest.raises(ToolNotFoundError):
            await registry.call("nonexistent")

    @pytest.mark.asyncio
    async def test_call_with_json(self, registry):
        def func(a: int, b: str) -> dict:
            return {"a": a, "b": b}

        registry.register("test", func)
        result = await registry.call_with_json("test", '{"a": 1, "b": "x"}')
        assert result == {"a": 1, "b": "x"}

    def test_to_dict(self, registry):
        class T:
            @tool(description="t")
            async def t(self) -> None:
                pass

        registry.register_from_instance(T())
        d = registry.to_dict()
        assert d["total"] == 1
        assert "t" in d["tools"]


# ---- helper functions ----

class TestHelpers:
    def test_type_to_str(self):
        assert _type_to_str(int) == "int"
        assert _type_to_str(str) == "str"
        assert _type_to_str(type(None)) == "NoneType"

    def test_infer_schema(self):
        def sample(a: int, b: str = "default") -> bool:
            """示例工具"""
            return True

        schema = _infer_schema(sample, "sample", "test")
        assert schema.name == "sample"
        assert schema.description == "示例工具"
        assert len(schema.parameters) == 2

        params = {p.name: p for p in schema.parameters}
        assert params["a"].type == "int"
        assert params["a"].required is True
        assert params["b"].type == "str"
        assert params["b"].required is False
        assert params["b"].default == "default"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
