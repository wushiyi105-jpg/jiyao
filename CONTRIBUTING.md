# 参与

## 本地跑起来

```bash
uv sync --extra dev
uv run jiyao doctor
uv run pytest -q
```

## 提 PR 之前

1. 规则改动必须落在 `jiyao/domain/rules/`，并且新增一条 `rule_id`；
2. 每条 `rule_id` 至少一条断言；
3. 原文校验不许放宽：引用的句子必须能在转写里逐字找到；
4. `ruff check .`、`mypy jiyao`、`pytest -q` 全过；
5. 改表结构就加一条 `migrations/versions/`，写清 up/down。

## 提交信息

`type: 一句话说清改了什么`，type 用 feat / fix / docs / test / refactor。
