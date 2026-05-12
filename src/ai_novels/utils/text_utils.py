"""
文本处理工具函数

@file: utils/text_utils.py
@date: 2026-03-13
@version: 1.0.0
@description: 文本处理相关函数
"""

import re
from typing import List, Dict, Optional, Any
from datetime import datetime
from functools import lru_cache


def format_chinese_date(dt: datetime) -> str:
    """
    格式化中文日期

    Args:
        dt: datetime对象

    Returns:
        "YYYY年MM月DD日"格式的日期字符串
    """
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日"


def parse_chinese_chapter_word_count(text: str) -> int:
    """
    统计中文字符数（包括标点符号）

    Args:
        text: 文本内容

    Returns:
        字符数量
    """
    # 统计所有中文字符（包括标点符号）
    chinese_pattern = r'[\u4e00-\u9fff]'
    chinese_chars = re.findall(chinese_pattern, text)
    return len(chinese_chars)


def count_chinese_words(text: str) -> int:
    """
    统计中文单词数（按词语分割）

    Args:
        text: 文本内容

    Returns:
        单词数量
    """
    # 简单按字符分割，实际应用可能需要分词
    chinese_pattern = r'[\u4e00-\u9fff]+'
    words = re.findall(chinese_pattern, text)
    return len(words)


def extract_paragraphs(text: str) -> List[str]:
    """
    提取段落

    Args:
        text: Markdown或纯文本

    Returns:
        段落列表
    """
    # 分割段落：两个或更多换行符
    paragraphs = re.split(r'\n\s*\n', text)

    # 过滤空段落
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return paragraphs


def extract_headings(text: str) -> List[Dict[str, Any]]:
    """
    提取标题层级

    Args:
        text: Markdown文本

    Returns:
        标题列表，每个元素包含level和text
    """
    headings = []
    pattern = r'^(#{1,6})\s+(.+)$'

    for line in text.split('\n'):
        match = re.match(pattern, line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append({
                'level': level,
                'text': title
            })

    return headings


def merge_nested_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并字典

    Args:
        base: 基础字典
        overlay: 覆盖字典

    Returns:
        合并后的字典
    """
    result = base.copy()

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_nested_dict(result[key], value)
        else:
            result[key] = value

    return result


def sanitize_text(text: str) -> str:
    """
    清理文本中的非法字符

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    # 移除控制字符（保留换行和制表符）
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return cleaned


def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
    """
    截断文本

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 后缀

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def word_wrap(text: str, width: int = 80) -> str:
    """
    文本自动换行

    Args:
        text: 原始文本
        width: 每行宽度

    Returns:
        自动换行后的文本
    """
    words = text.split()
    if not words:
        return text

    lines = []
    current_line = words[0]

    for word in words[1:]:
        if len(current_line) + 1 + len(word) <= width:
            current_line += ' ' + word
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return '\n'.join(lines)


def camel_to_snake(name: str) -> str:
    """
    驼峰命名转下划线命名

    Args:
        name: 驼峰命名字符串

    Returns:
        下划线命名字符串
    """
    # 处理连续大写
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    # 处理小写后的大写
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def snake_to_camel(name: str) -> str:
    """
    下划线命名转驼峰命名

    Args:
        name: 下划线命名字符串

    Returns:
        驼峰命名字符串
    """
    components = name.split('_')
    return components[0] + ''.join(x.capitalize() for x in components[1:])


def remove_html_tags(text: str) -> str:
    """
    移除HTML标签

    Args:
        text: 包含HTML的文本

    Returns:
        纯文本
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def extract_urls(text: str) -> List[str]:
    """
    提取URL

    Args:
        text: 文本

    Returns:
        URL列表
    """
    url_pattern = r'https?://[^\s<>)"]+|www\.[^\s<>)"]+'
    return re.findall(url_pattern, text)


def extract_emails(text: str) -> List[str]:
    """
    提取邮箱地址

    Args:
        text: 文本

    Returns:
        邮箱地址列表
    """
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(email_pattern, text)


def count_sentences(text: str) -> int:
    """
    统计句子数

    Args:
        text: 文本

    Returns:
        句子数
    """
    sentence_pattern = r'[。！？…]+'
    sentences = re.split(sentence_pattern, text)
    # 过滤空句子
    return len([s for s in sentences if s.strip()])


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """
    提取关键词（简单实现）

    Args:
        text: 文本
        top_n: 返回前N个关键词

    Returns:
        关键词列表
    """
    # 中文常用停用词
    stopwords = {
        '的', '了', '在', '是', '我', '有', '和', '就', '都', '而',
        '及', '与', '着', '也', '还', '但', '并', '个', '其', '已',
        '对', '们', '则', '哪', '后', '中', '等', '会', '可', '都'
    }

    # 提取中文词语（2-4个字符）
    word_pattern = r'[\u4e00-\u9fff]{2,4}'
    words = re.findall(word_pattern, text)

    # 统计词频
    word_freq = {}
    for word in words:
        if word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1

    # 按频率排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, freq in sorted_words[:top_n]]


@lru_cache(maxsize=128)
def cached_text_processing(text: str, operation: str) -> Any:
    """
    缓存的文本处理（用于频繁调用的处理）

    Args:
        text: 文本
        operation: 操作类型

    Returns:
        处理结果
    """
    if operation == 'count_words':
        return count_chinese_words(text)
    elif operation == 'count_chars':
        return parse_chinese_chapter_word_count(text)
    elif operation == 'extract_paragraphs':
        return extract_paragraphs(text)
    return None


if __name__ == "__main__":
    # 示例用法
    print("Text utils module loaded successfully!")

    # 测试格式化日期
    dt = datetime.now()
    print(f"Formatted date: {format_chinese_date(dt)}")

    # 测试段落提取
    text = "第一段文字。\n\n第二段文字。\n\n第三段文字。"
    paragraphs = extract_paragraphs(text)
    print(f"Paragraphs: {paragraphs}")
