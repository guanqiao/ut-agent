"""智能测试维护系统单元测试.

测试变更影响分析和测试修复建议功能。
"""

from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pytest

from ut_agent.tools.test_maintenance import (
    ChangeImpactAnalyzer,
    TestMaintenanceSuggester,
    AffectedTest,
    ChangeImpact,
    MaintenanceSuggestion,
)


class TestChangeImpactAnalyzer:
    """变更影响分析器测试."""

    def test_detect_method_signature_change(self):
        """测试检测方法签名变更."""
        old_code = '''
class UserService {
    public User findById(Long id) {
        return userRepository.findById(id);
    }
}
'''
        new_code = '''
class UserService {
    public User findById(Long id, boolean includeDeleted) {
        return userRepository.findById(id, includeDeleted);
    }
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "UserService.java")

        assert len(impacts) > 0
        assert any(i.change_type == "method_signature_change" for i in impacts)

    def test_detect_import_change(self):
        """测试检测导入变更."""
        old_code = '''
import com.example.User;
import com.example.UserService;
'''
        new_code = '''
import com.example.dto.User;
import com.example.service.UserService;
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "UserService.java")

        assert any(i.change_type == "import_change" for i in impacts)

    def test_detect_class_rename(self):
        """测试检测类重命名."""
        old_code = '''
class OldClassName {
    public void method() {}
}
'''
        new_code = '''
class NewClassName {
    public void method() {}
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "OldClassName.java")

        assert any(i.change_type == "class_rename" for i in impacts)

    def test_detect_method_deletion(self):
        """测试检测方法删除."""
        old_code = '''
class Service {
    public void methodA() {}
    public void methodB() {}
}
'''
        new_code = '''
class Service {
    public void methodA() {}
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "Service.java")

        assert any(i.change_type == "method_deletion" for i in impacts)

    def test_detect_field_change(self):
        """测试检测字段变更."""
        old_code = '''
class User {
    private String name;
    private int age;
}
'''
        new_code = '''
class User {
    private String fullName;
    private int age;
    private String email;
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "User.java")

        assert any(i.change_type == "field_change" for i in impacts)

    def test_find_affected_tests(self):
        """测试查找受影响的测试."""
        analyzer = ChangeImpactAnalyzer()
        
        test_files = [
            {"path": "UserServiceTest.java", "content": """
@Test
void testFindById() {
    UserService.findById(id);
}
"""},
            {"path": "UserControllerTest.java", "content": """
@Test
void testFindById() {
    userService.findById(1L);
}
"""},
        ]
        
        impact = ChangeImpact(
            change_type="method_signature_change",
            class_name="UserService",
            method_name="findById",
            old_signature="findById(Long)",
            new_signature="findById(Long, boolean)",
        )
        
        affected = analyzer.find_affected_tests(impact, test_files)
        
        assert len(affected) == 2
        assert all(isinstance(t, AffectedTest) for t in affected)

    def test_analyze_returns_empty_for_no_change(self):
        """测试无变更时返回空列表."""
        code = '''
class Service {
    public void method() {}
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(code, code, "Service.java")

        assert len(impacts) == 0


class TestAffectedTest:
    """受影响测试数据结构测试."""

    def test_affected_test_creation(self):
        """测试创建受影响测试对象."""
        affected = AffectedTest(
            test_file="UserServiceTest.java",
            test_method="testFindById",
            impact_type="method_signature_change",
            severity="high",
            suggested_fix="Update method call with new parameter",
        )

        assert affected.test_file == "UserServiceTest.java"
        assert affected.severity == "high"

    def test_affected_test_to_dict(self):
        """测试转换为字典."""
        affected = AffectedTest(
            test_file="UserServiceTest.java",
            test_method="testFindById",
            impact_type="method_signature_change",
            severity="high",
            suggested_fix="Update method call",
        )

        result = affected.to_dict()

        assert result["test_file"] == "UserServiceTest.java"
        assert result["severity"] == "high"


class TestChangeImpact:
    """变更影响数据结构测试."""

    def test_change_impact_creation(self):
        """测试创建变更影响对象."""
        impact = ChangeImpact(
            change_type="method_signature_change",
            class_name="UserService",
            method_name="findById",
            old_signature="findById(Long)",
            new_signature="findById(Long, boolean)",
        )

        assert impact.change_type == "method_signature_change"
        assert impact.class_name == "UserService"

    def test_change_impact_to_dict(self):
        """测试转换为字典."""
        impact = ChangeImpact(
            change_type="method_deletion",
            class_name="UserService",
            method_name="oldMethod",
        )

        result = impact.to_dict()

        assert result["change_type"] == "method_deletion"
        assert result["method_name"] == "oldMethod"


class TestTestMaintenanceSuggester:
    """测试维护建议生成器测试."""

    def test_suggest_fix_for_signature_change(self):
        """测试为签名变更生成修复建议."""
        suggester = TestMaintenanceSuggester()
        
        impact = ChangeImpact(
            change_type="method_signature_change",
            class_name="UserService",
            method_name="findById",
            old_signature="findById(Long)",
            new_signature="findById(Long, boolean)",
        )
        
