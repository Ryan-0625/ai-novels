"""
DI Container 单元测试 - Phase 1 Core层
真实环境测试，不使用Mock
"""

import pytest
from typing import Optional
from abc import ABC, abstractmethod

import sys
sys.path.insert(0, "e:/VScode(study)/Project/AI-Novels/src")

from ai_novels.core.di_container import (
    DIContainer,
    ServiceProvider,
    ServiceDescriptor,
    ServiceScope,
    Lifecycle,
    ServiceNotFoundError,
    DependencyResolutionError,
    get_global_container,
    get_global_provider,
)


# 测试用的接口和实现
class IDatabase(ABC):
    """数据库接口"""
    @abstractmethod
    def query(self, sql: str) -> list:
        pass


class MySQLDatabase(IDatabase):
    """MySQL实现"""
    def __init__(self):
        self.name = "MySQL"
    
    def query(self, sql: str) -> list:
        return [{"result": f"MySQL: {sql}"}]


class PostgreSQLDatabase(IDatabase):
    """PostgreSQL实现"""
    def __init__(self):
        self.name = "PostgreSQL"
    
    def query(self, sql: str) -> list:
        return [{"result": f"PostgreSQL: {sql}"}]


class ICache(ABC):
    """缓存接口"""
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass


class MemoryCache(ICache):
    """内存缓存实现"""
    def __init__(self):
        self._data = {}
    
    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)
    
    def set(self, key: str, value: str):
        self._data[key] = value


class ServiceWithDependency:
    """有依赖的服务"""
    def __init__(self, database: IDatabase, cache: ICache):
        self.database = database
        self.cache = cache


class ServiceWithOptionalDependency:
    """有可选依赖的服务"""
    def __init__(self, database: IDatabase, name: str = "default"):
        self.database = database
        self.name = name


class StandaloneService:
    """独立服务，无依赖"""
    def __init__(self):
        self.value = 42


class TestLifecycle:
    """测试生命周期枚举"""
    
    def test_lifecycle_values(self):
        """测试生命周期枚举值"""
        assert Lifecycle.SINGLETON.value == "singleton"
        assert Lifecycle.SCOPED.value == "scoped"
        assert Lifecycle.TRANSIENT.value == "transient"


class TestServiceDescriptor:
    """测试 ServiceDescriptor 类"""
    
    def test_descriptor_init(self):
        """测试描述符初始化"""
        descriptor = ServiceDescriptor(
            interface=IDatabase,
            implementation=MySQLDatabase,
            lifecycle=Lifecycle.SINGLETON
        )
        
        assert descriptor.interface == IDatabase
        assert descriptor.implementation == MySQLDatabase
        assert descriptor.lifecycle == Lifecycle.SINGLETON
        assert descriptor.instance is None


class TestDIContainer:
    """测试 DIContainer 类"""
    
    @pytest.fixture
    def container(self):
        """提供干净的 DIContainer 实例"""
        return DIContainer()
    
    def test_container_init(self, container):
        """测试容器初始化"""
        assert container._descriptors == {}
        assert container._provider is None
    
    def test_register_service(self, container):
        """测试注册服务"""
        container.register(IDatabase, MySQLDatabase)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor is not None
        assert descriptor.interface == IDatabase
        assert descriptor.implementation == MySQLDatabase
    
    def test_register_singleton(self, container):
        """测试注册单例服务"""
        container.register_singleton(IDatabase, MySQLDatabase)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor.lifecycle == Lifecycle.SINGLETON
    
    def test_register_scoped(self, container):
        """测试注册作用域服务"""
        container.register_scoped(IDatabase, MySQLDatabase)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor.lifecycle == Lifecycle.SCOPED
    
    def test_register_transient(self, container):
        """测试注册瞬态服务"""
        container.register_transient(IDatabase, MySQLDatabase)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor.lifecycle == Lifecycle.TRANSIENT
    
    def test_register_instance(self, container):
        """测试注册现有实例"""
        instance = MySQLDatabase()
        container.register_instance(IDatabase, instance)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor.instance is instance
        assert descriptor.lifecycle == Lifecycle.SINGLETON
    
    def test_register_with_factory(self, container):
        """测试使用工厂函数注册"""
        def factory(provider):
            return MySQLDatabase()
        
        container.register(IDatabase, MySQLDatabase, factory=factory)
        
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor.factory is factory
    
    def test_register_multiple_implementations(self, container):
        """测试注册多个实现"""
        container.register(IDatabase, MySQLDatabase)
        container.register(IDatabase, PostgreSQLDatabase)
        
        descriptors = container.get_descriptors(IDatabase)
        assert len(descriptors) == 2
    
    def test_chained_registration(self, container):
        """测试链式注册"""
        result = container.register(IDatabase, MySQLDatabase).register(ICache, MemoryCache)
        
        assert result is container
        assert container.get_descriptor(IDatabase) is not None
        assert container.get_descriptor(ICache) is not None
    
    def test_get_descriptor_not_found(self, container):
        """测试获取未注册的服务描述符"""
        descriptor = container.get_descriptor(IDatabase)
        assert descriptor is None
    
    def test_build_provider(self, container):
        """测试构建服务提供者"""
        provider = container.build_provider()
        
        assert provider is not None
        assert isinstance(provider, ServiceProvider)
        assert container._provider is provider


