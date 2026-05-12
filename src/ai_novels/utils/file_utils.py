"""
文件操作工具函数

@file: utils/file_utils.py
@date: 2026-03-13
@version: 1.0.0
@description: 文件和目录操作相关函数
"""

import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid


def sanitize_filename(filename: str) -> str:
    """
    清理文件名中的非法字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    # 移除或替换非法字符
    invalid_chars = '<>:"/\\|?*'
    cleaned = filename

    for char in invalid_chars:
        cleaned = cleaned.replace(char, '_')

    # 移除控制字符
    cleaned = ''.join(c for c in cleaned if ord(c) < 128 and c != '\x00')

    # 限制长度
    max_length = 255
    if len(cleaned) > max_length:
        name_part = cleaned[:max_length - 10]
        ext_part = cleaned[max_length - 10:]
        cleaned = f"{name_part}_{uuid.uuid4().hex[:8]}{ext_part}"

    return cleaned


def ensure_directory(path: str) -> str:
    """
    确保目录存在，不存在则创建

    Args:
        path: 目录路径

    Returns:
        确保后的路径
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def read_file_safe(filepath: str, encoding: str = 'utf-8') -> str:
    """
    安全读取文件

    Args:
        filepath: 文件路径
        encoding: 编码格式

    Returns:
        文件内容
    """
    try:
        with open(filepath, 'r', encoding=encoding) as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except PermissionError:
        return ""
    except Exception:
        return ""


def write_file_safe(filepath: str, content: str, encoding: str = 'utf-8') -> bool:
    """
    安全写入文件

    Args:
        filepath: 文件路径
        content: 写入内容
        encoding: 编码格式

    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        ensure_directory(os.path.dirname(filepath))

        with open(filepath, 'w', encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


def list_files_recursive(directory: str, pattern: str = '*') -> List[str]:
    """
    递归列出目录中的文件

    Args:
        directory: 目录路径
        pattern: 通配符模式

    Returns:
        文件路径列表
    """
    files = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            if pattern == '*' or filename.endswith(pattern.lstrip('*')):
                files.append(os.path.join(root, filename))

    return files


def get_file_info(filepath: str) -> Dict[str, Any]:
    """
    获取文件信息

    Args:
        filepath: 文件路径

    Returns:
        文件信息字典
    """
    try:
        stat = os.stat(filepath)
        return {
            'path': filepath,
            'size': stat.st_size,
            'size_kb': stat.st_size / 1024,
            'size_mb': stat.st_size / (1024 * 1024),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_file': os.path.isfile(filepath),
            'is_dir': os.path.isdir(filepath)
        }
    except FileNotFoundError:
        return {
            'path': filepath,
            'error': 'File not found'
        }


def delete_file(filepath: str) -> bool:
    """
    删除文件

    Args:
        filepath: 文件路径

    Returns:
        是否成功
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception:
        return False


def copy_file(src: str, dst: str) -> bool:
    """
    复制文件

    Args:
        src: 源文件路径
        dst: 目标文件路径

    Returns:
        是否成功
    """
    try:
        ensure_directory(os.path.dirname(dst))
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def move_file(src: str, dst: str) -> bool:
    """
    移动文件

    Args:
        src: 源文件路径
        dst: 目标文件路径

    Returns:
        是否成功
    """
    try:
        ensure_directory(os.path.dirname(dst))
        shutil.move(src, dst)
        return True
    except Exception:
        return False


def read_json_file(filepath: str) -> Dict[str, Any]:
    """
    读取JSON文件

    Args:
        filepath: JSON文件路径

    Returns:
        JSON数据
    """
    content = read_file_safe(filepath)
    if not content:
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def write_json_file(filepath: str, data: Dict[str, Any], indent: int = 2) -> bool:
    """
    写入JSON文件

    Args:
        filepath: JSON文件路径
        data: JSON数据
        indent: 缩进空格数

    Returns:
        是否成功
    """
    try:
        content = json.dumps(data, ensure_ascii=False, indent=indent)
        return write_file_safe(filepath, content, encoding='utf-8')
    except Exception:
        return False


def get_file_extension(filepath: str) -> str:
    """
    获取文件扩展名

    Args:
        filepath: 文件路径

    Returns:
        扩展名（包含点号，如 '.txt'）
    """
    return os.path.splitext(filepath)[1]


def change_file_extension(filepath: str, new_ext: str) -> str:
    """
    更改文件扩展名

    Args:
        filepath: 文件路径
        new_ext: 新扩展名

    Returns:
        新文件路径
    """
    name, _ = os.path.splitext(filepath)
    return f"{name}.{new_ext.lstrip('.')}"


def create_temp_directory(prefix: str = 'tmp_') -> str:
    """
    创建临时目录

    Args:
        prefix: 目录名前缀

    Returns:
        临时目录路径
    """
    temp_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..',
        '_temp',
        f"{prefix}{uuid.uuid4().hex[:8]}"
    )
    ensure_directory(temp_dir)
    return temp_dir


def count_files_in_directory(directory: str, pattern: str = '*') -> int:
    """
    统计目录中的文件数

    Args:
        directory: 目录路径
        pattern: 文件模式

    Returns:
        文件数量
    """
    return len(list_files_recursive(directory, pattern))


def get_directory_size(directory: str) -> int:
    """
    获取目录大小（字节）

    Args:
        directory: 目录路径

    Returns:
        目录大小（字节）
    """
    total_size = 0

    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                total_size += os.path.getsize(filepath)
            except OSError:
                pass

    return total_size


def file_exists(filepath: str) -> bool:
    """
    检查文件是否存在

    Args:
        filepath: 文件路径

    Returns:
        是否存在
    """
    return os.path.isfile(filepath)


def directory_exists(path: str) -> bool:
    """
    检查目录是否存在

    Args:
        path: 目录路径

    Returns:
        是否存在
    """
    return os.path.isdir(path)


def get_relative_path(path: str, base: str) -> str:
    """
    获取相对路径

    Args:
        path: 目标路径
        base: 基准路径

    Returns:
        相对路径
    """
    try:
        return os.path.relpath(path, base)
    except ValueError:
        # Windows和Linux混合路径情况
        return path


def join_paths(*paths: str) -> str:
    """
    连接路径

    Args:
        *paths: 路径片段

    Returns:
        连接后的路径
    """
    return os.path.join(*paths)


def get_parent_directory(path: str) -> str:
    """
    获取父目录

    Args:
        path: 文件或目录路径

    Returns:
        父目录路径
    """
    return os.path.dirname(path)


def create_symlink(target: str, link_name: str) -> bool:
    """
    创建符号链接

    Args:
        target: 目标路径
        link_name: 链接名称

    Returns:
        是否成功
    """
    try:
        # Windows需要管理员权限，使用 Junction
        if os.name == 'nt':
            os.system(f'mklink /J "{link_name}" "{target}"')
        else:
            os.symlink(target, link_name)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # 示例用法
    print("File utils module loaded successfully!")

    # 测试目录创建
    temp_dir = create_temp_directory("test_")
    print(f"Temp directory: {temp_dir}")

    # 清理
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
