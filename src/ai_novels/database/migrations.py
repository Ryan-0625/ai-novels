"""
数据库迁移系统

提供版本化的数据库schema管理
支持升级、回滚、状态检查等功能
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import asyncio

from .connection_pool import ConnectionPool
from ..core.exceptions import DatabaseError, ErrorCode
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MigrationStatus(Enum):
    """迁移状态"""
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Migration:
    """迁移定义"""
    id: str                          # 迁移ID (如: 001_init)
    version: int                     # 版本号
    name: str                        # 迁移名称
    description: str                 # 描述
    created_at: datetime             # 创建时间
    checksum: str                    # 校验和
    
    # 迁移操作
    upgrade_sql: str                 # 升级SQL
    downgrade_sql: Optional[str]    # 降级SQL
    
    # Python操作(可选)
    upgrade_func: Optional[Callable] = None
    downgrade_func: Optional[Callable] = None


@dataclass
class MigrationRecord:
    """迁移记录"""
    id: str
    version: int
    name: str
    applied_at: datetime
    execution_time_ms: int
    checksum: str
    status: MigrationStatus
    error_message: Optional[str] = None


class MigrationManager:
    """
    迁移管理器
    
    管理数据库schema的版本化变更
    """
    
    MIGRATIONS_TABLE = "_migrations"
    
    def __init__(
        self,
        pool: ConnectionPool,
        migrations_dir: str = "migrations"
    ):
        self.pool = pool
        self.migrations_dir = Path(migrations_dir)
        self._migrations: Dict[str, Migration] = {}
        self._history: List[MigrationRecord] = []
    
    async def initialize(self):
        """初始化迁移系统"""
        await self._create_migrations_table()
        await self._load_history()
        logger.info("Migration system initialized")
    
    async def _create_migrations_table(self):
        """创建迁移记录表"""
        sql = f"""
        CREATE TABLE IF NOT EXISTS {self.MIGRATIONS_TABLE} (
            id TEXT PRIMARY KEY,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            execution_time_ms INTEGER,
            checksum TEXT NOT NULL,
            status TEXT DEFAULT '{MigrationStatus.PENDING.value}',
            error_message TEXT
        )
        """
        async with self.pool.acquire() as conn:
            await conn.execute(sql)
    
    async def _load_history(self):
        """加载迁移历史"""
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM {self.MIGRATIONS_TABLE} ORDER BY version"
            )
            rows = await cursor.fetchall()
            
            self._history = []
            for row in rows:
                self._history.append(MigrationRecord(
                    id=row[0],
                    version=row[1],
                    name=row[2],
                    applied_at=datetime.fromisoformat(row[3]),
                    execution_time_ms=row[4],
                    checksum=row[5],
                    status=MigrationStatus(row[6]),
                    error_message=row[7]
                ))
    
    def register(self, migration: Migration):
        """注册迁移"""
        self._migrations[migration.id] = migration
        logger.info(f"Registered migration: {migration.id}")
    
    def create_migration(
        self,
        name: str,
        description: str,
        upgrade_sql: str,
        downgrade_sql: Optional[str] = None
    ) -> Migration:
        """
        创建新迁移
        
        自动生成版本号和ID
        """
        # 计算下一个版本号
        existing_versions = [m.version for m in self._migrations.values()]
        next_version = max(existing_versions, default=0) + 1
        
        # 生成ID
        migration_id = f"{next_version:03d}_{name.lower().replace(' ', '_')}"
        
        # 计算校验和
        content = f"{upgrade_sql}{downgrade_sql or ''}"
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        migration = Migration(
            id=migration_id,
            version=next_version,
            name=name,
            description=description,
            created_at=datetime.now(),
            checksum=checksum,
            upgrade_sql=upgrade_sql,
            downgrade_sql=downgrade_sql
        )
        
        self.register(migration)
        return migration
    
    async def migrate(self, target_version: Optional[int] = None) -> List[str]:
        """
        执行迁移
        
        Args:
            target_version: 目标版本(默认最新)
        
        Returns:
            已应用的迁移ID列表
        """
        applied = []
        
        # 获取当前版本
        current_version = await self.get_current_version()
        
        # 确定目标版本
        if target_version is None:
            target_version = max(
                (m.version for m in self._migrations.values()),
                default=0
            )
        
        if target_version == current_version:
            logger.info("Database is up to date")
            return applied
        
        if target_version > current_version:
            # 升级
            migrations_to_apply = sorted(
                [m for m in self._migrations.values() 
                 if m.version > current_version and m.version <= target_version],
                key=lambda m: m.version
            )
            
            for migration in migrations_to_apply:
                try:
                    await self._apply_migration(migration)
                    applied.append(migration.id)
                except Exception as e:
                    logger.error(f"Migration {migration.id} failed: {e}")
                    raise DatabaseError(
                        ErrorCode.MIGRATION_FAILED,
                        f"Migration {migration.id} failed: {e}"
                    )
        else:
            # 降级
            migrations_to_rollback = sorted(
                [m for m in self._migrations.values()
                 if m.version > target_version and m.version <= current_version],
                key=lambda m: m.version,
                reverse=True
            )
            
            for migration in migrations_to_rollback:
                try:
                    await self._rollback_migration(migration)
                    applied.append(migration.id)
                except Exception as e:
                    logger.error(f"Rollback {migration.id} failed: {e}")
                    raise DatabaseError(
                        ErrorCode.MIGRATION_FAILED,
                        f"Rollback {migration.id} failed: {e}"
                    )
        
        return applied
    
    async def _apply_migration(self, migration: Migration):
        """应用单个迁移"""
        logger.info(f"Applying migration: {migration.id}")
        
        start_time = datetime.now()
        
        try:
            async with self.pool.acquire() as conn:
                # 执行升级SQL
                if migration.upgrade_sql:
                    await conn.executescript(migration.upgrade_sql)
                
                # 执行Python函数
                if migration.upgrade_func:
                    await migration.upgrade_func(conn)
                
                # 记录迁移
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                
                await conn.execute(
                    f"""INSERT OR REPLACE INTO {self.MIGRATIONS_TABLE} 
                        (id, version, name, applied_at, execution_time_ms, checksum, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        migration.id,
                        migration.version,
                        migration.name,
                        datetime.now().isoformat(),
                        execution_time,
                        migration.checksum,
                        MigrationStatus.APPLIED.value
                    )
                )
            
            logger.info(f"Migration {migration.id} applied successfully")
            
        except Exception as e:
            # 记录失败
            async with self.pool.acquire() as conn:
                await conn.execute(
                    f"""INSERT OR REPLACE INTO {self.MIGRATIONS_TABLE}
                        (id, version, name, applied_at, checksum, status, error_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        migration.id,
                        migration.version,
                        migration.name,
                        datetime.now().isoformat(),
                        migration.checksum,
                        MigrationStatus.FAILED.value,
                        str(e)
                    )
                )
            raise
    
    async def _rollback_migration(self, migration: Migration):
        """回滚单个迁移"""
        logger.info(f"Rolling back migration: {migration.id}")
        
        if not migration.downgrade_sql and not migration.downgrade_func:
            raise DatabaseError(
                ErrorCode.MIGRATION_NO_ROLLBACK,
                f"Migration {migration.id} has no rollback"
            )
        
        async with self.pool.acquire() as conn:
            # 执行降级SQL
            if migration.downgrade_sql:
                await conn.executescript(migration.downgrade_sql)
            
            # 执行Python函数
            if migration.downgrade_func:
                await migration.downgrade_func(conn)
            
            # 更新状态
            await conn.execute(
                f"UPDATE {self.MIGRATIONS_TABLE} SET status = ? WHERE id = ?",
                (MigrationStatus.ROLLED_BACK.value, migration.id)
            )
        
        logger.info(f"Migration {migration.id} rolled back successfully")
    
    async def get_current_version(self) -> int:
        """获取当前版本"""
        async with self.pool.acquire() as conn:
            cursor = await conn.execute(
                f"""SELECT MAX(version) FROM {self.MIGRATIONS_TABLE}
                    WHERE status = ?
                """,
                (MigrationStatus.APPLIED.value,)
            )
            row = await cursor.fetchone()
            return row[0] or 0
    
    async def get_status(self) -> Dict[str, Any]:
        """获取迁移状态"""
        current_version = await self.get_current_version()
        
        pending = []
        applied = []
        
        for migration in sorted(self._migrations.values(), key=lambda m: m.version):
            record = next((r for r in self._history if r.id == migration.id), None)
            
            if record and record.status == MigrationStatus.APPLIED:
                applied.append({
                    "id": migration.id,
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": record.applied_at.isoformat()
                })
            else:
                pending.append({
                    "id": migration.id,
                    "version": migration.version,
                    "name": migration.name
                })
        
        return {
            "current_version": current_version,
            "latest_version": max(
                (m.version for m in self._migrations.values()),
                default=0
            ),
            "pending_count": len(pending),
            "applied_count": len(applied),
            "pending": pending,
            "applied": applied
        }
    
    async def verify(self) -> List[Dict[str, Any]]:
        """验证迁移完整性"""
        issues = []
        
        for record in self._history:
            if record.status != MigrationStatus.APPLIED:
                continue
            
            migration = self._migrations.get(record.id)
            if not migration:
                issues.append({
                    "type": "missing_migration",
                    "id": record.id,
                    "message": f"Migration {record.id} is applied but not registered"
                })
                continue
            
            if migration.checksum != record.checksum:
                issues.append({
                    "type": "checksum_mismatch",
                    "id": record.id,
                    "message": f"Migration {record.id} has been modified"
                })
        
        return issues
    
    def save_to_files(self):
        """将迁移保存到文件"""
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        
        for migration in self._migrations.values():
            file_path = self.migrations_dir / f"{migration.id}.sql"
            
            content = f"""-- Migration: {migration.id}
-- Version: {migration.version}
-- Name: {migration.name}
-- Description: {migration.description}
-- Created: {migration.created_at.isoformat()}
-- Checksum: {migration.checksum}

-- Upgrade
{migration.upgrade_sql}

-- Downgrade
{migration.downgrade_sql or '-- No downgrade available'}
"""
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        logger.info(f"Saved {len(self._migrations)} migrations to {self.migrations_dir}")
    
    def load_from_files(self):
        """从文件加载迁移"""
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return
        
        pattern = re.compile(
            r'-- Migration: (?P<id>\S+)\n'
            r'-- Version: (?P<version>\d+)\n'
            r'-- Name: (?P<name>.+)\n'
            r'-- Description: (?P<description>.+)\n'
            r'-- Created: (?P<created>.+)\n'
            r'-- Checksum: (?P<checksum>\S+)\n+\n'
            r'-- Upgrade\n(?P<upgrade>.+?)\n+\n'
            r'-- Downgrade\n(?P<downgrade>.*)',
            re.DOTALL
        )
        
        for file_path in sorted(self.migrations_dir.glob("*.sql")):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            match = pattern.match(content)
            if match:
                data = match.groupdict()
                migration = Migration(
                    id=data['id'],
                    version=int(data['version']),
                    name=data['name'],
                    description=data['description'],
                    created_at=datetime.fromisoformat(data['created']),
                    checksum=data['checksum'],
                    upgrade_sql=data['upgrade'].strip(),
                    downgrade_sql=data['downgrade'].strip() 
                        if data['downgrade'].strip() != '-- No downgrade available' 
                        else None
                )
                self.register(migration)
        
        logger.info(f"Loaded {len(self._migrations)} migrations from {self.migrations_dir}")


# 便捷装饰器
def upgrade(migration_id: str):
    """标记升级函数的装饰器"""
    def decorator(func: Callable):
        func._migration_id = migration_id
        func._is_upgrade = True
        return func
    return decorator


def downgrade(migration_id: str):
    """标记降级函数的装饰器"""
    def decorator(func: Callable):
        func._migration_id = migration_id
        func._is_downgrade = True
        return func
    return decorator


# 常用迁移模板
class MigrationTemplates:
    """迁移模板"""
    
    @staticmethod
    def create_table(
        table_name: str,
        columns: Dict[str, str],
        primary_key: str = "id"
    ) -> str:
        """生成创建表的SQL"""
        col_defs = []
        for name, def_str in columns.items():
            col_defs.append(f"    {name} {def_str}")
        
        return f"""CREATE TABLE IF NOT EXISTS {table_name} (
{','.join(col_defs)}
);"""
    
    @staticmethod
    def drop_table(table_name: str) -> str:
        """生成删除表的SQL"""
        return f"DROP TABLE IF EXISTS {table_name};"
    
    @staticmethod
    def add_column(table_name: str, column_name: str, column_def: str) -> str:
        """生成添加列的SQL"""
        return f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};"
    
    @staticmethod
    def create_index(
        table_name: str,
        index_name: str,
        columns: List[str],
        unique: bool = False
    ) -> str:
        """生成创建索引的SQL"""
        unique_str = "UNIQUE " if unique else ""
        cols = ', '.join(columns)
        return f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name}({cols});"
    
    @staticmethod
    def drop_index(index_name: str) -> str:
        """生成删除索引的SQL"""
        return f"DROP INDEX IF EXISTS {index_name};"
