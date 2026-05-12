"""
依赖注入容器

@file: core/di_container.py
@date: 2026-04-08
@version: 2.0.0
@description: 依赖注入容器实现，支持生命周期管理、循环依赖检测
"""

import inspect
import threading
from typing import Any, Dict, Type, TypeVar, Callable, Optional, List, Set
from functools import wraps
from enum import Enum

T = TypeVar('T')


class Lifecycle(Enum):
    """服务生命周期"""
    SINGLETON = "singleton"      # 单例，全局唯一
    SCOPED = "scoped"            # 作用域内唯一
    TRANSIENT = "transient"      # 每次创建新实例


class ServiceDescriptor:
    """服务描述符"""
    
    def __init__(
        self,
        interface: Type,
        implementation: Type,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        factory: Callable = None,
        instance: Any = None
    ):
        self.interface = interface
        self.implementation = implementation
        self.lifecycle = lifecycle
        self.factory = factory
        self.instance = instance
        self._lock = threading.Lock()
    
    def get_instance(self, provider: 'ServiceProvider') -> Any:
        """获取服务实例"""
        if self.lifecycle == Lifecycle.SINGLETON:
            if self.instance is None:
                with self._lock:
                    if self.instance is None:
                        self.instance = self._create_instance(provider)
            return self.instance
        
        elif self.lifecycle == Lifecycle.SCOPED:
            # 从作用域获取
            scope = provider.get_current_scope()
            if scope is None:
                raise RuntimeError("Scoped service requested outside of scope")
            return scope.get_or_create(self.interface, lambda: self._create_instance(provider))
        
        else:  # TRANSIENT
            return self._create_instance(provider)
    
    def _create_instance(self, provider: 'ServiceProvider') -> Any:
        """创建实例"""
        if self.factory:
            return self.factory(provider)
        
        # 使用构造函数注入
        return provider.create_instance(self.implementation)


class ServiceScope:
    """服务作用域"""
    
    def __init__(self, provider: 'ServiceProvider'):
        self.provider = provider
        self._instances: Dict[Type, Any] = {}
        self._lock = threading.Lock()
    
    def get_or_create(self, interface: Type, factory: Callable) -> Any:
        """获取或创建实例"""
        if interface not in self._instances:
            with self._lock:
                if interface not in self._instances:
                    self._instances[interface] = factory()
        return self._instances[interface]
    
    def dispose(self):
        """释放作用域资源"""
        for instance in self._instances.values():
            if hasattr(instance, 'dispose'):
                instance.dispose()
            elif hasattr(instance, 'close'):
                instance.close()
        self._instances.clear()


