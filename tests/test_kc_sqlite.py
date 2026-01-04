import os
import unittest
import tempfile
import asyncio
from typing import Dict, List

from KairoCore.db_tools.kc_sqlite import SqliteSession, AsyncSqliteSession, SqliteConfig


class TestKcSqlite(unittest.TestCase):
    """SQLite 工具框架单元测试"""

    @classmethod
    def setUpClass(cls):
        """测试初始化：创建临时数据库与基础表结构"""
        cls.tmp_db = tempfile.NamedTemporaryFile(prefix="kc_sqlite_test_", suffix=".db", delete=False)
        cls.tmp_db_path = cls.tmp_db.name
        cls.tmp_db.close()
        cls.config = SqliteConfig(db_path=cls.tmp_db_path, pool_size=2, cache_size=16, cache_ttl=60.0)

        schema = {
            "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL
            );
            """,
            "accounts": """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                balance INTEGER NOT NULL
            );
            """,
        }
        with SqliteSession(cls.config) as s:
            s.ensure_tables(schema)

    @classmethod
    def tearDownClass(cls):
        """测试结束：删除临时数据库文件"""
        try:
            os.unlink(cls.tmp_db_path)
        except Exception:
            pass

    def test_insert_and_fetch_one(self):
        """插入与单条查询"""
        with SqliteSession(self.config) as s:
            affected = s.insert("INSERT INTO users (name, age) VALUES (:name, :age)", {"name": "Alice", "age": 30})
            self.assertGreaterEqual(affected, 1)
            row = s.fetch_one("SELECT * FROM users WHERE name=:name", {"name": "Alice"})
            self.assertIsNotNone(row)
            self.assertEqual(row["age"], 30)

    def test_update_and_delete(self):
        """更新与删除"""
        with SqliteSession(self.config) as s:
            s.insert("INSERT INTO users (name, age) VALUES (:name, :age)", {"name": "Bob", "age": 22})
            upd = s.update("UPDATE users SET age=:age WHERE name=:name", {"age": 23, "name": "Bob"})
            self.assertGreaterEqual(upd, 1)
            row = s.fetch_one("SELECT * FROM users WHERE name=:name", {"name": "Bob"})
            self.assertEqual(row["age"], 23)
            dele = s.delete("DELETE FROM users WHERE name=:name", {"name": "Bob"})
            self.assertGreaterEqual(dele, 1)
            row2 = s.fetch_one("SELECT * FROM users WHERE name=:name", {"name": "Bob"})
            self.assertIsNone(row2)

    def test_batch_insert_and_in_query(self):
        """批量插入与 IN 查询"""
        data = [{"name": f"user_{i}", "age": i} for i in range(5)]
        with SqliteSession(self.config) as s:
            n = s.insert_many("INSERT INTO users (name, age) VALUES (:name, :age)", data)
            self.assertGreaterEqual(n, 1)
            ids = [r["id"] for r in s.fetch_all("SELECT id FROM users WHERE name LIKE :like", {"like": "user_%"})]
            res = s.fetch_all("SELECT * FROM users WHERE id IN :ids", {"ids": ids})
            self.assertEqual(len(res), len(ids))

    def test_pagination(self):
        """分页查询"""
        with SqliteSession(self.config) as s:
            # 保证有至少 6 条数据
            for i in range(6):
                s.insert("INSERT INTO users (name, age) VALUES (:name, :age)", {"name": f"page_{i}", "age": 18 + i})
            page1, total = s.query_with_pagination("SELECT * FROM users WHERE name LIKE :like ORDER BY id", {"like": "page_%"}, offset=1, limit=3)
            page2, _ = s.query_with_pagination("SELECT * FROM users WHERE name LIKE :like ORDER BY id", {"like": "page_%"}, offset=2, limit=3)
            self.assertEqual(len(page1), 3)
            self.assertEqual(len(page2), 3)
            self.assertGreaterEqual(total, 6)
            # 不重叠检查
            ids1 = {r["id"] for r in page1}
            ids2 = {r["id"] for r in page2}
            self.assertTrue(ids1.isdisjoint(ids2))

    def test_transaction_rollback_on_exception(self):
        """异常触发事务回滚"""
        with SqliteSession(self.config) as s:
            s.insert("INSERT INTO accounts (balance) VALUES (:b)", {"b": 100})
        # 故意触发异常，期望回滚
        try:
            with SqliteSession(self.config) as s:
                s.update("UPDATE accounts SET balance=balance-:amt WHERE id=:id", {"amt": 50, "id": 1})
                # 引发异常
                raise RuntimeError("模拟异常")
        except RuntimeError:
            pass
        # 验证余额仍为 100（回滚成功）
        with SqliteSession(self.config) as s:
            row = s.fetch_one("SELECT balance FROM accounts WHERE id=:id", {"id": 1})
            self.assertEqual(row["balance"], 100)

    def test_async_session_basic(self):
        """异步会话基本操作"""
        async def run():
            async with AsyncSqliteSession(self.config) as s:
                await s.ensure_table("t_async", "CREATE TABLE IF NOT EXISTS t_async (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT NOT NULL);")
                n = await s.execute_one("INSERT INTO t_async (v) VALUES (:v)", {"v": "hello"})
                self.assertGreaterEqual(n, 1)
                one = await s.fetch_one("SELECT * FROM t_async WHERE v=:v", {"v": "hello"})
                self.assertIsNotNone(one)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
