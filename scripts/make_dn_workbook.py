#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「发货单」Excel 版（每供应商一个 xlsx）

结构:
  填单            —— 固定信息 + 零件表，只在黄色格填「本次发货数量」
  发货单-凯华9000  —— 公式自动带出本次要发的件，直接打印
  发货单-凯华济南  —— 同上

原理: 填单!J/K 两个隐藏辅助列给每个工厂的发货行编号，发货单页用 MATCH 取行号再 INDEX，
纯普通公式(非数组、非宏)，Excel 2010+/WPS 全兼容。
"""
import json, re, sys
from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BASE = '/root/.hermes/scripts/dashboard'

SENDER = ('常州臻畅汽车配件有限公司', '曹旭锋 13671667491')
PLANTS = {
    '凯华9000工厂': ('浙江凯华汽车科技有限公司', '浙江省台州市三门县兴港大道7号', '李星星 19332067820'),
    '凯华济南工厂': ('浙江靖凯模塑科技有限公司济南分公司',
                '山东省济南市济阳区同德街6号少海汇科创绿建产业园五号厂房三号门', '马子航 19861918606'),
}
PAGES = [
    ('宁波互盛', 'supplier-husheng.html'),
    ('江苏诚丰', 'supplier-chengfeng.html'),
    ('新久玥', 'supplier-xinjiuyue.html'),
    ('上海泰瑞', 'pull-plan-tairui.html'),
]

RED = 'E82127'
DARK = '1F2733'
GREY_H = 'EEF1F5'
YELLOW = 'FFF6D6'
BORDER = Border(*[Side(style='thin', color='BFC5CC')] * 4)


def parse_page(fn):
    html = open(f'{BASE}/{fn}', encoding='utf-8').read()
    m = re.search(r'const DATA = (\[.*?\]);\n', html, re.S)
    if not m:
        return []
    rows = json.loads(m.group(1))
    out = []
    for r in rows:
        part = r['part']
        i = part.rfind(' ')
        name, code = (part[:i], part[i + 1:]) if i > 0 else (part, '')
        plant = '凯华济南工厂' if '济南' in name else '凯华9000工厂'
        out.append({'name': name, 'code': code, 'mat': r.get('mat') or code,
                    'plant': plant, 'daily': r.get('daily') or {}})
    return out


def week_plan(daily, d0, d1):
    s, d = 0, d0
    while d <= d1:
        arr = daily.get(str(d.month)) or []
        if d.day - 1 < len(arr):
            s += arr[d.day - 1] or 0
        d += timedelta(days=1)
    return s


def title_block(ws, text, sub, ncol):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(name='微软雅黑', size=15, bold=True, color='FFFFFF')
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)
    for col in range(1, ncol + 1):
        ws.cell(row=1, column=col).fill = PatternFill('solid', fgColor=DARK)
    ws.row_dimensions[1].height = 34
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
    c = ws.cell(row=2, column=1, value=sub)
    c.font = Font(name='微软雅黑', size=10, color='7A8794')
    c.alignment = Alignment(horizontal='left', vertical='center', indent=1)


def build(supplier, rows, out_path):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    for r in rows:
        r['plan'] = week_plan(r['daily'], monday, sunday)

    wb = Workbook()
    # ---------- 填单 ----------
    ws = wb.active
    ws.title = '填单'
    ws.sheet_properties.tabColor = RED
    NC = 7
    title_block(ws, f'发货单填单表 · {supplier}',
                f'本周 {monday:%Y-%m-%d} ~ {sunday:%Y-%m-%d}　｜　只在黄色格里填「本次发货数量」，其余不用动 → 点下面标签页「发货单-xxx」直接打印', NC)

    ws['A4'] = '发货单位'
    ws['B4'] = SENDER[0]
    ws.merge_cells('B4:D4')
    ws['E4'] = '发货联系人/电话'
    ws['F4'] = SENDER[1]
    ws.merge_cells('F4:G4')
    ws['A5'] = '发货日期'
    ws['B5'] = today
    ws['B5'].number_format = 'yyyy-mm-dd'
    ws.merge_cells('B5:D5')
    ws['E5'] = '单号'
    ws['F5'] = '=$B$6&"-"&TEXT($B$5,"yyyymmdd")&"-"&TEXT($F$6,"00")'
    ws.merge_cells('F5:G5')
    ws['A6'] = '单号前缀'
    ws['B6'] = 'ZC'
    ws['E6'] = '当日序号'
    ws['F6'] = 1
    ws['A7'] = '备注说明'
    ws['B7'] = '同一天发第 2 车请把「当日序号」改成 2（可顺手改单号前缀区分）'
    ws.merge_cells('B7:G7')
    for cell in ('A4', 'E4', 'A5', 'E5', 'A6', 'E6', 'A7'):
        ws[cell].font = Font(name='微软雅黑', size=10, bold=True, color='555566')
    for cell in ('B4', 'F4', 'B5', 'F5', 'B6', 'F6', 'B7'):
        ws[cell].font = Font(name='微软雅黑', size=10)
    ws['F5'].font = Font(name='Consolas', size=10, bold=True, color='C02020')
    ws['F6'].fill = PatternFill('solid', fgColor=YELLOW)
    ws['B5'].fill = PatternFill('solid', fgColor=YELLOW)

    # 表头
    HDR = ['序号', '物料号', '零件名称', '收货工厂', '本周计划', '本次发货数量', '备注']
    hr = 9
    for i, h in enumerate(HDR, 1):
        c = ws.cell(row=hr, column=i, value=h)
        c.font = Font(name='微软雅黑', size=10, bold=True, color='334155')
        c.fill = PatternFill('solid', fgColor=GREY_H)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[hr].height = 26

    r0 = hr + 1
    for k, r in enumerate(rows):
        rr = r0 + k
        ws.cell(row=rr, column=1, value=k + 1)
        ws.cell(row=rr, column=2, value=r['mat'])
        ws.cell(row=rr, column=3, value=r['name'])
        ws.cell(row=rr, column=4, value=r['plant'])
        ws.cell(row=rr, column=5, value=r['plan'])
        ws.cell(row=rr, column=6, value=None)
        ws.cell(row=rr, column=7, value=None)
        for col in range(1, 8):
            c = ws.cell(row=rr, column=col)
            c.border = BORDER
            c.font = Font(name='微软雅黑', size=9.5,
                          color='8A8F98' if col in (2, 4) else '222222')
            c.alignment = Alignment(horizontal='left' if col in (2, 3, 7) else 'center',
                                    vertical='center')
        ws.cell(row=rr, column=5).number_format = '#,##0'
        q = ws.cell(row=rr, column=6)
        q.fill = PatternFill('solid', fgColor=YELLOW)
        q.font = Font(name='微软雅黑', size=10, bold=True, color='B45309')
        q.number_format = '#,##0'
        ws.row_dimensions[rr].height = 20
    last = r0 + len(rows) - 1

    dv = DataValidation(type='whole', operator='greaterThanOrEqual', formula1='0', allow_blank=True,
                        error='只能填 0 或正整数', errorTitle='数量格式')
    ws.add_data_validation(dv)
    dv.add(f'F{r0}:F{last}')

    # 辅助列(隐藏): J=9000序 K=济南序
    ws['J8'] = '9000序'
    ws['K8'] = '济南序'
    for k in range(len(rows)):
        rr = r0 + k
        for col, plant in ((10, '凯华9000工厂'), (11, '凯华济南工厂')):
            L = get_column_letter(col)
            ws[f'{L}{rr}'] = (f'=IF(AND($D{rr}="{plant}",N($F{rr})>0),'
                              f'COUNTIFS($D${r0}:$D{rr},"{plant}",$F${r0}:$F{rr},">0"),"")')
        ws.row_dimensions[rr].height = 20
    ws.column_dimensions['J'].hidden = True
    ws.column_dimensions['K'].hidden = True

    # 合计
    tr = last + 2
    ws.merge_cells(start_row=tr, start_column=1, end_row=tr, end_column=4)
    c = ws.cell(row=tr, column=1, value='合计（本次发货）')
    c.font = Font(name='微软雅黑', size=10, bold=True)
    c.alignment = Alignment(horizontal='right', vertical='center')
    c1 = ws.cell(row=tr, column=5, value='=SUM(E%d:E%d)' % (r0, last))
    c1.number_format = '#,##0'
    c1.alignment = Alignment(horizontal='center')
    c1.font = Font(name='微软雅黑', size=10, color='555566')
    c2 = ws.cell(row=tr, column=6, value='=SUM(F%d:F%d)' % (r0, last))
    c2.font = Font(name='微软雅黑', size=11, bold=True, color='C02020')
    c2.alignment = Alignment(horizontal='center')
    c2.number_format = '#,##0'
    for col in range(1, 7):
        ws.cell(row=tr, column=col).fill = PatternFill('solid', fgColor=GREY_H)
        ws.cell(row=tr, column=col).border = BORDER

    widths = {'A': 6, 'B': 20, 'C': 44, 'D': 16, 'E': 11, 'F': 14, 'G': 18}
    for k, v in widths.items():
        ws.column_dimensions[k].width = v
    ws.freeze_panes = f'A{r0}'

    # ---------- 发货单 ----------
    for plant, meta in PLANTS.items():
        ws2 = wb.create_sheet('发货单-' + plant.replace('工厂', ''))
        helper_col = 10 if plant == '凯华9000工厂' else 11
        HC = get_column_letter(helper_col)
        nrows = max(6, sum(1 for r in rows if r['plant'] == plant) + 2)

        for col in range(1, 8):
            ws2.column_dimensions[get_column_letter(col)].width = [6, 20, 44, 8, 12, 18, 3][col - 1]

        ws2.merge_cells('A1:F1')
        c = ws2['A1']
        c.value = '发  货  单'
        c.font = Font(name='微软雅黑', size=20, bold=True, color=DARK)
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws2.row_dimensions[1].height = 34
        ws2.merge_cells('A2:F2')
        c = ws2['A2']
        c.value = 'D E L I V E R Y   N O T E'
        c.font = Font(name='Arial', size=9, color='8A8F98')
        c.alignment = Alignment(horizontal='center')

        info = [
            ('单号：', "=填单!$F$5"),
            ('发货日期：', "=填单!$B$5"),
            ('发货单位：', SENDER[0]),
            ('收货单位：', meta[0]),
            ('发货联系人/电话：', SENDER[1]),
            ('收货联系人/电话：', meta[2]),
            ('收货地址：', meta[1] + f'（{plant}）'),
        ]
        r = 4
        for a, b in info:
            ws2.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            c = ws2.cell(row=r, column=1, value=a)
            c.font = Font(name='微软雅黑', size=10, bold=True)
            c.alignment = Alignment(horizontal='left', vertical='center')
            ws2.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
            v = ws2.cell(row=r, column=3, value=b)
            v.font = Font(name='微软雅黑', size=10)
            v.alignment = Alignment(horizontal='left', vertical='center')
            ws2.row_dimensions[r].height = 19
            r += 1
        ws2['C5'].number_format = 'yyyy-mm-dd'
        ws2['C4'].font = Font(name='Consolas', size=10, bold=True, color='C02020')

        hdr = 12
        for i, h in enumerate(['序号', '物料号', '零件名称', '单位', '数量', '备注'], 1):
            c = ws2.cell(row=hdr, column=i, value=h)
            c.font = Font(name='微软雅黑', size=10, bold=True)
            c.fill = PatternFill('solid', fgColor='F2F2F2')
            c.alignment = Alignment(horizontal='center', vertical='center')
            c.border = Border(*[Side(style='thin', color='333333')] * 4)
        ws2.row_dimensions[hdr].height = 24

        r0 = 10          # 填单第一行零件
        r_end = last + 2  # 留 2 行余量
        for k in range(nrows):
            rr = hdr + 1 + k
            ws2.cell(row=rr, column=7,
                     value=f'=IFERROR(MATCH({k+1},填单!${HC}${r0}:${HC}${r_end},0),"")')
            ws2[f'G{rr}'].font = Font(color='FFFFFF')
            for col, formula in (
                (1, f'=IF($G{rr}="","",{k+1})'),
                (2, f'=IF($G{rr}="","",INDEX(填单!$B${r0}:$B${r_end},$G{rr}))'),
                (3, f'=IF($G{rr}="","",INDEX(填单!$C${r0}:$C${r_end},$G{rr}))'),
                (4, f'=IF($G{rr}="","","件")'),
                (5, f'=IF($G{rr}="","",INDEX(填单!$F${r0}:$F${r_end},$G{rr}))'),
                (6, f'=IF($G{rr}="","",IF(INDEX(填单!$G${r0}:$G${r_end},$G{rr})=0,"",INDEX(填单!$G${r0}:$G${r_end},$G{rr})))'),
            ):
                c = ws2.cell(row=rr, column=col, value=formula)
                c.border = Border(*[Side(style='thin', color='333333')] * 4)
                c.font = Font(name='微软雅黑', size=10)
                c.alignment = Alignment(horizontal='left' if col in (2, 3, 6) else 'center',
                                        vertical='center')
            ws2.cell(row=rr, column=2).font = Font(name='Consolas', size=9.5)
            ws2.cell(row=rr, column=5).font = Font(name='微软雅黑', size=10, bold=True)
            ws2.cell(row=rr, column=5).number_format = '#,##0'
            ws2.row_dimensions[rr].height = 21
        ws2.column_dimensions['G'].hidden = True

        tot = hdr + nrows + 1
        ws2.merge_cells(start_row=tot, start_column=1, end_row=tot, end_column=4)
        c = ws2.cell(row=tot, column=1, value='合计')
        c.font = Font(name='微软雅黑', size=10, bold=True)
        c.alignment = Alignment(horizontal='right', vertical='center')
        c2 = ws2.cell(row=tot, column=5, value=f'=SUM(E{hdr+1}:E{hdr+nrows})')
        c2.font = Font(name='微软雅黑', size=11, bold=True)
        c2.number_format = '#,##0'
        for col in range(1, 7):
            ws2.cell(row=tot, column=col).border = Border(*[Side(style='thin', color='333333')] * 4)
            ws2.cell(row=tot, column=col).fill = PatternFill('solid', fgColor='F2F2F2')

        s = tot + 3
        for txt, c0, c1 in (('发货人（签字/盖章）：', 1, 2), ('收货人（签字/盖章）：', 4, 6)):
            ws2.merge_cells(start_row=s, start_column=c0, end_row=s, end_column=c1)
            c = ws2.cell(row=s, column=c0, value=txt)
            c.font = Font(name='微软雅黑', size=10)
            c.border = Border(bottom=Side(style='thin', color='333333'))
        ws2.merge_cells(start_row=s + 2, start_column=1, end_row=s + 2, end_column=6)
        c = ws2.cell(row=s + 2, column=1,
                     value='本单由「填单」页自动生成：黄色格填多少，这里就带多少；没有发货的零件不会出现在单上。')
        c.font = Font(name='微软雅黑', size=8.5, color='8A8F98')
        c.alignment = Alignment(horizontal='center')

        ws2.print_area = f'A1:F{s+2}'
        ws2.page_setup.orientation = 'portrait'
        ws2.page_setup.paperSize = ws2.PAPERSIZE_A4
        ws2.sheet_properties.pageSetUpPr.fitToPage = True
        ws2.page_setup.fitToWidth = 1
        ws2.page_setup.fitToHeight = 1
        ws2.page_margins.left = ws2.page_margins.right = 0.55
        ws2.page_margins.top = 0.6
        ws2.page_margins.bottom = 0.5

    ws.print_area = f'A1:G{tr}'
    ws.page_setup.orientation = 'landscape'
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    wb.active = 0
    wb.save(out_path)
    return out_path


if __name__ == '__main__':
    outs = []
    for sup, fn in PAGES:
        rows = parse_page(fn)
        if not rows:
            print('!! 无数据:', sup, file=sys.stderr)
            continue
        out = f'{BASE}/files/发货单-{sup}.xlsx'
        build(sup, rows, out)
        outs.append((sup, out, len(rows)))
        print(f'{sup}: {len(rows)} 个零件 → {out}')
