"""Go 语言代码分析器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.go_analyzer import GoAnalyzer, GoMethod, GoStruct, GoInterface


class TestGoMethod:
    """Go 方法模型测试."""

    def test_method_creation(self):
        """测试 Go 方法创建."""
        method = GoMethod(
            name="Calculate",
            receiver="Calculator",
            params=[{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            returns=[{"type": "int"}],
            is_exported=True,
            docstring="Calculate sum"
        )
        assert method.name == "Calculate"
        assert method.receiver == "Calculator"
        assert len(method.params) == 2
        assert method.is_exported is True

    def test_method_signature_generation(self):
        """测试方法签名生成."""
        method = GoMethod(
            name="Divide",
            receiver="Calculator",
            params=[{"name": "a", "type": "float64"}, {"name": "b", "type": "float64"}],
            returns=[{"type": "float64"}, {"type": "error"}],
            is_exported=True
        )
        signature = method.get_signature()
        assert "Divide" in signature
        assert "float64" in signature


class TestGoStruct:
    """Go 结构体模型测试."""

    def test_struct_creation(self):
        """测试 Go 结构体创建."""
        struct = GoStruct(
            name="UserService",
            fields=[
                {"name": "repo", "type": "UserRepository", "is_interface": True},
                {"name": "logger", "type": "*Logger", "is_interface": False}
            ],
            methods=[],
            docstring="User service implementation"
        )
        assert struct.name == "UserService"
        assert len(struct.fields) == 2
        assert struct.fields[0]["is_interface"] is True

    def test_get_dependencies(self):
        """测试获取结构体依赖."""
        struct = GoStruct(
            name="OrderService",
            fields=[
                {"name": "repo", "type": "OrderRepository", "is_interface": True},
                {"name": "cache", "type": "Cache", "is_interface": True},
                {"name": "timeout", "type": "int", "is_interface": False}
            ],
            methods=[]
        )
        deps = struct.get_interface_dependencies()
        assert "OrderRepository" in deps
        assert "Cache" in deps
        assert "int" not in deps


class TestGoInterface:
    """Go 接口模型测试."""

    def test_interface_creation(self):
        """测试 Go 接口创建."""
        interface = GoInterface(
            name="UserRepository",
            methods=[
                {"name": "FindByID", "params": [{"name": "id", "type": "int"}], "returns": [{"type": "*User"}, {"type": "error"}]},
                {"name": "Save", "params": [{"name": "user", "type": "*User"}], "returns": [{"type": "error"}]}
            ],
            docstring="User repository interface"
        )
        assert interface.name == "UserRepository"
        assert len(interface.methods) == 2


class TestGoAnalyzer:
    """Go 代码分析器测试."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return GoAnalyzer()

    @pytest.fixture
    def sample_go_code(self):
        """示例 Go 代码."""
        return '''
package service

import (
    "context"
    "errors"
    "time"
)

// UserRepository defines user data access interface
type UserRepository interface {
    FindByID(ctx context.Context, id int64) (*User, error)
    Save(ctx context.Context, user *User) error
    Delete(ctx context.Context, id int64) error
}

// User represents a user entity
type User struct {
    ID        int64
    Name      string
    Email     string
    CreatedAt time.Time
}

// UserService handles user business logic
type UserService struct {
    repo   UserRepository
    cache  Cache
    logger *Logger
}

// Cache defines cache interface
type Cache interface {
    Get(key string) (interface{}, error)
    Set(key string, value interface{}, ttl time.Duration) error
}

// NewUserService creates a new user service
func NewUserService(repo UserRepository, cache Cache, logger *Logger) *UserService {
    return &UserService{
        repo:   repo,
        cache:  cache,
        logger: logger,
    }
}

// GetUser retrieves a user by ID
func (s *UserService) GetUser(ctx context.Context, id int64) (*User, error) {
    if id <= 0 {
        return nil, errors.New("invalid user id")
    }
    
    // Try cache first
    if cached, err := s.cache.Get(string(id)); err == nil {
        if user, ok := cached.(*User); ok {
            return user, nil
        }
    }
    
    return s.repo.FindByID(ctx, id)
}

// CreateUser creates a new user
func (s *UserService) CreateUser(ctx context.Context, name, email string) (*User, error) {
    if name == "" || email == "" {
        return nil, errors.New("name and email are required")
    }
    
    user := &User{
        Name:      name,
        Email:     email,
        CreatedAt: time.Now(),
    }
    
    if err := s.repo.Save(ctx, user); err != nil {
        return nil, err
    }
    
    return user, nil
}

// private helper method
func (s *UserService) validateEmail(email string) bool {
    return len(email) > 0 && contains(email, "@")
}

func contains(s, substr string) bool {
    return len(s) > 0 && len(substr) > 0
}
'''

    def test_analyze_structs(self, analyzer, sample_go_code):
        """测试分析结构体."""
        result = analyzer.analyze(sample_go_code)
        
        assert "UserService" in result.structs
        assert "User" in result.structs
        
        user_service = result.structs["UserService"]
        assert len(user_service.fields) == 3
        assert user_service.fields[0]["name"] == "repo"

    def test_analyze_interfaces(self, analyzer, sample_go_code):
        """测试分析接口."""
        result = analyzer.analyze(sample_go_code)
        
        assert "UserRepository" in result.interfaces
        assert "Cache" in result.interfaces
        
        user_repo = result.interfaces["UserRepository"]
        assert len(user_repo.methods) == 3

    def test_analyze_methods(self, analyzer, sample_go_code):
        """测试分析方法."""
        result = analyzer.analyze(sample_go_code)
        
        assert "GetUser" in result.methods
        assert "CreateUser" in result.methods
        
        get_user = result.methods["GetUser"]
        assert get_user.receiver == "UserService"
        assert get_user.is_exported is True

    def test_analyze_dependencies(self, analyzer, sample_go_code):
        """测试分析依赖关系."""
        result = analyzer.analyze(sample_go_code)
        
        # UserService 应该依赖 UserRepository 和 Cache
        user_service = result.structs["UserService"]
        deps = user_service.get_interface_dependencies()
        assert "UserRepository" in deps
        assert "Cache" in deps

    def test_analyze_imports(self, analyzer, sample_go_code):
        """测试分析导入包."""
        result = analyzer.analyze(sample_go_code)
        
        assert "context" in result.imports
        assert "errors" in result.imports
        assert "time" in result.imports

    def test_get_testable_methods(self, analyzer, sample_go_code):
        """测试获取可测试方法."""
        result = analyzer.analyze(sample_go_code)
        testable = result.get_testable_methods()
        
        # 只返回导出方法
        assert any(m.name == "GetUser" for m in testable)
        assert any(m.name == "CreateUser" for m in testable)
        # 非导出方法不应包含
        assert not any(m.name == "validateEmail" for m in testable)

    def test_get_mock_targets(self, analyzer, sample_go_code):
        """测试获取 Mock 目标."""
        result = analyzer.analyze(sample_go_code)
        
        mock_targets = result.get_mock_targets("UserService")
        assert "UserRepository" in mock_targets
        assert "Cache" in mock_targets

    def test_analyze_empty_code(self, analyzer):
        """测试分析空代码."""
        result = analyzer.analyze("")
        assert len(result.structs) == 0
        assert len(result.interfaces) == 0
        assert len(result.methods) == 0

    def test_analyze_invalid_code(self, analyzer):
        """测试分析无效代码."""
        invalid_code = "this is not valid go code { }"
        result = analyzer.analyze(invalid_code)
        # 应该优雅处理错误
        assert result is not None

    def test_analyze_file_with_comments(self, analyzer):
        """测试分析带注释的代码."""
        code = '''
package main

// Calculator performs calculations
type Calculator struct {
    value int
}

// Add adds a number to the calculator
func (c *Calculator) Add(n int) {
    c.value += n
}
'''
        result = analyzer.analyze(code)
        
        assert "Calculator" in result.structs
        calc = result.structs["Calculator"]
        assert calc.docstring == "Calculator performs calculations"


class TestGoAnalyzerIntegration:
    """Go 分析器集成测试."""

    def test_analyze_real_go_file(self, tmp_path):
        """测试分析真实 Go 文件."""
        go_file = tmp_path / "service.go"
        go_file.write_text('''
package service

type Calculator struct{}

func (c *Calculator) Add(a, b int) int {
    return a + b
}
''')
        
        analyzer = GoAnalyzer()
        result = analyzer.analyze_file(go_file)
        
        assert "Calculator" in result.structs
        assert "Add" in result.methods

    def test_analyze_directory(self, tmp_path):
        """测试分析目录."""
        # 创建多个 Go 文件
        (tmp_path / "service.go").write_text('''
package service
type Service struct{}
func (s *Service) Do() {}
''')
        (tmp_path / "model.go").write_text('''
package service
type Model struct{}
''')
        
        analyzer = GoAnalyzer()
        results = analyzer.analyze_directory(tmp_path)
        
        assert len(results) == 2
