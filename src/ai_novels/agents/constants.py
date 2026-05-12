"""
Agent 模块常量定义

@file: agents/constants.py
@date: 2026-04-07
@description: 集中管理所有 Agent 相关的常量，避免 Magic Numbers
"""

# =============================================================================
# LLM 默认配置
# =============================================================================

# 默认温度参数 (控制生成随机性)
DEFAULT_TEMPERATURE: float = 0.7

# 默认最大 Token 数
DEFAULT_MAX_TOKENS: int = 8192
DEFAULT_MAX_TOKENS_LARGE: int = 16384  # 大文本生成使用

# 默认超时时间 (秒)
DEFAULT_TIMEOUT_SECONDS: int = 60
DEFAULT_TIMEOUT_SECONDS_EXTENDED: int = 120  # 长时间任务

# 默认重试次数
DEFAULT_RETRY_TIMES: int = 3

# =============================================================================
# 小说生成默认参数
# =============================================================================

# 默认章节数
DEFAULT_CHAPTER_COUNT: int = 20

# 默认每章字数
DEFAULT_WORDS_PER_CHAPTER: int = 2000
DEFAULT_WORDS_PER_CHAPTER_MIN: int = 1500

# 默认小说类型
DEFAULT_GENRE: str = "fantasy"

# 默认小说标题
DEFAULT_NOVEL_TITLE: str = "Untitled Novel"

# =============================================================================
# 内容提取参数
# =============================================================================

# 默认章节号
DEFAULT_CHAPTER_NUMBER: int = 1

# 内容截断长度 (用于日志和提示)
CONTENT_TRUNCATE_LENGTH: int = 500
CONTENT_TRUNCATE_LENGTH_LARGE: int = 2000

# =============================================================================
# 数据库和持久化
# =============================================================================

# 默认任务 ID
DEFAULT_TASK_ID: str = ""

# =============================================================================
# 角色生成参数
# =============================================================================

# 主要角色数量范围
MAIN_CHARACTERS_MIN: int = 3
MAIN_CHARACTERS_MAX: int = 5

# 次要角色数量范围
SECONDARY_CHARACTERS_MIN: int = 2
SECONDARY_CHARACTERS_MAX: int = 3

# =============================================================================
# 叙事钩子参数
# =============================================================================

# 钩子数量范围
NARRATIVE_HOOKS_MIN: int = 3
NARRATIVE_HOOKS_MAX: int = 5

# =============================================================================
# 冲突生成参数
# =============================================================================

# 角色冲突数量
CHARACTER_CONFLICTS_COUNT: int = 3
CHARACTER_CONFLICTS_COUNT_ALT: int = 4

# 情节冲突数量
PLOT_COMPLICATIONS_COUNT: int = 2
PLOT_COMPLICATIONS_COUNT_ALT: int = 3