class ServiceProvider:
    """
    服务提供者（优化版）
    
    优化点：
    1. 服务实例缓存 - 减少重复解析开销
    2. 性能统计 - 监控服务解析性能
    3. 缓存预热 - 支持预加载常用服务
    """
    
    def __init__(self, container: 'DIContainer', enable_cache: bool = True):
        self._container = container
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[int, ServiceScope] = {}
        self._current_scope: Optional[ServiceScope] = None
        self._lock = threading.Lock()
        
        # 服务实例缓存（优化重复解析）
        self._enable_cache = enable_cache
        self._instance_cache: Dict[Type, Any] = {}
        self._cache_lock = threading.RLock()
        
        # 性能统计
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'singleton_hits': 0,
            'scoped_hits': 0,
            'transient_creates': 0,
            'total_requests': 0
        }
        self._stats_lock = threading.Lock()
    
    def get_service(self, interface: Type[T], use_cache: bool = True) -> Optional[T]:
        """
        获取服务（带缓存优化）
        
        Args:
            interface: 服务接口类型
            use_cache: 是否使用实例缓存
            
        Returns:
            服务实例或None
        """
        # 更新统计
        with self._stats_lock:
            self._stats['total_requests'] += 1
        
        # 尝试从缓存获取（仅对Singleton和Scoped有效）
        if self._enable_cache and use_cache:
            cached = self._get_from_cache(interface)
            if cached is not None:
                with self._stats_lock:
                    self._stats['cache_hits'] += 1
                return cached
            with self._stats_lock:
                self._stats['cache_misses'] += 1
        
        # 从容器获取
        descriptor = self._container.get_descriptor(interface)
        if descriptor is None:
            return None
        
        instance = descriptor.get_instance(self)
        
        # 更新统计
        if descriptor.lifecycle == Lifecycle.SINGLETON:
            with self._stats_lock:
                self._stats['singleton_hits'] += 1
        elif descriptor.lifecycle == Lifecycle.SCOPED:
            with self._stats_lock:
                self._stats['scoped_hits'] += 1
        else:
            with self._stats_lock:
                self._stats['transient_creates'] += 1
        
        # 缓存实例（仅缓存Singleton和Scoped）
        if self._enable_cache and use_cache and descriptor.lifecycle != Lifecycle.TRANSIENT:
            self._add_to_cache(interface, instance)
        
        return instance
    
    def _get_from_cache(self, interface: Type) -> Any:
        """从缓存获取服务实例"""
        with self._cache_lock:
            return self._instance_cache.get(interface)
    
    def _add_to_cache(self, interface: Type, instance: Any):
        """添加服务实例到缓存"""
        with self._cache_lock:
            self._instance_cache[interface] = instance
    
    def invalidate_cache(self, interface: Type = None):
        """
        使缓存失效
        
        Args:
            interface: 指定接口类型，None则清空所有缓存
        """
        with self._cache_lock:
            if interface is None:
                self._instance_cache.clear()
            else:
                self._instance_cache.pop(interface, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取服务解析统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()
            total = stats['total_requests']
            stats['cache_hit_rate'] = round(stats['cache_hits'] / total, 4) if total > 0 else 0
            stats['cache_size'] = len(self._instance_cache)
            return stats
    
    def warmup_cache(self, interfaces: List[Type]):
        """
        预热缓存 - 预加载常用服务
        
        Args:
            interfaces: 需要预热的服务接口列表
        """
        for interface in interfaces:
            try:
                self.get_service(interface, use_cache=True)
            except Exception as e:
                # 预热失败不影响主流程
                pass
    
    def get_required_service(self, interface: Type[T]) -> T:
        """获取必需的服务"""
        service = self.get_service(interface)
        if service is None:
            raise ServiceNotFoundError(f"Service {interface.__name__} not registered")
        return service
    
    def get_services(self, interface: Type[T]) -> List[T]:
        """获取所有实现该接口的服务"""
        descriptors = self._container.get_descriptors(interface)
        return [d.get_instance(self) for d in descriptors]
    
    def create_instance(self, implementation: Type[T]) -> T:
        """
        创建实例（自动注入依赖）
        
        通过检查构造函数参数，自动解析并注入依赖
        """
        # 获取构造函数签名
        try:
            sig = inspect.signature(implementation.__init__)
            params = list(sig.parameters.items())[1:]  # 跳过self
        except (ValueError, TypeError):
            # 没有__init__或无法获取签名
            return implementation()
        
        # 解析依赖
        kwargs = {}
        for name, param in params:
            if param.default is not inspect.Parameter.empty:
                # 有默认值，跳过
                continue
            
            # 获取参数类型
            param_type = param.annotation
            if param_type is inspect.Parameter.empty:
                raise DependencyResolutionError(
                    f"Cannot resolve parameter '{name}' in {implementation.__name__}: "
                    "no type annotation"
                )
            
            # 解析依赖
            dependency = self.get_service(param_type)
            if dependency is None:
                raise DependencyResolutionError(
                    f"Cannot resolve dependency '{param_type.__name__}' for parameter '{name}' "
                    f"in {implementation.__name__}"
                )
            
            kwargs[name] = dependency
        
        return implementation(**kwargs)
    
    def create_scope(self) -> ServiceScope:
        """创建新的作用域"""
        scope = ServiceScope(self)
        with self._lock:
            self._scoped_instances[id(scope)] = scope
        return scope
    
    def get_current_scope(self) -> Optional[ServiceScope]:
        """获取当前作用域"""
        return self._current_scope
    
    def set_current_scope(self, scope: Optional[ServiceScope]):
        """设置当前作用域"""
        self._current_scope = scope


class DIContainer:
    """
    依赖注入容器
    
    支持：
    - 服务注册（接口->实现）
    - 生命周期管理（Singleton/Scoped/Transient）
    - 构造函数自动注入
    - 循环依赖检测
    - 工厂函数支持
    """
    
    def __init__(self):
        self._descriptors: Dict[Type, List[ServiceDescriptor]] = {}
        self._provider: Optional[ServiceProvider] = None
        self._lock = threading.Lock()
    
    def register(
        self,
        interface: Type,
        implementation: Type = None,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        factory: Callable = None,
        instance: Any = None
    ) -> 'DIContainer':
        """
        注册服务
        
        Args:
            interface: 服务接口
            implementation: 实现类（可选，默认为接口本身）
            lifecycle: 生命周期
            factory: 工厂函数（可选）
            instance: 现有实例（用于Singleton）
            
        Returns:
            self，支持链式调用
        """
        if implementation is None:
            implementation = interface
        
        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            lifecycle=lifecycle,
            factory=factory,
            instance=instance
        )
        
        with self._lock:
            if interface not in self._descriptors:
                self._descriptors[interface] = []
            self._descriptors[interface].append(descriptor)
        
        return self
    
    def register_instance(self, interface: Type, instance: Any) -> 'DIContainer':
        """
        注册现有实例（单例）
        
        Args:
            interface: 服务接口
            instance: 现有实例
            
        Returns:
            self，支持链式调用
        """
        return self.register(
            interface=interface,
            implementation=type(instance),
            lifecycle=Lifecycle.SINGLETON,
            instance=instance
        )
    
    def register_singleton(
        self,
        interface: Type,
        implementation: Type = None,
        factory: Callable = None
    ) -> 'DIContainer':
        """
        注册单例服务
        
        Args:
            interface: 服务接口
            implementation: 实现类
            factory: 工厂函数
            
        Returns:
            self，支持链式调用
        """
        return self.register(
            interface=interface,
            implementation=implementation,
            lifecycle=Lifecycle.SINGLETON,
            factory=factory
        )
    
    def register_scoped(
        self,
        interface: Type,
        implementation: Type = None,
        factory: Callable = None
    ) -> 'DIContainer':
        """
        注册作用域服务
        
        Args:
            interface: 服务接口
            implementation: 实现类
            factory: 工厂函数
            
        Returns:
            self，支持链式调用
        """
        return self.register(
            interface=interface,
            implementation=implementation,
            lifecycle=Lifecycle.SCOPED,
            factory=factory
        )
    
    def register_transient(
        self,
        interface: Type,
        implementation: Type = None,
        factory: Callable = None
    ) -> 'DIContainer':
        """
        注册瞬态服务
        
        Args:
            interface: 服务接口
            implementation: 实现类
            factory: 工厂函数
            
        Returns:
            self，支持链式调用
        """
        return self.register(
            interface=interface,
            implementation=implementation,
            lifecycle=Lifecycle.TRANSIENT,
            factory=factory
        )
    
    def get_descriptor(self, interface: Type) -> Optional[ServiceDescriptor]:
        """获取服务描述符"""
        descriptors = self._descriptors.get(interface, [])
        return descriptors[0] if descriptors else None
    
    def get_descriptors(self, interface: Type) -> List[ServiceDescriptor]:
        """获取所有服务描述符"""
        return self._descriptors.get(interface, [])
    
    def build_provider(self) -> ServiceProvider:
        """构建服务提供者"""
        self._provider = ServiceProvider(self)
        return self._provider
    
    def check_circular_dependencies(self) -> List[List[Type]]:
        """
        检测循环依赖
        
        Returns:
            循环依赖链列表
        """
        cycles = []
        visited: Set[Type] = set()
        rec_stack: Set[Type] = set()
        path: List[Type] = []
        
        def dfs(interface: Type):
            visited.add(interface)
            rec_stack.add(interface)
            path.append(interface)
            
            descriptor = self.get_descriptor(interface)
            if descriptor:
                # 检查实现类的构造函数依赖
                impl = descriptor.implementation
                try:
                    sig = inspect.signature(impl.__init__)
                    params = list(sig.parameters.items())[1:]
                    
                    for name, param in params:
                        if param.default is not inspect.Parameter.empty:
                            continue
                        
                        dep_type = param.annotation
                        if dep_type is inspect.Parameter.empty:
                            continue
                        
                        if dep_type in rec_stack:
                            # 发现循环
                            cycle_start = path.index(dep_type)
                            cycles.append(path[cycle_start:] + [dep_type])
                        elif dep_type not in visited:
                            dfs(dep_type)
                except (ValueError, TypeError):
                    pass
            
            path.pop()
            rec_stack.remove(interface)
        
        for interface in self._descriptors:
            if interface not in visited:
                dfs(interface)
        
        return cycles


