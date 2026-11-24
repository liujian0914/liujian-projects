# -*- coding: utf-8 -*-
"""把旧的 bank.json 转成「题库格式规范 v1.0」的 .qbank.json，作为示例题库。"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = sys.argv[1] if len(sys.argv) > 1 else r"D:\毛概刷题系统\bank.json"
OUT = os.path.join(ROOT, "samples", "毛概题库.qbank.json")

old = json.load(open(SRC, encoding="utf-8"))

chapters = []
for c in old.get("chapters", []):
    chapters.append({"id": "ch%d" % c["id"], "name": c["name"], "order": c["id"]})

TYPE_MAP = {"single": "single", "multi": "multi", "judge": "judge", "indefinite": "indefinite"}

questions = []
for q in old["questions"]:
    o = {
        "id": "ch%d-%s-%d" % (q["ch"], q["type"], q["no"]),
        "type": TYPE_MAP.get(q["type"], "single"),
        "chapter": "ch%d" % q["ch"],
        "number": q["no"],
        "stem": q["stem"],
        "options": [{"key": k, "text": v} for k, v in sorted(q["options"].items())],
        "answer": q["answer"],
        "analysis": q.get("analysis", ""),
    }
    questions.append(o)

bank = {
    "format": "qbank",
    "version": "1.0",
    "meta": {
        "id": "maogai-2026-10",
        "title": "毛泽东思想和中国特色社会主义理论体系概论 题库",
        "subject": "毛泽东思想和中国特色社会主义理论体系概论",
        "source": "概论课题库（2026.10修订）.docx",
        "edition": "2026.10 修订",
        "createdAt": "2026-11-24T20:00:00+08:00",
        "questionCount": len(questions),
        "description": "8 章，含单选、多选、判断。第二章多选第 7 题按用户要求为 ABD。",
    },
    "chapters": chapters,
    "questions": questions,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(bank, f, ensure_ascii=False, indent=1)

print("写出", OUT)
print("题数", len(questions), "章节", len(chapters))
stat = {}
for q in questions:
    stat[q["type"]] = stat.get(q["type"], 0) + 1
print("题型", stat)
