"""
日志浏览 API 路由

@file: api/routes/log_routes.py
@date: 2026-05-12
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query

from ai_novels.utils import get_logger
from ai_novels.utils.logger import LOG_CATEGORIES, LOG_CATEGORY_LABELS

router = APIRouter(prefix="/logs", tags=["logs"])


def _parse_log_line(line: str) -> Optional[dict]:
    """解析单行日志（支持文本格式和JSON格式）"""
    line = line.strip()
    if not line:
        return None

    # 尝试 JSON 格式解析
    if line.startswith("{"):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            pass

    # 文本格式: [2026-05-12 15:27:40] [INFO     ] [llm] message [key=val]
    pattern = r'^\[(.+?)\]\s+\[(\w+)\s*\]\s+\[(\w+)\]\s+(.+)'
    m = re.match(pattern, line)
    if m:
        timestamp, level, category, rest = m.groups()
        # 从消息中提取 key=value 参数
        kwargs = {}
        msg_text = rest
        kv_pattern = r'(\w+)=(\S+)'
        kv_matches = re.findall(kv_pattern, rest)
        if kv_matches:
            kwargs = {k: v for k, v in kv_matches}
            # 将 key=value 对从消息中移除
            msg_text = re.sub(r'\s+' + kv_pattern, '', rest).strip()
        return {
            "timestamp": timestamp,
            "level": level.strip(),
            "category": category,
            "message": msg_text,
            "kwargs": kwargs,
        }

    # 普通文本行
    return {
        "timestamp": None,
        "level": None,
        "category": None,
        "message": line,
        "kwargs": {},
    }


def _get_logger_instance():
    """获取 HierarchicalLogger 实例"""
    return get_logger()


@router.get("", summary="获取所有日志分类")
async def list_log_categories():
    """返回所有可用的日志分类及其文件信息"""
    logger = _get_logger_instance()
    log_dir = logger.get_log_dir()
    categories = []
    for cat_key, cat_name in sorted(LOG_CATEGORIES.items(), key=lambda x: x[1]):
        filepath = os.path.join(log_dir, f"{cat_name}.log")
        size_bytes = 0
        last_modified = None
        if os.path.exists(filepath):
            try:
                size_bytes = os.path.getsize(filepath)
                last_modified = datetime.fromtimestamp(
                    os.path.getmtime(filepath)
                ).isoformat()
            except OSError:
                pass
        categories.append({
            "key": cat_key,
            "name": cat_name,
            "label": LOG_CATEGORY_LABELS.get(cat_name, cat_name),
            "path": filepath,
            "size_bytes": size_bytes,
            "last_modified": last_modified,
        })
    return {"categories": categories}


@router.get("/search", summary="跨分类搜索日志")
async def search_logs(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    level: Optional[str] = Query(None, description="按级别过滤"),
    max_results: int = Query(200, ge=1, le=1000, description="最大返回条数"),
):
    """跨所有分类搜索日志"""
    logger = _get_logger_instance()
    log_dir = logger.get_log_dir()
    results = []

    for cat_name in sorted(LOG_CATEGORIES.values()):
        if len(results) >= max_results:
            break
        filepath = os.path.join(log_dir, f"{cat_name}.log")
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(results) >= max_results:
                        break
                    entry = _parse_log_line(line)
                    if entry is None:
                        continue
                    if level and entry.get("level") and entry["level"].upper() != level.upper():
                        continue
                    if q.lower() not in entry.get("message", "").lower():
                        continue
                    entry["_category"] = cat_name
                    results.append(entry)
        except OSError:
            continue

    return {
        "query": q,
        "total": len(results),
        "results": results,
    }


@router.get("/{category}", summary="获取分类日志内容")
async def get_log_lines(
    category: str,
    level: Optional[str] = Query(None, description="按级别过滤 (DEBUG/INFO/WARNING/ERROR/CRITICAL)"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(100, ge=1, le=1000, description="每页条数"),
    tail: bool = Query(False, description="是否读取文件尾部（最新日志）"),
):
    """获取指定分类的日志内容，支持过滤和分页"""
    # 验证分类
    if category not in LOG_CATEGORIES.values():
        valid = ", ".join(sorted(LOG_CATEGORIES.values()))
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid: {valid}",
        )

    logger = _get_logger_instance()
    log_dir = logger.get_log_dir()
    filepath = os.path.join(log_dir, f"{category}.log")

    if not os.path.exists(filepath):
        return {"category": category, "lines": [], "total": 0, "page": page, "page_size": page_size}

    # 读取文件
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            if tail:
                # 从尾部读取（用于实时 tail）
                lines = _tail_file(f, max_lines=page_size * 5)
            else:
                lines = f.readlines()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {e}")

    # 解析并过滤
    parsed = []
    for line in lines:
        entry = _parse_log_line(line)
        if entry is None:
            continue
        # 级别过滤
        if level and entry.get("level") and entry["level"].upper() != level.upper():
            continue
        # 关键词过滤
        if keyword and keyword.lower() not in entry.get("message", "").lower():
            continue
        parsed.append(entry)

    # 分页（tail 模式倒序）
    if tail:
        parsed.reverse()

    total = len(parsed)
    start = (page - 1) * page_size
    end = start + page_size
    page_lines = parsed[start:end]

    return {
        "category": category,
        "lines": page_lines,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total,
    }


@router.get("/{category}/stats", summary="获取日志级别统计")
async def get_log_stats(category: str):
    """获取指定分类日志的级别统计"""
    if category not in LOG_CATEGORIES.values():
        valid = ", ".join(sorted(LOG_CATEGORIES.values()))
        raise HTTPException(
            status_code=404,
            detail=f"Invalid category '{category}'. Valid: {valid}",
        )

    logger = _get_logger_instance()
    log_dir = logger.get_log_dir()
    filepath = os.path.join(log_dir, f"{category}.log")

    if not os.path.exists(filepath):
        return {"category": category, "stats": {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}}

    stats = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                entry = _parse_log_line(line)
                if entry and entry.get("level"):
                    lv = entry["level"].upper()
                    if lv in stats:
                        stats[lv] += 1
    except OSError:
        pass

    return {"category": category, "stats": stats}


def _tail_file(f, max_lines: int = 500) -> List[str]:
    """高效读取文件尾部（类似 tail -n）"""
    try:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
    except OSError:
        return f.readlines()

    if file_size == 0:
        return []

    # 从文件末尾向前读取
    chunk_size = min(4096, file_size)
    buffer = []
    pos = file_size
    lines_found = 0

    while pos > 0 and lines_found < max_lines:
        read_size = min(chunk_size, pos)
        pos -= read_size
        f.seek(pos)
        chunk = f.read(read_size)

        # 分行处理
        chunk_lines = chunk.splitlines(True)
        buffer = chunk_lines + buffer
        lines_found = len([l for l in buffer if l.endswith('\n') or l == buffer[-1]])

        if lines_found >= max_lines:
            break

    # 仅保留最后 max_lines 行
    content = "".join(buffer)
    lines = content.splitlines()
    return lines[-max_lines:]
