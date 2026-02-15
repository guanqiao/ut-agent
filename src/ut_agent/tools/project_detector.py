"""项目类型检测模块."""

import os
from pathlib import Path
from typing import Tuple, List


def detect_project_type(project_path: str) -> Tuple[str, str]:
    """检测项目类型和构建工具.

    Args:
        project_path: 项目路径

    Returns:
        Tuple[str, str]: (项目类型, 构建工具)
    """
    path = Path(project_path)

    if not path.exists():
        raise ValueError(f"项目路径不存在: {project_path}")

    # 检测 Java 项目
    if (path / "pom.xml").exists():
        return ("java", "maven")
    elif (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
        return ("java", "gradle")

    # 检测前端项目
    package_json = path / "package.json"
    if package_json.exists():
        content = package_json.read_text(encoding="utf-8")

        # 检测 Vue
        if '"vue"' in content or (path / "vue.config.js").exists():
            return ("vue", "npm")

        # 检测 React
        if '"react"' in content:
            return ("react", "npm")

        # 检测 TypeScript
        if '"typescript"' in content or (path / "tsconfig.json").exists():
            return ("typescript", "npm")

        return ("javascript", "npm")

    # 检测 Python 项目
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return ("python", "pip")

    # 默认类型
    return ("unknown", "unknown")


def find_source_files(project_path: str, project_type: str) -> List[str]:
    """查找源代码文件.

    Args:
        project_path: 项目路径
        project_type: 项目类型

    Returns:
        List[str]: 源代码文件路径列表
    """
    path = Path(project_path)
    source_files = []

    if project_type == "java":
        # Java 源文件
        src_dirs = [
            path / "src" / "main" / "java",
            path / "src",
        ]

        for src_dir in src_dirs:
            if src_dir.exists():
                for java_file in src_dir.rglob("*.java"):
                    # 排除测试文件
                    if "test" not in str(java_file).lower():
                        source_files.append(str(java_file))
                break

    elif project_type in ["vue", "react", "typescript", "javascript"]:
        # 前端源文件
        src_dirs = [
            path / "src",
            path,
        ]

        extensions = {
            "vue": ["*.vue", "*.ts", "*.js"],
            "react": ["*.tsx", "*.ts", "*.jsx", "*.js"],
            "typescript": ["*.ts", "*.tsx"],
            "javascript": ["*.js", "*.jsx"],
        }

        patterns = extensions.get(project_type, ["*.ts", "*.js"])

        for src_dir in src_dirs:
            if src_dir.exists():
                for pattern in patterns:
                    for file in src_dir.rglob(pattern):
                        # 排除测试文件和 node_modules
                        file_str = str(file)
                        if (
                            "node_modules" not in file_str
                            and "test" not in file_str.lower()
                            and "__tests__" not in file_str
                            and ".spec." not in file_str
                            and ".test." not in file_str
                        ):
                            source_files.append(file_str)
                break

    elif project_type == "python":
        # Python 源文件
        for py_file in path.rglob("*.py"):
            file_str = str(py_file)
            if (
                "test_" not in file_str
                and "_test.py" not in file_str
                and "__pycache__" not in file_str
                and ".venv" not in file_str
            ):
                source_files.append(file_str)

    # 限制返回的文件数量，避免过多
    return source_files[:50]


def get_test_directory(project_path: str, project_type: str) -> str:
    """获取测试目录路径.

    Args:
        project_path: 项目路径
        project_type: 项目类型

    Returns:
        str: 测试目录路径
    """
    path = Path(project_path)

    if project_type == "java":
        test_dir = path / "src" / "test" / "java"
        if test_dir.exists():
            return str(test_dir)
        return str(path / "src" / "test" / "java")

    elif project_type in ["vue", "react", "typescript", "javascript"]:
        # 前端项目通常测试文件与源文件同级或在 __tests__ 目录
        test_dir = path / "src" / "__tests__"
        if test_dir.exists():
            return str(test_dir)
        return str(path / "src")

    elif project_type == "python":
        test_dir = path / "tests"
        if test_dir.exists():
            return str(test_dir)
        return str(path / "tests")

    return str(path)


def infer_package_name(file_path: str, project_path: str, project_type: str) -> str:
    """推断文件的包名/模块名.

    Args:
        file_path: 文件路径
        project_path: 项目路径
        project_type: 项目类型

    Returns:
        str: 包名或模块名
    """
    path = Path(file_path)
    proj_path = Path(project_path)

    if project_type == "java":
        # 从 src/main/java 或 src 后开始计算包名
        relative = None
        for parent in path.parents:
            if parent.name == "java" and (parent.parent.name == "main" or parent.parent.name == "src"):
                relative = path.relative_to(parent)
                break

        if relative:
            package_parts = list(relative.parent.parts)
            return ".".join(package_parts) if package_parts else ""

    elif project_type in ["vue", "react", "typescript", "javascript"]:
        # 返回相对路径作为模块名
        try:
            relative = path.relative_to(proj_path / "src")
            return str(relative.with_suffix("")).replace(os.sep, "/")
        except ValueError:
            return path.stem

    elif project_type == "python":
        try:
            relative = path.relative_to(proj_path)
            module_path = str(relative.with_suffix("")).replace(os.sep, ".")
            return module_path
        except ValueError:
            return path.stem

    return path.stem
