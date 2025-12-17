import unittest
import os
import sys
import asyncio
from typing import List, Dict

# 添加项目根目录到 sys.path，确保能导入模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, project_root)

from KairoCore.example.your_project_name.dao.user_sqlite import UserSqliteDao
from KairoCore.db_tools.kc_sqlite import AsyncSqliteSession

class TestUserSqliteDao(unittest.TestCase):

    def setUp(self):
        # 每个测试前清理环境（可选）
        pass

    def tearDown(self):
        # 每个测试后清理环境（可选）
        pass

    def async_run(self, coro):
        return asyncio.run(coro)

    def test_crud_flow(self):
        """
        测试完整的 CRUD 流程
        """
        async def _test():
            # 1. Add
            users = [
                {"name": "Alice", "phone": "13800000001", "location": "Beijing", "sex": "F", "birthday": "1990-01-01"},
                {"name": "Bob", "phone": "13800000002", "location": "Shanghai", "sex": "M", "birthday": "1991-02-02"},
                {"name": "Charlie", "phone": "13800000003", "location": "Guangzhou", "sex": "M", "birthday": "1992-03-03"},
            ]
            added_count = await UserSqliteDao.add(users)
            self.assertEqual(added_count, 3, "应该成功添加 3 个用户")

            # 2. Query (Pagination)
            results, total = await UserSqliteDao.query_by_pagination({"name": "Alice"}, limit=10, offset=1)
            self.assertGreaterEqual(total, 1, "应该至少查到一个叫 Alice 的用户")
            alice_id = results[0]['id']
            self.assertEqual(results[0]['name'], "Alice")

            # 3. Update
            update_data = [{"id": alice_id, "location": "Shenzhen"}]
            updated_count = await UserSqliteDao.update(update_data)
            self.assertEqual(updated_count, 1, "应该成功更新 1 个用户")
            
            # 验证更新
            results_updated, _ = await UserSqliteDao.query_info_options({"id": alice_id})
            self.assertEqual(results_updated[0]['location'], "Shenzhen", "Alice 的地址应该变为 Shenzhen")

            # 4. Soft Delete
            deleted_count = await UserSqliteDao.delete([alice_id], is_hard=False)
            self.assertEqual(deleted_count, 1, "应该成功软删除 1 个用户")
            
            # 验证软删除 (query_by_pagination 默认不带 is_del=0 过滤，除非 SqlTool 处理了，
            # 但在这里我们手动检查数据库状态)
            results_del, _ = await UserSqliteDao.query_info_options({"id": alice_id})
            self.assertEqual(results_del[0]['is_del'], 1, "Alice 的 is_del 应该为 1")

            # 5. Hard Delete
            bob_results, _ = await UserSqliteDao.query_info_options({"name": "Bob"})
            if bob_results:
                bob_id = bob_results[0]['id']
                hard_del_count = await UserSqliteDao.delete([bob_id], is_hard=True)
                self.assertEqual(hard_del_count, 1, "应该成功硬删除 Bob")
                
                # 验证硬删除
                bob_check, _ = await UserSqliteDao.query_info_options({"id": bob_id})
                self.assertEqual(len(bob_check), 0, "Bob 应该被彻底删除")

        self.async_run(_test())

if __name__ == '__main__':
    unittest.main()
