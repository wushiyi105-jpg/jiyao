"""集成测试:真起 http.server 发请求,真起子进程跑 CLI,用 examples/ 里的真实转写对着看结果。"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from jiyao import agent, rules, web

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
OUT = EXAMPLES / "out"


def _text(case):
    return (EXAMPLES / case).read_text(encoding="utf-8")


class ServerCase(unittest.TestCase):
    """每个用例起一个真 HTTP 服务,绑随机端口,用完关掉。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.db_path = os.path.join(cls.tmp.name, "it.db")
        handler = web._handler({"api_key": None, "model": None}, True, cls.db_path)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        """用原始 socket 发请求:要验的就是服务端自己的响应,不经过 urllib 的宽松处理。"""
        head = ["%s %s HTTP/1.1" % (method, path), "Host: 127.0.0.1"]
        raw = b""
        if body is not None:
            raw = body if isinstance(body, bytes) else body.encode("utf-8")
            head.append("Content-Type: application/json")
            head.append("Content-Length: %d" % len(raw))
        for k, v in (headers or {}).items():
            head.append("%s: %s" % (k, v))
        payload = ("\r\n".join(head) + "\r\n\r\n").encode("utf-8") + raw

        sock = socket.create_connection(("127.0.0.1", self.port), timeout=15)
        try:
            sock.sendall(payload)
            chunks = []
            while True:
                try:
                    piece = sock.recv(4096)
                except socket.timeout:
                    break
                if not piece:
                    break
                chunks.append(piece)
        finally:
            sock.close()
        data = b"".join(chunks).decode("utf-8", "replace")
        status = int(data.split(" ")[1])
        head, _, body_text = data.partition("\r\n\r\n")
        return status, head, body_text


class TestHttp(ServerCase):
    def test_index_serves_page(self):
        status, head, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", head)
        self.assertIn("会议转写", body)

    def test_status_reports_mock(self):
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"mock": True, "model": None})

    def test_minutes_roundtrip(self):
        status, _, body = self.request("POST", "/api/minutes",
                                       json.dumps({"text": _text("case-01.txt")}))
        self.assertEqual(status, 200)
        r = json.loads(body)
        for key in ("topic", "date", "template", "decisions", "todos", "suspended",
                    "vague", "agenda", "email", "minutes", "summary", "risks", "mode"):
            self.assertIn(key, r)
        self.assertEqual(r["topic"], "产品周会")
        self.assertEqual(r["date"], "2026-11-24")
        self.assertEqual(r["mode"], "offline")
        self.assertIsInstance(r["saved_id"], int)

    def test_minutes_save_false(self):
        status, _, body = self.request("POST", "/api/minutes",
                                       json.dumps({"text": _text("case-01.txt"), "save": False}))
        self.assertEqual(status, 200)
        self.assertNotIn("saved_id", json.loads(body))

    def test_truncated_json_is_400(self):
        """issue #3:非法 JSON 曾经是 500,还把 json 解析器原文透给前端。"""
        status, _, body = self.request("POST", "/api/minutes", '{"text": "张三: 明天')
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body), {"error": "请求体不是合法 JSON"})
        self.assertNotIn("Unterminated", body)
        self.assertNotIn("char", body)

    def test_form_body_is_400(self):
        status, _, body = self.request("POST", "/api/minutes", "text=hello&x=1")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body), {"error": "请求体不是合法 JSON"})
        self.assertNotIn("Expecting value", body)

    def test_unknown_post_path_404(self):
        status, _, body = self.request("POST", "/api/nope", '{"text": "x"}')
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"error": "not found"})

    def test_unknown_get_path_404(self):
        status, _, body = self.request("GET", "/api/nope")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"error": "not found"})

    def test_history_lists_saved(self):
        self.request("POST", "/api/minutes", json.dumps({"text": _text("case-02.txt")}))
        status, _, body = self.request("GET", "/api/history")
        self.assertEqual(status, 200)
        rows = json.loads(body)
        self.assertTrue(rows)
        self.assertEqual(rows[0]["topic"], "订单接口评审")


