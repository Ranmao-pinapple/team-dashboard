#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「月拉动计划」重算零件 pulled(已拉动) 标记。

规则(Zane 2026-11-24 定):
  pulled = 该零件在 orders.json 的月拉动计划中任一月有量(daily>0)
           或已有实际交付(actual>0)
  实际交付(actual)数据不全, 所以以「拉动计划有量」为主证据。

匹配顺序:
  1) 物料号/客户件号精确匹配(BIN/BEX/8位以上数字)
  2) 同项目内名称模糊匹配(相似度≥0.80, 取唯一最优)
  3) 都匹配不到 → 视为「未拉动」, 并在报告里列为"计划里没有该零件"

用法:
  python3 sync_pulled_from_pullplan.py            # 只出报告, 不改文件
  python3 sync_pulled_from_pullplan.py --apply    # 写回 projects.json
"""
import json, re, sys, os, difflib, unicodedata, collections, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
_D = os.path.join(BASE, "data")
if not os.path.isdir(_D):          # repo 布局: scripts/ 与 data/ 同级
    _D = os.path.join(os.path.dirname(BASE), "data")
PJ = os.path.join(_D, "projects.json")
OJ = os.path.join(_D, "orders.json")
ODJ = os.path.join(_D, "orders_data.json")
# ---- 项目/件号别名（Zane 2026-11-24: VF5 就是 VFe32 项目）----
ALIAS_PROJECT = {"VF5": "VFe32"}
ALIAS_CODE = {
    "BEX37122430AA": "510000000000017441",
    "BEX37122440AA": "510000000000017442",
    "BEX37122431AA": "510000000000017444",
    "BEX37122441AA": "510000000000017445",
    "BEX37122460AA": "510000000000017440",
    "BEX37122470AA": "510000000000017443",
}


CUR_MONTH = str(datetime.date.today().month)


def codes(s):
    return set(re.findall(r"(BIN\d{6,}[A-Z0-9]*|BEX\d+[A-Z]*|\d{8,})", s or ""))


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").upper()
    return re.sub(r"BIN\d+|BEX\d+|[\s\-_（）()、,·×]", "", s)


def flags(rows):
    plan_any = plan_cur = act = False
    months = set()
    for r in rows:
        d = r.get("daily") or {}
        for m, arr in d.items():
            if any(v for v in (arr or []) if v):
                plan_any = True
                months.add(m)
        if any(v for v in (d.get(CUR_MONTH) or []) if v):
            plan_cur = True
        ac = r.get("actual") or {}
        if any(v for arr in ac.values() for v in (arr or []) if v):
            act = True
    return plan_any, plan_cur, act, months


def main(apply=False):
    P = json.load(open(PJ, encoding="utf-8"))
    O = json.load(open(OJ, encoding="utf-8"))
    OD = json.load(open(ODJ, encoding="utf-8")) if os.path.exists(ODJ) else {"orders": []}

    # PO 证据(客户已下订单) 索引: part_code / 件号
    po_codes, po_parts = set(), []
    for o in OD.get("orders", []):
        if o.get("part_code"):
            po_codes.add(str(o["part_code"]))
        po_parts.append(o.get("part", ""))
    po_codes |= set(c for s in po_parts for c in codes(s))

    for r in O["rows"]:
        r["project"] = ALIAS_PROJECT.get(r.get("project", ""), r.get("project", ""))
    idx = collections.defaultdict(list)
    for r in O["rows"]:
        for c in codes(r["part"]):
            idx[c].append(r)
            if c in ALIAS_CODE:
                idx[ALIAS_CODE[c]].append(r)
    rows_by_proj = collections.defaultdict(list)
    for r in O["rows"]:
        rows_by_proj[r["project"]].append(r)

    flips_up, flips_dn, unmatched = [], [], []
    total = pulled = cur_cnt = 0
    for p in P["projects"]:
        cands = rows_by_proj.get(p["name"], [])
        for pt in (p.get("parts") or []):
            total += 1
            cs = codes(pt.get("name", "")) | ({pt["code"]} if pt.get("code") else set())
            rows, how = [], "code"
            for c in cs:
                rows += idx.get(c, [])
            if not rows and cands:
                n0 = norm(pt.get("name", ""))
                best = max(cands, key=lambda r: difflib.SequenceMatcher(None, n0, norm(r["part"])).ratio())
                ratio = difflib.SequenceMatcher(None, n0, norm(best["part"])).ratio()
                if ratio >= 0.80:
                    rows, how = [best], "fuzzy%.2f" % ratio
                else:
                    how = "unmatched"
            elif not rows:
                how = "unmatched"
            plan_any, plan_cur, act, months = flags(rows)
            has_po = bool(cs & po_codes)
            new = plan_any or act or has_po
            old = bool(pt.get("pulled"))
            if new:
                pulled += 1
            if plan_cur:
                cur_cnt += 1
            if new and not old:
                ev = "计划" if plan_any else ("实际" if act else "PO")
                flips_up.append((p["name"], pt.get("name", ""), sorted(months, key=int), plan_cur, ev))
            if old and not new:
                flips_dn.append((p["name"], pt.get("name", ""), how))
            if how == "unmatched":
                unmatched.append((p["name"], pt.get("name", "")))
            if apply:
                pt["pulled"] = new

    print("零件总数 %d | 已拉动 %d (本月 %d 月有量 %d) | 未拉动 %d"
          % (total, pulled, int(CUR_MONTH), cur_cnt, total - pulled))
    print("未拉动→已拉动 %d 件:" % len(flips_up))
    for f in flips_up:
        print("   +", f[0], f[1][:40], "| 证据", f[4], "| 计划月份", f[2], "| 本月有量" if f[3] else "")
    print("已拉动→未拉动 %d 件:" % len(flips_dn))
    for f in flips_dn:
        print("   -", f[0], f[1][:40], "|", f[2])
    print("拉动计划里查不到该零件 %d 件(保持未拉动):" % len(unmatched))
    u = collections.Counter(x[0] for x in unmatched)
    print("   ", dict(u))

    if apply:
        new_txt = json.dumps(P, ensure_ascii=False, indent=2, sort_keys=True)
        old_obj = json.load(open(PJ, encoding="utf-8"))
        old_txt = json.dumps({k: v for k, v in old_obj.items() if k != "updatedAt"},
                             ensure_ascii=False, indent=2, sort_keys=True)
        cmp_txt = json.dumps({k: v for k, v in P.items() if k != "updatedAt"},
                             ensure_ascii=False, indent=2, sort_keys=True)
        if new_txt == old_txt or cmp_txt == old_txt:
            print("拉动标记无变化，不写文件（避免 CI 循环提交）")
            return
        bak = PJ + ".bak.%s_pullplan_sync" % datetime.date.today().strftime("%Y%m%d")
        if not os.path.exists(bak):
            json.dump(old_obj, open(bak, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        P["updatedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        json.dump(P, open(PJ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("已写回", PJ)


if __name__ == "__main__":
    main("--apply" in sys.argv)
