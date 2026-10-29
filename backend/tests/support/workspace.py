"""测试隔离工作区：独占命名前缀、物理样例表与语义资产清理。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

PHYSICAL_COLUMNS = """
  order_no     TEXT,
  customer_no  TEXT,
  store_no     TEXT,
  sku_no       TEXT,
  dt           DATE,
  amt          NUMERIC(12, 2),
  refund_amt   NUMERIC(12, 2),
  order_status TEXT,
  channel_code TEXT,
  qty          INTEGER
"""
PHYSICAL_ROWS = """
  ('A1', 'C1', 'S1', 'P1', DATE '2026-09-01', 100, 0, 'paid', 'online', 2),
  ('A2', 'C2', 'S1', 'P2', DATE '2026-09-01', 200, 0, 'paid', 'offline', 1),
  ('A3', 'C1', 'S2', 'P1', DATE '2026-09-15', 300, 0, 'completed', 'online', 3),
  ('A4', 'C3', 'S2', 'P2', DATE '2026-09-15', 50, 50, 'refunded', 'offline', 1)
"""


@dataclass(slots=True)
class SemanticWorkspace:
    """一次测试独占的命名前缀、物理表与快照基线。"""

    prefix: str
    table: str
    baseline_snapshot_id: int

    @property
    def query_ref(self) -> str:
        return f"public.{self.table}"


def _id_list(values: list[int]) -> str:
    return ",".join(str(int(item)) for item in values) if values else "0"


def create_workspace() -> SemanticWorkspace:
    from app.semantic.repository.db import execute, one

    suffix = uuid.uuid4().hex[:8]
    baseline = one("SELECT COALESCE(MAX(snapshot_id), 0) AS snapshot_id FROM t_sem_snapshot") or {"snapshot_id": 0}
    workspace = SemanticWorkspace(
        prefix=f"pytest-{suffix}",
        table=f"sem_test_orders_{suffix}",
        baseline_snapshot_id=int(baseline["snapshot_id"]),
    )
    execute(f"CREATE TABLE public.{workspace.table} ({PHYSICAL_COLUMNS})")
    execute(f"INSERT INTO public.{workspace.table} VALUES {PHYSICAL_ROWS}")
    return workspace


def cleanup_workspace(workspace: SemanticWorkspace) -> None:
    from app.semantic.repository.db import execute, rows

    like = f"{workspace.prefix}%"
    domains = [int(item["domain_id"]) for item in rows("SELECT domain_id FROM t_sem_domain WHERE name LIKE :p", {"p": like})]
    models = [int(item["model_id"]) for item in rows("SELECT model_id FROM t_sem_model WHERE name LIKE :p", {"p": like})]
    if domains:
        models = sorted(
            set(models)
            | {
                int(item["model_id"])
                for item in rows(f"SELECT model_id FROM t_sem_model WHERE domain_id IN ({_id_list(domains)})")
            }
        )
    if models:
        mids = _id_list(models)
        metrics = [int(item["metric_id"]) for item in rows(f"SELECT metric_id FROM t_sem_metric WHERE model_id IN ({mids})")]
        if metrics:
            mts = _id_list(metrics)
            execute(f"DELETE FROM t_sem_metric_input WHERE metric_id IN ({mts})")
            execute(f"DELETE FROM t_sem_metric WHERE metric_id IN ({mts})")
            execute(f"DELETE FROM t_sem_validation_run WHERE object_type = 'metric' AND object_id IN ({mts})")
            execute(f"DELETE FROM t_sem_certification WHERE asset_type = 'metric' AND asset_id IN ({mts})")
        execute(f"DELETE FROM t_sem_join_edge WHERE from_model_id IN ({mids}) OR to_model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_binding WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_model_grain WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_dimension WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_measure WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_field WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_model WHERE model_id IN ({mids})")
        execute(f"DELETE FROM t_sem_validation_run WHERE object_type = 'model' AND object_id IN ({mids})")
        execute(f"DELETE FROM t_sem_certification WHERE asset_type = 'model' AND asset_id IN ({mids})")
    if domains:
        dids = _id_list(domains)
        execute(f"DELETE FROM t_sem_domain_member WHERE domain_id IN ({dids})")
        execute(f"DELETE FROM t_sem_domain WHERE domain_id IN ({dids})")

    execute(
        "DELETE FROM t_query_log WHERE snapshot_version IN "
        "(SELECT version FROM t_sem_snapshot WHERE snapshot_id > :baseline)",
        {"baseline": workspace.baseline_snapshot_id},
    )
    execute("DELETE FROM t_sem_snapshot WHERE snapshot_id > :baseline", {"baseline": workspace.baseline_snapshot_id})
    if workspace.baseline_snapshot_id:
        execute(
            "UPDATE t_sem_snapshot SET status = 'active' WHERE snapshot_id = :id",
            {"id": workspace.baseline_snapshot_id},
        )
    execute(f"DROP TABLE IF EXISTS public.{workspace.table}")