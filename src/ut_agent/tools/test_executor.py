"""测试执行模块."""

import subprocess
import os
import asyncio
import re
from pathlib import Path
from typing import Tuple, Optional, Callable, Any
from dataclasses import dataclass

from ut_agent.exceptions import (
    TestExecutionError,
    TimeoutError,
    ProjectDetectionError,
)
from ut_agent.utils.event_bus import event_bus, emit_progress
from ut_agent.utils.events import EventType


@dataclass
class TestProgress:
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    current_class: str = ""
    current_test: str = ""
    
    @property
    def completed(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors
    
    @property
    def success_rate(self) -> float:
        if self.completed == 0:
            return 0.0
        return self.passed / self.completed * 100


def execute_java_tests(project_path: str, build_tool: str = "maven") -> Tuple[bool, str]:
    """执行 Java 测试.

    Args:
        project_path: 项目路径
        build_tool: 构建工具 (maven/gradle)

    Returns:
        Tuple[bool, str]: (是否成功, 输出信息)
    """
    try:
        if build_tool == "maven":
            # Maven 执行测试
            cmd = ["mvn", "test", "-q"]
        elif build_tool == "gradle":
            # Gradle 执行测试
            cmd = ["gradle", "test", "-q"]
        else:
            return False, f"不支持的构建工具: {build_tool}"

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            return True, result.stdout or "测试执行成功"
        else:
            return False, result.stderr or result.stdout or "测试执行失败"

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Java test execution timed out after 300 seconds",
            timeout_seconds=300
        )
    except FileNotFoundError:
        raise ProjectDetectionError(
            f"{build_tool} command not found, please ensure it is installed and added to PATH",
            project_path=project_path
        )
    except TestExecutionError:
        raise
    except Exception as e:
        raise TestExecutionError(
            f"Unexpected error executing Java tests: {e}",
            source_file=None,
            test_file=None,
        )


def execute_frontend_tests(project_path: str) -> Tuple[bool, str]:
    """执行前端测试.

    Args:
        project_path: 项目路径

    Returns:
        Tuple[bool, str]: (是否成功, 输出信息)
    """
    path = Path(project_path)

    # 检测包管理器和测试命令
    if (path / "package-lock.json").exists():
        pkg_manager = "npm"
    elif (path / "yarn.lock").exists():
        pkg_manager = "yarn"
    elif (path / "pnpm-lock.yaml").exists():
        pkg_manager = "pnpm"
    else:
        pkg_manager = "npm"

    # 检测测试脚本
    test_cmd = "test"
    if (path / "vitest.config.ts").exists() or (path / "vitest.config.js").exists():
        test_cmd = "test:unit" if has_script(path, "test:unit") else "test"

    try:
        cmd = [pkg_manager, "run", test_cmd]

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            return True, result.stdout or "测试执行成功"
        else:
            return False, result.stderr or result.stdout or "测试执行失败"

    except subprocess.TimeoutExpired:
        return False, "测试执行超时"
    except FileNotFoundError:
        return False, f"未找到 {pkg_manager} 命令"
    except Exception as e:
        return False, f"执行出错: {e}"


