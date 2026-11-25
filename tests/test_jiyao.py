import unittest
from datetime import date

from jiyao import agent, mock, rules

TRANSCRIPT = """会议: 产品周会 2026-11-24 参会: 张三,李四,王五
张三: 登录改版这版就定了,按新稿上线。
李四: 接口文档我明天发出来。
王五: 埋点方案还没定,下次再说。
张三: 数据看板尽快看一下。
李四: 等王五给字段清单再对接口。
"""


class TestParse(unittest.TestCase):
    def test_header(self):
        topic, people, held = rules.parse_header(TRANSCRIPT)
        self.assertEqual(topic, "产品周会")
        self.assertEqual(people, ["张三", "李四", "王五"])
        self.assertEqual(held, date(2026, 11, 24))

    def test_lines_speaker(self):
        rows = rules.lines(TRANSCRIPT)
        self.assertIn(("张三", "登录改版这版就定了,按新稿上线。"), rows)

    def test_people(self):
        self.assertEqual(rules.people(TRANSCRIPT), ["张三", "李四", "王五"])

    def test_month_day(self):
        self.assertEqual(rules.parse_date("11月24日开会", date(2026, 1, 1)), date(2026, 11, 24))

    def test_iso_date(self):
        self.assertEqual(rules.parse_date("2026-11-24"), date(2026, 11, 24))

    def test_bad_date_falls_back(self):
        base = date(2026, 11, 24)
        self.assertEqual(rules.parse_date("2026-13-40", base), base)

    def test_relative_dates(self):
        base = date(2026, 11, 24)
        hits = dict(rules.dates_in("明天交,后天再看", base))
        self.assertEqual(hits["明天"], date(2026, 11, 25))
        self.assertEqual(hits["后天"], date(2026, 11, 26))

    def test_weekday(self):
        base = date(2026, 11, 24)  # Tuesday
        self.assertEqual(dict(rules.dates_in("本周五", base))["本周五"], date(2026, 11, 27))
        self.assertEqual(dict(rules.dates_in("下周三", base))["下周三"], date(2026, 12, 2))

    def test_month_end(self):
        self.assertEqual(dict(rules.dates_in("月底前", date(2026, 11, 24)))["月底"], date(2026, 11, 30))


class TestExtract(unittest.TestCase):
    def test_decisions(self):
        d = rules.decisions(TRANSCRIPT)
        self.assertEqual(len(d), 1)
        self.assertIn("登录改版", d[0]["text"])

    def test_suspended(self):
        s = rules.suspended(TRANSCRIPT)
        self.assertTrue(any("埋点" in x["text"] for x in s))

    def test_todos_count(self):
        t = rules.todos(TRANSCRIPT, ["张三", "李四", "王五"], date(2026, 11, 24))
        self.assertGreaterEqual(len(t), 2)

    def test_todo_complete(self):
        t = rules.todos(TRANSCRIPT, ["张三", "李四", "王五"], date(2026, 11, 24))
        li = [x for x in t if x["owner"] == "李四" and "文档" in x["action"]][0]
        self.assertTrue(li["complete"])
        self.assertEqual(li["due"], "2026-11-25")

    def test_todo_missing_due(self):
        t = rules.todos(TRANSCRIPT, ["张三", "李四", "王五"], date(2026, 11, 24))
        kan = [x for x in t if "看板" in x["action"]][0]
        self.assertEqual(kan["missing"], ["截止"])
        self.assertEqual(kan["vague"], "尽快")

    def test_dependency(self):
        t = rules.todos(TRANSCRIPT, ["张三", "李四", "王五"], date(2026, 11, 24))
        self.assertTrue(any(x["dependency"] for x in t))

    def test_vague_hits(self):
        v = rules.vague_hits(TRANSCRIPT)
        self.assertTrue(any(x["word"] == "尽快" for x in v))

    def test_overdue(self):
        t = [{"action": "发文档", "owner": "李四", "due": "2026-11-20"}]
        self.assertEqual(len(rules.overdue(t, date(2026, 11, 24))), 1)

    def test_agenda_types(self):
        r = rules.analyze(TRANSCRIPT)
        kinds = {a["type"] for a in r["agenda"]}
        self.assertIn("悬置", kinds)

    def test_template_match(self):
        self.assertEqual(rules.template_for("产品周会")["name"], "周会")
        self.assertEqual(rules.template_for("季度复盘")["name"], "复盘")

    def test_numbers(self):
        self.assertEqual(rules.numbers("预算 12000,占用 30%"), ["12000", "30"])


class TestMarkdownAndAgent(unittest.TestCase):
    def test_markdown_sections(self):
        r = rules.analyze(TRANSCRIPT)
        md = rules.minutes_markdown(r, "摘要")
        for key in ("## 决议", "## 待办", "## 悬置问题", "## 下次议程"):
            self.assertIn(key, md)

    def test_offline_structure(self):
        r = agent.analyze(TRANSCRIPT, force_mock=True)
        self.assertEqual(r["mode"], "offline")
        for k in ("summary", "email", "minutes", "todos", "decisions", "suspended", "risks"):
            self.assertTrue(r[k])

    def test_email_local(self):
        r = agent.analyze(TRANSCRIPT, force_mock=True)
        self.assertEqual(r["email_source"], "local")
        self.assertIn("2026-11-24", r["email"])

    def test_strip_dates(self):
        self.assertNotIn("2026-11-24", agent.strip_dates("会议在 2026-11-24 开"))

    def test_guard_rejects_bad_date(self):
        r = rules.analyze(TRANSCRIPT)
        self.assertIsNone(agent.guard_email("请于 2026-12-01 前完成", r))

    def test_guard_rejects_bad_number(self):
        r = rules.analyze(TRANSCRIPT)
        self.assertIsNone(agent.guard_email("预算 8800 元", r))

    def test_guard_accepts_local_dates(self):
        r = rules.analyze(TRANSCRIPT)
        self.assertIsNotNone(agent.guard_email("会议 2026-11-24,接口文档 2026-11-25 前", r))

    def test_mock_draft_same_keys(self):
        r = rules.analyze(TRANSCRIPT)
        d = mock.draft(r)
        self.assertEqual(set(d), {"summary", "todo_hints", "risks", "email"})


if __name__ == "__main__":
    unittest.main()

