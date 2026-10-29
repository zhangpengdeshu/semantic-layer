#!/usr/bin/env bash
# 初始化语义层数据库：只应用 001_schema.sql 与 002_seed.sql。
#
# 用法：
#   scripts/init_db.sh            幂等建表 + 种子
#   scripts/init_db.sh --reset    先删除所有 t_* 表，再重建（业务样例表不动）
set -euo pipefail

CONTAINER="${SEMANTIC_LAYER_PG_CONTAINER:-semantic-layer-pg}"
DB="${SEMANTIC_LAYER_PG_DB:-semantic_layer}"
DB_USER="${SEMANTIC_LAYER_PG_USER:-postgres}"

DIR="$(cd "$(dirname "$0")/.." && pwd)/deploy/sql"

psql_exec() {
  docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB" -v ON_ERROR_STOP=1 "$@"
}

count_tables() {
  psql_exec -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 't\\_%'"
}

if [[ "${1:-}" == "--reset" ]]; then
  echo ">> reset: drop all t_* tables (business sample tables preserved)"
  psql_exec <<'SQL'
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public' AND tablename LIKE 't\_%'
  LOOP
    EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', r.tablename);
  END LOOP;
END $$;
SQL
fi

echo ">> t_* tables before: $(count_tables)"

for f in "$DIR/001_schema.sql" "$DIR/002_seed.sql"; do
  echo ">> apply $(basename "$f")"
  psql_exec < "$f"
done

echo ">> t_* tables after: $(count_tables)"
echo "done."