class TestServiceProvider:
    """测试 ServiceProvider 类"""
    
    @pytest.fixture
    def provider(self):
        """提供配置好的 ServiceProvider"""
        container = DIContainer()
        container.register_transient(IDatabase, MySQLDatabase)
        container.register_transient(ICache, MemoryCache)
        return container.build_provider()
    
    def test_get_service(self, provider):
        """测试获取服务"""
        service = provider.get_service(IDatabase)
        
        assert service is not None
        assert isinstance(service, MySQLDatabase)
    
    def test_get_service_not_found(self, provider):
        """测试获取未注册的服务"""
        # 使用未注册的接口
        class IUnknown:
            pass
        
        service = provider.get_service(IUnknown)
        assert service is None
    
    def test_get_required_service(self, provider):
        """测试获取必需的服务"""
        service = provider.get_required_service(IDatabase)
        
        assert service is not None
        assert isinstance(service, MySQLDatabase)
    
    def test_get_required_service_not_found(self, provider):
        """测试获取未注册的必需服务"""
        class IUnknown:
            pass
        
        with pytest.raises(ServiceNotFoundError):
            provider.get_required_service(IUnknown)
    
    def test_get_services_multiple(self, provider):
        """测试获取多个服务实现"""
        # 先注册多个实现
        container = DIContainer()
        container.register(IDatabase, MySQLDatabase)
        container.register(IDatabase, PostgreSQLDatabase)
        provider = container.build_provider()
        
        services = provider.get_services(IDatabase)
        
        assert len(services) == 2
        assert any(isinstance(s, MySQLDatabase) for s in services)
        assert any(isinstance(s, PostgreSQLDatabase) for s in services)
    
    def test_create_instance_no_dependencies(self, provider):
        """测试创建无依赖的实例"""
        instance = provider.create_instance(StandaloneService)
        
        assert instance is not None
        assert isinstance(instance, StandaloneService)
        assert instance.value == 42
    
    def test_create_instance_with_dependencies(self, provider):
        """测试创建有依赖的实例（自动注入）"""
        instance = provider.create_instance(ServiceWithDependency)
        
        assert instance is not None
        assert isinstance(instance.database, MySQLDatabase)
        assert isinstance(instance.cache, MemoryCache)
    
    def test_create_instance_with_optional_params(self, provider):
        """测试创建有可选参数的实例"""
        instance = provider.create_instance(ServiceWithOptionalDependency)
        
        assert instance is not None
        assert isinstance(instance.database, MySQLDatabase)
        assert instance.name == "default"  # 使用默认值
    
    def test_singleton_lifecycle(self):
        """测试单例生命周期"""
        container = DIContainer()
        container.register_singleton(IDatabase, MySQLDatabase)
        provider = container.build_provider()
        
        # 获取两次应该是同一个实例
        instance1 = provider.get_service(IDatabase)
        instance2 = provider.get_service(IDatabase)
        
        assert instance1 is instance2
    
    def test_transient_lifecycle(self):
        """测试瞬态生命周期"""
        container = DIContainer()
        container.register_transient(IDatabase, MySQLDatabase)
        provider = container.build_provider()
        
        # 获取两次应该是不同实例
        instance1 = provider.get_service(IDatabase)
        instance2 = provider.get_service(IDatabase)
        
        assert instance1 is not instance2
        assert isinstance(instance1, MySQLDatabase)
        assert isinstance(instance2, MySQLDatabase)
    
    def test_scoped_lifecycle(self):
        """测试作用域生命周期"""
        container = DIContainer()
        container.register_scoped(IDatabase, MySQLDatabase)
        provider = container.build_provider()
        
        # 创建作用域
        scope = provider.create_scope()
        provider.set_current_scope(scope)
        
        # 在作用域内获取两次应该是同一个实例
        instance1 = provider.get_service(IDatabase)
        instance2 = provider.get_service(IDatabase)
        
        assert instance1 is instance2
        
        scope.dispose()
    
    def test_scoped_without_scope_raises(self):
        """测试在无作用域时获取作用域服务应抛出异常"""
        container = DIContainer()
        container.register_scoped(IDatabase, MySQLDatabase)
        provider = container.build_provider()
        
        # 不设置作用域，直接获取
        with pytest.raises(RuntimeError):
            provider.get_service(IDatabase)


