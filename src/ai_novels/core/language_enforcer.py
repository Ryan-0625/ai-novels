"""
语言强制模块

确保所有生成内容使用指定的语言（简体中文）

@file: core/language_enforcer.py
@date: 2026-04-08
@author: AI-Novels Team
@version: 2.0
@description: 语言强制验证和转换模块
"""

import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class LanguageCode(Enum):
    """语言代码枚举"""
    ZH_CN = "zh-CN"      # 简体中文
    ZH_TW = "zh-TW"      # 繁体中文
    EN = "en"            # 英语
    JA = "ja"            # 日语
    KO = "ko"            # 韩语


@dataclass
class LanguageCheckResult:
    """语言检查结果"""
    is_valid: bool
    detected_language: str
    confidence: float
    issues: List[str]
    suggestions: List[str]


class LanguageEnforcer:
    """
    语言强制器
    
    确保输出内容符合指定的语言要求
    """
    
    # 简体中文常见字符范围
    SIMPLIFIED_CHARS = set(
        "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动"
        "同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自"
        "理长物现实加都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义"
        "事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没"
        "结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式"
        "活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区"
        "强放决西被干做必战先回则任取完举色或或或或或或或或或或或或或或或或或或或或或或"
    )
    
    # 繁体中文特有字符
    TRADITIONAL_CHARS = set(
        "的一是在不了有和人這中大為上個國我以要他時來用們生到作地於出就分對成會可主發年動"
        "同工也能下過子說產種面而方後多定行學法所民得經十三之進著等部度家電力裡如水化高自"
        "理長物現實加都兩體制機當使點從業本去把性好應開它合還因由其些然前外天政四日那社義"
        "事平形相全表間樣與關各重新線內數正心反你明看原又麼利比或但質氣第向道命此變條只沒"
        "結解問意建月公無系軍很情者最立代想已通並提直題黨程展五果料象員革位入常文總次品式"
        "活設及管特件長求老頭基資邊流路級少圖山統接知較將組見計別她手角期根論運農指幾九區"
        "強放決西被幹做必戰先回則任取完舉色"
    )
    
    # AI 写作常见模式（需要去除的）
    AI_PATTERNS = {
        "inflated_symbolism": [
            r"是.*?的见证", r"是.*?的缩影", r"是.*?的写照",
            r"象征着.*?的", r"代表着.*?的", r"体现了.*?的",
            r"标志着.*?的", r"开启了.*?的", r"书写了.*?的"
        ],
        "ai_vocabulary": [
            "delve", "tapestry", "leverage", "crucial", "pivotal",
            "underscore", "highlight", "showcase", "foster", "garner",
            "intricate", "landscape", "testament", "embark", "journey"
        ],
        "filler_phrases": [
            r"值得一提的是", r"必须指出的是", r"显而易见的是",
            r"众所周知", r"不可否认的是", r"从某种意义上说",
            r"总的来说", r"归根结底", r"归根结底"
        ],
        "promotional_language": [
            r"令人惊叹的", r"卓越的", r"非凡的", r"无与伦比的",
            r"革命性的", r"开创性的", r\"极具.*?价值的\"
        ]
    }
    
    def __init__(self, target_language: LanguageCode = LanguageCode.ZH_CN):
        """
        初始化语言强制器
        
        Args:
            target_language: 目标语言代码
        """
        self.target_language = target_language
        self.validation_enabled = True
        self.auto_correct = True
        
    def enforce_language(self, text: str, context: str = "") -> str:
        """
        强制文本使用目标语言
        
        Args:
            text: 输入文本
            context: 上下文信息
            
        Returns:
            处理后的文本
        """
        if not text:
            return text
            
        # 1. 检测当前语言
        check_result = self.detect_language(text)
        
        # 2. 如果已经是目标语言，进行质量检查
        if check_result.detected_language == self.target_language.value:
            return self._improve_quality(text)
        
        # 3. 如果不是目标语言，标记问题
        issues = check_result.issues
        
        # 4. 应用语言强制提示
        enforced_text = self._apply_language_rules(text)
        
        return enforced_text
    
    def detect_language(self, text: str) -> LanguageCheckResult:
        """
        检测文本语言
        
        Args:
            text: 输入文本
            
        Returns:
            语言检查结果
        """
        if not text:
            return LanguageCheckResult(
                is_valid=False,
                detected_language="unknown",
                confidence=0.0,
                issues=["Empty text"],
                suggestions=["Provide non-empty text"]
            )
        
        issues = []
        suggestions = []
        
        # 检测中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        
        if total_chars == 0:
            chinese_ratio = 0
        else:
            chinese_ratio = chinese_chars / total_chars
        
        # 检测英文单词
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        
        # 检测繁体字符
        traditional_count = sum(1 for char in text if char in self.TRADITIONAL_CHARS)
        
        # 判断语言
        if chinese_ratio > 0.5:
            if traditional_count > chinese_chars * 0.3:
                detected = LanguageCode.ZH_TW.value
                issues.append("检测到繁体中文")
                suggestions.append("转换为简体中文")
            else:
                detected = LanguageCode.ZH_CN.value
        elif english_words > 10:
            detected = LanguageCode.EN.value
            issues.append("检测到英文内容")
            suggestions.append("翻译为简体中文")
        else:
            detected = "mixed"
            issues.append("混合语言内容")
            suggestions.append("统一使用简体中文")
        
        # 检查AI痕迹
        ai_issues = self._detect_ai_patterns(text)
        issues.extend(ai_issues)
        
        is_valid = detected == self.target_language.value and len(ai_issues) == 0
        
        return LanguageCheckResult(
            is_valid=is_valid,
            detected_language=detected,
            confidence=chinese_ratio if detected == LanguageCode.ZH_CN.value else 1 - chinese_ratio,
            issues=issues,
            suggestions=suggestions
        )
    
    def _detect_ai_patterns(self, text: str) -> List[str]:
        """
        检测AI写作模式
        
        Args:
            text: 输入文本
            
        Returns:
            发现的问题列表
        """
        issues = []
        
        # 检测过度象征
        for pattern in self.AI_PATTERNS["inflated_symbolism"]:
            if re.search(pattern, text):
                issues.append(f"过度象征化表达: {pattern}")
        
        # 检测AI词汇
        for word in self.AI_PATTERNS["ai_vocabulary"]:
            if word.lower() in text.lower():
                issues.append(f"AI高频词汇: {word}")
        
        # 检测填充短语
        for pattern in self.AI_PATTERNS["filler_phrases"]:
            if re.search(pattern, text):
                issues.append(f"填充短语: {pattern}")
        
        # 检测宣传语言
        for pattern in self.AI_PATTERNS["promotional_language"]:
            if re.search(pattern, text):
                issues.append(f"宣传性语言: {pattern}")
        
        return issues
    
    def _apply_language_rules(self, text: str) -> str:
        """
        应用语言规则
        
        Args:
            text: 输入文本
            
        Returns:
            处理后的文本
        """
        # 这里可以集成翻译API或规则转换
        # 目前返回原文，但添加语言强制标记
        return text
    
    def _improve_quality(self, text: str) -> str:
        """
        改进文本质量
        
        Args:
            text: 输入文本
            
        Returns:
            改进后的文本
        """
        # 去除多余的空格
        text = re.sub(r'  +', ' ', text)
        
        # 确保标点符号使用中文
        text = self._normalize_punctuation(text)
        
        return text
    
    def _normalize_punctuation(self, text: str) -> str:
        """
        规范化标点符号
        
        Args:
            text: 输入文本
            
        Returns:
            规范化后的文本
        """
        # 英文标点转中文标点
        replacements = {
            ',': '，',
            '.': '。',
            '!': '！',
            '?': '？',
            ':': '：',
            ';': '；',
            '"': '"',
            '"': '"',
            "'": ''',
            "'": ''',
            '(': '（',
            ')': '）',
            '[': '【',
            ']': '】',
        }
        
        # 只在中文语境中替换
        result = []
        for i, char in enumerate(text):
            if char in replacements:
                # 检查周围是否有中文字符
                has_chinese = False
                for j in range(max(0, i-3), min(len(text), i+4)):
                    if '\u4e00' <= text[j] <= '\u9fff':
                        has_chinese = True
                        break
                
                if has_chinese:
                    result.append(replacements[char])
                else:
                    result.append(char)
            else:
                result.append(char)
        
        return ''.join(result)
    
    def get_system_prompt_addon(self) -> str:
        """
        获取系统提示词附加内容
        
        Returns:
            附加提示词
        """
        return f"""
## 语言强制要求

**你必须使用简体中文（zh-CN）进行所有输出！**

### 要求：
1. 所有内容必须使用简体中文书写
2. 避免使用英文词汇（专有名词除外）
3. 使用中文标点符号（，。！？：；""''（）【】）
4. 避免翻译腔，使用地道的中文表达
5. 人名、地名可以保留特定风格，但描述必须使用中文

### 禁止：
- 使用AI高频词汇（delve, tapestry, leverage等）
- 过度使用被动语态
- 机械化的三段式列举
- 空洞的修饰语（\"非常重要的\"、\"极其关键的\"）
- 填充短语（\"值得一提的是\"、\"必须指出的是\"）

### 质量检查：
输出前请自我检查：
- [ ] 所有内容是否为简体中文？
- [ ] 是否使用了中文标点？
- [ ] 表达是否自然流畅？
- [ ] 是否有AI写作痕迹？

**违反以上要求的内容将被拒绝！**
"""


