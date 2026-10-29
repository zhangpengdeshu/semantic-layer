"""数据集 / 物理目录服务：只读镜像与同步。"""

from __future__ import annotations

from typing import Any

from app.semantic.repository.db import execute, insert, one, page_params, rows
from app.semantic.services.errors import NotFoundError, ValidationFailedError


def list_datasets(q: str | None = None, source_system: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page, page_size = page_params(page, page_size)
    where = ["1=1"]
    params: dict[str, Any] = {}
    if q:
        where.append("(d.dataset_name ILIKE :q OR d.dataset_code ILIKE :q OR d.table_name ILIKE :q)")
        params["q"] = f"%{q}%"
    if source_system:
        where.append("d.source_system = :source_system")
        params["source_system"] = source_system
    clause = " AND ".join(where)
    total = one(f"SELECT count(*) AS total FROM t_ext_dataset d WHERE {clause}", params)["total"]
    items = rows(
        f"""
        SELECT d.*,
               (SELECT count(*) FROM t_ext_column c WHERE c.dataset_id = d.dataset_id) AS column_count
        FROM t_ext_dataset d
        WHERE {clause}
        ORDER BY d.dataset_id DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_dataset(dataset_id: int) -> dict[str, Any]:
    dataset = one("SELECT * FROM t_ext_dataset WHERE dataset_id = :id", {"id": dataset_id})
    if not dataset:
        raise NotFoundError("数据集不存在", code="dataset_not_found")
    dataset["columns"] = rows(
        "SELECT * FROM t_ext_column WHERE dataset_id = :id ORDER BY ordinal NULLS LAST, column_id",
        {"id": dataset_id},
    )
    return dataset


def list_tables(q: str | None = None, source_system: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page, page_size = page_params(page, page_size)
    where = ["1=1"]
    params: dict[str, Any] = {}
    if q:
        where.append("(t.table_name ILIKE :q OR t.business_name ILIKE :q OR t.query_ref ILIKE :q)")
        params["q"] = f"%{q}%"
    if source_system:
        where.append("t.source_system = :source_system")
        params["source_system"] = source_system
    clause = " AND ".join(where)
    total = one(f"SELECT count(*) AS total FROM t_meta_table t WHERE {clause}", params)["total"]
    items = rows(
        f"""
        SELECT t.*,
               (SELECT count(*) FROM t_meta_column c WHERE c.table_id = t.table_id) AS column_count
        FROM t_meta_table t
        WHERE {clause}
        ORDER BY t.table_id DESC
        LIMIT :limit OFFSET :offset
        """,
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_table(table_id: int) -> dict[str, Any]:
    table = one("SELECT * FROM t_meta_table WHERE table_id = :id", {"id": table_id})
    if not table:
        raise NotFoundError("物理表不存在", code="table_not_found")
    table["columns"] = rows(
        "SELECT * FROM t_meta_column WHERE table_id = :id ORDER BY ordinal NULLS LAST, column_id",
        {"id": table_id},
    )
    table["keys"] = rows("SELECT * FROM t_meta_key WHERE table_id = :id ORDER BY key_id", {"id": table_id})
    return table


def sync_datasets(payload: dict[str, Any]) -> dict[str, Any]:
    """接收外部目录同步。payload: {source_system, datasets:[{external_dataset_id, ..., columns:[]}]}"""
    source_system = payload.get("source_system")
    datasets = payload.get("datasets") or []
    if not source_system:
        raise ValidationFailedError("source_system 不能为空", code="source_system_missing")
    count = 0
    for dataset in datasets:
        external_id = str(dataset.get("external_dataset_id") or "")
        if not external_id:
            raise ValidationFailedError("external_dataset_id 不能为空", code="external_dataset_id_missing")
        row = insert(
            """
            INSERT INTO t_ext_dataset
              (source_system, external_dataset_id, dataset_code, dataset_name, schema_name,
               table_name, description, status, source_version, synced_at)
            VALUES
              (:source_system, :external_dataset_id, :dataset_code, :dataset_name, :schema_name,
               :table_name, :description, :status, :source_version, now())
            ON CONFLICT (source_system, external_dataset_id) DO UPDATE SET
              dataset_code = EXCLUDED.dataset_code,
              dataset_name = EXCLUDED.dataset_name,
              schema_name = EXCLUDED.schema_name,
              table_name = EXCLUDED.table_name,
              description = EXCLUDED.description,
              status = EXCLUDED.status,
              source_version = EXCLUDED.source_version,
              synced_at = now()
            RETURNING dataset_id
            """,
            {
                "source_system": source_system,
                "external_dataset_id": external_id,
                "dataset_code": dataset.get("dataset_code"),
                "dataset_name": dataset.get("dataset_name"),
                "schema_name": dataset.get("schema_name"),
                "table_name": dataset.get("table_name"),
                "description": dataset.get("description"),
                "status": dataset.get("status", "active"),
                "source_version": dataset.get("source_version"),
            },
        )
        dataset_id = int(row["dataset_id"])
        execute("DELETE FROM t_ext_column WHERE dataset_id = :id", {"id": dataset_id})
        for ordinal, column in enumerate(dataset.get("columns") or [], start=1):
            execute(
                """
                INSERT INTO t_ext_column
                  (dataset_id, column_name, column_type, business_name, ordinal, sample_value, nullable)
                VALUES
                  (:dataset_id, :column_name, :column_type, :business_name, :ordinal, :sample_value, :nullable)
                """,
                {
                    "dataset_id": dataset_id,
                    "column_name": column["column_name"],
                    "column_type": column.get("column_type"),
                    "business_name": column.get("business_name"),
                    "ordinal": column.get("ordinal", ordinal),
                    "sample_value": column.get("sample_value"),
                    "nullable": column.get("nullable", True),
                },
            )
        count += 1
    return {"synced": count}


def columns_for_binding(binding: dict[str, Any]) -> list[dict[str, Any]]:
    """根据绑定类型返回可映射的物理列。"""
    if binding.get("binding_type") == "dataset":
        dataset = None
        if binding.get("external_dataset_id"):
            dataset = one(
                "SELECT dataset_id FROM t_ext_dataset WHERE external_dataset_id = :id ORDER BY dataset_id DESC LIMIT 1",
                {"id": binding["external_dataset_id"]},
            )
        if dataset:
            return rows(
                "SELECT * FROM t_ext_column WHERE dataset_id = :id ORDER BY ordinal NULLS LAST, column_id",
                {"id": dataset["dataset_id"]},
            )
    table_id = binding.get("table_id")
    if not table_id and binding.get("query_ref"):
        table = one("SELECT table_id FROM t_meta_table WHERE query_ref = :ref", {"ref": binding["query_ref"]})
        table_id = table["table_id"] if table else None
    if table_id:
        return rows(
            "SELECT * FROM t_meta_column WHERE table_id = :id ORDER BY ordinal NULLS LAST, column_id",
            {"id": table_id},
        )
    return []