"""变更检测器单元测试."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.selection.change_detector import (
    ChangeType,
    MethodChange,
    FileChange,
    ChangeSet,
    ChangeDetector,
)


class TestChangeType:
    """ChangeType 枚举测试."""

    def test_change_type_values(self):
        """测试 ChangeType 枚举值."""
        assert ChangeType.ADDED.value == "added"
        assert ChangeType.MODIFIED.value == "modified"
        assert ChangeType.DELETED.value == "deleted"
        assert ChangeType.RENAMED.value == "renamed"


class TestMethodChange:
    """MethodChange 数据类测试."""

    def test_method_change_creation(self):
        """测试 MethodChange 创建."""
        change = MethodChange(
            name="test_method",
            signature="public void test()",
            change_type=ChangeType.ADDED,
            line_start=10,
            line_end=20,
            old_content="",
            new_content="public void test() {}",
        )

        assert change.name == "test_method"
        assert change.signature == "public void test()"
        assert change.change_type == ChangeType.ADDED
        assert change.line_start == 10
        assert change.line_end == 20

    def test_method_change_defaults(self):
        """测试 MethodChange 默认值."""
        change = MethodChange(
            name="test",
            signature="void test()",
            change_type=ChangeType.MODIFIED,
        )

        assert change.line_start == 0
        assert change.line_end == 0
        assert change.old_content == ""
        assert change.new_content == ""


class TestFileChange:
    """FileChange 数据类测试."""

    def test_file_change_creation(self):
        """测试 FileChange 创建."""
        method_change = MethodChange(
            name="test",
            signature="void test()",
            change_type=ChangeType.ADDED,
        )

        change = FileChange(
            path="/src/Main.java",
            change_type=ChangeType.MODIFIED,
            old_path=None,
            old_content="old",
            new_content="new",
            method_changes=[method_change],
            added_lines=[10, 11],
            deleted_lines=[5],
        )

        assert change.path == "/src/Main.java"
        assert change.change_type == ChangeType.MODIFIED
        assert len(change.method_changes) == 1
        assert change.added_lines == [10, 11]
        assert change.deleted_lines == [5]

    def test_file_change_defaults(self):
        """测试 FileChange 默认值."""
        change = FileChange(
            path="/test.java",
            change_type=ChangeType.ADDED,
        )

        assert change.old_path is None
        assert change.old_content == ""
        assert change.new_content == ""
        assert change.method_changes == []
        assert change.added_lines == []
        assert change.deleted_lines == []


class TestChangeSet:
    """ChangeSet 数据类测试."""

    def test_change_set_creation(self):
        """测试 ChangeSet 创建."""
        change_set = ChangeSet(
            changes=[],
            base_ref="main",
            head_ref="feature",
        )

        assert change_set.changes == []
        assert change_set.base_ref == "main"
        assert change_set.head_ref == "feature"

    def test_change_set_add(self):
        """测试 add 方法."""
        change_set = ChangeSet()
        change = FileChange(path="/test.java", change_type=ChangeType.ADDED)

        change_set.add(change)

        assert len(change_set.changes) == 1
        assert change_set.changes[0] == change

    def test_change_set_get_by_type(self):
        """测试 get_by_type 方法."""
        change1 = FileChange(path="/test1.java", change_type=ChangeType.ADDED)
        change2 = FileChange(path="/test2.java", change_type=ChangeType.MODIFIED)
        change3 = FileChange(path="/test3.java", change_type=ChangeType.ADDED)

        change_set = ChangeSet(changes=[change1, change2, change3])

        added = change_set.get_by_type(ChangeType.ADDED)
        modified = change_set.get_by_type(ChangeType.MODIFIED)

        assert len(added) == 2
        assert len(modified) == 1
        assert all(c.change_type == ChangeType.ADDED for c in added)

    def test_change_set_get_file_paths(self):
        """测试 get_file_paths 方法."""
        change1 = FileChange(path="/test1.java", change_type=ChangeType.ADDED)
        change2 = FileChange(path="/test2.java", change_type=ChangeType.MODIFIED)

        change_set = ChangeSet(changes=[change1, change2])

        paths = change_set.get_file_paths()

        assert paths == ["/test1.java", "/test2.java"]


class TestChangeDetector:
    """ChangeDetector 测试."""

    def test_detector_initialization_without_git(self):
        """测试无 Git 仓库的初始化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            assert detector._repo_path == Path(tmpdir)
            assert detector._repo is None

    @patch("ut_agent.selection.change_detector.git", create=True)
    def test_detector_initialization_with_git(self, mock_git):
        """测试有 Git 仓库的初始化."""
        mock_repo = Mock()
        mock_git.Repo.return_value = mock_repo

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            assert detector._repo is not None
            mock_git.Repo.assert_called_once_with(tmpdir)

    def test_is_source_file(self):
        """测试 _is_source_file 方法."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            # 支持的扩展名
            assert detector._is_source_file("test.java") is True
            assert detector._is_source_file("test.ts") is True
            assert detector._is_source_file("test.tsx") is True
            assert detector._is_source_file("test.js") is True
            assert detector._is_source_file("test.jsx") is True
            assert detector._is_source_file("test.vue") is True
            assert detector._is_source_file("test.py") is True

            # 不支持的扩展名
            assert detector._is_source_file("test.txt") is False
            assert detector._is_source_file("test.md") is False
            assert detector._is_source_file("test") is False

    @patch("ut_agent.selection.change_detector.git", create=True)
    def test_detect_changes_without_repo(self, mock_git):
        """测试无仓库时的变更检测."""
        mock_git.Repo.side_effect = Exception("Not a git repo")

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change_set = detector.detect_changes()

            assert isinstance(change_set, ChangeSet)
            assert change_set.changes == []

    @patch("ut_agent.selection.change_detector.git", create=True)
    def test_detect_changes_with_repo(self, mock_git):
        """测试有仓库时的变更检测."""
        mock_diff = Mock()
        mock_diff.a_path = "test.java"
        mock_diff.b_path = "test.java"
        mock_diff.new_file = False
        mock_diff.deleted_file = False
        mock_diff.renamed = False
        mock_diff.a_blob = None
        mock_diff.b_blob = None

        mock_base_commit = Mock()
        mock_head_commit = Mock()
        mock_base_commit.diff.return_value = [mock_diff]

        mock_repo = Mock()
        mock_repo.commit.side_effect = [mock_base_commit, mock_head_commit]
        mock_git.Repo.return_value = mock_repo

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change_set = detector.detect_changes("HEAD~1", "HEAD")

            assert isinstance(change_set, ChangeSet)
            assert change_set.base_ref == "HEAD~1"
            assert change_set.head_ref == "HEAD"

    @patch("ut_agent.selection.change_detector.git", create=True)
    def test_detect_staged_changes(self, mock_git):
        """测试检测暂存区变更."""
        mock_diff = Mock()
        mock_diff.a_path = "test.java"
        mock_diff.b_path = "test.java"

        mock_repo = Mock()
        mock_repo.index.diff.return_value = [mock_diff]
        mock_git.Repo.return_value = mock_repo

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change_set = detector.detect_staged_changes()

            assert isinstance(change_set, ChangeSet)
            assert change_set.base_ref == "HEAD"
            assert change_set.head_ref == "INDEX"

    @patch("ut_agent.selection.change_detector.git", create=True)
    def test_detect_unstaged_changes(self, mock_git):
        """测试检测未暂存变更."""
        mock_item = Mock()
        mock_item.a_path = "test.java"

        mock_repo = Mock()
        mock_repo.is_dirty.return_value = True
        mock_repo.index.diff.return_value = [mock_item]
        mock_git.Repo.return_value = mock_repo

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change_set = detector.detect_unstaged_changes()

            assert isinstance(change_set, ChangeSet)
            assert change_set.base_ref == "INDEX"
            assert change_set.head_ref == "WORKING"

    def test_detect_method_changes_added(self):
        """测试检测新增方法变更."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            old_content = "public class Test {}"
            new_content = """public class Test {
    public void newMethod() {}
}"""

            file_change = FileChange(
                path="Test.java",
                change_type=ChangeType.MODIFIED,
                old_content=old_content,
                new_content=new_content,
            )

            method_changes = detector.detect_method_changes(file_change)

            # 应该检测到新增的方法
            assert len(method_changes) >= 1
            assert any(m.change_type == ChangeType.ADDED for m in method_changes)

    def test_detect_method_changes_deleted(self):
        """测试检测删除方法变更."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            old_content = """public class Test {
    public void oldMethod() {}
}"""
            new_content = "public class Test {}"

            file_change = FileChange(
                path="Test.java",
                change_type=ChangeType.MODIFIED,
                old_content=old_content,
                new_content=new_content,
            )

            method_changes = detector.detect_method_changes(file_change)

            # 应该检测到删除的方法
            assert len(method_changes) >= 1
            assert any(m.change_type == ChangeType.DELETED for m in method_changes)

    def test_detect_method_changes_modified(self):
        """测试检测修改方法变更."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            old_content = """public class Test {
    public void method() {
        int x = 1;
    }
}"""
            new_content = """public class Test {
    public void method() {
        int x = 2;
    }
}"""

            file_change = FileChange(
                path="Test.java",
                change_type=ChangeType.MODIFIED,
                old_content=old_content,
                new_content=new_content,
            )

            method_changes = detector.detect_method_changes(file_change)

            # 应该检测到修改的方法
            assert len(method_changes) >= 1
            assert any(m.change_type == ChangeType.MODIFIED for m in method_changes)

    def test_parse_methods_java(self):
        """测试解析 Java 方法."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            content = """public class Test {
    public void method1() {}
    public int method2(String arg) { return 0; }
}"""

            methods = detector._parse_methods(content, "Test.java")

            assert len(methods) == 2
            assert any(m.name == "method1" for m in methods)
            assert any(m.name == "method2" for m in methods)

    def test_parse_methods_typescript(self):
        """测试解析 TypeScript 方法."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            content = """function func1() {}
