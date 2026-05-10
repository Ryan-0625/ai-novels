"""
ToolEnabledAgent — 工具增强型 Agent

集成:
- ToolRegistry: 工具发现与调用
- TierRouter: 按任务复杂度路由模型
- WorkingMemory/AttentionController: 上下文管理
- RAGEngine: 知识检索增强
- PromptComposer: 动态 Prompt 组装
- EventBus: 事件发布

@file: agents/tool_enabled_agent.py
@date: 2026-04-29
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from deepnovel.agents.base import AgentConfig, AgentState, BaseAgent, Message, MessageType
from deepnovel.agents.prompt_composer import PromptComposer
from deepnovel.agents.tools.tool_registry import (
    ToolNotFoundError,
    ToolRegistry,
    get_tool_registry,
)
from deepnovel.core.event_bus import EventBus, EventPriority, EventType
from deepnovel.core.memory_context import MemoryContext
from deepnovel.core.working_memory import AttentionController, WorkingMemory
from deepnovel.llm.tier import ModelTier, TierConfig, TierRouter
from deepnovel.rag.rag_engine import RAGEngine
from deepnovel.utils.logger import get_logger

_logger = get_logger()


@dataclass
class ToolEnabledAgentConfig(AgentConfig):
    """工具增强型 Agent 配置"""

    # Tier 路由
    tier_router: Optional[TierRouter] = None
    default_tier: ModelTier = ModelTier.STANDARD

    # RAG
    rag_engine: Optional[RAGEngine] = None
    enable_rag: bool = True
    rag_top_k: int = 5
    rag_max_tokens: int = 2000

    # Working Memory
    working_memory_capacity: int = 7
    enable_working_memory: bool = True

    # 系统提示组件
    agent_role: str = ""
    task_description: str = ""
    constraints: List[str] = field(default_factory=list)

    # 事件
    event_bus: Optional[EventBus] = None
    enable_events: bool = True


class ToolEnabledAgent(BaseAgent):
    """工具增强型 Agent

    在 BaseAgent 基础上增加:
    1. 工具注册与调用 (ToolRegistry)
    2. 智能模型路由 (TierRouter)
    3. 工作记忆管理 (WorkingMemory + AttentionController)
    4. RAG 知识检索 (RAGEngine)
    5. 动态 Prompt 组装 (PromptComposer)
    6. 事件驱动 (EventBus)
    """

    def __init__(self, config: ToolEnabledAgentConfig):
        super().__init__(config)
        self._tool_config = config

        # ---- 工具注册表 ----
        self._tool_registry: ToolRegistry = get_tool_registry()

        # ---- Tier 路由 ----
        self._tier_router = config.tier_router or TierRouter()
        self._default_tier = config.default_tier

        # ---- 记忆上下文（三级记忆） ----
        self._memory_context = MemoryContext(
            character_id=f"agent_{self._name}",
            working_memory_capacity=config.working_memory_capacity,
        )
        # 向后兼容：直接暴露工作记忆和注意力
        self._attention = self._memory_context.attention
        self._working_memory = self._memory_context.working_memory

        # ---- RAG ----
        self._rag_engine = config.rag_engine
        self._enable_rag = config.enable_rag and self._rag_engine is not None

        # ---- Prompt 组装器 ----
        self._composer = PromptComposer()
        self._load_default_templates()

        # ---- 事件总线 ----
        self._event_bus = config.event_bus
        self._enable_events = config.enable_events and self._event_bus is not None

        # ---- 统计 ----
        self._stats = {
            "tool_calls": 0,
            "llm_calls": 0,
            "rag_queries": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "errors": 0,
        }

    def _load_default_templates(self) -> None:
        """加载默认模板到 composer"""
        defaults = self._composer.__class__.__dict__.get("get_default_templates")
        if defaults is None:
            from deepnovel.agents.prompt_composer import get_default_templates

            defaults = get_default_templates
        for name, template in defaults().items():
            self._composer.register_template(template)

    # ---- 工具管理 ----

    def register_tool_instance(
        self,
        instance: Any,
        prefix: str = "",
        category: str = "general",
    ) -> "ToolEnabledAgent":
        """注册工具实例的所有 @tool 方法

        Args:
            instance: 工具类实例
            prefix: 工具名前缀
            category: 工具类别

        Returns:
            self，支持链式调用
        """
        self._tool_registry.register_from_instance(
            instance, prefix=prefix, category=category
        )
        _logger.agent(
            f"Agent {self._name} registered tools from {instance.__class__.__name__}"
        )
        return self

    def list_available_tools(self) -> List[str]:
        """列出所有可用工具名"""
        return self._tool_registry.list_tools()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具 schema（用于 Prompt）"""
        schemas = self._tool_registry.list_schemas()
        return [s.to_dict() for s in schemas]

    async def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具

        Args:
            name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        try:
            result = await self._tool_registry.call(name, **kwargs)
            self._stats["tool_calls"] += 1

            # 记录到工作记忆
            self._working_memory.add(
                content={"tool": name, "params": kwargs, "result": result},
                entry_type="tool_call",
                priority=0.6,
                source="agent",
            )

            # 发布事件
            if self._enable_events and self._event_bus:
                await self._event_bus.publish_type(
                    EventType.TASK_COMPLETED,
                    payload={
                        "agent": self._name,
                        "tool": name,
                        "result_summary": str(result)[:200],
                    },
                    source=self._name,
                )

            return result
        except ToolNotFoundError:
            self._stats["errors"] += 1
            _logger.agent_error(f"Agent {self._name}: tool '{name}' not found")
            raise
        except Exception as e:
            self._stats["errors"] += 1
            _logger.agent_error(f"Agent {self._name}: tool '{name}' error: {e}")
            raise

    async def call_tool_with_json(self, name: str, params_json: str) -> Any:
        """从 JSON 字符串调用工具"""
        return await self._tool_registry.call_with_json(name, params_json)

    # ---- RAG 集成 ----

    async def retrieve_context(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """检索 RAG 上下文

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 元数据过滤

        Returns:
            格式化上下文文本，未启用 RAG 时返回 None
        """
        if not self._enable_rag or self._rag_engine is None:
            return None

        try:
            result = await self._rag_engine.query(
                query,
                top_k=top_k or self._tool_config.rag_top_k,
                filters=filters,
            )
            self._stats["rag_queries"] += 1

            context = self._rag_engine.build_prompt_context(
                result,
                max_tokens=self._tool_config.rag_max_tokens,
                include_sources=True,
            )

            # 记录检索结果到工作记忆
            if result.total_found > 0:
                self._working_memory.add(
                    content=f"检索到 {result.total_found} 条相关知识",
                    entry_type="rag_result",
                    priority=0.5,
                    source="rag",
                    tags={"rag", "knowledge"},
                )

            return context
        except Exception as e:
            _logger.agent_error(f"Agent {self._name}: RAG retrieval error: {e}")
            return None

    # ---- Tier 路由 ----

    def select_tier(self, prompt: str, preferred: Optional[ModelTier] = None) -> TierConfig:
        """为 prompt 选择合适的模型级别"""
        config, complexity = self._tier_router.route(prompt, preferred_tier=preferred)
        _logger.agent_debug(
            f"Agent {self._name}: prompt complexity={complexity}, tier={config.tier.value}"
        )
        return config

    # ---- Prompt 组装 ----

    def build_system_prompt(
        self,
        tool_schemas: Optional[List[Dict[str, Any]]] = None,
        rag_context: Optional[str] = None,
        extra_constraints: Optional[List[str]] = None,
    ) -> str:
        """构建系统 Prompt

        整合角色定义、工具说明、工作记忆、RAG 上下文。
        """
        constraints = list(self._tool_config.constraints)
        if extra_constraints:
            constraints.extend(extra_constraints)

        # 获取记忆上下文（含工作记忆、注意力焦点、情感状态等）
        working_memory = None
        memory_context_data = None
        if self._tool_config.enable_working_memory:
            memory_context_data = self._memory_context.build_context_for_prompt(
                max_entries=5
            )
            working_memory = memory_context_data.get("working_memory")

        # 获取工具 schema
        schemas = tool_schemas
        if schemas is None and self._tool_registry.list_tools():
            schemas = self.get_tool_schemas()

        return self._composer.compose_system_prompt(
            agent_role=self._tool_config.agent_role or f"Agent: {self._name}",
            task_description=self._tool_config.task_description or self._description,
            tool_schemas=schemas,
            working_memory=working_memory,
            rag_context=rag_context,
            constraints=constraints or None,
        )

    def compose_prompt(
        self,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """使用模板组装 Prompt"""
        return self._composer.compose(template_name, variables, **kwargs)

    # ---- LLM 生成（增强版） ----

    def generate_with_tier(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        preferred_tier: Optional[ModelTier] = None,
        **kwargs,
    ) -> Optional[str]:
        """使用 Tier 路由生成文本

        根据 prompt 复杂度自动选择模型级别。
        """
        tier_config = self.select_tier(prompt, preferred=preferred_tier)

        # 使用 Tier 配置的 provider/model
        original_provider = self._llm_provider
        original_model = self._llm_model
        original_max_tokens = self._llm_max_tokens
        original_temp = self._llm_temperature

        try:
            self._llm_provider = tier_config.provider
            self._llm_model = tier_config.model
            self._llm_max_tokens = tier_config.max_tokens
            self._llm_temperature = tier_config.temperature

            result = self._generate_with_llm(prompt, system_prompt, **kwargs)
            self._stats["llm_calls"] += 1

            if result:
                self._stats["tokens_input"] += len(prompt) // 4
                self._stats["tokens_output"] += len(result) // 4

            return result
        finally:
            # 恢复原始配置
            self._llm_provider = original_provider
            self._llm_model = original_model
            self._llm_max_tokens = original_max_tokens
            self._llm_temperature = original_temp

    async def generate_with_context(
        self,
        prompt: str,
        query_for_rag: Optional[str] = None,
        preferred_tier: Optional[ModelTier] = None,
        extra_constraints: Optional[List[str]] = None,
        **kwargs,
    ) -> Optional[str]:
        """带完整上下文（工具 + RAG + 工作记忆）的生成

        完整流程:
        1. 检索 RAG 上下文
        2. 构建系统 Prompt（含工具、工作记忆）
        3. Tier 路由选择模型
        4. LLM 生成
        """
        # 1. RAG 检索
        rag_context = None
        if query_for_rag:
            rag_context = await self.retrieve_context(query_for_rag)
        elif self._enable_rag:
            # 使用 prompt 本身作为查询
            rag_context = await self.retrieve_context(prompt[:200])

        # 2. 构建系统 Prompt
        system_prompt = self.build_system_prompt(
            rag_context=rag_context,
            extra_constraints=extra_constraints,
        )

        # 3. Tier 路由 + 生成
        return self.generate_with_tier(
            prompt,
            system_prompt=system_prompt,
            preferred_tier=preferred_tier,
            **kwargs,
        )

    # ---- 工作记忆操作 ----

    def add_to_working_memory(
        self,
        content: Any,
        entry_type: str = "generic",
        priority: float = 0.5,
        source: str = "",
        tags: Optional[set] = None,
    ) -> Optional[Any]:
        """添加内容到工作记忆"""
        entry = self._working_memory.add(
            content=content,
            entry_type=entry_type,
            priority=priority,
            source=source,
            tags=tags,
        )
        if entry:
            _logger.agent_debug(f"Agent {self._name}: added to working_memory: {entry_type}")
        return entry

    def get_working_memory_state(self) -> Dict[str, Any]:
        """获取工作记忆状态"""
        return self._attention.to_dict()

    def clear_working_memory(self) -> None:
        """清空工作记忆"""
        self._working_memory.clear()

    # ---- 三级记忆上下文（MemoryContext） ----

    def perceive(
        self,
        stimulus: Any,
        *,
        emotional_salience: float = 0.0,
        novelty: float = 0.5,
        source: str = "",
        tags: Optional[set] = None,
    ) -> Optional[Any]:
        """感知输入（感觉记忆 → 工作记忆）"""
        return self._memory_context.perceive(
            stimulus=stimulus,
            emotional_salience=emotional_salience,
            novelty=novelty,
            source=source,
            tags=tags,
        )

    def get_memory_context(self) -> MemoryContext:
        """获取记忆上下文实例"""
        return self._memory_context

    def get_memory_context_state(self) -> Dict[str, Any]:
        """获取完整记忆上下文状态"""
        return self._memory_context.to_dict()

    def enable_long_term_memory(self, memory_manager: Any) -> None:
        """启用长期记忆（注入 MemoryManager）"""
        self._memory_context.enable_long_term_memory(memory_manager)

    async def retrieve_long_term_memory(
        self,
        session: Any,
        query: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """从长期记忆检索信息"""
        snapshot = await self._memory_context.retrieve_long_term(
            session, query, top_k=top_k
        )
        return snapshot.to_dict()

    # ---- 事件 ----

    async def emit_event(
        self,
        event_type: EventType,
        payload: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """发布事件"""
        if self._enable_events and self._event_bus:
            await self._event_bus.publish_type(
                event_type,
                payload=payload or {},
                source=self._name,
                priority=priority,
            )

    # ---- 重载 process ----

    def process(self, message: Message) -> Message:
        """处理消息（同步接口，使用默认配置）"""
        import asyncio

        try:
            # 尝试异步处理
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果在运行中的事件循环中，创建新任务
                # 注意：这在某些情况下可能有问题，但作为兼容层使用
                return self._process_sync(message)
            else:
                return loop.run_until_complete(self.aprocess(message))
        except RuntimeError:
            # 无事件循环，同步处理
            return self._process_sync(message)

    def _process_sync(self, message: Message) -> Message:
        """同步处理（降级模式）"""
        self._state = AgentState.BUSY
        self._last_message = message
        self.add_message(message)

        try:
            # 简单使用基类的 LLM 生成
            prompt = str(message.content)
            system_prompt = self.build_system_prompt()

            result = self._generate_with_llm(prompt, system_prompt)

            response = self._create_message(
                content=result or "[无法生成响应]",
                message_type=MessageType.TEXT,
                processed_by=self._name,
            )
            self.add_message(response)
            self._state = AgentState.READY
            return response

        except Exception as e:
            _logger.agent_error(f"Agent {self._name} process error: {e}")
            self._state = AgentState.ERROR
            self._stats["errors"] += 1
            return self._create_message(
                content=f"处理出错: {e}",
                message_type=MessageType.SYSTEM,
                error=str(e),
            )

    async def aprocess(self, message: Message) -> Message:
        """异步处理消息（完整功能）"""
        self._state = AgentState.BUSY
        self._last_message = message
        self.add_message(message)

        # 发布开始事件
        if self._enable_events and self._event_bus:
            await self._event_bus.publish_type(
                EventType.AGENT_STARTED,
                payload={"agent": self._name, "message_id": message.id},
                source=self._name,
            )

        try:
            # 将消息内容加入工作记忆
            self._working_memory.add(
                content=message.content,
                entry_type="user_input",
                priority=0.8,
                source="user",
                tags={"input", "user"},
            )

            # 使用完整上下文生成
            prompt = str(message.content)
            result = await self.generate_with_context(prompt)

            if result is None:
                result = "[无法生成响应]"

            response = self._create_message(
                content=result,
                message_type=MessageType.TEXT,
                processed_by=self._name,
            )
            self.add_message(response)
            self._state = AgentState.READY

            # 发布完成事件
            if self._enable_events and self._event_bus:
                await self._event_bus.publish_type(
                    EventType.AGENT_COMPLETED,
                    payload={
                        "agent": self._name,
                        "message_id": message.id,
                        "response_length": len(result),
                    },
                    source=self._name,
                )

            return response

        except Exception as e:
            _logger.agent_error(f"Agent {self._name} async process error: {e}")
            self._state = AgentState.ERROR
            self._stats["errors"] += 1

            # 发布失败事件
            if self._enable_events and self._event_bus:
                await self._event_bus.publish_type(
                    EventType.AGENT_FAILED,
                    payload={"agent": self._name, "error": str(e)},
                    source=self._name,
                    priority=EventPriority.HIGH,
                )

            return self._create_message(
                content=f"处理出错: {e}",
                message_type=MessageType.SYSTEM,
                error=str(e),
            )

    # ---- 工具调用解析（LLM 输出 → 工具调用） ----

    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """从 LLM 输出中解析工具调用

        支持格式:
        ```tool
        {"tool": "工具名", "params": {...}}
        ```

        Returns:
            工具调用列表 [{"tool": str, "params": dict}]
        """
        calls = []
        # 匹配 ```tool ... ``` 块
        import re

        pattern = r"```tool\s*\n(.*?)\n```"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            match = match.strip()
            try:
                data = json.loads(match)
                if "tool" in data:
                    calls.append(
                        {
                            "tool": data["tool"],
                            "params": data.get("params", {}),
                        }
                    )
            except json.JSONDecodeError:
                # 尝试提取 tool/params
                try:
                    tool_match = re.search(r'"tool"\s*:\s*"([^"]+)"', match)
                    if tool_match:
                        tool_name = tool_match.group(1)
                        params_match = re.search(
                            r'"params"\s*:\s*(\{[^}]*\})', match
                        )
                        params = {}
                        if params_match:
                            params = json.loads(params_match.group(1))
                        calls.append({"tool": tool_name, "params": params})
                except Exception:
                    pass

        return calls

    async def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行工具调用列表

        Returns:
            结果列表 [{"tool": str, "params": dict, "result": Any}]
        """
        results = []
        for call in tool_calls:
            try:
                result = await self.call_tool(call["tool"], **call["params"])
                results.append(
                    {
                        "tool": call["tool"],
                        "params": call["params"],
                        "result": result,
                        "success": True,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "tool": call["tool"],
                        "params": call["params"],
                        "result": str(e),
                        "success": False,
                    }
                )
        return results

    async def generate_with_tools(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tool_rounds: int = 3,
        preferred_tier: Optional[ModelTier] = None,
    ) -> str:
        """生成文本，支持多轮工具调用

        流程:
        1. 生成初始响应
        2. 解析工具调用
        3. 执行工具
        4. 将结果反馈给 LLM
        5. 重复直到无工具调用或达到最大轮数

        Args:
            prompt: 用户请求
            system_prompt: 可选系统提示
            max_tool_rounds: 最大工具调用轮数
            preferred_tier: 偏好的模型级别

        Returns:
            最终响应文本
        """
        if system_prompt is None:
            system_prompt = self.build_system_prompt()

        current_prompt = prompt
        full_response = ""

        for round_num in range(max_tool_rounds + 1):
            # 生成响应
            response = self.generate_with_tier(
                current_prompt,
                system_prompt=system_prompt,
                preferred_tier=preferred_tier,
            )

            if response is None:
                break

            full_response = response

            # 解析工具调用
            tool_calls = self.parse_tool_calls(response)
            if not tool_calls:
                break

            # 执行工具
            tool_results = await self.execute_tool_calls(tool_calls)

            # 构建下一轮 prompt
            result_texts = []
            for tr in tool_results:
                status = "成功" if tr["success"] else "失败"
                result_texts.append(
                    f"工具 '{tr['tool']}' 调用{status}:\n"
                    f"结果: {json.dumps(tr['result'], ensure_ascii=False, default=str)[:500]}"
                )

            current_prompt = (
                f"原始请求: {prompt}\n\n"
                f"你的上一轮响应包含工具调用，以下是执行结果:\n"
                + "\n\n".join(result_texts)
                + "\n\n请基于以上结果给出最终回答。"
            )

        return full_response

    # ---- 状态与统计 ----

    def get_stats(self) -> Dict[str, Any]:
        """获取 Agent 统计信息"""
        return {
            "agent": self._name,
            "state": self._state.value,
            **self._stats,
            "working_memory": self._working_memory.to_dict(),
            "available_tools": self.list_available_tools(),
            "tier_config": self._tier_router.to_dict(),
        }

    def reset_stats(self) -> None:
        """重置统计"""
        self._stats = {
            "tool_calls": 0,
            "llm_calls": 0,
            "rag_queries": 0,
            "tokens_input": 0,
            "tokens_output": 0,
            "errors": 0,
        }

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base = super().health_check()
        base.update(
            {
                "tool_registry": {
                    "total_tools": len(self.list_available_tools()),
                },
                "working_memory": {
                    "capacity": self._working_memory.capacity,
                    "occupancy": self._working_memory.occupancy,
                    "load_ratio": round(self._working_memory.load_ratio, 3),
                },
                "attention": {
                    "cognitive_load": round(self._attention.cognitive_load, 3),
                    "is_overloaded": self._attention.is_overloaded(),
                    "focus": {
                        "target_id": self._attention.focus.target_id,
                        "target_type": self._attention.focus.target_type,
                    },
                },
                "rag_enabled": self._enable_rag,
                "events_enabled": self._enable_events,
                "stats": self._stats,
            }
        )
        return base
