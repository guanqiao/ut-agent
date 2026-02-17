"""测试隔离性检测.

分析测试代码，检测测试隔离性问题，如共享状态、外部依赖等。
"""

import ast
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class IsolationViolationType(Enum):
    """隔离性违规类型枚举."""
    SHARED_STATE = "shared_state"               # 共享状态
    EXTERNAL_DEPENDENCY = "external_dependency" # 外部依赖
    FILE_SYSTEM = "file_system"                 # 文件系统操作
    NETWORK = "network"                         # 网络操作
    DATABASE = "database"                       # 数据库操作
    GLOBAL_VARIABLE = "global_variable"         # 全局变量
    STATIC_VARIABLE = "static_variable"         # 静态/类变量
    ORDER_DEPENDENCY = "order_dependency"       # 测试顺序依赖


@dataclass
class SharedResource:
    """共享资源.
    
    Attributes:
        name: 资源名称
        resource_type: 资源类型
        line_number: 行号
        is_cleaned_up: 是否已清理
    """
    name: str
    resource_type: str
    line_number: int
    is_cleaned_up: bool = False
    
    def mark_cleaned_up(self) -> None:
        """标记资源已清理."""
        self.is_cleaned_up = True


@dataclass
class IsolationViolation:
    """隔离性违规.
    
    Attributes:
        violation_type: 违规类型
        message: 违规描述
        line_number: 行号
        test_function: 测试函数名
        severity: 严重程度 (high/medium/low)
    """
    violation_type: IsolationViolationType
    message: str
    line_number: int
    test_function: str
    severity: str = "medium"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return {
            "violation_type": self.violation_type.value,
            "message": self.message,
            "line_number": self.line_number,
            "test_function": self.test_function,
            "severity": self.severity,
        }


@dataclass
class TestDependency:
    """测试依赖.
    
    Attributes:
        source_test: 源测试
        target_test: 目标测试
        dependency_type: 依赖类型
    """
    source_test: str
    target_test: str
    dependency_type: str