        test_code = '''
@Test
void testFindById() {
    User result = userService.findById(1L);
    assertNotNull(result);
}
'''
        
        suggestions = suggester.suggest_fixes(impact, test_code)
        
        assert len(suggestions) > 0
        assert any("findById" in s.fix_code for s in suggestions)

    def test_suggest_fix_for_import_change(self):
        """测试为导入变更生成修复建议."""
        suggester = TestMaintenanceSuggester()
        
        impact = ChangeImpact(
            change_type="import_change",
            old_import="com.example.User",
            new_import="com.example.dto.User",
        )
        
        test_code = '''
import com.example.User;

@Test
void testUser() {
    User user = new User();
}
'''
        
        suggestions = suggester.suggest_fixes(impact, test_code)
        
        assert len(suggestions) > 0
        assert any("import" in s.fix_code.lower() for s in suggestions)

    def test_suggest_fix_for_class_rename(self):
        """测试为类重命名生成修复建议."""
        suggester = TestMaintenanceSuggester()
        
        impact = ChangeImpact(
            change_type="class_rename",
            old_class_name="OldService",
            new_class_name="NewService",
        )
        
        test_code = '''
@Test
void testService() {
    OldService service = new OldService();
}
'''
        
        suggestions = suggester.suggest_fixes(impact, test_code)
        
        assert len(suggestions) > 0
        assert any("NewService" in s.fix_code for s in suggestions)

    def test_suggest_fix_for_deleted_method(self):
        """测试为删除的方法生成建议."""
        suggester = TestMaintenanceSuggester()
        
        impact = ChangeImpact(
            change_type="method_deletion",
            class_name="UserService",
            method_name="deprecatedMethod",
        )
        
        test_code = '''
@Test
void testDeprecatedMethod() {
    userService.deprecatedMethod();
}
'''
        
        suggestions = suggester.suggest_fixes(impact, test_code)
        
        assert len(suggestions) > 0
        assert any(s.suggestion_type == "delete_test" for s in suggestions)

    def test_prioritize_suggestions(self):
        """测试建议优先级排序."""
        suggester = TestMaintenanceSuggester()
        
        suggestions = [
            MaintenanceSuggestion(
                suggestion_type="update_import",
                severity="low",
                fix_code="import com.example.dto.User;",
                description="Update import",
            ),
            MaintenanceSuggestion(
                suggestion_type="update_method_call",
                severity="high",
                fix_code="userService.findById(1L, false);",
                description="Update method call",
            ),
            MaintenanceSuggestion(
                suggestion_type="delete_test",
                severity="medium",
                fix_code="// Delete this test",
                description="Delete deprecated test",
            ),
        ]
        
        prioritized = suggester.prioritize_suggestions(suggestions)
        
        assert prioritized[0].severity == "high"
        assert prioritized[-1].severity == "low"


class TestMaintenanceSuggestion:
    """维护建议数据结构测试."""

    def test_maintenance_suggestion_creation(self):
        """测试创建维护建议对象."""
        suggestion = MaintenanceSuggestion(
            suggestion_type="update_method_call",
            severity="high",
            fix_code="userService.findById(1L, false);",
            description="Add boolean parameter to method call",
            line_number=10,
        )

        assert suggestion.suggestion_type == "update_method_call"
        assert suggestion.severity == "high"
        assert suggestion.line_number == 10

    def test_maintenance_suggestion_to_dict(self):
        """测试转换为字典."""
        suggestion = MaintenanceSuggestion(
            suggestion_type="update_import",
            severity="low",
            fix_code="import com.example.dto.User;",
            description="Update import statement",
        )

        result = suggestion.to_dict()

        assert result["suggestion_type"] == "update_import"
        assert result["severity"] == "low"


class TestIntegration:
    """集成测试."""

    def test_full_maintenance_workflow(self):
        """测试完整的维护工作流."""
        old_code = '''
package com.example;

import com.example.User;

public class UserService {
    public User findById(Long id) {
        return userRepository.findById(id);
    }
    
    public void deprecatedMethod() {
        // deprecated
    }
}
'''
        new_code = '''
package com.example;

import com.example.dto.User;

public class UserService {
    public User findById(Long id, boolean includeDeleted) {
        return userRepository.findById(id, includeDeleted);
    }
}
'''
        test_code = '''
package com.example;

import com.example.User;
import org.junit.jupiter.api.Test;

class UserServiceTest {
    @Test
    void testFindById() {
        User result = userService.findById(1L);
        assertNotNull(result);
    }
    
    @Test
    void testDeprecatedMethod() {
        userService.deprecatedMethod();
    }
}
'''
        analyzer = ChangeImpactAnalyzer()
        impacts = analyzer.analyze(old_code, new_code, "UserService.java")

        assert len(impacts) > 0

        suggester = TestMaintenanceSuggester()
        all_suggestions = []
        for impact in impacts:
            suggestions = suggester.suggest_fixes(impact, test_code)
            all_suggestions.extend(suggestions)

        assert len(all_suggestions) > 0

        prioritized = suggester.prioritize_suggestions(all_suggestions)
        assert prioritized[0].severity in ["high", "medium"]
