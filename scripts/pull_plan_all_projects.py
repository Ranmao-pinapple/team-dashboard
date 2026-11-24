#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月拉动计划页的数据展开：orders.json 的行 + 所有项目零件(没有计划的行补 0)。

build_dashboard.py 调 display_rows(projects, pull_data) 拿展开后的 rows。
规则：
  1) orders.json 的既有行原样保留（project 名按项目卡规范名归一，如 ROXMCE→ROX MCE）
  2) 项目卡里每个零件，先按物料号/件号精确匹配、再按同项目名称模糊匹配(≥0.80)找计划行
  3) 找不到 → 补一行 daily/actual 全空(前端按 0 显示)，noPlan=True
"""
import re
import difflib
import unicodedata
import collections

MATCH_RATIO = 0.80


def _codes(s):
    return set(re.findall(r"(BIN\d{6,}[A-Z0-9]*|BEX\d+[A-Z]*|\d{8,})", s or ""))


def _norm(s):
    s = unicodedata.normalize("NFKC", s or "").upper()
    return re.sub(r"BIN\d+|BEX\d+|[\s\-_（）()、,·×]", "", s)


def _canon(name, pool):
    n = re.sub(r"[^A-Z0-9]", "", (name or "").upper())
    for x in pool:
        if re.sub(r"[^A-Z0-9]", "", x.upper()) == n:
            return x
    return name


def display_rows(projects, pull_data):
    """返回展开后的 rows(新增零行), 不改动入参。"""
    src = [dict(r) for r in (pull_data.get("rows") or [])]
    names = [p.get("name", "") for p in (projects.get("projects") or [])]
    for r in src:
        r["project"] = _canon(r.get("project", ""), names)

    idx = collections.defaultdict(list)
    for r in src:
        for c in _codes(r.get("part", "")):
            idx[c].append(r)
    by_proj = collections.defaultdict(list)
    for r in src:
        by_proj[r.get("project")].append(r)

    extra = []
    for p in projects.get("projects") or []:
        cands = by_proj.get(p.get("name"), [])
        for pt in p.get("parts") or []:
            cs = _codes(pt.get("name", "")) | ({pt["code"]} if pt.get("code") else set())
            hit = []
            for c in cs:
                hit += idx.get(c, [])
            if not hit and cands:
                n0 = _norm(pt.get("name", ""))
                best = max(cands, key=lambda r: difflib.SequenceMatcher(None, n0, _norm(r.get("part", ""))).ratio())
                if difflib.SequenceMatcher(None, n0, _norm(best.get("part", ""))).ratio() >= MATCH_RATIO:
                    hit = [best]
            if hit:
                continue
            nm = pt.get("name", "")
            code = pt.get("code") or ""
            label = nm if (not code or code in nm) else (nm + " " + code)
            extra.append({
                "part": label,
                "project": p.get("name", ""),
                "proj": p.get("customer", ""),
                "status": p.get("status", "active"),
                "makeType": pt.get("makeType") or "",
                "supplier": pt.get("supplier") or "",
                "daily": {},
                "actual": {},
                "noPlan": True,
            })
    return src + extra


if __name__ == "__main__":
    import json
    import os
    import sys

    base = os.path.dirname(os.path.abspath(__file__))
    ddir = os.path.join(base, "data")
    if not os.path.isdir(ddir):
        ddir = os.path.join(os.path.dirname(base), "data")
    P = json.load(open(os.path.join(ddir, "projects.json"), encoding="utf-8"))
    O = json.load(open(os.path.join(ddir, "orders.json"), encoding="utf-8"))
    rows = display_rows(P, O)
    print("计划行 %d + 补零行 %d = %d 行" % (len(O.get("rows") or []), len(rows) - len(O.get("rows") or []), len(rows)))
    cnt = collections.Counter(r["project"] for r in rows)
    for k, v in cnt.items():
        print("  ", k, v)
