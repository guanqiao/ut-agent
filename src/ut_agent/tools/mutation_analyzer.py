"""变异测试分析模块.

集成 PIT (Pitest) 变异测试，评估测试有效性并建议补充测试。
"""

import json
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MutationStatus(Enum):
    KILLED = "KILLED"
    SURVIVED = "SURVIVED"
    TIMED_OUT = "TIMED_OUT"
    NO_COVERAGE = "NO_COVERAGE"
    RUN_ERROR = "RUN_ERROR"


@dataclass
class Mutation:
    mutation_id: str
    source_file: str
    class_name: str
    method_name: str
    line_number: int
    mutator: str
    description: str
    status: MutationStatus
    killing_test: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "source_file": self.source_file,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "line_number": self.line_number,
            "mutator": self.mutator,
            "description": self.description,
            "status": self.status.value,
            "killing_test": self.killing_test,
        }


@dataclass
class MutationReport:
    total_mutations: int = 0
    killed: int = 0
    survived: int = 0
    timed_out: int = 0
    no_coverage: int = 0
    run_error: int = 0
    mutation_coverage: float = 0.0
    test_strength: float = 0.0
    mutations: List[Mutation] = field(default_factory=list)
    
    @property
    def kill_rate(self) -> float:
        if self.total_mutations == 0:
            return 0.0
        return (self.killed / self.total_mutations) * 100
    
    @property
    def survived_mutations(self) -> List[Mutation]:
        return [m for m in self.mutations if m.status == MutationStatus.SURVIVED]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_mutations": self.total_mutations,
            "killed": self.killed,
            "survived": self.survived,
            "timed_out": self.timed_out,
            "no_coverage": self.no_coverage,
            "run_error": self.run_error,
            "mutation_coverage": round(self.mutation_coverage, 2),
            "test_strength": round(self.test_strength, 2),
            "kill_rate": round(self.kill_rate, 2),
            "survived_mutations": [m.to_dict() for m in self.survived_mutations],
        }


