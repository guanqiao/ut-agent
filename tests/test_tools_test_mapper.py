"""测试文件映射器测试"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from ut_agent.tools.test_mapper import (
    TestMapping,
    MethodTestMapping,
    TestFileMapper,
)
from ut_agent.tools.change_detector import MethodInfo


class TestTestMapping:
    """测试测试映射数据类"""
    
    def test_test_mapping_creation(self):
        """测试测试映射创建"""
        mapping = TestMapping(
            source_file="src/TestClass.java",
            test_file="src/test/java/TestClassTest.java",
            method_mappings={"testMethod": "testTestMethod"},
            last_generated=datetime.now(),
            source_hash="source_hash",
            test_hash="test_hash",
            has_manual_changes=False,
            manual_sections=[(10, 20), (30, 40)],
        )
        
        assert mapping.source_file == "src/TestClass.java"
        assert mapping.test_file == "src/test/java/TestClassTest.java"
        assert mapping.method_mappings == {"testMethod": "testTestMethod"}
        assert isinstance(mapping.last_generated, datetime)
        assert mapping.source_hash == "source_hash"
        assert mapping.test_hash == "test_hash"
        assert mapping.has_manual_changes is False
        assert mapping.manual_sections == [(10, 20), (30, 40)]
    
    def test_test_mapping_defaults(self):
        """测试测试映射默认值"""
        mapping = TestMapping(
            source_file="src/TestClass.java",
            test_file="src/test/java/TestClassTest.java",
        )
        
        assert mapping.method_mappings == {}
        assert isinstance(mapping.last_generated, datetime)
        assert mapping.source_hash == ""
        assert mapping.test_hash == ""
        assert mapping.has_manual_changes is False
        assert mapping.manual_sections == []


class TestMethodTestMapping:
    """测试方法测试映射数据类"""
    
    def test_method_test_mapping_creation(self):
        """测试方法测试映射创建"""
        mapping = MethodTestMapping(
            source_method="testMethod",
            test_method="testTestMethod",
            test_file="src/test/java/TestClassTest.java",
            line_start=10,
            line_end=20,
            is_auto_generated=True,
        )
        
        assert mapping.source_method == "testMethod"
        assert mapping.test_method == "testTestMethod"
        assert mapping.test_file == "src/test/java/TestClassTest.java"
        assert mapping.line_start == 10
        assert mapping.line_end == 20
        assert mapping.is_auto_generated is True
    
    def test_method_test_mapping_defaults(self):
        """测试方法测试映射默认值"""
        mapping = MethodTestMapping(
            source_method="testMethod",
            test_method="testTestMethod",
            test_file="src/test/java/TestClassTest.java",
            line_start=10,
            line_end=20,
        )
        
        assert mapping.is_auto_generated is True


class TestTestFileMapper:
    """测试测试文件映射器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
        
        # 创建必要的目录结构
        (self.project_path / "src" / "test" / "java").mkdir(parents=True, exist_ok=True)
        (self.project_path / ".ut-agent").mkdir(parents=True, exist_ok=True)
    
    def teardown_method(self):
        """清理测试环境"""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        mapper = TestFileMapper(str(self.project_path), "java")
        assert mapper.project_path == self.project_path
        assert mapper.project_type == "java"
        assert mapper.mappings == {}
        assert mapper.mapping_file == self.project_path / ".ut-agent" / "mappings.json"
    
    def test_load_mappings(self):
        """测试加载映射"""
        # 创建测试映射文件
        mapping_file = self.project_path / ".ut-agent" / "mappings.json"
        mapping_data = {
            "src/TestClass.java": {
                "source_file": "src/TestClass.java",
                "test_file": "src/test/java/TestClassTest.java",
                "method_mappings": {"testMethod": "testTestMethod"},
                "last_generated": "2024-01-01T00:00:00",
                "source_hash": "source_hash",
                "test_hash": "test_hash",
                "has_manual_changes": False,
                "manual_sections": [],
            }
        }
        
        with open(mapping_file, "w", encoding="utf-8") as f:
            json.dump(mapping_data, f)
        
        # 加载映射
        mapper = TestFileMapper(str(self.project_path), "java")
        assert "src/TestClass.java" in mapper.mappings
        assert mapper.mappings["src/TestClass.java"].test_file == "src/test/java/TestClassTest.java"
        assert mapper.mappings["src/TestClass.java"].method_mappings == {"testMethod": "testTestMethod"}
    
    def test_save_mappings(self):
        """测试保存映射"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 创建映射
        mapping = TestMapping(
            source_file="src/TestClass.java",
            test_file="src/test/java/TestClassTest.java",
            method_mappings={"testMethod": "testTestMethod"},
        )
        mapper.mappings["src/TestClass.java"] = mapping
        
        # 保存映射
        mapper._save_mappings()
        
        # 验证保存结果
        mapping_file = self.project_path / ".ut-agent" / "mappings.json"
        assert mapping_file.exists()
        
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "src/TestClass.java" in data
        assert data["src/TestClass.java"]["test_file"] == "src/test/java/TestClassTest.java"
        assert data["src/TestClass.java"]["method_mappings"] == {"testMethod": "testTestMethod"}
    
    def test_compute_hash(self):
        """测试计算哈希"""
        mapper = TestFileMapper(str(self.project_path), "java")
        content = "test content"
        hash_value = mapper._compute_hash(content)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 32  # MD5 哈希长度
    
    def test_infer_test_file_path_java(self):
        """测试推断 Java 测试文件路径"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 创建测试文件
        test_file = self.project_path / "src" / "test" / "java" / "TestClassTest.java"
        test_file.write_text("public class TestClassTest {}")
        
        # 推断测试文件路径
        test_file_path = mapper._infer_test_file_path("src/TestClass.java")
        assert test_file_path == "src/test/java/TestClassTest.java"
    
    def test_infer_test_file_path_typescript(self):
        """测试推断 TypeScript 测试文件路径"""
        mapper = TestFileMapper(str(self.project_path), "typescript")
        
        # 创建测试文件
        test_file = self.project_path / "src" / "TestClass.test.ts"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test('should test', () => {});")
        
        # 推断测试文件路径
        test_file_path = mapper._infer_test_file_path("src/TestClass.ts")
        assert test_file_path == "src/TestClass.test.ts"
    
    def test_extract_method_mappings_java(self):
        """测试提取 Java 方法映射"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        test_content = """
        public class TestClassTest {
            @Test
            public void testTestMethod() {
            }
        }
        """
        
        mappings = mapper._extract_method_mappings(test_content)
        assert "testMethod" in mappings
        assert mappings["testMethod"] == "testTestMethod"
    
    def test_extract_method_mappings_typescript(self):
        """测试提取 TypeScript 方法映射"""
        mapper = TestFileMapper(str(self.project_path), "typescript")
        
        test_content = """
        test('test method should work', () => {});
        """
        
        mappings = mapper._extract_method_mappings(test_content)
        assert "method" in mappings
        assert mappings["method"] == "test method should work"
    
    def test_infer_source_method(self):
        """测试推断源方法名"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 测试去掉 test 前缀
        assert mapper._infer_source_method("testTestMethod") == "testMethod"
        
        # 测试去掉 should 前缀
        assert mapper._infer_source_method("shouldTestMethod") == "testMethod"
    
    def test_extract_method_from_desc(self):
        """测试从描述中提取方法名"""
        mapper = TestFileMapper(str(self.project_path), "typescript")
        
        # 测试 "when method called" 模式
        assert mapper._extract_method_from_desc("when testMethod called") == "testMethod"
        
        # 测试 "method should" 模式
        assert mapper._extract_method_from_desc("testMethod should work") == "testMethod"
        
        # 测试 "should do method" 模式
        assert mapper._extract_method_from_desc("should test testMethod") == "testMethod"
        
        # 测试返回第一个单词
        assert mapper._extract_method_from_desc("testMethod") == "testMethod"
    
    def test_detect_manual_changes(self):
        """测试检测手工修改"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        test_content = """
        public class TestClassTest {
            // MANUAL
            @Test
            public void testTestMethod() {
            }
            // MANUAL
        }
        """
        
        has_manual, manual_sections = mapper._detect_manual_changes(test_content)
        assert has_manual is True
        assert len(manual_sections) > 0
    
    def test_create_mapping(self):
        """测试创建映射"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        source_content = "public class TestClass { public void testMethod() {} }"
        test_content = "public class TestClassTest { @Test public void testTestMethod() {} }"
        
        mapping = mapper.create_mapping(
            "src/TestClass.java",
            "src/test/java/TestClassTest.java",
            source_content,
            test_content,
        )
        
        assert mapping.source_file == "src/TestClass.java"
        assert mapping.test_file == "src/test/java/TestClassTest.java"
        assert "testMethod" in mapping.method_mappings
        assert mapping.method_mappings["testMethod"] == "testTestMethod"
        assert isinstance(mapping.last_generated, datetime)
        assert mapping.source_hash != ""
        assert mapping.test_hash != ""
    
    def test_get_affected_tests(self):
        """测试获取受影响的测试"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 创建映射
        mapping = TestMapping(
            source_file="src/TestClass.java",
            test_file="src/test/java/TestClassTest.java",
            method_mappings={"testMethod": "testTestMethod", "anotherMethod": "testAnotherMethod"},
        )
        mapper.mappings["src/TestClass.java"] = mapping
        
        # 获取受影响的测试
        affected_tests = mapper.get_affected_tests("src/TestClass.java", ["testMethod"])
        assert len(affected_tests) == 1
        assert "testTestMethod" in affected_tests
    
    def test_get_mapping_summary(self):
        """测试获取映射摘要"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 创建映射
        mapping1 = TestMapping(
            source_file="src/TestClass.java",
            test_file="src/test/java/TestClassTest.java",
            method_mappings={"testMethod": "testTestMethod"},
        )
        mapping2 = TestMapping(
            source_file="src/AnotherClass.java",
            test_file="src/test/java/AnotherClassTest.java",
            method_mappings={"anotherMethod": "testAnotherMethod"},
            has_manual_changes=True,
        )
        mapper.mappings["src/TestClass.java"] = mapping1
        mapper.mappings["src/AnotherClass.java"] = mapping2
        
        # 获取摘要
        summary = mapper.get_mapping_summary()
        assert summary["total_source_files"] == 2
        assert summary["with_manual_changes"] == 1
        assert summary["total_mapped_methods"] == 2
        assert isinstance(summary["last_updated"], datetime)
    
    def test_detect_manual_changes_no_markers(self):
        """测试检测无手工标记的修改"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        test_content = """
        public class TestClassTest {
            @Test
            public void testTestMethod() {
            }
        }
        """
        
        has_manual, manual_sections = mapper._detect_manual_changes(test_content)
        assert has_manual is False
        assert manual_sections == []
    
    def test_is_test_manually_modified(self):
        """测试检查测试方法是否被手工修改"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 带有手工标记的测试方法
        test_content_with_manual = """
        public class TestClassTest {
            // MANUAL
            @Test
            public void testTestMethod() {
            }
            // MANUAL
        }
        """
        
        # 不带手工标记的测试方法
        test_content_no_manual = """
        public class TestClassTest {
            @Test
            public void testTestMethod() {
            }
        }
        """
        
        assert mapper._is_test_manually_modified(test_content_with_manual, "testTestMethod") is True
        assert mapper._is_test_manually_modified(test_content_no_manual, "testTestMethod") is False
    
    def test_extract_test_method(self):
        """测试提取测试方法"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        test_content = """
        public class TestClassTest {
            @Test
            public void testTestMethod() {
                // test code
            }
        }
        """
        
        method_content = mapper._extract_test_method(test_content, "testTestMethod")
        assert method_content is not None
        assert "public void testTestMethod()" in method_content
        assert "// test code" in method_content
    
    def test_extract_test_method_not_found(self):
        """测试提取不存在的测试方法"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        test_content = """
        public class TestClassTest {
            @Test
            public void testTestMethod() {
            }
        }
        """
        
        method_content = mapper._extract_test_method(test_content, "nonExistentMethod")
        assert method_content is None
    
    def test_update_mapping(self):
        """测试更新映射"""
        mapper = TestFileMapper(str(self.project_path), "java")
        
        # 创建初始映射
        source_content = "public class TestClass { public void testMethod() {} }"
        test_content = "public class TestClassTest { @Test public void testTestMethod() {} }"
        
        # 创建测试文件
        test_file = self.project_path / "src" / "test" / "java" / "TestClassTest.java"
        test_file.write_text(test_content)
        
        # 创建映射
        mapper.create_mapping(
            "src/TestClass.java",
            "src/test/java/TestClassTest.java",
            source_content,
            test_content,
        )
        
        # 更新映射
        new_source_content = "public class TestClass { public void testMethod() {} public void newMethod() {} }"
        new_test_content = "public class TestClassTest { @Test public void testTestMethod() {} @Test public void testNewMethod() {} }"
        
        # 创建方法信息
        added_methods = [MethodInfo(name="newMethod", signature="newMethod()", content="public void newMethod() {}", line_start=1, line_end=1)]
        modified_methods = []
        deleted_methods = []
        
        # 更新映射
        merged_content, warnings = mapper.update_mapping(
            "src/TestClass.java",
            new_source_content,
            new_test_content,
            added_methods,
            modified_methods,
            deleted_methods,
        )
        
        # 验证映射是否更新成功
        assert "src/TestClass.java" in mapper.mappings
        assert mapper.mappings["src/TestClass.java"].source_hash != ""
        assert mapper.mappings["src/TestClass.java"].last_generated is not None
        assert len(warnings) == 0


if __name__ == "__main__":
    pytest.main([__file__])
