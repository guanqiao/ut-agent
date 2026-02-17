"""路径验证器测试."""

import pytest
from pathlib import Path

from ut_agent.security.path_validator import (
    PathValidator,
    ProjectPathValidator,
    PathValidationError,
    PathValidationConfig,
    PathValidationResult,
    validate_file_path,
    sanitize_path,
)


class TestPathValidationError:
    """路径验证错误测试."""

    def test_error_creation(self):
        """测试错误创建."""
        error = PathValidationError("test message", "/test/path", "invalid_traversal")
        
        assert str(error) == "test message"
        assert error.path == "/test/path"
        assert error.reason == "invalid_traversal"


class TestPathValidator:
    """路径验证器测试."""

    def test_validate_valid_path(self, tmp_path):
        """测试有效路径."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        result = validator.validate("test.txt")
        
        assert result == test_file.resolve()

    def test_validate_empty_path(self, tmp_path):
        """测试空路径."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("")
        
        assert exc_info.value.reason == PathValidationResult.INVALID_TRAVERSAL.value

    def test_validate_null_byte(self, tmp_path):
        """测试空字节."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("test\x00.txt")
        
        assert exc_info.value.reason == PathValidationResult.INVALID_NULL_BYTE.value

    def test_validate_path_traversal(self, tmp_path):
        """测试路径遍历攻击."""
        validator = PathValidator(tmp_path)
        
        # 尝试访问父目录
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("../etc/passwd")
        
        assert exc_info.value.reason == PathValidationResult.INVALID_OUTSIDE_BASE.value

    def test_validate_absolute_path_not_allowed(self, tmp_path):
        """测试不允许绝对路径."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError) as exc_info:
            # Windows 上使用 Windows 绝对路径
            import sys
            if sys.platform == 'win32':
                validator.validate("C:\\Windows\\System32\\config\\sam")
            else:
                validator.validate("/etc/passwd")
        
        # 可能是 INVALID_ABSOLUTE 或 INVALID_OUTSIDE_BASE
        assert exc_info.value.reason in [
            PathValidationResult.INVALID_ABSOLUTE.value,
            PathValidationResult.INVALID_OUTSIDE_BASE.value
        ]

    def test_validate_absolute_path_allowed(self, tmp_path):
        """测试允许绝对路径."""
        config = PathValidationConfig(allow_absolute=True)
        validator = PathValidator(tmp_path, config)
        
        # 在基础目录内的绝对路径应该被允许
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        result = validator.validate(str(test_file.resolve()))
        assert result == test_file.resolve()

    def test_validate_outside_base_dir(self, tmp_path):
        """测试超出基础目录."""
        validator = PathValidator(tmp_path)
        
        # 使用路径遍历尝试访问基础目录外的文件
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("../../outside.txt")
        
        # 可能是 INVALID_ABSOLUTE 或 INVALID_OUTSIDE_BASE
        assert exc_info.value.reason in [
            PathValidationResult.INVALID_ABSOLUTE.value,
            PathValidationResult.INVALID_OUTSIDE_BASE.value
        ]

    def test_validate_extension_not_allowed(self, tmp_path):
        """测试不允许的扩展名."""
        config = PathValidationConfig(allowed_extensions={".txt"})
        validator = PathValidator(tmp_path, config)
        
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("test.exe")
        
        assert "不允许的文件扩展名" in str(exc_info.value)

    def test_validate_extension_allowed(self, tmp_path):
        """测试允许的扩展名."""
        config = PathValidationConfig(allowed_extensions={".txt", ".java"})
        validator = PathValidator(tmp_path, config)
        test_file = tmp_path / "test.java"
        test_file.write_text("content")
        
        result = validator.validate("test.java")
        assert result.suffix == ".java"

    def test_validate_check_exists(self, tmp_path):
        """测试检查文件存在."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("nonexistent.txt", check_exists=True)
        
        assert "文件不存在" in str(exc_info.value)

    def test_validate_path_too_long(self, tmp_path):
        """测试路径过长."""
        config = PathValidationConfig(max_path_length=10)
        validator = PathValidator(tmp_path, config)
        
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate("a" * 20)
        
        assert "路径长度超过限制" in str(exc_info.value)

    def test_is_safe_valid(self, tmp_path):
        """测试 is_safe - 有效路径."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        assert validator.is_safe("test.txt") is True

    def test_is_safe_invalid(self, tmp_path):
        """测试 is_safe - 无效路径."""
        validator = PathValidator(tmp_path)
        
        assert validator.is_safe("../etc/passwd") is False


