"""影响分析器."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ut_agent.selection.change_detector import (
    ChangeSet,
    FileChange,
    MethodChange,
    ChangeType,
)


@dataclass
class DirectImpact:
    """直接影响 - 变更文件本身."""
    file_path: str
    change_type: ChangeType
    method_changes: List[MethodChange] = field(default_factory=list)
    test_file: Optional[str] = None


@dataclass
class IndirectImpact:
    """间接影响 - 依赖变更文件的代码."""
    file_path: str
    reason: str
    call_sites: List[str] = field(default_factory=list)
    test_file: Optional[str] = None


@dataclass
class TestImpact:
    """测试影响 - 需要更新的测试."""
    test_file: str
    test_method: Optional[str] = None
    reason: str = ""
    priority: int = 0


@dataclass
class ImpactReport:
    """影响报告."""
    direct_impacts: List[DirectImpact] = field(default_factory=list)
    indirect_impacts: List[IndirectImpact] = field(default_factory=list)
    test_impacts: List[TestImpact] = field(default_factory=list)
    
    def add_direct(self, impact: DirectImpact) -> None:
        self.direct_impacts.append(impact)
    
    def add_indirect(self, impact: IndirectImpact) -> None:
        self.indirect_impacts.append(impact)
    
    def add_test_impact(self, impact: TestImpact) -> None:
        self.test_impacts.append(impact)
    
    def get_all_files(self) -> List[str]:
        files = set()
        for impact in self.direct_impacts:
            files.add(impact.file_path)
        for impact in self.indirect_impacts:
            files.add(impact.file_path)
        return list(files)
    
    def get_all_tests(self) -> List[str]:
        tests = set()
        for impact in self.test_impacts:
            tests.add(impact.test_file)
        for impact in self.direct_impacts:
            if impact.test_file:
                tests.add(impact.test_file)
        return list(tests)


class ImpactAnalyzer:
    """影响分析器 - 分析变更的影响范围."""
    
    TEST_DIR_PATTERNS = {
        "java": ["src/test/java", "test/java"],
        "typescript": ["test", "tests", "__tests__", "src/__tests__"],
        "python": ["tests", "test"],
    }
    
    TEST_FILE_PATTERNS = {
        "java": ["Test.java", "Tests.java"],
        "typescript": [".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx"],
        "python": ["test_", "_test.py"],
    }
    
    def __init__(self, project_path: str, project_index=None):
        self._project_path = Path(project_path)
        self._project_index = project_index
        self._project_type = self._detect_project_type()
    
    def _detect_project_type(self) -> str:
        if (self._project_path / "pom.xml").exists() or \
           (self._project_path / "build.gradle").exists():
            return "java"
        elif (self._project_path / "package.json").exists():
            return "typescript"
        elif (self._project_path / "pyproject.toml").exists() or \
             (self._project_path / "setup.py").exists():
            return "python"
        return "java"
    
    def analyze_impact(self, change_set: ChangeSet) -> ImpactReport:
        report = ImpactReport()
        
        for change in change_set.changes:
            direct = self._analyze_direct_impact(change)
            report.add_direct(direct)
            
            indirect = self._analyze_indirect_impact(change)
            report.indirect_impacts.extend(indirect)
            
            test_impacts = self._analyze_test_impact(change)
            report.test_impacts.extend(test_impacts)
        
        return report
    
    def _analyze_direct_impact(self, change: FileChange) -> DirectImpact:
        test_file = self._find_test_file(change.path)
        
        return DirectImpact(
            file_path=change.path,
            change_type=change.change_type,
            method_changes=change.method_changes,
            test_file=test_file,
        )
    
    def _analyze_indirect_impact(self, change: FileChange) -> List[IndirectImpact]:
        impacts = []
        
        if self._project_index is None:
            return impacts
        
        try:
            dependents = self._find_dependents(change.path)
            
            for dependent in dependents:
                call_sites = self._find_call_sites(dependent, change)
                
                if call_sites:
                    test_file = self._find_test_file(dependent)
                    impacts.append(IndirectImpact(
                        file_path=dependent,
                        reason=f"调用了变更的方法: {', '.join(call_sites[:3])}",
                        call_sites=call_sites,
                        test_file=test_file,
                    ))
        except Exception:
            pass
        
        return impacts
    
    def _analyze_test_impact(self, change: FileChange) -> List[TestImpact]:
        impacts = []
        
        test_file = self._find_test_file(change.path)
        if not test_file:
            return impacts
        
        for method_change in change.method_changes:
            test_method = self._find_test_method(
                test_file,
                method_change.name
            )
            
            if test_method:
                priority = self._calculate_test_priority(
                    change.change_type,
                    method_change.change_type
                )
                
                impacts.append(TestImpact(
                    test_file=test_file,
                    test_method=test_method,
                    reason=f"测试方法需要更新: {method_change.name}",
                    priority=priority,
                ))
        
        return impacts
    
    def _find_test_file(self, source_file: str) -> Optional[str]:
        source_path = Path(source_file)
        file_stem = source_path.stem
        
        test_patterns = self.TEST_FILE_PATTERNS.get(self._project_type, [])
        test_dirs = self.TEST_DIR_PATTERNS.get(self._project_type, [])
        
        for test_dir in test_dirs:
            test_path = self._project_path / test_dir
            
            if not test_path.exists():
                continue
            
            for pattern in test_patterns:
                if self._project_type == "java":
                    test_name = f"{file_stem}{pattern}"
                elif self._project_type == "python":
                    test_name = f"{pattern}{file_stem}.py"
                else:
                    test_name = f"{file_stem}{pattern}"
                
                for found in test_path.rglob(test_name):
                    return str(found)
        
        return None
    
    def _find_test_method(self, test_file: str, method_name: str) -> Optional[str]:
        try:
            content = Path(test_file).read_text(encoding="utf-8")
        except Exception:
            return None
        
        import re
        
        if self._project_type == "java":
            patterns = [
                rf'void\s+test{method_name}\w*\s*\(',
                rf'void\s+{method_name}\w*Test\s*\(',
                rf'void\s+\w*_when{method_name}\w*\s*\(',
                rf'@Test.*\n.*void\s+\w*{method_name}\w*\s*\(',
            ]
        else:
            patterns = [
                rf'(?:it|test)\s*\([\'"][^\'"]*{method_name}[^\'"]*[\'"]',
                rf'describe\s*\([\'"][^\'"]*{method_name}[^\'"]*[\'"]',
            ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                if self._project_type == "java":
                    method_match = re.search(r'void\s+(\w+)\s*\(', match.group(0))
                    if method_match:
                        return method_match.group(1)
                else:
                    return match.group(0)[:50]
        
        return None
    
    def _find_dependents(self, file_path: str) -> List[str]:
        if self._project_index is None:
            return []
        
        dependents = []
        
        try:
            for symbol, info in self._project_index.symbols.items():
                if file_path in str(info.get("dependencies", [])):
                    dependents.append(info.get("file_path", ""))
        except Exception:
            pass
        
        return list(set(dependents))
    
    def _find_call_sites(self, dependent_file: str, change: FileChange) -> List[str]:
        call_sites = []
        
        try:
            content = Path(self._project_path / dependent_file).read_text(
                encoding="utf-8"
            )
            
            for method_change in change.method_changes:
                if method_change.name in content:
                    call_sites.append(method_change.name)
        except Exception:
            pass
        
        return call_sites
    
    def _calculate_test_priority(
        self,
        file_change_type: ChangeType,
        method_change_type: ChangeType,
    ) -> int:
        priority = 0
        
        if file_change_type == ChangeType.ADDED:
            priority += 30
        elif file_change_type == ChangeType.MODIFIED:
            priority += 20
        elif file_change_type == ChangeType.DELETED:
            priority += 10
        
        if method_change_type == ChangeType.ADDED:
            priority += 15
        elif method_change_type == ChangeType.MODIFIED:
            priority += 10
        elif method_change_type == ChangeType.DELETED:
            priority += 5
        
        return priority
