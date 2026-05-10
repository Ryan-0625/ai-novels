"""
服务层基类

封装业务逻辑，隔离API层与数据访问层。
所有服务通过 Repository 操作数据，保持事务边界清晰。

@file: services/base.py
@date: 2026-04-29
"""

from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from deepnovel.repositories.base import BaseRepository

RepoT = TypeVar("RepoT", bound=BaseRepository)


class BaseService(Generic[RepoT]):
    """服务层基类

    封装通用的业务逻辑模式：
    - 事务管理（通过传入的session控制）
    - 数据验证
    - 业务规则检查
    """

    def __init__(self, repository: RepoT):
        self._repo = repository
