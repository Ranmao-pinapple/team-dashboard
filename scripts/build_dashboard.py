#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
看板数据自动同步脚本(CI 用)
读 data/*.json → 重新生成 index.html / pull-plan.html / dashboard.html 里的数据块
用户在 GitHub 网页编辑 data/*.json 后，workflow 自动运行本脚本，看板随之更新。
纯标准库，无第三方依赖。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")


def load(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f"⚠️  数据源缺失，跳过: {name}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------- 数据块构建(与 update_dashboard.py 保持一致) ----------

def build_pull_data_js(orders):
    updated_at = orders.get("updatedAt", "未知")
    year = orders.get("year", 2026)
    rows = orders.get("rows", [])
    js_rows = []
    for r in rows:
        daily_parts = []
        for month in sorted(r.get("daily", {}).keys(), key=int):
            daily_parts.append(f"        {month}: {json.dumps(r['daily'][month])}")
        daily_str = "{\n" + ",\n".join(daily_parts) + "\n      }" if daily_parts else "{}"
        actual_parts = []
        for month in sorted(r.get("actual", {}).keys(), key=int):
            actual_parts.append(f"        {month}: {json.dumps(r['actual'][month])}")
        actual_str = "{\n" + ",\n".join(actual_parts) + "\n      }" if actual_parts else "{}"
        js_rows.append(
            '    {\n'
            f'      part: "{r["part"]}",\n'
            f'      project: "{r.get("project", r.get("proj", ""))}",\n'
            f'      proj: "{r.get("proj", "")}",\n'
            f'      status: "{r.get("status", "plan")}",\n'
            f'      makeType: "{r.get("makeType", "")}",\n'
            f'      supplier: "{r.get("supplier", "")}",\n'
            f'      daily: {daily_str},\n'
            f'      actual: {actual_str}\n'
            '    }'
        )
    return (
        "const PULL_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        f'  year: {year},\n'
        "  rows: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


def build_finance_data_js(finance):
    updated_at = finance.get("updatedAt", "未知")
    rows = finance.get("rows", [])
    js_rows = []
    for r in rows:
        details_js = json.dumps(r.get("details", []), ensure_ascii=False)
        js_rows.append(
            '    { '
            f'cust: "{r["cust"]}", proj: "{r.get("proj", "")}", period: "{r.get("period", "")}", '
            f'shipped: {r.get("shipped", 0)}, recon: "{r.get("recon", "pending")}", '
            f'invoiced: {r.get("invoiced", 0)}, invoiceNo: "{r.get("invoiceNo", "")}", '
            f'invoiceDate: "{r.get("invoiceDate", "")}", paid: {r.get("paid", 0)}, '
            f'overdue: {"true" if r.get("overdue") else "false"}, remark: "{r.get("remark", "")}", '
            f'details: {details_js} '
            '}'
        )
    return (
        "const FINANCE_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        "  rows: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


def build_po_data_js(po_data):
    updated_at = po_data.get("updatedAt", "未知")
    orders = po_data.get("orders", [])
    js_rows = []
    for o in orders:
        js_rows.append(
            '    { '
            f'po: "{o.get("po", "")}", date: "{o.get("date", "")}", '
            f'customer: "{o.get("customer", "")}", part: "{o.get("part", "")}", '
            f'partCode: "{o.get("part_code", o.get("partCode", ""))}", spec: "{o.get("spec", "")}", '
            f'makeType: "{o.get("makeType", "")}", supplier: "{o.get("supplier", "")}", '
            f'qty: {o.get("qty", 0)}, unitPrice: {o.get("unit_price_tax", o.get("unitPrice", 0))}, '
            f'total: {o.get("total_tax", o.get("total", 0))}, taxRate: {o.get("tax_rate", o.get("taxRate", 13))}, '
            f'delivery: "{o.get("delivery_sys", o.get("delivery", ""))}", '
            f'payment: "{o.get("payment", "")}", status: "{o.get("status", "received")}", '
            f'remark: "{o.get("delivery_note", o.get("remark", ""))}" '
            '}'
        )
    return (
        "const PO_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        "  orders: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


def build_project_data_js(proj_data):
    updated_at = proj_data.get("updatedAt", "未知")
    projects = proj_data.get("projects", [])
    js_rows = []
    for p in projects:
        phases_js = json.dumps(p.get("phases", []), ensure_ascii=False)
        timeline_js = json.dumps(p.get("timeline", []), ensure_ascii=False)
        parts_js = json.dumps(p.get("parts", []), ensure_ascii=False)
        js_rows.append(
            '    {\n'
            f'      name: "{p.get("name", "")}", customer: "{p.get("customer", "")}", oem: "{p.get("oem", "")}", product: "{p.get("product", "")}",\n'
            f'      status: "{p.get("status", "active")}", rfqDate: "{p.get("rfqDate", "")}", phase: {p.get("phase", 1)},\n'
            f'      nextStep: "{p.get("nextStep", "")}",\n'
            f'      bomFiles: {json.dumps(p.get("bomFiles", []), ensure_ascii=False)},\n'
            f'      phases: {phases_js},\n'
            f'      timeline: {timeline_js},\n'
            f'      parts: {parts_js}\n'
            '    }'
        )
    return (
        "const PROJECT_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        "  projects: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


def build_task_data_js(task_data):
    updated_at = task_data.get("updatedAt", "未知")
    tasks = task_data.get("tasks", [])
    js_rows = []
    for t in tasks:
        js_rows.append(
            '    { '
            f'id: "{t.get("id", "")}", title: "{t.get("title", "")}", '
            f'project: "{t.get("project", "")}", owner: "{t.get("owner", "")}", '
            f'priority: "{t.get("priority", "P3")}", due: "{t.get("due", "")}", '
            f'status: "{t.get("status", "todo")}", remark: "{t.get("remark", "")}" '
            '}'
        )
    return (
        "const TASK_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        "  tasks: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


def build_non2026_data_js(data):
    updated_at = data.get("updatedAt", "未知")
    periods = data.get("periods", [])
    js_periods = []
    for per in periods:
        rows = per.get("rows", [])
        totals = per.get("totals", {})
        js_rows = []
        for r in rows:
            js_rows.append(
                '      { '
                f'cust: "{r.get("cust", "")}", code: "{r.get("code", "")}", '
                f'part: "{r.get("part", "")}", spec: "{r.get("spec", "")}", '
                f'price: {r.get("price", 0)}, qty6: {r.get("qty6", 0)}, '
                f'rev6: {r.get("rev6", 0)}, qty7: {r.get("qty7", 0)}, '
                f'amt7: {r.get("amt7", 0)}, diffQty: {r.get("diffQty", 0)}, '
                f'diffAmt: {r.get("diffAmt", 0)} '
                '}'
            )
        totals_js = "{" + ", ".join(f'{k}: {v}' for k, v in totals.items()) + "}"
        js_periods.append(
            '    {\n'
            f'      id: "{per.get("id", "")}", label: "{per.get("label", "")}",\n'
            f'      note: "{per.get("note", "")}",\n'
            "      totals: " + totals_js + ",\n"
            "      rows: [\n" + ",\n".join(js_rows) + "\n      ]\n"
            "    }"
        )
    return (
        "const NON2026_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        f'  customer: "{data.get("customer", "")}",\n'
        f'  module: "{data.get("module", "")}",\n'
        "  periods: [\n" + ",\n".join(js_periods) + "\n  ]\n"
        "};"
    )


def build_sample_data_js(data):
    updated_at = data.get("updatedAt", "未知")
    rows = data.get("rows", [])
    js_rows = []
    for r in rows:
        js_rows.append(
            '    { '
            f'project: "{r.get("project", "")}", customer: "{r.get("customer", "")}", '
            f'part: "{r.get("part", "")}", qty: {r.get("qty", 0)}, '
            f'makeType: "{r.get("makeType", "")}", supplier: "{r.get("supplier", "")}", '
            f'stage: "{r.get("stage", "")}", planDate: "{r.get("planDate", "")}", '
            f'sendDate: "{r.get("sendDate", "")}", remark: "{r.get("remark", "")}" '
            "}"
        )
    return (
        "const SAMPLE_DATA = {\n"
        f'  updatedAt: "{updated_at}",\n'
        "  rows: [\n" + ",\n".join(js_rows) + "\n  ]\n"
        "};"
    )


# ---------- 主流程 ----------

def replace_block(html, name, new_block):
    """把 html 里的 const <name> = {...}; 替换为新块；返回 (新html, 是否变化)"""
    pattern = re.compile(rf"const {name} = \{{.*?\n\}};", re.DOTALL)
    if not pattern.search(html):
        print(f"  ⚠️ {name} 块在文件中不存在，跳过")
        return html, False
    new_html = pattern.sub(new_block, html)
    return new_html, new_html != html


def update_file(html_path, blocks):
    """blocks: {block_name: data_dict}"""
    path = os.path.join(ROOT, html_path)
    if not os.path.exists(path):
        print(f"  ⚠️ {html_path} 不存在，跳过")
        return False
    with open(path, encoding="utf-8") as f:
        html = f.read()
    changed = False
    for name, data in blocks.items():
        builder = BUILDERS.get(name)
        if not builder or data is None:
            continue
        new_block = builder(data)
        html, c = replace_block(html, name, new_block)
        changed = changed or c
    if changed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  ✅ {html_path} 已更新")
    else:
        print(f"  —  {html_path} 无变化")
    return changed


BUILDERS = {
    "PULL_DATA": build_pull_data_js,
    "PO_DATA": build_po_data_js,
    "FINANCE_DATA": build_finance_data_js,
    "PROJECT_DATA": build_project_data_js,
    "TASK_DATA": build_task_data_js,
    "NON2026_DATA": build_non2026_data_js,
    "SAMPLE_DATA": build_sample_data_js,
}

SOURCES = {
    "PULL_DATA": "orders.json",
    "PO_DATA": "orders_data.json",
    "FINANCE_DATA": "finance.json",
    "PROJECT_DATA": "projects.json",
    "TASK_DATA": "tasks.json",
    "NON2026_DATA": "non2026.json",
    "SAMPLE_DATA": "sample_plan.json",
}


def main():
    data = {}
    for block_name, src in SOURCES.items():
        d = load(src)
        if d is not None:
            data[block_name] = d

    print("=== 同步看板数据 ===")
    update_file("index.html", data)
    update_file("pull-plan.html", {
        "PULL_DATA": data.get("PULL_DATA"),
        "PROJECT_DATA": data.get("PROJECT_DATA"),
    })
    update_file("dashboard.html", {
        "PULL_DATA": data.get("PULL_DATA"),
        "PROJECT_DATA": data.get("PROJECT_DATA"),
    })
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
