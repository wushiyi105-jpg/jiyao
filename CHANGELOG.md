# 更新记录

## 1.0.0

- 新栈重写：规则抽取（标记词 + 负责人正则 + 日期解析）、原文校验、完整性、逾期
- 每条决议与待办都带 `quote` + `offset`，找不到原文就丢弃（`trace.decision` / `trace.action`）
- 待办缺负责人 / 缺期限分别出 `action.no_owner` / `action.no_due`
- 逾期按天计算，超 7 天 severity=high
- 提醒任务 `jobs` 表 + `remind` 子命令，同一 key 只发一次，`--force` 可重发
- Alembic `0001_init` + `migrate` 子命令（0.x `meetings.topic` / `todos` 先备份再转换）
- CLI：digest / email / actions / done / remind / migrate / serve / doctor
- 测试 26 条，覆盖抽取、校验、提醒幂等、迁移、Web
