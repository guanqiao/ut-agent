"""Analyzer Agent - 代码分析专家."""

import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from ut_agent.agents.base import (
    BaseAgent,
    AgentContext,
    AgentResult,
    AgentCapability,
    AgentStatus,
)
from ut_agent.tools.code_analyzer import (
    analyze_java_file,
    analyze_ts_file,
    extract_dependencies,
    find_testable_methods,
)
from ut_agent.tools.cross_file_analyzer import CrossFileAnalyzer, ProjectIndex


class ComplexityAnalyzer:
    """代码复杂度分析器."""
    
    @staticmethod
    def calculate_cyclomatic_complexity(method_info: Dict[str, Any]) -> int:
        complexity = 1
        content = method_info.get("content", "")
        
        control_keywords = ["if", "else", "for", "while", "case", "catch", "&&", "||", "?"]
        for keyword in control_keywords:
            complexity += content.count(f"{keyword} ") + content.count(f"{keyword}(")
        
        return complexity
    
    @staticmethod
    def calculate_cognitive_complexity(method_info: Dict[str, Any]) -> int:
        complexity = 0
        content = method_info.get("content", "")
        nesting_level = 0
        
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            
            if any(kw in stripped for kw in ["if", "for", "while", "catch"]):
                complexity += (nesting_level + 1)
                nesting_level += 1
            elif "}" in stripped:
                nesting_level = max(0, nesting_level - 1)
            elif "else" in stripped or "elif" in stripped:
                complexity += 1
        
        return complexity


