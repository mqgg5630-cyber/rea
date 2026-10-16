#!/usr/bin/env python3
"""DIMMO 'SHOUHU (Guardian)' plush keychain long-image V2 — cream/cute, FULLY CENTERED layout.
13 panels, 10 photos (d1-d10), total 13548px."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, M = 1240, 88
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'deliverable', 'hotcase', 'img8')
OUT = os.path.join(ROOT, 'deliverable', 'hotcase')
OUT_SEG = os.path.join(SRC, 'final_v2')
os.makedirs(OUT_SEG, exist_ok=True)

BG = (0xFB, 0xF1, 0xDF); CARD = (0xFF, 0xFF, 0xFF)
INK = (0x4A, 0x33, 0x24); MUTE = (0x9C, 0x84, 0x68)
ACC = (0xF0, 0x70, 0x4A); ACC2 = (0x7F, 0xB5, 0xD9)

FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]
def ctext(d, y, s, f, fill, x=W // 2):
    d.text((x, y), s, font=f, fill=fill, anchor='ma')
def capsule_c(d, y, s, fg=INK, bg=CARD):
    f = B(28); w_, h_ = tw(d, s, f)
    x = (W - (w_ + 52)) / 2
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
    d.polygon([(x, y - r), (x + r * .22, y - r * .22), (x + r, y), (x + r * .22, y + r * .22),
               (x, y + r), (x - r * .22, y + r * .22), (x - r, y), (x - r * .22, y - r * .22)], fill=color)
def scallop_row(d, y, color=CARD, r=14):
    x = 30
    while x < W:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
        x += r * 2 + 40

def band(im, d, at, label, title, sub):
    """centered 268px band; at='top'/'bottom'"""
    h = im.height
    y0 = 0 if at == 'top' else h - 268
    d.rectangle((0, y0, W, y0 + 268), fill=BG)
    capsule_c(d, y0 + 54, label)
    ctext(d, y0 + 138, title, B(56), INK)
    ctext(d, y0 + 224, sub, R(30), MUTE)

def card_full(im, path, y_top, y_bottom, cy=0.5):
    photo_card(im, path, (M, y_top, W - M, y_bottom), cy=cy)

# ---------- P1 hero 1200 ----------
def p1():
    h = 1200
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 56, '源头工厂 · 300只/箱 · 混色现货')
    ctext(d, 140, '小小守护者', B(104), INK)
    ctext(d, 262, '就位。', B(104), ACC)
    sparkle(d, W // 2 - 320, 190, 22, ACC2)
    sparkle(d, W // 2 + 320, 190, 22, ACC2)
    ctext(d, 400, 'DIMMO 守护系列 · 第一代毛绒挂件', R(32), MUTE)
    photo_card(im, f'{SRC}/d1.png', ((W - 560) // 2, 468, (W + 560) // 2, 468 + 560))
    f = B(44); t = '¥8.9 起/只'
    w_, _ = tw(d, t, f)
    x = (W - (w_ + 96)) / 2
    d.rounded_rectangle((x, 1064, x + w_ + 96, 1064 + 92), 46, fill=ACC)
    d.text((x + 48, 1064 + 46), t, font=f, fill=CARD, anchor='lm')
    scallop_row(d, h - 24)
    return im

# ---------- P2 params 600 ----------
def p2():
    im = Image.new('RGB', (W, 600), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 88, '一手掌握的大小')
    y0 = 220
    cw = (W - 2 * M) // 3
    data = [('13', ' cm', '含钥匙环，整高 20cm'), ('65', ' g', '挂上包包，轻若无物'), ('300', ' 只', '一箱混色，三色齐发')]
    for i, (num, unit, lab) in enumerate(data):
        cx0 = M + i * cw
        nf, uf = B(150), B(54)
        nw_, _ = tw(d, num, nf); uw_, _ = tw(d, unit, uf)
        gx = cx0 + (cw - nw_ - 14 - uw_) / 2
        d.text((gx, y0 + 168), num, font=nf, fill=INK, anchor='ls')
        d.text((gx + nw_ + 14, y0 + 168), unit, font=uf, fill=ACC, anchor='ls')
        lw_, _ = tw(d, lab, R(30))
        d.text((cx0 + (cw - lw_) / 2, y0 + 218), lab, font=R(30), fill=MUTE)
    return im

# ---------- P3 craft 1300 ----------
def p3():
    h = 1300
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 56, '用料 · 工艺')
    ctext(d, 130, '摸着软，看着萌，全是功夫', B(52), INK)
    card_full(im, f'{SRC}/d5.png', 220, 720)
    rows = [('面料', '超柔短绒'), ('填充', '回弹PP棉'), ('工艺', '3D刺绣眼'), ('安全', '无硬配饰')]
    lines = ['像云朵摸在手里', '捏一整天也不塌', '玻璃瞳，一眼心动', '小朋友抱着啃也放心']
    bw, bh, gap = (W - 2 * M - 24) // 2, 180, 24
    for i, ((name, _), line) in enumerate(zip(rows, lines)):
        x0 = M + (i % 2) * (bw + gap)
        y0 = 748 + (i // 2) * (bh + gap)
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 22, fill=CARD)
        ctext(d, y0 + 36, name, B(38), INK, x=x0 + bw / 2)
        ctext(d, y0 + 108, line, R(27), MUTE, x=x0 + bw / 2)
    return im

# ---------- P4 face 1100 ----------
def p4():
    h = 1100
    base = cover(f'{SRC}/d4.png', W, h, cy=0.5)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    band(im, d, 'top', '表情', '对视三秒，心先妥了', '3D 立体刺绣 · 一点高光缝进眼睛里')
    return im

# ---------- P5 palm 1150 ----------
def p5():
    h = 1150
    base = cover(f'{SRC}/d3.png', W, h, cy=0.45)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    band(im, d, 'bottom', '掌心', '捧在手心，刚刚好', '13cm 不多不少 · 挂着不晃，拿着不空')
    return im

# ---------- P6 size 1050 ----------
def p6():
    h = 1050
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 54, '大小')
    ctext(d, 128, '比一挂钥匙，多两倍可爱', B(52), INK)
    card_full(im, f'{SRC}/d6.png', 224, 1050 - 44)
    return im

# ---------- P7 colors 1120 ----------
def p7():
    h = 1120
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 54, '配色')
    ctext(d, 128, '一只一个心情', B(52), INK)
    card_full(im, f'{SRC}/d2.png', 224, 880)
    chips = ['薄荷蓝 · 清凉一夏', '蜜桃粉 · 甜度满格', '奶油白 · 云朵本尊']
    f = R(30)
    widths = [tw(d, c, f)[0] for c in chips]
    pad, pill_h, gap = 52, 78, 48
    total = sum(w + pad for w in widths) + gap * 2
    x = (W - total) / 2
    for i, c in enumerate(chips):
        w_ = widths[i] + pad
        d.rounded_rectangle((x, 940, x + w_, 940 + pill_h), pill_h // 2, fill=CARD, outline=INK, width=3)
        d.text((x + pad // 2, 940 + pill_h // 2), c, font=f, fill=INK, anchor='lm')
        x += w_ + gap
    return im

# ---------- P8 scene 1080 ----------
def p8():
    h = 1080
    base = cover(f'{SRC}/d7.png', W, h, cy=0.55)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    band(im, d, 'bottom', '场景', '挂在哪儿，可爱到哪儿', '书包 / 钥匙串 / 车钥匙 / 衣襟拉链')
    return im

# ---------- P9 family 1050 ----------
def p9():
    h = 1050
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 54, '家族')
    ctext(d, 128, '六只同框，整整齐齐', B(52), INK)
    card_full(im, f'{SRC}/d8.png', 224, 1050 - 44)
    return im

# ---------- P10 custom 560 ----------
def p10():
    h = 560
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 56, '定制 / 代工')
    ctext(d, 134, '来图定制，500 只就能起步', B(52), INK)
    ctext(d, 222, '专属绣标 / 配色定制 / 贺卡套装 / 别针改件', R(30), MUTE)
    parts = ['发图', '出效果图', '打样', '量产发货']
    f = B(30)
    pw = [tw(d, p, f)[0] + 52 for p in parts]
    arrow_w = 36
    tail = tw(d, '打样 3-5 天', f)[0] + 44
    total = sum(pw) + arrow_w * 3 + tail
    x = (W - total) / 2
    y2, ph = 336, 78
    for i, p in enumerate(parts):
        d.rounded_rectangle((x, y2, x + pw[i], y2 + ph), ph // 2, fill=CARD, outline=INK, width=3)
        d.text((x + 26, y2 + ph // 2), p, font=f, fill=INK, anchor='lm')
        x += pw[i]
        if i < len(parts) - 1:
            d.text((x + 6, y2 + ph // 2), '›', font=B(34), fill=MUTE, anchor='lm')
            x += arrow_w
    d.rounded_rectangle((x, y2, x + tail, y2 + ph), ph // 2, fill=ACC)
    d.text((x + 22, y2 + ph // 2), '打样 3-5 天', font=f, fill=CARD, anchor='lm')
    return im

# ---------- P11 tag 950 ----------
def p11():
    h = 950
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 54, '正版标识')
    ctext(d, 128, '一条小织标，一半是心意', B(52), INK)
    card_full(im, f'{SRC}/d10.png', 224, 950 - 44)
    return im

# ---------- P12 spec 1308 ----------
def p12():
    h = 1308
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 54, '规格参数')
    ctext(d, 128, '一只很轻，一箱很全', B(52), INK)
    rows = [('品名', 'DIMMO 守护 · 毛绒挂件'), ('尺寸', '约 13 cm（含钥匙环 20 cm）'),
            ('克重', '约 65 g'), ('面料', '超柔短毛绒'),
            ('填充', '三维 PP 棉'), ('配色', '奶油白 / 薄荷蓝 / 蜜桃粉'),
            ('配件', '合金钥匙环 + 提花织绳'), ('工艺', '3D 刺绣 + 贴布绣'),
            ('箱规', '300 只/箱 · 支持混色'), ('定制', '500 只起订 · 打样 3-5 天')]
    rh, top = 104, 268
    for i, (k, v) in enumerate(rows):
        y = top + i * rh
        if i % 2 == 0:
            d.rectangle((M, y, W - M, y + rh), fill=CARD)
        d.text((W / 2 - 32, y + rh / 2), k, font=B(32), fill=INK, anchor='rm')
        d.text((W / 2 + 32, y + rh / 2), v, font=R(30), fill=MUTE, anchor='lm')
    return im

# ---------- P13 pack + CTA 1080 ----------
def p13():
    h = 1080
    im = Image.new('RGB', (W, h), BG); d = ImageDraw.Draw(im)
    capsule_c(d, 56, '包装 · 承诺')
    ctext(d, 130, '把守护，寄给心动的人', B(52), INK)
    card_full(im, f'{SRC}/d9.png', 224, 756)
    ctext(d, 800, '独立防尘袋 · 加厚五层瓦楞箱 · 破损 48h 包赔', R(30), MUTE)
    d.rounded_rectangle((M, 872, W - M, 1000), 64, fill=ACC)
    ctext(d, 906, '量大价优 · 代发全国', B(42), CARD)
    ctext(d, 958, '详询在线客服 ›', R(30), CARD)
    return im

panels = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13]
ims = []
for p in panels:
    ims.append(p())
total = sum(im.height for im in ims)
print('total', total)
assert total <= 14000
out = Image.new('RGB', (W, total))
y = 0
for i, im in enumerate(ims, 1):
    out.paste(im, (0, y))
    im.save(f'{OUT_SEG}/n{i:02d}.png')
    y += im.height
out.save(f'{SRC}/LONG_SHOUHU_V2.jpg', quality=88)
c = canvas.Canvas(f'{OUT}/HOTCASE_LONG_SHOUHU_V2.pdf', pagesize=(W, total))
buf = io.BytesIO(); out.save(buf, format='JPEG', quality=88); buf.seek(0)
c.drawImage(ImageReader(buf), 0, 0, W, total); c.showPage(); c.save()
print('shouhu v2 ok', os.path.getsize(f'{OUT}/HOTCASE_LONG_SHOUHU_V2.pdf'))