class ServiceNotFoundError(Exception):
    """服务未找到异常"""
    pass


class DependencyResolutionError(Exception):
    """依赖解析异常"""
    pass


# 全局容器实例
_global_container: Optional[DIContainer] = None
_global_provider: Optional[ServiceProvider] = None


def get_global_container() -> DIContainer:
    """获取全局容器"""
    global _global_container
    if _global_container is None:
        _global_container = DIContainer()
    return _global_container


def get_global_provider() -> ServiceProvider:
    """获取全局服务提供者"""
    global _global_provider
    if _global_provider is None:
        container = get_global_container()
        _global_provider = container.build_provider()
    return _global_provider


def inject(interface: Type[T]) -> T:
    """
    注入装饰器
    
    用于函数参数注入
    
    Example:
        @inject(DatabaseService)
        def my_function(db: DatabaseService):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            provider = get_global_provider()
            service = provider.get_required_service(interface)
            
            # 获取函数签名
            sig = inspect.signature(func)
            param_name = None
            for name, param in sig.parameters.items():
                if param.annotation == interface:
                    param_name = name
                    break
            
            if param_name:
                kwargs[param_name] = service
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class Inject:
    """
    依赖注入辅助类
    
    用于类属性注入
    
    Example:
        class MyService:
            db: DatabaseService = Inject(DatabaseService)
    """
    
    def __init__(self, interface: Type[T]):
        self.interface = interface
        self._value: Optional[T] = None
    
    def __get__(self, instance, owner) -> T:
        if self._value is None:
            provider = get_global_provider()
            self._value = provider.get_required_service(self.interface)
        return self._value
    
    def __set__(self, instance, value):
        self._value = value


def configure_services(configure: Callable[[DIContainer], None]) -> ServiceProvider:
    """
    配置服务
    
    Args:
        configure: 配置函数，接收DIContainer参数
        
    Returns:
        ServiceProvider实例
        
    Example:
        def configure(container: DIContainer):
            container.register_singleton(DatabaseService, MySQLDatabaseService)
            container.register_transient(ILogger, ConsoleLogger)
        
        provider = configure_services(configure)
    """
    container = get_global_container()
    configure(container)
    
    # 检查循环依赖
    cycles = container.check_circular_dependencies()
    if cycles:
        cycle_strs = [" -> ".join(t.__name__ for t in cycle) for cycle in cycles]
        raise DependencyResolutionError(
            f"Circular dependencies detected: {', '.join(cycle_strs)}"
        )
    
    return container.build_provider()
