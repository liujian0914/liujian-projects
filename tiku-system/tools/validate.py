# -*- coding: utf-8 -*-
"""校验题库文件 / 记录文件是否符合「题库格式规范 v1.0（严格版）」。

用法：
    python tools/validate.py 题库.json
    python tools/validate.py 记录.qrec.json --record
    python tools/validate.py 记录.qrec.json --record --bank 题库.json
    python tools/validate.py 文件.json --json      以 JSON 输出

返回码：0 全部合格；1 有问题。
"""
import json
import re
import sys



# -------------------------------------------------- 宽容读取
def load_loose(path):
    """先按标准 JSON 读；失败则剥掉 AI 回复常见的代码围栏/前后说明。
    只处理外壳，数据内容仍交给 check_bank / check_record 严格校验。"""
    text = open(path, encoding="utf-8-sig").read().strip()
    try:
        return json.loads(text), False
    except Exception:
        pass

    for m in re.finditer(r"```[A-Za-z0-9_+-]*[ \t]*\r?\n([\s\S]*?)```", text):
        try:
            return json.loads(m.group(1).strip()), True
        except Exception:
            pass

    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        op, cl = ("{", "}") if ch == "{" else ("[", "]")
        depth, in_str, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
                continue
            if c == op:
                depth += 1
            elif c == cl:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:j + 1]), True
                    except Exception:
                        break
        if i > 20000:
            break
    raise ValueError("找不到合法的 JSON 对象（可手动去掉代码围栏后重试）")


# ---------------------------------------------------------------- 题库
def check_bank(bank):
    errs, warns = [], []

    if not isinstance(bank, dict):
        return ["顶层不是 JSON 对象"], [], {}

    if bank.get("format") != "qbank":
        errs.append('format 必须是 "qbank"，实际是 %r' % bank.get("format"))
    if str(bank.get("version")) != "1.0":
        errs.append('version 必须是 "1.0"，实际是 %r' % bank.get("version"))

    meta = bank.get("meta")
    if not isinstance(meta, dict):
        errs.append("缺少 meta 对象")
        meta = {}
    else:
        mid = str(meta.get("id") or "")
        if not mid:
            errs.append("meta.id 缺失")
        elif not re.match(r"^[a-z0-9][a-z0-9-]*$", mid):
            errs.append("meta.id 只能用 小写字母/数字/短横线，实际 %r" % mid)
        if not str(meta.get("title") or "").strip():
            errs.append("meta.title 缺失")

    chapters = bank.get("chapters") or []
    if not isinstance(chapters, list):
        errs.append("chapters 必须是数组")
        chapters = []
    chap_ids = set()
    for i, c in enumerate(chapters):
        if not isinstance(c, dict):
            errs.append("chapters[%d] 不是对象" % i)
            continue
        cid = str(c.get("id") or "")
        if not cid:
            errs.append("chapters[%d] 缺少 id" % i)
        elif cid in chap_ids:
            errs.append("章节 id 重复：%s" % cid)
        else:
            chap_ids.add(cid)
        if not str(c.get("name") or "").strip():
            errs.append("chapters[%d] 缺少 name" % i)

    qs = bank.get("questions")
    if not isinstance(qs, list) or not qs:
        errs.append("questions 缺失或为空")
        return errs, warns, {}

    ids = set()
    stat = {}
    for i, q in enumerate(qs):
        tag = "questions[%d]" % i
        if not isinstance(q, dict):
            errs.append(tag + " 不是对象")
            continue
        qid = str(q.get("id") or "")
        tag = qid or tag
        if not qid:
            errs.append("%s 缺少 id" % tag)
        elif qid in ids:
            errs.append("题目 id 重复：%s" % qid)
        else:
            ids.add(qid)

        t = q.get("type")
        if t not in ("single", "multi", "judge", "indefinite"):
            errs.append("%s：type 非法（%r）" % (tag, t))
            t = "single"
        stat[t] = stat.get(t, 0) + 1

        if not str(q.get("stem") or "").strip():
            errs.append("%s：题干为空" % tag)

        opts = q.get("options")
        keys = []
        if isinstance(opts, list):
            for o in opts:
                if not isinstance(o, dict):
                    errs.append("%s：options 里有非对象元素" % tag)
                    continue
                k = str(o.get("key") or "").upper()
                if not k:
                    errs.append("%s：有选项缺少 key" % tag)
                    continue
                keys.append(k)
                if not str(o.get("text") or "").strip():
                    errs.append("%s：选项 %s 内容为空" % (tag, k))
        elif isinstance(opts, dict):
            keys = sorted(str(k).upper() for k in opts.keys())
            warns.append("%s：options 用了对象写法，建议改成数组" % tag)
        else:
            errs.append("%s：缺少 options" % tag)

        if keys:
            expect = [chr(ord("A") + i) for i in range(len(keys))]
            if sorted(keys) != expect:
                errs.append("%s：选项字母应为 %s，实际 %s" % (tag, "".join(expect), "".join(sorted(keys))))
            if not (2 <= len(keys) <= 8):
                errs.append("%s：选项数量 %d，应为 2–8" % (tag, len(keys)))

        ans = q.get("answer")
        if not isinstance(ans, list):
            errs.append("%s：answer 必须是数组" % tag)
            ans = []
        ans = [str(a).upper() for a in ans]
        if not ans:
            errs.append("%s：没有答案" % tag)
        for a in ans:
            if keys and a not in keys:
                errs.append("%s：答案 %s 不在选项里" % (tag, a))
        if t in ("single", "judge") and len(ans) != 1:
            errs.append("%s：%s 应有 1 个答案，实际 %d 个" % (tag, t, len(ans)))
        if t == "multi" and 0 < len(ans) < 2:
            warns.append("%s：多选只有 1 个答案，原文若是「不定项」应改成 indefinite" % tag)

        ch = q.get("chapter")
        if ch not in (None, "") and chap_ids and str(ch) not in chap_ids:
            errs.append("%s：chapter %r 不在 chapters 里" % (tag, ch))

    cnt = meta.get("questionCount")
    if isinstance(cnt, int) and cnt != len(qs):
        warns.append("meta.questionCount 写的是 %d，实际 %d" % (cnt, len(qs)))

    return errs, warns, stat


