#!/usr/bin/env python3
"""Bag V2: slice LONG_BAG_V1.jpg -> regen N2/N3 (centered/boxed) -> drop N6
-> insert 3 new photo panels (b8 side pocket, b9 reflective, b10 handle)
-> 13 panels, 10 distinct photos, total 14160px -> V2 strip + PDF."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, M = 1240, 88
ROOT = os.path.dirname(os.path.abspath(__file__))
STRIP = os.path.join(ROOT, 'google_drive', 'LONG_BAG_V1.jpg')
SRC = os.path.join(ROOT, 'deliverable', 'hotcase', 'img6')
OUT = os.path.join(ROOT, 'deliverable', 'hotcase')
OUT_SEG = os.path.join(SRC, 'final_v2')
os.makedirs(OUT_SEG, exist_ok=True)

BG = (0x13, 0x11, 0x10); PANEL = (0x1E, 0x1A, 0x17); CREAM = (0xEF, 0xE7, 0xD8)
MUTE = (0xA2, 0x98, 0x88); ACC = (0xC0, 0x4F, 0x32)
FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]
def capsule(d, x, y, s, fg=MUTE):
    f = B(30)
    w_, h_ = tw(d, s, f)
    d.rounded_rectangle((x, y, x + w_ + 52, y + h_ + 44), (h_ + 44) // 2, outline=fg, width=3)
    d.text((x + 26, y + 22), s, font=f, fill=fg, anchor='lm')
def cover(path, w, h, cx=0.5, cy=0.5):
    im = Image.open(path).convert('RGB')
    iw, ih = im.size
    sc = max(w / iw, h / ih)
    im = im.resize((int(iw * sc + 0.5), int(ih * sc + 0.5)), Image.LANCZOS)
    x = int((im.width - w) * cx); y = int((im.height - h) * cy)
    return im.crop((x, y, x + w, y + h))
def photo_card(base, path, box, cx=0.5, cy=0.5, rad=44):
    x0, y0, x1, y1 = box
    ph = cover(path, x1 - x0, y1 - y0, cx, cy)
    mask = Image.new('L', (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), rad, fill=255)
    base.paste(ph, (x0, y0), mask)

OFFS = [0, 1360, 1960, 3320, 4470, 5710, 6330, 7480, 8040, 9140, 10540, 11690]
strip = Image.open(STRIP).convert('RGB')
assert strip.size == (W, 11690), strip.size
S = [strip.crop((0, OFFS[i], W, OFFS[i + 1])) for i in range(11)]

# --- regenerate N2: centered numerals ---
im = Image.new('RGB', (W, 600), BG); d = ImageDraw.Draw(im)
capsule(d, M, 88, '硬参数')
y0 = 220
cw = (W - 2 * M) // 3
data = [('20', ' L', '大容量，装得下'), ('780', ' g', '自重轻，省力气'), ('48', ' h', '现货即发，不压货')]
for i, (num, unit, lab) in enumerate(data):
    cx0 = M + i * cw
    nf, uf = B(150), B(54)
    nw_, _ = tw(d, num, nf); uw_, _ = tw(d, unit, uf)
    gx = cx0 + (cw - nw_ - 14 - uw_) / 2
    d.text((gx, y0 + 168), num, font=nf, fill=CREAM, anchor='ls')
    d.text((gx + nw_ + 14, y0 + 168), unit, font=uf, fill=ACC, anchor='ls')
    lw_, _ = tw(d, lab, R(34))
    d.text((cx0 + (cw - lw_) / 2, y0 + 216), lab, font=R(34), fill=MUTE)
S[1] = im

# --- regenerate N3: boxed callouts centered vs photo ---
im = S[2].copy(); d = ImageDraw.Draw(im)
x = M + 624 + 62
d.rectangle((x, 340, W - M, 340 + 896), fill=BG)
rows = [('面料', '防泼水尼龙，一抖就干'), ('拉链', '顺滑双向，万次开合'),
        ('车线', '加密双针，受力打枣'), ('底托', '加厚耐磨，随手放')]
box_h, gap = 148, 40
ry = 340 + (896 - (box_h * 4 + gap * 3)) // 2
for name, line in rows:
    d.rounded_rectangle((x, ry, W - M, ry + box_h), 20, fill=PANEL)
    d.rectangle((x + 24, ry + 26, x + 44, ry + 76), fill=ACC)
    d.text((x + 68, ry + 24), name, font=B(44), fill=CREAM)
    d.text((x + 68, ry + 92), line, font=R(30), fill=MUTE)
    ry += box_h + gap
S[2] = im

# --- new panel: side pocket (b8) ---
def side_pocket():
    im = Image.new('RGB', (W, 1030), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 66, '细节')
    d.text((M, 150), '翻盖侧袋，水杯雨伞随手放', font=B(56), fill=CREAM)
    photo_card(im, f'{SRC}/b8.png', (M, 258, W - M, 990))
    return im

# --- new panel: reflective at night (b9) ---
def reflective():
    h = 1030
    base = cover(f'{SRC}/b9.png', W, h, cy=0.55)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 268), fill=BG)
    capsule(d, M, 54, '安心')
    d.text((M, 138), '夜里，车一照就亮', font=B(60), fill=CREAM)
    d.text((M, 224), '肩带反光条 + 反光织标，夜行更安全', font=R(32), fill=MUTE)
    return im

# --- new panel: top handle (b10) ---
def handle():
    h = 1030
    base = cover(f'{SRC}/b10.png', W, h, cy=0.5)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, h - 268, W, h), fill=BG)
    capsule(d, M, h - 268 + 54, '随手')
    d.text((M, h - 268 + 138), '提着走，也很有型', font=B(60), fill=CREAM)
    d.text((M, h - 268 + 224), '织带提手，受力处打枣加固', font=R(32), fill=MUTE)
    return im

final = [S[0], S[1], S[2], S[3], S[4], side_pocket(), reflective(), S[6], S[7], handle(), S[8], S[9], S[10]]
total = sum(im.height for im in final)
print('total', total)
assert total <= 14400, total
out = Image.new('RGB', (W, total))
y = 0
for i, im in enumerate(final, 1):
    out.paste(im, (0, y))
    im.save(f'{OUT_SEG}/n{i:02d}.png')
    y += im.height
out.save(f'{OUT}/img6/LONG_BAG_V2.jpg', quality=88)
c = canvas.Canvas(f'{OUT}/HOTCASE_LONG_BAG_V2.pdf', pagesize=(W, total))
buf = io.BytesIO(); out.save(buf, format='JPEG', quality=88); buf.seek(0)
c.drawImage(ImageReader(buf), 0, 0, W, total); c.showPage(); c.save()
print('bag v2 ok', os.path.getsize(f'{OUT}/HOTCASE_LONG_BAG_V2.pdf'))
