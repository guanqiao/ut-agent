"""依赖注入容器模块 - 统一管理服务依赖."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from inspect import isclass, signature
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, get_origin, get_args

from ut_agent.utils import get_logger

logger = get_logger("container")

T = TypeVar("T")


class ServiceLifetime(Enum):
    """服务生命周期枚举."""

    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class ContainerError(Exception):
    """容器错误."""

    def __init__(self, message: str, service_type: Optional[Type] = None):
        self.service_type = service_type
        super().__init__(message)


@dataclass
class ServiceDescriptor:
    """服务描述符."""

    service_type: Type
    implementation_type: Optional[Type] = None
    instance: Optional[Any] = None
    factory: Optional[Callable] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    parameters: Dict[str, Any] = field(default_factory=dict)


class DependencyContainer:
    """依赖注入容器 - 统一管理服务依赖.

    功能:
    - 服务注册 (单例、瞬态、作用域)
    - 依赖解析
    - 工厂函数支持
    - 容器继承
    - 作用域管理
    """

    def __init__(self, parent: Optional["DependencyContainer"] = None):
        """初始化容器.

        Args:
            parent: 父容器
        """
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._parent = parent

    def register_instance(self, service_type: Type[T], instance: T) -> "DependencyContainer":
        """注册实例.

        Args:
            service_type: 服务类型
            instance: 实例

        Returns:
            DependencyContainer: 容器实例 (支持链式调用)
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance
        logger.debug(f"Registered instance: {service_type.__name__}")
        return self

    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "DependencyContainer":
        """注册单例服务.

        Args:
            service_type: 服务类型
            implementation_type: 实现类型
            parameters: 构造参数

        Returns:
            DependencyContainer: 容器实例
        """
        impl_type = implementation_type or service_type
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=impl_type,
            lifetime=ServiceLifetime.SINGLETON,
            parameters=parameters or {},
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered singleton: {service_type.__name__} -> {impl_type.__name__}")
        return self

    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "DependencyContainer":
        """注册瞬态服务.

        Args:
            service_type: 服务类型
            implementation_type: 实现类型
            parameters: 构造参数

        Returns:
            DependencyContainer: 容器实例
        """
        impl_type = implementation_type or service_type
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=impl_type,
            lifetime=ServiceLifetime.TRANSIENT,
            parameters=parameters or {},
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered transient: {service_type.__name__} -> {impl_type.__name__}")
        return self

    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "DependencyContainer":
        """注册工厂函数.

        Args:
            service_type: 服务类型
            factory: 工厂函数
            lifetime: 生命周期

        Returns:
            DependencyContainer: 容器实例
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered factory: {service_type.__name__}")
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """解析服务.

        Args:
            service_type: 服务类型

        Returns:
            T: 服务实例

        Raises:
            ContainerError: 服务未注册
        """
        descriptor = self._get_descriptor(service_type)

        if descriptor is None:
            if self._parent:
                return self._parent.resolve(service_type)
            raise ContainerError(
                f"Service not registered: {service_type.__name__}",
                service_type=service_type,
            )

        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

            instance = self._create_instance(descriptor)
            self._singletons[service_type] = instance
            return instance

        return self._create_instance(descriptor)

    def try_resolve(self, service_type: Type[T]) -> Optional[T]:
        """尝试解析服务.

        Args:
            service_type: 服务类型

        Returns:
            Optional[T]: 服务实例，未注册则返回 None
        """
        try:
            return self.resolve(service_type)
        except ContainerError:
            return None

    def _get_descriptor(self, service_type: Type) -> Optional[ServiceDescriptor]:
        """获取服务描述符."""
        return self._services.get(service_type)

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建服务实例.

        Args:
            descriptor: 服务描述符

        Returns:
            Any: 服务实例
        """
        if descriptor.factory:
            return descriptor.factory()

        impl_type = descriptor.implementation_type
        if impl_type is None:
            raise ContainerError(
                f"No implementation type for {descriptor.service_type.__name__}",
                service_type=descriptor.service_type,
            )

        try:
            sig = signature(impl_type.__init__)
            kwargs = {}

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                if param_name in descriptor.parameters:
                    kwargs[param_name] = descriptor.parameters[param_name]
                    continue

                param_type = param.annotation
                if param_type != param.empty:
                    actual_type = self._unwrap_optional(param_type)
                    
                    if isclass(actual_type):
                        try:
                            kwargs[param_name] = self.resolve(actual_type)
                        except ContainerError:
                            if param.default != param.empty:
                                kwargs[param_name] = param.default
                    elif param.default != param.empty:
                        kwargs[param_name] = param.default

            return impl_type(**kwargs)

        except Exception as e:
            raise ContainerError(
                f"Failed to create instance of {impl_type.__name__}: {e}",
                service_type=descriptor.service_type,
            )

    def _unwrap_optional(self, type_hint: Any) -> Any:
        """解包 Optional 类型.

        Args:
            type_hint: 类型提示

        Returns:
            Any: 实际类型
        """
        origin = get_origin(type_hint)
        if origin is Union:
            args = get_args(type_hint)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                return non_none_args[0]
        return type_hint

    def is_registered(self, service_type: Type) -> bool:
        """检查服务是否已注册.

        Args:
            service_type: 服务类型

        Returns:
            bool: 是否已注册
        """
        if service_type in self._services:
            return True
        if self._parent:
            return self._parent.is_registered(service_type)
        return False

    def unregister(self, service_type: Type) -> "DependencyContainer":
        """注销服务.

        Args:
            service_type: 服务类型

        Returns:
            DependencyContainer: 容器实例
        """
        if service_type in self._services:
            del self._services[service_type]
        if service_type in self._singletons:
            del self._singletons[service_type]
        return self

    def clear(self) -> None:
        """清空容器."""
        self._services.clear()
        self._singletons.clear()

    def get_registered_services(self) -> List[Type]:
        """获取已注册服务列表.

        Returns:
            List[Type]: 服务类型列表
        """
        services = list(self._services.keys())
        if self._parent:
            services.extend(self._parent.get_registered_services())
        return list(set(services))

    def create_child_container(self) -> "DependencyContainer":
        """创建子容器.

        Returns:
            DependencyContainer: 子容器实例
        """
        return DependencyContainer(parent=self)

    @contextmanager
    def create_scope(self):
        """创建作用域.

        Yields:
            DependencyContainer: 作用域容器
        """
        scope = DependencyContainer(parent=self)
        try:
            yield scope
        finally:
            scope.clear()


