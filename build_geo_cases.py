#!/usr/bin/env python3
"""SEO-GEO 助手模块 · 模拟数据跑通案例 PDF 生成器
跑通 seo-geo-suite 三行核心链路，输出 3 份案例 PDF（每份 3 页）：
  CASE01 星壳优选  = row3 短板定位 + prompts/store-checkup   -> 生意体检 + 30天整改
  CASE02 沐宠电器  = row1 发品 + row2 标题 + prompts/title-optimizer -> 新品发品 + 标题优化
  CASE03 良栖收纳  = row4 复盘 + prompts/data-review          -> 全店周报
版式口径：与 hotcase-longimage-skill 同款硬规则（胶囊真垂直居中、tw() 实测居中、全版中轴对称）。
数据全部为模拟演示，指标口径以 1688 后台实时为准。"""
import math, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'deliverable', 'geo-module', 'cases')
os.makedirs(OUT, exist_ok=True)

_FR = ImageFont.truetype('/tmp/fonts/NotoSansSC-Regular.ttf', 10)
_FB = ImageFont.truetype('/tmp/fonts/NotoSansSC-Bold.ttf', 10)
def R(s): return _FR.font_variant(size=s)
def B(s): return _FB.font_variant(size=s)

W, H = 1240, 1754
M = 88                       # 左右边距
CW = W - 2 * M               # 内容宽 1064
INK = (0x19, 0x1B, 0x22)
MUT = (0x6E, 0x72, 0x7C)
LINE = (0xD2, 0xD5, 0xDC)
PAPER = (0xFA, 0xFA, 0xF7)
CARD = (0xFF, 0xFF, 0xFF)
GOOD = (0x2E, 0x8E, 0x56)
BAD = (0xCB, 0x40, 0x2E)

CASES = {
    1: dict(acc=(0xE8, 0x4B, 0x2D), pale=(0xFC, 0xEA, 0xE5),
            store='星壳优选', cat='手机壳批发', tag='row3 短板定位 × prompts/store-checkup',
            title='店铺生意体检 · 30 天整改', fname='GEO_CASE01_store_checkup'),
    2: dict(acc=(0x2A, 0x84, 0xCE), pale=(0xE6, 0xF1, 0xFA),
            store='沐宠电器', cat='宠物智能用品', tag='row1 发品 × row2 标题 × prompts/title-optimizer',
            title='新品发品 · 标题优化', fname='GEO_CASE02_listing_title'),
    3: dict(acc=(0x6F, 0x85, 0x6C), pale=(0xEC, 0xF1, 0xEA),
            store='良栖收纳', cat='家居收纳', tag='row4 复盘 × prompts/data-review',
            title='全店周报 · 数据复盘', fname='GEO_CASE03_weekly_review'),
}

def tw(d, s, f):
    bb = d.textbbox((0, 0), s, font=f)
    return bb[2] - bb[0]

def ctext(d, s, cx, y, f, fill=INK):
    d.text((cx, y), s, font=f, fill=fill, anchor='ma')

def wrap(d, s, f, maxw):
    """CJK 逐字换行；遇 ASCII 单词（含 -+%,. 连接的 token）整体挪到下一行，不劈开。"""
    lines, cur = [], ''
    for ch in s:
        if ch == '\n':
            lines.append(cur); cur = ''; continue
        if tw(d, cur + ch, f) > maxw and cur:
            run = ''
            if ch.isascii() and ch.isalnum():
                while cur and cur[-1].isascii() and (cur[-1].isalnum() or cur[-1] in '-+%,.'):
                    run = cur[-1] + run
                    cur = cur[:-1]
            cur = cur.rstrip()
            if cur:
                lines.append(cur)
            cur = (run + ch) if run else ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines

def chip(d, cx, y, s, f, fg, bg, pad_x=24, h=None, outline=None, ow=0):
    """胶囊：真垂直居中（锚点画在 y+h/2，anchor mm）——硬规则第1条"""
    w = tw(d, s, f) + pad_x * 2
    h = h or f.size + 22
    d.rounded_rectangle((cx - w // 2, y, cx + w // 2, y + h), radius=h // 2,
                        fill=bg, outline=outline, width=ow or 1)
    d.text((cx, y + h // 2), s, font=f, fill=fg, anchor='mm')
    return w, h

def header(d, ci):
    c = CASES[ci]
    ctext(d, 'GEO布局 × 专家-SEO-GEO 助手 · 技能模拟跑通案例 0%d' % ci, W // 2, 52, R(24), MUT)
    ctext(d, c['title'], W // 2, 94, B(50), INK)
    items = [(c['store'], B(26), CARD, c['acc']),
             (c['cat'], R(26), MUT, CARD),
             (c['tag'], R(23), c['acc'], c['pale']),
             ('数据=模拟演示', B(23), (0xF2, 0xD3, 0x8B), (0x25, 0x27, 0x2E))]
    gap = 24
    ws = [tw(d, s, f) + 46 for s, f, _, _ in items]
    total = sum(ws) + gap * (len(ws) - 1)
    x = W // 2 - total // 2
    y0, hh = 166, 50
    for (s, f, fg, bg), w0 in zip(items, ws):
        d.rounded_rectangle((x, y0, x + w0, y0 + hh), radius=hh // 2, fill=bg)
        d.text((x + w0 // 2, y0 + hh // 2), s, font=f, fill=fg, anchor='mm')
        x += w0 + gap
    d.line((M, 248, W - M, 248), fill=LINE, width=2)
    return 272

def footer(d, page, pages):
    d.line((M, H - 96, W - M, H - 96), fill=LINE, width=2)
    ctext(d, '本案例由 seo-geo-suite 按 SOP 生成 · 全部数据为模拟演示 · 指标口径以 1688 后台实时为准',
          W // 2, H - 82, R(21), MUT)
    ctext(d, '· %d / %d ·' % (page, pages), W // 2, H - 54, R(21), MUT)

def page(ci, pageno, pages=3):
    im = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(im)
    y = header(d, ci)
    footer(d, pageno, pages)
    return im, d, y

def section(d, y, s, ci):
    c = CASES[ci]
    chip(d, W // 2, y, s, B(28), CARD, c['acc'], pad_x=32, h=56)
    return y + 56 + 24

def table(d, y, colws, rows, rh=60, hrh=58, hf=None, aligns=None, cell_colors=None, lh=34):
    """rows[0]=表头。文字垂直居中；超长自动换行（≤3 行）。aligns: 'c'/'l'/'r'。"""
    hf = hf or PAPER
    aligns = aligns or ['c'] * len(colws)
    cc = cell_colors or {}
    x0 = W // 2 - sum(colws) // 2
    h0 = hrh + rh * (len(rows) - 1)
    d.rounded_rectangle((x0, y, x0 + sum(colws), y + h0), radius=18, fill=CARD, outline=LINE, width=2)
    d.rounded_rectangle((x0, y, x0 + sum(colws), y + hrh), radius=18, fill=hf)
    d.rectangle((x0, y + hrh - 18, x0 + sum(colws), y + hrh), fill=hf)
    for ri, row in enumerate(rows):
        yy = y if ri == 0 else y + hrh + (ri - 1) * rh
        rhh = hrh if ri == 0 else rh
        if ri > 0:
            d.line((x0, yy, x0 + sum(colws), yy), fill=LINE, width=1)
        cy = yy + rhh // 2
        xx = x0
        for k, cell in enumerate(row):
            if k > 0:
                d.line((xx, yy + 10, xx, yy + rhh - 10), fill=LINE, width=1)
            if isinstance(cell, tuple):
                s, f, col = cell
            else:
                s, f, col = cell, (B(26) if ri == 0 else R(26)), cc.get((ri, k), INK)
            if (ri, k) in cc:
                col = cc[(ri, k)]
            maxw = colws[k] - 40
            lines = wrap(d, s, f, maxw)
            if len(lines) > 3:
                lines = lines[:2] + [''.join(lines[2:])]
            if s == '@check':
                cxh = xx + colws[k] // 2
                d.line((cxh - 10, cy, cxh - 3, cy + 8), fill=GOOD, width=5)
                d.line((cxh - 3, cy + 8, cxh + 11, cy - 9), fill=GOOD, width=5)
                xx += colws[k]
                continue
            al = aligns[k]
            if al == 'c':
                tx = xx + colws[k] // 2; anch = 'm'
            elif al == 'l':
                tx = xx + 20; anch = 'l'
            else:
                tx = xx + colws[k] - 20; anch = 'r'
            base = cy - (len(lines) * lh) // 2 + lh // 2
            for li, ln in enumerate(lines):
                d.text((tx, base + li * lh), ln, font=f, fill=col, anchor=anch + 'm')
            xx += colws[k]
    return y + h0

def checklist(d, y, items, rh=64, box=26):
    for i, (ok, s) in enumerate(items):
        yy = y + i * rh
        col = GOOD if ok else (0xC9, 0x8A, 0x3D)
        bx = M + 24
        d.rounded_rectangle((bx, yy + (rh - box) // 2, bx + box, yy + (rh + box) // 2),
                            radius=7, outline=col, width=3)
        cyb = yy + rh // 2
        if ok:
            d.line((bx + 6, cyb, bx + 12, cyb + 6), fill=col, width=4)
            d.line((bx + 12, cyb + 6, bx + 21, cyb - 8), fill=col, width=4)
        else:
            d.text((bx + box // 2, cyb), '…', font=B(22), fill=col, anchor='mm')
        x_text = bx + box + 20
        lines = wrap(d, s, R(26), W - M - x_text)
        base = cyb - (len(lines) * 36) // 2 + 18
        for li, ln in enumerate(lines):
            d.text((x_text, base + li * 36), ln, font=R(26), fill=INK, anchor='lm')
    return y + len(items) * rh

def funnel(d, y, vals, labels, subs, acc, rh=76, maxw=640, flags=None):
    """居中漏斗：条宽 ∝ sqrt(v)；值能进条内就进条内，进不了放条右侧；flags={i: 文本} 断点芯片。
    subs: [(text,color), ...]"""
    flags = flags or {}
    vmax = max(vals)
    yy = y
    for i, v in enumerate(vals):
        ww = int(math.sqrt(v / vmax) * maxw) + 160
        x0 = W // 2 - ww // 2
        f2 = 0.15 * i
        fill = tuple(int(acc[j] + (255 - acc[j]) * f2) for j in range(3))
        lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
        fg = CARD if lum < 170 else INK
        d.rounded_rectangle((x0, yy + 4, x0 + ww, yy + rh - 4), radius=16, fill=fill)
        val, vcol = subs[i]
        fv = B(24)
        if tw(d, val, fv) + tw(d, labels[i], B(26)) + 70 <= ww:
            d.text((W // 2, yy + rh // 2 - 15), labels[i], font=B(26), fill=fg, anchor='mm')
            d.text((W // 2, yy + rh // 2 + 16), val, font=fv, fill=fg, anchor='mm')
        else:
            d.text((W // 2, yy + rh // 2), labels[i], font=B(26), fill=fg, anchor='mm')
            right_room = (W - M) - (x0 + ww + 16)
            if tw(d, val, fv) <= right_room:
                d.text((x0 + ww + 16, yy + rh // 2), val, font=fv, fill=vcol, anchor='lm')
            else:
                d.text((x0 - 16, yy + rh // 2), val, font=fv, fill=vcol, anchor='rm')
        yy += rh
        if i in flags:
            t = flags[i]
            w2 = tw(d, t, B(22)) + 34
            d.rounded_rectangle((W // 2 - w2 // 2, yy + 0, W // 2 + w2 // 2, yy + 38),
                                radius=19, fill=BAD)
            d.text((W // 2, yy + 19), t, font=B(22), fill=CARD, anchor='mm')
            yy += 48
    return yy

def note_card(d, y, title_s, body_s, accent, pale, lh=38):
    lines = wrap(d, body_s, R(26), CW - 120)
    h0 = 66 + len(lines) * lh + 30
    d.rounded_rectangle((M, y, W - M, y + h0), radius=22, fill=pale)
    d.rounded_rectangle((M, y, M + 14, y + h0), radius=7, fill=accent)
    d.text((M + 44, y + 38), title_s, font=B(28), fill=accent, anchor='lm')
    yy = y + 66
    for ln in lines:
        d.text((M + 44, yy + lh // 2), ln, font=R(26), fill=INK, anchor='lm')
        yy += lh
    return y + h0

def save_case(ci, pages):
    c = CASES[ci]
    pdf = os.path.join(OUT, c['fname'] + '.pdf')
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=150)
    for i, pg in enumerate(pages, 1):
        pg.resize((W // 2, H // 2), Image.LANCZOS).save(
            os.path.join(OUT, 'qa_C%02d_p%d.jpg' % (ci, i)), quality=82)
    print('ok', pdf, len(pages), 'pages')

# ============ CASE 01 ============
def case01():
    c = CASES[1]
    im, d, y0 = page(1, 1)
    y = note_card(d, y0, '店铺身份锁（一句锁定）',
                  '星壳优选：TPU/液态硅胶手机壳批发，108 款现货图案，支持一图定制，48h 发货，'
                  '华东仓一件代发。主推 3 个 SKU，全店 42 个在售品。', c['acc'], c['pale'])
    y = section(d, y + 26, '近 30 天体检总表（10 项 · 本期/环比/类目均值/判定）', 1)
    ok = ('达标', B(24), GOOD); bad = ('短板', B(24), BAD); mid = ('— 持平', B(24), MUT)
    rows = [
        ['指标', '本期', '环比', '类目均值', '判定'],
        ['曝光', '128,400', ('+6.2% ↑', B(25), GOOD), '96,000', ok],
        ['点击率', '2.50%', ('-0.60pct ↓', B(25), BAD), '3.10%', bad],
        ['询盘', '156', ('-2.5% ↓', B(25), BAD), '168', mid],
        ['询盘率', '4.86%', ('-0.22pct ↓', B(25), BAD), '5.20%', bad],
        ['支付买家', '92', ('-10.7% ↓', B(25), BAD), '—', bad],
        ['支付转化率', '3.18%', ('-0.34pct ↓', B(25), BAD), '3.90%', bad],
        ['退款率', '2.1%', ('持平', B(25), MUT), '2.0%', mid],
        ['响应时长', '6分42秒', ('+1分10秒 ↑', B(25), BAD), '4分钟内', bad],
        ['发货超时率', '1.8%', ('-0.3pct ↓', B(25), GOOD), '2.0%', ok],
        ['综合评分', '4.6', ('持平', B(25), MUT), '4.6', mid],
    ]
    y = table(d, y + 4, [210, 170, 210, 180, 254], rows, rh=64,
              hf=c['pale'])
    y = note_card(d, y + 24, '一句话结论',
                  '曝光端健康（高于类目 33.8%），断点集中在「点击」与「询盘›支付」两环：'
                  '主图点击率 2.50% 低于类目均值 19.4%，详情说服力与响应速度拖累转化。', c['acc'], c['pale'])

    im2, d2, y0 = page(1, 2)
    y = section(d2, y0 + 4, '漏斗断点定位（row3 定位树走查）', 1)
    y = funnel(d2, y + 12,
               [128400, 3210, 156, 118, 92],
               ['曝光', '点击', '询盘', '下单', '支付'],
               [('128,400', INK), ('3,210 · CTR 2.50%', BAD),
                ('156 · 询盘率 4.86%', BAD), ('118 · 下单率 75.6%', INK),
                ('92 · 支付率 78.0%', INK)],
               c['acc'],
               flags={1: '断点1 · 点击低 › 主图1 不够打，按 A/B/C 三风格换图重测',
                      2: '断点2 · 询盘低 › 详情说服力不足，走 14 屏改版'})
    y = section(d2, y + 22, '7 天快赢项执行状态', 1)
    y = checklist(d2, y + 6, [
        (True, '48h 发货开关与真实履约已对齐；超时单当日清零'),
        (True, '42 个在售品属性完整率补到 100%（原 87%）'),
        (False, '低分单逐一回访：已处理 6/11，剩余 5 单进行中'),
        (False, '消息分钟级响应：自动应答已开，晚班轮值周三起排'),
        (True, '3 个在途滞销品降价清仓，库存权重拖累下降'),
    ])
    y = note_card(d2, y + 22, '定位树回挂（row3）',
                  '点击低›主图换风格重测（row2/hotcase 出图）｜询盘低›14 屏改版｜'
                  '转化低›价格梯度缺中档（row1 改档）｜响应慢›自动应答+轮班。', c['acc'], c['pale'])

    im3, d3, y0 = page(1, 3)
    y = section(d3, y0 + 4, '30 天整改剧本（体检 › 整改 › 复检）', 1)
    rows = [
        ['周', '动作', '验收指标'],
        ['W1', 'store-checkup 提示词跑短板清单；48h 发货与履约对齐；属性补全',
         '体检假设表落档；超时率 2%内'],
        ['W2', '快赢项全做一遍：响应提速、滞销清仓、低分回访收尾',
         '响应 4 分钟内；清仓品库存 -80%'],
        ['W3', '主图 A/B/C 三风格重拍上架 3 个主推品；2 个主销品详情 14 屏改版',
         'CTR 3.1%+；询盘率 5.5%+'],
        ['W4', '复检 10 项指标环比，冻结有效动作，写月报定稿',
         '支付转化率 3.9%+（回类目均值）'],
    ]
    y = table(d3, y + 4, [104, 580, 380], rows, rh=96, hf=c['pale'], aligns=['c', 'l', 'l'])
    y = section(d3, y + 22, '复检目标卡（W4 验收线）', 1)
    goals = [('点击率', '2.50% › 3.10%+'), ('询盘率', '4.86% › 5.50%+'),
             ('响应时长', '6分42秒 › 4分钟内'), ('支付转化', '3.18% › 3.90%+')]
    gw = (CW - 3 * 18) // 4
    for i, (k, v) in enumerate(goals):
        x0 = M + i * (gw + 18)
        d3.rounded_rectangle((x0, y, x0 + gw, y + 118), radius=18, fill=CARD, outline=LINE, width=2)
        d3.text((x0 + gw / 2, y + 38), k, font=R(24), fill=MUT, anchor='mm')
        d3.text((x0 + gw / 2, y + 80), v, font=B(22), fill=c['acc'], anchor='mm')
    y += 118 + 20
    y = note_card(d3, y, '口径与依赖声明',
                  '星级构成、采购指数等排名权重以 1688 后台实时规则为准。动作来源：'
                  'seo-geo-suite row3（定位树/快赢项/30 天剧本）+ prompts/store-checkup.md；'
                  '详情改版引用 hotcase-longimage-skill 14 屏流程。', c['acc'], c['pale'])
    save_case(1, [im, im2, im3])

# ============ CASE 02 ============
def case02():
    c = CASES[2]
    im, d, y0 = page(2, 1)
    y = note_card(d, y0, '产品身份锁（逐字进提示词与文案）',
                  '沐宠 · 宠物智能饮水机：2.4L 容量，304 不锈钢水盘+ABS 机身，超静音泵（30dB 以内，有检测报告），'
                  '三重滤芯（PP棉/活性炭/离子树脂），USB 供电，断电储水 200ml，猫狗通用，白/灰两色。',
                  c['acc'], c['pale'])
    y = section(d, y + 26, '发品字段必经清单（row1 · 一次性填全）', 2)
    rows = [
        ['字段', '本案例填写', '自查'],
        ['类目', '宠物 › 宠物智能用品 › 智能饮水机（挂最细类目）', ('@check', R(26), GOOD)],
        ['标题', '30 字满编，先过 row2 优化器（P2 五候选）', ('@check', R(26), GOOD)],
        ['主图 ×5', '1 白底 + 2 场景（客厅/多猫）+ 1 卖点（滤芯剖视）+ 1 规格', ('@check', R(26), GOOD)],
        ['详情长图', '走 hotcase-longimage-skill 14 屏，B/C 风抽测 CTR', ('@check', R(26), GOOD)],
        ['属性', '品牌/材质/容量/颜色/供电全勾选，完整率 100%', ('@check', R(26), GOOD)],
        ['价格梯度', '3 档：1–49 / 50–199 / 200 台起（见 P3）', ('@check', R(26), GOOD)],
        ['运费模板', '华东仓模板，与仓发地址一致', ('@check', R(26), GOOD)],
        ['服务承诺', '48h 发货｜批发件破损包赔｜滤芯常年供货', ('@check', R(26), GOOD)],
    ]
    y = table(d, y + 4, [160, 780, 84], rows, rh=66, hf=c['pale'],
              aligns=['c', 'l', 'c'], cell_colors={(i, 2): GOOD for i in range(1, 9)})
    y = note_card(d, y + 24, '上架 SOP 五步（row1）',
                  '1·身份锁 › 2·清单填字段、标题过优化器 › 3·主图 5 张+详情 1 套（风格抽测）› '
                  '4·梯度提交审核、24h 回查曝光种子 › 5·写 publish_log.csv 留档。', c['acc'], c['pale'])

    im2, d2, y0 = page(2, 2)
    y = section(d2, y0 + 4, '30 字标题公式（row2）', 2)
    parts = ['核心词', '属性词', '场景词', '批发营销词']
    pw, gp, gg = 200, 56, 20
    total = len(parts) * pw + (len(parts) - 1) * (gp + gg)
    x = W // 2 - total // 2
    for i, p in enumerate(parts):
        d2.rounded_rectangle((x, y, x + pw, y + 60), radius=14, fill=c['acc'])
        d2.text((x + pw / 2, y + 30), p, font=B(27), fill=CARD, anchor='mm')
        x += pw
        if i < 3:
            d2.text((x + (gp + gg) / 2, y + 30), '+', font=B(30), fill=MUT, anchor='mm')
            x += gp + gg
    y += 60 + 24
    y = section(d2, y, '五候选标题（prompts/title-optimizer 输出）', 2)
    cands = [
        ('候选1 · 大词流', '宠物饮水机猫咪自动饮水器不锈钢静音过滤循环大容量现货批发',
         '核心大词：宠物饮水机｜主流词：自动饮水器｜取舍：搜索面最大，相关性略散'),
        ('候选2 · 高相关', '猫咪饮水机智能循环过滤2.4L超静音不锈钢水盘源头厂家混批',
         '核心大词：猫咪饮水机｜主流词：静音饮水机｜取舍：词品对应最严，转化向'),
        ('候选3 · 场景化', '宠物饮水机猫狗通用自动循环活水家用静音滤芯可换代发全国',
         '核心大词：宠物饮水机｜主流词：猫狗通用｜取舍：场景带长尾，营销感弱'),
        ('候选4 · 定制向', '宠物智能饮水机OEM定制LOGO贴牌静音泵三重滤芯起订量低',
         '核心大词：智能饮水机｜主流词：OEM定制｜取舍：B 端意图强，零售曝光让位'),
        ('候选5 · 批发贸易感', '宠物饮水机批发2.4L不锈钢猫咪饮水器跨境货源现货48h发',
         '核心大词：饮水机批发｜主流词：跨境货源｜取舍：拉大单，C 端点击低'),
    ]
    for i, (tag, tt, note) in enumerate(cands):
        cy0 = y + i * 146
        d2.rounded_rectangle((M, cy0, W - M, cy0 + 132), radius=18, fill=CARD, outline=LINE, width=2)
        d2.text((M + 28, cy0 + 34), tag, font=B(23), fill=c['acc'], anchor='lm')
        n = len(tt)
        d2.text((W - M - 28, cy0 + 34), '%d字' % n, font=B(23),
                fill=GOOD if n <= 30 else BAD, anchor='rm')
        d2.text((M + 28, cy0 + 74), tt, font=B(29), fill=INK, anchor='lm')
        d2.text((M + 28, cy0 + 110), note, font=R(22), fill=MUT, anchor='lm')
    y += len(cands) * 146 + 6
    y = note_card(d2, y, '推荐结论',
                  '上架用 候选2（高相关）：核心词「猫咪饮水机」与主图1、属性完全对应，权重集中；'
                  '候选1、5 进 A/B 词池，每周只微调 1–2 个词位，7 天对比曝光与 CTR。', c['acc'], c['pale'])

    im3, d3, y0 = page(2, 3)
    y = section(d3, y0 + 4, '标题-属性-主图相关性自查（row2）', 2)
    y = checklist(d3, y + 6, [
        (True, '标题每个词在属性或详情图均有对应物（静音 30dB 内附检测）'),
        (True, '属性完整率 100%（容量/供电/适用宠物无空缺）'),
        (True, '主图1 与核心词「猫咪饮水机」完全对应（白底整机）'),
        (True, '服务真实可做（48h 发货现货；破损包赔已测试）'),
        (True, '无广告法禁词：功效词一律有证据才写'),
    ])
    y = section(d3, y + 22, '价格梯度（row1 定价档）', 2)
    rows = [
        ['档位', '数量', '单价', '定位'],
        ['档一', '1–49 台', '¥39.0', '试销 / 贴牌打样'],
        ['档二', '50–199 台', '¥35.0', '主走量档（详情页强调）'],
        ['档三', '200 台起', '¥29.9', '大单 / 跨境集采'],
    ]
    y = table(d3, y + 4, [170, 250, 190, 454], rows, rh=58, hf=c['pale'],
              aligns=['c', 'c', 'c', 'l'], cell_colors={(2, 2): c['acc']})
    y = section(d3, y + 22, 'A/B 迭代计划（row2 · 每周只动 1–2 词位）', 2)
    rows = [
        ['周期', '动作', '盯指标', '判定线'],
        ['W1', '候选2 上架，B 风详情', '曝光 / CTR', 'CTR 2%+ 冻结'],
        ['W2', '不达标则只换主图1', 'CTR / 询盘率', '达类目均值'],
        ['W3', '曝光乏力则换核心词位', '搜索曝光', '周环比 +15%'],
        ['W4', '词池复盘落档 publish_log', '曝光/CTR/转化', '三项不降则冻结'],
    ]
    y = table(d3, y + 4, [112, 420, 250, 282], rows, rh=56, hf=c['pale'],
              aligns=['c', 'l', 'c', 'l'])
    y = note_card(d3, y + 20, '回挂模块说明',
                  '表中判定线为占位值，执行时换成后台实时类目均值；详情 14 屏改版走 '
                  'hotcase-longimage-skill，新版只新增不覆盖旧版。', c['acc'], c['pale'])
    save_case(2, [im, im2, im3])

# ============ CASE 03 ============
def case03():
    c = CASES[3]
    im, d, y0 = page(3, 1)
    y = section(d, y0 + 4, '2026 第 41 周（10.05–10.11）大盘漏斗 · 对比第 40 周', 3)
    y = funnel(d, y + 12,
               [342800, 8912, 402, 268, 236],
               ['曝光', '点击', '询盘', '下单', '支付'],
               [('342,800 · +4.1% ↑', GOOD), ('8,912 · CTR 2.60% · -2.3% ↓', BAD),
                ('402 · +1.5% ↑', GOOD), ('268 · -5.6% ↓', BAD),
                ('236 · -3.3% ↓', BAD)],
               c['acc'], rh=80)
    y = section(d, y + 22, '其余核心指标一张表', 3)
    rows = [
        ['指标', '第 41 周', '环比', '判断'],
        ['GMV', '¥96,400', ('-3.2% ↓', B(25), BAD), '跟随支付买家回落'],
        ['询盘›下单率', '66.7%', ('-4.8pct ↓', B(25), BAD), '报价/起订量摩擦'],
        ['退款率', '1.9%', ('持平', B(25), MUT), '正常'],
        ['综合评分', '4.7', ('持平', B(25), MUT), '履约稳定'],
    ]
    y = table(d, y + 4, [250, 230, 220, 364], rows, rh=62, hf=c['pale'],
              aligns=['c', 'c', 'c', 'l'])
    y = note_card(d, y + 24, '大盘一句话结论',
                  '流量还在涨（曝光 +4.1%），掉的是「点击›下单」两个站内环节：CTR 连续两周低于自家 '
                  '4 周均值 3.02%，下单率跌 4.8pct——不是流量结构问题，是素材与价格档问题。',
                  c['acc'], c['pale'])

    im2, d2, y0 = page(3, 2)
    y = section(d2, y0 + 4, 'TOP5 商品卡（指标 + 环比 + 一句归因 · 须有证据）', 3)
    rows = [
        ['商品', '曝光', 'CTR', '询盘', '转化', '环比', '一句归因'],
        ['抽屉式收纳箱', '96,300', '3.4%', '128', '4.2%', ('+31%', B(23), GOOD), '10.08 活动位加持（活动记录可查）'],
        ['真空压缩袋', '58,700', '3.1%', '86', '3.8%', ('+18%', B(23), GOOD), '10.02 换主图后 CTR +38%'],
        ['桌面收纳架', '44,200', '2.2%', '61', '2.9%', ('-6%', B(23), BAD), '主图 2 个月未换，素材老化'],
        ['内衣分隔盒', '31,500', '2.8%', '74', '1.1%', ('-12%', B(23), BAD), '询盘高转化低：起订 200 偏高'],
        ['化妆品收纳架', '18,900', '1.9%', '23', '2.2%', ('-22%', B(23), BAD), '核心词排名 -6 位'],
    ]
    y = table(d2, y + 4, [200, 122, 100, 100, 100, 110, 332], rows, rh=68, hf=c['pale'],
              aligns=['l', 'c', 'c', 'c', 'c', 'c', 'l'])
    y = section(d2, y + 24, '沉没成本清单（90 天 0 转化 · 处置决策）', 3)
    rows = [
        ['品名', '状态', '处置'],
        ['藤编收纳篮（小）', '占坑位 90 天 0 支付，引流词与品不符', '下架，词位让给抽屉箱'],
        ['分隔抽屉隔板 B', '有点击 0 询盘，详情停留 9 秒', '走 14 屏改版后再观察 2 周'],
        ['铁艺文件架', '0 曝光，类目错挂「办公文具」', '改挂类目重新发品（row1）'],
    ]
    y = table(d2, y + 4, [230, 460, 374], rows, rh=76, hf=c['pale'], aligns=['l', 'l', 'l'])
    y = note_card(d2, y + 24, '归因纪律',
                  '每条归因必须指出证据（活动记录/改图日志/排名截图）；说不出证据的一律写「待验证假设」，'
                  '禁止把大盘波动写成自身动作成果。', c['acc'], c['pale'])

    im3, d3, y0 = page(3, 3)
    y = section(d3, y0 + 4, '诊断树走查（row4：先查平台动作，再查自身）', 3)
    y = checklist(d3, y + 6, [
        (True, 'CTR 下滑：活动结束是背景，但压缩袋换图 +38% 证明素材可救——桌面架/化妆品架主图老化优先处理'),
        (True, '下单率下滑：分隔盒询盘 74 转化仅 1.1%，客服记录 11 条显示起订量 200 为最大拒绝理由'),
        (True, '化妆品收纳：核心词排名 -6 位且 30 天趋势向下，非单日噪声，触发词权维护'),
    ], rh=72)
    y = section(d3, y + 20, '下周三件事（可验收 · 写明判定）', 3)
    rows = [
        ['事项', '执行（回挂技能）', '验收判定'],
        ['桌面架、化妆品架主图按 A/B/C 三风格重拍上架',
         'hotcase 出图 + row2 盯 CTR', '两款 CTR 3.02%+'],
        ['内衣分隔盒价格梯度加「20 件试单档」',
         'row1 梯度改档（只新增）', '支付转化 1.1% › 2.5%+'],
        ['压缩袋打法复制到 2 个同类品',
         'row2 词库 + 主图重拍', '搜索曝光周环比 +15% 以上'],
    ]
    y = table(d3, y + 4, [420, 380, 264], rows, rh=88, hf=c['pale'], aligns=['l', 'l', 'l'])
    y = section(d3, y + 6, '复盘 SOP 回写（row4 闭环）', 3)
    y = note_card(d3, y, '数据 › 结论 › 动作 › 验证',
                  '日报表导出 › data-review 提示词生成 1 页周报 › 缺陷归类：点击回 row2、转化与起订量回 '
                  'row1、星级履约回 row3 › 下周同一张漏斗表验证。30 天趋势为准，不为单日噪声改版。',
                  c['acc'], c['pale'])
    save_case(3, [im, im2, im3])

if __name__ == '__main__':
    case01()
    case02()
    case03()
    print('ALL DONE ->', OUT)
