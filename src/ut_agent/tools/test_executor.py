"""测试执行模块."""

import subprocess
import os
from pathlib import Path
from typing import Tuple, Optional

from ut_agent.exceptions import (
    TestExecutionError,
    TimeoutError,
    ProjectDetectionError,
)


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
