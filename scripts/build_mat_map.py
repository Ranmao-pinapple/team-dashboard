#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总 零件名→物料号(51开头) 映射，输出 data/part_mat.json，并检查对 orders.json 的覆盖率"""
import json, re, openpyxl

BASE = '/root/.hermes/scripts/dashboard/data'
orders = json.load(open(f'{BASE}/orders.json'))
od = json.load(open(f'{BASE}/orders_data.json'))


def norm(s):
    s = (s or '').strip()
    for ch in [' ', '-', '_', '(', ')', '（', '）', '·', '×', '*', '/', '\u3000']:
        s = s.replace(ch, '')
    return s.lower()


pairs = []
for o in od['orders']:
    if o.get('part') and o.get('part_code'):
        pairs.append((o['part'], o['part_code']))

XLSX = [
    '/mnt/c/Users/Administrator/Desktop/常州臻畅零件清单_20261101.xlsx',
    '/mnt/c/Users/Administrator/Desktop/凯华订单/常州臻畅零件清单_已补零件名_20260915（标注合同）.xlsx',
]
for xl in XLSX:
    try:
        wb = openpyxl.load_workbook(xl, read_only=True, data_only=True)
    except Exception as e:
        print('跳过', xl, e)
        continue
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            vals = [('' if c is None else str(c).strip()) for c in row]
            for i, v in enumerate(vals):
                if re.fullmatch(r'5100\d{10,}', v):
                    nm = ''
                    for j in range(i - 1, max(i - 4, -1), -1):
                        if vals[j] and not re.fullmatch(r'[\d\.]+', vals[j]):
                            nm = vals[j]
                            break
                    if nm:
                        pairs.append((nm, v))
                    break
    print(xl.split('/')[-1], 'ok')

print('候选项', len(pairs))

m = {}      # 归一化键 → 物料号
exact = {}  # 原始零件名 → 物料号
for nm, code in pairs:
    exact.setdefault(nm, code)
    m.setdefault(norm(nm), code)

# 覆盖率
rows = orders['rows']
hit = 0
misslist = []
for r in rows:
    p = r['part'].strip()
    i = p.rfind(' ')
    nm = p[:i] if i > 0 else p
    code = exact.get(nm) or m.get(norm(nm))
    if not code:
        n = norm(nm)
        best = None
        for k, v in m.items():
            if k and (k.startswith(n) or n in k):
                best = v
                break
        code = best
    if code:
        hit += 1
    else:
        misslist.append(nm)

print(f'覆盖 {hit}/{len(rows)}  缺 {len(misslist)}')
for x in misslist:
    print('   缺:', x)

out = {'updatedAt': '2026-11-03', 'exact': exact, 'norm': m}

# 手工补充：xlsx 里没带出、但已确认的 图号→物料号（从凯华零件资料/计划表核对）
MANUAL = {
    'VFe32防水海绵22×10.5×6mm': '510000000000011006',
    'VFe32防水海绵-侧裙（凯华9000工厂）': '510000000000011011',
    'VFe32防水海绵-侧裙（凯华济南工厂）': '510000000000011011',
    'BC03-吹面风隔音棉': '510000000000015797',
    'VFe32堵块（左）下方3M胶45.2x127.8x8': '510000000000011039',
    'VFe32堵块（右）下方3M胶45.2x127.8x8': '510000000000011040',
}
for k, v in MANUAL.items():
    out['exact'].setdefault(k, v)
    out['norm'].setdefault(norm(k), v)

json.dump(out, open(f'{BASE}/part_mat.json', 'w'), ensure_ascii=False, indent=1)
print('写出', f'{BASE}/part_mat.json', 'exact', len(out['exact']), 'norm', len(out['norm']))
