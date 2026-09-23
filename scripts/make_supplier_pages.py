#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成外协工厂月拉动计划网页 (宁波互盛/江苏诚丰) — CI 仓库内版本, 读 data/orders.json 本地生成"""
import json, os, datetime

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# ---------- 读取数据 ----------
orders = json.load(open(f"{BASE}/orders.json"))
YEAR = orders.get("year", 2026)
MONTHS = ["6", "7", "8", "9"]
MONTH_NAMES = {"6": "6月", "7": "7月", "8": "8月", "9": "9月"}

def supplier_rows(supplier):
    return [r for r in orders["rows"] if r.get("supplier") == supplier and r.get("makeType") == "外协"]

HUSHENG = supplier_rows("宁波互盛")
CHENGFENG = supplier_rows("江苏诚丰")
# 自制件（上海泰瑞生产）→ 内部生产计划用页面, 与外协页同款表格但不带外协反馈区
TAIRUI = [r for r in orders["rows"] if r.get("makeType") == "自制"]

# ---------- HTML 模板 ----------
TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>月拉动计划 · {supplier}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f5f6f8; color:#171a20; padding:20px; }}
  .wrap {{ max-width:1280px; margin:0 auto; background:#fff; border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.06); padding:24px; }}
  .head {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #e82127; padding-bottom:14px; margin-bottom:16px; }}
  h1 {{ font-size:20px; color:#171a20; }}
  h1 span {{ color:#e82127; }}
  .meta {{ font-size:12px; color:#8a8f98; }}
  .month-bar {{ display:flex; gap:8px; margin-bottom:14px; }}
  .month-bar button {{ padding:6px 18px; border:1px solid #d8dbe0; background:#fff; border-radius:8px; cursor:pointer; font-size:13px; }}
  .month-bar button.active {{ background:#e82127; color:#fff; border-color:#e82127; font-weight:700; }}
  .sum-line {{ font-size:13px; color:#555; margin-bottom:10px; }}
  .sum-line b {{ color:#e82127; font-size:16px; }}
  table {{ width:100%; border-collapse:collapse; font-size:11.5px; }}
  th, td {{ border:1px solid #e4e6ea; padding:4px 2px; text-align:center; white-space:nowrap; }}
  th {{ background:#f0f2f5; font-weight:600; position:sticky; top:0; }}
  td.part {{ text-align:left; min-width:220px; padding-left:8px; font-weight:600; background:#fff; position:sticky; left:0; }}
  tr.total-row td {{ background:#fff3cd; font-weight:700; }}
  td.weekend {{ background:#faf3f0; }}
  td.zero {{ color:#c8cbd0; }}
  .foot {{ margin-top:14px; font-size:11px; color:#8a8f98; text-align:right; }}
  @media print {{ body {{ padding:0; background:#fff; }} .wrap {{ box-shadow:none; border-radius:0; }} .month-bar {{ display:none; }} }}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <h1>📋 月拉动计划 · <span>{supplier}</span></h1>
    <div class="meta">臻畅/泰瑞 · 销售四部 &nbsp;|&nbsp; 数据更新：{updated}</div>
  </div>
  <div class="month-bar" id="monthBar"></div>
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:12px">
    <button id="confirmBtn" onclick="openConfirm()" style="background:#e82127;color:#fff;border:none;border-radius:8px;padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer;box-shadow:0 2px 6px rgba(232,33,39,.3)">✅ 能按期完成 · 可执行拉动</button>
    <button id="delayBtn" onclick="openDelay()" style="background:#fff;color:#b45309;border:1px solid #f0c36d;border-radius:8px;padding:10px 22px;font-size:14px;font-weight:700;cursor:pointer">⚠️ 无法按期完成 · 反馈交期</button>
    <button onclick="window.print()" style="background:#fff;color:#334155;border:1px solid #d6dae0;border-radius:8px;padding:10px 18px;font-size:14px;font-weight:700;cursor:pointer">🖨 打印 / 存PDF</button>
    <span id="confirmState" style="font-size:12px;color:#8a8f98"></span>
  </div>
  <div class="sum-line" id="sumLine"></div>
  <div style="overflow-x:auto"><table id="pt"><thead id="ptHead"></thead><tbody id="ptBody"></tbody></table></div>
  <div style="margin-top:18px;border:1px solid #f0d9a8;border-radius:10px;padding:12px 14px;background:#fffdf7">
    <h2 id="shipTitle" style="font-size:15px;margin:0 0 4px;color:#b45309">📦 上周发货情况填报</h2>
    <div style="font-size:12px;color:#8a8f98;margin-bottom:8px">请填写上周<b>实际发货件数</b>；缺货/延期的在备注里写明原因与预计发货日。填完点「提交」，邮件会自动带好。</div>
    <div id="shipBox" style="overflow-x:auto"></div>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px">
      <button onclick="submitShip()" style="background:#e82127;color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:14px;font-weight:700;cursor:pointer">📤 提交上周发货情况</button>
      <button onclick="copyShip()" style="background:#fff;color:#334155;border:1px solid #d6dae0;border-radius:8px;padding:9px 18px;font-size:13px;cursor:pointer">📋 复制表格</button>
      <span id="shipState" style="font-size:12px;color:#8a8f98"></span>
    </div>
    <div style="margin-top:12px;padding-top:10px;border-top:1px dashed #f0d9a8">
      <div style="font-size:13px;font-weight:700;color:#b45309;margin-bottom:6px">📎 签收单上传</div>
      <div style="font-size:12px;color:#8a8f98;margin-bottom:8px">选好上周签收单（照片可多张 / PDF）→ 手机端点「📤 发送到微信/邮箱」直接发我们；电脑端点「⬇️ 下载」后拖进微信。也可直接发到 <b>xufeng_cao@zhenchang.group</b>（邮件可带附件）。照片会自动压缩，不影响看清。</div>
      <input id="podFiles" type="file" accept="image/*,application/pdf" multiple onchange="onPodPick(event)" style="font-size:12px">
      <div id="podList" style="font-size:12px;color:#334155;margin-top:6px;line-height:1.7"></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px">
        <button onclick="sharePod()" style="background:#16a34a;color:#fff;border:none;border-radius:8px;padding:8px 16px;font-size:13px;font-weight:700;cursor:pointer">📤 发送到微信/邮箱</button>
        <button onclick="downloadPod()" style="background:#fff;color:#334155;border:1px solid #d6dae0;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer">⬇️ 下载签收单</button>
        <button onclick="copyMail()" style="background:#fff;color:#334155;border:1px solid #d6dae0;border-radius:8px;padding:8px 16px;font-size:13px;cursor:pointer">📧 复制我们的邮箱</button>
        <span id="podState" style="font-size:12px;color:#8a8f98"></span>
      </div>
    </div>
  </div>
  <div class="foot">※ 数量单位：件（pcs）· 按客户拉动计划排产，如有变动以最新通知为准</div>
</div>
<script>
const SUPPLIER = {supplier_json};
const DATA = {rows_json};
const YEAR = {year};
const MONTHS = {months_json};
const MONTH_NAMES = {month_names_json};
let curMonth = '9';
const dim = m => new Date(YEAR, parseInt(m), 0).getDate();
const fmt = n => (n||0).toLocaleString();
document.getElementById('monthBar').innerHTML = MONTHS.map(m =>
  `<button class="${{m===curMonth?'active':''}}" onclick="switchM('${{m}}')">${{MONTH_NAMES[m]}}</button>`).join('');
function switchM(m) {{ curMonth = m; render(); }}
function render() {{
  const dim = new Date(YEAR, parseInt(curMonth), 0).getDate();
  let head = '<tr><th>零件名称</th>';
  for (let d=1; d<=dim; d++) {{
    const dt = new Date(YEAR, parseInt(curMonth)-1, d);
    const wk = ['日','一','二','三','四','五','六'][dt.getDay()];
    const we = dt.getDay()===0 || dt.getDay()===6;
    head += `<th class="${{we?'weekend':''}}">${{d}}<br><span style="font-weight:400;font-size:10px;color:#8a8f98">${{wk}}</span></th>`;
  }}
  head += '<th>月合计</th></tr>';
  document.getElementById('ptHead').innerHTML = head;
  let body = '', grand = 0;
  DATA.forEach(r => {{
    const arr = r.daily[curMonth] || [];
    let sum = 0;
    let cells = '';
    for (let d=0; d<dim; d++) {{
      const v = arr[d] || 0;
      sum += v;
      const dt = new Date(YEAR, parseInt(curMonth)-1, d+1);
      const we = dt.getDay()===0 || dt.getDay()===6;
      cells += `<td class="${{v===0?'zero':''}} ${{we?'weekend':''}}">${{v?fmt(v):''}}</td>`;
    }}
    grand += sum;
    body += `<tr><td class="part">${{r.part}}</td>${{cells}}<td style="font-weight:700">${{fmt(sum)}}</td></tr>`;
  }});
  body += `<tr class="total-row"><td>合计（{supplier}）</td>`;
  const arrs = DATA.map(r => r.daily[curMonth] || []);
  for (let d=0; d<dim; d++) {{
    let s = 0; arrs.forEach(a => s += a[d]||0);
    body += `<td>${{s?fmt(s):''}}</td>`;
  }}
  body += `<td>${{fmt(grand)}}</td></tr>`;
  document.getElementById('ptBody').innerHTML = body;
  document.getElementById('sumLine').innerHTML = `${{MONTH_NAMES[curMonth]}} 拉动总量：<b>${{fmt(grand)}}</b> 件 · 共 ${{DATA.length}} 个零件`;
}}
render();

// ===== 确认收到 · 一键回执 =====
const RECEIVER_EMAIL = 'xufeng_cao@zhenchang.group';
const CONFIRM_KEY = 'sup_confirm_' + SUPPLIER;
function grandTotal(m) {{
  return DATA.reduce((s,r)=>s+((r.daily[m]||[]).reduce((a,b)=>a+(b||0),0)),0);
}}
function renderConfirmState() {{
  const done = localStorage.getItem(CONFIRM_KEY);
  const btn = document.getElementById('confirmBtn');
  const st = document.getElementById('confirmState');
  if (done) {{
    btn.innerHTML = '✅ 已反馈（' + done + '）';
    btn.style.background = '#16a34a';
    btn.style.boxShadow = 'none';
    st.textContent = '已向臻畅发送反馈，如计划有变请重新点击';
  }} else {{
    st.textContent = '能按期完成点 ✅；做不到请点 ⚠️ 反馈交期（自动带上原因与预计完成日期）';
  }}
}}
function openConfirm() {{
  const total = grandTotal(curMonth);
  const now = new Date();
  const ts = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0') + '-' + String(now.getDate()).padStart(2,'0') + ' ' + String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
  const subject = encodeURIComponent('【外协确认】' + SUPPLIER + ' 能按期完成 ' + MONTH_NAMES[curMonth] + '月拉动计划');
  const body = encodeURIComponent(
    SUPPLIER + ' 确认收到 ' + MONTH_NAMES[curMonth] + ' 月拉动计划，可执行订单拉动。\\n\\n' +
    '■ 供应商：' + SUPPLIER + '\\n' +
    '■ 计划月份：' + MONTH_NAMES[curMonth] + '月\\n' +
    '■ 零件数：' + DATA.length + ' 件\\n' +
    '■ 拉动总量：' + total.toLocaleString() + ' 件\\n' +
    '■ 确认时间：' + ts + '\\n' +
    '■ 页面：' + location.href + '\\n\\n' +
    '如有疑问请联系臻畅销售四部。'
  );
  const mailto = 'mailto:' + RECEIVER_EMAIL + '?subject=' + subject + '&body=' + body;
  if (confirm('确认【' + SUPPLIER + '】已收到 ' + MONTH_NAMES[curMonth] + ' 月拉动计划（共 ' + DATA.length + ' 个零件 / ' + total.toLocaleString() + ' 件），并通知臻畅可执行订单拉动？')) {{
    location.href = mailto;
    localStorage.setItem(CONFIRM_KEY, MONTH_NAMES[curMonth] + '月 ' + ts);
    renderConfirmState();
  }}
}}
// ===== 无法按期完成 → 反馈原因与交期 =====
const NL = `
`;
function openDelay() {{
  const total = grandTotal(curMonth);
  const now = new Date();
  const ts = now.getFullYear() + '-' + String(now.getMonth()+1).padStart(2,'0') + '-' + String(now.getDate()).padStart(2,'0') + ' ' + String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
  const why = prompt('请说明无法按期完成的原因（产能/模具/材料/交期等）：', '');
  if (why === null) return;
  const eta = prompt('预计什么时候可以完成？请填日期，例如 2026-10-08：', '');
  if (eta === null) return;
  const qty = prompt('本月计划 ' + total.toLocaleString() + ' 件，实际能完成多少件？（可留空）', '');
  if (qty === null) return;
  const subject = encodeURIComponent('【外协确认】' + SUPPLIER + ' 无法按期完成 ' + MONTH_NAMES[curMonth] + '月拉动计划');
  const body = encodeURIComponent(
    SUPPLIER + ' 反馈：' + MONTH_NAMES[curMonth] + ' 月拉动计划无法按期完成。' + NL + NL +
    '■ 供应商：' + SUPPLIER + NL +
    '■ 计划月份：' + MONTH_NAMES[curMonth] + ' 月' + NL +
    '■ 计划总量：' + total.toLocaleString() + ' 件 / ' + DATA.length + ' 个零件' + NL +
    '■ 实际可完成：' + (qty ? qty + ' 件' : '（未填）') + NL +
    '■ 原因：' + (why || '（未填）') + NL +
    '■ 预计完成日期：' + (eta || '（未填）') + NL +
    '■ 反馈时间：' + ts + NL +
    '■ 页面：' + location.href + NL + NL +
    '请臻畅确认调整后的拉动计划。'
  );
  location.href = 'mailto:' + RECEIVER_EMAIL + '?subject=' + subject + '&body=' + body;
  localStorage.setItem(CONFIRM_KEY, MONTH_NAMES[curMonth] + '月 需延期' + (eta ? ' 至 ' + eta : '') + ' (' + ts + ')');
  renderConfirmState();
}}
// ===== 上周发货情况填报 =====
function p2(n) {{ return String(n).padStart(2,'0'); }}
function dstr(d) {{ return d.getFullYear() + '-' + p2(d.getMonth()+1) + '-' + p2(d.getDate()); }}
function lastWeekRange() {{
  const today = new Date(); today.setHours(0,0,0,0);
  const end = new Date(today); end.setDate(today.getDate() - 1);
  const start = new Date(end); start.setDate(end.getDate() - 6);
  return [start, end];
}}
function planFor(r, s0, e0) {{
  let s = 0; const d = new Date(s0);
  while (d <= e0) {{
    const arr = (r.daily && r.daily[String(d.getMonth()+1)]) || [];
    s += arr[d.getDate()-1] || 0;
    d.setDate(d.getDate() + 1);
  }}
  return s;
}}
let SHIP_ROWS = [];
function renderShip() {{
  const rg = lastWeekRange(), s0 = rg[0], e0 = rg[1];
  document.getElementById('shipTitle').textContent = '📦 上周发货情况填报 · ' + dstr(s0) + ' ~ ' + dstr(e0);
  SHIP_ROWS = [];
  DATA.forEach((r, i) => {{ const p = planFor(r, s0, e0); if (p > 0) SHIP_ROWS.push({{i: i, part: r.part, plan: p}}); }});
  if (!SHIP_ROWS.length) {{ document.getElementById('shipBox').innerHTML = '<div style="color:#8a8f98;font-size:13px">上周（' + dstr(s0) + ' ~ ' + dstr(e0) + '）无计划量</div>'; return; }}
  let h = '<table><thead><tr><th>零件</th><th>上周计划(件)</th><th>实际发货(件)</th><th>发货日期</th><th>备注(缺料/延期原因)</th></tr></thead><tbody>';
  SHIP_ROWS.forEach((x, k) => {{
    h += '<tr><td class="part">' + x.part + '</td><td>' + x.plan.toLocaleString() + '</td>' +
      '<td><input class="shq" data-k="' + k + '" type="number" min="0" style="width:96px;padding:4px;border:1px solid #dfe2e7;border-radius:6px;text-align:right"></td>' +
      '<td><input class="shd" data-k="' + k + '" type="text" placeholder="如 9/16" style="width:80px;padding:4px;border:1px solid #dfe2e7;border-radius:6px"></td>' +
      '<td><input class="shr" data-k="' + k + '" type="text" placeholder="如 缺料延期至9/22" style="width:180px;padding:4px;border:1px solid #dfe2e7;border-radius:6px"></td></tr>';
  }});
  h += '</tbody></table>';
  document.getElementById('shipBox').innerHTML = h;
}}
function shipLines() {{
  const rg = lastWeekRange();
  let tp = 0, ta = 0, unfilled = 0, lines = [];
  SHIP_ROWS.forEach((x, k) => {{
    const q = document.querySelector('.shq[data-k="' + k + '"]');
    const dv = document.querySelector('.shd[data-k="' + k + '"]');
    const rv = document.querySelector('.shr[data-k="' + k + '"]');
    const act = (q && q.value !== '') ? parseInt(q.value, 10) : null;
    if (act === null) unfilled++;
    tp += x.plan; ta += (act || 0);
    lines.push('• ' + x.part + '｜计划 ' + x.plan + '｜实际 ' + (act === null ? '未填' : act) +
      (dv && dv.value ? '｜发货 ' + dv.value : '') + (rv && rv.value ? '｜' + rv.value : ''));
  }});
  const rate = tp ? Math.round(ta / tp * 1000) / 10 : 0;
  return {{lines: lines, tp: tp, ta: ta, rate: rate, unfilled: unfilled, rg: rg}};
}}
function submitShip() {{
  const d = shipLines();
  const now = new Date();
  const ts = dstr(now) + ' ' + p2(now.getHours()) + ':' + p2(now.getMinutes());
  const subject = encodeURIComponent('【外协发货】' + SUPPLIER + ' ' + dstr(d.rg[0]) + '~' + dstr(d.rg[1]) + ' 发货情况');
  const body = SUPPLIER + ' 上周发货情况反馈' + NL + NL +
    '■ 供应商：' + SUPPLIER + NL +
    '■ 周次：' + dstr(d.rg[0]) + ' ~ ' + dstr(d.rg[1]) + NL +
    '■ 计划总量：' + d.tp.toLocaleString() + ' 件' + NL +
    '■ 实际发货：' + d.ta.toLocaleString() + ' 件' + NL +
    '■ 达成率：' + d.rate + '%' + NL +
    '■ 未填零件：' + d.unfilled + ' 个' + NL +
    '■ 填报时间：' + ts + NL + NL + '明细：' + NL + d.lines.join(NL);
  location.href = 'mailto:' + RECEIVER_EMAIL + '?subject=' + subject + '&body=' + encodeURIComponent(body);
  document.getElementById('shipState').textContent = '已生成邮件，请在邮件客户端点发送（' + ts + '）';
}}
function copyShip() {{
  const d = shipLines();
  const txt = '【' + SUPPLIER + '】上周发货情况 ' + dstr(d.rg[0]) + '~' + dstr(d.rg[1]) + NL +
    '计划 ' + d.tp + ' 件 / 实际 ' + d.ta + ' 件 / 达成率 ' + d.rate + '%' + NL + d.lines.join(NL);
  const st = document.getElementById('shipState');
  if (navigator.clipboard) {{ navigator.clipboard.writeText(txt).then(() => {{ st.textContent = '已复制，可直接粘贴到微信发给臻畅'; }}).catch(() => {{ window.prompt('复制以下内容：', txt); }}); }}
  else {{ window.prompt('复制以下内容：', txt); }}
}}
// ===== 签收单上传(静态页无服务器: 压缩后分享到微信/邮件 或 下载) =====
let POD = [];
function onPodPick(e) {{
  const fs = Array.from((e.target && e.target.files) || []);
  POD = [];
  const st = document.getElementById('podState');
  if (!fs.length) {{ document.getElementById('podList').textContent = ''; st.textContent = ''; return; }}
  st.textContent = '处理中…';
  let pending = fs.length;
  function done() {{ pending--; if (pending <= 0) renderPod(); }}
  fs.forEach(f => {{
    if (f.type && f.type.indexOf('image') === 0) {{
      compressImg(f).then(c => {{ POD.push({{name: f.name.replace(/\.[^.]+$/, '') + '.jpg', blob: c}}); done(); }});
    }} else {{ POD.push({{name: f.name, blob: f}}); done(); }}
  }});
}}
function compressImg(file) {{
  return new Promise(res => {{
    const img = new Image();
    img.onload = () => {{
      const maxW = 1600, sc = Math.min(1, maxW / img.width);
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * sc); c.height = Math.round(img.height * sc);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(b => res(b || file), 'image/jpeg', 0.82);
    }};
    img.onerror = () => res(file);
    img.src = URL.createObjectURL(file);
  }});
}}
function renderPod() {{
  let kb = 0;
  POD.forEach(x => {{ kb += (x.blob.size || 0); }});
  document.getElementById('podList').innerHTML = POD.map((x, i) => (i + 1) + '. ' + x.name + '（' + Math.round((x.blob.size || 0) / 1024) + 'KB）').join('<br>');
  document.getElementById('podState').textContent = '已选 ' + POD.length + ' 个文件，合计 ' + Math.round(kb / 1024) + 'KB';
}}
function sharePod() {{
  const st = document.getElementById('podState');
  if (!POD.length) {{ st.textContent = '请先选择签收单文件'; return; }}
  const files = POD.map(x => new File([x.blob], x.name, {{type: x.blob.type || 'image/jpeg'}}));
  const txt = '【' + SUPPLIER + '】上周发货签收单 ' + POD.length + ' 个文件';
  if (navigator.canShare && navigator.canShare({{files: files}})) {{
    navigator.share({{files: files, title: txt, text: txt}})
      .then(() => {{ st.textContent = '已发送，谢谢！'; }})
      .catch(() => {{ st.textContent = '已取消。可改用「⬇️ 下载签收单」后在微信里发给我们'; }});
  }} else {{
    st.textContent = '当前浏览器不支持直接分享，请点「⬇️ 下载签收单」，再在微信里发给臻畅（或发 xufeng_cao@zhenchang.group）';
  }}
}}
function downloadPod() {{
  const st = document.getElementById('podState');
  if (!POD.length) {{ st.textContent = '请先选择签收单文件'; return; }}
  POD.forEach((x, i) => {{
    const a = document.createElement('a');
    a.href = URL.createObjectURL(x.blob); a.download = x.name;
    document.body.appendChild(a);
    setTimeout(() => {{ a.click(); }}, i * 500);
  }});
  st.textContent = '开始下载 → 下载后请在微信里发给臻畅对接人（或发 xufeng_cao@zhenchang.group）';
}}
function copyMail() {{
  const mail = 'xufeng_cao@zhenchang.group';
  const st = document.getElementById('podState');
  if (navigator.clipboard) {{ navigator.clipboard.writeText(mail).then(() => {{ st.textContent = '已复制邮箱：' + mail; }}); }}
  else {{ window.prompt('我们的邮箱：', mail); }}
}}
renderShip();
renderConfirmState();
</script>
</body>
</html>"""

def make_page(supplier, rows):
    rows_data = [{
        "part": r["part"],
        "daily": {m: r.get("daily", {}).get(m, [0]*31) for m in MONTHS},
    } for r in rows]
    html = TMPL.format(
        supplier=supplier,
        supplier_json=json.dumps(supplier, ensure_ascii=False),
        rows_json=json.dumps(rows_data, ensure_ascii=False),
        year=YEAR,
        months_json=json.dumps(MONTHS),
        month_names_json=json.dumps(MONTH_NAMES, ensure_ascii=False),
        updated=datetime.date.today().isoformat(),
    )
    return html

pages = [
    ("supplier-husheng.html", "宁波互盛", HUSHENG),
    ("supplier-chengfeng.html", "江苏诚丰", CHENGFENG),
]

OUT = os.path.dirname(BASE)  # 仓库根目录
for fname, sup, rows in pages:
    if not rows:
        print(f"{fname}: 无数据, 跳过")
        continue
    html = make_page(sup, rows)
    path = os.path.join(OUT, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

# 自制件页面（内部生产计划）— 复用外协同款模板, 全套确认/反馈/发货填报/签收单
if TAIRUI:
    with open(os.path.join(OUT, "pull-plan-tairui.html"), "w", encoding="utf-8") as f:
        f.write(make_page("上海泰瑞·自制", TAIRUI))
    print(f"pull-plan-tairui.html: {len(TAIRUI)} 个自制零件(含确认/反馈/发货填报/签收单) -> 已生成")
else:
    print("pull-plan-tairui.html: 无自制件数据, 跳过")