class TestCli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run([sys.executable, "-m", "jiyao", *args],
                              cwd=str(ROOT), input=stdin, capture_output=True,
                              text=True, encoding="utf-8", timeout=60)

    def test_minutes_file(self):
        p = self.run_cli("--mock", "minutes", "--file", str(EXAMPLES / "case-01.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("产品周会", p.stdout)
        self.assertIn("模板 周会", p.stdout)
        self.assertIn("决议 1 条", p.stdout)

    def test_todos_only(self):
        p = self.run_cli("--mock", "todos", "--file", str(EXAMPLES / "case-01.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("📌 待办", p.stdout)
        self.assertNotIn("跟进邮件", p.stdout)

    def test_email_has_subject(self):
        p = self.run_cli("--mock", "email", "--file", str(EXAMPLES / "case-01.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("【周会纪要】产品周会 2026-11-24", p.stdout)

    def test_agenda_only(self):
        p = self.run_cli("--mock", "agenda", "--file", str(EXAMPLES / "case-02.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("🗓 下次议程", p.stdout)
        self.assertIn("[悬置]", p.stdout)

    def test_json_is_parseable(self):
        p = self.run_cli("--mock", "--json", "minutes", "--file", str(EXAMPLES / "case-04.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        r = json.loads(p.stdout)
        self.assertEqual(r["template"], "复盘")
        self.assertIn("## 待办", r["minutes"])

    def test_stdin_pipe(self):
        p = self.run_cli("--mock", "minutes", stdin=_text("case-01.txt"))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("产品周会", p.stdout)

    def test_empty_input_is_2(self):
        p = self.run_cli("--mock", "minutes", stdin="")
        self.assertEqual(p.returncode, 2)
        self.assertIn("没有转写内容", p.stderr)

    def test_missing_file_is_2(self):
        """issue #6:曾经抛 FileNotFoundError 裸栈。"""
        p = self.run_cli("--mock", "minutes", "--file", str(ROOT / "nope.txt"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("找不到文件", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_db_is_dir_is_2(self):
        p = self.run_cli("--db", str(EXAMPLES), "history")
        self.assertEqual(p.returncode, 2)
        self.assertIn("数据库打不开", p.stderr)
        self.assertNotIn("Traceback", p.stderr)

    def test_bad_date_is_2(self):
        p = self.run_cli("--mock", "minutes", "--text", "会议: 周会\n张三: 接口文档我明天发出来。",
                         "--date", "2026-13-45")
        self.assertEqual(p.returncode, 2)
        self.assertIn("不是真实存在的日期", p.stderr)

    def test_history_saves_and_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "cli.db")
            empty = self.run_cli("--db", db, "history")
            self.assertIn("还没有记录", empty.stdout)
            saved = self.run_cli("--mock", "--db", db, "minutes",
                                 "--file", str(EXAMPLES / "case-03.txt"), "--save")
            self.assertEqual(saved.returncode, 0, saved.stderr)
            self.assertIn("已入库", saved.stdout)
            rows = self.run_cli("--db", db, "history")
            self.assertIn("客户沟通", rows.stdout)


class TestExamplesGolden(unittest.TestCase):
    """examples/out 是这几份真实转写的存档输出:改了规则就得一起改,否则这里红。"""

    CASES = ["case-01.txt", "case-02.txt", "case-03.txt", "case-04.txt"]

    def test_archive_matches_cli(self):
        for case in self.CASES:
            with self.subTest(case=case):
                p = subprocess.run([sys.executable, "-m", "jiyao", "--mock", "minutes",
                                    "--file", str(EXAMPLES / case)],
                                   cwd=str(ROOT), capture_output=True, text=True,
                                   encoding="utf-8", timeout=60)
                self.assertEqual(p.returncode, 0, p.stderr)
                archived = (OUT / case).read_text(encoding="utf-8")
                self.assertEqual(p.stdout.strip(), archived.strip())

    def test_cases_json_matches_files(self):
        data = json.loads((EXAMPLES / "cases.json").read_text(encoding="utf-8"))
        ids = [c["id"] for c in data["cases"]]
        self.assertEqual(ids, ["case-01", "case-02", "case-03", "case-04"])
        for c in data["cases"]:
            self.assertTrue((EXAMPLES / c["file"]).exists(), c["file"])
            self.assertTrue((OUT / c["file"]).exists(), c["file"])
            self.assertTrue(c["source"])
            self.assertTrue(c["expect"])

    def test_case01_expectations(self):
        r = rules.analyze(_text("case-01.txt"))
        self.assertEqual(r["template"], "周会")
        self.assertEqual(len(r["decisions"]), 1)
        li = [t for t in r["todos"] if t["owner"] == "李四" and "接口文档" in t["action"]][0]
        self.assertEqual(li["due"], "2026-11-25")
        self.assertTrue(li["complete"])
        wang = [t for t in r["todos"] if t["owner"] == "王五" and "回滚脚本" in t["action"]][0]
        self.assertEqual(wang["dependency"], "等")
        zhao = [t for t in r["todos"] if "灰度名单" in t["action"]][0]
        self.assertIn("截止", zhao["missing"])
        self.assertEqual(zhao["vague"], "尽快")

    def test_case01_deferred_is_suspended(self):
        """issue #7:「下周再说」「回头看看再定」曾进待办,悬置却是 0 条。"""
        r = rules.analyze(_text("case-01.txt"))
        self.assertEqual(len(r["suspended"]), 2)
        for t in r["todos"]:
            self.assertNotIn("下周再说", t["action"])
            self.assertNotIn("回头看看再定", t["action"])
        self.assertTrue(any("灰度" in s["text"] for s in r["suspended"]))
        self.assertTrue(any("回头看看再定" in s["text"] for s in r["suspended"]))

    def test_case02_expectations(self):
        r = rules.analyze(_text("case-02.txt"))
        self.assertEqual(r["template"], "评审")
        self.assertEqual(len(r["decisions"]), 2)
        self.assertEqual(len(r["suspended"]), 2)
        for s in r["suspended"]:
            self.assertNotIn(",,", s["question"])
            self.assertNotIn("，,", s["question"])

    def test_case03_expectations(self):
        r = rules.analyze(_text("case-03.txt"))
        self.assertEqual(r["template"], "客户")
        self.assertEqual(len(r["decisions"]), 0)
        zhao = [t for t in r["todos"] if "需求清单" in t["action"]][0]
        self.assertEqual(zhao["due"], "2026-11-19")
        self.assertTrue(any("导出" in s["question"] for s in r["suspended"]))
        mail = agent.analyze(_text("case-03.txt"), force_mock=True)["email"]
        self.assertIn("导出", mail)

    def test_case04_expectations(self):
        r = rules.analyze(_text("case-04.txt"))
        self.assertEqual(r["template"], "复盘")
        self.assertEqual(len(r["decisions"]), 1)
        wang = [t for t in r["todos"] if t["action"].startswith("回调字段清单")][0]
        self.assertEqual(wang["owner"], "王五")
        self.assertEqual(wang["due"], "2026-11-15")
        li = [t for t in r["todos"] if "幂等改造" in t["action"]][0]
        self.assertEqual(li["dependency"], "等")
        self.assertIn("37", r["numbers"])
        mail = agent.analyze(_text("case-04.txt"), force_mock=True)["email"]
        self.assertIn("37", mail)
        self.assertIn("21:40", mail)
        self.assertTrue(any("监控阈值" in s["question"] for s in r["suspended"]))


class TestRulesRegression(unittest.TestCase):
    def test_header_line_not_a_todo(self):
        """issue #4:表头行曾被动词表命中,抽成一条「完整」待办。"""
        r = rules.analyze(_text("case-02.txt"))
        for t in r["todos"]:
            self.assertNotIn("参会:", t["action"])
        self.assertFalse([a for a in r["agenda"] if "参会:" in a["text"]])

    def test_question_strips_clean(self):
        """issue #5:剥离标记词后曾有「,,」和断句。"""
        q = rules._question("遗留问题是幂等键,待定,下次评审再说")
        self.assertNotIn(",,", q)
        self.assertTrue(q.startswith("遗留问题是幂等键"))
        self.assertEqual(rules._question(""), "未明确结论，需要下次会上定")

    def test_question_only_markers(self):
        self.assertEqual(rules._question("待定"), "未明确结论，需要下次会上定")

    def test_strict_date_accepts(self):
        from datetime import date
        self.assertEqual(rules.strict_date("2026-11-24"), date(2026, 11, 24))

    def test_strict_date_rejects(self):
        """issue #6:2026-13-45 曾经静默回落到今天。"""
        for bad in ("2026-13-45", "2026-2-30", "11-24", "", "明天"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    rules.strict_date(bad)

    def test_header_words_skipped(self):
        rows = rules.lines("会议: 周会 2026-11-24\n张三: 明天发文档")
        self.assertEqual(rows, [("张三", "明天发文档")])


if __name__ == "__main__":
    unittest.main()
