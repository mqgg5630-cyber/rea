#!/usr/bin/env python3
# DIMMO「守护」长图 V2 —— D 杂志风(The Guardian 季刊) / E 涂鸦风(贴纸手账)
import math
from PIL import Image, ImageDraw, ImageFont

W = 1240
IMG = 'deliverable/hotcase/img8'
FD = '/home/user/fonts'
F = dict(r=lambda s: ImageFont.truetype(f'{FD}/NotoSansSC_400Regular.ttf', s),
         m=lambda s: ImageFont.truetype(f'{FD}/NotoSansSC_500Medium.ttf', s),
         b=lambda s: ImageFont.truetype(f'{FD}/NotoSansSC_700Bold.ttf', s),
         k=lambda s: ImageFont.truetype(f'{FD}/NotoSansSC_900Black.ttf', s))

def mw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0]

def C(d, s, cx, y, f, fill, anchor='ma', spacing=8):
    d.text((cx, y), s, font=f, fill=fill, anchor=anchor, spacing=spacing)

def photo(path, h=None, crop_top=False):
    ph = Image.open(path).convert('RGB')
    if h and ph.height != h:
        top = 0 if crop_top else max(0, (ph.height - h)//2)
        ph = ph.crop((0, top, ph.width, top+h))
    return ph

# ================= D · 杂志风 =================
MG = dict(PAPER=(0xF8,0xF4,0xEC), INK=(0x1E,0x1C,0x19), MUT=(0x85,0x7D,0x71),
          RED=(0xA8,0x32,0x32), RULE=(0xD8,0xD2,0xC6))

def mg_rules(d, y, gap=6):
    d.line((0, y, W, y), fill=MG['INK'], width=6)
    d.line((0, y+gap+2, W, y+gap+2), fill=MG['INK'], width=2)

def mg_fig(d, im, y, tag, title, sub, img, ph_h, crop_top=False):
    C(d, tag, W//2, y, F['b'](28), MG['RED'])
    C(d, title, W//2, y+48, F['k'](56), MG['INK'])
    C(d, sub, W//2, y+130, F['r'](28), MG['MUT'])
    ip = photo(img, ph_h, crop_top)
    im.paste(ip, (48, y+196))
    ImageDraw.Draw(im).rectangle((48, y+196, 48+ip.width, y+196+ip.height), outline=MG['INK'], width=3)
    C(d, f'— 本刊摄 · {sub} —', W//2, y+196+ip.height+16, F['r'](22), MG['MUT'])
    return y+196+ip.height+16+60

def build_magazine(out):
    H = 15000
    im = Image.new('RGB', (W, H), MG['PAPER'])
    d = ImageDraw.Draw(im)
    y = 40
    # --- 刊头 ---
    mg_rules(d, y); mg_rules(d, y+98, gap=6)
    d.line((0, y+98, W, y+98), fill=MG['INK'], width=2)
    d.line((0, y+104, W, y+104), fill=MG['INK'], width=6)
    C(d, 'VOL.01 · 初代刊', 110, y+22, F['b'](26), MG['INK'])
    C(d, 'DIMMO 守护', W//2, y+16, F['k'](64), MG['INK'])
    C(d, '源头工厂特辑', W-110, y+22, F['b'](26), MG['INK'], anchor='ra')
    y += 130
    # 封面图
    ip = photo(f'{IMG}/d1.png', 620)
    im.paste(ip, (48, y))
    d.rectangle((48, y, 48+ip.width, y+ip.height), outline=MG['INK'], width=3)
    C(d, '封面：云朵白 13cm 守护 · 本刊摄', W//2, y+636, F['r'](22), MG['MUT'])
    y += 690
    C(d, '把它挂上包的人，', W//2, y+28, F['k'](104), MG['INK'])
    C(d, '都被守护住了', W//2, y+148, F['k'](104), MG['INK'])
    C(d, '你好，我叫守护。云朵绒帽、玻璃蓝眼、桃粉连体衣，', W//2, y+290, F['r'](32), MG['MUT'])
    C(d, '源头工厂新出厂的“包上搭子”，能挂包、能贴背、能送人，', W//2, y+348, F['r'](32), MG['MUT'])
    C(d, '13cm 小守护，现货 24h 发。', W//2, y+406, F['r'](32), MG['MUT'])
    d.rounded_rectangle((W//2-190, y+466, W//2+190, y+538), radius=36, outline=MG['INK'], width=3)
    C(d, '本期定价 ¥8.9 起/只', W//2, y+482, F['b'](32), MG['RED'])
    y += 600
    d.line((96, y, W-96, y), fill=MG['RULE'], width=3); y += 60

    # --- 速览 ---
    C(d, '速览', W//2, y, F['k'](52), MG['INK'])
    C(d, 'QUICK FACTS', W//2, y+66, F['b'](22), MG['RED'])
    rows = [('尺寸', '约 13 cm（坐姿）'), ('克重', '约 65 g'), ('面料', '超柔短毛绒'),
            ('填充', '三维 PP 棉 · 回弹定型'), ('配色', '云朵白 · 蜜桃粉 · 薄荷蓝'),
            ('箱规', '300 只/箱 · 支持混色')]
    y += 120
    d.rectangle((120, y, W-120, y+len(rows)*76+8), outline=MG['INK'], width=3)
    for i, (k, v) in enumerate(rows):
        ry = y+8+i*76
        if i: d.line((140, ry, W-140, ry), fill=MG['RULE'], width=2)
        d.text((W//2-46, ry+38), k, font=F['r'](28), fill=MG['MUT'], anchor='rm')
        d.text((W//2+46, ry+38), v, font=F['b'](30), fill=MG['INK'], anchor='lm')
    y += len(rows)*76+8+80

    # --- 读者来信(痛点) ---
    C(d, '读者来信', W//2, y, F['k'](52), MG['INK'])
    C(d, 'LETTERS · 挂件踩过的坑', W//2, y+66, F['b'](22), MG['RED'])
    letters = [('太素太普通，送不出手', '他有大眼睛，还有名字和性格'),
               ('硬配饰刮包还硌手', '全都是绣上去的，贴背也安心'),
               ('两天下线，三周走样', '满脸回弹，怎么揉都不塌')]
    y += 124
    for ask, ans in letters:
        C(d, '“', 180, y+6, F['k'](88), MG['RED'])
        C(d, ask, W//2, y+18, F['r'](32), MG['MUT'])
        C(d, '——编辑回：' + ans, W//2, y+84, F['b'](32), MG['INK'])
        y += 168
    y += 30

    # --- 特写 FIG.1 面料 FIG.2 微距 ---
    y = mg_fig(d, im, y+30, '特写 FIG.1', '从脸到脚，都是手工活', '超柔短毛绒 × 白蝴蝶结', f'{IMG}/d5.png', 480)
    y = mg_fig(d, im, y, '特写 FIG.2', '这双眼睛，装了整片天空', '3D 刺绣大眼 · 人工表情检', f'{IMG}/d4.png', 640)
    crafts = [('面', '超柔短毛绒', '手感像云朵，蹭脸上不想停'), ('绣', '3D 立体刺绣', '眉眼神情在线，连线头都藏着'),
              ('棉', '三维 PP 棉', '回弹成型快，揉成一团也能站起来'), ('安', '全刺绣五官', '没有硬配饰，贴背包蹭衣服都 OK')]
    for i, (g, a, b) in enumerate(crafts):
        cx0 = 96 + (i%2)*536
        cy0 = y + (i//2)*170
        d.rectangle((cx0, cy0, cx0+518, cy0+150), outline=MG['INK'], width=3)
        d.ellipse((cx0+28, cy0+43, cx0+92, cy0+107), outline=MG['RED'], width=4)
        C(d, g, cx0+60, cy0+60, F['b'](30), MG['RED'])
        d.text((cx0+116, cy0+40), a, font=F['b'](30), fill=MG['INK'], anchor='lm')
        d.text((cx0+116, cy0+94), b, font=F['r'](23), fill=MG['MUT'], anchor='lm')
    y += 2*170+90

    # --- 特写 FIG.3 掌心 / FIG.4 场景 ---
    y = mg_fig(d, im, y, '特写 FIG.3', '一只手刚好握住', '13cm · 65g 的随身分量', f'{IMG}/d3.png', 430)
    y = mg_fig(d, im, y, '特写 FIG.4', '挂在哪儿，可爱到哪儿', '书包/钥匙/车上的常驻客', f'{IMG}/d7.png', 470)

    # --- 色票薄 ---
    C(d, '色票薄', W//2, y, F['k'](52), MG['INK'])
    C(d, 'COLOR ARCHIVE · 三色在架', W//2, y+66, F['b'](22), MG['RED'])
    y += 124
    ip = photo(f'{IMG}/d2.png', 460)
    im.paste(ip, (48, y))
    d.rectangle((48, y, 48+ip.width, y+ip.height), outline=MG['INK'], width=3)
    y += ip.height+40
    for ccol, cn, cs in [((0xfa,0xf6,0xef), '云朵白', '软乎乎的经典款'), ((0xf5,0xc6,0xce), '蜜桃粉', '甜度满格，送人首选'), ((0xbf,0xd9,0xde), '薄荷蓝', '清清爽爽过夏天')]:
        d.rectangle((W//2-330, y, W//2-250, y+64), fill=ccol, outline=MG['INK'], width=3)
        d.text((W//2-216, y+32), cn, font=F['b'](32), fill=MG['INK'], anchor='lm')
        d.text((W//2-10, y+32), cs, font=F['r'](26), fill=MG['MUT'], anchor='lm')
        y += 96
    y += 30

    # --- 全家福 / 吊牌 / 包装 ---
    y = mg_fig(d, im, y, '合影', '同框的时候，团圆就开始了', '云朵白 · 蜜桃粉 · 薄荷蓝 随心混批', f'{IMG}/d8.png', 560)
    y = mg_fig(d, im, y, '档案', '每只守护，都带专属织标', '合金钥匙环 + 白色织带', f'{IMG}/d10.png', 520)
    y = mg_fig(d, im, y, '出厂', '出厂自带仪式感', '礼盒 + 拉菲草 + 手写卡位', f'{IMG}/d9.png', 560, crop_top=True)

    # --- 产品档案 ---
    C(d, '产品档案', W//2, y, F['k'](52), MG['INK'])
    C(d, 'SPEC SHEET', W//2, y+66, F['b'](22), MG['RED'])
    specs = [('品名', 'DIMMO 守护 · 毛绒挂件（第一代）'), ('尺寸', '约 13 cm（坐姿）'), ('克重', '约 65 g'),
             ('面料', '超柔短毛绒（聚酯纤维）'), ('填充', '三维 PP 棉 · 回弹定型'), ('五官', '3D 立体脸片 + 全刺绣'),
             ('配件', '合金钥匙环 + 白色织带'), ('配色', '云朵白 · 蜜桃粉 · 薄荷蓝'),
             ('箱规', '300 只/箱 · 支持混色混批'), ('定制', '500 只起订 · 打样 3-5 天')]
    y += 120
    d.rectangle((96, y, W-96, y+len(specs)*72+8), outline=MG['INK'], width=3)
    for i, (k, v) in enumerate(specs):
        ry = y+8+i*72
        if i: d.line((116, ry, W-116, ry), fill=MG['RULE'], width=2)
        d.text((W//2-46, ry+36), k, font=F['r'](27), fill=MG['MUT'], anchor='rm')
        d.text((W//2+46, ry+36), v, font=F['b'](28), fill=MG['INK'], anchor='lm')
    y += len(specs)*72+8+70

    # --- 服务栏 ---
    for i, (a, b) in enumerate([('24h 发货', '现货拍下即发'), ('破损包赔', '签收 48h 内处理'),
                                ('混色混批', '三色随意拼箱'), ('免费效果图', '定制先试印')]):
        cx0 = 96 + i*((W-192)//4)
        if i: d.line((cx0-8, y, cx0-8, y+170), fill=MG['RULE'], width=2)
        C(d, a, cx0+((W-192)//4)//2, y+8, F['b'](32), MG['INK'])
        C(d, b, cx0+((W-192)//4)//2, y+70, F['r'](22), MG['MUT'])
        C(d, f'COL.{i+1}', cx0+((W-192)//4)//2, y+120, F['b'](20), MG['RED'])
    y += 210

    # --- 结语 CTA ---
    d.rectangle((0, y, W, y+860), fill=MG['INK'])
    C(d, '本刊结语', W//2, y+80, F['b'](26), MG['RED'])
    C(d, '“愿你被世界温柔守护，', W//2, y+150, F['k'](62), (0xF8,0xF4,0xEC))
    C(d, '也愿你把守护，交到别人手上。”', W//2, y+240, F['k'](62), (0xF8,0xF4,0xEC))
    d.rounded_rectangle((W//2-300, y+380, W//2+300, y+494), radius=57, fill=(0xF8,0xF4,0xEC))
    C(d, '订阅你的守护 · 询单再减', W//2, y+412, F['k'](38), MG['INK'])
    C(d, '源头工厂一件代发 · OEM/ODM · 打样 3-5 天', W//2, y+560, F['r'](26), (0xF8,0xF4,0xEC))
    mg = [MG['INK']]
    d.line((0, y+720, W, y+720), fill=(0xF8,0xF4,0xEC), width=2)
    C(d, 'DIMMO 守护刊 · 感谢阅读 · VOL.01 终', W//2, y+752, F['r'](24), (0xF8,0xF4,0xEC))
    y += 860+80

    im = im.crop((0, 0, W, y))
    im.save(out, 'PDF', resolution=144)
    im.save(out.replace('.pdf', '.jpg'), quality=90)
    im.resize((W//2, y//2), Image.LANCZOS).save(out.replace('.pdf', '_half.jpg'), quality=82)
    print('D magazine height', y)

# ================= E · 涂鸦风 =================
DO = dict(BG=(0xFF,0xFF,0xFF), INK=(0x23,0x23,0x23), YEL=(0xFF,0xD8,0x4D),
          PNK=(0xFF,0xB6,0xC9), BLU=(0xB7,0xE3,0xF1), GRN=(0xC9,0xEB,0xC0),
          ORG=(0xFF,0x9E,0x5E), MUT=(0x8c,0x8c,0x8c))

def squiggle(d, cx, y, wid, color, amp=10, per=56, wd=6):
    pts = []
    for x in range(0, wid+1, 6):
        pts.append((cx-wid//2+x, y + amp*math.sin(x/per*2*math.pi)))
    d.line(pts, fill=color, width=wd, joint='curve')

def star4(d, cx, cy, r, color, wd=5):
    pts = []
    for i in range(8):
        rr = r if i%2==0 else r*0.32
        a = i*math.pi/4 - math.pi/2
        pts.append((cx+rr*math.cos(a), cy+rr*math.sin(a)))
    d.polygon(pts, fill=color)

def tape(im, x, y, w=150, h=44, ang=0, color=None):
    t = Image.new('RGBA', (w, h), (color or DO['YEL'])+(150,))
    t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
    im.paste(t, (x, y), t)

def paste_card(im, io_img, cx, cy):
    """拍立得卡：白框+阴影 io_img=(img, angle)"""
    img, ang = io_img
    pad = 30
    card = Image.new('RGBA', (img.width+pad*2, img.height+pad*2+66), (0,0,0,0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((6, 6, card.width-6, card.height-6), radius=24, fill=(255,255,255,255), outline=DO['INK'], width=4)
    card = card.rotate(ang, expand=True, resample=Image.BICUBIC)
    sh = Image.new('RGBA', card.size, (0,0,0,0))
    ImageDraw.Draw(sh).rounded_rectangle((14, 14, card.width-4, card.height-4), radius=24, fill=(0,0,0,60))
    rot_img = img.convert('RGBA').rotate(ang, expand=True, resample=Image.BICUBIC)
    x = cx - card.width//2; y = cy - card.height//2
    im.paste(sh, (x+10, y+12), sh)
    im.paste(card, (x, y), card)
    im.paste(rot_img, (x + (card.width-rot_img.width)//2, y + (card.height-rot_img.height)//2 - 8), rot_img)
    return card.height, card.width

def speech(d, cx, y, s, f, fill=DO['INK'], bw=None):
    w = bw or mw(d, s, f)+80
    h = f.size+50
    d.rounded_rectangle((cx-w//2, y, cx+w//2, y+h), radius=h//2-6, fill=(255,255,255), outline=DO['INK'], width=5)
    d.polygon([(cx-24, y+h-2), (cx+22, y+h-2), (cx-38, y+h+40)], fill=(255,255,255), outline=DO['INK'])
    C(d, s, cx, y+22, f, fill)
    return y+h+40

def burst(d, cx, cy, r, color, txt1, txt2):
    pts = []
    for i in range(32):
        rr = r if i%2==0 else r*0.78
        a = i*math.pi/16
        pts.append((cx+rr*math.cos(a), cy+rr*math.sin(a)))
    d.polygon(pts, fill=color, outline=DO['INK'])
    C(d, txt1, cx, cy-46, F['k'](56), DO['INK'])
    C(d, txt2, cx, cy+24, F['b'](26), DO['INK'])

def do_title(d, cx, y, s, hl=DO['YEL']):
    f = F['k'](58)
    w = mw(d, s, f)
    d.rounded_rectangle((cx-w//2-22, y+f.size-22, cx+w//2+22, y+f.size+14), radius=16, fill=hl)
    C(d, s, cx, y, f, DO['INK'])
    return y + f.size + 70

def build_doodle(out):
    H = 15000
    im = Image.new('RGB', (W, H), DO['BG'])
    d = ImageDraw.Draw(im)
    y = 60
    # --- hero ---
    star4(d, 150, 120, 34, DO['YEL']); star4(d, W-140, 170, 26, DO['PNK'])
    star4(d, W-220, 76, 18, DO['BLU'])
    C(d, 'DIMMO 守护系列 · 初代', W//2, y, F['b'](30), DO['MUT'])
    y = do_title(d, W//2, y+56, '守护驾到！')
    ph = photo(f'{IMG}/d1.png', 500)
    ph.thumbnail((900, 700))
    chh, cwd = paste_card(im, (ph, -2.5), W//2, y+chh0) if False else paste_card(im, (ph, -2.5), W//2, y+300+ (ph.height//2) )
    d = ImageDraw.Draw(im)
    # tape strips
    tape(im, W//2-260, y+270-24, ang=-38)
    tape(im, W//2+120, y+270-20, ang=32, color=DO['BLU'])
    y = y + 300 + ph.height + 70
    y = speech(d, W//2, y, '你好，我叫守护，把我挂上包吧！', F['b'](36))
    y += 30
    C(d, '云朵绒帽 · 玻璃蓝眼 · 桃粉连体衣 · 13cm 一手掌握', W//2, y, F['r'](28), DO['MUT'])
    burst(d, W-240, y+130, 128, DO['YEL'], '¥8.9', '起/只 · 混批')
    ys = y+250
    # squiggle divider helper
    def divider(yy):
        squiggle(d, W//2, yy, 760, DO['BLU'], amp=9)
        return yy+60

    # --- 参数 ---
    y = divider(ys)
    C(d, '先报参数，再上才艺', W//2, y, F['b'](30), DO['MUT']); y = do_title(d, W//2, y+50, '13cm · 65g · 三色')
    rows = [('面料', '超柔短毛绒'), ('填充', '三维 PP 棉·回弹定型'), ('五官', '3D 脸片+全刺绣'),
            ('配件', '合金钥匙环+白织带'), ('箱规', '300 只/箱·支持混色')]
    y += 16
    for k, v in rows:
        d.rounded_rectangle((W//2-430, y, W//2+430, y+70), radius=35, fill=DO['GRN'] if k in ('面料','填充') else DO['PNK'] if k in ('五官','配件') else DO['BLU'])
        d.text((W//2-380, y+35), k, font=F['b'](30), fill=DO['INK'], anchor='lm')
        d.text((W//2+380, y+35), v, font=F['r'](28), fill=DO['INK'], anchor='rm')
        y += 92
    y += 10

    # --- 痛点 ---
    y = divider(y)
    y = do_title(d, W//2, y, '踩过的坑，都填平了', hl=DO['PNK'])
    for ask, ans in [('太素太普通，送不出手', '有大眼睛，还有名字性格'),
                     ('硬配饰刮包还硌手', '全都绣上去，贴背安心'),
                     ('两天下线三周走样', '满脸回弹，怎么揉不塌')]:
        d.rounded_rectangle((W//2-460, y, W//2+460, y+92), radius=18, fill=(255,255,255), outline=DO['INK'], width=4)
        # 手绘涂改叉：椭圆圈 + 两道斜线
        cx, cy = W//2-432, y+46
        d.ellipse((cx-14, cy-14, cx+14, cy+14), outline=DO['ORG'], width=4)
        d.line((cx-8, cy-8, cx+8, cy+8), fill=DO['ORG'], width=4)
        d.line((cx+8, cy-8, cx-8, cy+8), fill=DO['ORG'], width=4)
        d.text((W//2-400, y+46), ask, font=F['r'](28), fill=DO['MUT'], anchor='lm')
        y += 112
        d.polygon([(W//2-18, y-16), (W//2+18, y-16), (W//2, y+10)], fill=DO['ORG'])
        d.text((W//2, y+38), ans, font=F['b'](32), fill=DO['INK'], anchor='mm')
        y += 96
    y += 10

    # --- 工艺 ---
    y = divider(y)
    y = do_title(d, W//2, y, '从脸到脚，都是手工活')
    cards = [(f'{IMG}/d5.png', '面料特写', '短毛绒手感像云朵'), (f'{IMG}/d4.png', '微距大眼', '每一只都过表情检')]
    phh = 330
    for i, (p, cap, sub) in enumerate(cards):
        pimg = photo(p)
        pimg.thumbnail((980, phh+80))
        pimg = pimg.crop((0, 0, pimg.width, min(pimg.height, phh)))
        ch, cw = paste_card(im, (pimg, (-2.0 if i==0 else 2.0)), W//2, y+chh-1 if False else y+ pimg.height//2+33)
        d = ImageDraw.Draw(im)
        y += 66 + pimg.height + 30
        C(d, f'▲ {cap}', W//2, y, F['b'](30), DO['INK'])
        C(d, sub, W//2, y+44, F['r'](26), DO['MUT'])
        y += 110
    for g, a, col in [('面', '超柔短毛绒', DO['YEL']), ('绣', '3D 立体刺绣', DO['PNK']), ('棉', '三维 PP 棉', DO['BLU']), ('安', '全刺绣五官', DO['GRN'])]:
        d.rounded_rectangle((W//2-430, y, W//2+430, y+64), radius=32, fill=col)
        d.ellipse((W//2-410, y+12, W//2-370, y+52), fill=(255,255,255), outline=DO['INK'], width=3)
        C(d, g, W//2-390, y+16, F['b'](26), DO['INK'])
        d.text((W//2+400, y+32), a, font=F['b'](28), fill=DO['INK'], anchor='rm')
        y += 84
    y += 10

    # --- 掌心 / 场景 ---
    y = divider(y)
    y = do_title(d, W//2, y, '一只手刚好握住', hl=DO['BLU'])
    pimg = photo(f'{IMG}/d3.png', 430)
    ch, cw = paste_card(im, (pimg, 1.8), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+24
    C(d, '13cm 一手掌握 · 65g 没感觉', W//2, y, F['b'](28), DO['INK']); y += 90
    y = do_title(d, W//2, y, '挂在哪儿，可爱到哪儿', hl=DO['GRN'])
    pimg = photo(f'{IMG}/d7.png', 460)
    ch, cw = paste_card(im, (pimg, -1.6), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+24
    C(d, '书包拉链 · 钥匙串 · 车后视镜 · 行李箱', W//2, y, F['b'](28), DO['INK']); y += 100

    # --- 配色 ---
    y = divider(y)
    y = do_title(d, W//2, y, '三个颜色，三种心情', hl=DO['YEL'])
    pimg = photo(f'{IMG}/d2.png', 440)
    ch, cw = paste_card(im, (pimg, 0.0), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+34
    for ccol, cn, cs in [((0xfa,0xf6,0xef), '云朵白', '软乎乎经典款'), ((0xf5,0xc6,0xce), '蜜桃粉', '甜度满格'), ((0xbf,0xd9,0xde), '薄荷蓝', '清爽过夏天')]:
        d.ellipse((W//2-310, y, W//2-254, y+56), fill=ccol, outline=DO['INK'], width=4)
        d.text((W//2-220, y+28), cn, font=F['b'](32), fill=DO['INK'], anchor='lm')
        d.text((W//2+20, y+28), cs, font=F['r'](26), fill=DO['MUT'], anchor='lm')
        y += 86
    y += 20

    # --- 全家福/吊牌/包装 ---
    y = divider(y)
    y = do_title(d, W//2, y, '全家都到齐了', hl=DO['PNK'])
    pimg = photo(f'{IMG}/d8.png', 520)
    ch, cw = paste_card(im, (pimg, 1.5), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+24
    C(d, '三色集结 · 混色混批', W//2, y, F['b'](28), DO['INK']); y += 92
    pimg = photo(f'{IMG}/d10.png', 420)
    ch, cw = paste_card(im, (pimg, -2.2), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+24
    C(d, '专属织标 + 合金环，认准正版小脸', W//2, y, F['b'](28), DO['INK']); y += 92
    pimg = photo(f'{IMG}/d9.png', 480, crop_top=True)
    ch, cw = paste_card(im, (pimg, 2.0), W//2, y+pimg.height//2+33)
    d = ImageDraw.Draw(im)
    y += 66+pimg.height+24
    C(d, '礼盒 + 拉菲草 + 手写卡位，出厂自带仪式感', W//2, y, F['b'](28), DO['INK']); y += 110

    # --- 规格 ---
    y = divider(y)
    y = do_title(d, W//2, y, '规格一张表', hl=DO['BLU'])
    specs = [('品名', 'DIMMO 守护 · 毛绒挂件 一代'), ('尺寸', '约 13 cm（坐姿）'), ('克重', '约 65 g'),
             ('面料', '超柔短毛绒（聚酯纤维）'), ('填充', '三维 PP 棉 · 回弹定型'), ('五官', '3D 立体脸片 + 全刺绣'),
             ('配件', '合金钥匙环 + 白色织带'), ('配色', '云朵白 · 蜜桃粉 · 薄荷蓝'),
             ('箱规', '300 只/箱 · 混色混批'), ('定制', '500 只起 · 打样 3-5 天')]
    for k, v in specs:
        d.text((W//2-60, y+30), k, font=F['r'](28), fill=DO['MUT'], anchor='rm')
        d.text((W//2+60, y+30), v, font=F['b'](29), fill=DO['INK'], anchor='lm')
        d.line((W//2-330, y+66, W//2+330, y+66), fill=(0xE8,0xE8,0xE8), width=2)
        y += 74
    y += 30

    # --- 信任 ---
    for i, (a, col) in enumerate([('24h 发货', DO['YEL']), ('破损包赔', DO['PNK']), ('混色混批', DO['BLU']), ('免费效果图', DO['GRN'])]):
        cx0 = 96 + i*((W-192)//4)
        cw = (W-192)//4 - 18
        d.rounded_rectangle((cx0, y, cx0+cw, y+150), radius=24, fill=col, outline=DO['INK'], width=4)
        C(d, a, cx0+cw//2, y+38, F['b'](28), DO['INK'])
    y += 210

    # --- CTA ---
    d.rounded_rectangle((62, y, W-62, y+640), radius=48, fill=DO['INK'])
    star4(d, 150, y+90, 30, DO['YEL']); star4(d, W-150, y+90, 30, DO['PNK'])
    C(d, '愿你被世界温柔守护', W//2, y+96, F['k'](64), (255,255,255))
    C(d, '也愿你把守护，交到别人手上', W//2, y+196, F['r'](30), (0xD9,0xD9,0xD9))
    d.rounded_rectangle((W//2-320, y+300, W//2+320, y+420), radius=60, fill=DO['YEL'])
    C(d, '立即拿货 · 询单再减', W//2, y+330, F['k'](42), DO['INK'])
    C(d, '源头工厂一件代发 · OEM/ODM · 打样 3-5 天', W//2, y+480, F['r'](26), (0xD9,0xD9,0xD9))
    squiggle(d, W//2, y+568, 700, DO['PNK'], amp=8)
    y += 640+90

    im = im.crop((0, 0, W, y))
    im.save(out, 'PDF', resolution=144)
    im.save(out.replace('.pdf', '.jpg'), quality=90)
    im.resize((W//2, y//2), Image.LANCZOS).save(out.replace('.pdf', '_half.jpg'), quality=82)
    print('E doodle height', y)

if __name__ == '__main__':
    build_magazine('deliverable/hotcase/SHOUHU_V2_D_magazine.pdf')
    build_doodle('deliverable/hotcase/SHOUHU_V2_E_doodle.pdf')
