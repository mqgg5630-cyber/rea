# -*- coding: utf-8 -*-
"""Parse AWB 话术 flat text into structured JSON for the 8 scenarios."""
import re, json

flat = open('google_drive/awb_flat.txt').read()
marks = [(m.start(), m.group()) for m in re.finditer(r'场景[一二三四五六七八](?=[^点])', flat)]
segs = []
for i, (pos, _m) in enumerate(marks):
    end = marks[i+1][0] if i+1 < len(marks) else len(flat)
    segs.append(flat[pos:end])

NAME = r'[一-龥A-Za-z0-9（）之·+/&；]{2,20}'
TITLES = ['市场洞察', '选品开款', '视觉优化', '运营获客', '数字营销', '客户管理与业务转化', '履约复购', '团队管理']
NUM = '一二三四五六七八'

SELL_NAMES = [
 ['经营数据自由查询','竞店竞品分析','价格带分析','行业热词追踪','平台新规解读'],
 ['数据驱动选品','关键词选品','竞品爆款分析','改款建议','排产指导'],
 ['AI出图对标头部标准','全场景覆盖','即时修改','工厂风变电商风','批量出图'],
 ['搜索排名优化','批量上新发品','全店诊断修复','店铺指标提升','数据复盘'],
 ['智能推广策略','投产比实时监控','广告自动优化','看数做报表'],
 ['客户背调','智能报价','沉睡客户激活','智能客服','询盘质量评估'],
 ['订单全流程跟踪','库存智能预警','异常自动提醒','复购自动激活'],
 ['自动化办公','知识库沉淀','新人快速上手','使用报表监控','任务定时提醒'],
]

out = []
for idx, seg in enumerate(segs):
    n, ch = idx + 1, NUM[idx]
    rec = {'title': TITLES[idx]}
    assert seg.startswith(f'场景{ch}'), seg[:20]
    assert TITLES[idx] in seg[:40], seg[:40]
    sub = seg[len('场景' + ch):seg.find('【工厂痛点】')]
    rec['subtitle'] = sub[len(TITLES[idx]):].strip('·/ ')

    m = re.search(r'【工厂痛点】(.+?)' + re.escape(f'{n}.1场景开场话术'), seg)
    rec['pain'] = m.group(1).strip('：:') if m else None

    rec['talks'] = [(t[0], t[1], t[2].strip('“” ')) for t in
                    re.findall(r'话术([ABC])（([^）]+)）：["“](.+?)["”](?=话术[ABC]|◉工厂老板视角)', seg)][:3]

    m = re.search(r'◉工厂老板视角(.+?)' + re.escape(f'{n}.2核心卖点'), seg)
    rec['boss'] = m.group(1).strip('：: ') if m else None

    m = re.search(re.escape(f'{n}.2核心卖点') + r'(.+?)' + re.escape(f'{n}.3常见反对意见'), seg)
    core = m.group(1)
    names = SELL_NAMES[idx]
    sps = []
    pos = 0
    for i, nm in enumerate(names):
        p = core.find(nm, pos)
        assert p >= 0, (n, nm, core[:200])
        # 名字后须紧跟“：”；若该处不是，继续找
        while core[p+len(nm):p+len(nm)+1] != '：':
            q = core.find(nm, p+1)
            if q < 0 or (i+1 < len(names) and core.find(names[i+1], pos) < q):
                break
            p = q
        txt0 = p + len(nm) + 1
        txt1 = core.find(names[i+1], txt0) if i+1 < len(names) else len(core)
        if txt1 < 0: txt1 = len(core)
        sps.append((nm, core[txt0:txt1].strip('，。； ')))
        pos = txt1
    rec['sells'] = sps

    m = re.search(re.escape(f'{n}.3常见反对意见及应对') + r'(.+?)' + re.escape(f'{n}.4场景金句'), seg)
    obj_region = m.group(1) if m else ''
    rec['objections'] = [(q.strip(), a.strip('“” ')) for q, a in
                         re.findall(r'▶(.+?)◆应对话术[：:]["“]?(.+?)["”]?(?=▶|$)', obj_region)]

    m = re.search(re.escape(f'{n}.4场景金句') + r'["“]?(.+?)["”]?★促单收尾', seg)
    rec['quote'] = m.group(1).strip('“” ') if m else None

    m = re.search(r'★促单收尾["“]?(.+?)["”]?\s*$', seg, re.S)
    rec['close'] = m.group(1).strip('“” ') if m else None

    out.append(rec)
    print(n, rec['title'], '| sub:', rec['subtitle'], '| talks:', len(rec['talks']),
          '| sells:', len(rec['sells']), '| obj:', len(rec['objections']),
          '| pain?', bool(rec['pain']), '| boss?', bool(rec['boss']),
          '| quote?', bool(rec['quote']), '| close?', bool(rec['close']))

json.dump(out, open('google_drive/awb_parsed.json', 'w'), ensure_ascii=False, indent=1)
print('saved google_drive/awb_parsed.json')
