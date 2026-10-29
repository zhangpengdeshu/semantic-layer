"""JOIN 规划：认证语义边上的 BFS、路径歧义与 fanout 阻断。"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from shared.config import settings

from app.semantic.domain.entities import SemanticCatalog
from app.semantic.planning.errors import PlanError

REVERSE = {"1:1": "1:1", "N:1": "1:N", "1:N": "N:1", "N:N": "N:N"}

# 路径缓存：仅在快照目录下生效，key = (base_model, target 集合, 快照版本)
_PLAN_CACHE: dict[tuple[int, tuple[int, ...], str], dict[int, list["Step"]]] = {}
_CACHE_LIMIT = 256


@dataclass(slots=True)
class Step:
    edge_id: int
    source_model_id: int
    target_model_id: int
    source_field_id: int
    target_field_id: int
    cardinality: str
    join_type: str
    priority: int
    fanout: bool
    join_predicate: str | None = None


def _step(edge, reverse: bool) -> Step:
    if reverse:
        cardinality = REVERSE[edge.cardinality]
        source_model_id, source_field_id = edge.to_model_id, edge.to_field_id
        target_model_id, target_field_id = edge.from_model_id, edge.from_field_id
    else:
        cardinality = edge.cardinality
        source_model_id, source_field_id = edge.from_model_id, edge.from_field_id
        target_model_id, target_field_id = edge.to_model_id, edge.to_field_id
    return Step(
        edge_id=edge.edge_id,
        source_model_id=source_model_id,
        target_model_id=target_model_id,
        source_field_id=source_field_id,
        target_field_id=target_field_id,
        cardinality=cardinality,
        join_type=edge.join_type,
        priority=edge.priority,
        fanout=cardinality in {"1:N", "N:N"},
        join_predicate=edge.join_predicate,
    )


def distances(base_model_id: int, catalog: SemanticCatalog) -> dict[int, int]:
    """返回 base 模型到其他模型的最短 JOIN 跳数，不校验路径安全性。"""
    adjacency: dict[int, set[int]] = defaultdict(set)
    for edge in catalog.verified_edges():
        adjacency[edge.from_model_id].add(edge.to_model_id)
        adjacency[edge.to_model_id].add(edge.from_model_id)
    distance: dict[int, int] = {base_model_id: 0}
    queue: deque[int] = deque([base_model_id])
    while queue:
        current = queue.popleft()
        for target in adjacency.get(current, set()):
            if target not in distance:
                distance[target] = distance[current] + 1
                queue.append(target)
    return distance


def plan(base_model_id: int, targets: set[int], catalog: SemanticCatalog) -> dict[int, list[Step]]:
    """返回 base 到每个 target 的唯一最短路径；不安全路径直接抛错。"""
    targets = {item for item in targets if item != base_model_id}
    if not targets:
        return {}
    base_model = catalog.models.get(base_model_id)
    if not base_model:
        raise PlanError("model_not_found", f"模型 {base_model_id} 不存在")

    cache_key = None
    if catalog.snapshot_version:
        cache_key = (base_model_id, tuple(sorted(targets)), catalog.snapshot_version)
        cached = _PLAN_CACHE.get(cache_key)
        if cached is not None:
            return {key: list(value) for key, value in cached.items()}

    adjacency: dict[int, list[Step]] = defaultdict(list)
    for edge in catalog.verified_edges():
        adjacency[edge.from_model_id].append(_step(edge, reverse=False))
        adjacency[edge.to_model_id].append(_step(edge, reverse=True))
    for items in adjacency.values():
        items.sort(key=lambda item: (item.priority, item.edge_id))

    distance: dict[int, int] = {base_model_id: 0}
    previous: dict[int, list[Step]] = defaultdict(list)
    queue: deque[int] = deque([base_model_id])
    while queue:
        current = queue.popleft()
        for step in adjacency.get(current, []):
            candidate_distance = distance[current] + 1
            if step.target_model_id not in distance:
                distance[step.target_model_id] = candidate_distance
                previous[step.target_model_id].append(step)
                queue.append(step.target_model_id)
            elif distance[step.target_model_id] == candidate_distance:
                previous[step.target_model_id].append(step)

    result: dict[int, list[Step]] = {}
    for target in targets:
        if target not in distance:
            raise PlanError(
                "join_path_not_found",
                f"模型 {base_model_id} 到 {target} 没有已认证的 JOIN 路径",
                detail={"base_model_id": base_model_id, "target_model_id": target},
            )
        path: list[Step] = []
        node = target
        while node != base_model_id:
            candidates = previous.get(node, [])
            if not candidates:
                raise PlanError("join_path_not_found", f"无法还原到模型 {target} 的 JOIN 路径")
            if len(candidates) > 1:
                priorities = sorts = sorted({item.priority for item in candidates})
                if len(priorities) == 1:
                    # 同优先级多路径：按 edge_id 取最小，但标记为歧义更安全
                    raise PlanError(
                        "join_path_ambiguous",
                        f"模型 {base_model_id} 到 {target} 存在多条同优先级路径",
                        detail={"candidates": [item.edge_id for item in candidates]},
                    )
                candidates.sort(key=lambda item: (item.priority, item.edge_id))
            step = candidates[0]
            path.append(step)
            node = step.source_model_id
        path.reverse()
        path_models = {base_model_id} | {step.target_model_id for step in path}
        hop_limit = min(
            [catalog.models[item].max_hops for item in path_models if item in catalog.models]
            + [int(settings.max_join_hops or 5)]
        )
        if len(path) > hop_limit:
            raise PlanError(
                "join_path_too_long",
                f"模型 {base_model_id} 到 {target} 的路径超过 max_hops={hop_limit}",
                detail={"hops": len(path), "max_hops": hop_limit},
            )
        for step in path:
            if step.cardinality == "N:N":
                raise PlanError(
                    "join_nn_blocked",
                    f"JOIN 边 {step.edge_id} 是 N:N，必须经桥表模型",
                )
            if step.fanout:
                raise PlanError(
                    "join_fanout_risk",
                    f"JOIN 边 {step.edge_id} 会从 1 侧放大到 N 侧，可能造成重复统计",
                    detail={"edge_id": step.edge_id, "cardinality": step.cardinality},
                )
        result[target] = path
    if cache_key is not None:
        if len(_PLAN_CACHE) >= _CACHE_LIMIT:
            _PLAN_CACHE.clear()
        _PLAN_CACHE[cache_key] = {key: list(value) for key, value in result.items()}
    return result