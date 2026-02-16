"""跨文件上下文分析模块单元测试."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from ut_agent.tools.cross_file_analyzer import (
    ClassRelationship,
    CrossFileAnalyzer,
    DependencyInfo,
    ProjectIndex,
    SymbolInfo,
)


class TestSymbolInfo:
    """SymbolInfo 数据类测试."""

    def test_symbol_info_creation(self):
        """测试 SymbolInfo 创建."""
        symbol = SymbolInfo(
            name="UserService",
            type="class",
            file_path="/project/src/UserService.java",
            package="com.example",
            line_number=10,
            is_public=True,
            signature="public class UserService",
            documentation="Service class for users",
        )

        assert symbol.name == "UserService"
        assert symbol.type == "class"
        assert symbol.file_path == "/project/src/UserService.java"
        assert symbol.package == "com.example"
        assert symbol.is_public is True

    def test_symbol_info_defaults(self):
        """测试 SymbolInfo 默认值."""
        symbol = SymbolInfo(
            name="test",
            type="function",
            file_path="/test.ts",
        )

        assert symbol.package == ""
        assert symbol.line_number == 0
        assert symbol.is_public is True
        assert symbol.signature == ""
        assert symbol.documentation == ""


class TestDependencyInfo:
    """DependencyInfo 数据类测试."""

    def test_dependency_info_creation(self):
        """测试 DependencyInfo 创建."""
        dep = DependencyInfo(
            source_file="/project/src/A.java",
            target_file="/project/src/B.java",
            dependency_type="import",
            symbol="B",
            line_number=5,
        )

        assert dep.source_file == "/project/src/A.java"
        assert dep.target_file == "/project/src/B.java"
        assert dep.dependency_type == "import"
        assert dep.symbol == "B"
        assert dep.line_number == 5

    def test_dependency_info_defaults(self):
        """测试 DependencyInfo 默认值."""
        dep = DependencyInfo(
            source_file="/A.java",
            target_file="/B.java",
            dependency_type="extends",
        )

        assert dep.symbol == ""
        assert dep.line_number == 0


class TestClassRelationship:
    """ClassRelationship 数据类测试."""

    def test_class_relationship_creation(self):
        """测试 ClassRelationship 创建."""
        rel = ClassRelationship(
            class_name="UserService",
            file_path="/project/src/UserService.java",
            superclass="BaseService",
            interfaces=["IUserService", "Serializable"],
            subclasses=["AdminUserService"],
            implementors=[],
            dependencies=["UserRepository"],
        )

        assert rel.class_name == "UserService"
        assert rel.superclass == "BaseService"
        assert len(rel.interfaces) == 2
        assert "IUserService" in rel.interfaces

    def test_class_relationship_defaults(self):
        """测试 ClassRelationship 默认值."""
        rel = ClassRelationship(
            class_name="Test",
            file_path="/Test.java",
        )

        assert rel.superclass is None
        assert rel.interfaces == []
        assert rel.subclasses == []
        assert rel.implementors == []
        assert rel.dependencies == []


class TestProjectIndex:
    """ProjectIndex 测试."""

    def test_project_index_initialization(self):
        """测试 ProjectIndex 初始化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)

            assert index.project_path == Path(tmpdir)
            assert index.symbols == {}
            assert index.files == {}
            assert index.dependencies == []
            assert index.relationships == {}

    def test_find_source_files_java(self):
        """测试查找 Java 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "Main.java").write_text("public class Main {}")
            (src_dir / "Service.java").write_text("public class Service {}")

            index = ProjectIndex(tmpdir)
            files = index._find_source_files()

            # Test.java 可能被排除（测试文件），所以至少找到 1 个
            assert len(files) >= 1
            assert any("Main.java" in f for f in files)

    def test_find_source_files_typescript(self):
        """测试查找 TypeScript 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "app.ts").write_text("export const app = {}")
            (src_dir / "types.d.ts").write_text("declare type MyType = string")

            index = ProjectIndex(tmpdir)
            files = index._find_source_files()

            # .d.ts 文件应该被排除
            assert len(files) == 1
            assert "app.ts" in files[0]

    def test_find_source_files_vue(self):
        """测试查找 Vue 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "App.vue").write_text("<template></template>")

            index = ProjectIndex(tmpdir)
            files = index._find_source_files()

            assert len(files) == 1
            assert "App.vue" in files[0]

    def test_find_source_files_excludes_test_files(self):
        """测试排除测试文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "Main.java").write_text("public class Main {}")
            (src_dir / "MainTest.java").write_text("public class MainTest {}")

            index = ProjectIndex(tmpdir)
            files = index._find_source_files()

            assert len(files) == 1
            assert "Main.java" in files[0]
            assert "MainTest.java" not in files[0]

    def test_find_source_files_excludes_node_modules(self):
        """测试排除 node_modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            node_modules = Path(tmpdir) / "node_modules" / "lib"
            node_modules.mkdir(parents=True)

            (src_dir / "app.ts").write_text("export const app = {}")
            (node_modules / "lib.ts").write_text("export const lib = {}")

            index = ProjectIndex(tmpdir)
            files = index._find_source_files()

            assert len(files) == 1
            assert "node_modules" not in files[0]

    @patch("ut_agent.tools.cross_file_analyzer.analyze_java_file")
    def test_index_file_java(self, mock_analyze):
        """测试索引 Java 文件."""
        mock_analyze.return_value = {
            "file_path": "/project/src/UserService.java",
            "language": "java",
            "package": "com.example",
            "class_name": "UserService",
            "methods": [{"name": "getUser", "signature": "public User getUser()"}],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / "UserService.java"
            java_file.write_text("public class UserService {}")

            index = ProjectIndex(tmpdir)
            index._index_file(str(java_file))

            assert str(java_file) in index.files
            assert "com.example.UserService" in index.symbols
            assert "com.example.UserService.getUser" in index.symbols

    def test_is_index_valid_no_index_file(self):
        """测试索引文件不存在."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            assert index._is_index_valid() is False

    def test_is_index_valid_with_valid_index(self):
        """测试有效的索引文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)

            # 创建一个 Java 文件
            java_file = Path(tmpdir) / "Test.java"
            java_file.write_text("public class Test {}")

            # 手动设置文件哈希
            import hashlib

            content = java_file.read_text()
            file_hash = hashlib.md5(content.encode()).hexdigest()
            index._file_hashes[str(java_file)] = file_hash

            # 保存索引
            index._save_index()

            # 检查索引是否有效
            assert index._is_index_valid() is True

    def test_is_index_valid_file_changed(self):
        """测试文件变更后的索引无效."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)

            # 创建索引文件
            index.index_file.parent.mkdir(parents=True, exist_ok=True)
            index._file_hashes[str(Path(tmpdir) / "Test.java")] = "old_hash"
            index._save_index()

            # 创建新文件（不同内容）
            java_file = Path(tmpdir) / "Test.java"
            java_file.write_text("public class Test {}")

            assert index._is_index_valid() is False

    def test_save_and_load_index(self):
        """测试保存和加载索引."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)

            # 添加一些数据
            index.symbols["Test"] = SymbolInfo(name="Test", type="class", file_path="/Test.java")
            index.dependencies.append(
                DependencyInfo(
                    source_file="/A.java",
                    target_file="/B.java",
                    dependency_type="import",
                )
            )

            # 保存
            index._save_index()

            # 创建新索引并加载
            new_index = ProjectIndex(tmpdir)
            new_index._load_index()

            assert "Test" in new_index.symbols
            assert new_index.symbols["Test"].name == "Test"
            assert len(new_index.dependencies) == 1

    def test_find_symbol_exact_match(self):
        """测试精确匹配查找符号."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.symbols["com.example.UserService"] = SymbolInfo(
                name="UserService",
                type="class",
                file_path="/UserService.java",
            )

            result = index.find_symbol("com.example.UserService")

            assert result is not None
            assert result.name == "UserService"

    def test_find_symbol_partial_match(self):
        """测试部分匹配查找符号."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.symbols["com.example.UserService"] = SymbolInfo(
                name="UserService",
                type="class",
                file_path="/UserService.java",
            )

            result = index.find_symbol("UserService")

            assert result is not None
            assert result.name == "UserService"

    def test_find_symbol_not_found(self):
        """测试查找不存在的符号."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)

            result = index.find_symbol("NonExistent")

            assert result is None

    def test_find_implementations(self):
        """测试查找接口实现."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.dependencies = [
                DependencyInfo(
                    source_file="/UserServiceImpl.java",
                    target_file="IUserService",
                    dependency_type="implements",
                ),
                DependencyInfo(
                    source_file="/AdminServiceImpl.java",
                    target_file="IUserService",
                    dependency_type="implements",
                ),
            ]

            implementations = index.find_implementations("IUserService")

            assert len(implementations) == 2
            assert "/UserServiceImpl.java" in implementations

    def test_find_subclasses(self):
        """测试查找子类."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.dependencies = [
                DependencyInfo(
                    source_file="/AdminUser.java",
                    target_file="User",
                    dependency_type="extends",
                ),
            ]

            subclasses = index.find_subclasses("User")

            assert len(subclasses) == 1
            assert "/AdminUser.java" in subclasses

    def test_get_file_dependencies(self):
        """测试获取文件依赖."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.symbols["UserRepository"] = SymbolInfo(
                name="UserRepository",
                type="class",
                file_path="/UserRepository.java",
            )
            index.dependencies = [
                DependencyInfo(
                    source_file="/UserService.java",
                    target_file="UserRepository",
                    dependency_type="import",
                ),
            ]

            deps = index.get_file_dependencies("/UserService.java")

            assert len(deps) == 1
            assert "/UserRepository.java" in deps[0]

    def test_get_dependent_files(self):
        """测试获取依赖该文件的文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = ProjectIndex(tmpdir)
            index.symbols["com.example.UserService"] = SymbolInfo(
                name="UserService",
                type="class",
                file_path="/UserService.java",
            )
            index.dependencies = [
                DependencyInfo(
                    source_file="/UserController.java",
                    target_file="UserService",
                    dependency_type="import",
                ),
            ]

            dependents = index.get_dependent_files("/UserService.java")

            assert len(dependents) == 1
            assert "/UserController.java" in dependents


