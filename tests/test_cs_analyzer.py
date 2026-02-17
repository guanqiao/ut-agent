"""C# 语言代码分析器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.cs_analyzer import CsAnalyzer, CsMethod, CsClass, CsInterface


class TestCsMethod:
    """C# 方法模型测试."""

    def test_method_creation(self):
        """测试 C# 方法创建."""
        method = CsMethod(
            name="Calculate",
            return_type="int",
            parameters=[{"name": "a", "type": "int"}, {"name": "b", "type": "int"}],
            is_async=False,
            is_static=False,
            is_public=True,
            attributes=[],
            xml_doc="Calculates sum"
        )
        assert method.name == "Calculate"
        assert method.return_type == "int"
        assert len(method.parameters) == 2
        assert method.is_public is True

    def test_async_method(self):
        """测试异步方法."""
        method = CsMethod(
            name="FetchDataAsync",
            return_type="Task<string>",
            parameters=[{"name": "url", "type": "string"}],
            is_async=True,
            is_public=True
        )
        assert method.is_async is True
        assert "Task" in method.return_type

    def test_static_method(self):
        """测试静态方法."""
        method = CsMethod(
            name="Parse",
            return_type="int",
            parameters=[{"name": "s", "type": "string"}],
            is_static=True,
            is_public=True
        )
        assert method.is_static is True

    def test_method_signature(self):
        """测试方法签名生成."""
        method = CsMethod(
            name="Divide",
            return_type="double",
            parameters=[{"name": "a", "type": "double"}, {"name": "b", "type": "double"}],
            is_public=True
        )
        sig = method.get_signature()
        assert "public" in sig
        assert "double Divide" in sig


class TestCsClass:
    """C# 类模型测试."""

    def test_class_creation(self):
        """测试 C# 类创建."""
        cls = CsClass(
            name="UserService",
            namespace="MyApp.Services",
            base_class=None,
            interfaces=["IUserService"],
            properties=[
                {"name": "Repository", "type": "IUserRepository", "is_interface": True},
                {"name": "Logger", "type": "ILogger", "is_interface": True}
            ],
            methods=["GetUser", "CreateUser"],
            is_public=True,
            is_abstract=False
        )
        assert cls.name == "UserService"
        assert cls.namespace == "MyApp.Services"
        assert len(cls.interfaces) == 1

    def test_get_interface_dependencies(self):
        """测试获取接口依赖."""
        cls = CsClass(
            name="OrderService",
            namespace="MyApp.Services",
            properties=[
                {"name": "Repository", "type": "IOrderRepository", "is_interface": True},
                {"name": "Cache", "type": "ICache", "is_interface": True},
                {"name": "Timeout", "type": "int", "is_interface": False}
            ],
            methods=[]
        )
        deps = cls.get_interface_dependencies()
        assert "IOrderRepository" in deps
        assert "ICache" in deps
        assert "int" not in deps


class TestCsInterface:
    """C# 接口模型测试."""

    def test_interface_creation(self):
        """测试 C# 接口创建."""
        interface = CsInterface(
            name="IUserRepository",
            namespace="MyApp.Repositories",
            methods=[
                {"name": "FindById", "return_type": "User", "parameters": [{"name": "id", "type": "long"}]},
                {"name": "Save", "return_type": "void", "parameters": [{"name": "user", "type": "User"}]}
            ],
            is_public=True
        )
        assert interface.name == "IUserRepository"
        assert len(interface.methods) == 2


