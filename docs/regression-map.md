# 回归测试映射

这一轮改的四条 issue 与测试的对应关系。写下来是为了下次动 `rules.py` / `web.py` / `cli.py` 时知道哪条测试会挡住。

## #3 非法或截断 JSON 回 500，还带着解析器原文

**原来**：`_read()` 直接 `json.loads`，`JSONDecodeError` 落到 `do_POST` 末尾的 `except Exception`，回 500，`str(e)` 原样给前端。用户看到的是「请求失败:Unterminated string starting at: line 1 column 10 (char 9)」。

**改法**：解析单独 `try`，失败回 **400** + `{"error": "请求体不是合法 JSON"}`；兜底 500 只回 `{"error": "服务器内部错误"}`，不再透 `str(e)`。

- 测试：`TestHttp.test_truncated_json_is_400` —— 断言 400、断言响应等于那句固定文案、断言**没有** `Unterminated`。
- 测试：`TestHttp.test_form_body_is_400` —— 表单编码同样走 400，不再冒出 `Expecting value`。

## #4 表头行被抽成一条待办

**原来**：`lines()` 用「短词 + 冒号」认发言人，表头里的 `会议:` `参会:` 和 `张三:` 长得一样，于是 `("会议", "订单接口评审 2026-11-20 参会: …")` 成了一条发言。「评审」命中动词表、日期成了截止、owner 落到第一个参会人 —— 整行表头变成一条「今天完成」的完整待办，还进下次议程的「超期」列表。

**改法**：`lines()` 加 `HEADER_WORDS` 排除（会议/主题/议题/参会/参与/参加/出席/地点/时间/日期/主持/记录），表头行不进 `sentences()`。`people()` 里本来就有一份排除名单，现在两处一致。

- 测试：`TestRulesRegression.test_header_line_not_a_todo` —— case-02 的待办里不能出现 `参会:`，下次议程里也不能。
- 测试：`TestRulesRegression.test_header_words_skipped` —— `lines()` 只留下真正的发言行。

## #5 剥离标记词后残留标点

**原来**：`_question()` 逐词 `replace` 再 `strip(" ，,。；")`，只去首尾。`待定` 被删掉后中间留下 `,,`，`回头讨论` 被删掉后留下「这个我,先按旧方案上」。

**改法**：按 `，,、；;` 切成分句，删空分句再拼回：`这个我，先按旧方案上`、`遗留问题是幂等键，下次评审再说`。

- 测试：`TestRulesRegression.test_question_strips_clean` —— 断言没有 `,,`，且前半句完整。
- 测试：`TestRulesRegression.test_question_only_markers` —— 整句只有「待定」时给兜底文案，不给空串。

## #6 CLI 入参出错时没有提示

**原来**：`--file` 不存在抛 `FileNotFoundError` 裸栈；`--db` 指向目录抛 `sqlite3.OperationalError`；`--date` 写 `2026-13-45` 时 `parse_date()` 静默 return today，截止日期全跟着漂。

**改法**：`_text()` 抛 `CliError`（找不到文件 / 是目录 / 不是 UTF-8）；`main()` 捕获 `CliError` 与 `sqlite3.Error`，打印一行 `❌` 并 exit 2；新增 `rules.strict_date()`，`--date` 先校验，非法直接 exit 2。

- 测试：`TestCli.test_missing_file_is_2` / `test_db_is_dir_is_2` / `test_bad_date_is_2` —— 都是 exit 2、都有 `❌`、都断言**没有** `Traceback`。
- 测试：`TestRulesRegression.test_strict_date_rejects` —— `2026-13-45`、`2026-2-30`、`11-24`、空串、「明天」全部抛 `ValueError`。

## 示例侧的护栏

`examples/out/` 是四份真实转写的存档输出。`TestExamplesGolden.test_archive_matches_cli` 会重跑 CLI 逐字比对 —— **动了抽取规则而忘了更新存档，这条立刻红**。另外四组 `test_case0N_expectations` 把 `cases.json` 里承诺的结论钉成断言（哪条进决议、哪条缺截止、哪条进悬置）。
