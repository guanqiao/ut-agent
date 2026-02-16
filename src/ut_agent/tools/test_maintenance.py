"""智能测试维护系统.

分析代码变更对测试的影响，并生成维护建议。
"""

import re
from dataclasses import dataclass, field
from difflib import unified_diff
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ChangeImpact:
    """代码变更影响."""
    change_type: str
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    old_import: Optional[str] = None
    new_import: Optional[str] = None
    old_class_name: Optional[str] = None
    new_class_name: Optional[str] = None
    field_name: Optional[str] = None
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "old_signature": self.old_signature,
            "new_signature": self.new_signature,
            "old_import": self.old_import,
            "new_import": self.new_import,
            "old_class_name": self.old_class_name,
            "new_class_name": self.new_class_name,
            "field_name": self.field_name,
            "line_number": self.line_number,
        }


@dataclass
class AffectedTest:
    """受影响的测试."""
    test_file: str
    test_method: str
    impact_type: str
    severity: str
    suggested_fix: str
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_file": self.test_file,
            "test_method": self.test_method,
            "impact_type": self.impact_type,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
            "line_number": self.line_number,
        }


@dataclass
class MaintenanceSuggestion:
    """维护建议."""
    suggestion_type: str
    severity: str
    fix_code: str
    description: str
    line_number: Optional[int] = None
    original_code: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_type": self.suggestion_type,
            "severity": self.severity,
            "fix_code": self.fix_code,
            "description": self.description,
            "line_number": self.line_number,
            "original_code": self.original_code,
        }