class TestIsolationAnalyzer:
    """测试隔离性分析器.
    
    分析测试代码，检测隔离性问题。
    """
    
    # 文件系统相关模块和函数
    FILE_SYSTEM_INDICATORS: Set[str] = {
        "open", "file", "os.open", "os.remove", "os.rename",
        "os.mkdir", "os.rmdir", "os.path", "pathlib.Path",
        "shutil.copy", "shutil.move", "shutil.rmtree",
        "tempfile", "FileStorage",
    }
    
    # 网络相关模块和函数
    NETWORK_INDICATORS: Set[str] = {
        "requests", "urllib", "http.client", "socket",
        "ftplib", "smtplib", "imaplib", "poplib",
        "httpx", "aiohttp",
    }
    
    # 数据库相关模块和函数
    DATABASE_INDICATORS: Set[str] = {
        "sqlite3", "mysql", "psycopg2", "pymongo",
        "sqlalchemy", "peewee", "django.db",
        "redis", "pymemcache", "cassandra",
    }
    
    # 全局状态相关
    GLOBAL_STATE_INDICATORS: Set[str] = {
        "global", "globals",
    }
    
    def __init__(self):
        """初始化分析器."""
        self.violations: List[IsolationViolation] = []
        self.shared_resources: List[SharedResource] = []
        self.dependencies: List[TestDependency] = []
        
    def _check_global_variables(
        self,
        func_node: ast.FunctionDef,
    ) -> List[IsolationViolation]:
        """检查全局变量使用.
        
        Args:
            func_node: 函数定义节点
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        for node in ast.walk(func_node):
            # 检查 global 关键字
            if isinstance(node, ast.Global):
                violations.append(IsolationViolation(
                    violation_type=IsolationViolationType.GLOBAL_VARIABLE,
                    message=f"Function uses global variable(s): {', '.join(node.names)}",
                    line_number=node.lineno,
                    test_function=func_node.name,
                    severity="high" if len(node.names) > 1 else "medium",
                ))
            # 检查 globals() 调用
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "globals":
                    violations.append(IsolationViolation(
                        violation_type=IsolationViolationType.GLOBAL_VARIABLE,
                        message="Function calls globals() which accesses global state",
                        line_number=node.lineno,
                        test_function=func_node.name,
                        severity="high",
                    ))
                    
        return violations
        
    def _check_file_system_operations(
        self,
        func_node: ast.FunctionDef,
    ) -> List[IsolationViolation]:
        """检查文件系统操作.
        
        Args:
            func_node: 函数定义节点
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name:
                    # 检查 open() 函数
                    if func_name == "open":
                        violations.append(IsolationViolation(
                            violation_type=IsolationViolationType.FILE_SYSTEM,
                            message="Function performs file system operation using open()",
                            line_number=node.lineno,
                            test_function=func_node.name,
                            severity="medium",
                        ))
                    # 检查 os 模块操作
                    elif func_name.startswith(("os.", "os.path.")):
                        violations.append(IsolationViolation(
                            violation_type=IsolationViolationType.FILE_SYSTEM,
                            message=f"Function uses os module: {func_name}",
                            line_number=node.lineno,
                            test_function=func_node.name,
                            severity="medium",
                        ))
                    # 检查 pathlib
                    elif "Path" in func_name:
                        violations.append(IsolationViolation(
                            violation_type=IsolationViolationType.FILE_SYSTEM,
                            message="Function uses pathlib for file operations",
                            line_number=node.lineno,
                            test_function=func_node.name,
                            severity="low",
                        ))
                        
        return violations
        
    def _check_network_operations(
        self,
        func_node: ast.FunctionDef,
    ) -> List[IsolationViolation]:
        """检查网络操作.
        
        Args:
            func_node: 函数定义节点
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name:
                    # 检查网络相关调用
                    for indicator in self.NETWORK_INDICATORS:
                        if indicator in func_name.lower():
                            violations.append(IsolationViolation(
                                violation_type=IsolationViolationType.NETWORK,
                                message=f"Function performs network operation using {func_name}",
                                line_number=node.lineno,
                                test_function=func_node.name,
                                severity="high",
                            ))
                            break
                            
            # 检查 import 网络库
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.name if hasattr(alias, 'name') else alias.asname
                    if name:
                        for indicator in self.NETWORK_INDICATORS:
                            if indicator in name.lower():
                                # 不直接报告，因为只是导入
                                pass
                                
        return violations
        
    def _check_database_operations(
        self,
        func_node: ast.FunctionDef,
    ) -> List[IsolationViolation]:
        """检查数据库操作.
        
        Args:
            func_node: 函数定义节点
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name:
                    # 检查数据库连接
                    for indicator in self.DATABASE_INDICATORS:
                        if indicator in func_name.lower():
                            # 检查是否是连接操作
                            if any(op in func_name.lower() for op in ["connect", "execute", "commit"]):
                                violations.append(IsolationViolation(
                                    violation_type=IsolationViolationType.DATABASE,
                                    message=f"Function performs database operation: {func_name}",
                                    line_number=node.lineno,
                                    test_function=func_node.name,
                                    severity="high",
                                ))
                                break
                                
        return violations
        
    def _check_static_variables(
        self,
        func_node: ast.FunctionDef,
        class_node: Optional[ast.ClassDef] = None,
    ) -> List[IsolationViolation]:
        """检查静态/类变量修改.
        
        Args:
            func_node: 函数定义节点
            class_node: 类定义节点（可选）
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        if not class_node:
            return violations
            
        class_name = class_node.name
        
        for node in ast.walk(func_node):
            # 检查对类属性的赋值
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        # 检查是否是类属性修改
                        if isinstance(target.value, ast.Name):
                            if target.value.id == class_name or target.value.id == "self":
                                violations.append(IsolationViolation(
                                    violation_type=IsolationViolationType.STATIC_VARIABLE,
                                    message=f"Function modifies class/static variable: {target.attr}",
                                    line_number=node.lineno,
                                    test_function=func_node.name,
                                    severity="high",
                                ))
            # 检查 AugAssign (+=, -=, etc.)
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Attribute):
                    if isinstance(node.target.value, ast.Name):
                        if node.target.value.id == class_name or node.target.value.id == "self":
                            violations.append(IsolationViolation(
                                violation_type=IsolationViolationType.STATIC_VARIABLE,
                                message=f"Function modifies class/static variable: {node.target.attr}",
                                line_number=node.lineno,
                                test_function=func_node.name,
                                severity="high",
                            ))
                            
        return violations
        
    def _check_resource_cleanup(
        self,
        func_node: ast.FunctionDef,
    ) -> List[IsolationViolation]:
        """检查资源清理.
        
        Args:
            func_node: 函数定义节点
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        # 查找打开的资源
        opened_resources = []
        closed_resources = []
        
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name == "open":
                    opened_resources.append(node)
                elif func_name in ("close", "f.close"):
                    closed_resources.append(node)
                    
        # 简单检查：如果有 open 但没有 with 语句，可能有问题
        # 这是一个简化的检查，实际实现可以更复杂
        
        return violations
        
    def _check_order_dependencies(
        self,
        class_node: ast.ClassDef,
    ) -> List[TestDependency]:
        """检查测试顺序依赖.
        
        Args:
            class_node: 类定义节点
            
        Returns:
            List[TestDependency]: 依赖列表
        """
        dependencies = []
        
        # 获取所有测试方法
        test_methods = [
            node for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
        ]
        
        # 检查类变量修改
        class_vars = set()
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        class_vars.add(target.id)
                        
        # 检查哪些测试方法读取了被其他方法修改的类变量
        for i, method in enumerate(test_methods):
            for node in ast.walk(method):
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        if node.value.id == class_node.name and node.attr in class_vars:
                            # 这个方法读取了类变量
                            # 检查之前的方法是否修改了它
                            for prev_method in test_methods[:i]:
                                if self._method_modifies_variable(prev_method, node.attr, class_node.name):
                                    dependencies.append(TestDependency(
                                        source_test=method.name,
                                        target_test=prev_method.name,
                                        dependency_type="order",
                                    ))
                                    
        return dependencies
        
    def _method_modifies_variable(
        self,
        method: ast.FunctionDef,
        var_name: str,
        class_name: str,
    ) -> bool:
        """检查方法是否修改变量.
        
        Args:
            method: 方法节点
            var_name: 变量名
            class_name: 类名
            
        Returns:
            bool: 是否修改
        """
        for node in ast.walk(method):
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    targets = node.targets
                else:
                    targets = [node.target]
                    
                for target in targets:
                    if isinstance(target, ast.Attribute):
                        if target.attr == var_name:
                            if isinstance(target.value, ast.Name):
                                if target.value.id in (class_name, "self"):
                                    return True
        return False
        
    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """获取调用名称.
        
        Args:
            node: 调用节点
            
        Returns:
            Optional[str]: 调用名称
        """
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return None
        
    def analyze_test_function(
        self,
        func_node: ast.FunctionDef,
        class_node: Optional[ast.ClassDef] = None,
    ) -> List[IsolationViolation]:
        """分析测试函数.
        
        Args:
            func_node: 函数定义节点
            class_node: 类定义节点（可选）
            
        Returns:
            List[IsolationViolation]: 违规列表
        """
        violations = []
        
        # 检查各种隔离性问题
        violations.extend(self._check_global_variables(func_node))
        violations.extend(self._check_file_system_operations(func_node))
        violations.extend(self._check_network_operations(func_node))
        violations.extend(self._check_database_operations(func_node))
        violations.extend(self._check_static_variables(func_node, class_node))
        violations.extend(self._check_resource_cleanup(func_node))
        
        return violations
        
    def calculate_isolation_score(self, violations: List[IsolationViolation]) -> float:
        """计算隔离性分数.
        
        Args:
            violations: 违规列表
            
        Returns:
            float: 隔离性分数 (0-1)
        """
        if not violations:
            return 1.0
            
        # 根据违规严重程度计算分数
        severity_weights = {
            "high": 0.3,
            "medium": 0.2,
            "low": 0.1,
        }
        
        total_penalty = sum(
            severity_weights.get(v.severity, 0.1)
            for v in violations
        )
        
        # 分数 = 1 - 惩罚，但不低于0
        score = max(0.0, 1.0 - total_penalty)
        
        return round(score, 2)
        
    def generate_recommendations(
        self,
        violations: List[IsolationViolation],
    ) -> List[Dict[str, Any]]:
        """生成改进建议.
        
        Args:
            violations: 违规列表
            
        Returns:
            List[Dict[str, Any]]: 建议列表
        """
        recommendations = []
        
        # 按类型分组
        by_type: Dict[IsolationViolationType, List[IsolationViolation]] = {}
        for v in violations:
            by_type.setdefault(v.violation_type, []).append(v)
            
        # 为每种类型生成建议
        for vtype, vs in by_type.items():
            if vtype == IsolationViolationType.GLOBAL_VARIABLE:
                recommendations.append({
                    "category": "global_state",
                    "message": f"{len(vs)} test(s) use global variables. Consider using fixtures or dependency injection.",
                    "priority": "high",
                    "example": "# Instead of global state, use:\n@pytest.fixture\ndef setup_state():\n    return {'counter': 0}",
                })
            elif vtype == IsolationViolationType.FILE_SYSTEM:
                recommendations.append({
                    "category": "file_operations",
                    "message": f"{len(vs)} test(s) perform file system operations. Consider using tmp_path fixture or mocking.",
                    "priority": "medium",
                    "example": "# Use pytest's tmp_path fixture:\ndef test_file(tmp_path):\n    file = tmp_path / 'test.txt'",
                })
            elif vtype == IsolationViolationType.NETWORK:
                recommendations.append({
                    "category": "network",
                    "message": f"{len(vs)} test(s) make network calls. Consider mocking or using vcr/vcrpy.",
                    "priority": "high",
                    "example": "# Mock network calls:\n@patch('requests.get')\ndef test_api(mock_get):\n    mock_get.return_value.status_code = 200",
                })
            elif vtype == IsolationViolationType.DATABASE:
                recommendations.append({
                    "category": "database",
                    "message": f"{len(vs)} test(s) access database. Ensure proper transaction rollback or use test database.",
                    "priority": "high",
                    "example": "# Use transactions:\n@pytest.fixture\ndef db_transaction():\n    with db.begin() as tx:\n        yield tx\n        tx.rollback()",
                })
            elif vtype == IsolationViolationType.STATIC_VARIABLE:
                recommendations.append({
                    "category": "static_state",
                    "message": f"{len(vs)} test(s) modify class/static variables. Reset state in setUp/tearDown.",
                    "priority": "high",
                    "example": "# Reset state:\ndef setUp(self):\n    self.__class__.counter = 0",
                })
                
        return recommendations
        
    def get_isolation_report(self, test_code: str) -> Dict[str, Any]:
        """获取隔离性报告.
        
        Args:
            test_code: 测试代码
            
        Returns:
            Dict[str, Any]: 隔离性报告
        """
        try:
            tree = ast.parse(test_code)
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}
            
        all_violations = []
        test_count = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                test_count += 1
                violations = self.analyze_test_function(node)
                all_violations.extend(violations)
                
            elif isinstance(node, ast.ClassDef):
                class_violations = []
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name.startswith("test"):
                        test_count += 1
                        violations = self.analyze_test_function(child, node)
                        class_violations.extend(violations)
                        
                # 检查顺序依赖
                dependencies = self._check_order_dependencies(node)
                if dependencies:
                    for dep in dependencies:
                        class_violations.append(IsolationViolation(
                            violation_type=IsolationViolationType.ORDER_DEPENDENCY,
                            message=f"Test {dep.source_test} depends on {dep.target_test}",
                            line_number=0,
                            test_function=dep.source_test,
                            severity="high",
                        ))
                        
                all_violations.extend(class_violations)
                
        # 统计违规类型
        violations_by_type: Dict[str, int] = {}
        for v in all_violations:
            type_name = v.violation_type.value
            violations_by_type[type_name] = violations_by_type.get(type_name, 0) + 1
            
        isolation_score = self.calculate_isolation_score(all_violations)
        recommendations = self.generate_recommendations(all_violations)
        
        return {
            "isolation_score": isolation_score,
            "test_count": test_count,
            "violation_count": len(all_violations),
            "violations_by_type": violations_by_type,
            "violations": [v.to_dict() for v in all_violations],
            "recommendations": recommendations,
        }
        
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """分析测试文件.
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        path = Path(file_path)
        
        if not path.exists():
            return {"error": f"File not found: {file_path}"}
            
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}
            
        report = self.get_isolation_report(content)
        report["file_path"] = str(file_path)
        
        return report
