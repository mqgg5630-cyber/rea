#!/usr/bin/env python3
"""DIMMO SHOUHU V3 style pack — 3 themes on the same 10 photos, all centered.
A cream/healing (fixed capsule + pain screen), B morandi/sage, C dopamine.
14 panels each (incl. pain->solution screen); total 14188 <= 14400.
Capsule bug fixed: text drawn at TRUE pill vertical center (anchor lm at y+H/2)."""
import io, os
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, M = 1240, 88
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'deliverable', 'hotcase', 'img8')
OUT = os.path.join(ROOT, 'deliverable', 'hotcase')

FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return FR.font_variant(size=s)
def B(s): return FB.font_variant(size=s)
def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0], bb[3] - bb[1]
def ctc(d, y, s, f, fill):
    d.text((W / 2, y), s, font=f, fill=fill, anchor='ma')
def cover(path, w, h, cx=0.5, cy=0.5):
    im = Image.open(path).convert('RGB')
    iw, ih = im.size
    sc = max(w / iw, h / ih)
    im = im.resize((int(iw * sc + 0.5), int(ih * sc + 0.5)), Image.LANCZOS)
    return im.crop((int((im.width - w) * cx), int((im.height - h) * cy),
                    int((im.width - w) * cx) + w, int((im.height - h) * cy) + h))
def photo_card(base, path, box, rad, cx=0.5, cy=0.5):
    x0, y0, x1, y1 = box
    ph = cover(path, x1 - x0, y1 - y0, cx, cy)
    mask = Image.new('L', (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, x1 - x0, y1 - y0), rad, fill=255)
    base.paste(ph, (x0, y0), mask)

THEMES = {
 'A': dict(slug='A_CREAM', bg=(0xFB,0xF1,0xDF), card=(255,255,255), ink=(0x4A,0x33,0x24),
        mute=(0x9C,0x84,0x68), acc=(0xF0,0x70,0x4A), acc2=(0x7F,0xB5,0xD9),
        rad=48, cap='pill-outline', frame=None, deco='cream',
        chip=('card','ink'), spec_white=(255,255,255), cta=None, cta_rad=64),
 'B': dict(slug='B_MORANDI', bg=(0xF5,0xF3,0xEE), card=(0xEC,0xEF,0xE4), ink=(0x3C,0x46,0x39),
        mute=(0x93,0xA0,0x8E), acc=(0x8F,0xA5,0x8C), acc2=(0xC9,0x8A,0x5E),
        rad=16, cap='soft-rect', frame=None, deco=None,
        chip=('card','ink'), spec_white=(255,255,255), cta=None, cta_rad=18),
 'C': dict(slug='C_DOPAMINE', bg=(255,255,255), card=(0xFF,0xC9,0x3C), ink=(0x1F,0x1B,0x16),
        mute=(0x8B,0x7E,0x72), acc=(0xFF,0x5C,0x39), acc2=(0x2F,0xA4,0xE7),
        rad=56, cap='solid', frame='acc', deco='confetti',
        chip=('fill','white'), spec_white=(0xFA,0xF6,0xF0), cta=None, cta_rad=999),
}

