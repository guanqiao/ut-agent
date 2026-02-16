"""变异测试分析器测试"""

import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import pytest

from ut_agent.tools.mutation_analyzer import (
    MutationStatus,
    Mutation,
    MutationReport,
    MutationAnalyzer,
    configure_pit_maven,
    configure_pit_gradle,
)


class TestMutationStatus:
    """测试变异状态枚举"""
    
    def test_mutation_status_values(self):
        """测试变异状态值"""
        assert MutationStatus.KILLED.value == "KILLED"
        assert MutationStatus.SURVIVED.value == "SURVIVED"
        assert MutationStatus.TIMED_OUT.value == "TIMED_OUT"
        assert MutationStatus.NO_COVERAGE.value == "NO_COVERAGE"
        assert MutationStatus.RUN_ERROR.value == "RUN_ERROR"


class TestMutation:
    """测试变异数据类"""
    
    def test_mutation_creation(self):
        """测试变异创建"""
        mutation = Mutation(
            mutation_id="TestClass.testMethod:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod",
            line_number=42,
            mutator="NEGATE_CONDITIONALS",
            description="Negated conditional",
            status=MutationStatus.KILLED,
            killing_test="TestClassTest.testTestMethod",
        )
        
        assert mutation.mutation_id == "TestClass.testMethod:42"
        assert mutation.source_file == "TestClass.java"
        assert mutation.class_name == "TestClass"
        assert mutation.method_name == "testMethod"
        assert mutation.line_number == 42
        assert mutation.mutator == "NEGATE_CONDITIONALS"
        assert mutation.description == "Negated conditional"
        assert mutation.status == MutationStatus.KILLED
        assert mutation.killing_test == "TestClassTest.testTestMethod"
    
    def test_mutation_to_dict(self):
        """测试变异转换为字典"""
        mutation = Mutation(
            mutation_id="TestClass.testMethod:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod",
            line_number=42,
            mutator="NEGATE_CONDITIONALS",
            description="Negated conditional",
            status=MutationStatus.KILLED,
            killing_test="TestClassTest.testTestMethod",
        )
        
        mutation_dict = mutation.to_dict()
        assert mutation_dict["mutation_id"] == "TestClass.testMethod:42"
        assert mutation_dict["source_file"] == "TestClass.java"
        assert mutation_dict["class_name"] == "TestClass"
        assert mutation_dict["method_name"] == "testMethod"
        assert mutation_dict["line_number"] == 42
        assert mutation_dict["mutator"] == "NEGATE_CONDITIONALS"
        assert mutation_dict["description"] == "Negated conditional"
        assert mutation_dict["status"] == "KILLED"
        assert mutation_dict["killing_test"] == "TestClassTest.testTestMethod"


