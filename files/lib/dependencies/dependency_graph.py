"""
Dependency graph and topological sorting for packages.
"""
from typing import Callable, Dict, List, Optional, Set, Tuple
from lib.core.dependency_cycle_error import DependencyCycleError
from lib.core.deploy_engine_error import DeployEngineError
from lib.discovery.package_registry import PackageRegistry


class DependencyGraph:
    """Построение графа зависимостей пакетов и топологическая сортировка (алгоритм Кана)."""

    def __init__(self, registry: PackageRegistry):
        self.registry = registry

    def resolve_order(self, targets: List[str]) -> List[str]:
        """
        Принимает список целевых пакетов (короткие имена или неймспейсы).
        Возвращает топологически отсортированный список неймспейсов
        в порядке, безопасном для установки (зависимости первыми).
        """
        # 1. Собираем все транзитивные зависимости
        resolved_targets = [self.registry.get(t)["namespace"] for t in targets]
        visited_nodes: Set[str] = set()
        stack: List[str] = list(resolved_targets)

        # Проверка циклов через DFS поиск предков
        def dfs_find_cycle(node: str, current_path: List[str]) -> None:
            if node in current_path:
                cycle_start = current_path.index(node)
                cycle = current_path[cycle_start:] + [node]
                raise DependencyCycleError(cycle)
            pkg = self.registry.get(node)
            for req in pkg.get("requires", []):
                req_ns = self.registry.get(req)["namespace"]
                dfs_find_cycle(req_ns, current_path + [node])

        for target_ns in resolved_targets:
            dfs_find_cycle(target_ns, [])

        # 2. Собираем полное подмножество узлов
        while stack:
            curr = stack.pop()
            if curr not in visited_nodes:
                visited_nodes.add(curr)
                pkg = self.registry.get(curr)
                for req in pkg.get("requires", []):
                    req_ns = self.registry.get(req)["namespace"]
                    if req_ns not in visited_nodes:
                        stack.append(req_ns)

        # 3. Строим граф зависимостей и входящие степени (in-degrees)
        in_degree: Dict[str, int] = {node: 0 for node in visited_nodes}
        adj: Dict[str, List[str]] = {node: [] for node in visited_nodes}

        for node in visited_nodes:
            pkg = self.registry.get(node)
            for req in pkg.get("requires", []):
                req_ns = self.registry.get(req)["namespace"]
                adj[req_ns].append(node)
                in_degree[node] += 1

        # 4. Алгоритм Кана
        queue = [node for node, deg in in_degree.items() if deg == 0]
        order: List[str] = []

        while queue:
            queue.sort()
            curr = queue.pop(0)
            order.append(curr)

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(visited_nodes):
            remaining = [node for node, deg in in_degree.items() if deg > 0]
            raise DeployEngineError(f"Ошибка разрешения графа зависимостей для узлов: {remaining}")

        return order

    def resolve_install_order(
        self,
        targets: List[str],
        is_installed_fn: Optional[Callable[[str], object]] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Возвращает кортеж (список_к_установке, пропущенные_установленные_зависимости).
        Пакеты, указанные в targets явно, никогда не пропускаются; пропускаются только
        подтянутые зависимости из requires, для которых is_installed_fn(node) возвращает истину.
        """
        ordered = self.resolve_order(targets)
        if not is_installed_fn:
            return ordered, []

        explicit_ns = {self.registry.get(t)["namespace"] for t in targets if self.registry.has(t)}
        to_install: List[str] = []
        skipped: List[str] = []

        for node in ordered:
            if node not in explicit_ns and bool(is_installed_fn(node)):
                skipped.append(node)
            else:
                to_install.append(node)

        return to_install, skipped
