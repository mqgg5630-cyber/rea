# -*- coding: utf-8 -*-
"""8 份 AWB 场景话术 PDF：reportlab + NotoSansSC，每场景独立配色，配网上案例图。"""
import json, os
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                Table, TableStyle, Image, KeepTogether, Flowable, NextPageTemplate)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FD = '/home/user/fonts'
pdfmetrics.registerFont(TTFont('NSC4', f'{FD}/NotoSansSC_400Regular.ttf'))
pdfmetrics.registerFont(TTFont('NSC5', f'{FD}/NotoSansSC_500Medium.ttf'))
pdfmetrics.registerFont(TTFont('NSC7', f'{FD}/NotoSansSC_700Bold.ttf'))
pdfmetrics.registerFont(TTFont('NSC9', f'{FD}/NotoSansSC_900Black.ttf'))
from reportlab.lib.fonts import addMapping
addMapping('NSC7', 1, 0, 'NSC7')

RECS = json.load(open('google_drive/awb_parsed.json'))
IMGF = {
 1: ('image-search/s1.png',  'Accio Work × 1688 联合产品推广图（图源：ITBEAR）'),
 2: ('image-search/s2.png',  '生意参谋 · 店铺业绩分析数据看板（图源：九数云）'),
 3: ('image-search/s3.jpg',  '电商详情页头图设计实战案例（图源：我要自学网）'),
 4: ('image-search/s4.jpg',  'AI 搜索结果排名优化案例（图源：知乎 · GEO 服务）'),
 5: ('image-search/s5.png',  '效果广告 ROI 优化方法对照表（图源：知乎）'),
 6: ('image-search/s6.png',  'CRM 客户与商机经营管理界面（图源：完美易法）'),
 7: ('image-search/s7.webp', '电商订单履约系统流程示意（图源：易书通）'),
 8: ('image-search/s8.png',  '协同办公 · 知识管理产品界面（图源：精选库）'),
}
ACCENT = {1:'#2463EB',2:'#E07B16',3:'#DB2777',4:'#16A34A',5:'#DC2626',6:'#0891B2',7:'#B45309',8:'#7C3AED'}
OSDIR = 'deliverable/awb'
os.makedirs(OSDIR, exist_ok=True)

# webp -> png
if os.path.exists('image-search/s7.webp'):
    PILImage.open('image-search/s7.webp').convert('RGB').save('image-search/s7_fix.png')
    IMGF[7] = ('image-search/s7_fix.png', IMGF[7][1])

PAGE_W, PAGE_H = A4
ML = MR = 16*mm; MT = 14*mm; MB = 16*mm
CW = PAGE_W - ML - MR

INK = HexColor('#1F2937'); MUT = HexColor('#6B7280'); RULE = HexColor('#E5E7EB')

def shade(c, f):
    """f 越大越接近纯白的 tint"""
    from reportlab.lib.colors import Color
    return Color(c.red + (1-c.red)*f, c.green + (1-c.green)*f, c.blue + (1-c.blue)*f)

def P(name, **kw):
    base = dict(fontName='NSC4', textColor=INK, leading=15, wordWrap='CJK')
    base.update(kw)
    return ParagraphStyle(name, **base)

