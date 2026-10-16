#!/usr/bin/env python3
"""Replicate the 'GEO布局 x 专家-SEO-GEO 助手' operations matrix module (2700x600, 2x fidelity).
Faithful copy of the reference: white grid table, dark thin lines, header + 4 rows,
left row-group label cell, right summary cell. Mixed-weight centered text per cell."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'deliverable', 'geo-module')
os.makedirs(OUT, exist_ok=True)

FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0]

W = 2700
C1, C2, C3, C4 = 190, 880, 1200, 430   # col widths
X = [0, C1, C1 + C2, C1 + C2 + C3, W]
H_H = 160
H_R = 110
H = H_H + 4 * H_R
LINE = (0x15, 0x15, 0x2B)
INK = (0x11, 0x11, 0x22)

im = Image.new('RGB', (W, H), (255, 255, 255))
d = ImageDraw.Draw(im)

# grid lines: outer 4, inner 3
for x in X:
    d.rectangle((x - 2 if x in (X[0], X[-1]) else x - 1.5, 0,
                 x + 2 if x in (X[0], X[-1]) else x + 1.5, H), fill=LINE)
ys = [0, H_H] + [H_H + i * H_R for i in range(1, 5)]
for i, y in enumerate(ys):
    w_ = 4 if i in (0, len(ys) - 1) else 3
    d.rectangle((0, y - w_ / 2, W, y + w_ / 2), fill=LINE)

def cell_center(cx0, cx1, y0, y1, segs, fsize=44):
    """segs: list of (text, boldflag); centered composite, baseline on em-middle"""
    total = sum(tw(d, s, (B if b else R)(fsize)) for s, b in segs)
    x = cx0 + (cx1 - cx0 - total) / 2
    yc = (y0 + y1) / 2
    for s, b in segs:
        f = (B if b else R)(fsize)
        d.text((x, yc), s, font=f, fill=INK, anchor='lm')
        x += tw(d, s, f)

def cell_right(cx0, cx1, y0, y1, s, f):
    d.text((cx1 - 34, (y0 + y1) / 2), s, font=f, fill=INK, anchor='rm')

# header
cell_center(X[1], X[2], 0, H_H, [('GEO布局', True)], 50)
cell_center(X[2], X[3], 0, H_H, [('专家-SEO-GEO 助手', True)], 50)

# left row-group label (spans rows)
yc_all = (H_H + H) / 2
lblw = tw(d, '运营获客', B(44))
d.text((X[0] + (C1 - lblw) / 2, yc_all), '运营获客', font=B(44), fill=INK, anchor='lm')

ROWS = [
    ([('上新发品：', True), ('发品+一键上架', False)],
     [('1688生意助手+提示词+技能（商品一键操作）', False)]),
    ([('商品优化：', True), ('标题/属性/关键词/服务/相关性', False)],
     [('1688生意助手+提示词+技能（', False), ('1688商品标题优化', True), (' 工具能力）、自建智能体/skill', False)]),
    ([('指标提升：', True), ('供应链星级、采购指数4.0', False)],
     [('1688生意助手+提示词+技能（店铺生息体检）、自建智能体/skill', False)]),
    ([('数据分析：', True), ('全店数据复盘、商品分析、店铺诊断', False)],
     [('1688生意助手+提示词+技能（店铺生息体检）、自建智能体/skill', False)]),
]
for i, (c2, c3) in enumerate(ROWS):
    y0 = H_H + i * H_R
    cell_center(X[1], X[2], y0, y0 + H_R, c2, 32)
    cell_center(X[2], X[3], y0, y0 + H_R, c3, 30)

# right summary cell: 3 wrapped lines, centered in its own column across rows
SUM = ['全方位SEO流量卡位，', '诊断店铺短板，', '实现精细化运营增长']
for j, s in enumerate(SUM):
    d.text(((X[3] + X[4]) / 2, yc_all + (j - 1) * 58), s, font=R(34), fill=INK, anchor='mm')

im.save(f'{OUT}/GEO_MODULE_v1.png')
im.save(f'{OUT}/GEO_MODULE_v1.jpg', quality=92)
c = canvas.Canvas(f'{OUT}/GEO_MODULE_v1.pdf', pagesize=(W, H))
buf = io.BytesIO(); im.save(buf, format='JPEG', quality=92); buf.seek(0)
c.drawImage(ImageReader(buf), 0, 0, W, H); c.showPage(); c.save()
print('geo module ok', os.path.getsize(f'{OUT}/GEO_MODULE_v1.pdf'))