class ContainerBuilder:
    """容器构建器 - 流式 API 构建容器."""

    def __init__(self):
        """初始化构建器."""
        self._services: List[tuple] = []

    def add_instance(self, service_type: Type[T], instance: T) -> "ContainerBuilder":
        """添加实例.

        Args:
            service_type: 服务类型
            instance: 实例

        Returns:
            ContainerBuilder: 构建器实例
        """
        self._services.append(("instance", service_type, instance))
        return self

    def add_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "ContainerBuilder":
        """添加单例服务.

        Args:
            service_type: 服务类型
            implementation_type: 实现类型
            parameters: 构造参数

        Returns:
            ContainerBuilder: 构建器实例
        """
        self._services.append(("singleton", service_type, implementation_type, parameters))
        return self

    def add_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> "ContainerBuilder":
        """添加瞬态服务.

        Args:
            service_type: 服务类型
            implementation_type: 实现类型
            parameters: 构造参数

        Returns:
            ContainerBuilder: 构建器实例
        """
        self._services.append(("transient", service_type, implementation_type, parameters))
        return self

    def add_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "ContainerBuilder":
        """添加工厂函数.

        Args:
            service_type: 服务类型
            factory: 工厂函数
            lifetime: 生命周期

        Returns:
            ContainerBuilder: 构建器实例
        """
        self._services.append(("factory", service_type, factory, lifetime))
        return self

    def build(self) -> DependencyContainer:
        """构建容器.

        Returns:
            DependencyContainer: 容器实例
        """
        container = DependencyContainer()

        for item in self._services:
            if item[0] == "instance":
                _, service_type, instance = item
                container.register_instance(service_type, instance)
            elif item[0] == "singleton":
                _, service_type, impl_type, params = item
                container.register_singleton(service_type, impl_type, params)
            elif item[0] == "transient":
                _, service_type, impl_type, params = item
                container.register_transient(service_type, impl_type, params)
            elif item[0] == "factory":
                _, service_type, factory, lifetime = item
                container.register_factory(service_type, factory, lifetime)

        return container


_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """获取全局容器实例.

    Returns:
        DependencyContainer: 容器实例
    """
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def configure_container(builder: ContainerBuilder) -> DependencyContainer:
    """配置全局容器.

    Args:
        builder: 容器构建器

    Returns:
        DependencyContainer: 容器实例
    """
    global _container
    _container = builder.build()
    return _container
