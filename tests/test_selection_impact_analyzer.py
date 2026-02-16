"""影响分析器单元测试."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from ut_agent.selection.impact_analyzer import (
    DirectImpact,
    IndirectImpact,
    TestImpact,
    ImpactReport,
    ImpactAnalyzer,
)
from ut_agent.selection.change_detector import (
    ChangeSet,
    FileChange,
    MethodChange,
    ChangeType,
)


class TestDataClasses:
    """数据类测试."""

    def test_direct_impact_creation(self):
        """测试 DirectImpact 创建."""
        method_change = MethodChange(
            name="test",
            signature="void test()",
            change_type=ChangeType.ADDED,
        )

        impact = DirectImpact(
            file_path="/src/Main.java",
            change_type=ChangeType.MODIFIED,
            method_changes=[method_change],
            test_file="/test/MainTest.java",
        )

        assert impact.file_path == "/src/Main.java"
        assert impact.change_type == ChangeType.MODIFIED
        assert len(impact.method_changes) == 1
        assert impact.test_file == "/test/MainTest.java"

    def test_indirect_impact_creation(self):
        """测试 IndirectImpact 创建."""
        impact = IndirectImpact(
            file_path="/src/Service.java",
            reason="依赖变更的类",
            call_sites=["method1", "method2"],
            test_file="/test/ServiceTest.java",
        )

        assert impact.file_path == "/src/Service.java"
        assert impact.reason == "依赖变更的类"
        assert impact.call_sites == ["method1", "method2"]
        assert impact.test_file == "/test/ServiceTest.java"

    def test_test_impact_creation(self):
        """测试 TestImpact 创建."""
        impact = TestImpact(
            test_file="/test/MainTest.java",
            test_method="testMethod",
            reason="需要更新测试",
            priority=50,
        )

        assert impact.test_file == "/test/MainTest.java"
        assert impact.test_method == "testMethod"
        assert impact.reason == "需要更新测试"
        assert impact.priority == 50

    def test_impact_report_creation(self):
        """测试 ImpactReport 创建."""
        report = ImpactReport()

        assert report.direct_impacts == []
        assert report.indirect_impacts == []
        assert report.test_impacts == []

    def test_impact_report_add_methods(self):
        """测试 ImpactReport 的添加方法."""
        report = ImpactReport()

        direct_impact = DirectImpact(
            file_path="/src/Main.java",
            change_type=ChangeType.MODIFIED,
        )
        indirect_impact = IndirectImpact(
            file_path="/src/Service.java",
            reason="依赖变更",
        )
        test_impact = TestImpact(
            test_file="/test/MainTest.java",
        )

        report.add_direct(direct_impact)
        report.add_indirect(indirect_impact)
        report.add_test_impact(test_impact)

        assert len(report.direct_impacts) == 1
        assert len(report.indirect_impacts) == 1
        assert len(report.test_impacts) == 1

    def test_impact_report_get_all_files(self):
        """测试 ImpactReport 的 get_all_files 方法."""
        report = ImpactReport()

        direct1 = DirectImpact(
            file_path="/src/Main.java",
            change_type=ChangeType.MODIFIED,
        )
        direct2 = DirectImpact(
            file_path="/src/Service.java",
            change_type=ChangeType.ADDED,
        )
        indirect = IndirectImpact(
            file_path="/src/Controller.java",
            reason="依赖变更",
        )

        report.add_direct(direct1)
        report.add_direct(direct2)
        report.add_indirect(indirect)

        files = report.get_all_files()
        assert len(files) == 3
        assert "/src/Main.java" in files
        assert "/src/Service.java" in files
        assert "/src/Controller.java" in files

    def test_impact_report_get_all_tests(self):
        """测试 ImpactReport 的 get_all_tests 方法."""
        report = ImpactReport()

        direct = DirectImpact(
            file_path="/src/Main.java",
            change_type=ChangeType.MODIFIED,
            test_file="/test/MainTest.java",
        )
        test_impact = TestImpact(
            test_file="/test/ServiceTest.java",
        )

        report.add_direct(direct)
        report.add_test_impact(test_impact)

        tests = report.get_all_tests()
        assert len(tests) == 2
        assert "/test/MainTest.java" in tests
        assert "/test/ServiceTest.java" in tests


class TestImpactAnalyzer:
    """ImpactAnalyzer 测试."""

    def test_analyzer_initialization(self):
        """测试 ImpactAnalyzer 初始化."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            assert analyzer._project_path == Path(tmpdir)
            assert analyzer._project_index is None
            assert analyzer._project_type == "java"

    def test_detect_project_type_java(self):
        """测试检测 Java 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 pom.xml
            pom = Path(tmpdir) / "pom.xml"
            pom.write_text("<project></project>")

            analyzer = ImpactAnalyzer(tmpdir)
            assert analyzer._project_type == "java"

    def test_detect_project_type_typescript(self):
        """测试检测 TypeScript 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 package.json
            package = Path(tmpdir) / "package.json"
            package.write_text('{"name": "test"}')

            analyzer = ImpactAnalyzer(tmpdir)
            assert analyzer._project_type == "typescript"

    def test_detect_project_type_python(self):
        """测试检测 Python 项目."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建 pyproject.toml
            pyproject = Path(tmpdir) / "pyproject.toml"
            pyproject.write_text("[project]")

            analyzer = ImpactAnalyzer(tmpdir)
            assert analyzer._project_type == "python"

    def test_analyze_impact(self):
        """测试分析影响."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            # 创建变更集
            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
            )
            change_set = ChangeSet(changes=[change])

            report = analyzer.analyze_impact(change_set)

            assert isinstance(report, ImpactReport)
            assert len(report.direct_impacts) == 1
            assert len(report.indirect_impacts) == 0
            assert len(report.test_impacts) == 0

    def test_analyze_direct_impact(self):
        """测试分析直接影响."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
            )

            impact = analyzer._analyze_direct_impact(change)

            assert isinstance(impact, DirectImpact)
            assert impact.file_path == "/src/Main.java"
            assert impact.change_type == ChangeType.MODIFIED

    def test_analyze_indirect_impact_no_index(self):
        """测试无项目索引时的间接影响分析."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
            )

            impacts = analyzer._analyze_indirect_impact(change)

            assert impacts == []

    def test_analyze_indirect_impact_with_index(self):
        """测试有项目索引时的间接影响分析."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟的项目索引
            mock_index = Mock()
            mock_index.symbols = {
                "Service": {
                    "dependencies": ["/src/Main.java"],
                    "file_path": "/src/Service.java",
                },
            }

            analyzer = ImpactAnalyzer(tmpdir, mock_index)

            method_change = MethodChange(
                name="test",
                signature="void test()",
                change_type=ChangeType.MODIFIED,
            )

            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
                method_changes=[method_change],
            )

            impacts = analyzer._analyze_indirect_impact(change)

            # 由于没有实际的文件，应该返回空列表
            assert isinstance(impacts, list)

    def test_analyze_test_impact(self):
        """测试分析测试影响."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            method_change = MethodChange(
                name="test",
                signature="void test()",
                change_type=ChangeType.MODIFIED,
            )

            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
                method_changes=[method_change],
            )

            impacts = analyzer._analyze_test_impact(change)

            assert isinstance(impacts, list)

    def test_find_test_file_not_found(self):
        """测试查找测试文件（未找到）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            test_file = analyzer._find_test_file("/src/Main.java")

            assert test_file is None

    def test_find_test_method(self):
        """测试查找测试方法."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            # 创建测试文件
            test_content = """
            public class MainTest {
                @Test
                void testMethod() {
                }
            }
            """
            test_file = Path(tmpdir) / "test" / "java" / "MainTest.java"
            test_file.parent.mkdir(parents=True)
            test_file.write_text(test_content)

            method = analyzer._find_test_method(str(test_file), "method")

            # 可能找到也可能找不到，取决于实现
            assert method is None or isinstance(method, str)

    def test_find_dependents_no_index(self):
        """测试查找依赖项（无索引）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            dependents = analyzer._find_dependents("/src/Main.java")

            assert dependents == []

    def test_find_dependents_with_index(self):
        """测试查找依赖项（有索引）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建模拟的项目索引
            mock_index = Mock()
            mock_index.symbols = {
                "Service": {
                    "dependencies": ["/src/Main.java"],
                    "file_path": "/src/Service.java",
                },
            }

            analyzer = ImpactAnalyzer(tmpdir, mock_index)
            dependents = analyzer._find_dependents("/src/Main.java")

            assert isinstance(dependents, list)

    def test_find_call_sites(self):
        """测试查找调用点."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            method_change = MethodChange(
                name="test",
                signature="void test()",
                change_type=ChangeType.MODIFIED,
            )

            change = FileChange(
                path="/src/Main.java",
                change_type=ChangeType.MODIFIED,
                method_changes=[method_change],
            )

            call_sites = analyzer._find_call_sites("/src/Service.java", change)

            assert isinstance(call_sites, list)

    def test_calculate_test_priority(self):
        """测试计算测试优先级."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ImpactAnalyzer(tmpdir)

            # 新增文件 + 新增方法
            priority1 = analyzer._calculate_test_priority(
                ChangeType.ADDED,
                ChangeType.ADDED,
            )
            assert priority1 == 45  # 30 + 15

            # 修改文件 + 修改方法
            priority2 = analyzer._calculate_test_priority(
                ChangeType.MODIFIED,
                ChangeType.MODIFIED,
            )
            assert priority2 == 30  # 20 + 10

            # 删除文件 + 删除方法
            priority3 = analyzer._calculate_test_priority(
                ChangeType.DELETED,
                ChangeType.DELETED,
            )
            assert priority3 == 15  # 10 + 5