class TestServiceScope:
    """测试 ServiceScope 类"""
    
    def test_scope_get_or_create(self):
        """测试作用域获取或创建实例"""
        container = DIContainer()
        provider = container.build_provider()
        scope = ServiceScope(provider)
        
        call_count = 0
        
        def factory():
            nonlocal call_count
            call_count += 1
            return MySQLDatabase()
        
        # 第一次获取
        instance1 = scope.get_or_create(IDatabase, factory)
        # 第二次获取（应该返回缓存的实例）
        instance2 = scope.get_or_create(IDatabase, factory)
        
        assert instance1 is instance2
        assert call_count == 1  # 工厂只被调用一次
    
    def test_scope_dispose(self):
        """测试作用域释放"""
        container = DIContainer()
        provider = container.build_provider()
        scope = ServiceScope(provider)
        
        # 创建一些实例
        scope.get_or_create(IDatabase, lambda: MySQLDatabase())
        
        assert len(scope._instances) == 1
        
        scope.dispose()
        
        assert len(scope._instances) == 0


class TestCircularDependencyDetection:
    """测试循环依赖检测"""
    
    def test_no_circular_dependencies(self):
        """测试无循环依赖"""
        container = DIContainer()
        container.register(IDatabase, MySQLDatabase)
        container.register(ICache, MemoryCache)
        
        cycles = container.check_circular_dependencies()
        
        assert len(cycles) == 0
    
    def test_circular_dependencies_detected(self):
        """测试检测到循环依赖"""
        # 创建循环依赖的类 - 使用前置声明
        container = DIContainer()
        
        # 先定义两个互相依赖的接口
        class IServiceA:
            pass
        
        class IServiceB:
            pass
        
        # 再定义实现类
        class ServiceAImpl:
            def __init__(self, b: IServiceB):
                self.b = b
        
        class ServiceBImpl:
            def __init__(self, a: IServiceA):
                self.a = a
        
        # 注册到容器
        container.register(IServiceA, ServiceAImpl)
        container.register(IServiceB, ServiceBImpl)
        
        cycles = container.check_circular_dependencies()
        
        # 应该检测到循环
        assert len(cycles) > 0


class TestGlobalContainer:
    """测试全局容器"""
    
    def test_get_global_container_singleton(self):
        """测试全局容器是单例"""
        container1 = get_global_container()
        container2 = get_global_container()
        
        assert container1 is container2
    
    def test_get_global_provider_singleton(self):
        """测试全局提供者是单例"""
        provider1 = get_global_provider()
        provider2 = get_global_provider()
        
        assert provider1 is provider2


class TestExceptions:
    """测试异常类"""
    
    def test_service_not_found_error(self):
        """测试 ServiceNotFoundError"""
        error = ServiceNotFoundError("Test error")
        
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_dependency_resolution_error(self):
        """测试 DependencyResolutionError"""
        error = DependencyResolutionError("Test error")
        
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
