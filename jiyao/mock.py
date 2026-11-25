"""Offline draft: same shape as the model answer, built from local facts only."""


def draft(result):
    n_decision = len(result["decisions"])
    n_todo = len(result["todos"])
    n_open = len(result["suspended"])
    summary = "本次%s共 %d 条决议、%d 条待办、%d 个悬置问题；%s。" % (
        result["template"], n_decision, n_todo, n_open,
        "待办均含负责人与截止" if all(t["complete"] for t in result["todos"]) and n_todo
        else "有 %d 条待办信息不全，已标黄" % sum(1 for t in result["todos"] if not t["complete"])
    )
    hints = []
    for t in result["todos"]:
        if t["complete"]:
            h = "%s 前完成「%s」，完成后在群里回一句进度。" % (t["due_phrase"] or t["due"], t["verb"])
        else:
            h = "先补齐%s，再排期；否则下次会上仍会悬着。" % "、".join(t["missing"])
        hints.append({"action": t["action"], "hint": h})
    risks = []
    if result["overdue"]:
        risks.append("有 %d 条待办已过截止，仍未销项。" % len(result["overdue"]))
    for v in result["vague"]:
        risks.append("「%s」出现 %d 次，没有具体时间就等于没有截止。" % (v["word"], v["count"]))
    if n_open:
        risks.append("%d 个问题没有拍板，下次会容易重复讨论。" % n_open)
    if not risks:
        risks.append("本次没有明显风险项。")
    return {"summary": summary, "todo_hints": hints, "risks": risks[:4], "email": None}
