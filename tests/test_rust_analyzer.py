"""Rust 语言代码分析器测试."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from ut_agent.tools.rust_analyzer import RustAnalyzer, RustFunction, RustStruct, RustTrait, RustImpl


class TestRustFunction:
    """Rust 函数模型测试."""

    def test_function_creation(self):
        """测试 Rust 函数创建."""
        func = RustFunction(
            name="calculate",
            params=[{"name": "a", "type": "i32"}, {"name": "b", "type": "i32"}],
            return_type="i32",
            is_async=False,
            is_public=True,
            docstring="Calculate sum"
        )
        assert func.name == "calculate"
        assert func.return_type == "i32"
        assert func.is_public is True
        assert func.is_async is False

    def test_async_function(self):
        """测试异步函数."""
        func = RustFunction(
            name="fetch_data",
            params=[{"name": "url", "type": "String"}],
            return_type="Result<String, Error>",
            is_async=True,
            is_public=True
        )
        assert func.is_async is True
        assert "Result" in func.return_type

    def test_function_signature(self):
        """测试函数签名生成."""
        func = RustFunction(
            name="divide",
            params=[{"name": "a", "type": "f64"}, {"name": "b", "type": "f64"}],
            return_type="Option<f64>",
            is_public=True
        )
        sig = func.get_signature()
        assert "pub fn divide" in sig
        assert "f64" in sig


class TestRustStruct:
    """Rust 结构体模型测试."""

    def test_struct_creation(self):
        """测试 Rust 结构体创建."""
        struct = RustStruct(
            name="UserService",
            fields=[
                {"name": "repo", "type": "Box<dyn UserRepository>", "is_trait": True},
                {"name": "name", "type": "String", "is_trait": False}
            ],
            is_public=True,
            docstring="User service implementation"
        )
        assert struct.name == "UserService"
        assert len(struct.fields) == 2
        assert struct.fields[0]["is_trait"] is True

    def test_get_trait_dependencies(self):
        """测试获取 trait 依赖."""
        struct = RustStruct(
            name="OrderService",
            fields=[
                {"name": "repo", "type": "Box<dyn OrderRepository>", "is_trait": True},
                {"name": "cache", "type": "Arc<dyn Cache>", "is_trait": True},
                {"name": "timeout", "type": "u64", "is_trait": False}
            ],
            is_public=True
        )
        deps = struct.get_trait_dependencies()
        assert "OrderRepository" in deps
        assert "Cache" in deps
        assert "u64" not in deps


class TestRustTrait:
    """Rust Trait 模型测试."""

    def test_trait_creation(self):
        """测试 Rust Trait 创建."""
        trait = RustTrait(
            name="UserRepository",
            methods=[
                {"name": "find_by_id", "params": [{"name": "id", "type": "i64"}], "return_type": "Option<User>"},
                {"name": "save", "params": [{"name": "user", "type": "&User"}], "return_type": "Result<(), Error>"}
            ],
            is_public=True,
            docstring="User repository trait"
        )
        assert trait.name == "UserRepository"
        assert len(trait.methods) == 2


class TestRustImpl:
    """Rust Impl 块模型测试."""

    def test_impl_creation(self):
        """测试 Rust Impl 块创建."""
        impl = RustImpl(
            struct_name="UserService",
            trait_name="Clone",
            methods=["new", "get_user"],
            is_for_trait=True
        )
        assert impl.struct_name == "UserService"
        assert impl.trait_name == "Clone"
        assert impl.is_for_trait is True


class TestRustAnalyzer:
    """Rust 代码分析器测试."""

    @pytest.fixture
    def analyzer(self):
        """创建分析器实例."""
        return RustAnalyzer()

    @pytest.fixture
    def sample_rust_code(self):
        """示例 Rust 代码."""
        return '''
use std::collections::HashMap;
use std::sync::Arc;
use async_trait::async_trait;

/// User repository trait
#[async_trait]
pub trait UserRepository: Send + Sync {
    async fn find_by_id(&self, id: i64) -> Option<User>;
    async fn save(&self, user: &User) -> Result<(), String>;
}

/// User entity
#[derive(Debug, Clone)]
pub struct User {
    pub id: i64,
    pub name: String,
    pub email: String,
}

/// User service
pub struct UserService {
    repo: Arc<dyn UserRepository>,
    cache: HashMap<i64, User>,
}

impl UserService {
    /// Create new user service
    pub fn new(repo: Arc<dyn UserRepository>) -> Self {
        Self {
            repo,
            cache: HashMap::new(),
        }
    }

    /// Get user by ID
    pub async fn get_user(&self, id: i64) -> Option<User> {
        if let Some(user) = self.cache.get(&id) {
            return Some(user.clone());
        }
        self.repo.find_by_id(id).await
    }

    /// Create new user
    pub async fn create_user(&self, name: String, email: String) -> Result<User, String> {
        if name.is_empty() || email.is_empty() {
            return Err("Name and email are required".to_string());
        }
        
        let user = User {
            id: 0,
            name,
            email,
        };
        
        self.repo.save(&user).await?;
        Ok(user)
    }

    // Private helper
    fn validate_email(&self, email: &str) -> bool {
        email.contains('@')
    }
}

impl Clone for UserService {
    fn clone(&self) -> Self {
        Self {
            repo: Arc::clone(&self.repo),
            cache: self.cache.clone(),
        }
    }
}
'''

    def test_analyze_structs(self, analyzer, sample_rust_code):
        """测试分析结构体."""
        result = analyzer.analyze(sample_rust_code)
        
        assert "UserService" in result.structs
        assert "User" in result.structs
        
        user_service = result.structs["UserService"]
        assert len(user_service.fields) == 2
        assert user_service.is_public is True

    def test_analyze_traits(self, analyzer, sample_rust_code):
        """测试分析 trait."""
        result = analyzer.analyze(sample_rust_code)
        
        assert "UserRepository" in result.traits
        
        user_repo = result.traits["UserRepository"]
        assert len(user_repo.methods) == 2
        assert user_repo.is_public is True

    def test_analyze_functions(self, analyzer, sample_rust_code):
        """测试分析函数."""
        result = analyzer.analyze(sample_rust_code)
        
        # 应该找到 impl 块中的方法
        assert "get_user" in result.functions
        assert "create_user" in result.functions
        
        get_user = result.functions["get_user"]
        assert get_user.is_async is True
        assert get_user.is_public is True

    def test_analyze_impls(self, analyzer, sample_rust_code):
        """测试分析 impl 块."""
        result = analyzer.analyze(sample_rust_code)
        
        # 应该找到 UserService 的 impl 块
        user_service_impls = [i for i in result.impls if i.struct_name == "UserService"]
        assert len(user_service_impls) >= 1

    def test_analyze_dependencies(self, analyzer, sample_rust_code):
        """测试分析依赖关系."""
        result = analyzer.analyze(sample_rust_code)
        
        # UserService 应该依赖 UserRepository trait
        user_service = result.structs["UserService"]
        deps = user_service.get_trait_dependencies()
        assert "UserRepository" in deps

    def test_analyze_imports(self, analyzer, sample_rust_code):
        """测试分析导入."""
        result = analyzer.analyze(sample_rust_code)
        
        assert "std::collections::HashMap" in result.imports or "HashMap" in result.imports
        assert "std::sync::Arc" in result.imports or "Arc" in result.imports

    def test_get_testable_functions(self, analyzer, sample_rust_code):
        """测试获取可测试函数."""
        result = analyzer.analyze(sample_rust_code)
        testable = result.get_testable_functions()
        
        # 只返回公开函数
        assert any(f.name == "get_user" for f in testable)
        assert any(f.name == "create_user" for f in testable)
        # 非公开函数不应包含
        assert not any(f.name == "validate_email" for f in testable)

    def test_get_mock_targets(self, analyzer, sample_rust_code):
        """测试获取 Mock 目标."""
        result = analyzer.analyze(sample_rust_code)
        
        mock_targets = result.get_mock_targets("UserService")
        assert "UserRepository" in mock_targets

    def test_analyze_empty_code(self, analyzer):
        """测试分析空代码."""
        result = analyzer.analyze("")
        assert len(result.structs) == 0
        assert len(result.traits) == 0
        assert len(result.functions) == 0

    def test_analyze_invalid_code(self, analyzer):
        """测试分析无效代码."""
        invalid_code = "this is not valid rust code { }"
        result = analyzer.analyze(invalid_code)
        # 应该优雅处理错误
        assert result is not None

    def test_analyze_with_attributes(self, analyzer):
        """测试分析带属性的代码."""
        code = '''
#[derive(Debug, Clone)]
pub struct Calculator {
    value: i32,
}

#[async_trait]
impl Calculator {
    pub async fn add(&self, n: i32) -> i32 {
        self.value + n
    }
}
'''
        result = analyzer.analyze(code)
        
        assert "Calculator" in result.structs
        calc = result.structs["Calculator"]
        assert calc.is_public is True


class TestRustAnalyzerIntegration:
    """Rust 分析器集成测试."""

    def test_analyze_real_rust_file(self, tmp_path):
        """测试分析真实 Rust 文件."""
        rust_file = tmp_path / "service.rs"
        rust_file.write_text('''
pub struct Calculator {
    value: i32,
}

impl Calculator {
    pub fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }
}
''')
        
        analyzer = RustAnalyzer()
        result = analyzer.analyze_file(rust_file)
        
        assert "Calculator" in result.structs
        assert "add" in result.functions

    def test_analyze_directory(self, tmp_path):
        """测试分析目录."""
        # 创建多个 Rust 文件
        (tmp_path / "service.rs").write_text('''
pub struct Service;
impl Service {
    pub fn do_something(&self) {}
}
''')
        (tmp_path / "model.rs").write_text('''
pub struct Model {
    pub id: i32,
}
''')
        
        analyzer = RustAnalyzer()
        results = analyzer.analyze_directory(tmp_path)
        
        assert len(results) == 2