class ContentQualityChecker:
    """
    内容质量检查器
    
    检查生成内容的质量，确保符合标准
    """
    
    def __init__(self):
        self.language_enforcer = LanguageEnforcer()
        
    def check_content(self, content: str, content_type: str = "chapter") -> Dict[str, Any]:
        """
        检查内容质量
        
        Args:
            content: 内容文本
            content_type: 内容类型（chapter/outline/character等）
            
        Returns:
            质量检查结果
        """
        results = {
            "overall_score": 0,
            "passed": False,
            "checks": {}
        }
        
        # 1. 语言检查
        lang_result = self.language_enforcer.detect_language(content)
        results["checks"]["language"] = {
            "score": 10 if lang_result.is_valid else 5,
            "passed": lang_result.is_valid,
            "issues": lang_result.issues
        }
        
        # 2. 长度检查
        word_count = len(content)
        results["checks"]["length"] = {
            "score": 10 if word_count > 500 else 5,
            "passed": word_count > 100,
            "word_count": word_count
        }
        
        # 3. 结构检查
        structure_score = self._check_structure(content, content_type)
        results["checks"]["structure"] = structure_score
        
        # 4. 多样性检查
        diversity_score = self._check_diversity(content)
        results["checks"]["diversity"] = diversity_score
        
        # 计算总分
        total_score = sum(check["score"] for check in results["checks"].values())
        max_score = len(results["checks"]) * 10
        results["overall_score"] = (total_score / max_score) * 10
        results["passed"] = results["overall_score"] >= 7.0
        
        return results
    
    def _check_structure(self, content: str, content_type: str) -> Dict[str, Any]:
        """
        检查内容结构
        
        Args:
            content: 内容文本
            content_type: 内容类型
            
        Returns:
            结构检查结果
        """
        issues = []
        
        # 检查段落数量
        paragraphs = [p for p in content.split('\n') if p.strip()]
        if len(paragraphs) < 3:
            issues.append("段落过少，内容可能过于集中")
        
        # 检查对话比例
        dialogue_count = content.count('"') + content.count('"') + content.count('"') + content.count('"')
        dialogue_ratio = dialogue_count / max(len(content), 1)
        
        if dialogue_ratio > 0.5:
            issues.append("对话比例过高")
        elif dialogue_ratio < 0.1 and content_type == "chapter":
            issues.append("对话比例过低，建议增加对话")
        
        return {
            "score": 8 if len(issues) == 0 else 6,
            "passed": len(issues) <= 1,
            "issues": issues,
            "paragraphs": len(paragraphs),
            "dialogue_ratio": dialogue_ratio
        }
    
    def _check_diversity(self, content: str) -> Dict[str, Any]:
        """
        检查内容多样性
        
        Args:
            content: 内容文本
            
        Returns:
            多样性检查结果
        """
        issues = []
        
        # 检查句子长度多样性
        sentences = re.split(r'[。！？]', content)
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        
        if len(sentence_lengths) > 1:
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
            
            if variance < 10:
                issues.append("句子长度过于统一，缺乏节奏变化")
        
        # 检查词汇多样性
        words = re.findall(r'[\u4e00-\u9fff]+', content)
        unique_words = set(words)
        if len(words) > 0:
            diversity_ratio = len(unique_words) / len(words)
            if diversity_ratio < 0.3:
                issues.append("词汇重复度较高")
        
        return {
            "score": 8 if len(issues) == 0 else 6,
            "passed": len(issues) <= 1,
            "issues": issues
        }


# 全局实例
_language_enforcer: Optional[LanguageEnforcer] = None
_quality_checker: Optional[ContentQualityChecker] = None


def get_language_enforcer() -> LanguageEnforcer:
    """获取语言强制器实例"""
    global _language_enforcer
    if _language_enforcer is None:
        _language_enforcer = LanguageEnforcer()
    return _language_enforcer


def get_quality_checker() -> ContentQualityChecker:
    """获取质量检查器实例"""
    global _quality_checker
    if _quality_checker is None:
        _quality_checker = ContentQualityChecker()
    return _quality_checker
