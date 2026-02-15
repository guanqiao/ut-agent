"""Git分析器测试."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from ut_agent.tools.git_analyzer import (
    GitAnalyzer,
    CodeChange,
    MethodChange,
    ChangeType,
    filter_source_files,
    get_changed_methods,
)


class TestGitAnalyzer:
    """GitAnalyzer测试类."""

    def test_init_with_non_git_repo(self, tmp_path):
        """测试非Git仓库初始化."""
        with pytest.raises(ValueError, match="不是Git仓库"):
            GitAnalyzer(str(tmp_path))

    def test_init_with_git_repo(self, tmp_path):
        """测试Git仓库初始化."""
        # 创建.git目录
        (tmp_path / ".git").mkdir()

        with patch.object(GitAnalyzer, '_run_git_command', return_value=""):
            analyzer = GitAnalyzer(str(tmp_path))
            assert analyzer.project_path == tmp_path

    def test_run_git_command_success(self, tmp_path):
        """测试成功的Git命令执行."""
        (tmp_path / ".git").mkdir()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="test output",
                stderr=""
            )

            analyzer = GitAnalyzer(str(tmp_path))
            result = analyzer._run_git_command(["status"])

            assert result == "test output"
            mock_run.assert_called_once()

    def test_run_git_command_failure(self, tmp_path):
        """测试失败的Git命令执行."""
        (tmp_path / ".git").mkdir()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="error message"
            )

            analyzer = GitAnalyzer(str(tmp_path))
            with pytest.raises(RuntimeError, match="Git命令失败"):
                analyzer._run_git_command(["status"])

    def test_parse_diff_added(self, tmp_path):
        """测试解析新增文件的diff."""
        (tmp_path / ".git").mkdir()

        diff_content = """diff --git a/Test.java b/Test.java
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/Test.java
@@ -0,0 +1,10 @@
+public class Test {
+    public void method1() {
+        System.out.println("hello");
+    }
+}
"""

        with patch.object(GitAnalyzer, '_run_git_command', return_value=""):
            analyzer = GitAnalyzer(str(tmp_path))
            change = analyzer._parse_diff("Test.java", diff_content)

            assert change.file_path == "Test.java"
            assert change.change_type == ChangeType.ADDED
            assert len(change.added_lines) == 5
            assert len(change.deleted_lines) == 0

    def test_parse_diff_modified(self, tmp_path):
        """测试解析修改文件的diff."""
        (tmp_path / ".git").mkdir()

        diff_content = """diff --git a/Test.java b/Test.java
index 1234567..abcdefg 100644
--- a/Test.java
+++ b/Test.java
@@ -1,5 +1,5 @@
 public class Test {
     public void method1() {
-        System.out.println("old");
+        System.out.println("new");
     }
 }
"""

        with patch.object(GitAnalyzer, '_run_git_command', return_value=""):
            analyzer = GitAnalyzer(str(tmp_path))
            change = analyzer._parse_diff("Test.java", diff_content)

            assert change.file_path == "Test.java"
            assert change.change_type == ChangeType.MODIFIED
            assert len(change.added_lines) == 1
            assert len(change.deleted_lines) == 1


class TestFilterSourceFiles:
    """过滤源文件测试类."""

    def test_filter_java_files(self):
        """测试过滤Java文件."""
        changes = [
            CodeChange(file_path="src/Main.java", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/Utils.java", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/TestTest.java", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/config.xml", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="README.md", change_type=ChangeType.MODIFIED),
        ]

        result = filter_source_files(changes, "java")

        assert len(result) == 2
        assert result[0].file_path == "src/Main.java"
        assert result[1].file_path == "src/Utils.java"

    def test_filter_typescript_files(self):
        """测试过滤TypeScript文件."""
        changes = [
            CodeChange(file_path="src/App.ts", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/Component.tsx", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/utils.js", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/style.css", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/App.spec.ts", change_type=ChangeType.MODIFIED),
        ]

        result = filter_source_files(changes, "typescript")

        # .js 文件也被包含在 typescript 类型中
        assert len(result) == 3
        assert result[0].file_path == "src/App.ts"
        assert result[1].file_path == "src/Component.tsx"

    def test_filter_vue_files(self):
        """测试过滤Vue文件."""
        changes = [
            CodeChange(file_path="src/App.vue", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/Component.vue", change_type=ChangeType.MODIFIED),
            CodeChange(file_path="src/main.js", change_type=ChangeType.MODIFIED),
        ]

        result = filter_source_files(changes, "vue")

        # .js 文件也被包含在 vue 类型中
        assert len(result) == 3


class TestGetChangedMethods:
    """获取变更方法测试类."""

    def test_extract_methods_from_java(self, tmp_path):
        """测试从Java代码提取方法."""
        from ut_agent.tools.git_analyzer import _extract_methods

        java_code = """
public class Test {
    public void method1() {
        System.out.println("hello");
    }

    private int method2(String arg) {
        return arg.length();
    }
}
"""
        methods = _extract_methods(java_code)

        assert "method1" in methods
        assert "method2" in methods
        assert methods["method1"]["line_start"] == 3

    def test_method_changed(self):
        """测试方法变化检测."""
        from ut_agent.tools.git_analyzer import _method_changed

        old_info = {"content": "public void test() { old(); }"}
        new_info = {"content": "public void test() { new(); }"}
        same_info = {"content": "public void test() { old(); }"}

        assert _method_changed(old_info, new_info) is True
        assert _method_changed(old_info, same_info) is False


class TestCodeChange:
    """CodeChange数据类测试."""

    def test_code_change_creation(self):
        """测试CodeChange创建."""
        change = CodeChange(
            file_path="src/Test.java",
            change_type=ChangeType.MODIFIED,
            line_range=(10, 20),
            added_lines=[15, 16, 17],
            deleted_lines=[12],
        )

        assert change.file_path == "src/Test.java"
        assert change.change_type == ChangeType.MODIFIED
        assert change.line_range == (10, 20)
        assert len(change.added_lines) == 3
        assert len(change.deleted_lines) == 1


class TestChangeType:
    """ChangeType枚举测试."""

    def test_change_type_values(self):
        """测试变更类型值."""
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.DELETED.value == "deleted"
        assert ChangeType.RENAMED.value == "renamed"