class TestSanitizeFilename:
    """文件名清理测试."""

    def test_sanitize_removes_path_separators(self):
        """测试移除路径分隔符."""
        validator = PathValidator()
        
        result = validator.sanitize_filename("path/to/file.txt")
        
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_removes_null_bytes(self):
        """测试移除空字节."""
        validator = PathValidator()
        
        result = validator.sanitize_filename("file\x00.txt")
        
        assert "\x00" not in result

    def test_sanitize_removes_control_chars(self):
        """测试移除控制字符."""
        validator = PathValidator()
        
        result = validator.sanitize_filename("file\x01\x02.txt")
        
        assert "\x01" not in result
        assert "\x02" not in result

    def test_sanitize_removes_dangerous_chars(self):
        """测试移除危险字符."""
        validator = PathValidator()
        
        result = validator.sanitize_filename('file<>:"|?*.txt')
        
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert '"' not in result
        assert "|" not in result
        assert "?" not in result
        assert "*" not in result

    def test_sanitize_removes_leading_dots(self):
        """测试移除开头的点."""
        validator = PathValidator()
        
        result = validator.sanitize_filename(".hidden.txt")
        
        assert not result.startswith(".")

    def test_sanitize_limits_length(self):
        """测试限制长度."""
        validator = PathValidator()
        
        long_name = "a" * 300 + ".txt"
        result = validator.sanitize_filename(long_name)
        
        assert len(result) <= 255

    def test_sanitize_empty_name(self):
        """测试空名称."""
        validator = PathValidator()
        
        result = validator.sanitize_filename("...")
        
        assert result == "unnamed"


class TestJoinSafe:
    """安全路径拼接测试."""

    def test_join_safe_basic(self, tmp_path):
        """测试基本拼接."""
        validator = PathValidator(tmp_path)
        
        result = validator.join_safe("dir", "file.txt")
        
        assert result == tmp_path / "dir" / "file.txt"

    def test_join_safe_sanitizes_parts(self, tmp_path):
        """测试清理各部分."""
        validator = PathValidator(tmp_path)
        
        result = validator.join_safe("../dir", "file.txt")
        
        # 应该清理掉 ../
        assert ".." not in str(result)


class TestProjectPathValidator:
    """项目路径验证器测试."""

    def test_project_validator_allows_java(self, tmp_path):
        """测试允许 Java 文件."""
        validator = ProjectPathValidator(tmp_path)
        test_file = tmp_path / "Test.java"
        test_file.write_text("public class Test {}")
        
        result = validator.validate("Test.java")
        
        assert result.suffix == ".java"

    def test_project_validator_allows_python(self, tmp_path):
        """测试允许 Python 文件."""
        validator = ProjectPathValidator(tmp_path)
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")
        
        result = validator.validate("test.py")
        
        assert result.suffix == ".py"

    def test_project_validator_blocks_exe(self, tmp_path):
        """测试阻止可执行文件."""
        validator = ProjectPathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("test.exe")

    def test_project_validator_blocks_sh(self, tmp_path):
        """测试阻止脚本文件."""
        validator = ProjectPathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("test.sh")


