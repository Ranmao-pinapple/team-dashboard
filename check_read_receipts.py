#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外协月拉动计划 · 已读回执监控
外协厂在 supplier 页点"一键回执"→ 发【外协确认】邮件到 xufeng_cao@zhenchang.group
本脚本每天查一次收件箱: 有新回执→stdout 输出提醒(no_agent 直接投递); 无→静默。
去重: 记录已提醒过的 Message-ID 到状态文件。"""
import imaplib, email, re, json, os, sys
from email.header import decode_header
from datetime import datetime, timedelta

HOST = 'imaphz.qiye.163.com'
USER = 'xufeng_cao@zhenchang.group'
AUTH_FILE = '/mnt/c/Users/Administrator/Desktop/模切资料/授权码.txt'
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.read_receipts_seen.json')

def dec(s):
    if not s:
        return ''
    out = []
    for t, enc in decode_header(s):
        if isinstance(t, bytes):
            try:
                out.append(t.decode(enc or 'utf-8', 'replace'))
            except Exception:
                out.append(t.decode('utf-8', 'replace'))
        else:
            out.append(t)
    return ''.join(out)

def main():
    auth = open(AUTH_FILE).read().strip()
    seen = set()
    if os.path.exists(STATE):
        try:
            seen = set(json.load(open(STATE)))
        except Exception:
            seen = set()
    M = imaplib.IMAP4_SSL(HOST, 993)
    M.login(USER, auth)
    M.select('INBOX')
    since = (datetime.now() - timedelta(days=3)).strftime('%d-%b-%Y')
    typ, data = M.search(None, '(SINCE "%s")' % since)
    hits = []
    if typ == 'OK' and data and data[0]:
        for num in data[0].split():
            typ2, d2 = M.fetch(num, '(BODY.PEEK[HEADER])')
            if typ2 != 'OK' or not d2 or not d2[0]:
                continue
            hdr = d2[0][1]
            try:
                msg = email.message_from_bytes(hdr)
            except Exception:
                continue
            subj = dec(msg.get('Subject', ''))
            if '外协确认' not in subj and '外协发货' not in subj:
                continue
            mid = msg.get('Message-ID', num.decode())
            if mid in seen:
                continue
            if '外协确认' in subj:
                m = re.search(r'【外协确认】(.+?)\s*(能按期完成|无法按期完成|已收到)\s*(\d+)月拉动计划', subj)
                if m:
                    supplier, status_, month = m.group(1).strip(), m.group(2), m.group(3)
                else:
                    supplier, status_, month = subj, '已收到', '?'
                hits.append({'mid': mid, 'kind': 'confirm', 'supplier': supplier, 'status': status_,
                             'month': month, 'date': msg.get('Date', '')})
            else:
                # 上周发货情况填报: 取正文里的 计划/实际/达成率
                info = {}
                atts = []
                try:
                    typ3, d3 = M.fetch(num, '(BODY.PEEK[])')
                    full = email.message_from_bytes(d3[0][1])
                    body = ''
                    if full.is_multipart():
                        for part in full.walk():
                            if part.get_content_type() == 'text/plain':
                                body += (part.get_payload(decode=True) or b'').decode('utf-8', 'replace')
                    else:
                        body = (full.get_payload(decode=True) or b'').decode('utf-8', 'replace')
                    # 保存附件(签收单等)
                    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'files', 'receipts')
                    for part in full.walk():
                        fn = dec(part.get_filename())
                        if not fn:
                            continue
                        data = part.get_payload(decode=True) or b''
                        if not data:
                            continue
                        os.makedirs(outdir, exist_ok=True)
                        safe = re.sub(r'[^\w.\-]+', '_', fn)
                        path = os.path.join(outdir, datetime.now().strftime('%Y%m%d') + '_' + safe)
                        with open(path, 'wb') as fo:
                            fo.write(data)
                        atts.append((fn, len(data), path))
                    for key, pat in (('plan', r'计划总量：([\d,]+)'), ('actual', r'实际发货：([\d,]+)'),
                                     ('rate', r'达成率：([\d.]+)%'), ('unfilled', r'未填零件：(\d+)')):
                        mm = re.search(pat, body)
                        if mm:
                            info[key] = mm.group(1)
                except Exception:
                    pass
                m2 = re.search(r'【外协发货】(.+?)\s*(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})', subj)
                hits.append({'mid': mid, 'kind': 'ship', 'supplier': (m2.group(1).strip() if m2 else subj),
                             'week': (m2.group(2) if m2 else '?'), 'info': info, 'atts': atts,
                             'date': msg.get('Date', '')})
    M.logout()
    # 更新状态(仅记录本次确认命中的)
    for h in hits:
        seen.add(h['mid'])
    try:
        json.dump(sorted(seen), open(STATE, 'w'))
    except Exception:
        pass
    if hits:
        print('📬 外协反馈 · 新收到:')
        for h in hits:
            if h.get('kind') == 'ship':
                i = h.get('info') or {}
                if i:
                    print(f"📦 {h['supplier']} 上周发货填报（{h['week']}）：计划 {i.get('plan','?')} 件 / 实际 {i.get('actual','?')} 件 · 达成率 {i.get('rate','?')}% · 未填 {i.get('unfilled','?')} 个（{h['date']}）")
                else:
                    print(f"📦 {h['supplier']} 上周发货填报（{h['week']}）— 请到邮箱看明细（{h['date']}）")
                for fn, sz, path in (h.get('atts') or []):
                    print(f"   📎 签收单附件已存: {fn}（{round(sz/1024)}KB）→ {path}")
                continue
            if h['status'] == '无法按期完成':
                print(f"⚠️ {h['supplier']} 反馈【无法按期完成】{h['month']}月拉动计划 —— 需重点跟进（{h['date']}）")
            elif h['status'] == '能按期完成':
                print(f"✅ {h['supplier']} 反馈【能按期完成】{h['month']}月拉动计划（{h['date']}）")
            else:
                print(f"✅ {h['supplier']} 已收到 {h['month']}月拉动计划（{h['date']}）")
        print('— 邮件正文含原因/实际可完成量/预计完成日期，可去收件箱查看')
    # 无新回执 → 静默(不输出)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # 出错时报错,让 cron 知道监控坏了
        print(f'⚠️ 已读回执监控异常: {e}', file=sys.stderr)
        sys.exit(1)
