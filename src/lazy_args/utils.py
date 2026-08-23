"""Utilities for reporting unresolved lazy dependencies."""

from typing import Any, Mapping


def report_deps_error(pending: Mapping[str, Mapping[str, Any]]) -> str:
    cycle = find_cycle(pending)
    if cycle:
        cycle_str = " -> ".join(cycle)
        return f"Circular lazy dependency detected: {cycle_str}"

    # Defensive fallback; this should normally be unreachable.
    return "Cannot resolve lazy parameters:\n" + "\n".join(
        f"  {name} depends on: " f"{', '.join(sorted(info['deps']))}"
        for name, info in pending.items()
    )


def find_cycle(
    pending: Mapping[str, Mapping[str, Any]],
) -> list[str] | None:
    """Find one dependency cycle among pending nodes."""
    graph = {
        name: {dep for dep in info["deps"] if dep in pending}
        for name, info in pending.items()
    }

    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visiting:
            idx = path.index(node)
            return path[idx:] + [node]

        if node in visited:
            return None

        visiting.add(node)
        path.append(node)

        for dep in graph[node]:
            cycle = dfs(dep)
            if cycle:
                return cycle

        path.pop()
        visiting.remove(node)
        visited.add(node)

        return None

    for node in graph:
        cycle = dfs(node)
        if cycle:
            return cycle

    return None