class ChangeImpactAnalyzer:
    """代码变更影响分析器."""

    METHOD_PATTERN = re.compile(
        r'(?:public|private|protected)?\s*'
        r'(?:static\s+)?'
        r'(\w+(?:<[^>]+>)?)\s+'  # return type
        r'(\w+)\s*'  # method name
        r'\(([^)]*)\)',  # parameters
        re.MULTILINE
    )

    CLASS_PATTERN = re.compile(
        r'class\s+(\w+)\s*(?:extends\s+\w+)?(?:\s*implements\s+[\w,\s]+)?\s*\{',
        re.MULTILINE
    )

    IMPORT_PATTERN = re.compile(
        r'import\s+([\w.]+);',
        re.MULTILINE
    )

    FIELD_PATTERN = re.compile(
        r'(?:public|private|protected)?\s*'
        r'(?:static\s+)?'
        r'(?:final\s+)?'
        r'(\w+(?:<[^>]+>)?)\s+'  # type
        r'(\w+)\s*[;=]',  # name
        re.MULTILINE
    )

    def analyze(
        self,
        old_code: str,
        new_code: str,
        file_name: str,
    ) -> List[ChangeImpact]:
        """分析代码变更的影响.

        Args:
            old_code: 变更前的代码
            new_code: 变更后的代码
            file_name: 文件名

        Returns:
            变更影响列表
        """
        if old_code == new_code:
            return []

        impacts: List[ChangeImpact] = []

        impacts.extend(self._detect_import_changes(old_code, new_code))
        impacts.extend(self._detect_class_rename(old_code, new_code))
        impacts.extend(self._detect_method_changes(old_code, new_code))
        impacts.extend(self._detect_field_changes(old_code, new_code))

        return impacts

    def _detect_import_changes(
        self,
        old_code: str,
        new_code: str,
    ) -> List[ChangeImpact]:
        """检测导入变更."""
        impacts = []

        old_imports = set(self.IMPORT_PATTERN.findall(old_code))
        new_imports = set(self.IMPORT_PATTERN.findall(new_code))

        removed = old_imports - new_imports
        added = new_imports - old_imports

        for old_imp in removed:
            for new_imp in added:
                old_name = old_imp.split('.')[-1]
                new_name = new_imp.split('.')[-1]
                if old_name == new_name:
                    impacts.append(ChangeImpact(
                        change_type="import_change",
                        old_import=old_imp,
                        new_import=new_imp,
                    ))
                    break

        return impacts

    def _detect_class_rename(
        self,
        old_code: str,
        new_code: str,
    ) -> List[ChangeImpact]:
        """检测类重命名."""
        impacts = []

        old_classes = self.CLASS_PATTERN.findall(old_code)
        new_classes = self.CLASS_PATTERN.findall(new_code)

        old_set = set(old_classes)
        new_set = set(new_classes)

        removed = old_set - new_set
        added = new_set - old_set

        if len(removed) == 1 and len(added) == 1:
            old_name = list(removed)[0]
            new_name = list(added)[0]
            impacts.append(ChangeImpact(
                change_type="class_rename",
                old_class_name=old_name,
                new_class_name=new_name,
            ))

        return impacts

    def _detect_method_changes(
        self,
        old_code: str,
        new_code: str,
    ) -> List[ChangeImpact]:
        """检测方法变更."""
        impacts = []

        old_methods = self._extract_methods(old_code)
        new_methods = self._extract_methods(new_code)

        old_by_name = {m['name']: m for m in old_methods}
        new_by_name = {m['name']: m for m in new_methods}

        old_names = set(old_by_name.keys())
        new_names = set(new_by_name.keys())

        for name in old_names - new_names:
            impacts.append(ChangeImpact(
                change_type="method_deletion",
                method_name=name,
                class_name=self._extract_class_name(old_code),
            ))

        for name in new_names - old_names:
            pass

        for name in old_names & new_names:
            old_method = old_by_name[name]
            new_method = new_by_name[name]

            if old_method['params'] != new_method['params']:
                impacts.append(ChangeImpact(
                    change_type="method_signature_change",
                    method_name=name,
                    class_name=self._extract_class_name(new_code),
                    old_signature=f"{name}({old_method['params']})",
                    new_signature=f"{name}({new_method['params']})",
                ))

        return impacts

    def _detect_field_changes(
        self,
        old_code: str,
        new_code: str,
    ) -> List[ChangeImpact]:
        """检测字段变更."""
        impacts = []

        old_fields = self._extract_fields(old_code)
        new_fields = self._extract_fields(new_code)

        old_by_name = {f['name']: f for f in old_fields}
        new_by_name = {f['name']: f for f in new_fields}

        old_names = set(old_by_name.keys())
        new_names = set(new_by_name.keys())

        for name in old_names - new_names:
            impacts.append(ChangeImpact(
                change_type="field_change",
                field_name=name,
                class_name=self._extract_class_name(old_code),
            ))

        for name in new_names - old_names:
            impacts.append(ChangeImpact(
                change_type="field_change",
                field_name=name,
                class_name=self._extract_class_name(new_code),
            ))

        for name in old_names & new_names:
            if old_by_name[name]['type'] != new_by_name[name]['type']:
                impacts.append(ChangeImpact(
                    change_type="field_change",
                    field_name=name,
                    class_name=self._extract_class_name(new_code),
                ))

        return impacts

    def _extract_methods(self, code: str) -> List[Dict[str, str]]:
        """提取方法信息."""
        methods = []
        for match in self.METHOD_PATTERN.finditer(code):
            methods.append({
                'return_type': match.group(1),
                'name': match.group(2),
                'params': match.group(3).strip(),
            })
        return methods

    def _extract_fields(self, code: str) -> List[Dict[str, str]]:
        """提取字段信息."""
        fields = []
        for match in self.FIELD_PATTERN.finditer(code):
            fields.append({
                'type': match.group(1),
                'name': match.group(2),
            })
        return fields

    def _extract_class_name(self, code: str) -> Optional[str]:
        """提取类名."""
        match = self.CLASS_PATTERN.search(code)
        return match.group(1) if match else None

    def find_affected_tests(
        self,
        impact: ChangeImpact,
        test_files: List[Dict[str, str]],
    ) -> List[AffectedTest]:
        """查找受影响的测试.

        Args:
            impact: 变更影响
            test_files: 测试文件列表，每个包含 path 和 content

        Returns:
            受影响的测试列表
        """
        affected = []

        search_pattern = ""
        severity = "medium"

        if impact.change_type == "method_signature_change":
            search_pattern = f"{impact.method_name}"
            severity = "high"
        elif impact.change_type == "method_deletion":
            search_pattern = f"{impact.method_name}"
            severity = "high"
        elif impact.change_type == "class_rename":
            search_pattern = f"{impact.old_class_name}"
            severity = "high"
        elif impact.change_type == "import_change":
            search_pattern = f"{impact.old_import}"
            severity = "medium"
        elif impact.change_type == "field_change":
            search_pattern = f"{impact.field_name}"
            severity = "low"

        if not search_pattern:
            return affected

        for test_file in test_files:
            content = test_file.get("content", "")
            path = test_file.get("path", "")

            if search_pattern in content:
                test_methods = self._extract_test_methods(content)

                for method in test_methods:
                    if search_pattern in method['body']:
                        affected.append(AffectedTest(
                            test_file=path,
                            test_method=method['name'],
                            impact_type=impact.change_type,
                            severity=severity,
                            suggested_fix=self._generate_fix_suggestion(impact, method),
                            line_number=method.get('line_number'),
                        ))

        return affected

    def _extract_test_methods(self, code: str) -> List[Dict[str, Any]]:
        """提取测试方法."""
        test_pattern = re.compile(
            r'@Test\s*(?:\([^)]*\))?\s*'
            r'(?:public\s+)?(?:void\s+)?'
            r'(\w+)\s*\(([^)]*)\)\s*\{',
            re.MULTILINE
        )

        methods = []
        for match in test_pattern.finditer(code):
            method_name = match.group(1)
            start_pos = match.end()

            brace_count = 1
            end_pos = start_pos
            for i, char in enumerate(code[start_pos:], start_pos):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break

            method_body = code[start_pos:end_pos]

            methods.append({
                'name': method_name,
                'body': method_body,
                'line_number': code[:match.start()].count('\n') + 1,
            })

        return methods

    def _generate_fix_suggestion(
        self,
        impact: ChangeImpact,
        method: Dict[str, Any],
    ) -> str:
        """生成修复建议."""
        if impact.change_type == "method_signature_change":
            return f"Update {impact.method_name} call with new parameters"
        elif impact.change_type == "method_deletion":
            return f"Remove or update test for deleted method {impact.method_name}"
        elif impact.change_type == "class_rename":
            return f"Replace {impact.old_class_name} with {impact.new_class_name}"
        elif impact.change_type == "import_change":
            return f"Update import from {impact.old_import} to {impact.new_import}"
        elif impact.change_type == "field_change":
            return f"Update references to field {impact.field_name}"
        return "Review and update test code"


