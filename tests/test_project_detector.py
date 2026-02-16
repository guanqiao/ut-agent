"""项目类型检测模块单元测试."""

import tempfile
from pathlib import Path

import pytest

from ut_agent.tools.project_detector import (
    detect_project_type,
    find_source_files,
    get_test_directory,
    infer_package_name,
)


class TestDetectProjectType:
    """项目类型检测测试."""

    def test_detect_maven_project(self):
        """测试 Maven 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pom_file = Path(tmpdir) / "pom.xml"
            pom_file.write_text("<project></project>")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "java"
            assert build_tool == "maven"

    def test_detect_gradle_project(self):
        """测试 Gradle 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_file = Path(tmpdir) / "build.gradle"
            build_file.write_text("plugins {}")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "java"
            assert build_tool == "gradle"

    def test_detect_gradle_kts_project(self):
        """测试 Gradle Kotlin 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            build_file = Path(tmpdir) / "build.gradle.kts"
            build_file.write_text("plugins {}")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "java"
            assert build_tool == "gradle"

    def test_detect_vue_project(self):
        """测试 Vue 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text('{"dependencies": {"vue": "^3.0.0"}}')

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "vue"
            assert build_tool == "npm"

    def test_detect_vue_config_project(self):
        """测试通过 vue.config.js 检测 Vue 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text("{}")
            vue_config = Path(tmpdir) / "vue.config.js"
            vue_config.write_text("module.exports = {}")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "vue"
            assert build_tool == "npm"

    def test_detect_react_project(self):
        """测试 React 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text('{"dependencies": {"react": "^18.0.0"}}')

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "react"
            assert build_tool == "npm"

    def test_detect_typescript_project(self):
        """测试 TypeScript 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text('{"devDependencies": {"typescript": "^5.0.0"}}')

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "typescript"
            assert build_tool == "npm"

    def test_detect_typescript_by_tsconfig(self):
        """测试通过 tsconfig.json 检测 TypeScript 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text("{}")
            tsconfig = Path(tmpdir) / "tsconfig.json"
            tsconfig.write_text('{"compilerOptions": {}}')

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "typescript"
            assert build_tool == "npm"

    def test_detect_javascript_project(self):
        """测试 JavaScript 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_file = Path(tmpdir) / "package.json"
            package_file.write_text('{"name": "js-project"}')

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "javascript"
            assert build_tool == "npm"

    def test_detect_python_project(self):
        """测试 Python 项目检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text("[tool.poetry]")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "python"
            assert build_tool == "pip"

    def test_detect_python_by_setup(self):
        """测试通过 setup.py 检测 Python 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            setup = Path(tmpdir) / "setup.py"
            setup.write_text("from setuptools import setup")

            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "python"
            assert build_tool == "pip"

    def test_detect_unknown_project(self):
        """测试未知项目类型检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_type, build_tool = detect_project_type(tmpdir)
            assert project_type == "unknown"
            assert build_tool == "unknown"

    def test_detect_nonexistent_path(self):
        """测试不存在的路径."""
        with pytest.raises(ValueError, match="项目路径不存在"):
            detect_project_type("/nonexistent/path")


