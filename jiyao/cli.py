"""命令行入口:python -m jiyao <命令>。"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, agent, db, llm, rules
from .llm import LLMError

BANNER = ("⚠️  当前为离线模式(未配置 LLM_API_KEY):待办、决议、悬置与纪要正文由本地规则生成。\n"
          "   填入 LLM_API_KEY 后,摘要、执行提示与跟进邮件由模型撰写(日期与数字仍以本地抽取为准)。\n")


def _text(args):
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def render(r):
    mode = "模型" if r["mode"] == "model" else "离线模式"
    lines = ["📝 会议纪要 · %s  [%s]" % (r["topic"], mode), "",
             "📅 %s · 模板 %s · 参会 %s" % (r["date"], r["template"], "、".join(r["participants"]) or "—"), ""]
    lines.append("✅ 决议 %d 条" % len(r["decisions"]))
    for d in r["decisions"]:
        lines.append("  · %s(%s)" % (d["text"], d["speaker"] or "—"))
    lines.append("")
    lines.append("📌 待办 %d 条" % len(r["todos"]))
    for i, t in enumerate(r["todos"], 1):
        flag = "✅" if t["complete"] else "⚠️ 缺 " + "、".join(t["missing"])
        lines.append("  %d. [%s] %s · 截止 %s · 依赖 %s  %s"
                     % (i, t["owner"], t["action"], t["due"] or "待定", t["dependency"] or "—", flag))
        if t.get("hint"):
            lines.append("     提示:" + t["hint"])
    lines.append("")
    lines.append("⏳ 悬置 %d 条" % len(r["suspended"]))
    for s in r["suspended"]:
        lines.append("  · %s(%s)" % (s["question"], s["speaker"] or "—"))
    lines.append("")
    if r["vague"]:
        lines.append("🟡 含糊词")
        for v in r["vague"]:
            lines.append("  · 「%s」× %d" % (v["word"], v["count"]))
        lines.append("")
    lines.append("🗓 下次议程")
    for a in r["agenda"]:
        lines.append("  · [%s] %s" % (a["type"], a["text"]))
    if not r["agenda"]:
        lines.append("  · 无")
    lines.append("")
    lines.append("📄 跟进邮件 (%s)" % ("模型草稿" if r["email_source"] == "model" else "本地生成"))
    lines.append(r["email"])
    return "\n".join(lines)


def cmd_minutes(args):
    text = _text(args)
    if not text.strip():
        print("❌ 没有转写内容:用 --text、--file 或管道输入。", file=sys.stderr)
        sys.exit(2)
    db.use(args.db)
    r = agent.analyze(text, topic=args.topic, meeting_date=args.date, force_mock=args.mock)
    if args.save:
        r["saved_id"] = db.save(r)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(render(r))
    if r.get("saved_id"):
        print("\n已入库(#%d),`python -m jiyao history` 可回看。" % r["saved_id"])


def cmd_todos(args):
    text = _text(args)
    r = rules.analyze(text, topic=args.topic, meeting_date=args.date)
    if args.json:
        print(json.dumps(r["todos"], ensure_ascii=False, indent=2))
        return
    print("📌 待办 %d 条" % len(r["todos"]))
    for i, t in enumerate(r["todos"], 1):
        print("  %d. [%s] %s · %s %s" % (i, t["owner"], t["action"], t["due"] or "待定",
                                        "" if t["complete"] else "⚠️ 缺 " + "、".join(t["missing"])))


def cmd_email(args):
    text = _text(args)
    db.use(args.db)
    r = agent.analyze(text, topic=args.topic, meeting_date=args.date, force_mock=args.mock)
    print(r["email"])
    print("\n(来源:%s)" % ("模型草稿,已通过日期与数字校验" if r["email_source"] == "model" else "本地模板"))


def cmd_agenda(args):
    text = _text(args)
    r = rules.analyze(text, topic=args.topic, meeting_date=args.date)
    print("🗓 下次议程")
    for a in r["agenda"]:
        print("  · [%s] %s" % (a["type"], a["text"]))
    if not r["agenda"]:
        print("  · 无待定项")


def cmd_history(args):
    db.use(args.db)
    rows = db.meetings(args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("还没有记录。`python -m jiyao minutes --file transcript.txt --save` 存一条。")
        return
    print("📚 会议记录")
    for r in rows:
        print("  #%d  %s  %s  决议 %d / 待办 %d / 悬置 %d  %s"
              % (r["id"], r["held_on"], r["topic"], r["decisions"], r["todos"],
                 r["open_items"], r["created_at"]))


def cmd_web(args):
    from . import web
    web.serve(host=args.host, port=args.port, db_path=args.db, force_mock=args.mock)


def build_parser():
    p = argparse.ArgumentParser(prog="jiyao", description="纪要 · 会议:决议、待办、悬置、跟进邮件。")
    p.add_argument("--version", action="version", version="jiyao %s" % __version__)
    p.add_argument("--mock", action="store_true", help="强制离线模式")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    p.add_argument("--model", help="覆盖 LLM_MODEL")
    p.add_argument("--base-url", help="覆盖 LLM_BASE_URL")
    p.add_argument("--api-key", help="覆盖 LLM_API_KEY")
    p.add_argument("--db", help="SQLite 路径")
    sub = p.add_subparsers(dest="command", required=True)

    for name, func, help_text in (("minutes", cmd_minutes, "生成完整纪要"),
                                  ("todos", cmd_todos, "只看待办"),
                                  ("email", cmd_email, "只出跟进邮件"),
                                  ("agenda", cmd_agenda, "只看下次议程")):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--text", help="转写文本")
        sp.add_argument("--file", help="从文件读")
        sp.add_argument("--topic", help="会议主题(默认取首行)")
        sp.add_argument("--date", help="会议日期 YYYY-MM-DD")
        if name in ("minutes", "email"):
            sp.add_argument("--save", action="store_true")
        sp.set_defaults(func=func)

    hp = sub.add_parser("history", help="历史记录")
    hp.add_argument("--limit", type=int, default=10)
    hp.set_defaults(func=cmd_history)

    wp = sub.add_parser("web", help="启动 Web 界面")
    wp.add_argument("--host", default="127.0.0.1")
    wp.add_argument("--port", type=int, default=8000)
    wp.add_argument("--mock", action="store_true", default=argparse.SUPPRESS)
    wp.set_defaults(func=cmd_web)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.mock and args.command in ("minutes", "email") and not llm.default_config().get("api_key"):
        print(BANNER, file=sys.stderr)
    try:
        args.func(args)
    except LLMError as e:
        print("❌ %s" % e, file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