class TestMaintenanceSuggester:
    """测试维护建议生成器."""

    def suggest_fixes(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """生成维护建议.

        Args:
            impact: 变更影响
            test_code: 测试代码

        Returns:
            维护建议列表
        """
        suggestions = []

        if impact.change_type == "method_signature_change":
            suggestions.extend(self._suggest_signature_fix(impact, test_code))
        elif impact.change_type == "import_change":
            suggestions.extend(self._suggest_import_fix(impact, test_code))
        elif impact.change_type == "class_rename":
            suggestions.extend(self._suggest_class_rename_fix(impact, test_code))
        elif impact.change_type == "method_deletion":
            suggestions.extend(self._suggest_deletion_fix(impact, test_code))
        elif impact.change_type == "field_change":
            suggestions.extend(self._suggest_field_fix(impact, test_code))

        return suggestions

    def _suggest_signature_fix(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """为方法签名变更生成建议."""
        suggestions = []

        pattern = re.compile(
            rf'{impact.method_name}\s*\([^)]*\)',
            re.MULTILINE
        )

        for match in pattern.finditer(test_code):
            old_call = match.group(0)

            new_params = self._infer_new_params(impact, old_call)
            new_call = f"{impact.method_name}({new_params})"

            suggestions.append(MaintenanceSuggestion(
                suggestion_type="update_method_call",
                severity="high",
                fix_code=new_call,
                description=f"Update method call from {old_call} to {new_call}",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=old_call,
            ))

        return suggestions

    def _infer_new_params(
        self,
        impact: ChangeImpact,
        old_call: str,
    ) -> str:
        """推断新参数列表."""
        old_params_match = re.search(r'\(([^)]*)\)', old_call)
        old_params = old_params_match.group(1) if old_params_match else ""

        old_param_count = len([p.strip() for p in old_params.split(',') if p.strip()])
        new_param_count = len([p.strip() for p in impact.new_signature.split('(')[1].rstrip(')').split(',') if p.strip()])

        if new_param_count > old_param_count:
            additional_params = ["false", "null", "0", "\"\""]
            params = [p.strip() for p in old_params.split(',') if p.strip()]
            while len(params) < new_param_count:
                params.append(additional_params[len(params) - old_param_count])
            return ", ".join(params)

        return old_params

    def _suggest_import_fix(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """为导入变更生成建议."""
        suggestions = []

        old_import_pattern = re.compile(
            rf'import\s+{re.escape(impact.old_import)}\s*;',
            re.MULTILINE
        )

        for match in old_import_pattern.finditer(test_code):
            old_statement = match.group(0)
            new_statement = f"import {impact.new_import};"

            suggestions.append(MaintenanceSuggestion(
                suggestion_type="update_import",
                severity="low",
                fix_code=new_statement,
                description=f"Update import from {impact.old_import} to {impact.new_import}",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=old_statement,
            ))

        return suggestions

    def _suggest_class_rename_fix(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """为类重命名生成建议."""
        suggestions = []

        class_pattern = re.compile(
            rf'\b{re.escape(impact.old_class_name)}\b',
            re.MULTILINE
        )

        for match in class_pattern.finditer(test_code):
            old_text = match.group(0)

            suggestions.append(MaintenanceSuggestion(
                suggestion_type="update_class_reference",
                severity="high",
                fix_code=impact.new_class_name,
                description=f"Replace {impact.old_class_name} with {impact.new_class_name}",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=old_text,
            ))

        return suggestions

    def _suggest_deletion_fix(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """为删除的方法生成建议."""
        suggestions = []

        test_pattern = re.compile(
            rf'@Test\s*(?:\([^)]*\))?\s*'
            rf'(?:public\s+)?(?:void\s+)?'
            rf'(\w*{re.escape(impact.method_name)}\w*)\s*\([^)]*\)\s*\{{',
            re.MULTILINE | re.IGNORECASE
        )

        for match in test_pattern.finditer(test_code):
            test_name = match.group(1)

            suggestions.append(MaintenanceSuggestion(
                suggestion_type="delete_test",
                severity="medium",
                fix_code=f"// Delete test: {test_name} - method {impact.method_name} was removed",
                description=f"Delete test {test_name} as method {impact.method_name} no longer exists",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=match.group(0),
            ))

        method_call_pattern = re.compile(
            rf'\.{re.escape(impact.method_name)}\s*\([^)]*\)',
            re.MULTILINE
        )

        for match in method_call_pattern.finditer(test_code):
            suggestions.append(MaintenanceSuggestion(
                suggestion_type="delete_method_call",
                severity="high",
                fix_code=f"// Remove: {match.group(0)} - method was deleted",
                description=f"Remove call to deleted method {impact.method_name}",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=match.group(0),
            ))

        return suggestions

    def _suggest_field_fix(
        self,
        impact: ChangeImpact,
        test_code: str,
    ) -> List[MaintenanceSuggestion]:
        """为字段变更生成建议."""
        suggestions = []

        field_pattern = re.compile(
            rf'\.{re.escape(impact.field_name)}\b',
            re.MULTILINE
        )

        for match in field_pattern.finditer(test_code):
            suggestions.append(MaintenanceSuggestion(
                suggestion_type="update_field_reference",
                severity="low",
                fix_code=f"// Review field access: {impact.field_name}",
                description=f"Review access to field {impact.field_name} which has changed",
                line_number=test_code[:match.start()].count('\n') + 1,
                original_code=match.group(0),
            ))

        return suggestions

    def prioritize_suggestions(
        self,
        suggestions: List[MaintenanceSuggestion],
    ) -> List[MaintenanceSuggestion]:
        """按优先级排序建议.

        Args:
            suggestions: 建议列表

        Returns:
            排序后的建议列表
        """
        severity_order = {"high": 0, "medium": 1, "low": 2}

        return sorted(
            suggestions,
            key=lambda s: severity_order.get(s.severity, 3)
        )
