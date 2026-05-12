"""
QualityCheckerAgent - 质量检查智能体

@file: agents/quality_checker.py
@date: 2026-03-12
@author: AI-Novels Team
@version: 1.0
@description: 连贯性/一致性/风格检查
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .base import BaseAgent, AgentConfig, Message, MessageType
from ai_novels.persistence import get_persistence_manager


class CheckType(Enum):
    """检查类型"""
    COHERENCE = "coherence"         # 连贯性
    CONSISTENCY = "consistency"     # 一致性
    STYLE = "style"                 # 风格
    PLOT = "plot"                   # 情节
    CHARACTER = "character"         # 角色
    SETTING = "setting"             # 世界观
    GRAMMAR = "grammar"             # 语法
    PACING = "pacing"               # 节奏


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = "critical"           # 严重
    MAJOR = "major"                 # 主要
    MINOR = "minor"                 # 次要
    SUGGESTION = "suggestion"       # 建议


@dataclass
class QualityIssue:
    """质量问题"""
    issue_id: str
    issue_type: CheckType
    severity: IssueSeverity
    message: str
    location: str  # 位置 (章节-段落)
    context: str     # 上下文
    suggestion: str  # 建议
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "type": self.issue_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "location": self.location,
            "context": self.context,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class QualityReport:
    """质量报告"""
    report_id: str
    content_id: str
    overall_score: float
    chapters_checked: int
    issues: List[QualityIssue]
    check_results: Dict[str, Dict[str, Any]]
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "content_id": self.content_id,
            "overall_score": self.overall_score,
            "chapters_checked": self.chapters_checked,
            "issues": [i.to_dict() for i in self.issues],
            "check_results": self.check_results,
            "timestamp": self.timestamp
        }

    def json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class QualityCheckerAgent(BaseAgent):
    """
    质量检查智能体

    核心功能：
    - 连贯性检查（逻辑流、过渡、因果）
    - 一致性检查（时间线、角色特征、世界观）
    - 风格检查（词汇、句式、语气）
    - 情节检查（节奏、张力、转折）
    - 角色检查（行为一致性、发展）
    - 语法检查（基础错误）
    """

    def __init__(self, config: AgentConfig = None):
        if config is None:
            config = AgentConfig(
                name="quality_checker",
                description="Content quality verification",
                provider="ollama",
                model="qwen2.5-7b",
                max_tokens=4096
            )
        super().__init__(config)

        # 质量问题存储
        self._issues: List[QualityIssue] = []
        self._reports: Dict[str, QualityReport] = {}

        # 检查规则
        self._coherence_rules = [
            self._check_coherence_llm,
        ]

        self._consistency_rules = [
            self._check_consistency_llm,
        ]

        self._style_rules = [
            self._check_style_llm,
        ]

        self._plot_rules = [
            self._check_plot_llm,
        ]

        # 统计
        self._total_checks_performed = 0
        self._total_issues_found = 0
        self._check_history: List[Dict[str, Any]] = []

        # 缓存章节内容（由 _generate_quality_report 填充）
        self._chapter_contents: Dict[str, str] = {}
        # 缓存 Task Context（genre/style/target_audience），由 process 解析
        self._task_genre: str = ""
        self._task_style: str = ""
        self._task_audience: str = ""

    def process(self, message: Message) -> Message:
        """处理消息"""
        content = str(message.content).lower()

        if "check" in content or "quality" in content:
            if "report" in content or "generate" in content:
                return self._handle_generate_report(message)
            elif "issues" in content or "list" in content:
                return self._handle_list_issues(message)
            elif "coherence" in content:
                return self._handle_coherence_check(message)
            elif "consistency" in content:
                return self._handle_consistency_check(message)
            elif "style" in content:
                return self._handle_style_check(message)
            elif "plot" in content:
                return self._handle_plot_check(message)
            elif "character" in content or "character" in content:
                return self._handle_character_check(message)
        elif "fix" in content and "suggestion" in content:
            return self._handle_get_suggestion(message)

        return self._handle_generate_report(message)

    def _parse_task_context(self, content: str) -> None:
        """从消息内容中提取 Task Context 的 genre/style/audience"""
        for line in content.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, _, value = line.partition(':')
            key = key.strip().lower()
            value = value.strip()
            if key == 'genre' and value:
                self._task_genre = value
            elif key == 'style' and value:
                self._task_style = value
            elif key in ('target audience', 'target_audience') and value:
                self._task_audience = value

    def _task_context_section(self) -> str:
        """构建 Task Context 文本段供 LLM 提示词使用"""
        parts = []
        if self._task_genre:
            parts.append(f"目标体裁: {self._task_genre}")
        if self._task_style:
            parts.append(f"写作风格: {self._task_style}")
        if self._task_audience:
            parts.append(f"目标读者: {self._task_audience}")
        return "\n".join(parts)

    def _handle_generate_report(self, message: Message) -> Message:
        """处理生成报告请求"""
        content = str(message.content)

        # 解析 Task Context（genre/style/audience）
        self._parse_task_context(content)

        content_id = self._extract_param(content, "content_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        # 解析章节
        chapters = self._parse_chapters(chapters_str)

        # 生成检查报告
        report = self._generate_quality_report(
            content_id=content_id,
            chapters=chapters
        )

        self._reports[content_id] = report
        self._issues.extend(report.issues)
        self._total_issues_found += len(report.issues)
        self._total_checks_performed += 1

        response = f"Quality Report for {content_id}:\n\n"
        response += f"Overall Score: {report.overall_score:.1f}/100\n"
        response += f"Chapters Checked: {report.chapters_checked}\n"
        response += f"Total Issues: {len(report.issues)}\n\n"

        # 按严重程度分类统计
        by_severity = defaultdict(list)
        for issue in report.issues:
            by_severity[issue.severity.value].append(issue)

        response += "Issues by Severity:\n"
        for severity in ["critical", "major", "minor", "suggestion"]:
            count = len(by_severity[severity])
            if count > 0:
                response += f"  {severity.upper()}: {count}\n"

        # 显示前几个问题
        if report.issues:
            response += "\nTop Issues:\n"
            for i, issue in enumerate(report.issues[:5], 1):
                response += f"{i}. [{issue.severity.value.upper()}] {issue.message[:60]}...\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            content_id=content_id,
            overall_score=report.overall_score,
            issue_count=len(report.issues)
        )

    def _handle_list_issues(self, message: Message) -> Message:
        """处理列出问题请求"""
        content = str(message.content)

        severity_filter = self._extract_param(content, "severity", "").lower()
        type_filter = self._extract_param(content, "type", "").lower()

        issues = self._issues[:]

        if severity_filter:
            issues = [i for i in issues if i.severity.value == severity_filter]
        if type_filter:
            issues = [i for i in issues if i.issue_type.value == type_filter]

        response = f"Quality Issues ({len(issues)} total):\n\n"
        for i, issue in enumerate(issues[:20], 1):
            response += f"{i}. [{issue.severity.value.upper()}] {issue.issue_type.value}\n"
            response += f"   {issue.message[:80]}...\n"
            response += f"   Location: {issue.location}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            issue_count=len(issues)
        )

    def _handle_coherence_check(self, message: Message) -> Message:
        """处理连贯性检查请求"""
        content = str(message.content)

        content_id = self._extract_param(content, "content_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        chapters = self._parse_chapters(chapters_str)

        issues = []
        for rule in self._coherence_rules:
            issues.extend(rule(content_id, chapters))

        self._issues.extend(issues)
        self._total_checks_performed += 1

        response = f"Coherence Check for {content_id}:\n\n"
        response += f"Issues Found: {len(issues)}\n\n"

        # 按严重程度分组
        critical = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        major = [i for i in issues if i.severity == IssueSeverity.MAJOR]
        minor = [i for i in issues if i.severity == IssueSeverity.MINOR]

        if critical:
            response += "CRITICAL:\n"
            for issue in critical:
                response += f"  - {issue.message}\n"
            response += "\n"

        if major:
            response += "MAJOR:\n"
            for issue in major:
                response += f"  - {issue.message}\n"
            response += "\n"

        response += f"MINOR: {len(minor)} issues\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            coherence_issues=len(issues)
        )

    def _handle_consistency_check(self, message: Message) -> Message:
        """处理一致性检查请求"""
        content = str(message.content)

        content_id = self._extract_param(content, "content_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        chapters = self._parse_chapters(chapters_str)

        issues = []
        for rule in self._consistency_rules:
            issues.extend(rule(content_id, chapters))

        self._issues.extend(issues)
        self._total_checks_performed += 1

        response = f"Consistency Check for {content_id}:\n\n"
        response += f"Issues Found: {len(issues)}\n\n"

        # 分组显示
        by_type = defaultdict(list)
        for issue in issues:
            by_type[issue.issue_type.value].append(issue)

        for issue_type, type_issues in by_type.items():
            response += f"{issue_type.upper()} ({len(type_issues)}):\n"
            for issue in type_issues[:3]:
                response += f"  - {issue.message}\n"
            response += "\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            consistency_issues=len(issues)
        )

    def _handle_style_check(self, message: Message) -> Message:
        """处理风格检查请求"""
        content = str(message.content)

        content_id = self._extract_param(content, "content_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        chapters = self._parse_chapters(chapters_str)

        issues = []
        for rule in self._style_rules:
            issues.extend(rule(content_id, chapters))

        self._issues.extend(issues)
        self._total_checks_performed += 1

        response = f"Style Check for {content_id}:\n\n"
        response += f"Issues Found: {len(issues)}\n\n"

        if issues:
            for issue in issues:
                response += f"[{issue.severity.value}] {issue.message}\n"
        else:
            response += "Style is consistent throughout.\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            style_issues=len(issues)
        )

    def _handle_plot_check(self, message: Message) -> Message:
        """处理情节检查请求"""
        content = str(message.content)

        content_id = self._extract_param(content, "content_id", "")
        chapters_str = self._extract_param(content, "chapters", "")

        chapters = self._parse_chapters(chapters_str)

        issues = []
        for rule in self._plot_rules:
            issues.extend(rule(content_id, chapters))

        self._issues.extend(issues)
        self._total_checks_performed += 1

        response = f"Plot Check for {content_id}:\n\n"
        response += f"Issues Found: {len(issues)}\n\n"

        for issue in issues:
            response += f"[{issue.severity.value}] {issue.message}\n"
            response += f"Suggestion: {issue.suggestion}\n\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            plot_issues=len(issues)
        )

    def _handle_character_check(self, message: Message) -> Message:
        """处理角色检查请求"""
        content = str(message.content)

        content_id = self._extract_param(content, "content_id", "")
        character_name = self._extract_param(content, "character", "")

        issues = self._check_character_llm(content_id, character_name)

        self._issues.extend(issues)
        self._total_checks_performed += 1

        response = f"Character Check for {character_name} (in {content_id}):\n\n"
        response += f"Issues Found: {len(issues)}\n\n"

        if issues:
            for issue in issues:
                response += f"[{issue.severity.value}] {issue.message}\n"
        else:
            response += "Character behavior is consistent.\n"

        return self._create_message(
            response,
            MessageType.TEXT,
            character_issues=len(issues)
        )

    def _handle_get_suggestion(self, message: Message) -> Message:
        """处理获取建议请求"""
        content = str(message.content)
        issue_id = self._extract_param(content, "issue_id", "")

        if issue_id:
            # 查找对应问题
            for issue in self._issues:
                if issue_id in issue.issue_id:
                    response = f"Suggestion for {issue_id}:\n\n"
                    response += f"Issue: {issue.message}\n"
                    response += f"Suggestion: {issue.suggestion}\n"
                    return self._create_message(response, MessageType.TEXT)

        # 返回随机建议
        suggestions = [
            "Consider adding more sensory details to improve immersion.",
            "Review character motivations to ensure they align with actions.",
            "Vary sentence structure to improve reading flow.",
            "Check for timeline consistency in consecutive chapters.",
            "Ensure emotional responses match the situation intensity.",
        ]

        response = "Quality Improvement Suggestions:\n\n"
        for i, suggestion in enumerate(suggestions, 1):
            response += f"{i}. {suggestion}\n"

        return self._create_message(response, MessageType.TEXT)

    def _handle_general_request(self, message: Message) -> Message:
        """处理一般请求"""
        response = (
            "Quality Checker Agent available commands:\n"
            "- 'generate report content_id=X chapters=X' - 生成质量报告\n"
            "- 'list issues [severity=X] [type=X]' - 列出问题\n"
            "- 'check coherence content_id=X chapters=X' - 连贯性检查\n"
            "- 'check consistency content_id=X chapters=X' - 一致性检查\n"
            "- 'check style content_id=X chapters=X' - 风格检查\n"
            "- 'check plot content_id=X chapters=X' - 情节检查\n"
            "- 'check character content_id=X character=X' - 角色检查\n"
            "- 'get suggestion issue_id=X' - 获取改进建议"
        )
        return self._create_message(response)

    def _generate_quality_report(
        self,
        content_id: str,
        chapters: List[str]
    ) -> QualityReport:
        """
        生成质量报告

        Args:
            content_id: 内容ID
            chapters: 章节列表

        Returns:
            QualityReport实例
        """
        report_id = f"report_{content_id}_{int(time.time())}"

        all_issues = []
        check_results = {}

        # 加载章节内容供 LLM 检查使用
        self._load_chapter_content(content_id, chapters)

        # 执行各项检查
        for check_type, rules in [
            (CheckType.COHERENCE, self._coherence_rules),
            (CheckType.CONSISTENCY, self._consistency_rules),
            (CheckType.STYLE, self._style_rules),
            (CheckType.PLOT, self._plot_rules),
        ]:
            for rule in rules:
                issues = rule(content_id, chapters)
                all_issues.extend(issues)

                # 记录检查结果
                rule_name = rule.__name__
                check_results[rule_name] = {
                    "issues_found": len(issues),
                    "severity_distribution": self._get_severity_distribution(issues),
                    "check_type": check_type.value
                }

        # 计算总体分数
        overall_score = self._calculate_overall_score(all_issues)

        report = QualityReport(
            report_id=report_id,
            content_id=content_id,
            overall_score=overall_score,
            chapters_checked=len(chapters),
            issues=all_issues,
            check_results=check_results,
            timestamp=time.time()
        )

        return report

    def _load_chapter_content(self, content_id: str, chapters: List[str]) -> None:
        """从数据库加载章节内容供 LLM 检查使用"""
        self._chapter_contents = {}
        pm = get_persistence_manager()
        if not pm.mongodb_client:
            return
        try:
            # 按章节号读取内容
            for ch in chapters:
                ch_num = None
                for prefix in ["chapter_", "Chapter ", "第"]:
                    if prefix in ch:
                        digits = "".join(filter(str.isdigit, ch.split(prefix)[-1]))
                        if digits:
                            ch_num = int(digits)
                            break
                if ch_num is None:
                    continue
                cursor = pm.mongodb_client.read(
                    collection="chapters",
                    query={"task_id": content_id, "chapter_num": ch_num},
                    limit=1,
                )
                docs = list(cursor) if hasattr(cursor, "__iter__") else [cursor]
                for doc in docs if isinstance(docs, list) else [docs]:
                    text = doc.get("content", "") if isinstance(doc, dict) else ""
                    self._chapter_contents[ch] = text[:3000]
        except Exception:
            pass

    def _build_content_section(self) -> str:
        """构建章节内容文本供 LLM 评估"""
        if not self._chapter_contents:
            return ""
        parts = ["\n\n## 章节内容："]
        for ch_name, text in self._chapter_contents.items():
            if text:
                parts.append(f"\n### {ch_name}\n{text[:2000]}\n")
        return "".join(parts)

    def _parse_llm_issues(self, llm_response: str, content_id: str, check_type: CheckType) -> List[QualityIssue]:
        """解析 LLM 返回的 JSON 问题列表"""
        import json
        issues = []
        try:
            data = json.loads(llm_response)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    try:
                        issues.append(QualityIssue(
                            issue_id=f"{check_type.value}_{content_id}_{len(issues)}",
                            issue_type=check_type,
                            severity=IssueSeverity(item.get("severity", "minor")),
                            message=item.get("message", ""),
                            location=item.get("location", content_id),
                            context=item.get("context", ""),
                            suggestion=item.get("suggestion", ""),
                        ))
                    except (ValueError, KeyError):
                        continue
        except (json.JSONDecodeError, TypeError):
            pass
        return issues

    def _check_coherence_llm(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """使用 LLM 检查时间线/因果/过渡连贯性"""
        task_ctx = self._task_context_section()
        ctx_section = f"\n{task_ctx}\n" if task_ctx else ""
        prompt = (
            f"你是一个小说质量评审专家。分析以下章节列表的时间线一致性、因果逻辑和过渡平滑度。\n\n"
            f"内容ID: {content_id}\n"
            f"章节数: {len(chapters)}\n"
            f"章节列表: {', '.join(chapters[:10])}\n"
            f"{ctx_section}"
            f"{self._build_content_section()}\n"
            f"以JSON数组格式返回发现的问题，每个问题包含：\n"
            f"- severity: 严重程度（critical/major/minor/suggestion）\n"
            f"- message: 问题描述\n"
            f"- location: 问题位置\n"
            f"- context: 上下文说明\n"
            f"- suggestion: 改进建议\n"
            f"如果没问题返回空数组 []。"
        )
        llm_response = self._generate_with_llm(prompt)
        return self._parse_llm_issues(llm_response, content_id, CheckType.COHERENCE)

    def _check_consistency_llm(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """使用 LLM 检查设定/时间/角色一致性"""
        task_ctx = self._task_context_section()
        ctx_section = f"\n{task_ctx}\n" if task_ctx else ""
        prompt = (
            f"你是一个小说质量评审专家。分析以下章节列表的世界观一致性、时间一致性和设定连贯性。\n\n"
            f"内容ID: {content_id}\n"
            f"章节数: {len(chapters)}\n"
            f"章节列表: {', '.join(chapters[:10])}\n"
            f"{ctx_section}"
            f"{self._build_content_section()}\n"
            f"以JSON数组格式返回发现的问题，每个问题包含：\n"
            f"- severity: 严重程度（critical/major/minor/suggestion）\n"
            f"- message: 问题描述\n"
            f"- location: 问题位置\n"
            f"- context: 上下文说明\n"
            f"- suggestion: 改进建议\n"
            f"如果没问题返回空数组 []。"
        )
        llm_response = self._generate_with_llm(prompt)
        return self._parse_llm_issues(llm_response, content_id, CheckType.CONSISTENCY)

    def _check_style_llm(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """使用 LLM 检查词汇/句式/语气风格一致性"""
        task_ctx = self._task_context_section()
        ctx_section = f"\n{task_ctx}\n" if task_ctx else ""
        prompt = (
            f"你是一个小说风格评审专家。分析以下章节列表的词汇水平、句式多样性和语气一致性。\n\n"
            f"内容ID: {content_id}\n"
            f"章节数: {len(chapters)}\n"
            f"章节列表: {', '.join(chapters[:10])}\n"
            f"{ctx_section}"
            f"{self._build_content_section()}\n"
            f"以JSON数组格式返回发现的问题，每个问题包含：\n"
            f"- severity: 严重程度（critical/major/minor/suggestion）\n"
            f"- message: 问题描述\n"
            f"- location: 问题位置\n"
            f"- context: 上下文说明\n"
            f"- suggestion: 改进建议\n"
            f"如果没问题返回空数组 []。"
        )
        llm_response = self._generate_with_llm(prompt)
        return self._parse_llm_issues(llm_response, content_id, CheckType.STYLE)

    def _check_plot_llm(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """使用 LLM 检查节奏/张力/高潮位置等情节质量"""
        task_ctx = self._task_context_section()
        ctx_section = f"\n{task_ctx}\n" if task_ctx else ""
        prompt = (
            f"你是一个小说情节评审专家。分析以下章节列表的叙事节奏、张力弧线和高潮位置。\n\n"
            f"内容ID: {content_id}\n"
            f"章节数: {len(chapters)}\n"
            f"章节列表: {', '.join(chapters[:10])}\n"
            f"{ctx_section}"
            f"{self._build_content_section()}\n"
            f"以JSON数组格式返回发现的问题，每个问题包含：\n"
            f"- severity: 严重程度（critical/major/minor/suggestion）\n"
            f"- message: 问题描述\n"
            f"- location: 问题位置\n"
            f"- context: 上下文说明\n"
            f"- suggestion: 改进建议\n"
            f"如果没问题返回空数组 []。"
        )
        llm_response = self._generate_with_llm(prompt)
        return self._parse_llm_issues(llm_response, content_id, CheckType.PLOT)

    def _check_character_llm(
        self,
        content_id: str,
        character_name: str
    ) -> List[QualityIssue]:
        """使用 LLM 检查角色一致性和行为合理性"""
        prompt = (
            f"你是一个小说角色评审专家。分析角色 '{character_name}' 的行为一致性和角色发展。\n\n"
            f"内容ID: {content_id}\n\n"
            f"以JSON数组格式返回发现的问题，每个问题包含：\n"
            f"- severity: 严重程度（critical/major/minor/suggestion）\n"
            f"- message: 问题描述\n"
            f"- location: 问题位置\n"
            f"- context: 上下文说明\n"
            f"- suggestion: 改进建议\n"
            f"如果没问题返回空数组 []。"
        )
        llm_response = self._generate_with_llm(prompt)
        return self._parse_llm_issues(llm_response, content_id, CheckType.CHARACTER)

    def _get_severity_distribution(self, issues: List[QualityIssue]) -> Dict[str, int]:
        """获取严重程度分布"""
        dist = defaultdict(int)
        for issue in issues:
            dist[issue.severity.value] += 1
        return dict(dist)

    def _calculate_overall_score(self, issues: List[QualityIssue]) -> float:
        """计算总体分数"""
        if not issues:
            return 100.0

        # 基于严重程度扣分
        severity_weights = {
            IssueSeverity.CRITICAL: 20,
            IssueSeverity.MAJOR: 10,
            IssueSeverity.MINOR: 5,
            IssueSeverity.SUGGESTION: 2,
        }

        total_penalty = sum(
            severity_weights.get(issue.severity, 5) for issue in issues
        )

        # 最低50分
        return max(50.0, 100.0 - total_penalty)

    def _parse_chapters(self, chapters_str: str) -> List[str]:
        """解析章节字符串"""
        if not chapters_str:
            return ["chapter_1", "chapter_2", "chapter_3"]

        # 分割章节
        chapters = [c.strip() for c in chapters_str.split(",")]
        return chapters[:20]  # 限制数量

    def _extract_param(self, content: str, param: str, default: str = "") -> str:
        """从内容提取参数"""
        pattern = f"{param}="
        if pattern in content:
            try:
                start = content.index(pattern) + len(pattern)
                end = start
                while end < len(content) and content[end] not in " ,;":
                    end += 1
                return content[start:end]
            except ValueError:
                return default
        return default

    def generate_report(
        self,
        content_id: str,
        chapters: List[str]
    ) -> Optional[QualityReport]:
        """生成质量报告（外部接口）"""
        try:
            report = self._generate_quality_report(content_id, chapters)
            self._reports[content_id] = report
            self._issues.extend(report.issues)
            return report
        except Exception:
            return None

    def check_coherence(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """连贯性检查（外部接口）"""
        issues = []
        for rule in self._coherence_rules:
            issues.extend(rule(content_id, chapters))
        self._issues.extend(issues)
        return issues

    def check_consistency(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """一致性检查（外部接口）"""
        issues = []
        for rule in self._consistency_rules:
            issues.extend(rule(content_id, chapters))
        self._issues.extend(issues)
        return issues

    def check_style(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """风格检查（外部接口）"""
        issues = []
        for rule in self._style_rules:
            issues.extend(rule(content_id, chapters))
        self._issues.extend(issues)
        return issues

    def check_plot(
        self,
        content_id: str,
        chapters: List[str]
    ) -> List[QualityIssue]:
        """情节检查（外部接口）"""
        issues = []
        for rule in self._plot_rules:
            issues.extend(rule(content_id, chapters))
        self._issues.extend(issues)
        return issues

    def get_issues(
        self,
        severity: IssueSeverity = None,
        issue_type: CheckType = None
    ) -> List[QualityIssue]:
        """获取问题列表（外部接口）"""
        issues = self._issues[:]

        if severity:
            issues = [i for i in issues if i.severity == severity]
        if issue_type:
            issues = [i for i in issues if i.issue_type == issue_type]

        return issues

    def get_report(self, content_id: str) -> Optional[QualityReport]:
        """获取报告"""
        return self._reports.get(content_id)

    def get_all_reports(self) -> Dict[str, QualityReport]:
        """获取所有报告"""
        return self._reports

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        severity_dist = defaultdict(int)
        type_dist = defaultdict(int)

        for issue in self._issues:
            severity_dist[issue.severity.value] += 1
            type_dist[issue.issue_type.value] += 1

        return {
            "total_issues": len(self._issues),
            "by_severity": dict(severity_dist),
            "by_type": dict(type_dist),
            "total_checks": self._total_checks_performed,
            "total_reports": len(self._reports)
        }

    def export_issues(self) -> Dict[str, Any]:
        """导出问题数据"""
        return {
            "issues": [i.to_dict() for i in self._issues],
            "reports": {k: v.to_dict() for k, v in self._reports.items()},
            "statistics": self.get_statistics()
        }

    def reset(self) -> None:
        """重置智能体"""
        self._issues.clear()
        self._reports.clear()
        self._total_checks_performed = 0
        self._total_issues_found = 0
        self._check_history.clear()