class TestValidateFilePath:
    """便捷函数测试."""

    def test_validate_file_path_valid(self, tmp_path):
        """测试有效路径."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # 使用相对于 tmp_path 的路径
        result = validate_file_path(
            "test.txt",
            base_dir=tmp_path,
            allowed_extensions={".txt"}
        )
        
        assert result == test_file.resolve()

    def test_validate_file_path_invalid_extension(self, tmp_path):
        """测试无效扩展名."""
        test_file = tmp_path / "test.exe"
        test_file.write_text("content")
        
        with pytest.raises(PathValidationError):
            validate_file_path(
                str(test_file),
                allowed_extensions={".txt"}
            )


class TestSanitizePath:
    """sanitize_path 便捷函数测试."""

    def test_sanitize_path_basic(self):
        """测试基本清理."""
        result = sanitize_path("path/to/file.txt")
        
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_path_dangerous(self):
        """测试清理危险字符."""
        result = sanitize_path('file<>:"|?*.txt')
        
        assert "<" not in result


class TestPathTraversalAttacks:
    """路径遍历攻击测试."""

    def test_dot_dot_slash_attack(self, tmp_path):
        """测试 ../ 攻击."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("../../../etc/passwd")

    def test_dot_dot_backslash_attack(self, tmp_path):
        """测试 ..\\ 攻击."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("..\\..\\windows\\system32\\config\\sam")

    def test_url_encoded_attack(self, tmp_path):
        """测试 URL 编码攻击."""
        validator = PathValidator(tmp_path)
        
        # URL 编码的 ../ 会被当作普通文件名处理
        # 但如果解析后超出基础目录，应该被拒绝
        result = validator.validate("%2e%2e%2fetc%2fpasswd")
        # URL 编码字符不会被解码，所以这是一个有效的文件名
        assert "%2e%2e%2fetc%2fpasswd" in str(result)

    def test_null_byte_attack(self, tmp_path):
        """测试空字节攻击."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("file.txt\x00.php")

    def test_absolute_path_attack(self, tmp_path):
        """测试绝对路径攻击."""
        validator = PathValidator(tmp_path)
        
        with pytest.raises(PathValidationError):
            validator.validate("/etc/passwd")

    def test_tilde_expansion_attack(self, tmp_path):
        """测试 ~ 扩展攻击."""
        validator = PathValidator(tmp_path)
        
        # ~ 在 Windows 上不会被扩展为用户目录
        # 在 Unix 上，~ 开头的路径如果不在基础目录内会被拒绝
        try:
            result = validator.validate("~/.ssh/id_rsa")
            # 如果通过了，说明 ~ 被当作普通字符处理
            assert "~" in str(result)
        except PathValidationError:
            # 如果被拒绝，也是预期的行为
            pass


class TestEdgeCases:
    """边界情况测试."""

    def test_unicode_filename(self, tmp_path):
        """测试 Unicode 文件名."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "测试文件.txt"
        test_file.write_text("content")
        
        result = validator.validate("测试文件.txt")
        
        assert result.name == "测试文件.txt"

    def test_whitespace_filename(self, tmp_path):
        """测试空格文件名."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "file with spaces.txt"
        test_file.write_text("content")
        
        result = validator.validate("file with spaces.txt")
        
        assert " " in str(result)

    def test_multiple_dots(self, tmp_path):
        """测试多个点."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "file.name.with.dots.txt"
        test_file.write_text("content")
        
        result = validator.validate("file.name.with.dots.txt")
        
        assert result.name == "file.name.with.dots.txt"

    def test_case_sensitivity(self, tmp_path):
        """测试大小写敏感."""
        validator = PathValidator(tmp_path)
        test_file = tmp_path / "Test.Java"
        test_file.write_text("content")
        
        config = PathValidationConfig(allowed_extensions={".java"})
        validator = PathValidator(tmp_path, config)
        
        result = validator.validate("Test.Java")
        
        assert result.suffix.lower() == ".java"
