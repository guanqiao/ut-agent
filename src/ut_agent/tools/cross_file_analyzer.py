"""跨文件上下文分析模块.

提供项目级代码分析能力，包括：
- 项目索引构建
- 依赖关系分析
- 接口实现查找
- 类型推断
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import hashlib

from ut_agent.tools.code_analyzer import analyze_java_file, analyze_ts_file


@dataclass
class SymbolInfo:
    """符号信息."""
    name: str
    type: str  # class, interface, enum, function
    file_path: str
    package: str = ""
    line_number: int = 0
    is_public: bool = True
    signature: str = ""
    documentation: str = ""


@dataclass
class DependencyInfo:
    """依赖信息."""
    source_file: str
    target_file: str
    dependency_type: str  # import, extends, implements, call
    symbol: str = ""
    line_number: int = 0


@dataclass
class ClassRelationship:
    """类关系信息."""
    class_name: str
    file_path: str
    superclass: Optional[str] = None
    interfaces: List[str] = field(default_factory=list)
    subclasses: List[str] = field(default_factory=list)
    implementors: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


class ProjectIndex:
    """项目索引."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.index_file = self.project_path / ".ut-agent" / "index.json"
        self.symbols: Dict[str, SymbolInfo] = {}
        self.files: Dict[str, Dict[str, Any]] = {}
        self.dependencies: List[DependencyInfo] = []
        self.relationships: Dict[str, ClassRelationship] = {}
        self._file_hashes: Dict[str, str] = {}

    def build_index(self, force_rebuild: bool = False) -> None:
        """构建项目索引.

        Args:
            force_rebuild: 是否强制重建
        """
        # 检查是否需要重建
        if not force_rebuild and self._is_index_valid():
            self._load_index()
            return

        self.symbols.clear()
        self.files.clear()
        self.dependencies.clear()
        self.relationships.clear()

        # 扫描所有源文件
        source_files = self._find_source_files()

        for file_path in source_files:
            try:
                self._index_file(file_path)
            except Exception as e:
                print(f"索引文件失败 {file_path}: {e}")

        # 分析依赖关系
        self._analyze_dependencies()

        # 保存索引
        self._save_index()

    def _find_source_files(self) -> List[str]:
        """查找所有源文件."""
        files = []

        # Java 文件
        java_files = list(self.project_path.rglob("*.java"))
        files.extend([str(f) for f in java_files])

        # TypeScript 文件
        ts_files = list(self.project_path.rglob("*.ts"))
        files.extend([str(f) for f in ts_files if not f.name.endswith(".d.ts")])

        # Vue 文件
        vue_files = list(self.project_path.rglob("*.vue"))
        files.extend([str(f) for f in vue_files])

        # 排除测试文件和 node_modules
        files = [
            f for f in files
            if "test" not in f.lower()
            and "spec" not in f.lower()
            and "node_modules" not in f
            and "target" not in f
            and "build" not in f
        ]

        return files

    def _index_file(self, file_path: str) -> None:
        """索引单个文件."""
        path = Path(file_path)

        # 计算文件哈希
        content = path.read_text(encoding="utf-8", errors="ignore")
        file_hash = hashlib.md5(content.encode()).hexdigest()
        self._file_hashes[file_path] = file_hash

        # 分析文件
        if file_path.endswith(".java"):
            analysis = analyze_java_file(file_path)
        elif file_path.endswith(".ts") or file_path.endswith(".vue"):
            analysis = analyze_ts_file(file_path)
        else:
            return

        self.files[file_path] = analysis

        # 提取符号
        self._extract_symbols(analysis)

    def _extract_symbols(self, analysis: Dict[str, Any]) -> None:
        """提取符号信息."""
        file_path = analysis["file_path"]
        package = analysis.get("package", "")

        # Java 类
        if analysis["language"] == "java":
            class_name = analysis.get("class_name", "")
            if class_name:
                full_name = f"{package}.{class_name}" if package else class_name
                self.symbols[full_name] = SymbolInfo(
                    name=class_name,
                    type="class",
                    file_path=file_path,
                    package=package,
                )

            # 方法
            for method in analysis.get("methods", []):
                method_name = method.get("name", "")
                if method_name:
                    symbol_name = f"{full_name}.{method_name}"
                    self.symbols[symbol_name] = SymbolInfo(
                        name=method_name,
                        type="method",
                        file_path=file_path,
                        package=package,
                        signature=method.get("signature", ""),
                    )

        # TypeScript/Vue
        elif analysis["language"] in ["typescript", "vue"]:
            file_name = Path(file_path).stem

            for func in analysis.get("functions", []):
                func_name = func.get("name", "")
                if func_name:
                    symbol_name = f"{file_name}.{func_name}"
                    self.symbols[symbol_name] = SymbolInfo(
                        name=func_name,
                        type="function",
                        file_path=file_path,
                        signature=f"{func_name}({', '.join(p['name'] for p in func.get('parameters', []))})",
                    )

    def _analyze_dependencies(self) -> None:
        """分析依赖关系."""
        for file_path, analysis in self.files.items():
            if analysis["language"] == "java":
                self._analyze_java_dependencies(file_path, analysis)
            elif analysis["language"] in ["typescript", "vue"]:
                self._analyze_ts_dependencies(file_path, analysis)

    def _analyze_java_dependencies(self, file_path: str, analysis: Dict[str, Any]) -> None:
        """分析 Java 依赖."""
        package = analysis.get("package", "")
        class_name = analysis.get("class_name", "")

        # 记录类关系
        if class_name:
            relationship = ClassRelationship(
                class_name=class_name,
                file_path=file_path,
            )

            # 提取继承关系
            content = analysis.get("content", "")

            # extends
            extends_match = __import__('re').search(
                rf"class\s+{class_name}\s+extends\s+(\w+)",
                content
            )
            if extends_match:
                superclass = extends_match.group(1)
                relationship.superclass = superclass
                self.dependencies.append(DependencyInfo(
                    source_file=file_path,
                    target_file=superclass,
                    dependency_type="extends",
                    symbol=superclass,
                ))

            # implements
            implements_match = __import__('re').search(
                rf"class\s+{class_name}(?:\s+extends\s+\w+)?\s+implements\s+([\w\s,]+)",
                content
            )
            if implements_match:
                interfaces = [i.strip() for i in implements_match.group(1).split(",")]
                relationship.interfaces = interfaces
                for interface in interfaces:
                    self.dependencies.append(DependencyInfo(
                        source_file=file_path,
                        target_file=interface,
                        dependency_type="implements",
                        symbol=interface,
                    ))

            self.relationships[class_name] = relationship

        # 分析 import
        for import_stmt in analysis.get("imports", []):
            self.dependencies.append(DependencyInfo(
                source_file=file_path,
                target_file=import_stmt,
                dependency_type="import",
                symbol=import_stmt,
            ))

    def _analyze_ts_dependencies(self, file_path: str, analysis: Dict[str, Any]) -> None:
        """分析 TypeScript 依赖."""
        for imp in analysis.get("imports", []):
            source = imp.get("source", "")
            if source:
                self.dependencies.append(DependencyInfo(
                    source_file=file_path,
                    target_file=source,
                    dependency_type="import",
                    symbol=imp.get("name", ""),
                ))

    def _is_index_valid(self) -> bool:
        """检查索引是否有效."""
        if not self.index_file.exists():
            return False

        try:
            with open(self.index_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            stored_hashes = data.get("file_hashes", {})

            # 检查文件是否有变化
            for file_path, stored_hash in stored_hashes.items():
                if not os.path.exists(file_path):
                    return False

                current_content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
                current_hash = hashlib.md5(current_content.encode()).hexdigest()

                if current_hash != stored_hash:
                    return False

            return True
        except Exception:
            return False

    def _save_index(self) -> None:
        """保存索引到文件."""
        self.index_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "symbols": {k: asdict(v) for k, v in self.symbols.items()},
            "dependencies": [asdict(d) for d in self.dependencies],
            "relationships": {k: asdict(v) for k, v in self.relationships.items()},
            "file_hashes": self._file_hashes,
        }

        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_index(self) -> None:
        """从文件加载索引."""
        with open(self.index_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.symbols = {k: SymbolInfo(**v) for k, v in data.get("symbols", {}).items()}
        self.dependencies = [DependencyInfo(**d) for d in data.get("dependencies", [])]
        self.relationships = {k: ClassRelationship(**v) for k, v in data.get("relationships", {}).items()}
        self._file_hashes = data.get("file_hashes", {})

    def find_symbol(self, name: str) -> Optional[SymbolInfo]:
        """查找符号."""
        # 完全匹配
        if name in self.symbols:
            return self.symbols[name]

        # 部分匹配
        for full_name, symbol in self.symbols.items():
            if symbol.name == name:
                return symbol

        return None

    def find_implementations(self, interface_name: str) -> List[str]:
        """查找接口实现类."""
        implementations = []

        for dep in self.dependencies:
            if dep.dependency_type == "implements" and dep.target_file == interface_name:
                implementations.append(dep.source_file)

        return implementations

    def find_subclasses(self, class_name: str) -> List[str]:
        """查找子类."""
        subclasses = []

        for dep in self.dependencies:
            if dep.dependency_type == "extends" and dep.target_file == class_name:
                subclasses.append(dep.source_file)

        return subclasses

    def get_file_dependencies(self, file_path: str) -> List[str]:
        """获取文件依赖."""
        deps = []

        for dep in self.dependencies:
            if dep.source_file == file_path:
                # 查找目标文件路径
                target_symbol = self.find_symbol(dep.target_file)
                if target_symbol:
                    deps.append(target_symbol.file_path)
                else:
                    deps.append(dep.target_file)

        return list(set(deps))

    def get_dependent_files(self, file_path: str) -> List[str]:
        """获取依赖该文件的文件."""
        dependents = []
        file_symbol = None

        # 找到文件对应的符号名
        for name, symbol in self.symbols.items():
            if symbol.file_path == file_path:
                file_symbol = symbol.name
                break

        if file_symbol:
            for dep in self.dependencies:
                if dep.target_file == file_symbol:
                    dependents.append(dep.source_file)

        return dependents


class CrossFileAnalyzer:
    """跨文件分析器."""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.index = ProjectIndex(project_path)

    def analyze(self, file_path: str) -> Dict[str, Any]:
        """分析文件及其上下文.

        Args:
            file_path: 文件路径

        Returns:
            Dict: 包含跨文件上下文的分析结果
        """
        # 确保索引已构建
        self.index.build_index()

        # 分析目标文件
        path = Path(file_path)

        if file_path.endswith(".java"):
            analysis = analyze_java_file(file_path)
        elif file_path.endswith(".ts") or file_path.endswith(".vue"):
            analysis = analyze_ts_file(file_path)
        else:
            return {"error": "不支持的文件类型"}

        # 添加上下文信息
        context = self._build_context(file_path, analysis)
        analysis["context"] = context

        return analysis

    def _build_context(self, file_path: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """构建上下文信息."""
        context = {
            "dependencies": [],
            "dependents": [],
            "implementations": {},
            "super_classes": [],
            "interface_implementations": {},
        }

        # 获取文件依赖
        deps = self.index.get_file_dependencies(file_path)
        for dep_path in deps:
            dep_symbol = None
            for name, symbol in self.index.symbols.items():
                if symbol.file_path == dep_path:
                    dep_symbol = symbol
                    break

            if dep_symbol:
                context["dependencies"].append({
                    "name": dep_symbol.name,
                    "file_path": dep_path,
                    "type": dep_symbol.type,
                })

        # Java 特有分析
        if analysis["language"] == "java":
            class_name = analysis.get("class_name", "")

            # 查找父类
            if class_name in self.index.relationships:
                relationship = self.index.relationships[class_name]

                if relationship.superclass:
                    context["super_classes"].append(relationship.superclass)

                # 查找接口实现
                for interface in relationship.interfaces:
                    impls = self.index.find_implementations(interface)
                    context["interface_implementations"][interface] = impls

        return context

    def suggest_mocks(self, file_path: str) -> List[Dict[str, Any]]:
        """建议需要 Mock 的依赖.

        Args:
            file_path: 文件路径

        Returns:
            List[Dict]: Mock 建议列表
        """
        analysis = self.analyze(file_path)
        mocks = []

        if analysis["language"] == "java":
            # 分析字段注入
            for field in analysis.get("fields", []):
                field_type = field.get("type", "")
                field_name = field.get("name", "")

                # 检查是否是接口或需要 Mock 的类型
                symbol = self.index.find_symbol(field_type)
                if symbol:
                    mocks.append({
                        "field_name": field_name,
                        "field_type": field_type,
                        "mock_type": "interface" if symbol.type == "interface" else "class",
                        "file_path": symbol.file_path,
                    })

        return mocks


def build_project_index(project_path: str, force_rebuild: bool = False) -> ProjectIndex:
    """构建项目索引的便捷函数.

    Args:
        project_path: 项目路径
        force_rebuild: 是否强制重建

    Returns:
        ProjectIndex: 项目索引
    """
    index = ProjectIndex(project_path)
    index.build_index(force_rebuild)
    return index
