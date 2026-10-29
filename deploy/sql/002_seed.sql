-- 语义层种子数据：角色、演示用户、演示主题域
-- 不插入示例模型/指标；由建模台或零售示例脚本创建。

INSERT INTO t_role (code, name, description) VALUES
  ('admin', '管理员', '全部权限'),
  ('modeler', '数据建模者', '语义模型、字段、维度、度量、关系'),
  ('metric_owner', '指标负责人', '指标口径与同义词'),
  ('engineer', '数据工程师', '绑定、字段映射、漂移处理'),
  ('reviewer', '评审者', '校验、认证、发布')
ON CONFLICT (code) DO NOTHING;

INSERT INTO t_user (user_id, name) VALUES
  ('dev-user', '演示用户'),
  ('admin', '管理员')
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO t_user_role (user_id, role_id)
SELECT 'dev-user', role_id FROM t_role WHERE code IN ('admin', 'modeler')
ON CONFLICT DO NOTHING;

INSERT INTO t_user_role (user_id, role_id)
SELECT 'admin', role_id FROM t_role WHERE code = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO t_sem_domain (name, description, owner)
VALUES ('零售经营', '订单、客户、门店、商品的经营分析', 'data-team')
ON CONFLICT (name) DO NOTHING;

INSERT INTO t_sem_domain_member (domain_id, user_id, role)
SELECT domain_id, 'dev-user', 'admin' FROM t_sem_domain WHERE name = '零售经营'
ON CONFLICT DO NOTHING;