# ---------------------------------------------------------------- 记录
def check_record(rec, bank=None):
    errs, warns = [], []

    if not isinstance(rec, dict):
        return ["顶层不是 JSON 对象"], []

    if rec.get("format") != "qbank-record":
        errs.append('format 必须是 "qbank-record"，实际是 %r' % rec.get("format"))
    if str(rec.get("version")) != "1.0":
        errs.append('version 必须是 "1.0"，实际是 %r' % rec.get("version"))

    bank_id = str(rec.get("bankId") or "")
    if not bank_id:
        errs.append("缺少 bankId")
    if bank and isinstance(bank, dict):
        want = str((bank.get("meta") or {}).get("id") or "")
        if want and bank_id and bank_id != want:
            errs.append("bankId 不匹配：记录是 %r，题库是 %r" % (bank_id, want))

    known = set()
    if bank and isinstance(bank, dict):
        known = {str(q.get("id")) for q in (bank.get("questions") or []) if isinstance(q, dict)}

    recs = rec.get("records")
    if not isinstance(recs, dict):
        return errs + ["records 必须是对象"], warns
    if not recs:
        errs.append("records 是空的")

    miss = []
    for qid, r in recs.items():
        tag = str(qid)
        if known and tag not in known:
            miss.append(tag)
            continue
        if not isinstance(r, dict):
            errs.append("%s：记录不是对象" % tag)
            continue

        att = r.get("attempts")
        cor = r.get("correct")
        if att is not None and (not isinstance(att, int) or isinstance(att, bool) or att < 0):
            errs.append("%s：attempts 必须是非负整数" % tag)
        if cor is not None:
            if not isinstance(cor, int) or isinstance(cor, bool) or cor < 0:
                errs.append("%s：correct 必须是非负整数" % tag)
            elif isinstance(att, int) and cor > att:
                errs.append("%s：correct(%s) 超过 attempts(%s)" % (tag, cor, att))

        h = r.get("history")
        if h is not None:
            if not isinstance(h, list):
                errs.append("%s：history 必须是数组" % tag)
            else:
                if len(h) > 50:
                    errs.append("%s：history 有 %d 条，超过 50 上限" % (tag, len(h)))
                if isinstance(att, int) and att < len(h):
                    errs.append("%s：attempts(%s) 小于明细条数(%d)" % (tag, att, len(h)))
                for j, x in enumerate(h):
                    if not isinstance(x, dict):
                        errs.append("%s：history[%d] 不是对象" % (tag, j))
                        continue
                    if not isinstance(x.get("picked"), list):
                        errs.append("%s：history[%d].picked 必须是数组" % (tag, j))
                    if not isinstance(x.get("correct"), bool):
                        errs.append("%s：history[%d].correct 必须是布尔" % (tag, j))

        wo = r.get("wrongOptions")
        if wo is not None:
            if not isinstance(wo, dict):
                errs.append("%s：wrongOptions 必须是对象" % tag)
            else:
                for k, v in wo.items():
                    if str(k).upper() not in list("ABCDEFGH"):
                        errs.append("%s：wrongOptions 的键 %r 不是 A–H" % (tag, k))
                    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                        errs.append("%s：wrongOptions[%r] 必须是正整数" % (tag, k))

        for key in ("flagged", "starred"):
            if r.get(key) is not None and not isinstance(r.get(key), bool):
                errs.append("%s：%s 必须是布尔" % (tag, key))
        for key in ("note", "aiAnalysis"):
            if r.get(key) is not None and not isinstance(r.get(key), str):
                errs.append("%s：%s 必须是字符串" % (tag, key))
        if r.get("lastCorrect") is not None and not isinstance(r.get("lastCorrect"), bool):
            errs.append("%s：lastCorrect 必须是布尔或 null" % tag)

    if miss:
        errs.append("有 %d 个题号在题库里找不到：%s" % (len(miss), "、".join(miss[:8])))

    return errs, warns


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    is_record = "--record" in sys.argv
    bank_path = None
    if "--bank" in sys.argv:
        i = sys.argv.index("--bank")
        if i + 1 < len(sys.argv):
            bank_path = sys.argv[i + 1]

    if not args:
        print(__doc__)
        return

    path = args[0]
    try:
        data, cleaned = load_loose(path)
        if cleaned:
            print("提示：已自动去掉代码围栏/说明文字，以下校验针对里面的 JSON 本体。")
    except Exception as e:
        print("读取失败：%s" % e)
        sys.exit(1)

    if is_record:
        bank = None
        if bank_path:
            try:
                bank, _ = load_loose(bank_path)
            except Exception as e:
                print("题库读取失败：%s" % e)
                sys.exit(1)
        errs, warns = check_record(data, bank)
        if as_json:
            print(json.dumps({"ok": not errs, "kind": "record", "errors": errs, "warnings": warns},
                             ensure_ascii=False, indent=1))
        else:
            print("记录文件：bankId=%s，%d 条记录" % (data.get("bankId"), len(data.get("records") or {})))
            print("-" * 50)
            if not errs:
                print("全部通过" + ("（已与题库核对题号）" if bank else "（未提供 --bank，未核对题号）"))
            for e in errs:
                print("[错误] " + e)
            for w in warns:
                print("[警告] " + w)
            print("-" * 50)
            print("错误 %d 处，警告 %d 处" % (len(errs), len(warns)))
        sys.exit(1 if errs else 0)

    errs, warns, stat = check_bank(data)
    if as_json:
        print(json.dumps({"ok": not errs, "kind": "bank", "errors": errs, "warnings": warns,
                          "types": stat}, ensure_ascii=False, indent=1))
    else:
        meta = data.get("meta") or {}
        print("题库：%s（%s）" % (meta.get("title", "?"), meta.get("id", "?")))
        print("题数 %d ｜ 章节 %d ｜ 题型 %s" % (
            len(data.get("questions") or []), len(data.get("chapters") or []),
            "，".join("%s %d" % (k, v) for k, v in sorted(stat.items())) or "—"))
        print("-" * 50)
        if not errs and not warns:
            print("全部通过")
        for e in errs:
            print("[错误] " + e)
        for w in warns:
            print("[警告] " + w)
        print("-" * 50)
        print("错误 %d 处，警告 %d 处" % (len(errs), len(warns)))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