class MutationAnalyzer:
    
    DEFAULT_MUTATORS = [
        "DEFAULTS",
        "NON_VOID",
        "VOID",
        "RETURN_VALS",
        "NEGATE_CONDITIONALS",
        "CONDITIONALS_BOUNDARY",
        "INCREMENTS",
        "INVERT_NEGS",
        "MATH",
        "EMPTY_RETURNS",
    ]
    
    def __init__(
        self,
        project_path: str,
        target_classes: Optional[List[str]] = None,
        target_tests: Optional[List[str]] = None,
        mutators: Optional[List[str]] = None,
        timeout: int = 300,
        threads: int = 4,
    ):
        self.project_path = Path(project_path)
        self.target_classes = target_classes
        self.target_tests = target_tests
        self.mutators = mutators or self.DEFAULT_MUTATORS
        self.timeout = timeout
        self.threads = threads
        self._report: Optional[MutationReport] = None
    
    def detect_build_tool(self) -> str:
        if (self.project_path / "pom.xml").exists():
            return "maven"
        if (self.project_path / "build.gradle").exists() or (self.project_path / "build.gradle.kts").exists():
            return "gradle"
        return "unknown"
    
    def run_mutation_tests(self) -> MutationReport:
        build_tool = self.detect_build_tool()
        
        if build_tool == "maven":
            self._run_maven_pit()
        elif build_tool == "gradle":
            self._run_gradle_pit()
        else:
            raise ValueError(f"Unsupported build tool: {build_tool}")
        
        self._report = self._parse_pit_report()
        return self._report
    
    def _run_maven_pit(self) -> None:
        cmd = [
            "mvn",
            "org.pitest:pitest-maven:mutationCoverage",
            f"-DtargetClasses={','.join(self.target_classes or ['*'])}",
            f"-DtargetTests={','.join(self.target_tests or ['*Test'])}",
            f"-Dmutators={','.join(self.mutators)}",
            f"-Dthreads={self.threads}",
            f"-DtimeoutConstant={self.timeout * 1000}",
            "-DoutputFormats=XML,HTML",
        ]
        
        subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            timeout=self.timeout * 2,
        )
    
    def _run_gradle_pit(self) -> None:
        cmd = [
            "./gradlew",
            "pitest",
            f"--targetClasses={','.join(self.target_classes or ['*'])}",
            f"--targetTests={','.join(self.target_tests or ['*Test'])}",
            f"--mutators={','.join(self.mutators)}",
            f"--threads={self.threads}",
            f"--timeout={self.timeout}",
        ]
        
        subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            timeout=self.timeout * 2,
        )
    
    def _parse_pit_report(self) -> MutationReport:
        report = MutationReport()
        
        xml_paths = [
            self.project_path / "target" / "pit-reports" / "mutations.xml",
            self.project_path / "target" / "pit-reports" / "*" / "mutations.xml",
            self.project_path / "build" / "reports" / "pitest" / "mutations.xml",
        ]
        
        xml_path = None
        for path in xml_paths:
            if path.exists():
                xml_path = path
                break
            parent = path.parent
            if parent.exists() and parent.is_dir():
                for child in parent.iterdir():
                    if child.is_dir() and (child / "mutations.xml").exists():
                        xml_path = child / "mutations.xml"
                        break
        
        if not xml_path or not xml_path.exists():
            return report
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            for mutation_elem in root.findall(".//mutation"):
                mutation = self._parse_mutation_element(mutation_elem)
                if mutation:
                    report.mutations.append(mutation)
                    report.total_mutations += 1
                    
                    if mutation.status == MutationStatus.KILLED:
                        report.killed += 1
                    elif mutation.status == MutationStatus.SURVIVED:
                        report.survived += 1
                    elif mutation.status == MutationStatus.TIMED_OUT:
                        report.timed_out += 1
                    elif mutation.status == MutationStatus.NO_COVERAGE:
                        report.no_coverage += 1
                    elif mutation.status == MutationStatus.RUN_ERROR:
                        report.run_error += 1
            
            covered_mutations = report.killed + report.survived + report.timed_out
            if covered_mutations > 0:
                report.mutation_coverage = (report.killed / covered_mutations) * 100
            
            if report.total_mutations > 0:
                report.test_strength = (report.killed / report.total_mutations) * 100
            
        except Exception as e:
            print(f"Error parsing PIT report: {e}")
        
        return report
    
    def _parse_mutation_element(self, elem: ET.Element) -> Optional[Mutation]:
        try:
            source_file = elem.findtext("sourceFile", "")
            class_name = elem.findtext("mutatedClass", "")
            method_name = elem.findtext("mutatedMethod", "")
            line_number = int(elem.findtext("lineNumber", "0"))
            mutator = elem.findtext("mutator", "")
            description = elem.findtext("description", "")
            status_str = elem.findtext("status", "NO_COVERAGE")
            killing_test = elem.findtext("killingTest")
            
            status = MutationStatus(status_str)
            
            return Mutation(
                mutation_id=f"{class_name}.{method_name}:{line_number}",
                source_file=source_file,
                class_name=class_name,
                method_name=method_name,
                line_number=line_number,
                mutator=mutator,
                description=description,
                status=status,
                killing_test=killing_test,
            )
        except Exception:
            return None
    
    def get_survived_mutations(self) -> List[Mutation]:
        if not self._report:
            self._report = self._parse_pit_report()
        return self._report.survived_mutations if self._report else []
    
    def generate_test_suggestions(self) -> List[Dict[str, Any]]:
        suggestions = []
        survived = self.get_survived_mutations()
        
        for mutation in survived:
            suggestion = {
                "source_file": mutation.source_file,
                "class_name": mutation.class_name,
                "method_name": mutation.method_name,
                "line_number": mutation.line_number,
                "mutation_type": mutation.mutator,
                "description": mutation.description,
                "suggested_test": self._generate_test_suggestion(mutation),
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    def _generate_test_suggestion(self, mutation: Mutation) -> str:
        suggestions = {
            "NEGATE_CONDITIONALS": f"Add test case to verify the opposite condition in {mutation.method_name}()",
            "CONDITIONALS_BOUNDARY": f"Add boundary test case for {mutation.method_name}() at line {mutation.line_number}",
            "INCREMENTS": f"Add test case to verify increment/decrement behavior in {mutation.method_name}()",
            "INVERT_NEGS": f"Add test case with negative values for {mutation.method_name}()",
            "MATH": f"Add test case to verify mathematical operation in {mutation.method_name}()",
            "VOID": f"Add test case to verify side effects in {mutation.method_name}()",
            "RETURN_VALS": f"Add test case to verify return value of {mutation.method_name}()",
            "EMPTY_RETURNS": f"Add test case to verify empty return handling in {mutation.method_name}()",
        }
        
        return suggestions.get(
            mutation.mutator,
            f"Add test case to cover mutation in {mutation.method_name}() at line {mutation.line_number}",
        )
    
    def get_report_summary(self) -> str:
        if not self._report:
            return "No mutation report available. Run mutation tests first."
        
        r = self._report
        return f"""
Mutation Testing Report Summary
===============================
Total Mutations: {r.total_mutations}
Killed: {r.killed} ({r.kill_rate:.1f}%)
Survived: {r.survived}
Timed Out: {r.timed_out}
No Coverage: {r.no_coverage}
Run Error: {r.run_error}

Mutation Coverage: {r.mutation_coverage:.1f}%
Test Strength: {r.test_strength:.1f}%

Survived Mutations: {len(r.survived_mutations)}
"""


def configure_pit_maven(pom_path: Path, target_classes: str = "*", target_tests: str = "*Test") -> None:
    """Configure PIT plugin in Maven pom.xml."""
    pit_plugin = f'''
    <plugin>
        <groupId>org.pitest</groupId>
        <artifactId>pitest-maven</artifactId>
        <version>1.15.3</version>
        <configuration>
            <targetClasses>
                <param>{target_classes}</param>
            </targetClasses>
            <targetTests>
                <param>{target_tests}</param>
            </targetTests>
            <mutators>
                <mutator>DEFAULTS</mutator>
            </mutators>
            <outputFormats>
                <format>XML</format>
                <format>HTML</format>
            </outputFormats>
        </configuration>
    </plugin>
'''
    
    if not pom_path.exists():
        return
    
    content = pom_path.read_text()
    if "pitest-maven" in content:
        return
    
    if "</plugins>" in content:
        content = content.replace("</plugins>", f"{pit_plugin}\n    </plugins>")
        pom_path.write_text(content)


def configure_pit_gradle(build_path: Path) -> None:
    """Configure PIT plugin in Gradle build file."""
    pit_config = '''
plugins {
    id 'info.solidsoft.pitest' version '1.15.0'
}

pitest {
    targetClasses = ['*']
    targetTests = ['*Test']
    mutators = ['DEFAULTS']
    outputFormats = ['XML', 'HTML']
}
'''
    
    if not build_path.exists():
        return
    
    content = build_path.read_text()
    if "pitest" in content:
        return
    
    if "plugins {" in content:
        content = content.replace(
            "plugins {",
            "plugins {\n    id 'info.solidsoft.pitest' version '1.15.0'"
        )
    
    build_path.write_text(content + "\n" + pit_config)