def capsule(d, y, s, T):
    f = B(28); w_, h_ = tw(d, s, f)
    H = h_ + (44 if T['cap'] == 'pill-outline' else 40)
    x = (W - (w_ + 52)) / 2
    yc = y + H / 2                      # TRUE pill vertical center -> anchored lm
    if T['cap'] == 'pill-outline':
        d.rounded_rectangle((x, y, x + w_ + 52, y + H), H // 2, fill=T['card'], outline=T['ink'], width=3)
        d.text((x + 26, yc), s, font=f, fill=T['ink'], anchor='lm')
    elif T['cap'] == 'soft-rect':
        d.rounded_rectangle((x, y, x + w_ + 48, y + H), 12, fill=T['card'])
        d.text((x + 24, yc), s, font=f, fill=T['ink'], anchor='lm')
    else:
        d.rounded_rectangle((x, y, x + w_ + 56, y + H), H // 2, fill=T['acc'])
        d.text((x + 28, yc), s, font=f, fill=(255,255,255), anchor='lm')

def sparkle(d, x, y, r, color):
    d.polygon([(x, y-r*2), (x+r*.44, y-r*.44), (x+r*2, y), (x+r*.44, y+r*.44),
               (x, y+r*2), (x-r*.44, y+r*.44), (x-r*2, y), (x-r*.44, y-r*.44)], fill=color)

def scallop(d, y, color=(255,255,255), r=14):
    x = 30
    while x < W:
        d.ellipse((x-r, y-r, x+r, y+r), fill=color); x += r*2 + 40

def confetti(d, T, spots):
    cols = [T['acc'], T['acc2'], (0xFF,0xC9,0x3C)]
    for i, (x, y, r) in enumerate(spots):
        d.ellipse((x-r, y-r, x+r, y+r), fill=cols[i % 3])

def pain_rows(d, T, top=250):
    rows = [('礼物总差最后一口心意', '会眨眼的小守护，刚刚好'),
            ('小挂件用两天就塌又脏', '回弹 PP 棉，脏了轻轻一冲'),
            ('钥匙撞包叮当，还划表面', '毛绒外衣，一挂就安静')]
    rh = 104
    for i, (pain, fix) in enumerate(rows):
        y = top + i * (rh + 20)
        if T['deco'] == 'confetti':
            cols = [T['acc'], T['acc2'], (0xFF,0xC9,0x3C)]
            d.rounded_rectangle((M, y, W - M, y + rh), 32, fill=cols[i % 3])
            fg_p = (255, 230, 222) if i == 0 else ((224, 240, 250) if i == 1 else (66, 52, 16))
            fg_f = (255,255,255) if i < 2 else (0x1F,0x1B,0x16)
        else:
            d.rounded_rectangle((M, y, W - M, y + rh), rh // 2 if T['deco'] == 'cream' else 20,
                                fill=T['card'])
            fg_p, fg_f = T['mute'], T['ink']
        f1, f2 = R(30), B(30)
        w1, _ = tw(d, pain, f1); w2, _ = tw(d, fix, f2); wa, _ = tw(d, '  ›  ', B(34))
        x = (W - (w1 + wa + w2)) / 2
        yc = y + rh / 2
        d.text((x, yc), pain, font=f1, fill=fg_p, anchor='lm')
        d.text((x + w1, yc), '  ›  ', font=B(34), fill=(T['acc'] if T['deco'] != 'confetti' else fg_f), anchor='lm')
        d.text((x + w1 + wa, yc), fix, font=f2, fill=fg_f, anchor='lm')

def params_strip(d, y0, T, data):
    cw = (W - 2 * M) // 3
    for i, (num, unit, lab) in enumerate(data):
        cx0 = M + i * cw
        nf = B(150); uf = B(54)
        nw_, _ = tw(d, num, nf); uw_, _ = tw(d, unit, uf)
        gx = cx0 + (cw - nw_ - 14 - uw_) / 2
        d.text((gx, y0 + 168), num, font=nf, fill=T['ink'], anchor='ls')
        d.text((gx + nw_ + 14, y0 + 168), unit, font=uf, fill=T['acc'], anchor='ls')
        lw_, _ = tw(d, lab, R(30))
        d.text((cx0 + (cw - lw_) / 2, y0 + 218), lab, font=R(30), fill=T['mute'])

def chips_row(d, y, labels, T, f=None, pill_h=78, pad=52, gap=48, outline=True):
    f = f or R(30)
    widths = [tw(d, c, f)[0] for c in labels]
    total = sum(wd + pad for wd in widths) + gap * (len(labels) - 1)
    x = (W - total) / 2
    for i, c in enumerate(labels):
        wd = widths[i] + pad
        if T['chip'][0] == 'fill':
            cols = [T['acc'], T['acc2'], (0xFF,0xC9,0x3C)]
            d.rounded_rectangle((x, y, x + wd, y + pill_h), pill_h // 2, fill=cols[i % 3])
            fg = (255,255,255) if i % 3 != 2 else (0x1F,0x1B,0x16)
        else:
            d.rounded_rectangle((x, y, x + wd, y + pill_h), pill_h // 2, fill=T['card'],
                                outline=(T['ink'] if outline else None), width=3 if outline else 1)
            fg = T['ink']
        d.text((x + pad // 2, y + pill_h / 2), c, font=f, fill=fg, anchor='lm')
        x += wd + gap

def band(d, h, at, T, label, title, sub):
    y0 = 0 if at == 'top' else h - 268
    if T['deco'] == 'confetti':
        d.rectangle((0, y0, W, y0 + 268), fill=T['acc'])
        capT = dict(T, cap='pill-outline')
        f = B(28); w_, h_ = tw(d, label, f); H = h_ + 40
        x = (W - (w_ + 52)) / 2
        d.rounded_rectangle((x, y0+46, x+w_+52, y0+46+H), H//2, fill=(255,255,255))
        d.text((x+26, y0+46+H/2), label, font=f, fill=T['acc'], anchor='lm')
        ctc(d, y0 + 128, title, B(56), (255,255,255))
        ctc(d, y0 + 214, sub, R(30), (255, 233, 226))
    else:
        d.rectangle((0, y0, W, y0 + 268), fill=T['bg'])
        if T['deco'] is None:
            d.rectangle((0, y0 if at == 'top' else y0 + 268 - 10, W,
                         y0 + 10 if at == 'top' else y0 + 268), fill=T['acc'])
        capsule(d, y0 + 46, label, T)
        ctc(d, y0 + 130, title, B(56), T['ink'])
        ctc(d, y0 + 216, sub, R(30), T['mute'])

def craft_2x2(d, top, T, rows):
    bw, bh, gap = (W - 2 * M - 24) // 2, 180, 24
    for i, (name, line) in enumerate(rows):
        x0 = M + (i % 2) * (bw + gap)
        y0 = top + (i // 2) * (bh + gap)
        if T['deco'] == 'confetti':
            cols = [(0xFF,0x5C,0x39), (0x2F,0xA4,0xE7), (0xFF,0xC9,0x3C), (0x1F,0x1B,0x16)]
            fgs = [((255,255,255),(255,229,224)), ((255,255,255),(219,240,251)),
                   ((0x46,0x36,0x0A),(0x7A,0x63,0x22)), ((255,255,255),(215,215,215))]
            d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 40, fill=cols[i])
            fg1, fg2 = fgs[i]
        else:
            d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 40 if T['deco'] == 'cream' else 22,
                                fill=T['card'])
            fg1, fg2 = T['ink'], T['mute']
        ctc(d, y0 + 36, name, B(38), fg1) if False else d.text((x0 + bw/2, y0 + 36),
            name, font=B(38), fill=fg1, anchor='ma')
        d.text((x0 + bw/2, y0 + 104), line, font=R(27), fill=fg2, anchor='ma')

def spec_table(d, top, T, rows):
    rh = 104
    for i, (k, v) in enumerate(rows):
        y = top + i * rh
        if i % 2 == 0:
            d.rectangle((M, y, W - M, y + rh), fill=T['spec_white'])
        key_fg = T['acc'] if T['deco'] == 'confetti' else T['ink']
        d.text((W / 2 - 32, y + rh / 2), k, font=B(32), fill=key_fg, anchor='rm')
        d.text((W / 2 + 32, y + rh / 2), v, font=R(30), fill=T['mute'], anchor='lm')

def price_badge(d, y, T, txt='¥8.9 起/只'):
    if T['deco'] == 'confetti':
        layer = Image.new('RGBA', (560, 190), (0,0,0,0))
        dl = ImageDraw.Draw(layer)
        dl.rounded_rectangle((8, 8, 552, 182), 87, fill=(0xFF,0xC9,0x3C), outline=T['acc'], width=8)
        f = B(52); w_, h_ = tw(dl, txt, f)
        dl.text(((560 - w_) / 2, 95), txt, font=f, fill=T['acc'], anchor='mm')
        rot = layer.rotate(-6, expand=True, resample=Image.BICUBIC)
        x = (W - rot.width) / 2
        return ('rot', rot, x, y)
    else:
        f = B(44); w_, _ = tw(d, txt, f)
        PW = w_ + 96; PH = 92 if T['deco'] == 'cream' else 84
        x = (W - PW) / 2
        d.rounded_rectangle((x, y, x + PW, y + PH),
                            PH // 2 if T['deco'] == 'cream' else 14, fill=T['acc'])
        d.text((x + PW/2, y + PH/2), txt, font=f, fill=(255,255,255), anchor='mm')

def framed_card(im, path, box, T, cy=0.5, caption=None):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(im)
    if T.get('frame'):
        cw = T['acc'] if y0 % 2 == 0 or True else T['acc2']
        d.rounded_rectangle((x0-6, y0-6, x1+6, y1+6), T['rad'] + 18, fill=T['acc'])
    photo_card(im, path, (x0, y0, x1, y1), T['rad'], cy=cy)
    if caption:
        strip_h = 64
        d.rounded_rectangle((x0, y1, x1, y1 + strip_h), T['rad'], fill=T['card'])
        d.text(((x0 + x1)/2, y1 + strip_h/2), caption, font=B(28), fill=T['ink'], anchor='mm')

# ---------- panel builders (theme-generic) ----------
DATA_PARAMS = [('13', ' cm', '含钥匙环，整高 20cm'), ('65', ' g', '挂上包包，轻若无物'), ('300', ' 只', '一箱混色，三色齐发')]
ROWS_CRAFT = [('面料', '像云朵摸在手里'), ('填充', '捏一整天也不塌'), ('工艺', '玻璃瞳，一眼心动'), ('安全', '小朋友抱着啃也放心')]
ROWS_SPEC = [('品名', 'DIMMO 守护 · 毛绒挂件'), ('尺寸', '约 13 cm（含钥匙环 20 cm）'),
             ('克重', '约 65 g'), ('面料', '超柔短毛绒'), ('填充', '三维 PP 棉'),
             ('配色', '奶油白 / 薄荷蓝 / 蜜桃粉'), ('配件', '合金钥匙环 + 提花织绳'),
             ('工艺', '3D 刺绣 + 贴布绣'), ('箱规', '300 只/箱 · 支持混色'), ('定制', '500 只起订 · 打样 3-5 天')]

def p_hero(T):
    h = 1200
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 56, '源头工厂 · 300只/箱 · 混色现货', T)
    if T['deco'] == 'cream':
        ctc(d, 140, '小小守护者', B(104), T['ink']); ctc(d, 262, '就位。', B(104), T['acc'])
        sparkle(d, W/2 - 320, 190, 11, T['acc2']); sparkle(d, W/2 + 320, 190, 11, T['acc2'])
    elif T['deco'] == 'confetti':
        ctc(d, 150, '小小守护者', B(104), T['ink'])
        bb = d.textbbox((0, 0), '就位。', font=B(104), anchor='ma')
        gtop, gbot = 272 + bb[1], 272 + bb[3]
        d.rounded_rectangle(((W-tw(d, '就位。', B(104))[0])/2 - 28, gtop - 14,
                             (W+tw(d, '就位。', B(104))[0])/2 + 28, gbot + 16), 24, fill=(0xFF,0xC9,0x3C))
        ctc(d, 272, '就位。', B(104), T['ink'])
    else:
        ctc(d, 150, '小小守护者', B(106), T['ink']); ctc(d, 280, '就位。', B(106), T['acc'])
    sub = 'DIMMO 守护系列 · 全新首发毛绒挂件'
    ctc(d, 410 if T['deco'] != 'cream' else 400, sub, R(32) if T['deco'] == 'cream' else R(30), T['mute'])
    card_y = 480 if T['deco'] != 'cream' else 468
    framed_card(im, f'{SRC}/d1.png', ((W-560)//2, card_y, (W+560)//2, card_y + 520), T,
                caption='DIMMO 守护 · 云朵白' if T['deco'] is None else None)
    if T['deco'] == 'confetti':
        confetti(d, T, [(300, 500, 10), (950, 520, 12), (340, 1060, 9), (930, 1050, 10)])
        badge = price_badge(d, 932, T)
        _, rot, x, y = badge
        im.paste(rot, (int(x), y), rot)
    else:
        price_badge(d, 1072 if T['deco'] == 'cream' else 1080, T)
    if T['deco'] == 'cream':
        scallop(d, h - 24)
    return im

def p_pain(T):
    h = 640
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 56, '为什么是它', T)
    ctc(d, 128, '解决三件小烦恼', B(52), T['ink'])
    pain_rows(d, T, top=244)
    return im

def p_params(T):
    im = Image.new('RGB', (W, 600), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 88, '一手掌握的大小', T)
    params_strip(d, 220, T, DATA_PARAMS)
    return im

def p_craft(T):
    h = 1300
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 56, '用料 · 工艺', T)
    ctc(d, 130, '摸着软，看着萌，全是功夫', B(52), T['ink'])
    if T.get('frame'):
        framed_card(im, f'{SRC}/d5.png', (M+40, 230, W-M-40, 700), T)
    else:
        photo_card(im, f'{SRC}/d5.png', (M, 230, W-M, 720), T['rad'])
    top = 770 if T.get('frame') else 748
    craft_2x2(d, top, T, ROWS_CRAFT)
    return im

def p_fullbleed(T, photo, at, label, title, sub, cy=0.5, h=1100):
    base = cover(f'{SRC}/{photo}.png', W, h, cy=cy)
    im = Image.new('RGB', (W, h)); im.paste(base, (0, 0))
    d = ImageDraw.Draw(im)
    band(d, h, at, T, label, title, sub)
    return im

def p_card_panel(T, h, photo, label, title, chips=None, chip_y=None, caption=None, cy=0.5):
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 54, label, T)
    ctc(d, 128, title, B(52), T['ink'])
    y2 = (chip_y - 40) if chips else (h - 44)
    framed_card(im, f'{SRC}/{photo}.png', (M+40 if T.get('frame') else M, 224,
                W-M-40 if T.get('frame') else W - M, y2), T, cy=cy,
                caption=caption if T['deco'] is None else None)
    if chips:
        chips_row(d, chip_y, chips, T)
    return im

def p_custom(T):
    h = 560
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 56, '定制 / 代工', T)
    ctc(d, 134, '来图定制，500 只就能起步', B(52), T['ink'])
    ctc(d, 222, '专属绣标 / 配色定制 / 贺卡套装 / 别针改件', R(30), T['mute'])
    parts = ['发图', '出效果图', '打样', '量产发货']
    f = B(30)
    pw = [tw(d, p, f)[0] + 52 for p in parts]
    arrow_w = 36
    tailw = tw(d, '打样 3-5 天', f)[0] + 44
    x = (W - (sum(pw) + arrow_w * 3 + tailw)) / 2
    y2, ph = 336, 78
    for i, p in enumerate(parts):
        if T['deco'] == 'confetti':
            d.rounded_rectangle((x, y2, x + pw[i], y2 + ph), ph//2, fill=(0xFA,0xF6,0xF0), outline=T['ink'], width=3)
        else:
            d.rounded_rectangle((x, y2, x + pw[i], y2 + ph), ph // 2 if T['deco']=='cream' else 14,
                                fill=T['card'], outline=T['ink'] if T['deco']=='cream' else None,
                                width=3 if T['deco']=='cream' else 1)
        d.text((x + 26, y2 + ph/2), p, font=f, fill=T['ink'], anchor='lm')
        x += pw[i]
        if i < len(parts) - 1:
            d.text((x + 6, y2 + ph/2), '›', font=B(34), fill=T['mute'], anchor='lm')
            x += arrow_w
    d.rounded_rectangle((x, y2, x + tailw, y2 + ph), ph//2, fill=T['acc'] if T['deco']!='confetti' else T['acc2'])
    d.text((x + 22, y2 + ph/2), '打样 3-5 天', font=f, fill=(255,255,255), anchor='lm')
    return im

def p_spec(T):
    h = 1308
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 54, '规格参数', T)
    ctc(d, 128, '一只很轻，一箱很全', B(52), T['ink'])
    spec_table(d, 268, T, ROWS_SPEC)
    return im

def p_cta(T):
    h = 1080
    im = Image.new('RGB', (W, h), T['bg']); d = ImageDraw.Draw(im)
    capsule(d, 56, '包装 · 承诺', T)
    ctc(d, 130, '把守护，寄给心动的人', B(52), T['ink'])
    photo_card(im, f'{SRC}/d9.png', (M, 224, W - M, 760), T['rad'])
    ctc(d, 806, '独立防尘袋 · 加厚五层瓦楞箱 · 破损 48h 包赔', R(30), T['mute'])
    bar_fill = T['acc'] if T['deco'] != 'confetti' else T['ink']
    d.rounded_rectangle((M, 874, W - M, 1002), T['cta_rad'] if T['cta_rad'] != 999 else 64, fill=bar_fill)
    ctc(d, 906, '量大价优 · 代发全国', B(42), (0xFF,0xC9,0x3C) if T['deco']=='confetti' else (255,255,255))
    ctc(d, 960, '详询在线客服 ›', R(30), (255,255,255))
    return im

def build_theme(key, T):
    p = [p_hero, p_pain, p_params, p_craft,
         lambda T=T: p_fullbleed(T, 'd4', 'top', '表情', '对视三秒，心先妥了', '3D 立体刺绣 · 一点高光缝进眼睛里', cy=0.5, h=1100),
         lambda T=T: p_fullbleed(T, 'd3', 'bottom', '掌心', '捧在手心，刚刚好', '13cm 不多不少 · 挂着不晃，拿着不空', cy=0.45, h=1150),
         lambda T=T: p_card_panel(T, 1050, 'd6', '大小', '比一挂钥匙，多两倍可爱'),
         lambda T=T: p_card_panel(T, 1120, 'd2', '配色', '一只一个心情',
                    chips=['薄荷蓝 · 清凉一夏', '蜜桃粉 · 甜度满格', '奶油白 · 云朵本尊'], chip_y=940),
         lambda T=T: p_fullbleed(T, 'd7', 'bottom', '场景', '挂在哪儿，可爱到哪儿', '书包 / 钥匙串 / 车钥匙 / 衣襟拉链', cy=0.55, h=1080),
         lambda T=T: p_card_panel(T, 1050, 'd8', '家族', '六只同框，整整齐齐', caption='三色混装 · 一箱齐发'),
         p_custom,
         lambda T=T: p_card_panel(T, 950, 'd10', '正版标识', '一条小织标，一半是心意'),
         p_spec, p_cta]
    ims = [fn(T) for fn in p]
    total = sum(i.height for i in ims)
    print(key, 'total', total)
    assert total <= 14400, total
    outdir = os.path.join(SRC, f'final_v3{key}')
    os.makedirs(outdir, exist_ok=True)
    strip = Image.new('RGB', (W, total))
    y = 0
    for i, im in enumerate(ims, 1):
        strip.paste(im, (0, y)); im.save(f'{outdir}/n{i:02d}.png'); y += im.height
    jpg = f'{SRC}/LONG_SHOUHU_V3_{key}.jpg'
    strip.save(jpg, quality=88)
    strip.resize((750, int(total * 750 / W)), Image.LANCZOS).save(f'{SRC}/LONG_SHOUHU_V3_{key}_750.jpg', quality=88)
    pdf = f'{OUT}/HOTCASE_LONG_SHOUHU_V3_{key}.pdf'
    c = canvas.Canvas(pdf, pagesize=(W, total))
    buf = io.BytesIO(); strip.save(buf, format='JPEG', quality=88); buf.seek(0)
    c.drawImage(ImageReader(buf), 0, 0, W, total); c.showPage(); c.save()
    print(key, 'pdf', os.path.getsize(pdf))

for k, T in THEMES.items():
    build_theme(k, T)
print('v3 pack ok')
