"""SQLite 数据库层（MVP 可选缓存）

提供简单的缓存功能：
- 缓存最近解析的 NOTAM 结果
- 基于 NOTAM 文本哈希的键值存储
- 自动过期清理

注意：MVP 阶段为可选功能，通过配置 cache_enabled 控制
"""
import json
import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from .config import get_settings

settings = get_settings()


class NotamCache:
    """NOTAM 解析结果缓存"""

    def __init__(self, db_path: Optional[str] = None):
        """初始化缓存

        Args:
            db_path: SQLite 数据库路径，默认使用 .notam_cache.db
        """
        if db_path:
            self.db_path = db_path
        elif settings.database_url:
            # 支持 sqlite:/// 前缀
            self.db_path = settings.database_url.replace("sqlite:///", "")
        else:
            self.db_path = ".notam_cache.db"

        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    notam_text TEXT NOT NULL,
                    parse_result TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_key ON cache(cache_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)"
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _compute_key(self, notam_text: str) -> str:
        """计算 NOTAM 文本的缓存键"""
        return hashlib.sha256(notam_text.encode()).hexdigest()

    def _cleanup_expired(self):
        """清理过期缓存"""
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM cache WHERE expires_at < ?",
                (datetime.now().isoformat(),)
            )
            conn.commit()

    def get(self, notam_text: str) -> Optional[Dict[str, Any]]:
        """获取缓存的解析结果

        Args:
            notam_text: NOTAM 原始文本

        Returns:
            解析结果字典，如果不存在或已过期则返回 None
        """
        if not settings.cache_enabled:
            return None

        cache_key = self._compute_key(notam_text)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT parse_result, expires_at FROM cache WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # 检查是否过期
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at < datetime.now():
                self.delete(notam_text)
                return None

            # 清理过期缓存（后台操作）
            self._cleanup_expired()

            return json.loads(row["parse_result"])

    def set(
        self,
        notam_text: str,
        parse_result: Dict[str, Any],
        ttl: Optional[int] = None
    ):
        """设置缓存

        Args:
            notam_text: NOTAM 原始文本
            parse_result: 解析结果字典
            ttl: 缓存存活时间（秒），默认使用配置的 cache_ttl
        """
        if not settings.cache_enabled:
            return

        cache_key = self._compute_key(notam_text)
        ttl = ttl or settings.cache_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache
                (cache_key, notam_text, parse_result, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    cache_key,
                    notam_text,
                    json.dumps(parse_result),
                    expires_at.isoformat()
                )
            )
            conn.commit()

    def delete(self, notam_text: str) -> bool:
        """删除缓存

        Args:
            notam_text: NOTAM 原始文本

        Returns:
            是否删除成功
        """
        cache_key = self._compute_key(notam_text)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE cache_key = ?",
                (cache_key,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def clear(self):
        """清空所有缓存"""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含缓存数量、大小等信息的字典
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count, MIN(expires_at) as min_expires, MAX(expires_at) as max_expires FROM cache"
            )
            row = cursor.fetchone()

            # 计算数据库文件大小
            db_size = 0
            if Path(self.db_path).exists():
                db_size = Path(self.db_path).stat().st_size

            return {
                "count": row["count"] if row else 0,
                "oldest_entry": row["min_expires"] if row else None,
                "newest_entry": row["max_expires"] if row else None,
                "db_size_bytes": db_size
            }


# 全局缓存实例
cache: Optional[NotamCache] = None


def get_cache() -> NotamCache:
    """获取缓存实例"""
    global cache
    if cache is None:
        cache = NotamCache()
    return cache


def init_cache():
    """初始化缓存（应用启动时调用）"""
    global cache
    cache = NotamCache()
    return cache
