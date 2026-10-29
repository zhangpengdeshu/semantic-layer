"""知识上下文：术语、业务规则、资产 Context 与召回测试。"""

from __future__ import annotations

import json
from typing import Any

from app.semantic.repository.catalog_repo import load_catalog
from app.semantic.repository.db import execute, insert, one, rows
from app.semantic.services.errors import ConflictError, NotFoundError, ValidationFailedError


def list_terms(q: str | None = None) -> list[dict[str, Any]]:
    if q:
        return rows(
            "SELECT * FROM t_term WHERE name ILIKE :q OR definition ILIKE :q ORDER BY term_id DESC",
            {"q": f"%{q}%"},
        )
    return rows("SELECT * FROM t_term ORDER BY term_id DESC")


def create_term(payload: dict[str, Any]) -> dict[str, Any]:
    item = insert(
        """
        INSERT INTO t_term (name, synonyms, definition, scope_type, scope_id, status, owner)
        VALUES (:name, CAST(:synonyms AS TEXT[]), :definition, :scope_type, :scope_id, :status, :owner)
        RETURNING *
        """,
        {
            "name": payload["name"],
            "synonyms": payload.get("synonyms") or [],
            "definition": payload.get("definition"),
            "scope_type": payload.get("scope_type", "global"),
            "scope_id": payload.get("scope_id"),
            "status": payload.get("status", "active"),
            "owner": payload.get("owner"),
        },
    )
    return item


