-- 语义层基线 DDL（v3：语义优先 + 物化绑定）
-- 适用：空库初始化。不迁移旧五层表；重复执行请先清库。
-- 分组：语义 / 绑定 / 目录 / 治理 / 知识 / 平台

-- ============================================================
-- 1. 语义层
-- ============================================================

CREATE TABLE IF NOT EXISTS t_sem_domain (
  domain_id    BIGSERIAL PRIMARY KEY,
  name         VARCHAR(128) NOT NULL UNIQUE,
  description  TEXT,
  owner        VARCHAR(64),
  status       VARCHAR(16) NOT NULL DEFAULT 'active'
               CHECK (status IN ('active','inactive')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_sem_domain_member (
  domain_id  BIGINT NOT NULL REFERENCES t_sem_domain(domain_id) ON DELETE CASCADE,
  user_id    VARCHAR(64) NOT NULL,
  role       VARCHAR(32) NOT NULL DEFAULT 'modeler',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (domain_id, user_id)
);

CREATE TABLE IF NOT EXISTS t_sem_model (
  model_id       BIGSERIAL PRIMARY KEY,
  domain_id      BIGINT NOT NULL REFERENCES t_sem_domain(domain_id),
  name           VARCHAR(128) NOT NULL UNIQUE,
  business_name  VARCHAR(256),
  description    TEXT,
  owner          VARCHAR(64),
  status         VARCHAR(16) NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft','certified','deprecated')),
  max_hops       INT NOT NULL DEFAULT 3 CHECK (max_hops BETWEEN 1 AND 10),
  origin         VARCHAR(16) NOT NULL DEFAULT 'manual'
                 CHECK (origin IN ('manual','import','template','ai')),
  version        INT NOT NULL DEFAULT 1,
  semantic_hash  VARCHAR(128),
  certified_at   TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sem_model_domain ON t_sem_model (domain_id);
CREATE INDEX IF NOT EXISTS idx_sem_model_status ON t_sem_model (status);

CREATE TABLE IF NOT EXISTS t_sem_field (
  field_id       BIGSERIAL PRIMARY KEY,
  model_id       BIGINT NOT NULL REFERENCES t_sem_model(model_id) ON DELETE CASCADE,
  name           VARCHAR(256) NOT NULL,
  business_name  VARCHAR(256),
  synonyms       TEXT[] NOT NULL DEFAULT '{}',
  semantic_type  VARCHAR(16) NOT NULL DEFAULT 'unknown'
                 CHECK (semantic_type IN ('key','dimension','time','measure','unknown')),
  data_type      VARCHAR(32) NOT NULL DEFAULT 'unknown'
                 CHECK (data_type IN ('string','number','date','boolean','unknown')),
  description    TEXT,
  expression     TEXT,
  is_hidden      BOOLEAN NOT NULL DEFAULT FALSE,
  sensitivity    VARCHAR(16) NOT NULL DEFAULT 'internal'
                 CHECK (sensitivity IN ('public','internal','confidential','pii')),
  origin         VARCHAR(16) NOT NULL DEFAULT 'manual'
                 CHECK (origin IN ('manual','import','template','ai')),
  verified       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, name)
);
CREATE INDEX IF NOT EXISTS idx_sem_field_model ON t_sem_field (model_id);

CREATE TABLE IF NOT EXISTS t_sem_model_grain (
  model_id   BIGINT NOT NULL REFERENCES t_sem_model(model_id) ON DELETE CASCADE,
  field_id   BIGINT NOT NULL REFERENCES t_sem_field(field_id) ON DELETE CASCADE,
  position   INT NOT NULL DEFAULT 1,
  PRIMARY KEY (model_id, field_id)
);

CREATE TABLE IF NOT EXISTS t_sem_dimension (
  dimension_id      BIGSERIAL PRIMARY KEY,
  model_id          BIGINT NOT NULL REFERENCES t_sem_model(model_id) ON DELETE CASCADE,
  name              VARCHAR(128) NOT NULL,
  field_id          BIGINT NOT NULL REFERENCES t_sem_field(field_id),
  dimension_type    VARCHAR(16) NOT NULL CHECK (dimension_type IN ('categorical','time')),
  time_granularity  VARCHAR(16)
                    CHECK (time_granularity IS NULL OR time_granularity IN ('day','week','month','quarter','year')),
  hierarchy         VARCHAR(128),
  code_mapping      JSONB NOT NULL DEFAULT '{}',
  default_filter    TEXT,
  filterable        BOOLEAN NOT NULL DEFAULT TRUE,
  origin            VARCHAR(16) NOT NULL DEFAULT 'manual'
                    CHECK (origin IN ('manual','import','template','ai')),
  verified          BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, name)
);

CREATE TABLE IF NOT EXISTS t_sem_measure (
  measure_id          BIGSERIAL PRIMARY KEY,
  model_id            BIGINT NOT NULL REFERENCES t_sem_model(model_id) ON DELETE CASCADE,
  name                VARCHAR(128) NOT NULL,
  business_name       VARCHAR(256),
  field_id            BIGINT REFERENCES t_sem_field(field_id),
  expr                TEXT,
  filter              TEXT,
  agg                 VARCHAR(32) NOT NULL,
  agg_param           NUMERIC(6,4),
  agg_time_dimension  BIGINT REFERENCES t_sem_field(field_id),
  additivity          VARCHAR(16) NOT NULL DEFAULT 'additive'
                      CHECK (additivity IN ('additive','semi_additive','non_additive')),
  window_choice       VARCHAR(8) CHECK (window_choice IN ('max','min')),
  unit                VARCHAR(32),
  origin              VARCHAR(16) NOT NULL DEFAULT 'manual'
                      CHECK (origin IN ('manual','import','template','ai')),
  verified            BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, name),
  CHECK (field_id IS NOT NULL OR expr IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS t_sem_metric (
  metric_id       BIGSERIAL PRIMARY KEY,
  model_id        BIGINT REFERENCES t_sem_model(model_id),
  name            VARCHAR(128) NOT NULL UNIQUE,
  business_name   VARCHAR(256),
  synonyms        TEXT[] NOT NULL DEFAULT '{}',
  definition      TEXT,
  metric_type     VARCHAR(16) NOT NULL
                  CHECK (metric_type IN ('simple','ratio','derived','cumulative','conversion')),
  filter          TEXT,
  window_spec     TEXT,
  grain_to_date   VARCHAR(16),
  unit            VARCHAR(32),
  scale           INT NOT NULL DEFAULT 2,
  domain_id       BIGINT REFERENCES t_sem_domain(domain_id),
  owner           VARCHAR(64),
  valid_from      DATE,
  valid_to        DATE,
  status          VARCHAR(16) NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','certified','deprecated')),
  origin          VARCHAR(16) NOT NULL DEFAULT 'manual'
                  CHECK (origin IN ('manual','import','template','ai')),
  version         INT NOT NULL DEFAULT 1,
  certified_hash  VARCHAR(128),
  certified_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sem_metric_domain ON t_sem_metric (domain_id);
CREATE INDEX IF NOT EXISTS idx_sem_metric_status ON t_sem_metric (status);

CREATE TABLE IF NOT EXISTS t_sem_metric_input (
  metric_id   BIGINT NOT NULL REFERENCES t_sem_metric(metric_id) ON DELETE CASCADE,
  input_type  VARCHAR(8) NOT NULL CHECK (input_type IN ('metric','measure')),
  input_ref   BIGINT NOT NULL,
  role        VARCHAR(16) NOT NULL
              CHECK (role IN ('numerator','denominator','input','base','conversion')),
  position    INT NOT NULL DEFAULT 1,
  PRIMARY KEY (metric_id, input_type, input_ref, role)
);

CREATE TABLE IF NOT EXISTS t_sem_join_edge (
  edge_id         BIGSERIAL PRIMARY KEY,
  name            VARCHAR(128) NOT NULL UNIQUE,
  from_model_id   BIGINT NOT NULL REFERENCES t_sem_model(model_id),
  from_field_id   BIGINT NOT NULL REFERENCES t_sem_field(field_id),
  to_model_id     BIGINT NOT NULL REFERENCES t_sem_model(model_id),
  to_field_id     BIGINT NOT NULL REFERENCES t_sem_field(field_id),
  cardinality     VARCHAR(8) NOT NULL CHECK (cardinality IN ('1:1','N:1','1:N','N:N')),
  join_type       VARCHAR(16) NOT NULL DEFAULT 'inner' CHECK (join_type IN ('inner','left')),
  join_predicate  TEXT,
  priority        INT NOT NULL DEFAULT 100,
  origin          VARCHAR(16) NOT NULL DEFAULT 'manual'
                  CHECK (origin IN ('manual','import','template','ai')),
  verified        BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (from_model_id, from_field_id, to_model_id, to_field_id)
);
CREATE INDEX IF NOT EXISTS idx_sem_join_from ON t_sem_join_edge (from_model_id);
CREATE INDEX IF NOT EXISTS idx_sem_join_to ON t_sem_join_edge (to_model_id);

-- ============================================================
-- 2. 绑定层
-- ============================================================

CREATE TABLE IF NOT EXISTS t_sem_binding (
  binding_id          BIGSERIAL PRIMARY KEY,
  model_id            BIGINT NOT NULL REFERENCES t_sem_model(model_id) ON DELETE CASCADE,
  binding_type        VARCHAR(16) NOT NULL
                      CHECK (binding_type IN ('dataset','table','view','subquery')),
  source_system       VARCHAR(64),
  external_dataset_id VARCHAR(128),
  table_id            BIGINT,
  query_ref           VARCHAR(512) NOT NULL,
  alias               VARCHAR(64),
  is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
  priority            INT NOT NULL DEFAULT 100,
  row_filter          TEXT,
  status              VARCHAR(16) NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','certified','disabled')),
  source_version      VARCHAR(128),
  schema_hash         VARCHAR(128),
  verified            BOOLEAN NOT NULL DEFAULT FALSE,
  certified_at        TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (model_id, binding_type, query_ref)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_sem_binding_primary
  ON t_sem_binding (model_id)
  WHERE is_primary AND status <> 'disabled';

CREATE TABLE IF NOT EXISTS t_sem_field_binding (
  id           BIGSERIAL PRIMARY KEY,
  binding_id   BIGINT NOT NULL REFERENCES t_sem_binding(binding_id) ON DELETE CASCADE,
  field_id     BIGINT NOT NULL REFERENCES t_sem_field(field_id) ON DELETE CASCADE,
  column_id    BIGINT,
  column_name  VARCHAR(256) NOT NULL,
  transform    TEXT,
  status       VARCHAR(16) NOT NULL DEFAULT 'draft'
               CHECK (status IN ('draft','certified','disabled')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (binding_id, field_id)
);

-- ============================================================
-- 3. 目录层
-- ============================================================

CREATE TABLE IF NOT EXISTS t_ext_dataset (
  dataset_id          BIGSERIAL PRIMARY KEY,
  source_system       VARCHAR(64) NOT NULL,
  external_dataset_id VARCHAR(128) NOT NULL,
  dataset_code        VARCHAR(128),
  dataset_name        VARCHAR(256),
  schema_name         VARCHAR(128),
  table_name          VARCHAR(256),
  description         TEXT,
  status              VARCHAR(16) NOT NULL DEFAULT 'active',
  source_version      VARCHAR(128),
  synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source_system, external_dataset_id)
);

CREATE TABLE IF NOT EXISTS t_ext_column (
  column_id      BIGSERIAL PRIMARY KEY,
  dataset_id     BIGINT NOT NULL REFERENCES t_ext_dataset(dataset_id) ON DELETE CASCADE,
  column_name    VARCHAR(256) NOT NULL,
  column_type    VARCHAR(64),
  business_name  VARCHAR(256),
  ordinal        INT,
  sample_value   TEXT,
  nullable       BOOLEAN DEFAULT TRUE,
  UNIQUE (dataset_id, column_name)
);

CREATE TABLE IF NOT EXISTS t_meta_table (
  table_id         BIGSERIAL PRIMARY KEY,
  source_system    VARCHAR(64),
  schema_name      VARCHAR(128) NOT NULL,
  table_name       VARCHAR(256) NOT NULL,
  table_type       VARCHAR(16) NOT NULL DEFAULT 'table'
                   CHECK (table_type IN ('table','view','materialized_view','platform_dataset')),
  query_ref        VARCHAR(512) NOT NULL UNIQUE,
  business_name    VARCHAR(256),
  description      TEXT,
  status           VARCHAR(16) NOT NULL DEFAULT 'active',
  verified         BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (schema_name, table_name)
);

CREATE TABLE IF NOT EXISTS t_meta_column (
  column_id    BIGSERIAL PRIMARY KEY,
  table_id     BIGINT NOT NULL REFERENCES t_meta_table(table_id) ON DELETE CASCADE,
  column_name  VARCHAR(256) NOT NULL,
  data_type    VARCHAR(64),
  ordinal      INT,
  business_name VARCHAR(256),
  nullable     BOOLEAN DEFAULT TRUE,
  UNIQUE (table_id, column_name)
);

CREATE TABLE IF NOT EXISTS t_meta_key (
  key_id        BIGSERIAL PRIMARY KEY,
  table_id      BIGINT NOT NULL REFERENCES t_meta_table(table_id) ON DELETE CASCADE,
  columns       TEXT[] NOT NULL DEFAULT '{}',
  key_type      VARCHAR(16) NOT NULL DEFAULT 'pk' CHECK (key_type IN ('pk','fk','unique')),
  ref_table_id  BIGINT REFERENCES t_meta_table(table_id),
  ref_columns   TEXT[] NOT NULL DEFAULT '{}',
  cardinality   VARCHAR(8),
  verified      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. 治理
-- ============================================================

CREATE TABLE IF NOT EXISTS t_sem_validation_run (
  run_id       BIGSERIAL PRIMARY KEY,
  object_type  VARCHAR(32) NOT NULL,
  object_id    BIGINT NOT NULL,
  level        VARCHAR(16) NOT NULL CHECK (level IN ('semantic','queryable')),
  status       VARCHAR(16) NOT NULL CHECK (status IN ('passed','failed')),
  issues       JSONB NOT NULL DEFAULT '[]',
  created_by   VARCHAR(64),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sem_validation_object
  ON t_sem_validation_run (object_type, object_id, created_at DESC);

CREATE TABLE IF NOT EXISTS t_sem_certification (
  certification_id BIGSERIAL PRIMARY KEY,
  asset_type       VARCHAR(32) NOT NULL,
  asset_id         BIGINT NOT NULL,
  fingerprint      VARCHAR(128) NOT NULL,
  status           VARCHAR(16) NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','approved','rejected')),
  requested_by     VARCHAR(64),
  approved_by      VARCHAR(64),
  approved_at      TIMESTAMPTZ,
  comment          TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sem_cert_asset ON t_sem_certification (asset_type, asset_id);

CREATE TABLE IF NOT EXISTS t_sem_snapshot (
  snapshot_id   BIGSERIAL PRIMARY KEY,
  version       VARCHAR(64) NOT NULL UNIQUE,
  fingerprint   VARCHAR(128) NOT NULL,
  payload       JSONB NOT NULL,
  status        VARCHAR(16) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','archived')),
  published_by  VARCHAR(64),
  published_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 5. 知识
-- ============================================================

CREATE TABLE IF NOT EXISTS t_term (
  term_id       BIGSERIAL PRIMARY KEY,
  name          VARCHAR(128) NOT NULL UNIQUE,
  synonyms      TEXT[] NOT NULL DEFAULT '{}',
  definition    TEXT,
  scope_type    VARCHAR(16) NOT NULL DEFAULT 'global'
                CHECK (scope_type IN ('global','domain','model')),
  scope_id      BIGINT,
  status        VARCHAR(16) NOT NULL DEFAULT 'active',
  owner         VARCHAR(64),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_sem_synonym (
  synonym_id    BIGSERIAL PRIMARY KEY,
  synonym       VARCHAR(128) NOT NULL UNIQUE,
  standard_name VARCHAR(128) NOT NULL,
  target_type   VARCHAR(32) NOT NULL DEFAULT 'global'
                CHECK (target_type IN ('global','metric','term','dimension','model','field')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_business_rule (
  rule_id        BIGSERIAL PRIMARY KEY,
  name           VARCHAR(128) NOT NULL UNIQUE,
  rule_type      VARCHAR(32) NOT NULL DEFAULT 'filter',
  target_type    VARCHAR(32) NOT NULL DEFAULT 'global',
  target_id      BIGINT,
  condition      TEXT NOT NULL,
  action         VARCHAR(32) NOT NULL DEFAULT 'exclude',
  priority       INT NOT NULL DEFAULT 100,
  status         VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_sem_asset_context (
  id                BIGSERIAL PRIMARY KEY,
  asset_type        VARCHAR(32) NOT NULL,
  asset_id          BIGINT NOT NULL,
  business_name     VARCHAR(256),
  synonyms          TEXT[] NOT NULL DEFAULT '{}',
  definition        TEXT,
  examples          JSONB NOT NULL DEFAULT '[]',
  negative_examples JSONB NOT NULL DEFAULT '[]',
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (asset_type, asset_id)
);

-- ============================================================
-- 6. 平台
-- ============================================================

CREATE TABLE IF NOT EXISTS t_async_task (
  task_id     BIGSERIAL PRIMARY KEY,
  task_type   VARCHAR(64) NOT NULL,
  status      VARCHAR(16) NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending','running','success','failed')),
  payload     JSONB NOT NULL DEFAULT '{}',
  result      JSONB,
  error       TEXT,
  created_by  VARCHAR(64),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_query_log (
  query_id            BIGSERIAL PRIMARY KEY,
  request_id          VARCHAR(64) NOT NULL UNIQUE,
  user_id             VARCHAR(64),
  question            TEXT NOT NULL,
  normalized_question TEXT,
  metric_ids          BIGINT[] NOT NULL DEFAULT '{}',
  model_ids           BIGINT[] NOT NULL DEFAULT '{}',
  binding_ids         BIGINT[] NOT NULL DEFAULT '{}',
  query_ir            JSONB,
  sql                 TEXT,
  snapshot_version    VARCHAR(64),
  row_count           INT,
  elapsed_ms          INT,
  status              VARCHAR(16) NOT NULL DEFAULT 'ok'
                      CHECK (status IN ('ok','clarification','failed')),
  error_code          VARCHAR(64),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_query_log_user ON t_query_log (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS t_audit_event (
  event_id    BIGSERIAL PRIMARY KEY,
  actor       VARCHAR(64),
  action      VARCHAR(64) NOT NULL,
  object_type VARCHAR(32),
  object_id   BIGINT,
  before      JSONB,
  after       JSONB,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_object ON t_audit_event (object_type, object_id, created_at DESC);

CREATE TABLE IF NOT EXISTS t_user (
  user_id    VARCHAR(64) PRIMARY KEY,
  name       VARCHAR(128),
  status     VARCHAR(16) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t_role (
  role_id     BIGSERIAL PRIMARY KEY,
  code        VARCHAR(32) NOT NULL UNIQUE,
  name        VARCHAR(64) NOT NULL,
  description TEXT
);

CREATE TABLE IF NOT EXISTS t_user_role (
  user_id VARCHAR(64) NOT NULL REFERENCES t_user(user_id) ON DELETE CASCADE,
  role_id BIGINT NOT NULL REFERENCES t_role(role_id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS t_permission (
  permission_id BIGSERIAL PRIMARY KEY,
  subject_type  VARCHAR(16) NOT NULL DEFAULT 'role',
  subject_id    VARCHAR(64) NOT NULL,
  asset_type    VARCHAR(32) NOT NULL,
  asset_id      BIGINT,
  effect        VARCHAR(8) NOT NULL DEFAULT 'allow' CHECK (effect IN ('allow','deny')),
  row_filter    TEXT,
  column_mask   JSONB NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 常用视图：模型可问数状态由服务层派生，不在库内固化。