class TestFindSourceFiles:
    """源代码文件查找测试."""

    def test_find_java_source_files(self):
        """测试查找 Java 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src" / "main" / "java" / "com" / "example"
            src_dir.mkdir(parents=True)
            (src_dir / "UserService.java").write_text("public class UserService {}")
            (src_dir / "OrderService.java").write_text("public class OrderService {}")

            files = find_source_files(tmpdir, "java")
            assert len(files) == 2
            assert any("UserService.java" in f for f in files)
            assert any("OrderService.java" in f for f in files)

    def test_find_java_test_files_excluded(self):
        """测试 Java 测试文件被排除."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src" / "main" / "java"
            src_dir.mkdir(parents=True)
            test_dir = Path(tmpdir) / "src" / "test" / "java"
            test_dir.mkdir(parents=True)

            (src_dir / "Service.java").write_text("public class Service {}")
            (test_dir / "ServiceTest.java").write_text("public class ServiceTest {}")

            files = find_source_files(tmpdir, "java")
            assert len(files) == 1
            assert "Service.java" in files[0]

    def test_find_vue_source_files(self):
        """测试查找 Vue 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src" / "components"
            src_dir.mkdir(parents=True)
            (src_dir / "Button.vue").write_text("<template></template>")
            (src_dir / "Input.vue").write_text("<template></template>")

            files = find_source_files(tmpdir, "vue")
            assert len(files) == 2

    def test_find_react_source_files(self):
        """测试查找 React 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            (src_dir / "App.tsx").write_text("export function App() {}")
            (src_dir / "utils.ts").write_text("export const util = () => {}")

            files = find_source_files(tmpdir, "react")
            assert len(files) == 2

    def test_find_node_modules_excluded(self):
        """测试 node_modules 被排除."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            node_modules = Path(tmpdir) / "node_modules" / "some-lib"
            node_modules.mkdir(parents=True)

            (src_dir / "App.tsx").write_text("export function App() {}")
            (node_modules / "lib.tsx").write_text("export const lib = {}")

            files = find_source_files(tmpdir, "react")
            assert len(files) == 1
            assert "node_modules" not in files[0]

    def test_find_python_source_files(self):
        """测试查找 Python 源文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "module1.py").write_text("def func1(): pass")
            (Path(tmpdir) / "module2.py").write_text("def func2(): pass")

            files = find_source_files(tmpdir, "python")
            assert len(files) == 2

    def test_find_python_test_files_excluded(self):
        """测试 Python 测试文件被排除."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "module.py").write_text("def func(): pass")
            (Path(tmpdir) / "test_module.py").write_text("def test_func(): pass")
            (Path(tmpdir) / "module_test.py").write_text("def test_func(): pass")

            files = find_source_files(tmpdir, "python")
            assert len(files) == 1
            assert "module.py" in files[0]

    def test_find_source_files_limit(self):
        """测试源文件数量限制."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()

            # 创建超过 50 个文件
            for i in range(60):
                (src_dir / f"File{i}.java").write_text(f"public class File{i} {{}}")

            files = find_source_files(tmpdir, "java")
            assert len(files) == 50  # 限制为 50 个


class TestGetTestDirectory:
    """测试目录获取测试."""

    def test_get_java_test_directory_existing(self):
        """测试获取已存在的 Java 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "src" / "test" / "java"
            test_dir.mkdir(parents=True)

            result = get_test_directory(tmpdir, "java")
            # 支持 Windows 和 Unix 路径分隔符
            assert "src" in result and "test" in result and "java" in result

    def test_get_java_test_directory_new(self):
        """测试获取新的 Java 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_test_directory(tmpdir, "java")
            # 支持 Windows 和 Unix 路径分隔符
            assert "src" in result and "test" in result and "java" in result

    def test_get_vue_test_directory_existing(self):
        """测试获取已存在的 Vue 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "src" / "__tests__"
            test_dir.mkdir(parents=True)

            result = get_test_directory(tmpdir, "vue")
            assert "__tests__" in result

    def test_get_vue_test_directory_default(self):
        """测试获取默认的 Vue 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_test_directory(tmpdir, "vue")
            assert result.endswith("src")

    def test_get_python_test_directory_existing(self):
        """测试获取已存在的 Python 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "tests"
            test_dir.mkdir()

            result = get_test_directory(tmpdir, "python")
            assert "tests" in result

    def test_get_python_test_directory_new(self):
        """测试获取新的 Python 测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_test_directory(tmpdir, "python")
            assert "tests" in result

    def test_get_unknown_project_test_directory(self):
        """测试获取未知项目的测试目录."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_test_directory(tmpdir, "unknown")
            assert result == tmpdir


class TestInferPackageName:
    """包名推断测试."""

    def test_infer_java_package_name(self):
        """测试推断 Java 包名."""
        project_path = "/project"
        file_path = "/project/src/main/java/com/example/service/UserService.java"

        result = infer_package_name(file_path, project_path, "java")
        assert result == "com.example.service"

    def test_infer_java_package_name_alt_structure(self):
        """测试推断替代结构的 Java 包名."""
        project_path = "/project"
        file_path = "/project/src/java/com/example/Service.java"

        result = infer_package_name(file_path, project_path, "java")
        assert result == "com.example"

    def test_infer_typescript_module_name(self):
        """测试推断 TypeScript 模块名."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            file_path = str(src_dir / "components" / "Button.tsx")

            result = infer_package_name(file_path, tmpdir, "typescript")
            assert "components/Button" in result

    def test_infer_vue_module_name(self):
        """测试推断 Vue 模块名."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir()
            file_path = str(src_dir / "views" / "Home.vue")

            result = infer_package_name(file_path, tmpdir, "vue")
            assert "views/Home" in result

    def test_infer_python_module_name(self):
        """测试推断 Python 模块名."""
        project_path = "/project"
        file_path = "/project/src/utils/helpers.py"

        result = infer_package_name(file_path, project_path, "python")
        assert result == "src.utils.helpers"

    def test_infer_package_name_fallback(self):
        """测试包名推断回退."""
        project_path = "/project"
        file_path = "/other/path/Service.java"

        result = infer_package_name(file_path, project_path, "java")
        assert result == "Service"
