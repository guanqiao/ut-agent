"""CI 运行器模块."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ut_agent.ci.reporter import CIReporter, CIResult
from ut_agent.graph import create_test_generation_graph, AgentState
from ut_agent.tools.coverage_analyzer import (
    parse_jacoco_report,
    parse_istanbul_report,
    identify_coverage_gaps,
)


class CIRunner:
    def __init__(
        self,
        project_path: str,
        project_type: str = "auto",
        coverage_target: float = 80.0,
        max_iterations: int = 5,
        llm_provider: str = "openai",
        output_format: str = "json",
        output_file: Optional[str] = None,
        fail_on_coverage: bool = False,
        dry_run: bool = False,
        incremental: bool = False,
        base_ref: Optional[str] = None,
    ):
        self.project_path = Path(project_path)
        self.project_type = project_type
        self.coverage_target = coverage_target
        self.max_iterations = max_iterations
        self.llm_provider = llm_provider
        self.dry_run = dry_run
        self.incremental = incremental
        self.base_ref = base_ref
        
        self.reporter = CIReporter(
            output_format=output_format,
            output_file=Path(output_file) if output_file else None,
            fail_on_coverage=fail_on_coverage,
            github_output=self._is_github_actions(),
        )
    
    def _is_github_actions(self) -> bool:
        return os.environ.get("GITHUB_ACTIONS", "false").lower() == "true"
    
    def _is_gitlab_ci(self) -> bool:
        return os.environ.get("GITLAB_CI", "false").lower() == "true"
    
    def _detect_project_type(self) -> str:
        if self.project_type != "auto":
            return self.project_type
        
        if (self.project_path / "pom.xml").exists():
            return "java"
        if (self.project_path / "build.gradle").exists() or (self.project_path / "build.gradle.kts").exists():
            return "java"
        if (self.project_path / "package.json").exists():
            package_json = json.loads((self.project_path / "package.json").read_text())
            deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
            if "vue" in deps:
                return "vue"
            if "react" in deps:
                return "react"
            return "typescript"
        return "java"
    
    def _get_changed_files(self) -> List[str]:
        if not self.incremental:
            return []
        
        changed_files = []
        
        try:
            if self._is_github_actions():
                base_ref = self.base_ref or os.environ.get("GITHUB_BASE_REF", "main")
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"origin/{base_ref}", "HEAD"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                )
                changed_files = result.stdout.strip().split("\n")
            elif self._is_gitlab_ci():
                base_ref = self.base_ref or os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME", "main")
                result = subprocess.run(
                    ["git", "diff", "--name-only", f"origin/{base_ref}", "HEAD"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                )
                changed_files = result.stdout.strip().split("\n")
            else:
                result = subprocess.run(
                    ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                )
                changed_files = result.stdout.strip().split("\n")
        except Exception:
            pass
        
        return [f for f in changed_files if f and not f.endswith("Test.java") and not f.endswith("Test.kt")]
    
    async def run(self) -> int:
        project_type = self._detect_project_type()
        changed_files = self._get_changed_files()
        
        initial_state: AgentState = {
            "project_path": str(self.project_path),
            "project_type": project_type,
            "build_tool": "",
            "target_files": changed_files if self.incremental else [],
            "coverage_target": self.coverage_target,
            "max_iterations": self.max_iterations,
            "iteration_count": 0,
            "status": "started",
            "message": "Starting CI run...",
            "analyzed_files": [],
            "generated_tests": [],
            "coverage_report": None,
            "current_coverage": 0.0,
            "coverage_gaps": [],
            "improvement_plan": None,
            "output_path": None,
            "summary": None,
        }
        
        result_data = None
        
        try:
            graph = create_test_generation_graph()
            
            async for event in graph.astream(
                initial_state,
                config={"configurable": {"llm_provider": self.llm_provider}},
            ):
                for node_name, node_data in event.items():
                    if isinstance(node_data, dict):
                        result_data = node_data
            
            coverage = 0.0
            coverage_report = None
            generated_tests = []
            coverage_gaps = []
            
            if result_data:
                coverage_report = result_data.get("coverage_report")
                if coverage_report:
                    coverage = coverage_report.overall_coverage
                    coverage_gaps = [
                        {
                            "file_path": gap.file_path,
                            "line_number": gap.line_number,
                            "line_content": gap.line_content,
                            "gap_type": gap.gap_type,
                        }
                        for gap in identify_coverage_gaps(coverage_report, str(self.project_path))
                    ]
                
                generated_tests = [
                    {"test_file_path": t.test_file_path, "source_file": t.source_file}
                    for t in result_data.get("generated_tests", [])
                ]
            
            ci_result = self.reporter.create_result(
                status=result_data.get("status", "completed") if result_data else "failed",
                success=result_data.get("status") in ["completed", "target_reached"] if result_data else False,
                coverage=coverage,
                target_coverage=self.coverage_target,
                generated_tests=generated_tests,
                coverage_gaps=coverage_gaps,
            )
            
            return self.reporter.report(ci_result)
            
        except Exception as e:
            ci_result = self.reporter.create_result(
                status="error",
                success=False,
                error=str(e),
            )
            return self.reporter.report(ci_result)
    
    def run_sync(self) -> int:
        return asyncio.run(self.run())
