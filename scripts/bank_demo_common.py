"""银行场景写入语义层的公共工具。

每个银行场景一个脚本（seed_bank_*.py），共享本模块的 API 调用、建模、绑定、
校验、认证、发布与问数逻辑。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import bindparam, text  # noqa: E402

from app.main import app  # noqa: E402
from shared.db import write_session  # noqa: E402

API = "/api/semantic/v1"
HEADERS = {"X-User-Id": "demo-modeler", "X-Roles": "admin,modeler,engineer,reviewer"}
SOURCE_SYSTEM = "bank_demo"
client = TestClient(app)


def api(method: str, path: str, payload: Any = None, params: Any = None) -> Any:
    kwargs: dict[str, Any] = {"headers": HEADERS}
    if payload is not None:
        kwargs["json"] = payload
    if params is not None:
        kwargs["params"] = params
    response = getattr(client, method)(f"{API}{path}", **kwargs)
    try:
        body = response.json()
    except ValueError:  # pragma: no cover
        raise RuntimeError(f"{method.upper()} {path} -> {response.status_code}: {response.text}")
    if response.status_code >= 400:
        raise RuntimeError(f"{method.upper()} {path} -> {response.status_code}: {body}")
    return body.get("data", body)


def step(title: str) -> None:
    print(f"\n=== {title}")


def field(name, business, semantic_type, data_type, synonyms=None, sensitivity=None):
    item = {
        "name": name,
        "business_name": business,
        "semantic_type": semantic_type,
        "data_type": data_type,
    }
    if synonyms:
        item["synonyms"] = synonyms
    if sensitivity:
        item["sensitivity"] = sensitivity
    return item


def ensure_domain(name: str, description: str, owner: str) -> int:
    page = api("get", "/domains", params={"q": name, "page_size": 50})
    for item in page.get("items", []):
        if item["name"] == name:
            return int(item["domain_id"])
    item = api(
        "post",
        "/domains",
        {
            "name": name,
            "description": description,
            "owner": owner,
            "members": [{"user_id": "demo-modeler", "role": "modeler"}],
        },
    )
    return int(item["domain_id"])


def _table_meta(tables: list[str]) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    with write_session() as session:
        for table in tables:
            columns = session.execute(
                text(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :table
                    ORDER BY ordinal_position
                    """
                ),
                {"table": table},
            ).fetchall()
            sample = session.execute(text(f'SELECT * FROM public."{table}" LIMIT 1')).mappings().first()
            meta[table] = {"columns": [(row[0], row[1]) for row in columns], "sample": dict(sample or {})}
    return meta


def sync_datasets(models: dict[str, dict[str, Any]]) -> None:
    """把场景涉及的物理表同步为数据集目录，列信息直接读 information_schema。"""
    tables = sorted({spec["table"] for spec in models.values()})
    meta = _table_meta(tables)
    datasets = []
    for table in tables:
        spec = next(item for item in models.values() if item["table"] == table)
        labels = {field["name"]: field.get("business_name") or field["name"] for field in spec["fields"]}
        columns = []
        for name, data_type in meta[table]["columns"]:
            sample_value = meta[table]["sample"].get(name)
            columns.append(
                {
                    "column_name": name,
                    "column_type": data_type,
                    "business_name": labels.get(name, name),
                    "sample_value": None if sample_value is None else str(sample_value)[:64],
                }
            )
        datasets.append(
            {
                "external_dataset_id": f"bank.ds_{table}",
                "dataset_code": f"ds_{table}",
                "dataset_name": spec["business_name"],
                "schema_name": "public",
                "table_name": table,
                "description": spec.get("description"),
                "source_version": "v1",
                "columns": columns,
            }
        )
    result = api("post", "/catalog/datasets:sync", {"source_system": SOURCE_SYSTEM, "datasets": datasets})
    print(f"数据集目录同步：{result.get('synced')} 个（{len(tables)} 张物理表）")


def build_models(
    models: dict[str, dict[str, Any]],
    domain_ids: dict[str, int],
) -> dict[str, dict[str, Any]]:
    created: dict[str, dict[str, Any]] = {}
    for key, spec in models.items():
        item = api(
            "post",
            "/models",
            {
                "domain_id": domain_ids[spec["domain"]],
                "name": spec["name"],
                "business_name": spec["business_name"],
                "description": spec.get("description"),
                "owner": "demo-modeler",
                "max_hops": spec.get("max_hops", 3),
            },
        )
        created[key] = item
    print("模型：" + "、".join(f"{item['name']}({item['model_id']})" for item in created.values()))
    return created