class TestMutationReport:
    """测试变异报告数据类"""
    
    def test_mutation_report_creation(self):
        """测试变异报告创建"""
        report = MutationReport()
        assert report.total_mutations == 0
        assert report.killed == 0
        assert report.survived == 0
        assert report.timed_out == 0
        assert report.no_coverage == 0
        assert report.run_error == 0
        assert report.mutation_coverage == 0.0
        assert report.test_strength == 0.0
        assert report.mutations == []
    
    def test_kill_rate_property(self):
        """测试杀死率属性"""
        # 测试空报告
        report = MutationReport()
        assert report.kill_rate == 0.0
        
        # 测试有数据的报告
        report = MutationReport(
            total_mutations=10,
            killed=7,
            survived=2,
            timed_out=1,
        )
        assert report.kill_rate == 70.0  # 7/10 * 100
    
    def test_survived_mutations_property(self):
        """测试幸存变异属性"""
        # 创建测试变异
        killed_mutation = Mutation(
            mutation_id="TestClass.testMethod1:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod1",
            line_number=42,
            mutator="NEGATE_CONDITIONALS",
            description="Negated conditional",
            status=MutationStatus.KILLED,
        )
        
        survived_mutation = Mutation(
            mutation_id="TestClass.testMethod2:45",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod2",
            line_number=45,
            mutator="CONDITIONALS_BOUNDARY",
            description="Boundary condition",
            status=MutationStatus.SURVIVED,
        )
        
        # 创建报告
        report = MutationReport(
            mutations=[killed_mutation, survived_mutation],
            total_mutations=2,
            killed=1,
            survived=1,
        )
        
        # 验证幸存变异
        survived_mutations = report.survived_mutations
        assert len(survived_mutations) == 1
        assert survived_mutations[0] == survived_mutation
    
    def test_to_dict(self):
        """测试报告转换为字典"""
        # 创建测试变异
        mutation = Mutation(
            mutation_id="TestClass.testMethod:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod",
            line_number=42,
            mutator="NEGATE_CONDITIONALS",
            description="Negated conditional",
            status=MutationStatus.KILLED,
        )
        
        # 创建报告
        report = MutationReport(
            total_mutations=1,
            killed=1,
            survived=0,
            timed_out=0,
            no_coverage=0,
            run_error=0,
            mutation_coverage=100.0,
            test_strength=100.0,
            mutations=[mutation],
        )
        
        # 验证转换结果
        report_dict = report.to_dict()
        assert report_dict["total_mutations"] == 1
        assert report_dict["killed"] == 1
        assert report_dict["survived"] == 0
        assert report_dict["timed_out"] == 0
        assert report_dict["no_coverage"] == 0
        assert report_dict["run_error"] == 0
        assert report_dict["mutation_coverage"] == 100.0
        assert report_dict["test_strength"] == 100.0
        assert report_dict["kill_rate"] == 100.0
        assert len(report_dict["survived_mutations"]) == 0


