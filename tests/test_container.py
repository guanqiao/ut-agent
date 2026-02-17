"""依赖注入容器测试模块."""

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable
from unittest.mock import MagicMock

import pytest

from ut_agent.core.container import (
    DependencyContainer,
    ServiceLifetime,
    ServiceDescriptor,
    ContainerError,
)


@runtime_checkable
class ILogger(Protocol):
    """日志接口."""

    def log(self, message: str) -> None: ...


@runtime_checkable
class IDatabase(Protocol):
    """数据库接口."""

    def query(self, sql: str) -> list: ...


@dataclass
class MockLogger:
    """Mock 日志实现."""

    name: str = "mock_logger"
    messages: list = None

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


@dataclass
class MockDatabase:
    """Mock 数据库实现."""

    connection_string: str = "mock://db"
    logger: Optional[MockLogger] = None

    def query(self, sql: str) -> list:
        if self.logger:
            self.logger.log(f"Query: {sql}")
        return [{"id": 1, "name": "test"}]


class TestServiceDescriptor:
    """ServiceDescriptor 测试."""

    def test_transient_descriptor(self):
        """测试瞬态服务描述符."""
        descriptor = ServiceDescriptor(
            service_type=ILogger,
            implementation_type=MockLogger,
            lifetime=ServiceLifetime.TRANSIENT,
        )

        assert descriptor.service_type == ILogger
        assert descriptor.implementation_type == MockLogger
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_singleton_descriptor(self):
        """测试单例服务描述符."""
        instance = MockLogger()
        descriptor = ServiceDescriptor(
            service_type=ILogger,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )

        assert descriptor.instance == instance
        assert descriptor.lifetime == ServiceLifetime.SINGLETON


class TestDependencyContainer:
    """DependencyContainer 测试."""

    @pytest.fixture
    def container(self):
        """创建容器实例."""
        return DependencyContainer()

    def test_container_initialization(self, container):
        """测试容器初始化."""
        assert container._services == {}
        assert container._singletons == {}

    def test_register_instance(self, container):
        """测试注册实例."""
        logger = MockLogger()
        container.register_instance(ILogger, logger)

        resolved = container.resolve(ILogger)
        assert resolved == logger

    def test_register_singleton(self, container):
        """测试注册单例."""
        container.register_singleton(ILogger, MockLogger)

        instance1 = container.resolve(ILogger)
        instance2 = container.resolve(ILogger)

        assert instance1 == instance2
        assert isinstance(instance1, MockLogger)

    def test_register_transient(self, container):
        """测试注册瞬态服务."""
        container.register_transient(ILogger, MockLogger)

        instance1 = container.resolve(ILogger)
        instance2 = container.resolve(ILogger)

        assert instance1 is not instance2
        assert isinstance(instance1, MockLogger)
        assert isinstance(instance2, MockLogger)

    def test_register_factory(self, container):
        """测试注册工厂函数."""
        call_count = 0

        def create_logger():
            nonlocal call_count
            call_count += 1
            return MockLogger(name=f"logger_{call_count}")

        container.register_factory(ILogger, create_logger, ServiceLifetime.TRANSIENT)

        instance1 = container.resolve(ILogger)
        instance2 = container.resolve(ILogger)

        assert instance1.name == "logger_1"
        assert instance2.name == "logger_2"

    def test_resolve_with_dependencies(self, container):
        """测试解析带依赖的服务."""
        container.register_singleton(MockLogger, MockLogger)
        container.register_transient(MockDatabase, MockDatabase)

        db = container.resolve(MockDatabase)

        assert isinstance(db, MockDatabase)
        assert db.logger is not None
        assert isinstance(db.logger, MockLogger)

    def test_resolve_unregistered_service(self, container):
        """测试解析未注册的服务."""
        with pytest.raises(ContainerError):
            container.resolve(ILogger)

    def test_try_resolve_success(self, container):
        """测试尝试解析成功."""
        container.register_instance(ILogger, MockLogger())

        result = container.try_resolve(ILogger)
        assert result is not None

    def test_try_resolve_failure(self, container):
        """测试尝试解析失败."""
        result = container.try_resolve(ILogger)
        assert result is None

    def test_is_registered(self, container):
        """测试检查服务是否已注册."""
        assert not container.is_registered(ILogger)

        container.register_instance(ILogger, MockLogger())
        assert container.is_registered(ILogger)

    def test_unregister(self, container):
        """测试注销服务."""
        container.register_instance(ILogger, MockLogger())
        assert container.is_registered(ILogger)

        container.unregister(ILogger)
        assert not container.is_registered(ILogger)

    def test_clear(self, container):
        """测试清空容器."""
        container.register_instance(ILogger, MockLogger())
        container.register_instance(IDatabase, MockDatabase())

        container.clear()

        assert not container.is_registered(ILogger)
        assert not container.is_registered(IDatabase)

    def test_get_registered_services(self, container):
        """测试获取已注册服务列表."""
        container.register_instance(ILogger, MockLogger())
        container.register_instance(IDatabase, MockDatabase())

        services = container.get_registered_services()

        assert ILogger in services
        assert IDatabase in services

    def test_singleton_factory_caching(self, container):
        """测试单例工厂缓存."""
        call_count = 0

        def create_logger():
            nonlocal call_count
            call_count += 1
            return MockLogger()

        container.register_factory(ILogger, create_logger, ServiceLifetime.SINGLETON)

        container.resolve(ILogger)
        container.resolve(ILogger)
        container.resolve(ILogger)

        assert call_count == 1

    def test_scoped_resolution(self, container):
        """测试作用域解析."""
        container.register_singleton(ILogger, MockLogger)

        with container.create_scope() as scope:
            logger1 = scope.resolve(ILogger)
            logger2 = scope.resolve(ILogger)

            assert logger1 == logger2

    def test_nested_dependencies(self, container):
        """测试嵌套依赖."""
        @dataclass
        class ServiceA:
            name: str = "A"

        @dataclass
        class ServiceB:
            a: ServiceA
            name: str = "B"

        @dataclass
        class ServiceC:
            b: ServiceB
            name: str = "C"

        container.register_singleton(ServiceA, ServiceA)
        container.register_singleton(ServiceB, ServiceB)
        container.register_singleton(ServiceC, ServiceC)

        c = container.resolve(ServiceC)

        assert c.name == "C"
        assert c.b.name == "B"
        assert c.b.a.name == "A"

    def test_register_with_parameters(self, container):
        """测试带参数的注册."""
        container.register_singleton(
            ILogger,
            MockLogger,
            parameters={"name": "custom_logger"},
        )

        logger = container.resolve(ILogger)
        assert logger.name == "custom_logger"