def has_script(project_path: Path, script_name: str) -> bool:
    """检查 package.json 中是否有指定脚本."""
    try:
        import json
        package_json = project_path / "package.json"
        if package_json.exists():
            with open(package_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                scripts = data.get("scripts", {})
                return script_name in scripts
    except Exception:
        pass
    return False


def run_tests_with_coverage(
    project_path: str, project_type: str, build_tool: str = "maven"
) -> Tuple[bool, str]:
    """执行测试并生成覆盖率报告.

    Args:
        project_path: 项目路径
        project_type: 项目类型
        build_tool: 构建工具

    Returns:
        Tuple[bool, str]: (是否成功, 输出信息)
    """
    try:
        if project_type == "java":
            if build_tool == "maven":
                cmd = ["mvn", "test", "jacoco:report", "-q"]
            else:
                cmd = ["gradle", "test", "jacocoTestReport", "-q"]
        elif project_type in ["vue", "react", "typescript", "javascript"]:
            path = Path(project_path)

            # 检测包管理器
            if (path / "package-lock.json").exists():
                pkg_manager = "npm"
            elif (path / "yarn.lock").exists():
                pkg_manager = "yarn"
            elif (path / "pnpm-lock.yaml").exists():
                pkg_manager = "pnpm"
            else:
                pkg_manager = "npm"

            # 检测是否有 coverage 脚本
            if has_script(path, "test:coverage"):
                cmd = [pkg_manager, "run", "test:coverage"]
            else:
                cmd = [pkg_manager, "run", "test", "--", "--coverage"]
        else:
            return False, f"不支持的项目类型: {project_type}"

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            return True, result.stdout or "测试和覆盖率报告生成成功"
        else:
            return False, result.stderr or result.stdout or "测试执行失败"

    except subprocess.TimeoutExpired:
        return False, "执行超时"
    except Exception as e:
        return False, f"执行出错: {e}"


def check_java_environment() -> Tuple[bool, str]:
    """检查 Java 环境."""
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, "Java 环境正常"
        return False, "Java 环境检查失败"
    except FileNotFoundError:
        return False, "未找到 Java，请安装 JDK"


def check_maven_environment() -> Tuple[bool, str]:
    """检查 Maven 环境."""
    try:
        result = subprocess.run(
            ["mvn", "-version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True, "Maven 环境正常"
        return False, "Maven 环境检查失败"
    except FileNotFoundError:
        return False, "未找到 Maven，请安装 Maven"


def check_node_environment() -> Tuple[bool, str]:
    """检查 Node.js 环境."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Node.js 环境正常: {version}"
        return False, "Node.js 环境检查失败"
    except FileNotFoundError:
        return False, "未找到 Node.js，请安装 Node.js"


async def execute_tests_async(
    project_path: str,
    project_type: str,
    build_tool: str = "maven",
    on_progress: Optional[Callable[[TestProgress], None]] = None,
) -> Tuple[bool, str, TestProgress]:
    """异步执行测试，支持实时进度回调.
    
    Args:
        project_path: 项目路径
        project_type: 项目类型
        build_tool: 构建工具
        on_progress: 进度回调函数
        
    Returns:
        Tuple[bool, str, TestProgress]: (是否成功, 输出信息, 测试进度)
    """
    progress = TestProgress()
    
    event_bus.emit_simple(EventType.TEST_EXECUTION_STARTED, {
        "project_type": project_type,
        "build_tool": build_tool,
    }, source="test_executor")
    
    if project_type == "java":
        cmd = ["mvn", "test"] if build_tool == "maven" else ["gradle", "test"]
        return await _execute_java_tests_async(project_path, cmd, progress, on_progress)
    elif project_type in ["vue", "react", "typescript", "javascript"]:
        return await _execute_frontend_tests_async(project_path, progress, on_progress)
    else:
        return False, f"不支持的项目类型: {project_type}", progress


async def _execute_java_tests_async(
    project_path: str,
    cmd: list,
    progress: TestProgress,
    on_progress: Optional[Callable[[TestProgress], None]] = None,
) -> Tuple[bool, str, TestProgress]:
    """异步执行Java测试."""
    output_lines = []
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
        )
        
        maven_pattern = re.compile(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)')
        gradle_pattern = re.compile(r'(\d+) tests completed, (\d+) failed')
        running_pattern = re.compile(r'Running (\S+)')
        
        async def read_stream(stream, is_stderr=False):
            async for line in stream:
                line_str = line.decode('utf-8', errors='replace').strip()
                output_lines.append(line_str)
                
                running_match = running_pattern.search(line_str)
                if running_match:
                    progress.current_class = running_match.group(1)
                
                maven_match = maven_pattern.search(line_str)
                if maven_match:
                    progress.passed = int(maven_match.group(1)) - int(maven_match.group(2)) - int(maven_match.group(3))
                    progress.failed = int(maven_match.group(2))
                    progress.errors = int(maven_match.group(3))
                    progress.skipped = int(maven_match.group(4))
                    progress.total_tests = progress.completed
                
                gradle_match = gradle_pattern.search(line_str)
                if gradle_match:
                    progress.total_tests = int(gradle_match.group(1))
                    progress.failed = int(gradle_match.group(2))
                    progress.passed = progress.total_tests - progress.failed
                
                if on_progress:
                    on_progress(progress)
                
                emit_progress(
                    stage="execute_tests",
                    current=progress.completed,
                    total=max(progress.total_tests, progress.completed),
                    message=f"Tests: {progress.passed} passed, {progress.failed} failed",
                    current_file=progress.current_class,
                    source="test_executor",
                )
        
        await asyncio.gather(
            read_stream(process.stdout),
            read_stream(process.stderr, is_stderr=True),
        )
        
        await process.wait()
        
        output = "\n".join(output_lines)
        success = process.returncode == 0
        
        event_bus.emit_simple(EventType.TEST_EXECUTION_COMPLETED, {
            "passed": progress.passed,
            "failed": progress.failed,
            "skipped": progress.skipped,
            "errors": progress.errors,
            "success": success,
        }, source="test_executor")
        
        return success, output, progress
        
    except FileNotFoundError:
        raise ProjectDetectionError(
            f"Command not found: {cmd[0]}",
            project_path=project_path
        )
    except Exception as e:
        raise TestExecutionError(
            f"Error executing tests: {e}",
            source_file=None,
            test_file=None,
        )


async def _execute_frontend_tests_async(
    project_path: str,
    progress: TestProgress,
    on_progress: Optional[Callable[[TestProgress], None]] = None,
) -> Tuple[bool, str, TestProgress]:
    """异步执行前端测试."""
    path = Path(project_path)
    output_lines = []
    
    if (path / "package-lock.json").exists():
        pkg_manager = "npm"
    elif (path / "yarn.lock").exists():
        pkg_manager = "yarn"
    elif (path / "pnpm-lock.yaml").exists():
        pkg_manager = "pnpm"
    else:
        pkg_manager = "npm"
    
    cmd = [pkg_manager, "run", "test"]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=project_path,
        )
        
        jest_pattern = re.compile(r'Tests:\s+(\d+) passed, (\d+) total')
        jest_fail_pattern = re.compile(r'(\d+) failed')
        vitest_pattern = re.compile(r'(\d+) passed \| (\d+) failed')
        
        async def read_stream(stream, is_stderr=False):
            async for line in stream:
                line_str = line.decode('utf-8', errors='replace').strip()
                output_lines.append(line_str)
                
                jest_match = jest_pattern.search(line_str)
                if jest_match:
                    progress.passed = int(jest_match.group(1))
                    progress.total_tests = int(jest_match.group(2))
                    fail_match = jest_fail_pattern.search(line_str)
                    if fail_match:
                        progress.failed = int(fail_match.group(1))
                        progress.passed = progress.total_tests - progress.failed
                
                vitest_match = vitest_pattern.search(line_str)
                if vitest_match:
                    progress.passed = int(vitest_match.group(1))
                    progress.failed = int(vitest_match.group(2))
                    progress.total_tests = progress.passed + progress.failed
                
                if on_progress:
                    on_progress(progress)
                
                emit_progress(
                    stage="execute_tests",
                    current=progress.completed,
                    total=max(progress.total_tests, progress.completed),
                    message=f"Tests: {progress.passed} passed, {progress.failed} failed",
                    source="test_executor",
                )
        
        await asyncio.gather(
            read_stream(process.stdout),
            read_stream(process.stderr, is_stderr=True),
        )
        
        await process.wait()
        
        output = "\n".join(output_lines)
        success = process.returncode == 0
        
        event_bus.emit_simple(EventType.TEST_EXECUTION_COMPLETED, {
            "passed": progress.passed,
            "failed": progress.failed,
            "skipped": progress.skipped,
            "success": success,
        }, source="test_executor")
        
        return success, output, progress
        
    except FileNotFoundError:
        return False, f"未找到 {pkg_manager} 命令", progress
    except Exception as e:
        return False, f"执行出错: {e}", progress


def parse_test_summary(output: str, project_type: str) -> TestProgress:
    """解析测试输出摘要."""
    progress = TestProgress()
    
    if project_type == "java":
        maven_pattern = re.compile(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)')
        match = maven_pattern.search(output)
        if match:
            total = int(match.group(1))
            progress.failed = int(match.group(2))
            progress.errors = int(match.group(3))
            progress.skipped = int(match.group(4))
            progress.passed = total - progress.failed - progress.errors
            progress.total_tests = total
    
    elif project_type in ["vue", "react", "typescript"]:
        jest_pattern = re.compile(r'Tests:\s+(\d+) passed, (\d+) failed')
        match = jest_pattern.search(output)
        if match:
            progress.passed = int(match.group(1))
            progress.failed = int(match.group(2))
            progress.total_tests = progress.passed + progress.failed
    
    return progress