def update_term(term_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not one("SELECT term_id FROM t_term WHERE term_id = :id", {"id": term_id}):
        raise NotFoundError("术语不存在", code="term_not_found")
    allowed = {"name", "synonyms", "definition", "scope_type", "scope_id", "status", "owner"}
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(f"UPDATE t_term SET {sets}, updated_at = now() WHERE term_id = :id", {**fields, "id": term_id})
    return one("SELECT * FROM t_term WHERE term_id = :id", {"id": term_id}) or {}


def delete_term(term_id: int) -> None:
    execute("DELETE FROM t_term WHERE term_id = :id", {"id": term_id})


SYNONYM_TARGET_TYPES = {"global", "metric", "term", "dimension", "model", "field"}


def list_synonyms(q: str | None = None) -> list[dict[str, Any]]:
    if q:
        return rows(
            "SELECT * FROM t_sem_synonym WHERE synonym ILIKE :q OR standard_name ILIKE :q ORDER BY synonym_id DESC",
            {"q": f"%{q}%"},
        )
    return rows("SELECT * FROM t_sem_synonym ORDER BY synonym_id DESC")


def _validate_synonym(payload: dict[str, Any]) -> tuple[str, str, str]:
    synonym = (payload.get("synonym") or "").strip()
    standard_name = (payload.get("standard_name") or "").strip()
    target_type = payload.get("target_type") or "global"
    if not synonym:
        raise ValidationFailedError("同义词不能为空", code="synonym_required")
    if not standard_name:
        raise ValidationFailedError("标准词不能为空", code="standard_name_required")
    if target_type not in SYNONYM_TARGET_TYPES:
        raise ValidationFailedError("作用对象类型不合法", code="synonym_target_invalid")
    return synonym, standard_name, target_type


def create_synonym(payload: dict[str, Any]) -> dict[str, Any]:
    synonym, standard_name, target_type = _validate_synonym(payload)
    if one("SELECT synonym_id FROM t_sem_synonym WHERE synonym = :synonym", {"synonym": synonym}):
        raise ConflictError("同义词已存在", code="synonym_conflict")
    return insert(
        """
        INSERT INTO t_sem_synonym (synonym, standard_name, target_type)
        VALUES (:synonym, :standard_name, :target_type)
        RETURNING *
        """,
        {"synonym": synonym, "standard_name": standard_name, "target_type": target_type},
    )


def update_synonym(synonym_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    current = one("SELECT * FROM t_sem_synonym WHERE synonym_id = :id", {"id": synonym_id})
    if not current:
        raise NotFoundError("同义词不存在", code="synonym_not_found")
    synonym, standard_name, target_type = _validate_synonym({**current, **payload})
    duplicated = one(
        "SELECT synonym_id FROM t_sem_synonym WHERE synonym = :synonym AND synonym_id <> :id",
        {"synonym": synonym, "id": synonym_id},
    )
    if duplicated:
        raise ConflictError("同义词已存在", code="synonym_conflict")
    execute(
        """
        UPDATE t_sem_synonym
        SET synonym = :synonym, standard_name = :standard_name, target_type = :target_type, updated_at = now()
        WHERE synonym_id = :id
        """,
        {"synonym": synonym, "standard_name": standard_name, "target_type": target_type, "id": synonym_id},
    )
    return one("SELECT * FROM t_sem_synonym WHERE synonym_id = :id", {"id": synonym_id}) or {}


def delete_synonym(synonym_id: int) -> None:
    execute("DELETE FROM t_sem_synonym WHERE synonym_id = :id", {"id": synonym_id})


def list_rules() -> list[dict[str, Any]]:
    return rows("SELECT * FROM t_business_rule ORDER BY priority, rule_id")


def create_rule(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("condition"):
        raise ValidationFailedError("规则条件不能为空", code="rule_condition_missing")
    return insert(
        """
        INSERT INTO t_business_rule (name, rule_type, target_type, target_id, condition, action, priority, status)
        VALUES (:name, :rule_type, :target_type, :target_id, :condition, :action, :priority, :status)
        RETURNING *
        """,
        {
            "name": payload["name"],
            "rule_type": payload.get("rule_type", "filter"),
            "target_type": payload.get("target_type", "global"),
            "target_id": payload.get("target_id"),
            "condition": payload["condition"],
            "action": payload.get("action", "exclude"),
            "priority": payload.get("priority", 100),
            "status": payload.get("status", "active"),
        },
    )


def update_rule(rule_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not one("SELECT rule_id FROM t_business_rule WHERE rule_id = :id", {"id": rule_id}):
        raise NotFoundError("业务规则不存在", code="rule_not_found")
    allowed = {"name", "rule_type", "target_type", "target_id", "condition", "action", "priority", "status"}
    fields = {key: value for key, value in payload.items() if key in allowed and value is not None}
    if fields:
        sets = ", ".join(f"{key} = :{key}" for key in fields)
        execute(f"UPDATE t_business_rule SET {sets}, updated_at = now() WHERE rule_id = :id", {**fields, "id": rule_id})
    return one("SELECT * FROM t_business_rule WHERE rule_id = :id", {"id": rule_id}) or {}


def delete_rule(rule_id: int) -> None:
    execute("DELETE FROM t_business_rule WHERE rule_id = :id", {"id": rule_id})


def get_context(asset_type: str, asset_id: int) -> dict[str, Any]:
    item = one(
        "SELECT * FROM t_sem_asset_context WHERE asset_type = :asset_type AND asset_id = :asset_id",
        {"asset_type": asset_type, "asset_id": asset_id},
    )
    return item or {"asset_type": asset_type, "asset_id": asset_id, "synonyms": [], "examples": [], "negative_examples": []}


def put_context(asset_type: str, asset_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    item = insert(
        """
        INSERT INTO t_sem_asset_context
          (asset_type, asset_id, business_name, synonyms, definition, examples, negative_examples)
        VALUES
          (:asset_type, :asset_id, :business_name, CAST(:synonyms AS TEXT[]), :definition, CAST(:examples AS JSONB), CAST(:negative_examples AS JSONB))
        ON CONFLICT (asset_type, asset_id) DO UPDATE SET
          business_name = EXCLUDED.business_name,
          synonyms = EXCLUDED.synonyms,
          definition = EXCLUDED.definition,
          examples = EXCLUDED.examples,
          negative_examples = EXCLUDED.negative_examples,
          updated_at = now()
        RETURNING *
        """,
        {
            "asset_type": asset_type,
            "asset_id": asset_id,
            "business_name": payload.get("business_name"),
            "synonyms": payload.get("synonyms") or [],
            "definition": payload.get("definition"),
            "examples": json.dumps(payload.get("examples") or [], ensure_ascii=False),
            "negative_examples": json.dumps(payload.get("negative_examples") or [], ensure_ascii=False),
        },
    )
    return item


def recall_test(question: str) -> dict[str, Any]:
    catalog = load_catalog()
    metrics = []
    for metric in catalog.metrics.values():
        names = {metric.name, metric.business_name, *metric.synonyms}
        if any(name and name in question for name in names):
            metrics.append({"metric_id": metric.metric_id, "name": metric.name, "business_name": metric.business_name})
    dimensions = []
    for dimension in catalog.dimensions.values():
        if dimension.name in question:
            dimensions.append(
                {"dimension_id": dimension.dimension_id, "name": dimension.name, "model_id": dimension.model_id}
            )
    terms = [item for item in list_terms() if item["name"] in question]
    return {"question": question, "metrics": metrics, "dimensions": dimensions, "terms": terms}