class TestDependencyContainerIntegration:
    """DependencyContainer 集成测试."""

    def test_full_dependency_injection_workflow(self):
        """测试完整依赖注入工作流."""
        container = DependencyContainer()

        container.register_singleton(MockLogger, MockLogger)
        container.register_transient(MockDatabase, MockDatabase)

        db1 = container.resolve(MockDatabase)
        db2 = container.resolve(MockDatabase)

        assert db1 is not db2
        assert db1.logger == db2.logger

        db1.query("SELECT * FROM users")
        assert len(db1.logger.messages) == 1

    def test_container_inheritance(self):
        """测试容器继承."""
        parent = DependencyContainer()
        parent.register_singleton(ILogger, MockLogger)

        child = parent.create_child_container()
        child.register_transient(IDatabase, MockDatabase)

        assert child.is_registered(ILogger)
        assert child.is_registered(IDatabase)

        logger_from_child = child.resolve(ILogger)
        logger_from_parent = parent.resolve(ILogger)

        assert logger_from_child == logger_from_parent


class TestContainerBuilder:
    """ContainerBuilder 测试."""

    def test_builder_pattern(self):
        """测试构建器模式."""
        from ut_agent.core.container import ContainerBuilder

        container = (
            ContainerBuilder()
            .add_singleton(ILogger, MockLogger)
            .add_transient(IDatabase, MockDatabase)
            .build()
        )

        assert container.is_registered(ILogger)
        assert container.is_registered(IDatabase)

    def test_builder_with_configuration(self):
        """测试带配置的构建器."""
        from ut_agent.core.container import ContainerBuilder

        container = (
            ContainerBuilder()
            .add_singleton(ILogger, MockLogger, parameters={"name": "configured"})
            .build()
        )

        logger = container.resolve(ILogger)
        assert logger.name == "configured"
