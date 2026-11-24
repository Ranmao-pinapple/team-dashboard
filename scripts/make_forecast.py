#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「销售额预测」页数据 (data/forecast.json) 并注入 forecast.html

口径（Zane 2026-11-24）：
    年用量(件)     = 单车用量 × 年产量(台/年)
    年销售额(未税) = 单价未税 × 年用量
    含税 = 未税 × 1.13

数据来源优先级：
    1) 定点内部信（凯华/海泰 提交表）—— 单价未税、单车用量、平均年产量、生命周期
    2) 项目卡 projects.json 的报价（含税 ÷1.13）+ 参数表里的年产量/单车用量
    3) 都没有 → 标「待补」，不计入合计
"""
import json
import os
import glob
import datetime
import openpyxl

BASE = os.path.dirname(os.path.abspath(__file__))
DDIR = os.path.join(BASE, "data")
if not os.path.isdir(DDIR):
    DDIR = os.path.join(os.path.dirname(BASE), "data")
ROOT = os.path.dirname(DDIR)
PJ = os.path.join(DDIR, "projects.json")
OUT = os.path.join(DDIR, "forecast.json")
TAX = 1.13

DESK = "/mnt/c/Users/Administrator/Desktop"

# ---- 定点内部信（按项目）----
DINGDIAN = {
    "VFe32": DESK + "/上汽/Vfe32项目新增零件 定点内部信20261013110322893(V1更新-11.15).xlsx",
    "ROX01": DESK + "/凯华订单/10月/ROX01项目IP毛毡海绵条内部定点信.xlsx",
    "EHEA": DESK + "/凯华订单/浙江凯华 EH项目IP件辅料定点信息提交表.xlsx",
    "S56": DESK + "/海泰/浙江凯华奇瑞项目S56吸音棉定点信息提交表价格更新.xlsx",
}

# ---- 没有定点信的项目：年产量（台/年），None=待补 ----
VOLUME = {
    "BS5PR": (100000, "定点信 平均年产量 10 万台"),
    "LEV1": (192000, "名义 19.2 万套/年（台账为准）"),
    "ZH5EM": (96000, "8,000 台/月 × 12（需确认）"),
    "VFe32": (60000, "定点信 平均年产量 6 万台"),
    "ROX01": (12000, "定点信 平均年产量 1.2 万台"),
    "EHEA": (100000, "定点信 平均年产量 10 万台"),
    "S56": (50000, "定点信 平均年产量 5 万台"),
}
# ---- 单车用量覆盖（没有定点信的项目）----
PERCAR = {
    "BS5PR": {"__all__": 6},
    "ZH5EM": {"__all__": 1},
    "LEV1": {"__all__": 1},
}


def load_dingdian(path):
    """解析定点内部信 → {code: [dict(net,cost,perCar,vol,life,name)]}"""
    if not os.path.exists(path):
        return {}, None
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(min_row=1, max_row=80, max_col=30, values_only=True))
    wb.close()
    hdr = [str(c) if c is not None else "" for c in rows[0]]

    def col(*names):
        for n in names:
            for i, h in enumerate(hdr):
                if n in h:
                    return i
        return None

    ci, cn, cp, cc = col("零件号"), col("零件名称"), col("定点单价"), col("成本")
    cper, cvol, clife = col("单车用量"), col("平均年产量"), col("生命周期")
    out, vols = {}, []
    for r in rows[1:]:
        if not r[ci] or not r[cn]:
            continue
        code = str(r[ci]).strip()
        if not code[:3].isdigit():
            continue
        net = r[cp]
        if net is None:
            continue
        per = r[cper] or 0
        vol = r[cvol] or 0
        if vol:
            vols.append(vol)
        out.setdefault(code, []).append({
            "name": str(r[cn]).strip(), "net": float(net),
            "cost": float(r[cc]) if r[cc] is not None else None,
            "perCar": float(per), "vol": float(vol),
            "life": r[clife] if clife is not None else None,
        })
    vol_main = max(set(vols), key=vols.count) if vols else None
    return out, vol_main


def percar_of(proj, code, name):
    t = PERCAR.get(proj) or {}
    if code in t:
        return t[code], "参数表"
    if "__all__" in t:
        return t["__all__"], "参数表(每件1)"
    for k, v in (("单车2件", 2), ("单车 2 件", 2), ("单车4件", 4), ("单车4 件", 4),
                 ("单车6件", 6), ("单车 6 件", 6)):
        if k in (name or ""):
            return v, "名称注明"
    return 1, "默认1·待确认"


def main():
    P = json.load(open(PJ, encoding="utf-8"))
    dd = {k: load_dingdian(v) for k, v in DINGDIAN.items()}

    out = {"updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "year": 2026, "tax": TAX, "projects": [], "gaps": []}

    for p in P.get("projects") or []:
        name = p.get("name", "")
        parts = p.get("parts") or []
        if not parts:
            continue
        src_map, dd_vol = dd.get(name, ({}, None))
        vol, volnote = VOLUME.get(name, (None, "年产量待补"))
        src_label = "定点信" if src_map else ("项目卡报价" if vol else "待补")
        rows = []
        for pt in parts:
            code = pt.get("code") or ""
            nm = pt.get("name", "")
            if "不生产" in nm:
                rows.append(dict(code=code, name=nm, priceNet=None, perCar=0,
                                 perCarNote="0 不生产", annualQty=0, annualNet=0,
                                 src="—", no=True))
                continue
            hit = None
            if code in src_map and src_map[code]:
                hit = src_map[code].pop(0)          # 同码多次出现时按顺序取
            if hit:
                pnet, pc, pcnote, asrc = hit["net"], hit["perCar"], "定点信", "定点信"
                if not vol and hit["vol"]:
                    vol, volnote = hit["vol"], "定点信 平均年产量"
                cost = hit["cost"]
            else:
                pnet = round(pt["priceTax"] / TAX, 6) if pt.get("priceTax") is not None else None
                pc, pcnote = percar_of(name, code, nm)
                asrc = "项目卡报价" if pnet is not None else "待报价"
                cost = pt.get("cost")
            aq = (pc * vol) if (pc and vol) else None
            anet = round(pnet * aq, 2) if (pnet is not None and aq) else None
            rows.append(dict(code=code, name=nm, priceNet=pnet, cost=cost, perCar=pc,
                             perCarNote=pcnote, annualQty=aq, annualNet=anet,
                             src=asrc, no=False))
            if pnet is None:
                out["gaps"].append({"project": name, "part": nm, "reason": "无报价"})
            elif not vol:
                out["gaps"].append({"project": name, "part": nm, "reason": "年产量待补"})
            elif asrc != "定点信" and pcnote.startswith("默认"):
                out["gaps"].append({"project": name, "part": nm, "reason": "单车用量待确认(暂按1)"})

        tot = sum(r["annualNet"] or 0 for r in rows)
        out["projects"].append({
            "name": name, "customer": p.get("customer", ""), "oem": p.get("oem", ""),
            "status": p.get("status", ""), "volume": vol, "volumeNote": volnote,
            "parts": rows, "annualNet": round(tot, 2),
            "annualTax": round(tot * TAX, 2),
            "annualQty": sum(r["annualQty"] or 0 for r in rows),
            "complete": bool(vol) and all(r["priceNet"] is not None or r["no"] for r in rows),
            "src": src_label,
        })

    out["projects"].sort(key=lambda x: (x["annualNet"] == 0, -x["annualNet"]))
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 注入 forecast.html
    ht = os.path.join(ROOT, "forecast.html")
    if os.path.exists(ht):
        s = open(ht, encoding="utf-8").read()
        import re
        blob = json.dumps(out, ensure_ascii=False, indent=1)
        s2 = re.sub(r"/\*FORECAST_DATA_START\*/.*?/\*FORECAST_DATA_END\*/",
                    "/*FORECAST_DATA_START*/\nconst FORECAST_DATA = " + blob + ";\n/*FORECAST_DATA_END*/",
                    s, count=1, flags=re.S)
        if s2 != s:
            open(ht, "w", encoding="utf-8").write(s2)
            print("✅ forecast.html 数据已注入")
        else:
            print("⚠️ forecast.html 未找到 FORECAST_DATA 块")

    total = sum(p["annualNet"] for p in out["projects"])
    print("销售额预测: %d 项目 / 可测算年销售额(未税) ¥%s / 待补 %d 项"
          % (len(out["projects"]), format(round(total), ","), len(out["gaps"])))
    for p in out["projects"]:
        print("   %-10s %-10s 年产 %-8s 年销售额未税 %12s  %s"
              % (p["name"], p["customer"],
                 format(int(p["volume"]), ",") if p["volume"] else "待补",
                 format(int(p["annualNet"]), ",") if p["annualNet"] else "-", p["src"]))
    return out


if __name__ == "__main__":
    main()
