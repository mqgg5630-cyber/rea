#!/usr/bin/env python3
# DIMMO「守护」毛绒挂件 · 长图视觉探索 V1 —— 热情方格子 Editorial Grid
# 结构：HERO / 参数 / 痛点 / 工艺 / 掌心 / 微距 / 场景 / 配色 / 全家福 / 吊牌 / 包装 / 规格 / 信任 / CTA
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, M = 1240, 88
IMG = 'deliverable/hotcase/img8'
FONT_R = '/tmp/fonts/NotoSansSC-Regular.ttf'
FONT_B = '/tmp/fonts/NotoSansSC-Bold.ttf'

THEMES = {
 'A': dict(  # 奶油暖阳
  BG=(253,247,238), PAPER=(255,252,246), CARD=(255,255,255),
  INK=(0x3a,0x2c,0x22), MUTED=(0x8a,0x7a,0x6c),
  ACCENT=(0xe8,0x7d,0x3e), ACC2=(0xf3,0xbe,0x8f), CHIP=(0xf6,0xe3,0xc8),
  STRIP=(0xf3,0xbe,0x8f), PAIN=(0xc4,0xb2,0xa1),
  BUTTON=(0xe8,0x7d,0x3e), PHOTDBG='color', GRID=(0xf0,0xe3,0xd0),
 ),
 'B': dict(  # 蜜桃粉格
  BG=(255,240,244), PAPER=(255,247,249), CARD=(255,255,255),
  INK=(0x4a,0x2a,0x33), MUTED=(0xa0,0x82,0x8a),
  ACCENT=(0xd9,0x5b,0x7a), ACC2=(0xf3,0xa7,0xbb), CHIP=(0xfa,0xd9,0xe1),
  STRIP=(0xf3,0xa7,0xbb), PAIN=(0xd3,0xb0,0xb8),
  BUTTON=(0xd9,0x5b,0x7a), PHOTDBG='photo', GRID=(0xf2,0xda,0xe0),
 ),
 'C': dict(  # 海盐蓝格
  BG=(236,241,247),
  PAPER=(243,247,251), CARD=(255,255,255),
  INK=(0x24,0x32,0x43), MUTED=(0x74,0x85,0x97),
  ACCENT=(0x2f,0x6f,0xaf), ACC2=(0x9c,0xc3,0xe4), CHIP=(0xd8,0xe7,0xf4),
  STRIP=(0x1e,0x2a,0x38), PAIN=(0xa9,0xb8,0xc7),
  BUTTON=(0x1e,0x2a,0x38), PHOTDBG='photo', GRID=(0xd5,0xe0,0xea),
 ),
}

def FS(p): return ImageFont.truetype(FONT_B, p)
def FR(p): return ImageFont.truetype(FONT_R, p)

def measure(d, s, f):
    bb = d.textbbox((0,0), s, font=f)
    return bb[2]-bb[0], bb[3]-bb[1]

def C(d, s, cx, y, f, fill):
    d.text((cx, y), s, font=f, fill=fill, anchor='ma')
    return y + f.size

