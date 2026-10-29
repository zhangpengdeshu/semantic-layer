# 语义层 · Semantic Layer

一个可独立部署的语义建模平台：把业务口径沉淀为主题域、语义模型、字段、维度、度量、指标与关系，再通过数据绑定映射到物理表，完成校验、认证、快照发布与问数。

后端为 FastAPI + PostgreSQL + SQLGlot，前端为 Vue 3 + Vite + TypeScript + Element Plus。

## 为什么需要语义层

- 指标口径散落在 SQL 和报表里，同名不同义、同义不同名。
- 物理表改名、换库后，上层报表和问数全部失效。
- 业务问题无法追溯到指标、模型、表、字段和 JOIN 路径。
- 权限与敏感字段缺少统一的编译期约束。

语义层把「业务语义」与「物理实现」解耦：语义对象只描述业务含义，物理位置通过绑定表达；问数时由规划器选择认证关系、解析绑定、编译 SQL，并给出完整解释。

## 核心能力

| 模块 | 能力 |
| --- | --- |
| 主题域 | 按业务主题组织模型，维护负责人与成员 |
| 语义模型 | 模型、字段、粒度、维度、度量、关系 |
| 指标 | simple / ratio / derived / cumulative / conversion 五种类型，输入与依赖管理 |
| 数据绑定 | 数据集 / 表 / 视图 / 子查询绑定，主绑定、字段映射、自动映射、漂移检测 |
| 校验 | semantic 与 queryable 两级校验，Issue 可定位到对象与字段 |
| 认证与发布 | 认证评审、语义指纹、快照构建、diff、回滚 |
| 知识上下文 | 术语、同义词、业务规则、资产说明、召回测试 |
| 问数 | 问题归一、语义召回、JOIN 规划、SQL 编译、结果解释 |
| 平台 | 用户与角色、审计日志、查询日志、工作台指标 |

## 仓库结构

```text
semantic-layer/
├── backend/                # FastAPI 应用与测试
│   ├── app/
│   │   ├── api/            # 路由、请求模型、统一响应与错误
│   │   ├── semantic/       # 领域、服务、校验、规划、编译、仓储
│   │   ├── agent/          # 问数管线与同环比
│   │   └── platform/       # 审计、权限
│   └── tests/              # unit / integration / golden / e2e
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── api/            # 请求封装与语义层接口
│       ├── views/          # 工作台、主题域、模型、指标、绑定、知识、发布、管理
│       ├── router/ stores/ i18n/ layouts/ styles/
├── deploy/sql/             # 数据库基线 DDL 与种子
├── scripts/                # 初始化与演示数据脚本
├── shared/                 # 配置与数据库连接
├── docs/                   # 运行部署说明
└── docker-compose.yml      # 本地 PostgreSQL
```

## 快速开始

### 1. 数据库

```bash
docker compose up -d
bash scripts/init_db.sh
```

### 2. 后端

```bash
cp .env.example .env
uv venv --python 3.11 .venv
uv pip install -e ".[dev]" -e backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8888 --reload
```

验证：`curl http://127.0.0.1:8888/health`，接口文档 http://127.0.0.1:8888/docs 。

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 。详细说明见 [后端运行部署](docs/后端运行部署.md) 与 [前端运行部署](docs/前端运行部署.md)。

### 4. 演示数据

`scripts/` 下提供零售与银行场景的建模脚本，例如：

```bash
.venv/bin/python scripts/seed_retail_example.py
.venv/bin/python scripts/seed_bank_compare.py
```

## 技术架构

```text
浏览器 (Vue 3 + Element Plus)
        │  /api/semantic/v1, /api/ask
        ▼
FastAPI ── 领域服务 ── 校验器 ── 规划器 ── SQL 编译器(sqlglot)
        │                                      │
        └──────── PostgreSQL: 语义库 / 元数据镜像 / 审计
                                               │
                                    只读执行 → 业务数据源
```

设计要点：

- 语义层表不出现 `table_id`、`dataset_id`、`query_ref`，物理位置只存在于绑定。
- SQL 通过 AST 编译，不拼接字符串；强制只读、超时与行数限制。
- 快照冻结模型、字段、维度、度量、指标、关系、绑定、映射与规则。
- 认证、发布、查询、权限变更全部落审计。

## 开源路线图

当前版本已具备完整的建模、绑定、校验、发布与问数闭环，并完成了前后端分离与独立前端迁移。后续按以下方向逐步完善：

### P0 已完成

- [x] 后端语义模型、绑定、校验、编译、问数、发布
- [x] Vue 3 + Vite + TypeScript 独立前端
- [x] 菜单与路由中英文词条
- [x] 本地运行与部署文档
- [x] 演示数据脚本

### P1 开源可用性

- [x] 选择并补充 LICENSE（MIT）
- [ ] 全栈 `docker compose up` 一键启动（后端 Dockerfile + 前端 Nginx）
- [ ] GitHub Actions：后端 pytest、前端 typecheck/build
- [ ] ESLint + Prettier + 提交规范
- [ ] 截图与在线演示环境
- [ ] CONTRIBUTING.md、Issue/PR 模板、CHANGELOG

### P2 工程质量

- [ ] TypeScript 严格模式，补齐领域类型
- [ ] 页面文案完整国际化（当前菜单/路由已双语，页面内文案以中文为主）
- [ ] 前端页面组件拆分与统一表单/表格组件
- [ ] 后端 API 集成测试与 golden SQL 覆盖扩充
- [ ] OpenAPI 文档完善与示例请求
- [ ] 性能基线：模型列表、校验、编译

### P3 产品能力

- [ ] 登录鉴权与多租户 RBAC
- [ ] 问数页面（SQL 预览、结果表格、解释链路）
- [ ] 指标血缘与依赖图可视化
- [ ] 关系画布
- [ ] 更多 SQL 方言适配
- [ ] 数据源连接管理与只读账号校验

欢迎按路线图提交 PR，或在 Issue 中讨论优先级。

## License

本项目采用 [MIT License](LICENSE)。