class Band(Flowable):
    """顶部色带：场景号 + 大标题 + 副标 chips"""
    def __init__(self, n, title, subtitle, accent):
        super().__init__()
        self.n, self.title, self.subtitle, self.accent = n, title, subtitle, HexColor(accent)
        self.h = 56*mm
    def wrap(self, w, h):
        self.width = w
        return (w, self.h + 8*mm)
    def draw(self):
        c = self.canv; W = self.width; H = self.h
        c.setFillColor(self.accent); c.roundRect(0, 0, W, H, 8, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont('NSC5', 9.5); c.drawString(7*mm, H-9*mm, 'AWB 核心权益及售卖话术 · 八大应用场景')
        # 巨号数字
        c.setFillColor(white); c.saveState()
        c.setFillAlpha(0.18); c.setFont('NSC9', 58)
        c.drawRightString(W-7*mm, H-26*mm, f'{self.n:02d}')
        c.restoreState()
        c.setFillColor(white)
        c.setFont('NSC9', 26); c.drawString(7*mm, H-24*mm, f'场景{"一二三四五六七八"[self.n-1]} · {self.title}')
        # subtitle chips
        x = 7*mm; y = H-38*mm
        subs = [s for s in self.subtitle.replace('·', ' ').replace('/', ' ').split(' ') if s]
        for it in subs:
            w = pdfmetrics.stringWidth(it, 'NSC5', 9.5) + 6*mm
            if x + w > W - 30*mm: x = 7*mm; y -= 9*mm
            c.setFillColor(white); c.roundRect(x, y, w, 6.6*mm, 3.3*mm, stroke=0, fill=1)
            c.setFillColor(self.accent); c.setFont('NSC5', 9.5); c.drawString(x+3*mm, y+2.1*mm, it)
            x += w + 2.2*mm

        c.setFillColor(white); c.setFont('NSC4', 8.5)
        c.drawString(7*mm, 4.5*mm, 'Accio Work（AWB）1688 华南商家共创 · 反对意见处理大全')

class SecTitle(Flowable):
    def __init__(self, text, accent):
        super().__init__(); self.text, self.accent = text, HexColor(accent)
    def wrap(self, w, h): self.width = w; return (w, 11*mm)
    def draw(self):
        c = self.canv
        c.setFillColor(self.accent); c.rect(0, 2.4*mm, 2.6*mm, 6.2*mm, stroke=0, fill=1)
        c.setFillColor(INK); c.setFont('NSC7', 14.5); c.drawString(4.6*mm, 3.4*mm, self.text)

def call(text, bg, fg=None, fs=10.5, lead=None, pad=4*mm, radius=None, bold=False, align=None):
    st = P('c', fontName='NSC7' if bold else 'NSC4', fontSize=fs,
           textColor=fg or INK, leading=lead or fs*1.55, alignment=align if align is not None else 0)
    t = Table([[Paragraph(text, st)]], colWidths=[CW])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),
        ('LEFTPADDING',(0,0),(-1,-1),pad),('RIGHTPADDING',(0,0),(-1,-1),pad),
        ('TOPPADDING',(0,0),(-1,-1),pad-1),('BOTTOMPADDING',(0,0),(-1,-1),pad-1)]))
    return t

