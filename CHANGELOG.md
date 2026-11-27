# 更新记录

## Unreleased

- 新增 `minutes`：一次输出会议纪要 + 邮件草稿 + 可复制群消息，每条结论附原文与字符位置
- 新增 `seed`：3 场真实会议（周会 / 复盘 / 启动会），共 12 条结论、9 条待办
- 新增本地数据：3 类会议模板、12 条决议句式、14 个责任人别名（小李→李明、运营→运营组等）
- 动作识别改为“动词 + 时间/负责人”，去掉只有时间词的假待办；疑问句不再误判为决议
- `0001_init` 改为显式 `op.create_table` / `op.create_index`，运行期走 `alembic upgrade`
- `app/` 只依赖 `ports`，新增内存假实现用例
- 开 ruff `E2`/`E3`；CI 增加 `docker build` 与 `/health` 探活

## 1.0.0

- 新栈重写：规则抽取（标记词 + 负责人正则 + 日期解析）、原文校验、完整性、逾期
- 每条决议与待办都带 `quote` + `offset`，找不到原文就丢弃（`trace.decision` / `trace.action`）
- 待办缺负责人 / 缺期限分别出 `action.no_owner` / `action.no_due`
- 逾期按天计算，超 7 天 severity=high
- 提醒任务 `jobs` 表 + `remind` 子命令，同一 key 只发一次，`--force` 可重发
- Alembic `0001_init` + `migrate` 子命令（0.x `meetings.topic` / `todos` 先备份再转换）
- CLI：digest / email / actions / done / remind / migrate / serve / doctor
- 测试 26 条，覆盖抽取、校验、提醒幂等、迁移、Web
