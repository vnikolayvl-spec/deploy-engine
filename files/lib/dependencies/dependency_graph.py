"""
Dependency graph and topological sorting for packages (v3.0.0):
hard requires + SemVer constraints + soft 'after' ordering + CLI argument order tie-breaking.
"""
from typing import Callable, Dict, List, Optional, Set, Tuple
from lib.core.dependency_cycle_error import DependencyCycleError
from lib.core.deploy_engine_error import DeployEngineError
from lib.core.version_utils import (
    format_constraints,
    parse_requirement,
    satisfies_constraints,
)
from lib.discovery.package_registry import PackageRegistry


class DependencyGraph:
    """Построение графа зависимостей пакетов и топологическая сортировка (алгоритм Кана)."""

    def __init__(self, registry: PackageRegistry):
        self.registry = registry

    def _resolve_req(self, raw_req: str, requester_ns: str) -> str:
        """Разрешает имя зависимости и проверяет SemVer-ограничение при его наличии."""
        req_name, constraints = parse_requirement(raw_req)
        req_pkg = self.registry.get(req_name)
        req_ns = req_pkg["namespace"]
        if constraints:
            avail_ver = str(req_pkg.get("version", "1.0.0"))
            if not satisfies_constraints(avail_ver, constraints):
                spec_str = format_constraints(constraints)
                raise DeployEngineError(
                    f"Пакет '{requester_ns}' требует '{req_name}{spec_str}', "
                    f"но в реестре доступна версия v{avail_ver}."
                )
        return req_ns

    @staticmethod
    def _has_path(adj: Dict[str, List[str]], start: str, goal: str) -> bool:
        """Проверяет достижимость goal из start в ориентированном графе."""
        seen: Set[str] = set()
        stack = [start]
        while stack:
            curr = stack.pop()
            if curr == goal:
                return True
            if curr in seen:
                continue
            seen.add(curr)
            stack.extend(adj.get(curr, []))
        return False

    def resolve_order(self, targets: List[str]) -> List[str]:
        """
        Принимает список целевых пакетов (короткие имена или неймспейсы).
        Учитывает:
        1) жесткие зависимости requires (с валидацией SemVer-ограничений),
        2) мягкие зависимости after (только среди пакетов текущего плана),
        3) исходный порядок аргументов CLI для независимых пакетов.
        """
        resolved_targets: List[str] = []
        target_priority: Dict[str, int] = {}
        for idx, t in enumerate(targets):
            ns = self.registry.get(t)["namespace"]
            if ns not in target_priority:
                target_priority[ns] = idx
                resolved_targets.append(ns)

        visited_nodes: Set[str] = set()
        stack: List[str] = list(resolved_targets)

        # 1. Проверка циклов по жестким requires через DFS
        def dfs_find_cycle(node: str, current_path: List[str]) -> None:
            if node in current_path:
                cycle_start = current_path.index(node)
                cycle = current_path[cycle_start:] + [node]
                raise DependencyCycleError(cycle)
            pkg = self.registry.get(node)
            for req in pkg.get("requires", []):
                req_ns = self._resolve_req(req, node)
                dfs_find_cycle(req_ns, current_path + [node])

        for target_ns in resolved_targets:
            dfs_find_cycle(target_ns, [])

        # 2. Собираем полное подмножество узлов (только жесткие requires)
        dep_priority: Dict[str, int] = dict(target_priority)
        while stack:
            curr = stack.pop(0)
            if curr not in visited_nodes:
                visited_nodes.add(curr)
                pkg = self.registry.get(curr)
                parent_prio = dep_priority.get(curr, 10**6)
                for req in pkg.get("requires", []):
                    req_ns = self._resolve_req(req, curr)
                    if req_ns not in dep_priority or parent_prio < dep_priority[req_ns]:
                        dep_priority[req_ns] = parent_prio
                    if req_ns not in visited_nodes:
                        stack.append(req_ns)

        # 3. Строим граф: сначала жесткие ребра requires
        in_degree: Dict[str, int] = {node: 0 for node in visited_nodes}
        adj: Dict[str, List[str]] = {node: [] for node in visited_nodes}

        for node in visited_nodes:
            pkg = self.registry.get(node)
            seen_reqs: Set[str] = set()
            for req in pkg.get("requires", []):
                req_ns = self._resolve_req(req, node)
                if req_ns not in seen_reqs and req_ns != node:
                    seen_reqs.add(req_ns)
                    adj[req_ns].append(node)
                    in_degree[node] += 1

        # 4. Добавляем мягкие ребра 'after' только среди узлов плана (без создания циклов)
        for node in sorted(visited_nodes):
            pkg = self.registry.get(node)
            for after_raw in pkg.get("after", []) or []:
                after_name, _ = parse_requirement(after_raw)
                if not after_name or not self.registry.has(after_name):
                    continue
                after_ns = self.registry.get(after_name)["namespace"]
                if after_ns not in visited_nodes or after_ns == node:
                    continue
                if node in adj[after_ns]:
                    continue
                if not self._has_path(adj, node, after_ns):
                    adj[after_ns].append(node)
                    in_degree[node] += 1

        # 5. Алгоритм Кана с сохранением порядка CLI-аргументов как tie-breaker
        queue = [node for node, deg in in_degree.items() if deg == 0]
        order: List[str] = []

        def _sort_key(n: str) -> Tuple[int, int, str]:
            is_explicit = 0 if n in target_priority else 1
            return (dep_priority.get(n, 10**9), is_explicit, n)

        while queue:
            queue.sort(key=_sort_key)
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