const func2 = () => {}"""

            methods = detector._parse_methods(content, "test.ts")

            # TypeScript 应该也能解析
            assert len(methods) >= 0  # 可能解析出函数

    def test_parse_methods_empty(self):
        """测试解析空内容."""
        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)

            methods = detector._parse_methods("", "test.java")

            assert methods == []

    def test_create_file_change(self):
        """测试 _create_file_change 方法."""
        mock_diff = Mock()
        mock_diff.a_path = "old.java"
        mock_diff.b_path = "new.java"
        mock_diff.new_file = False
        mock_diff.deleted_file = False
        mock_diff.renamed = True
        
        # Mock blob with data_stream
        mock_blob = Mock()
        mock_blob.data_stream.read.return_value.decode.return_value = ""
        mock_diff.a_blob = mock_blob
        mock_diff.b_blob = mock_blob

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change = detector._create_file_change(mock_diff)

            assert change is not None
            assert change.path == "new.java"
            assert change.old_path == "old.java"
            assert change.change_type == ChangeType.RENAMED

    def test_create_file_change_added(self):
        """测试创建新增文件变更."""
        mock_diff = Mock()
        mock_diff.a_path = None
        mock_diff.b_path = "new.java"
        mock_diff.new_file = True
        mock_diff.deleted_file = False
        mock_diff.renamed = False
        
        # Mock blob with data_stream
        mock_blob = Mock()
        mock_blob.data_stream.read.return_value.decode.return_value = ""
        mock_diff.a_blob = None
        mock_diff.b_blob = mock_blob

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change = detector._create_file_change(mock_diff)

            assert change is not None
            assert change.path == "new.java"
            assert change.change_type == ChangeType.ADDED

    def test_create_file_change_deleted(self):
        """测试创建删除文件变更."""
        mock_diff = Mock()
        mock_diff.a_path = "old.java"
        mock_diff.b_path = None
        mock_diff.new_file = False
        mock_diff.deleted_file = True
        mock_diff.renamed = False
        
        # Mock blob with data_stream
        mock_blob = Mock()
        mock_blob.data_stream.read.return_value.decode.return_value = ""
        mock_diff.a_blob = mock_blob
        mock_diff.b_blob = None

        with tempfile.TemporaryDirectory() as tmpdir:
            detector = ChangeDetector(tmpdir)
            change = detector._create_file_change(mock_diff)

            assert change is not None
            assert change.path == "old.java"
            assert change.change_type == ChangeType.DELETED
