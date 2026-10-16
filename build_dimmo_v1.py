#!/usr/bin/env python3
"""DIMMO cloud plush long-image V1 — cream/cute design system.
11 panels, 7 photos (d1-d7), total 12268px <= 14400."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, M = 1240, 88
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'deliverable', 'hotcase', 'img7')
OUT = os.path.join(ROOT, 'deliverable', 'hotcase')
OUT_SEG = os.path.join(SRC, 'final_v1')
os.makedirs(OUT_SEG, exist_ok=True)

BG = (0xFB, 0xF1, 0xDF)        # cream
CARD = (0xFF, 0xFF, 0xFF)      # white card
INK = (0x4A, 0x33, 0x24)       # deep cocoa
MUTE = (0x9C, 0x84, 0x68)      # warm taupe
ACC = (0xF0, 0x70, 0x4A)       # coral
ACC2 = (0x7F, 0xB5, 0xD9)      # fog blue

FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]

def capsule(d, x, y, s, fg=INK, bg=CARD):
    f = B(28)
    w_, h_ = tw(d, s, f)
    d.rounded_rectangle((x, y, x + w_ + 52, y + h_ + 42), (h_ + 42) // 2, fill=bg, outline=fg, width=3)
    d.text((x + 26, y + 21), s, font=f, fill=fg, anchor='lm')

def cover(path, w, h, cx=0.5, cy=0.5):
    im = Image.open(path).convert('RGB')
    iw, ih = im.size
    sc = max(w / iw, h / ih)
    im = im.resize((int(iw * sc + 0.5), int(ih * sc + 0.5)), Image.LANCZOS)
    return im.crop((int((im.width - w) * cx), int((im.height - h) * cy),
                    int((im.width - w) * cx) + w, int((im.height - h) * cy) + h))

def photo_card(base, path, box, cx=0.5, cy=0.5, rad=48):
    x0, y0, x1, y1 = box
    ph = cover(path, x1 - x0, y1 - y0, cx, cy)
    mask = Image.new('L', (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), rad, fill=255)
    base.paste(ph, (x0, y0), mask)

def sparkle(d, x, y, r, color):
    d.polygon([(x, y - r), (x + r * 0.22, y - r * 0.22), (x + r, y), (x + r * 0.22, y + r * 0.22),
               (x, y + r), (x - r * 0.22, y + r * 0.22), (x - r, y), (x - r * 0.22, y - r * 0.22)],
              fill=color)

def scallop_row(d, y, color=CARD, r=16, gap=64):
    x = -8
    while x < W + r * 2:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
        x += r * 2 + gap - 2 * r  # touching-ish
        x += 24

# ---------- P1 hero ----------
def p1():
    h = 1000
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 84, '源头工厂 · 48只/箱')
    d.text((M, 176), '一朵云，', font=B(126), fill=INK)
    d.text((M, 330), '抱回家', font=B(126), fill=ACC)
    sparkle(d, M + 470, 220, 26, ACC2)
    sparkle(d, M + 405, 470, 18, ACC2)
    sparkle(d, M + 490, 430, 11, (0xE9, 0xB0, 0x8E))
    d.text((M, 500), 'DIMMO 迪莫 · 云朵安抚玩偶', font=R(38), fill=MUTE)
    d.text((M, 556), '刺绣笑脸 / 三维PP棉 / A 类母婴面料', font=R(30), fill=MUTE)
    photo_card(im, f'{SRC}/d1.png', (668, 84, 1152, 568))
    f = B(78)
    txt = '¥12.9 起/只'
    w_, _ = tw(d, txt, f)
    d.rounded_rectangle((M, 632, M + w_ + 96, 632 + 136), 68, fill=ACC)
    d.text((M + 48, 632 + 68), txt, font=f, fill=CARD, anchor='lm')
    f2 = B(33)
    t2 = '48 只/箱 · 支持混色 · 现货 48h 发'
    w2, _ = tw(d, t2, f2)
    d.rounded_rectangle((M, 800, M + w2 + 88, 800 + 88), 44, fill=CARD, outline=INK, width=3)
    d.text((M + 44, 800 + 44), t2, font=f2, fill=INK, anchor='lm')
    scallop_row(d, h - 26)
    return im

# ---------- P2 params ----------
def p2():
    im = Image.new('RGB', (W, 600), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 88, '抱感参数')
    y0 = 220
    cw = (W - 2 * M) // 3
    data = [('35', ' cm', '抱满怀，大小刚刚好'), ('300', ' g', '哄睡抱着，不累手腕'), ('48', ' 只', '一箱混色，现货齐发')]
    for i, (num, unit, lab) in enumerate(data):
        cx0 = M + i * cw
        nf, uf = B(150), B(54)
        nw_, _ = tw(d, num, nf); uw_, _ = tw(d, unit, uf)
        gx = cx0 + (cw - nw_ - 14 - uw_) / 2
        d.text((gx, y0 + 168), num, font=nf, fill=INK, anchor='ls')
        d.text((gx + nw_ + 14, y0 + 168), unit, font=uf, fill=ACC, anchor='ls')
        lw_, _ = tw(d, lab, R(32))
        d.text((cx0 + (cw - lw_) / 2, y0 + 218), lab, font=R(32), fill=MUTE)
    return im

# ---------- P3 craft ----------
def p3():
    h = 1300
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 64, '用料 · 工艺')
    d.text((M, 156), '抱过一次，就知道值', font=B(56), fill=INK)
    photo_card(im, f'{SRC}/d5.png', (M, 340, M + 624, 340 + 896))
    x = M + 624 + 62
    rows = [('面料', '水晶超柔，一摸上瘾'), ('填充', '三维PP棉，回弹不塌'),
            ('工艺', '全刺绣五官，无硬配件'), ('等级', 'A类母婴标准，可机洗')]
    box_h, gap = 148, 40
    ry = 340 + (896 - (box_h * 4 + gap * 3)) // 2
    for name, line in rows:
        d.rounded_rectangle((x, ry, W - M, ry + box_h), 20, fill=CARD)
        d.rectangle((x + 24, ry + 26, x + 44, ry + 76), fill=ACC)
        d.text((x + 68, ry + 24), name, font=B(44), fill=INK)
        d.text((x + 68, ry + 92), line, font=R(30), fill=MUTE)
        ry += box_h + gap
    return im

# ---------- P4 face ----------
def p4():
    h = 1100
    base = cover(f'{SRC}/d4.png', W, h, cy=0.5)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 268), fill=BG)
    capsule(d, M, 54, '表情')
    d.text((M, 138), '看久了，会跟着笑', font=B(60), fill=INK)
    d.text((M, 224), '刺绣五官 · 无硬配件，小娃娃抱着啃也安心', font=R(32), fill=MUTE)
    return im

# ---------- P5 hug ----------
def p5():
    h = 1150
    base = cover(f'{SRC}/d3.png', W, h, cy=0.45)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, h - 268, W, h), fill=BG)
    capsule(d, M, h - 268 + 54, '大小')
    d.text((M, h - 268 + 138), '一个怀抱，刚刚好', font=B(60), fill=INK)
    d.text((M, h - 268 + 224), '哄睡 / 解压 / 陪伴，它都在岗', font=R(32), fill=MUTE)
    return im

# ---------- P6 size ----------
def p6():
    h = 1050
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 54, '尺寸')
    d.text((M, 128), '比矿泉水瓶，还高半头', font=B(56), fill=INK)
    photo_card(im, f'{SRC}/d6.png', (M, 240, W - M, 1050 - 44))
    return im

# ---------- P7 colors ----------
def p7():
    h = 1120
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 54, '配色')
    d.text((M, 128), '三个颜色，三种心情', font=B(56), fill=INK)
    photo_card(im, f'{SRC}/d2.png', (M, 232, W - M, 872))
    chips = ['云朵白 · 治愈主色', '奶茶杏 · 软萌人气', '雾霾蓝 · 安静好梦']
    f = R(32)
    widths = [tw(d, c, f)[0] for c in chips]
    pad, pill_h, gap = 56, 84, 56
    total = sum(w + pad for w in widths) + gap * 2
    x = (W - total) / 2
    for i, c in enumerate(chips):
        w_ = widths[i] + pad
        d.rounded_rectangle((x, 940, x + w_, 940 + pill_h), pill_h // 2, fill=CARD, outline=INK, width=3)
        d.text((x + pad // 2, 940 + pill_h // 2), c, font=f, fill=INK, anchor='lm')
        x += w_ + gap
    return im

# ---------- P8 scene ----------
def p8():
    h = 1080
    base = cover(f'{SRC}/d7.png', W, h, cy=0.5)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((0, h - 268, W, h), fill=BG)
    capsule(d, M, h - 268 + 54, '场景')
    d.text((M, h - 268 + 138), '它在哪，哪儿就软下来', font=B(60), fill=INK)
    d.text((M, h - 268 + 224), '床头 / 沙发 / 工位 / 通勤路上', font=R(32), fill=MUTE)
    return im

# ---------- P9 custom ----------
def p9():
    h = 560
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 56, '定制 / 代工')
    d.text((M, 134), '来图定制，100 只就能起步', font=B(54), fill=INK)
    d.text((M, 222), 'LOGO 绣字 / 专属织标 / 颜色定制 / 贺卡套装', font=R(32), fill=MUTE)
    parts = ['发图', '出效果图', '打样', '量产发货']
    f = B(32)
    x = M
    y2 = 340
    for i, p in enumerate(parts):
        w_, _ = tw(d, p, f)
        d.rounded_rectangle((x, y2, x + w_ + 56, y2 + 84), 42, fill=CARD, outline=INK, width=3)
        d.text((x + 28, y2 + 42), p, font=f, fill=INK, anchor='lm')
        x += w_ + 56
        if i < len(parts) - 1:
            d.text((x + 8, y2 + 42), '›', font=B(38), fill=MUTE, anchor='lm')
            x += 40
    t = '打样 3-5 天'
    w_, _ = tw(d, t, f)
    d.rounded_rectangle((x, y2, x + w_ + 40, y2 + 84), 42, fill=ACC)
    d.text((x + 20, y2 + 42), t, font=f, fill=CARD, anchor='lm')
    return im

# ---------- P10 spec ----------
def p10():
    h = 1308
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 54, '规格参数')
    d.text((M, 128), '一只的重量，一箱的心意', font=B(56), fill=INK)
    rows = [('品名', 'DIMMO 迪莫 · 云朵安抚玩偶'), ('尺寸', '约 35 cm（坐姿）'),
            ('克重', '约 300 g'), ('面料', '水晶超柔短毛绒'),
            ('填充', '三维 PP 棉'), ('颜色', '云朵白 / 奶茶杏 / 雾霾蓝'),
            ('安全等级', 'A 类婴幼儿级'), ('保养', '可机洗，轻柔档'),
            ('箱规', '48 只/箱 · 支持混色'), ('定制', '100 只起订 · 打样 3-5 天')]
    rh, top = 104, 268
    for i, (k, v) in enumerate(rows):
        y = top + i * rh
        if i % 2 == 0:
            d.rectangle((M, y, W - M, y + rh), fill=CARD)
        d.text((150, y + rh / 2), k, font=B(34), fill=INK, anchor='lm')
        d.text((430, y + rh / 2), v, font=R(32), fill=MUTE, anchor='lm')
    return im

# ---------- P11 pack / CTA ----------
def p11():
    h = 1000
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule(d, M, 56, '包装 · 承诺')
    d.text((M, 134), '把一朵云，寄给喜欢的人', font=B(56), fill=INK)
    d.text((M, 226), '独立防尘袋 + 加厚纸箱 · 自己发礼品，也有面', font=R(32), fill=MUTE)
    rows = [('每只独立防尘袋', '一只一袋，干净出场'), ('加厚五层瓦楞纸箱', '抗压耐摔，箱到即上架'),
            ('售后承诺', '破损 / 错发，48 小时内补发')]
    y = 316
    for name, line in rows:
        d.rounded_rectangle((M, y, W - M, y + 120), 20, fill=CARD)
        d.rectangle((M + 24, y + 24, M + 44, y + 74), fill=ACC)
        d.text((M + 68, y + 20), name, font=B(40), fill=INK)
        d.text((M + 68, y + 76), line, font=R(30), fill=MUTE)
        y += 120 + 32
    d.rounded_rectangle((M, 800, W - M, 920), 60, fill=ACC)
    d.text((M + 56, 860), '量大价优 · 代发全国', font=B(44), fill=CARD, anchor='lm')
    d.text((W - M - 56, 860), '详询在线客服 ›', font=B(40), fill=CARD, anchor='rm')
    return im

panels = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11]
ims = [p() for p in panels]
total = sum(im.height for im in ims)
print('total', total)
assert total <= 14400
out = Image.new('RGB', (W, total))
y = 0
for i, im in enumerate(ims, 1):
    out.paste(im, (0, y))
    im.save(f'{OUT_SEG}/n{i:02d}.png')
    y += im.height
out.save(f'{SRC}/LONG_DIMMO_V1.jpg', quality=88)
c = canvas.Canvas(f'{OUT}/HOTCASE_LONG_DIMMO_V1.pdf', pagesize=(W, total))
buf = io.BytesIO(); out.save(buf, format='JPEG', quality=88); buf.seek(0)
c.drawImage(ImageReader(buf), 0, 0, W, total); c.showPage(); c.save()
print('dimmo ok', os.path.getsize(f'{OUT}/HOTCASE_LONG_DIMMO_V1.pdf'))