class RiskIdentifier:
    """风险识别器."""
    
    RISK_PATTERNS = {
        "null_pointer": [
            r"\.get\([^)]+\)\s*\.",
            r"\[\s*\w+\s*\]\s*\.",
            r"return\s+\w+\s*;",
        ],
        "boundary": [
            r"for\s*\(\s*\w+\s+\w+\s*=\s*0",
            r"for\s*\(\s*let\s+\w+\s*=\s*0",
            r"\.length\s*-\s*1",
            r"\.size\(\)\s*-\s*1",
        ],
        "exception": [
            r"try\s*\{",
            r"catch\s*\(",
            r"throw\s+",
            r"raise\s+",
        ],
        "concurrency": [
            r"synchronized",
            r"volatile",
            r"Thread\s*\(",
            r"async\s+",
            r"await\s+",
            r"Promise\.",
        ],
    }
    
    @classmethod
    def identify_risks(cls, method_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        import re
        
        risks = []
        content = method_info.get("content", method_info.get("signature", ""))
        
        for risk_type, patterns in cls.RISK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    risks.append({
                        "type": risk_type,
                        "severity": "medium" if risk_type in ["null_pointer", "boundary"] else "high",
                        "description": f"Potential {risk_type.replace('_', ' ')} risk",
                        "location": method_info.get("name", "unknown"),
                    })
        
        return risks


class TestStrategyRecommender:
    """测试策略推荐器."""
    
    @staticmethod
    def recommend(file_analysis: Dict[str, Any], risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        strategies = []
        
        language = file_analysis.get("language", "java")
        methods = file_analysis.get("methods", file_analysis.get("functions", []))
        
        has_database = any(
            "repository" in str(m).lower() or "dao" in str(m).lower()
            for m in methods
        )
        has_external_api = any(
            "client" in str(m).lower() or "api" in str(m).lower() or "http" in str(m).lower()
            for m in methods
        )
        
        strategies.append({
            "type": "unit",
            "priority": "high",
            "description": "基础单元测试覆盖所有公共方法",
            "coverage_target": 80,
        })
        
        if has_database:
            strategies.append({
                "type": "integration",
                "priority": "medium",
                "description": "数据库集成测试，使用测试容器或内存数据库",
                "coverage_target": 60,
            })
        
        if has_external_api:
            strategies.append({
                "type": "contract",
                "priority": "medium",
                "description": "API 契约测试，验证接口兼容性",
                "coverage_target": 50,
            })
        
        high_risks = [r for r in risks if r.get("severity") == "high"]
        if high_risks:
            strategies.append({
                "type": "edge_case",
                "priority": "high",
                "description": f"针对 {len(high_risks)} 个高风险点进行边界测试",
                "risks": high_risks,
            })
        
        return {
            "strategies": strategies,
            "recommended_framework": "JUnit 5 + Mockito" if language == "java" else "Vitest",
            "mock_strategy": "constructor_injection" if language == "java" else "vi.fn()",
        }


class AnalyzerAgent(BaseAgent):
    """代码分析 Agent."""
    
    name = "analyzer"
    description = "代码分析专家 - 解析源代码结构、依赖关系、复杂度和风险点"
    capabilities = [
        AgentCapability.AST_PARSE,
        AgentCapability.DEPENDENCY_ANALYSIS,
        AgentCapability.COMPLEXITY_ANALYSIS,
        AgentCapability.RISK_IDENTIFICATION,
        AgentCapability.TEST_STRATEGY,
    ]
    
    def __init__(
        self,
        memory: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        project_index: Optional[ProjectIndex] = None,
    ):
        super().__init__(memory, config)
        self._complexity_analyzer = ComplexityAnalyzer()
        self._risk_identifier = RiskIdentifier()
        self._test_strategy_recommender = TestStrategyRecommender()
        self._project_index = project_index
        self._cross_file_analyzer: Optional[CrossFileAnalyzer] = None
    
    def set_project_index(self, project_index: ProjectIndex) -> None:
        self._project_index = project_index
        self._cross_file_analyzer = CrossFileAnalyzer(project_index)
    
    async def execute(self, context: AgentContext) -> AgentResult:
        start_time = time.time()
        self._status = AgentStatus.RUNNING
        
        errors = []
        warnings = []
        
        try:
            source_file = context.source_file
            if not source_file:
                source_file = context.config.get("source_file", "")
            
            if not source_file:
                return AgentResult(
                    success=False,
                    agent_name=self.name,
                    task_id=context.task_id,
                    errors=["No source file specified"],
                )
            
            project_type = context.project_type
            if not project_type:
                project_type = self._detect_project_type(source_file)
            
            file_analysis = await self._analyze_file(source_file, project_type)
            
            dependencies = await self._analyze_dependencies(file_analysis, context.project_path)
            
            complexity_metrics = self._analyze_complexity(file_analysis)
            
            risks = self._identify_risks(file_analysis)
            
            test_strategy = self._recommend_test_strategy(file_analysis, risks)
            
            testable_methods = find_testable_methods(file_analysis)
            
            mock_suggestions = await self._suggest_mocks(file_analysis, dependencies)
            
            result_data = {
                "file_analysis": file_analysis,
                "dependencies": dependencies,
                "complexity_metrics": complexity_metrics,
                "risks": risks,
                "test_strategy": test_strategy,
                "testable_methods": testable_methods,
                "mock_suggestions": mock_suggestions,
            }
            
            self.remember(f"analysis:{source_file}", result_data)
            
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = AgentStatus.SUCCESS
            
            result = AgentResult(
                success=True,
                agent_name=self.name,
                task_id=context.task_id,
                data=result_data,
                warnings=warnings,
                metrics={
                    "duration_ms": duration_ms,
                    "method_count": len(testable_methods),
                    "risk_count": len(risks),
                    "complexity_avg": complexity_metrics.get("average_complexity", 0),
                },
                duration_ms=duration_ms,
            )
            
            self.record_execution(result)
            return result
            
        except Exception as e:
            self._status = AgentStatus.FAILED
            errors.append(str(e))
            return AgentResult(
                success=False,
                agent_name=self.name,
                task_id=context.task_id,
                errors=errors,
            )
    
    def _detect_project_type(self, file_path: str) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        if suffix == ".java":
            return "java"
        elif suffix == ".vue":
            return "vue"
        elif suffix in [".tsx", ".jsx"]:
            return "react"
        elif suffix in [".ts", ".js"]:
            return "typescript"
        elif suffix == ".py":
            return "python"
        else:
            return "unknown"
    
    async def _analyze_file(self, file_path: str, project_type: str) -> Dict[str, Any]:
        if project_type == "java":
            return analyze_java_file(file_path)
        elif project_type in ["vue", "react", "typescript"]:
            return analyze_ts_file(file_path)
        else:
            return {
                "file_path": file_path,
                "language": project_type,
                "error": f"Unsupported project type: {project_type}",
            }
    
    async def _analyze_dependencies(
        self,
        file_analysis: Dict[str, Any],
        project_path: str,
    ) -> Dict[str, Any]:
        direct_deps = extract_dependencies(file_analysis)
        
        result = {
            "direct": direct_deps,
            "transitive": [],
            "internal": [],
            "external": [],
        }
        
        if self._cross_file_analyzer and project_path:
            try:
                file_path = file_analysis.get("file_path", "")
                cross_deps = self._cross_file_analyzer.analyze_dependencies(file_path)
                result["transitive"] = cross_deps.get("transitive", [])
                result["internal"] = cross_deps.get("internal", [])
                result["external"] = cross_deps.get("external", [])
            except Exception:
                pass
        
        return result
    
    def _analyze_complexity(self, file_analysis: Dict[str, Any]) -> Dict[str, Any]:
        methods = file_analysis.get("methods", file_analysis.get("functions", []))
        
        complexities = []
        for method in methods:
            cc = self._complexity_analyzer.calculate_cyclomatic_complexity(method)
            cog = self._complexity_analyzer.calculate_cognitive_complexity(method)
            complexities.append({
                "method": method.get("name", "unknown"),
                "cyclomatic": cc,
                "cognitive": cog,
            })
        
        if complexities:
            avg_cyclomatic = sum(c["cyclomatic"] for c in complexities) / len(complexities)
            avg_cognitive = sum(c["cognitive"] for c in complexities) / len(complexities)
        else:
            avg_cyclomatic = 0
            avg_cognitive = 0
        
        return {
            "methods": complexities,
            "average_complexity": avg_cyclomatic,
            "average_cognitive": avg_cognitive,
            "high_complexity_methods": [
                c for c in complexities if c["cyclomatic"] > 10
            ],
        }
    
    def _identify_risks(self, file_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        methods = file_analysis.get("methods", file_analysis.get("functions", []))
        
        all_risks = []
        for method in methods:
            risks = self._risk_identifier.identify_risks(method)
            all_risks.extend(risks)
        
        return all_risks
    
    def _recommend_test_strategy(
        self,
        file_analysis: Dict[str, Any],
        risks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return self._test_strategy_recommender.recommend(file_analysis, risks)
    
    async def _suggest_mocks(
        self,
        file_analysis: Dict[str, Any],
        dependencies: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        suggestions = []
        
        fields = file_analysis.get("fields", [])
        for field in fields:
            field_type = field.get("type", "")
            field_name = field.get("name", "")
            
            if field.get("access") == "private" and field_type:
                suggestions.append({
                    "field_name": field_name,
                    "field_type": field_type,
                    "mock_type": "mock",
                    "reason": "Private dependency should be mocked",
                })
        
        for dep in dependencies.get("external", []):
            suggestions.append({
                "dependency": dep,
                "mock_type": "mock",
                "reason": "External dependency should be mocked",
            })
        
        return suggestions