class TestMutationAnalyzer:
    """测试变异分析器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = Path(self.temp_dir.name)
    
    def teardown_method(self):
        """清理测试环境"""
        self.temp_dir.cleanup()
    
    def test_detect_build_tool_maven(self):
        """测试检测 Maven 构建工具"""
        # 创建 pom.xml 文件
        (self.project_path / "pom.xml").write_text('<project></project>')
        
        analyzer = MutationAnalyzer(str(self.project_path))
        assert analyzer.detect_build_tool() == "maven"
    
    def test_detect_build_tool_gradle(self):
        """测试检测 Gradle 构建工具"""
        # 创建 build.gradle 文件
        (self.project_path / "build.gradle").write_text('plugins { id "java" }')
        
        analyzer = MutationAnalyzer(str(self.project_path))
        assert analyzer.detect_build_tool() == "gradle"
    
    def test_detect_build_tool_gradle_kts(self):
        """测试检测 Gradle Kotlin DSL 构建工具"""
        # 创建 build.gradle.kts 文件
        (self.project_path / "build.gradle.kts").write_text('plugins { java }')
        
        analyzer = MutationAnalyzer(str(self.project_path))
        assert analyzer.detect_build_tool() == "gradle"
    
    def test_detect_build_tool_unknown(self):
        """测试检测未知构建工具"""
        analyzer = MutationAnalyzer(str(self.project_path))
        assert analyzer.detect_build_tool() == "unknown"
    
    @mock.patch('subprocess.run')
    def test_run_maven_pit(self, mock_run):
        """测试运行 Maven PIT"""
        # 创建 pom.xml 文件
        (self.project_path / "pom.xml").write_text('<project></project>')
        
        analyzer = MutationAnalyzer(
            str(self.project_path),
            target_classes=["com.example.*"],
            target_tests=["*Test"],
            mutators=["DEFAULTS"],
            threads=4,
            timeout=300,
        )
        
        # 模拟 PIT 报告文件
        pit_report_dir = self.project_path / "target" / "pit-reports" / "com.example"
        pit_report_dir.mkdir(parents=True, exist_ok=True)
        pit_report_file = pit_report_dir / "mutations.xml"
        
        # 创建简单的 PIT 报告
        pit_report_content = """
        <mutationResult>
            <mutation>
                <sourceFile>TestClass.java</sourceFile>
                <mutatedClass>TestClass</mutatedClass>
                <mutatedMethod>testMethod</mutatedMethod>
                <lineNumber>42</lineNumber>
                <mutator>NEGATE_CONDITIONALS</mutator>
                <description>Negated conditional</description>
                <status>KILLED</status>
                <killingTest>TestClassTest.testTestMethod</killingTest>
            </mutation>
        </mutationResult>
        """
        pit_report_file.write_text(pit_report_content)
        
        # 运行变异测试
        report = analyzer.run_mutation_tests()
        
        # 验证结果
        assert report.total_mutations == 1
        assert report.killed == 1
        assert report.mutation_coverage == 100.0
        assert report.test_strength == 100.0
    
    def test_parse_mutation_element(self):
        """测试解析变异元素"""
        analyzer = MutationAnalyzer(str(self.project_path))
        
        # 创建测试 XML 元素
        xml_content = """
        <mutation>
            <sourceFile>TestClass.java</sourceFile>
            <mutatedClass>TestClass</mutatedClass>
            <mutatedMethod>testMethod</mutatedMethod>
            <lineNumber>42</lineNumber>
            <mutator>NEGATE_CONDITIONALS</mutator>
            <description>Negated conditional</description>
            <status>KILLED</status>
            <killingTest>TestClassTest.testTestMethod</killingTest>
        </mutation>
        """
        root = ET.fromstring(xml_content)
        
        # 解析元素
        mutation = analyzer._parse_mutation_element(root)
        
        # 验证结果
        assert mutation is not None
        assert mutation.mutation_id == "TestClass.testMethod:42"
        assert mutation.source_file == "TestClass.java"
        assert mutation.class_name == "TestClass"
        assert mutation.method_name == "testMethod"
        assert mutation.line_number == 42
        assert mutation.mutator == "NEGATE_CONDITIONALS"
        assert mutation.description == "Negated conditional"
        assert mutation.status == MutationStatus.KILLED
        assert mutation.killing_test == "TestClassTest.testTestMethod"
    
    def test_generate_test_suggestion(self):
        """测试生成测试建议"""
        analyzer = MutationAnalyzer(str(self.project_path))
        
        # 创建测试变异
        mutation = Mutation(
            mutation_id="TestClass.testMethod:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod",
            line_number=42,
            mutator="NEGATE_CONDITIONALS",
            description="Negated conditional",
            status=MutationStatus.SURVIVED,
        )
        
        # 生成建议
        suggestion = analyzer._generate_test_suggestion(mutation)
        assert "Add test case to verify the opposite condition" in suggestion
        assert "testMethod()" in suggestion
    
    def test_generate_test_suggestion_default(self):
        """测试生成默认测试建议"""
        analyzer = MutationAnalyzer(str(self.project_path))
        
        # 创建测试变异（使用未知的变异器）
        mutation = Mutation(
            mutation_id="TestClass.testMethod:42",
            source_file="TestClass.java",
            class_name="TestClass",
            method_name="testMethod",
            line_number=42,
            mutator="UNKNOWN_MUTATOR",
            description="Unknown mutation",
            status=MutationStatus.SURVIVED,
        )
        
        # 生成建议
        suggestion = analyzer._generate_test_suggestion(mutation)
        assert "Add test case to cover mutation" in suggestion
        assert "testMethod()" in suggestion
        assert "line 42" in suggestion
    
    def test_get_report_summary_no_report(self):
        """测试获取无报告时的摘要"""
        analyzer = MutationAnalyzer(str(self.project_path))
        summary = analyzer.get_report_summary()
        assert "No mutation report available" in summary
    
    def test_configure_pit_maven(self):
        """测试配置 Maven PIT"""
        # 创建 pom.xml 文件
        pom_path = self.project_path / "pom.xml"
        pom_path.write_text('<project><build><plugins></plugins></build></project>')
        
        # 配置 PIT
        configure_pit_maven(pom_path)
        
        # 验证配置
        content = pom_path.read_text()
        assert "pitest-maven" in content
        assert "org.pitest" in content
    
    def test_configure_pit_gradle(self):
        """测试配置 Gradle PIT"""
        # 创建 build.gradle 文件
        build_path = self.project_path / "build.gradle"
        build_path.write_text('plugins { id "java" }')
        
        # 配置 PIT
        configure_pit_gradle(build_path)
        
        # 验证配置
        content = build_path.read_text()
        assert "pitest" in content
        assert "info.solidsoft.pitest" in content


if __name__ == "__main__":
    pytest.main([__file__])