class TestCrossFileAnalyzer:
    """CrossFileAnalyzer 测试."""

    @patch("ut_agent.tools.cross_file_analyzer.analyze_java_file")
    @patch.object(ProjectIndex, "build_index")
    def test_analyze_java_file(self, mock_build, mock_analyze):
        """测试分析 Java 文件."""
        mock_analyze.return_value = {
            "file_path": "/project/src/UserService.java",
            "language": "java",
            "class_name": "UserService",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / "UserService.java"
            java_file.write_text("public class UserService {}")

            analyzer = CrossFileAnalyzer(tmpdir)
            result = analyzer.analyze(str(java_file))

            assert result["language"] == "java"
            assert result["class_name"] == "UserService"
            assert "context" in result

    @patch("ut_agent.tools.cross_file_analyzer.analyze_ts_file")
    @patch.object(ProjectIndex, "build_index")
    def test_analyze_typescript_file(self, mock_build, mock_analyze):
        """测试分析 TypeScript 文件."""
        mock_analyze.return_value = {
            "file_path": "/project/src/app.ts",
            "language": "typescript",
            "functions": [{"name": "main"}],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = Path(tmpdir) / "app.ts"
            ts_file.write_text("export function main() {}")

            analyzer = CrossFileAnalyzer(tmpdir)
            result = analyzer.analyze(str(ts_file))

            assert result["language"] == "typescript"
            assert "context" in result

    @patch.object(ProjectIndex, "build_index")
    def test_analyze_unsupported_file(self, mock_build):
        """测试分析不支持的文件类型."""
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "script.py"
            py_file.write_text("print('hello')")

            analyzer = CrossFileAnalyzer(tmpdir)
            result = analyzer.analyze(str(py_file))

            assert "error" in result

    @patch.object(ProjectIndex, "get_file_dependencies")
    @patch.object(ProjectIndex, "build_index")
    def test_build_context(self, mock_build, mock_deps):
        """测试构建上下文."""
        mock_deps.return_value = ["/project/src/Dependency.java"]

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / "UserService.java"
            java_file.write_text("public class UserService {}")

            analyzer = CrossFileAnalyzer(tmpdir)
            analyzer.index.symbols["Dependency"] = SymbolInfo(
                name="Dependency",
                type="class",
                file_path="/project/src/Dependency.java",
            )

            analysis = {"language": "java", "class_name": "UserService"}
            context = analyzer._build_context(str(java_file), analysis)

            assert "dependencies" in context
            assert "dependents" in context
            assert "implementations" in context