def build(n):
    r = RECS[n-1]; acc = ACCENT[n]; accH = HexColor(acc)
    story = [Band(n, r['title'], r['subtitle'], acc)]

    story.append(SecTitle('工厂痛点 · 这一行生意卡在哪', acc))
    story.append(Table([[Paragraph(r['pain'], P('p', fontSize=10.5, leading=16.5, textColor=INK))]], colWidths=[CW],
                       style=TableStyle([('BACKGROUND',(0,0),(-1,-1),shade(accH, 0.9)),
                       ('BOX',(0,0),(-1,-1),0.75,shade(accH, 0.55)),
                       ('LEFTPADDING',(0,0),(-1,-1),4*mm),('RIGHTPADDING',(0,0),(-1,-1),4*mm),
                       ('TOPPADDING',(0,0),(-1,-1),3*mm),('BOTTOMPADDING',(0,0),(-1,-1),3*mm)])))
    story.append(Spacer(1, 5*mm))

    story.append(SecTitle(f'{n}.1 场景开场话术（A / B / C）', acc))
    for tag, nm, txt in r['talks']:
        chip = Table([[Paragraph(f'话术{tag}', P('ch', fontName='NSC7', fontSize=10, textColor=white, alignment=TA_CENTER))]],
                     colWidths=[17*mm], rowHeights=[8*mm])
        chip.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),accH),
                                  ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        body = [Paragraph(f'切入法：{nm}', P('t1', fontName='NSC7', fontSize=11, textColor=accH, leading=14)),
                Spacer(1, 1.4*mm),
                Paragraph(f'“{txt}”', P('t2', fontSize=10.5, leading=16.5, textColor=INK))]
        row = Table([[chip, body]], colWidths=[21*mm, CW-21*mm])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                 ('BOX',(0,0),(-1,-1),0.6,RULE), ('TOPPADDING',(0,0),(-1,-1),3*mm),
                                 ('BOTTOMPADDING',(0,0),(-1,-1),3*mm),
                                 ('LEFTPADDING',(0,0),(-1,-1),3*mm),('RIGHTPADDING',(0,0),(-1,-1),3*mm)]))
        story.append(KeepTogether(row)); story.append(Spacer(1, 2.4*mm))
    story.append(Spacer(1, 2.6*mm))

    story.append(KeepTogether([SecTitle('工厂老板视角', acc),
                 Table([[Paragraph(r['boss'], P('b', fontSize=10.5, leading=16.5, textColor=HexColor('#374151'))),
                         ]], colWidths=[CW], style=TableStyle([
                        ('BACKGROUND',(0,0),(-1,-1),HexColor('#F3F4F6')),
                        ('LINEBEFORE',(0,0),(0,-1),2.2,accH),
                        ('LEFTPADDING',(0,0),(-1,-1),4*mm),('RIGHTPADDING',(0,0),(-1,-1),4*mm),
                        ('TOPPADDING',(0,0),(-1,-1),3*mm),('BOTTOMPADDING',(0,0),(-1,-1),3*mm)]))]))
    story.append(Spacer(1, 5*mm))

    story.append(SecTitle(f'{n}.2 核心卖点', acc))
    rows=[]
    for nm, desc in r['sells']:
        rows.append([Paragraph('●', P('d', fontSize=8, textColor=accH, leading=15)),
                     Paragraph(f'<font name="NSC7">{nm}：</font>{desc}', P('s', fontSize=10.5, leading=15.5))])
    t = Table(rows, colWidths=[7*mm, CW-7*mm])
    t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),2.2*mm),
                           ('TOPPADDING',(0,0),(-1,-1),2.2*mm),('LEFTPADDING',(0,0),(-1,-1),0)]))
    story.append(t); story.append(Spacer(1, 5*mm))

    story.append(SecTitle(f'{n}.3 常见反对意见及应对', acc))
    for q, a in r['objections']:
        block = Table([[Paragraph(f'<font name="NSC7" color="{acc}">◆ 异议：</font><font name="NSC7">{q}</font>',
                                  P('q', fontSize=10.5, leading=15.5, textColor=INK))],
                       [Paragraph(f'<font name="NSC7" color="#16A34A">应对话术：</font>“{a}”',
                                  P('a', fontSize=10.2, leading=15.5, textColor=HexColor('#374151')))]],
                      colWidths=[CW])
        block.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),4*mm),('RIGHTPADDING',(0,0),(-1,-1),4*mm),
                                   ('TOPPADDING',(0,0),(-1,-1),2.4*mm),('BOTTOMPADDING',(0,0),(-1,-1),2.4*mm),
                                   ('BOX',(0,0),(-1,-1),0.6,RULE)]))
        story.append(KeepTogether(block)); story.append(Spacer(1, 2.4*mm))
    story.append(Spacer(1, 2.6*mm))

    story.append(KeepTogether([SecTitle(f'{n}.4 场景金句', acc),
        Paragraph(f'“{r["quote"]}”',
                  P('gq', fontName='NSC7', fontSize=14, leading=21, textColor=accH, alignment=TA_CENTER)),
        Spacer(1, 4*mm)]))
    story.append(Spacer(1, 1*mm))

    story.append(KeepTogether([SecTitle('促单收尾', acc),
        Table([[Paragraph(f'“{r["close"]}”', P('cl', fontSize=10.5, leading=16.5, textColor=white))]],
              colWidths=[CW], style=TableStyle([('BACKGROUND',(0,0),(-1,-1),accH),
              ('LEFTPADDING',(0,0),(-1,-1),4.5*mm),('RIGHTPADDING',(0,0),(-1,-1),4.5*mm),
              ('TOPPADDING',(0,0),(-1,-1),3.4*mm),('BOTTOMPADDING',(0,0),(-1,-1),3.4*mm)]))]))
    story.append(Spacer(1, 6*mm))

    img_path, cap = IMGF[n]
    im = PILImage.open(img_path); iw, ih = im.size
    w = CW*0.86; hgt = w*ih/iw
    if hgt > 95*mm: hgt = 95*mm; w = hgt*iw/ih
    story.append(KeepTogether([SecTitle('应用参考 · 真实案例图', acc),
        Table([[Image(img_path, width=w, height=hgt)]],
              colWidths=[CW], style=TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),
              ('TOPPADDING',(0,0),(-1,-1),1*mm),('BOTTOMPADDING',(0,0),(-1,-1),1*mm)])),
        Paragraph(cap, P('cap', fontSize=8.6, textColor=MUT, alignment=TA_CENTER, leading=12))]))

    out = f'{OSDIR}/AWB_场景{n}_{r["title"]}.pdf'
    def footer(cv, doc):
        cv.saveState(); cv.setFillColor(MUT); cv.setFont('NSC4', 8)
        cv.drawString(ML, 8*mm, f'Accio Work（AWB）· 场景{"一二三四五六七八"[n-1]} {r["title"]} · 共创业内参考资料')
        cv.drawRightString(PAGE_W-MR, 8*mm, f'{doc.page}')
        cv.setStrokeColor(RULE); cv.line(ML, 12*mm, PAGE_W-MR, 12*mm); cv.restoreState()
    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                          title=f'AWB 场景{"一二三四五六七八"[n-1]} {r["title"]}')
    fr = Frame(ML, MB, CW, PAGE_H-MT-MB, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='p', frames=[fr], onPage=footer)])
    doc.build(story)
    print('OK', out)

for n in range(1, 9):
    build(n)
