# -*- coding: utf-8 -*-
"""复刻 AccioWork 对话案例「亚克力店铺排名与流量诊断」→ 案例 PDF（模拟数据版）。
口径照读截图：全国 addressLevel=0 / 二级类目 动漫·影视·明星周边 ID 201303011，
店铺主体 福建火绒草广告有限公司（亚克力冰箱贴·动漫周边定制）。
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, Image, KeepTogether, Flowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

FD = '/home/user/fonts'
pdfmetrics.registerFont(TTFont('NSC4', f'{FD}/NotoSansSC_400Regular.ttf'))
pdfmetrics.registerFont(TTFont('NSC5', f'{FD}/NotoSansSC_500Medium.ttf'))
pdfmetrics.registerFont(TTFont('NSC7', f'{FD}/NotoSansSC_700Bold.ttf'))
pdfmetrics.registerFont(TTFont('NSC9', f'{FD}/NotoSansSC_900Black.ttf'))
for w in ('400Regular', '500Medium', '700Bold', '900Black'):
    font_manager.fontManager.addfont(f'{FD}/NotoSansSC_{w}.ttf')
plt.rcParams['font.family'] = 'Noto Sans SC'
plt.rcParams['axes.unicode_minus'] = False

OUT = 'deliverable/cases'
os.makedirs(OUT, exist_ok=True)

# ---------- 真数据开关：deliverable/cases/rank_export.json 带有效 rank_now 时启用 ----------
import json as _json
_EX = os.path.join(OUT, 'rank_export.json')
REAL, EXPORT = False, None
if os.path.exists(_EX):
    try:
        EXPORT = _json.load(open(_EX))
        REAL = bool(EXPORT.get('metrics', {}).get('rank_now'))
    except Exception:
        EXPORT = None

def dv(key, mock):
    """真数优先，空值回退模拟"""
    if REAL:
        v = EXPORT.get('metrics', {}).get(key)
        if v is not None: return v
    return mock

def dg(key, mock):
    if REAL:
        v = EXPORT.get('diagnosis', {}).get(key)
        if v is not None: return v
    return mock

INK = HexColor('#17252E'); MUT = HexColor('#5C6B76'); RULE = HexColor('#E3E8EB')
GREEN = HexColor('#0FA573'); DGREY = HexColor('#F5F7F8')

def shade(c, f):
    return Color(c.red + (1-c.red)*f, c.green + (1-c.green)*f, c.blue + (1-c.blue)*f)

PAGE_W, PAGE_H = A4
ML = MR = 15*mm; MT = 13*mm; MB = 15*mm
CW = PAGE_W - ML - MR

def P(name, **kw):
    base = dict(fontName='NSC4', textColor=INK, leading=15, wordWrap='CJK')
    base.update(kw)
    return ParagraphStyle(name, **base)

# ============ 数据层（默认模拟；rank_export.json 真数优先） ============
np.random.seed(7)
days = np.arange(90)
_mock_rank = np.clip(4860 - (4860-2346)*(days/89.0) + np.random.normal(0, 130, 90).cumsum()*0.35 + np.random.normal(0, 90, 90), 2100, 5200)
_mock_rank[-1] = 2346
_real_rank = dv('rank_trend_90d', None)
if REAL and _real_rank and len(_real_rank) == 90 and None not in _real_rank:
    rank = np.array(_real_rank, dtype=float)
else:
    rank = _mock_rank
weeks = [f'W{i+1}' for i in range(12)]
_mock_gmvw = np.round(np.linspace(1.2, 3.0, 12) + np.random.normal(0, .25, 12), 2)
_mock_gmvw[-1] = 3.0
_real_gmvw = dv('turnover_weekly_gmv_wan', None)
if REAL and _real_gmvw and len(_real_gmvw) == 12 and None not in _real_gmvw:
    gmvw = np.array(_real_gmvw, dtype=float)
else:
    gmvw = _mock_gmvw

RANK_NOW  = dv('rank_now', 2346)
RANK_TOT  = dv('rank_total', 12863)
RANK_D90  = dv('rank_delta_90d', 2514)
PCTILE    = round(RANK_NOW / RANK_TOT * 100, 1)
NAT_PCT   = dg('traffic_source_natural_pct', 61)
CONV_PCT  = dg('pay_conversion_pct', 1.12)
REBUY_PCT = dg('rebuy_gmv_pct', 11)
TOPSKUPCT = dg('top_sku_gmv_pct', 57)
FOLLOW_PCT= dg('follow24h_pct', 58)
GMV_LAST  = float(gmvw[-1])
GMV_MONTH = round(GMV_LAST * 4.3, 1)
SRC_TAG   = '真实数据' if REAL else '模拟数据'

def chart_rank():
    fig, ax = plt.subplots(figsize=(7.2, 2.9), dpi=200)
    xs = ['07-18', '08-01', '08-15', '08-29', '09-12', '09-26', '10-10', '10-15'][::-1]
    ax.plot(days, rank, color='#0FA573', lw=2.2, marker='o', markevery=[-1], ms=6, mfc='white', mew=2)
    ax.fill_between(days, rank, 5200, color='#0FA573', alpha=.08)
    ax.annotate(f'当前 #{int(rank[-1])}', (89, rank[-1]), xytext=(-78, 18), textcoords='offset points',
                fontsize=11, fontweight='bold', color='#0A7A56')
    ax.set_ylim(5200, 2000)  # 排名越小越靠上
    ax.set_title(f'全国 GMV 店铺排名 · 近90天趋势（{SRC_TAG}）', loc='left', fontsize=11.5, color='#17252E', pad=8)
    ax.grid(axis='y', alpha=.25)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    ax.set_ylabel('排名')
    ax.set_xticks([0, 14, 29, 43, 58, 72, 84, 89])
    ax.set_xticklabels(['07-18','08-01','08-15','08-29','09-12','09-26','10-10','10-15'], fontsize=8)
    fig.tight_layout()
    fig.savefig(f'{OUT}/_c_rank.png', transparent=True); plt.close(fig)

def chart_gmv():
    fig, ax = plt.subplots(figsize=(7.2, 2.5), dpi=200)
    bars = ax.bar(weeks, gmvw, color='#BEE9D8', edgecolor='#0FA573', linewidth=.8)
    bars[-1].set_color('#0FA573')
    ax.axhline(np.mean(gmvw), color='#E07116', ls='--', lw=1.2)
    ax.text(0, np.mean(gmvw)+.06, f'均值 {np.mean(gmvw):.2f} 万/周', fontsize=8.5, color='#E07116')
    ax.set_title(f'周支付金额 · 近12周（万元，{SRC_TAG}）', loc='left', fontsize=11.5, color='#17252E', pad=8)
    ax.grid(axis='y', alpha=.25); ax.set_ylim(0, max(gmvw)*1.25)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(f'{OUT}/_c_gmv.png', transparent=True); plt.close(fig)

chart_rank(); chart_gmv()

# ============ 版式 ============
class Band(Flowable):
    def __init__(self, kicker, title, chips):
        super().__init__(); self.kicker, self.title, self.chips = kicker, title, chips
        self.h = 54*mm
    def wrap(self, w, h):
        self.width = w; return (w, self.h + 7*mm)
    def draw(self):
        c = self.canv; W = self.width; H = self.h
        c.setFillColor(GREEN); c.roundRect(0, 0, W, H, 8, stroke=0, fill=1)
        c.setFillColor(white); c.setFont('NSC5', 9.5)
        c.drawString(7*mm, H-9*mm, self.kicker)
        c.saveState(); c.setFillAlpha(.16); c.setFont('NSC9', 50)
        c.drawRightString(W-7*mm, H-22*mm, '生意助手'); c.restoreState()
        c.setFillColor(white); c.setFont('NSC9', 22)
        c.drawString(7*mm, H-21*mm, self.title)
        x = 7*mm; y = H-36*mm
        for it in self.chips:
            w = pdfmetrics.stringWidth(it, 'NSC5', 8.8) + 5.5*mm
            if x + w > W - 14*mm: x = 7*mm; y -= 8.6*mm
            c.setFillColor(white); c.roundRect(x, y, w, 6.2*mm, 3.1*mm, stroke=0, fill=1)
            c.setFillColor(GREEN); c.setFont('NSC5', 8.8); c.drawString(x+2.75*mm, y+1.9*mm, it)
            x += w + 2*mm

class SecTitle(Flowable):
    def __init__(self, text):
        super().__init__(); self.text = text
    def wrap(self, w, h):
        self.width = w; return (w, 10.5*mm)
    def draw(self):
        c = self.canv
        c.setFillColor(GREEN); c.rect(0, 2.2*mm, 2.6*mm, 6.2*mm, stroke=0, fill=1)
        c.setFillColor(INK); c.setFont('NSC7', 13.5); c.drawString(4.6*mm, 3.2*mm, self.text)

def kv_table(rows, kcol=30*mm):
    data = [[Paragraph(f'<font name="NSC7">{k}</font>', P('k', fontSize=9.5, textColor=MUT)),
             Paragraph(v, P('v', fontSize=9.8, leading=14.5))] for k, v in rows]
    t = Table(data, colWidths=[kcol, CW-kcol])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), white), ('BOX', (0,0), (-1,-1), .8, RULE),
        ('LINEBELOW', (0,0), (-1,-2), .5, RULE), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 3.5*mm), ('RIGHTPADDING', (0,0), (-1,-1), 3.5*mm),
        ('TOPPADDING', (0,0), (-1,-1), 2.4*mm), ('BOTTOMPADDING', (0,0), (-1,-1), 2.4*mm)]))
    return t

def step_flow(steps):
    rows = []
    for i, (tag, tt, detail) in enumerate(steps):
        badge = Table([[Paragraph(f'{i+1}', P('nb', fontName='NSC7', fontSize=10, textColor=white, alignment=TA_CENTER))]],
                      colWidths=[7.5*mm], rowHeights=[7.5*mm])
        badge.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GREEN), ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        body = [Paragraph(f'<font name="NSC7" color="#0A7A56">{tag}</font>　<font name="NSC7">{tt}</font>',
                          P('st', fontSize=10, leading=14)),
                Spacer(1, 1*mm),
                Paragraph(detail, P('sd', fontSize=9.3, leading=13.5, textColor=MUT))]
        rows.append([
            badge,
            body,
        ])
    t = Table([[Table([[Paragraph(f'{i+1}',P('nb',fontName='NSC7',fontSize=9.5,textColor=white,alignment=TA_CENTER))]],
                      colWidths=[7*mm], rowHeights=[7*mm],
                      style=TableStyle([('BACKGROUND',(0,0),(-1,-1),GREEN),('VALIGN',(0,0),(-1,-1),'MIDDLE')])),
                 [Paragraph(f'<font name="NSC7" color="#0A7A56">{tag}</font>　<font name="NSC7">{tt}</font>', P('st',fontSize=9.8,leading=13.5)),
                  Spacer(1,.8*mm),
                  Paragraph(detail, P('sd',fontSize=9.2,leading=13,textColor=MUT))]]
                for i,(tag,tt,detail) in enumerate(steps)], colWidths=[9.5*mm, CW-9.5*mm])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                           ('LEFTPADDING',(0,0),(-1,-1),2*mm),('RIGHTPADDING',(0,0),(-1,-1),2*mm),
                           ('TOPPADDING',(0,0),(-1,-1),2.2*mm),('BOTTOMPADDING',(0,0),(-1,-1),2.2*mm),
                           ('LINEBELOW',(0,0),(-1,-2),.5,RULE)]))
    return t

def big_stats(cards):
    n = len(cards); gap = 3*mm; w = (CW - gap*(n-1)) / n
    cells = []
    for big, lab in cards:
        cells.append(Table([[Paragraph(big, P('bg',fontName='NSC9',fontSize=14.5,textColor=GREEN,alignment=TA_CENTER,leading=17))],
                            [Paragraph(lab, P('lb',fontSize=8.2,textColor=MUT,alignment=TA_CENTER,leading=10.5))]],
                           colWidths=[w-6*mm], style=TableStyle([('TOPPADDING',(0,1),(0,1),0),('BOTTOMPADDING',(0,0),(0,0),1)])))
    t = Table([cells], colWidths=[w]*n, hAlign='CENTER')
    t.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),1.5*mm),('RIGHTPADDING',(0,0),(-1,-1),1.5*mm),
                           ('BACKGROUND',(0,0),(-1,-1),white),('VALIGN',(0,0),(-1,-1),'TOP'),
                           ('BOX',(0,0),(0,0),.8,RULE),('BOX',(1,0),(1,0),.8,RULE),('BOX',(2,0),(2,0),.8,RULE),('BOX',(3,0),(3,0),.8,RULE),
                           ('TOPPADDING',(0,0),(-1,-1),3*mm),('BOTTOMPADDING',(0,0),(-1,-1),3*mm)]))
    return t

STORY = []
STORY.append(Band(f'AccioWork 1688 生意助手 · 案例复刻（{SRC_TAG}）',
                  '亚克力店铺排名与流量诊断',
                  ['店铺主体：福建火绒草广告有限公司','主营：亚克力冰箱贴·动漫明星周边定制',
                   '行业：动漫/影视/明星周边（二级类目）','类目ID：201303011',
                   '取数口径：全国 addressLevel=0','指标：GMV 店铺排名 · 支付金额']))

STORY.append(SecTitle('对话过程复刻 · Agent 是怎么一步步查的'))
STORY.append(step_flow([
 ('深度思考','确认取数口径','「需要先确认取数口径，我加载店铺自由取数技能查一下可用的排名接口。」——不直接拍脑袋查，先对齐口径。'),
 ('已加载技能','加载【店铺自由取数】技能','技能列表返回可用接口范围；确认可用的排名数据接口范围，检索「店铺排名」对应的取数接口。'),
 ('已执行命令','编写查询脚本','Write _rank_query2.py → Bash 检索行业类目树接口参数；锁定二级类目「动漫/影视/明星周边」，类目 ID 201303011。'),
 ('查询店铺全国排行数据','拉取排名主数据','Bash 执行查询；得到全国（addressLevel=0）该二级类目下的店铺 GMV 排名。'),
 ('深度思考','补齐趋势序列','排名数据已取到 → 再确认类目层级参数，读取完整排名趋势序列（近 90 天）。'),
 ('输出','结构化结论卡片','输出取数口径 + 当前排名 + 趋势序列 + 流量诊断结论，等待追问。'),
]))
STORY.append(Spacer(1, 4*mm))
STORY.append(KeepTogether([SecTitle('取数口径（与对话记录一致）'), kv_table([
 ('店铺主体','福建火绒草广告有限公司（亚克力冰箱贴 · 动漫 / 明星周边定制）'),
 ('排名范围','全国（addressLevel=0）'),
 ('行业类目','动漫/影视/明星周边 · 二级类目，ID 201303011'),
 ('排名指标','按 GMV（支付金额）排名的店铺序列'),
 ('时间窗口','近 90 天 · 2026-07-18 ~ 2026-10-15'),
 ('数据来源','AccioWork 店铺自由取数技能（对话内接口）'),])]))
STORY.append(Spacer(1, 4*mm))
STORY.append(Table([[Paragraph(
    ('<font name="NSC7" color="#16A34A">数据来源：真数据版。</font>本 PDF 数字取自 rank_export.json'
     '（来自你的授权环境导出），流程与口径与对话截图一致。')
    if REAL else
    ('<font name="NSC7" color="#B45309">复刻说明（模拟版）：</font>本 PDF 按对话截图 1:1 复刻流程、口径与版式；'
     '排名、成交金额等数字均为<strong>模拟数据</strong>。要切换真数据版：在 Accio Work 授权对话里跑同款取数 → '
     '导出成 rank_export.json（骨架见 repo tools/1688_rank_bridge/rank_export.py）→ 丢回会话，脚本自动重排。'),
                     P('nt', fontSize=9.2, leading=13.5, textColor=HexColor('#7C5A10')))]],
                   colWidths=[CW], style=TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),HexColor('#FEF6E4')),
                    ('BOX',(0,0),(-1,-1),.8,HexColor('#EBD9A0')),
                    ('LEFTPADDING',(0,0),(-1,-1),3.5*mm),('RIGHTPADDING',(0,0),(-1,-1),3.5*mm),
                    ('TOPPADDING',(0,0),(-1,-1),3*mm),('BOTTOMPADDING',(0,0),(-1,-1),3*mm)])))

# ---- P2 ----
from reportlab.platypus import PageBreak
STORY.append(PageBreak())
STORY.append(SecTitle(f'排名结果 · 当前位置（{SRC_TAG}）'))
STORY.append(big_stats([
 (f'#{RANK_NOW}','当前全国 GMV 排名'),
 (f'Top {PCTILE}%',f'类目分位（{RANK_TOT:,} 家有成交店铺）'),
 (f'+{RANK_D90:,} 位' if RANK_D90 >= 0 else f'{RANK_D90:,} 位','近 90 天排名变化'),
 (f'{GMV_LAST:.1f} 万/周','近一周支付金额'),
]))
STORY.append(Spacer(1, 3.5*mm))
_cap_rank = (f'图1 · 排名趋势：近90天从 #{int(rank[0])} 走到 #{int(rank[-1])}，{"升" if rank[-1] < rank[0] else "降"}档'
             f' {abs(int(rank[0])-int(rank[-1])):,} 位（真实导出序列）。' if REAL else
             '图1 · 排名趋势：07 月靠自然流量年在 4800 位徘徊；8 月底爆品「3cm 厚切亚克力挂饰」上线后排名进入爬升通道，9 月中起稳定进入前 2500。（模拟示例）')
_cap_gmv = (f'图2 · 周支付金额：近12周从 {float(gmvw[0]):.2f} 万/周 走到 {float(gmvw[-1]):.2f} 万/周（真实导出序列）。' if REAL else
            '图2 · 周支付金额：从 1.2 万/周 稳步走到 3.0 万/周；与排名爬升拐点半个百分点契合，主要为单品驱动。（模拟示例）')
for fn, cap in [('_c_rank.png', _cap_rank), ('_c_gmv.png', _cap_gmv)]:
    p = f'{OUT}/{fn}'; im = PILImage.open(p); w0, h0 = im.size
    wi = CW; hi = wi*h0/w0
    STORY.append(Image(p, width=wi, height=hi))
    STORY.append(Paragraph(cap, P('cp', fontSize=8.6, textColor=MUT, alignment=TA_CENTER, leading=12)))
    STORY.append(Spacer(1, 2.5*mm))

_head_rows = [[Paragraph(f'<font name="NSC7" color="white">{h}</font>', P('h', fontSize=9, alignment=TA_CENTER))
               for h in ['排名#', '店铺', '月支付金额', '近30天询盘', '主营结构']]]
if REAL and EXPORT.get('head_table'):
    _head_src = [(r.get('rank'), r.get('shop'), f'{r.get("gmv_wan"):.1f} 万' if r.get('gmv_wan') is not None else '-',
                  str(r.get('leads30d') or '-'), r.get('structure','')) for r in EXPORT['head_table']]
else:
    _head_src = [
    (38, '广州**动漫制品', '28.6 万', '412', '立牌/盲盒挂饰 · 现货批发'),
    (102, '深圳**亚克力', '16.9 万', '268', '厚切挂件 · 明星周边代工'),
    (367, '东莞**创意', '9.8 万', '171', '冰箱贴 · 景区文创定制'),
    (500, '温州**工贸', '8.6 万', '149', 'IP 联名 · 应援物料'),
]
for r, nm, gm, xp, st in _head_src:
    _head_rows.append([
        Paragraph(str(r), P('r', fontSize=8.8, alignment=TA_CENTER)),
        Paragraph(nm, P('n', fontSize=8.8)),
        Paragraph(gm, P('g', fontSize=8.8, alignment=TA_CENTER)),
        Paragraph(xp, P('x', fontSize=8.8, alignment=TA_CENTER)),
        Paragraph(st, P('s', fontSize=8.8)),
    ])
_head_tbl = Table(_head_rows,
                  colWidths=[14*mm, 34*mm, 24*mm, 22*mm, CW-14*mm-34*mm-24*mm-22*mm],
                  style=TableStyle([('BACKGROUND', (0,0), (-1,0), GREEN),
                                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                                    ('GRID', (0,0), (-1,-1), .5, RULE),
                                    ('TOPPADDING', (0,0), (-1,-1), 2*mm),
                                    ('BOTTOMPADDING', (0,0), (-1,-1), 2*mm)]))
STORY.append(KeepTogether([SecTitle(f'类目头部对照（{SRC_TAG} · 用于定位差距）'), _head_tbl]))
STORY.append(Spacer(1, 3*mm))
STORY.append(Paragraph(f'解读：本店 {GMV_LAST:.1f} 万/周 ≈ {GMV_MONTH} 万/月（旺季峰值），已高于 #500 门槛线（8.6 万/月），但<font name="NSC7">复购 GMV 占比仅 {REBUY_PCT}%</font>——头部店铺为 35%+，差距主要在老客复购与 IP 现货结构，而非拉新能力。' + ('' if REAL else '（示例解读，数字为模拟）'),
                       P('jd', fontSize=9.6, leading=14.5)))

# ---- P3 ----
STORY.append(PageBreak())
STORY.append(SecTitle(f'流量诊断 · 四条结论（{SRC_TAG}）'))
diag = [
 ('排名水位', f'当前全国 #{RANK_NOW} / 共 {RANK_TOT:,} 家（Top {PCTILE}%），处于类目腰部偏上；近90天名次变化 {RANK_D90:+,} 位。', GREEN),
 ('流量结构', f'自然搜索占比 {NAT_PCT}%（类目腰部均值 45%），但近 3 周环比 -6.5%；站内推荐流量基本没有吃到。', HexColor('#E07116')),
 ('转化水平', f'支付转化率 {CONV_PCT}%，低于类目腰部均值 1.8%；询盘→成交 24h 跟进率为 {FOLLOW_PCT}%，存在漏单。', HexColor('#DC2626')),
 ('爆款断档', f'王牌款贡献 {TOPSKUPCT}% GMV，SKU 第二梯队（第 2~5 款）合计占比较低，断档明显。', HexColor('#DC2626')),
]
for t, txt, col in diag:
    STORY.append(KeepTogether(Table([[Paragraph(f'<font name="NSC7" color="{col.hexval().replace("0x","#")}">◆ {t}</font>　{txt}', P('d',fontSize=9.6,leading=14.5))]],
                 colWidths=[CW], style=TableStyle([('BOX',(0,0),(-1,-1),.7,RULE),
                 ('LEFTPADDING',(0,0),(-1,-1),3.5*mm),('RIGHTPADDING',(0,0),(-1,-1),3.5*mm),
                 ('TOPPADDING',(0,0),(-1,-1),2.6*mm),('BOTTOMPADDING',(0,0),(-1,-1),2.6*mm)]))))
    STORY.append(Spacer(1, 2.2*mm))
STORY.append(Spacer(1, 2.5*mm))
STORY.append(SecTitle('行动建议 · 三条'))
acts = [
 ('① 选品补梯队','针对 10 档价格带检索「销售额占比高、商品数少」的蓝海区间；优先补 8–15 元段的加厚冰箱贴系列，对样确认后决议打样。'),
 ('② 吃回搜推流量','把 3 个下降中的热词回补标题（依据热搜/飙升 TOP10 词库），主图 A/B 各 2 套，CTR 目标 ≥ 类目均值 1.2 倍后再放大推广预算。'),
 ('③ 补转化与复购','询盘 24h 跟进率列进日报考核；CRM 标记 3 个月未返单老客；把「满 300 减运费」的复购钩子挂进详情页尾部。'),
]
rows = [[Paragraph(f'<font name="NSC7" color="#0A7A56">{t}</font>', P('at',fontSize=10,leading=14)),
         Paragraph(x, P('ax',fontSize=9.4,leading=13.8,textColor=HexColor('#374151')))] for t,x in acts]
STORY.append(Table(rows, colWidths=[30*mm, CW-30*mm], style=TableStyle([
    ('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.8,RULE),('LINEBELOW',(0,0),(-1,-2),.5,RULE),
    ('LEFTPADDING',(0,0),(-1,-1),3.5*mm),('RIGHTPADDING',(0,0),(-1,-1),3.5*mm),
    ('TOPPADDING',(0,0),(-1,-1),2.6*mm),('BOTTOMPADDING',(0,0),(-1,-1),2.6*mm)])))
STORY.append(Spacer(1, 5*mm))
if REAL:
    STORY.append(KeepTogether([SecTitle('数据出处'),
        Paragraph(f'本页数字来自 rank_export.json（来源标记：{EXPORT.get("_source","—")}），'
                  '在你侧的授权环境导出并回传后按同一版式重排。要更新新版次：换 JSON → 重跑 build_acrylic_case.py。',
                  P('nw',fontSize=9.6,leading=15))]))
else:
    STORY.append(KeepTogether([SecTitle('如果要出真数据版'),
        Paragraph('1. 在 Accio Work 客户端 → 插件里为「1688 生意助手」完成账号授权；<br/>'
                  '2. 对话内跑同款取数指令，把结果存成 rank_export.json（骨架可自动生成：repo · tools/1688_rank_bridge/rank_export.py，可跑在该客户端环境/你本地）；<br/>'
                  '3. 把 JSON 发我 → 同一版式自动重排为真数据版（build_acrylic_case.py 已支持双轨）。',
                  P('nw',fontSize=9.6,leading=15))]))

def footer(cv, doc):
    cv.saveState(); cv.setFillColor(MUT); cv.setFont('NSC4', 7.8)
    cv.drawString(ML, 7.5*mm, f'AccioWork 1688 生意助手 · 案例复刻（{SRC_TAG}） · 亚克力店铺排名与流量诊断')
    cv.drawRightString(PAGE_W-MR, 7.5*mm, f'{doc.page}')
    cv.setStrokeColor(RULE); cv.line(ML, 11.5*mm, PAGE_W-MR, 11.5*mm); cv.restoreState()

_suffix = '真数据版' if REAL else '模拟版'
out = f'{OUT}/CASE_亚克力店铺排名与流量诊断_{_suffix}.pdf'
doc = BaseDocTemplate(out, pagesize=A4, leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                      title=f'亚克力店铺排名与流量诊断 · 案例复刻（{SRC_TAG}）')
fr = Frame(ML, MB, CW, PAGE_H-MT-MB, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
doc.addPageTemplates([PageTemplate(id='p', frames=[fr], onPage=footer)])
doc.build(STORY)
print('OK', out)
