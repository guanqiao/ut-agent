"""工具变更检测器测试"""

import tempfile
from pathlib import Path
from unittest import mock

import pytest

from ut_agent.tools.change_detector import (
    MethodInfo,
    ClassInfo,
    ChangeSummary,
    JavaChangeDetector,
    TypeScriptChangeDetector,
    create_change_detector,
)
from ut_agent.tools.git_analyzer import ChangeType, CodeChange


class TestMethodInfo:
    """测试方法信息数据类"""
    
    def test_method_info_creation(self):
        """测试方法信息创建"""
        method = MethodInfo(
            name="testMethod",
            signature="public void testMethod()",
            line_start=10,
            line_end=20,
            content="public void testMethod() { }",
            modifiers=["public"],
            return_type="void",
            parameters=[],
        )
        
        assert method.name == "testMethod"
        assert method.signature == "public void testMethod()"
        assert method.line_start == 10
        assert method.line_end == 20
        assert method.content == "public void testMethod() { }"
        assert method.modifiers == ["public"]
        assert method.return_type == "void"
        assert method.parameters == []
    
    def test_method_info_defaults(self):
        """测试方法信息默认值"""
        method = MethodInfo(
            name="testMethod",
            signature="void testMethod()",
            line_start=1,
            line_end=5,
            content="void testMethod() { }",
        )
        
        assert method.modifiers == []
        assert method.return_type == ""
        assert method.parameters == []


class TestClassInfo:
    """测试类信息数据类"""
    
    def test_class_info_creation(self):
        """测试类信息创建"""
        cls = ClassInfo(
            name="TestClass",
            line_start=1,
            line_end=50,
            methods={"testMethod": MethodInfo(
                name="testMethod",
                signature="public void testMethod()",
                line_start=10,
                line_end=20,
                content="public void testMethod() { }",
            )},
            fields=["field1"],
            imports=["java.util.List"],
            package="com.example",
        )
        
        assert cls.name == "TestClass"
        assert cls.line_start == 1
        assert cls.line_end == 50
        assert "testMethod" in cls.methods
        assert cls.fields == ["field1"]
        assert cls.imports == ["java.util.List"]
        assert cls.package == "com.example"
    
    def test_class_info_defaults(self):
        """测试类信息默认值"""
        cls = ClassInfo(
            name="TestClass",
            line_start=1,
            line_end=50,
        )
        
        assert cls.methods == {}
        assert cls.fields == []
        assert cls.imports == []
        assert cls.package == ""


class TestChangeSummary:
    """测试变更摘要数据类"""
    
    def test_change_summary_creation(self):
        """测试变更摘要创建"""
        summary = ChangeSummary(
            file_path="src/Test.java",
            change_type=ChangeType.MODIFIED,
            affected_classes=["TestClass"],
            added_methods=[MethodInfo(
                name="newMethod",
                signature="public void newMethod()",
                line_start=10,
                line_end=20,
                content="public void newMethod() { }",
            )],
            modified_methods=[],
            deleted_methods=[],
        )
        
        assert summary.file_path == "src/Test.java"
        assert summary.change_type == ChangeType.MODIFIED
        assert summary.affected_classes == ["TestClass"]
        assert len(summary.added_methods) == 1
        assert summary.modified_methods == []
        assert summary.deleted_methods == []
    
    def test_change_summary_defaults(self):
        """测试变更摘要默认值"""
        summary = ChangeSummary(
            file_path="src/Test.java",
            change_type=ChangeType.ADDED,
        )
        
        assert summary.affected_classes == []
        assert summary.added_methods == []
        assert summary.modified_methods == []
        assert summary.deleted_methods == []