def create_fields(
    models: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for key, spec in models.items():
        model_id = int(created[key]["model_id"])
        items = api("post", f"/models/{model_id}/fields:batch", {"fields": spec["fields"]})
        result[key] = {item["name"]: int(item["field_id"]) for item in items}
    print("字段：" + "、".join(f"{key}={len(value)}" for key, value in result.items()))
    return result


def set_grains(models: dict[str, dict[str, Any]], created: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> None:
    for key, spec in models.items():
        grain = spec.get("grain")
        if not grain:
            continue
        grain_fields = grain if isinstance(grain, list) else [grain]
        model_id = int(created[key]["model_id"])
        api("put", f"/models/{model_id}/grain", {"field_ids": [fields[key][name] for name in grain_fields]})
    print("粒度已声明")


def create_dimensions(models: dict[str, dict[str, Any]], created: dict[str, dict[str, Any]], fields: dict[str, dict[str, int]]) -> None:
    count = 0
    for key, spec in models.items():
        model_id = int(created[key]["model_id"])
        for name, field_name, dimension_type, extra in spec.get("dimensions", []):
            api(
                "post",
                f"/models/{model_id}/dimensions",
                {"name": name, "field_id": fields[key][field_name], "dimension_type": dimension_type, **extra},
            )
            count += 1
    print(f"维度：{count} 个")


def create_measures(
    models: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    count = 0
    for key, spec in models.items():
        model_id = int(created[key]["model_id"])
        result[key] = {}
        for item in spec.get("measures", []):
            payload = {
                "name": item["name"],
                "business_name": item.get("business_name"),
                "agg": item.get("agg", "sum"),
                "additivity": item.get("additivity", "additive"),
                "unit": item.get("unit"),
            }
            if item.get("field"):
                payload["field_id"] = fields[key][item["field"]]
            if item.get("expr"):
                payload["expr"] = item["expr"]
            if item.get("filter"):
                payload["filter"] = item["filter"]
            if item.get("window_choice"):
                payload["window_choice"] = item["window_choice"]
            if item.get("time_field"):
                payload["agg_time_dimension"] = fields[key][item["time_field"]]
            measure = api("post", f"/models/{model_id}/measures", payload)
            result[key][item["name"]] = int(measure["measure_id"])
            count += 1
    print(f"度量：{count} 个")
    return result


def create_metrics(
    models: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
    domain_ids: dict[str, int],
    measures: dict[str, dict[str, int]],
) -> dict[str, int]:
    metric_ids: dict[str, int] = {}
    for key, spec in models.items():
        model_id = int(created[key]["model_id"])
        for item in spec.get("metrics", []):
            inputs = []
            for input_type, ref, role in item.get("inputs", []):
                ref_id = measures[key][ref] if input_type == "measure" else metric_ids[ref]
                inputs.append({"input_type": input_type, "input_ref": ref_id, "role": role})
            payload = {
                "model_id": model_id,
                "domain_id": domain_ids[spec["domain"]],
                "owner": "demo-modeler",
                "name": item["name"],
                "business_name": item.get("business_name"),
                "synonyms": item.get("synonyms", []),
                "definition": item.get("definition"),
                "metric_type": item.get("metric_type", "simple"),
                "filter": item.get("filter"),
                "window_spec": item.get("window_spec"),
                "grain_to_date": item.get("grain_to_date"),
                "unit": item.get("unit"),
                "inputs": inputs,
            }
            metric = api("post", "/metrics", payload)
            metric_ids[item["name"]] = int(metric["metric_id"])
    print(f"指标：{len(metric_ids)} 个（" + "、".join(metric_ids) + "）")
    return metric_ids


def model_id_by_name(name: str) -> int:
    page = api("get", "/models", params={"page_size": 200})
    for item in page.get("items", []):
        if item["name"] == name:
            return int(item["model_id"])
    raise RuntimeError(f"语义模型不存在：{name}")


def field_id_by_name(model_id: int, name: str) -> int:
    for item in api("get", f"/models/{model_id}/fields"):
        if item["name"] == name:
            return int(item["field_id"])
    raise RuntimeError(f"模型 {model_id} 中不存在字段 {name}")


def create_relationships(
    relationships: list[dict[str, str]],
    created: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, int]],
) -> None:
    for item in relationships:
        from_model_id = int(created[item["from"]]["model_id"])
        to_model_id = (
            int(created[item["to"]]["model_id"]) if item["to"] in created else model_id_by_name(item["to"])
        )
        from_field_id = fields[item["from"]][item["from_field"]]
        to_field_id = (
            fields[item["to"]][item["to_field"]]
            if item["to"] in fields
            else field_id_by_name(to_model_id, item["to_field"])
        )
        api(
            "post",
            f"/models/{from_model_id}/relationships",
            {
                "name": item["name"],
                "from_field_id": from_field_id,
                "to_model_id": to_model_id,
                "to_field_id": to_field_id,
                "cardinality": "N:1",
                "join_type": "left",
                "priority": 100,
                "verified": True,
            },
        )
    print(f"关系：{len(relationships)} 条（N:1，已认证）")


def create_bindings(
    models: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
    fields: dict[str, dict[str, int]],
) -> dict[str, dict[str, Any]]:
    datasets = {
        item["external_dataset_id"]: item
        for item in api("get", "/catalog/datasets", params={"source_system": SOURCE_SYSTEM, "page_size": 100})["items"]
    }
    bindings: dict[str, dict[str, Any]] = {}
    for key, spec in models.items():
        model_id = int(created[key]["model_id"])
        external_id = f"bank.ds_{spec['table']}"
        dataset = api("get", f"/catalog/datasets/{datasets[external_id]['dataset_id']}")
        column_ids = {item["column_name"]: int(item["column_id"]) for item in dataset["columns"]}
        binding = api(
            "post",
            f"/models/{model_id}/bindings",
            {
                "binding_type": "dataset",
                "source_system": SOURCE_SYSTEM,
                "external_dataset_id": external_id,
                "query_ref": f"public.{spec['table']}",
                "is_primary": True,
                "status": "draft",
                "source_version": "v1",
            },
        )
        binding_id = int(binding["binding_id"])
        api(
            "put",
            f"/bindings/{binding_id}/field-mappings",
            {
                "items": [
                    {
                        "field_id": fields[key][item["name"]],
                        "column_id": column_ids[item["name"]],
                        "column_name": item["name"],
                        "transform": None,
                        "status": "draft",
                    }
                    for item in spec["fields"]
                ]
            },
        )
        api("post", f"/bindings/{binding_id}:set-primary")
        binding["coverage"] = api("get", f"/bindings/{binding_id}")["coverage"]
        bindings[key] = binding
    print(
        "绑定："
        + "、".join(f"{created[key]['name']}(覆盖率 {round(item['coverage'] * 100)}%)" for key, item in bindings.items())
    )
    return bindings


def create_knowledge(
    terms: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    contexts: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
    metric_ids: dict[str, int],
) -> None:
    for term in terms:
        api("post", "/terms", {"scope_type": "domain", **term})
    for rule in rules:
        payload = {key: value for key, value in rule.items() if key != "target_model"}
        payload["target_type"] = "model"
        payload["target_id"] = int(created[rule["target_model"]]["model_id"])
        payload.setdefault("status", "active")
        api("post", "/rules", payload)
    for metric_name, context in contexts.items():
        api("put", f"/context/metric/{metric_ids[metric_name]}", context)
    print(f"知识上下文：{len(terms)} 条术语、{len(rules)} 条业务规则、{len(contexts)} 份指标上下文")


def create_permission(model_key: str, role: str, row_filter: str, created: dict[str, dict[str, Any]]) -> None:
    with write_session() as session:
        session.execute(
            text(
                """
                INSERT INTO t_permission
                  (subject_type, subject_id, asset_type, asset_id, effect, row_filter, column_mask)
                VALUES ('role', :role, 'model', :model_id, 'allow', :row_filter, '{}'::jsonb)
                """
            ),
            {"role": role, "model_id": int(created[model_key]["model_id"]), "row_filter": row_filter},
        )
    print(f"权限策略：角色 {role} 行过滤 {row_filter}")


# --------------------------------------------------------------------------- 校验 / 认证 / 发布


def certify(asset_type: str, asset_id: int, comment: str) -> None:
    item = api("post", "/certifications", {"asset_type": asset_type, "asset_id": asset_id})
    api("post", f"/certifications/{item['certification_id']}/decision", {"approve": True, "comment": comment})


def validate_all(
    models: dict[str, dict[str, Any]],
    created: dict[str, dict[str, Any]],
    bindings: dict[str, dict[str, Any]],
    metric_ids: dict[str, int],
) -> None:
    for key, item in bindings.items():
        certify("binding", int(item["binding_id"]), f"{key} 字段映射完整")

    for key, item in created.items():
        result = api("post", f"/models/{item['model_id']}/validation", {"level": "semantic"})
        if result["status"] != "passed":
            raise RuntimeError(f"模型 {key} 语义校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")

    for name, metric_id in metric_ids.items():
        result = api("post", f"/metrics/{metric_id}/validation")
        if result["status"] != "passed":
            raise RuntimeError(f"指标 {name} 校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")

    for key, item in created.items():
        certify("model", int(item["model_id"]), f"{key} 语义定义确认")
    for name, metric_id in metric_ids.items():
        certify("metric", metric_id, f"{name} 口径确认")

    summary = []
    for key, item in created.items():
        result = api("post", f"/models/{item['model_id']}/validation", {"level": "queryable"})
        if result["status"] != "passed":
            raise RuntimeError(f"模型 {key} 可问数校验未通过：{json.dumps(result['issues'], ensure_ascii=False)}")
        summary.append(f"{key}={result.get('queryable')}")
    print("校验：semantic 全部 passed，queryable 全部 passed")
    print("认证：模型 / 指标 / 绑定均已认证")
    print("可问数：" + "、".join(summary))


def publish() -> dict[str, Any]:
    snapshot = api("post", "/snapshots")
    print(f"快照发布：{snapshot['version']}（{snapshot['status']}）")
    return snapshot


def run_ask(question: str, rows: int = 8) -> dict[str, Any]:
    response = client.post("/api/ask", json={"question": question}, headers=HEADERS)
    body = response.json()
    if response.status_code >= 400:
        raise RuntimeError(f"问数失败 {response.status_code}: {body}")
    data = body.get("data", body)
    print(f"\n问数：{question}")
    print(f"  状态：{data['status']}，快照：{(data.get('result') or {}).get('snapshot_version')}")
    if data["status"] != "ok":
        print(f"  澄清：{json.dumps(data.get('clarification'), ensure_ascii=False)}")
        return data
    result = data["result"]
    print(f"  列：{result['columns']}，行数：{result['row_count']}")
    for row in result["rows"][:rows]:
        print(f"    {row}")
    return data


# --------------------------------------------------------------------------- 清理


def cleanup_scope(
    model_names: list[str],
    metric_names: list[str],
    term_names: list[str],
    rule_names: list[str],
    permission_subjects: list[str] | None = None,
    clear_datasets: bool = True,
) -> None:
    with write_session() as session:
        def ids(sql: str, names: list[str]) -> list[int]:
            statement = text(sql).bindparams(bindparam("names", expanding=True))
            return [int(row[0]) for row in session.execute(statement, {"names": names})]

        model_ids = ids("SELECT model_id FROM t_sem_model WHERE name IN :names", model_names)
        metric_ids = ids("SELECT metric_id FROM t_sem_metric WHERE name IN :names", metric_names)

        if model_ids:
            session.execute(
                text("DELETE FROM t_sem_join_edge WHERE from_model_id IN :ids OR to_model_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": model_ids},
            )
            binding_ids = [
                int(row[0])
                for row in session.execute(
                    text("SELECT binding_id FROM t_sem_binding WHERE model_id IN :ids").bindparams(
                        bindparam("ids", expanding=True)
                    ),
                    {"ids": model_ids},
                )
            ]
            if binding_ids:
                session.execute(
                    text(
                        "DELETE FROM t_sem_certification WHERE asset_type = 'binding' AND asset_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"ids": binding_ids},
                )
            session.execute(
                text("DELETE FROM t_sem_binding WHERE model_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": model_ids},
            )

        if metric_ids:
            session.execute(
                text("DELETE FROM t_sem_metric WHERE metric_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": metric_ids},
            )

        if model_ids:
            session.execute(
                text("DELETE FROM t_sem_model WHERE model_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": model_ids},
            )

        for asset_type, asset_ids in (("model", model_ids), ("metric", metric_ids)):
            if not asset_ids:
                continue
            session.execute(
                text("DELETE FROM t_sem_asset_context WHERE asset_type = :asset_type AND asset_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"asset_type": asset_type, "ids": asset_ids},
            )
            session.execute(
                text("DELETE FROM t_sem_certification WHERE asset_type = :asset_type AND asset_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"asset_type": asset_type, "ids": asset_ids},
            )

        if clear_datasets:
            session.execute(text("DELETE FROM t_ext_dataset WHERE source_system = :source"), {"source": SOURCE_SYSTEM})
        if term_names:
            session.execute(
                text("DELETE FROM t_term WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
                {"names": term_names},
            )
        if rule_names:
            session.execute(
                text("DELETE FROM t_business_rule WHERE name IN :names").bindparams(bindparam("names", expanding=True)),
                {"names": rule_names},
            )
        for subject in permission_subjects or []:
            session.execute(text("DELETE FROM t_permission WHERE subject_id = :subject"), {"subject": subject})
        session.execute(text("DELETE FROM t_sem_snapshot"))
        session.execute(text("DELETE FROM t_query_log"))

    print("已清理上一轮银行示例数据")