def chip(d, x, y, s, f, fg, bg, pad=(26,12), anchor='la'):
    w, h = measure(d, s, f)
    w += pad[0]*2; h += pad[1]*2
    if anchor == 'ma':  # 仅水平中心锚才左移半个宽（la 是左上角锚，绝不能动）
        x -= w//2
    d.rounded_rectangle((x, y, x+w, y+h), radius=(h)//2, fill=bg)
    d.text((x+pad[0], y+pad[1]), s, font=f, fill=fg, anchor='la')
    return w, h

def scallop(d, y, color, r=22, step=44):
    x = 0
    while x < W+step:
        d.ellipse((x, y-r, x+step, y+r), fill=color)
        x += step

def grid_bg(im, t):
    d = ImageDraw.Draw(im)
    for x in range(0, W, 62):
        d.line((x, 0, x, im.height), fill=t['GRID'], width=2)
    for y in range(0, im.height, 62):
        d.line((0, y, W, y), fill=t['GRID'], width=2)
    return d

def paste_photo(im, path, y, h=None, blend_bg=None, blend=0):
    ph = Image.open(path).convert('RGB')
    if h is None:
        h = ph.height
    if ph.height != h:  # center-crop to target height
        top = max(0, (ph.height - h)//2)
        ph = ph.crop((0, top, ph.width, top+h))
    im.paste(ph, (0, y))
    if blend:  # soft edge into bg color
        ov = Image.new('L', (1, blend))
        for i in range(blend):
            ov.putpixel((0, i), int(255*(1-i/blend)))
        top_g = Image.new('RGB', (W, blend), blend_bg)
        im.paste(top_g, (0, y), ov.resize((W, blend)))
        bot_g = Image.new('RGB', (W, blend), blend_bg)
        im.paste(bot_g, (0, y+h-blend), ov.transpose(Image.FLIP_TOP_BOTTOM).resize((W, blend)))
    return h

def caption_strip(d, y, t, tag, title, sub):
    d.rectangle((0, y, W, y+210), fill=t['CARD'])
    chip(d, W//2, y+26, tag, FR(26), t['ACCENT'], t['CHIP'], anchor='ma')
    C(d, title, W//2, y+84, FS(44), t['INK'])
    C(d, sub, W//2, y+152, FR(28), t['MUTED'])
    return y+210

def strike(d, cx, cy, s, f, color):
    """cy = 文本垂直中心（anchor mm），删除线过字心。"""
    w, _ = measure(d, s, f)
    d.text((cx, cy), s, font=f, fill=color, anchor='mm')
    d.line((cx-w//2-8, cy+2, cx+w//2+8, cy+2), fill=color, width=4)

def build(name, t, out):
    H = 15000
    im = Image.new('RGB', (W, H), t['BG'])
    grid_bg(im, t)
    d = ImageDraw.Draw(im)
    y = 0

    # ---------- HERO ----------
    photo_hero = t['PHOTDBG'] == 'photo'
    panel_h = 790
    if photo_hero:
        ph = paste_photo(im, f'{IMG}/d1.png', 0, h=460)
        d = ImageDraw.Draw(im)
        d.rectangle((0, ph, W, ph+panel_h), fill=t['INK'])
        hero_h = ph + panel_h
    else:
        d.rectangle((0, 0, W, 1250), fill=t['BG'])
        scallop(d, 0, t['CARD'])
        paste_photo(im, f'{IMG}/d1.png', 150, h=430, blend_bg=t['BG'], blend=70)
        d = ImageDraw.Draw(im)
        hero_h = 1250
    chip(d, 96, 96, 'DIMMO 守护系列', FR(28), t['CARD'], (0,0,0) if photo_hero else t['INK'])
    chip(d, W-96-340, 96, '第一代 · 毛绒挂件', FR(28), t['CARD'], t['ACCENT'])
    ty = (ph + 70) if photo_hero else 640
    tcol = t['CARD'] if photo_hero else t['INK']
    mcol = tuple(int(a*0.82+b*0.18) for a, b in zip(tcol, t['BG'])) if not photo_hero else tuple(min(255, int(c*0.62 + 255*0.38)) for c in t['INK'])
    C(d, '把你那份守护，', W//2, ty, FS(112), tcol)
    C(d, '挂在身上', W//2, ty+128, FS(112), tcol)
    C(d, '你好，我叫守护', W//2, ty+276, FS(52), tcol)
    C(d, '源头工厂 · 现货 24h 发 · 支持混色混批 · 定制 500 只起', W//2, ty+366, FR(32), mcol)
    bx, by, br = W-268, ty+560, 118
    d.ellipse((bx-br, by-br, bx+br, by+br), fill=t['BUTTON'])
    C(d, '¥8.9', bx, by-58, FS(58), t['CARD'])
    C(d, '起/只', bx, by+16, FR(28), t['CARD'])
    y = hero_h

    # ---------- 硬参数 ----------
    C(d, '一眼看懂它', W//2, y+74, FS(64), t['INK'])
    tw_, _ = measure(d, '一眼看懂它', FS(64))
    d.line((W//2-tw_//2, y+166, W//2+tw_//2, y+166), fill=t['ACCENT'], width=6)
    rows = [('尺寸', '约 13 cm（坐姿）'), ('克重', '约 65 g'), ('面料', '超柔短毛绒'),
            ('填充', '三维 PP 棉 · 回弹定型'), ('配色', '云朵白 · 蜜桃粉 · 薄荷蓝'),
            ('箱规', '300 只/箱 · 支持混色')]
    ty = y+210
    d.rounded_rectangle((M, ty, W-M, ty+len(rows)*86+40), radius=36, fill=t['CARD'])
    for i, (k, v) in enumerate(rows):
        ry = ty+20+i*86
        d.text((W//2-60, ry+43), k, font=FR(30), fill=t['MUTED'], anchor='rm')
        d.text((W//2+60, ry+43), v, font=FS(32), fill=t['INK'], anchor='lm')
        if i: d.line((M+60, ry, W-M-60, ry), fill=t['GRID'], width=2)
    y = ty+len(rows)*86+40+96

    # ---------- 痛点 ----------
    d.rounded_rectangle((M, y, W-M, y+640), radius=48, fill=t['CARD'])
    chip(d, W//2, y+46, '痛点', FR(26), t['CARD'], t['ACCENT'], anchor='ma')
    C(d, '挂件踩过的坑，我们都懂', W//2, y+104, FS(52), t['INK'])
    pains = [('太素太普通，送不出手', '他有大眼睛，还有名字和性格'),
             ('硬配饰刮包还硌手', '全都是绣上去的，贴背也安心'),
             ('两天下线，三周走样', '满脸回弹，怎么揉都不塌')]
    py = y+196
    for p, s in pains:
        strike(d, W//2-190, py+20, p, FR(30), t['PAIN'])
        d.text((W//2+22, py+20), '›', font=FS(38), fill=t['ACCENT'], anchor='mm')
        d.text((W//2+250, py+20), s, font=FS(32), fill=t['INK'], anchor='mm')
        py += 148
    y += 640+96

    # ---------- 工艺（面料微距 + 2x2） ----------
    ph = paste_photo(im, f'{IMG}/d5.png', y, h=480, blend_bg=t['BG'], blend=60)
    d = ImageDraw.Draw(im)
    y += ph
    chip(d, W//2, y+44, '工艺', FR(26), t['ACCENT'], t['CHIP'], anchor='ma')
    C(d, '从脸到脚，都是手工活', W//2, y+98, FS(52), t['INK'])
    crafts = [('面', '超柔短毛绒', '手感像云朵，蹭脸上不想停'),
              ('绣', '3D 立体刺绣', '眉眼神情在线，连线头都藏着'),
              ('棉', '三维 PP 棉', '回弹成型快，揉成一团也能站起来'),
              ('安', '全刺绣五官', '没有硬配饰，贴背包蹭衣服都 OK')]
    gx, gy = W//2-518, y+186
    for i, (g, a, b) in enumerate(crafts):
        cx0 = gx + (i%2)*536; cy0 = gy + (i//2)*196
        d.rounded_rectangle((cx0, cy0, cx0+518, cy0+176), radius=28, fill=t['CARD'])
        d.rounded_rectangle((cx0+28, cy0+44, cx0+116, cy0+132), radius=22, fill=t['CHIP'])
        C(d, g, cx0+72, cy0+64, FS(40), t['ACCENT'])
        d.text((cx0+140, cy0+56), a, font=FS(32), fill=t['INK'], anchor='lm')
        d.text((cx0+140, cy0+108), b, font=FR(24), fill=t['MUTED'], anchor='lm')
    y = gy + 2*196 + 96

    # ---------- 掌心 ----------
    ph = paste_photo(im, f'{IMG}/d3.png', y, h=430, blend_bg=t['BG'], blend=60)
    y += ph
    d = ImageDraw.Draw(im)
    y = caption_strip(d, y, t, '掌心', '一只手刚好握住', '13 cm 刚好一手掌握 · 65 g 走在路上没感觉') + 96

    # ---------- 微距 ----------
    ph = paste_photo(im, f'{IMG}/d4.png', y, h=620)
    y += ph
    d = ImageDraw.Draw(im)
    y = caption_strip(d, y, t, '微距', '这双眼睛，装了整片天空', '3D 刺绣大眼 · 每一只都要过人工表情检') + 96

    # ---------- 场景 ----------
    ph = paste_photo(im, f'{IMG}/d7.png', y, h=470)
    y += ph
    d = ImageDraw.Draw(im)
    y = caption_strip(d, y, t, '场景', '挂在哪儿，可爱到哪儿', '书包拉链 · 钥匙串 · 车后视镜 · 行李箱拉杆') + 96

    # ---------- 配色 ----------
    chip(d, W//2, y+44, '配色', FR(26), t['ACCENT'], t['CHIP'], anchor='ma')
    C(d, '三个颜色，三种心情', W//2, y+98, FS(52), t['INK'])
    ph = paste_photo(im, f'{IMG}/d2.png', y+186, h=470, blend_bg=t['BG'], blend=50)
    d = ImageDraw.Draw(im)
    y = y+186+ph+40
    cols = [((0xfa,0xf6,0xef), '云朵白', '软乎乎的经典款'),
            ((0xf5,0xc6,0xce), '蜜桃粉', '甜度满格，送人首选'),
            ((0xbf,0xd9,0xde), '薄荷蓝', '清清爽爽过夏天')]
    for ccol, cn, cs in cols:
        d.ellipse((W//2-330, y, W//2-274, y+56), fill=ccol, outline=t['GRID'], width=3)
        d.text((W//2-240, y+28), cn, font=FS(34), fill=t['INK'], anchor='lm')
        d.text((W//2, y+28), cs, font=FR(26), fill=t['MUTED'], anchor='lm')
        y += 86
    y += 70

    # ---------- 全家福 ----------
    chip(d, W//2, y+44, '全家福', FR(26), t['ACCENT'], t['CHIP'], anchor='ma')
    C(d, '六只同框，提前拥有团团圆圆', W//2, y+98, FS(52), t['INK'])
    ph = paste_photo(im, f'{IMG}/d8.png', y+186, h=560, blend_bg=t['BG'], blend=50)
    d = ImageDraw.Draw(im)
    C(d, '云朵白 ×2 · 蜜桃粉 ×2 · 薄荷蓝 ×2', W//2, y+186+ph+36, FR(30), t['MUTED'])
    y = y+186+ph+36+86

    # ---------- 吊牌 ----------
    ph = paste_photo(im, f'{IMG}/d10.png', y, h=520)
    y += ph
    d = ImageDraw.Draw(im)
    y = caption_strip(d, y, t, '吊牌', '每只守护，都带专属织标', '合金钥匙环 + 白色织带 · 认准正版小脸蛋') + 96

    # ---------- 包装 ----------
    ph = paste_photo(im, f'{IMG}/d9.png', y, h=560)
    y += ph
    d = ImageDraw.Draw(im)
    y = caption_strip(d, y, t, '包装', '出厂自带仪式感', '礼盒 + 拉菲草 + 手写卡位 · 支持整箱批发装') + 110

    # ---------- 规格表 ----------
    C(d, '规格参数', W//2, y+20, FS(64), t['INK'])
    tw_, _ = measure(d, '规格参数', FS(64))
    d.line((W//2-tw_//2, y+112, W//2+tw_//2, y+112), fill=t['ACCENT'], width=6)
    specs = [('品名', 'DIMMO 守护 · 毛绒挂件（第一代）'), ('尺寸', '约 13 cm（坐姿）'),
             ('克重', '约 65 g'), ('面料', '超柔短毛绒（聚酯纤维）'),
             ('填充', '三维 PP 棉 · 回弹定型'), ('五官', '3D 立体脸片 + 全刺绣'),
             ('配件', '合金钥匙环 + 白色织带'), ('配色', '云朵白 · 蜜桃粉 · 薄荷蓝'),
             ('箱规', '300 只/箱 · 支持混色混批'), ('定制', '500 只起订 · 打样 3-5 天')]
    ty = y+170
    d.rounded_rectangle((M, ty, W-M, ty+len(specs)*80+40), radius=36, fill=t['CARD'])
    for i, (k, v) in enumerate(specs):
        ry = ty+20+i*80
        d.text((W//2-60, ry+40), k, font=FR(28), fill=t['MUTED'], anchor='rm')
        d.text((W//2+60, ry+40), v, font=FS(29), fill=t['INK'], anchor='lm')
        if i: d.line((M+60, ry, W-M-60, ry), fill=t['GRID'], width=2)
    y = ty+len(specs)*80+40+110

    # ---------- 信任 ----------
    trusts = [('发', '24h 发货', '现货拍下即发'), ('赔', '破损包赔', '签收 48h 内秒处理'),
              ('批', '混色混批', '三色随意拼箱'), ('图', '免费效果图', '定制先试印')]
    for i, (g, a, b) in enumerate(trusts):
        cx0 = M + i*((W-2*M-3*24)//4+24)
        cw = (W-2*M-3*24)//4
        d.rounded_rectangle((cx0, y, cx0+cw, y+250), radius=28, fill=t['CARD'])
        d.ellipse((cx0+cw//2-44, y+34, cx0+cw//2+44, y+122), fill=t['CHIP'])
        C(d, g, cx0+cw//2, y+52, FS(40), t['ACCENT'])
        C(d, a, cx0+cw//2, y+140, FS(30), t['INK'])
        C(d, b, cx0+cw//2, y+190, FR(22), t['MUTED'])
    y += 250+110

    # ---------- CTA ----------
    cta_h = 700
    d.rounded_rectangle((M, y, W-M, y+cta_h), radius=56, fill=t['STRIP'])
    C(d, '愿你被世界温柔守护', W//2, y+110, FS(66), t['CARD'])
    C(d, '也愿你把守护，交到别人手上', W//2, y+216, FR(34), t['CARD'])
    d.rounded_rectangle((W//2-300, y+310, W//2+300, y+424), radius=57, fill=t['CARD'])
    d.text((W//2, y+367), '立即拿货 · 询单再减', font=FS(40),
           fill=t['ACCENT'] if t['BUTTON']!=t['STRIP'] else t['INK'], anchor='mm')
    C(d, '源头工厂一件代发 · 支持 OEM / ODM · 客服 9:00-23:00 在线', W//2, y+496, FR(26), t['CARD'])
    C(d, 'DIMMO 守护系列 · 第一代', W//2, y+566, FR(24), t['CARD'])
    y += cta_h + 100

    im = im.crop((0, 0, W, y))
    im.save(out, 'PDF', resolution=144)
    im.save(out.replace('.pdf', '.jpg'), quality=90)
    im.resize((W//2, y//2), Image.LANCZOS).save(out.replace('.pdf', '_half.jpg'), quality=82)
    print(name, 'height', y)

for k, th in THEMES.items():
    build(k, th, f'deliverable/hotcase/SHOUHU_V1_{k}.pdf')
