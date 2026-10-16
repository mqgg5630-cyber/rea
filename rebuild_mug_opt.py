#!/usr/bin/env python3
"""Rebuild mug V7 optimized: slice aligned strip, regenerate N2 (centered
numerals) and N3 (boxed callouts, vertically centered), restitch + PDF."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, M = 1240, 88
ROOT = os.path.dirname(os.path.abspath(__file__))
STRIP = os.path.join(ROOT, 'google_drive', 'LONG_MUG_V7_对齐版.jpg')
OUT = os.path.join(ROOT, 'deliverable', 'hotcase')
os.makedirs(os.path.join(OUT, 'img5'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'img5', 'final_v7o'), exist_ok=True)

BG = (0x13, 0x11, 0x10); PANEL = (0x1E, 0x1A, 0x17); CREAM = (0xEF, 0xE7, 0xD8)
MUTE = (0xA2, 0x98, 0x88); ACC = (0xC0, 0x4F, 0x32)
FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]

OFFS = [0, 1360, 1960, 3320, 4470, 5620, 6860, 7480, 8540, 9640, 10948, 12098]
strip = Image.open(STRIP).convert('RGB')
assert strip.size == (W, 12098), strip.size
segs = [strip.crop((0, OFFS[i], W, OFFS[i + 1])) for i in range(11)]

# N2 — centered numeral strip
im = Image.new('RGB', (W, 600), BG); d = ImageDraw.Draw(im)
f = B(30)
s = '硬参数'
w_, h_ = tw(d, s, f)
d.rounded_rectangle((M, 88, M + w_ + 52, 88 + h_ + 44), (h_ + 44) // 2, outline=MUTE, width=3)
d.text((M + 26, 88 + 22), s, font=f, fill=MUTE, anchor='lm')
y0 = 220
cw = (W - 2 * M) // 3
data = [('350', 'ml', '黄金容量，一杯刚好'),
        ('282', 'g', '轻，但不失手感'),
        ('48', '只', '起订，支持混色混款')]
for i, (num, unit, lab) in enumerate(data):
    cx0 = M + i * cw
    nf, uf = B(150), B(54)
    nw_, _ = tw(d, num, nf); uw_, _ = tw(d, unit, uf)
    gx = cx0 + (cw - nw_ - 14 - uw_) / 2
    d.text((gx, y0 + 168), num, font=nf, fill=CREAM, anchor='ls')
    d.text((gx + nw_ + 14, y0 + 168), unit, font=uf, fill=ACC, anchor='ls')
    lw_, _ = tw(d, lab, R(34))
    d.text((cx0 + (cw - lw_) / 2, y0 + 216), lab, font=R(34), fill=MUTE)
segs[1] = im

# N3 — boxed callouts centered vs photo card
im = segs[2].copy(); d = ImageDraw.Draw(im)
x = M + 624 + 62
d.rectangle((x, 340, W - M, 340 + 896), fill=BG)
rows = [('杯口', '圆润卷边，不硌唇'),
        ('杯身', '立体浮雕，手工开模'),
        ('把手', '拱形加宽，稳握不烫'),
        ('杯底', '加厚圈足，防滑稳放')]
box_h, gap = 148, 40
ry = 340 + (896 - (box_h * 4 + gap * 3)) // 2
for name, line in rows:
    d.rounded_rectangle((x, ry, W - M, ry + box_h), 20, fill=PANEL)
    d.rectangle((x + 24, ry + 26, x + 44, ry + 76), fill=ACC)
    d.text((x + 68, ry + 24), name, font=B(44), fill=CREAM)
    d.text((x + 68, ry + 92), line, font=R(30), fill=MUTE)
    ry += box_h + gap
segs[2] = im

total = 12098
out_strip = Image.new('RGB', (W, total))
y = 0
for i, s_ in enumerate(segs, 1):
    out_strip.paste(s_, (0, y))
    s_.save(f"{OUT}/img5/final_v7o/n{i:02d}.png")
    y += s_.height
out_strip.save(f'{OUT}/img5/LONG_MUG_V7_OPT.jpg', quality=88)
c = canvas.Canvas(f'{OUT}/HOTCASE_LONG_MUG_V7_OPT.pdf', pagesize=(W, total))
buf = io.BytesIO(); out_strip.save(buf, format='JPEG', quality=88); buf.seek(0)
c.drawImage(ImageReader(buf), 0, 0, W, total); c.showPage(); c.save()
print('mug opt ok', os.path.getsize(f'{OUT}/HOTCASE_LONG_MUG_V7_OPT.pdf'))
