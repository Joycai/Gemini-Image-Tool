import os
import sqlite3
import sys
import unittest

# 将项目根目录添加到 Python 路径中，以便能够导入 database 模块
# 这对于在 tests/ 目录下直接运行测试是必需的
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db # pylint: disable=wrong-import-position

class TestDatabase(unittest.TestCase):

    TEST_DB_FILE = "test_app_data.db"

    def setUp(self):
        """在每个测试方法运行前执行"""
        # 强制 database 模块使用测试数据库文件
        db.DB_FILE = self.TEST_DB_FILE
        # 确保每次测试都在一个干净的环境中进行
        if os.path.exists(self.TEST_DB_FILE):
            os.remove(self.TEST_DB_FILE)
        # 初始化新的测试数据库
        db.init_db()

    def tearDown(self):
        """在每个测试方法运行后执行"""
        # 清理测试数据库文件
        if os.path.exists(self.TEST_DB_FILE):
            os.remove(self.TEST_DB_FILE)

    def test_init_db(self):
        """测试数据库表是否被成功创建"""
        conn = sqlite3.connect(self.TEST_DB_FILE)
        c = conn.cursor()
        # 检查 settings 表
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
        self.assertIsNotNone(c.fetchone(), "The 'settings' table should be created.")
        # 检查 prompts 表
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prompts'")
        self.assertIsNotNone(c.fetchone(), "The 'prompts' table should be created.")
        conn.close()

    def test_save_and_get_setting(self):
        """测试保存和获取配置项"""
        # 测试保存新值
        db.save_setting("api_key", "test_key_123")
        self.assertEqual(db.get_setting("api_key"), "test_key_123")

        # 测试更新现有值
        db.save_setting("api_key", "updated_key_456")
        self.assertEqual(db.get_setting("api_key"), "updated_key_456")

        # 测试获取不存在的键，应返回默认值
        self.assertEqual(db.get_setting("non_existent_key", "default_value"), "default_value")
        self.assertEqual(db.get_setting("another_non_existent_key"), "", "Default should be an empty string if not provided.")

    def test_get_all_settings(self):
        """测试获取所有配置项"""
        # 测试默认值
        settings = db.get_all_settings()
        self.assertEqual(settings["api_key"], "")
        self.assertEqual(settings["save_path"], "outputs")
        self.assertEqual(settings["language"], "zh")

        # 测试设置值后
        db.save_setting("api_key", "my_api_key")
        db.save_setting("last_dir", "/my/test/dir")
        settings = db.get_all_settings()
        self.assertEqual(settings["api_key"], "my_api_key")
        self.assertEqual(settings["last_dir"], "/my/test/dir")

    def test_save_and_get_prompt(self):
        """测试保存和获取 Prompt"""
        db.save_prompt("Test Title", "This is the content.")
        content = db.get_prompt_content("Test Title")
        self.assertEqual(content, "This is the content.")

        # 测试获取不存在的 Prompt
        non_existent_content = db.get_prompt_content("Non Existent Title")
        self.assertEqual(non_existent_content, "")

    def test_delete_prompt(self):
        """测试删除 Prompt"""
        title = "Prompt to be deleted"
        content = "Some content"
        db.save_prompt(title, content)
        self.assertEqual(db.get_prompt_content(title), content, "Prompt should exist before deletion.")

        # 执行删除
        db.delete_prompt(title)
        self.assertEqual(db.get_prompt_content(title), "", "Prompt should not exist after deletion.")

    def test_get_all_prompt_titles(self):
        """测试获取所有 Prompt 标题"""
        # 初始状态下，应该只有一个默认的 "---"
        self.assertEqual(db.get_all_prompt_titles(), ["---"])

        # 添加几个 prompt
        prompts = {"B Title": "Content B", "A Title": "Content A", "C Title": "Content C"}
        for title, content in prompts.items():
            db.save_prompt(title, content)

        # 标题应该按字母顺序排序，并且包含默认的 "---"
        expected_titles = ["---", "A Title", "B Title", "C Title"]
        self.assertEqual(db.get_all_prompt_titles(), expected_titles)

        # 删除一个 prompt 后再检查
        db.delete_prompt("B Title")
        expected_titles_after_delete = ["---", "A Title", "C Title"]
        self.assertEqual(db.get_all_prompt_titles(), expected_titles_after_delete)

if __name__ == '__main__':
    unittest.main()