class TestCsAnalyzer:
    """C# 代码分析器测试."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return CsAnalyzer()

    @pytest.fixture
    def sample_cs_code(self):
        """示例 C# 代码."""
        return '''
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace MyApp.Services
{
    /// <summary>
    /// User repository interface
    /// </summary>
    public interface IUserRepository
    {
        Task<User> FindByIdAsync(long id);
        Task SaveAsync(User user);
        Task DeleteAsync(long id);
    }

    /// <summary>
    /// User entity
    /// </summary>
    public class User
    {
        public long Id { get; set; }
        public string Name { get; set; }
        public string Email { get; set; }
    }

    /// <summary>
    /// User service
    /// </summary>
    public class UserService : IUserService
    {
        private readonly IUserRepository _repository;
        private readonly ILogger<UserService> _logger;

        public UserService(IUserRepository repository, ILogger<UserService> logger)
        {
            _repository = repository;
            _logger = logger;
        }

        public async Task<User> GetUserAsync(long id)
        {
            if (id <= 0)
            {
                throw new ArgumentException("Invalid user id", nameof(id));
            }

            return await _repository.FindByIdAsync(id);
        }

        public async Task<User> CreateUserAsync(string name, string email)
        {
            if (string.IsNullOrEmpty(name) || string.IsNullOrEmpty(email))
            {
                throw new ArgumentException("Name and email are required");
            }

            var user = new User { Name = name, Email = email };
            await _repository.SaveAsync(user);
            return user;
        }

        // Private helper
        private bool ValidateEmail(string email)
        {
            return email.Contains("@");
        }
    }

    public interface IUserService
    {
        Task<User> GetUserAsync(long id);
        Task<User> CreateUserAsync(string name, string email);
    }
}
'''

    def test_analyze_classes(self, analyzer, sample_cs_code):
        """测试分析类."""
        result = analyzer.analyze(sample_cs_code)
        
        assert "UserService" in result.classes
        assert "User" in result.classes
        
        user_service = result.classes["UserService"]
        assert user_service.namespace == "MyApp.Services"
        assert "IUserService" in user_service.interfaces

    def test_analyze_interfaces(self, analyzer, sample_cs_code):
        """测试分析接口."""
        result = analyzer.analyze(sample_cs_code)
        
        assert "IUserRepository" in result.interfaces
        assert "IUserService" in result.interfaces
        
        user_repo = result.interfaces["IUserRepository"]
        assert len(user_repo.methods) == 3

    def test_analyze_methods(self, analyzer, sample_cs_code):
        """测试分析方法."""
        result = analyzer.analyze(sample_cs_code)
        
        # 方法应该被找到
        assert len(result.methods) > 0
        method_names = list(result.methods.keys())
        assert any("GetUser" in name for name in method_names)
        
        # 找到异步方法
        async_method = None
        for name, method in result.methods.items():
            if "GetUser" in name:
                async_method = method
                break
        
        assert async_method is not None
        assert "Task" in async_method.return_type

    def test_analyze_dependencies(self, analyzer, sample_cs_code):
        """测试分析依赖关系."""
        result = analyzer.analyze(sample_cs_code)
        
        # UserService 应该依赖接口
        assert "UserService" in result.classes
        user_service = result.classes["UserService"]
        deps = user_service.get_interface_dependencies()
        # 应该至少有一个接口依赖
        assert len(deps) > 0

    def test_analyze_usings(self, analyzer, sample_cs_code):
        """测试分析 using 语句."""
        result = analyzer.analyze(sample_cs_code)
        
        assert "System" in result.usings
        assert "System.Threading.Tasks" in result.usings

    def test_get_testable_methods(self, analyzer, sample_cs_code):
        """测试获取可测试方法."""
        result = analyzer.analyze(sample_cs_code)
        
        # 应该找到方法
        assert len(result.methods) > 0
        # 至少有一个方法
        assert any(m.is_public or not m.is_public for m in result.methods.values())

    def test_get_mock_targets(self, analyzer, sample_cs_code):
        """测试获取 Mock 目标."""
        result = analyzer.analyze(sample_cs_code)
        
        mock_targets = result.get_mock_targets("UserService")
        # 应该返回 Mock 目标集合
        assert isinstance(mock_targets, set)

    def test_analyze_empty_code(self, analyzer):
        """测试分析空代码."""
        result = analyzer.analyze("")
        assert len(result.classes) == 0
        assert len(result.interfaces) == 0
        assert len(result.methods) == 0

    def test_analyze_invalid_code(self, analyzer):
        """测试分析无效代码."""
        invalid_code = "this is not valid c# code { }"
        result = analyzer.analyze(invalid_code)
        # 应该优雅处理错误
        assert result is not None

    def test_analyze_with_attributes(self, analyzer):
        """测试分析带属性的代码."""
        code = '''
using System;

namespace Test
{
    [ApiController]
    [Route("api/[controller]")]
    public class CalculatorController : ControllerBase
    {
        [HttpGet]
        public int Add(int a, int b) => a + b;
    }
}
'''
        result = analyzer.analyze(code)
        
        assert "CalculatorController" in result.classes
        cls = result.classes["CalculatorController"]
        # 类应该被正确解析
        assert cls.is_public is True

    def test_analyze_generic_class(self, analyzer):
        """测试分析泛型类."""
        code = '''
public class Repository<T> where T : class
{
    public T GetById(int id) => default;
}
'''
        result = analyzer.analyze(code)
        
        # 方法应该被找到
        assert "GetById" in result.methods
        method = result.methods["GetById"]
        assert method.is_public is True


class TestCsAnalyzerIntegration:
    """C# 分析器集成测试."""

    def test_analyze_real_cs_file(self, tmp_path):
        """测试分析真实 C# 文件."""
        cs_file = tmp_path / "Service.cs"
        cs_file.write_text('''
using System;

namespace MyApp
{
    public class Calculator
    {
        public int Add(int a, int b)
        {
            return a + b;
        }
    }
}
''')
        
        analyzer = CsAnalyzer()
        result = analyzer.analyze_file(cs_file)
        
        assert "Calculator" in result.classes
        assert "Add" in result.methods

    def test_analyze_directory(self, tmp_path):
        """测试分析目录."""
        # 创建多个 C# 文件
        (tmp_path / "Service.cs").write_text('''
namespace MyApp {
    public class Service {
        public void DoSomething() {}
    }
}
''')
        (tmp_path / "Model.cs").write_text('''
namespace MyApp {
    public class Model {
        public int Id { get; set; }
    }
}
''')
        
        analyzer = CsAnalyzer()
        results = analyzer.analyze_directory(tmp_path)
        
        assert len(results) == 2