class TestJavaChangeDetector:
    """测试 Java 变更检测器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
    
    def teardown_method(self):
        """清理测试环境"""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        detector = JavaChangeDetector(str(self.project_path))
        assert detector.project_path == self.project_path
    
    def test_parse_classes(self):
        """测试解析类定义"""
        detector = JavaChangeDetector(str(self.project_path))
        
        content = """
        package com.example;
        
        public class TestClass {
            public void testMethod() {
            }
            
            private int getValue() {
                return 42;
            }
        }
        """
        
        classes = detector._parse_classes(content)
        assert len(classes) == 1
        assert classes[0].name == "TestClass"
        assert classes[0].package == "com.example"
        assert "testMethod" in classes[0].methods
        assert "getValue" in classes[0].methods
    
    def test_parse_methods(self):
        """测试解析方法定义"""
        detector = JavaChangeDetector(str(self.project_path))
        
        class_content = """
        public class TestClass {
            public void testMethod() {
                System.out.println("test");
            }
            
            private int getValue() {
                return 42;
            }
        }
        """
        
        methods = detector._parse_methods(class_content, 1)
        assert "testMethod" in methods
        assert "getValue" in methods
        assert methods["testMethod"].return_type == "void"
        assert methods["getValue"].return_type == "int"
    
    def test_find_class_end(self):
        """测试查找类结束位置"""
        detector = JavaChangeDetector(str(self.project_path))
        
        lines = [
            "public class TestClass {",
            "    public void testMethod() {",
            "    }",
            "}",
            "// End of file",
        ]
        
        end_line = detector._find_class_end(lines, 0)
        assert end_line == 4
    
    def test_find_method_end(self):
        """测试查找方法结束位置"""
        detector = JavaChangeDetector(str(self.project_path))
        
        lines = [
            "public void testMethod() {",
            "    System.out.println(\"test\");",
            "}",
            "public void anotherMethod() {",
            "}",
        ]
        
        end_line = detector._find_method_end(lines, 0, 1)
        assert end_line == 3
    
    @mock.patch("ut_agent.tools.change_detector.GitAnalyzer")
    def test_analyze_changes_added_file(self, mock_git_analyzer_class):
        """测试分析新增文件"""
        # 创建测试文件
        test_file = self.project_path / "src" / "Test.java"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""
        package com.example;
        
        public class Test {
            public void testMethod() {
            }
        }
        """)
        
        # Mock GitAnalyzer
        mock_git_analyzer = mock.MagicMock()
        mock_git_analyzer.get_file_at_ref.return_value = None
        mock_git_analyzer_class.return_value = mock_git_analyzer
        
        detector = JavaChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.java",
            change_type=ChangeType.ADDED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 1
        assert summaries[0].change_type == ChangeType.ADDED
        assert "Test" in summaries[0].affected_classes
        assert len(summaries[0].added_methods) == 1
    
    @mock.patch("ut_agent.tools.change_detector.GitAnalyzer")
    def test_analyze_changes_deleted_file(self, mock_git_analyzer_class):
        """测试分析删除文件"""
        # Mock GitAnalyzer
        mock_git_analyzer = mock.MagicMock()
        mock_git_analyzer.get_file_at_ref.return_value = """
        package com.example;
        
        public class Test {
            public void testMethod() {
            }
        }
        """
        mock_git_analyzer_class.return_value = mock_git_analyzer
        
        detector = JavaChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.java",
            change_type=ChangeType.DELETED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 1
        assert summaries[0].change_type == ChangeType.DELETED
        assert "Test" in summaries[0].affected_classes
        assert len(summaries[0].deleted_methods) == 1
    
    @mock.patch("ut_agent.tools.change_detector.GitAnalyzer")
    def test_analyze_changes_modified_file(self, mock_git_analyzer_class):
        """测试分析修改文件"""
        # 创建测试文件
        test_file = self.project_path / "src" / "Test.java"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""
        package com.example;
        
        public class Test {
            public void testMethod() {
                System.out.println("modified");
            }
            
            public void newMethod() {
            }
        }
        """)
        
        # Mock GitAnalyzer
        mock_git_analyzer = mock.MagicMock()
        mock_git_analyzer.get_file_at_ref.return_value = """
        package com.example;
        
        public class Test {
            public void testMethod() {
            }
        }
        """
        mock_git_analyzer_class.return_value = mock_git_analyzer
        
        detector = JavaChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.java",
            change_type=ChangeType.MODIFIED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 1
        assert summaries[0].change_type == ChangeType.MODIFIED
        assert len(summaries[0].modified_methods) == 1
        assert len(summaries[0].added_methods) == 1
    
    def test_compare_versions(self):
        """测试比较两个版本"""
        detector = JavaChangeDetector(str(self.project_path))
        
        old_content = """
        public class Test {
            public void oldMethod() {
            }
            
            public void modifiedMethod() {
                System.out.println("old");
            }
        }
        """
        
        new_content = """
        public class Test {
            public void modifiedMethod() {
                System.out.println("new");
            }
            
            public void newMethod() {
            }
        }
        """
        
        summary = detector._compare_versions("Test.java", old_content, new_content)
        
        assert summary.change_type == ChangeType.MODIFIED
        assert len(summary.added_methods) == 1
        assert summary.added_methods[0].name == "newMethod"
        assert len(summary.modified_methods) == 1
        assert summary.modified_methods[0][0].name == "modifiedMethod"
        assert len(summary.deleted_methods) == 1
        assert summary.deleted_methods[0].name == "oldMethod"
    
    def test_analyze_changes_non_java_file(self):
        """测试分析非 Java 文件"""
        detector = JavaChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.ts",
            change_type=ChangeType.ADDED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 0


class TestTypeScriptChangeDetector:
    """测试 TypeScript 变更检测器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
    
    def teardown_method(self):
        """清理测试环境"""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """测试初始化"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        assert detector.project_path == self.project_path
    
    def test_parse_functions(self):
        """测试解析函数定义"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        content = """
        export function testFunction(): void {
            console.log("test");
        }
        
        async function asyncFunction(): Promise<string> {
            return "test";
        }
        """
        
        functions = detector._parse_functions(content)
        assert "testFunction" in functions
        assert "asyncFunction" in functions
    
    def test_find_function_end(self):
        """测试查找函数结束位置"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        lines = [
            "export function testFunction(): void {",
            "    console.log(\"test\");",
            "}",
            "export function anotherFunction(): void {",
            "}",
        ]
        
        end_line = detector._find_function_end(lines, 0)
        assert end_line == 3
    
    @mock.patch("ut_agent.tools.change_detector.GitAnalyzer")
    def test_analyze_changes_added_file(self, mock_git_analyzer_class):
        """测试分析新增文件"""
        # 创建测试文件
        test_file = self.project_path / "src" / "test.ts"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""
        export function testFunction(): void {
            console.log("test");
        }
        """)
        
        # Mock GitAnalyzer
        mock_git_analyzer = mock.MagicMock()
        mock_git_analyzer.get_file_at_ref.return_value = None
        mock_git_analyzer_class.return_value = mock_git_analyzer
        
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/test.ts",
            change_type=ChangeType.ADDED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 1
        assert summaries[0].change_type == ChangeType.ADDED
        assert len(summaries[0].added_methods) == 1
    
    @mock.patch("ut_agent.tools.change_detector.GitAnalyzer")
    def test_analyze_changes_modified_file(self, mock_git_analyzer_class):
        """测试分析修改文件"""
        # 创建测试文件
        test_file = self.project_path / "src" / "test.ts"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""
        export function testFunction(): void {
            console.log("modified");
        }
        
        export function newFunction(): void {
        }
        """)
        
        # Mock GitAnalyzer
        mock_git_analyzer = mock.MagicMock()
        mock_git_analyzer.get_file_at_ref.return_value = """
        export function testFunction(): void {
            console.log("test");
        }
        """
        mock_git_analyzer_class.return_value = mock_git_analyzer
        
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/test.ts",
            change_type=ChangeType.MODIFIED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 1
        assert summaries[0].change_type == ChangeType.MODIFIED
        assert len(summaries[0].modified_methods) == 1
        assert len(summaries[0].added_methods) == 1
    
    def test_compare_versions(self):
        """测试比较两个版本"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        old_content = """
        export function oldFunction(): void {
        }
        
        export function modifiedFunction(): void {
            console.log("old");
        }
        """
        
        new_content = """
        export function modifiedFunction(): void {
            console.log("new");
        }
        
        export function newFunction(): void {
        }
        """
        
        summary = detector._compare_versions("test.ts", old_content, new_content)
        
        assert summary.change_type == ChangeType.MODIFIED
        assert len(summary.added_methods) == 1
        assert summary.added_methods[0].name == "newFunction"
        assert len(summary.modified_methods) == 1
        assert summary.modified_methods[0][0].name == "modifiedFunction"
        assert len(summary.deleted_methods) == 1
        assert summary.deleted_methods[0].name == "oldFunction"
    
    def test_analyze_changes_vue_file(self):
        """测试分析 Vue 文件"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.vue",
            change_type=ChangeType.ADDED,
        )
        
        with mock.patch.object(detector, "_analyze_file_change") as mock_analyze:
            mock_analyze.return_value = ChangeSummary(
                file_path="src/Test.vue",
                change_type=ChangeType.ADDED,
            )
            
            summaries = detector.analyze_changes([code_change])
            assert len(summaries) == 1
    
    def test_analyze_changes_non_ts_file(self):
        """测试分析非 TypeScript 文件"""
        detector = TypeScriptChangeDetector(str(self.project_path))
        
        code_change = CodeChange(
            file_path="src/Test.java",
            change_type=ChangeType.ADDED,
        )
        
        summaries = detector.analyze_changes([code_change])
        assert len(summaries) == 0


class TestCreateChangeDetector:
    """测试创建变更检测器工厂函数"""
    
    def test_create_java_detector(self):
        """测试创建 Java 检测器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = create_change_detector(tmpdir, "java")
            assert isinstance(detector, JavaChangeDetector)
    
    def test_create_typescript_detector(self):
        """测试创建 TypeScript 检测器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = create_change_detector(tmpdir, "typescript")
            assert isinstance(detector, TypeScriptChangeDetector)
    
    def test_create_vue_detector(self):
        """测试创建 Vue 检测器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = create_change_detector(tmpdir, "vue")
            assert isinstance(detector, TypeScriptChangeDetector)
    
    def test_create_react_detector(self):
        """测试创建 React 检测器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = create_change_detector(tmpdir, "react")
            assert isinstance(detector, TypeScriptChangeDetector)
    
    def test_create_unsupported_detector(self):
        """测试创建不支持的检测器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError) as exc_info:
                create_change_detector(tmpdir, "unsupported")
            assert "不支持的项目类型" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__])
