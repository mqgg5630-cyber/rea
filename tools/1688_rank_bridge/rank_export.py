# -*- coding: utf-8 -*-
"""
[摆渡脚本] 1688 店铺排名取数 → rank_export.json
====================================================
用途：补齐「复刻案例」缺失的最后一环——真实取数。
跑法（三选一，全部在你自己的授权环境内执行，凭据不出你的设备）：

A. 跑在 Accio Work 客户端对话里（推荐）
   在双方已授权的「1688 生意助手」对话中发送：
     「查本店在全国·动漫/影视/明星周边（二级类目 ID 201303011）的 GMV
       店铺排名与近 90 天趋势序列 + 近 12 周支付金额序列，把结果按
       rank_export.schema.json 的格式写成 JSON 文件给我。」
   然后把 Agent 产出的 JSON 丢给 Arena（重命名 rank_export.json）。

B. 跑在本地（你的电脑，已装好 1688 开放平台应用 key/令牌）
   把环境变量配好再执行本脚本：
     export ALIBABA_APP_KEY=xxx
     export ALIBABA_APP_SECRET=yyy
     export ALIBABA_ACCESS_TOKEN=zzz
     python3 rank_export.py
   脚本按官方开放平台签名规则调 com.alibaba.trade / 生意参谋类目
   排行接口，落地 rank_export.json。

C. 纯手工
   在 1688 后台生意参谋自己导出 CSV/截图，或照着
   rank_export.schema.json 手填数字，同样命名 rank_export.json。

三者任意一个得到 rank_export.json 之后，把它发回 Arena 会话：
  我侧的 build_acrylic_case.py 检测到该文件即自动出“真数据版 PDF”。
"""
import os, sys, json, time, hashlib, urllib.parse, urllib.request

# ---------- 排名范围（与对话截图口径一致，可按需改） -----------
SCOPE = {
    "owner": "福建火绒草广告有限公司",
    "trade": "亚克力冰箱贴 · 动漫/明星周边定制",
    "addressLevel": 0,                     # 0=全国
    "category_id": 201303011,              # 二级类目：动漫/影视/明星周边
    "category_name": "动漫/影视/明星周边",
    "metric": "gmv_rank_shop",
    "window_days": 90,
    "window_weeks": 12,
}

def call_open_platform(params: dict) -> dict:
    """1688 开放平台签名调用（占位实现）。
    真接口在你本机跑：请按你的应用文档，把
    https://gw.open.1688.com/openapi/… 换成对应排行/参谋 API 的路由。
    """
    app_key = os.environ.get("ALIBABA_APP_KEY")
    app_secret = os.environ.get("ALIBABA_APP_SECRET")
    token = os.environ.get("ALIBABA_ACCESS_TOKEN")
    if not (app_key and app_secret and token):
        sys.exit("[Bridge B] 缺环境变量 ALIBABA_APP_KEY / _SECRET / _TOKEN。"
                 "没配就走 Bridge A/C；不要在此脚本里硬写密码。")
    p = dict(params)
    p["app_key"] = app_key
    p["sign_method"] = "md5"
    p["sessionKey"] = token
    p["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    base = app_secret
    base += "".join(f"{k}{p[k]}" for k in sorted(p))
    base += app_secret
    p["sign"] = hashlib.md5(base.encode("utf-8")).hexdigest().upper()
    url = "https://gw.open.1688.com/openapi/http/1/param2/" \
          + "1/" + params["api"]  # 按你应用的 API 路由改
    # 注意：Arena 沙箱出不了 1688.com —— 本段代码只能在**你的机器上**生效
    with urllib.request.urlopen(url, data=urllib.parse.urlencode(p).encode(), timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    print("[Bridge] 目标口径：", json.dumps(SCOPE, ensure_ascii=False))
    env = os.environ
    print("[Bridge] 判定走法：", "B（开放平台取数）" if env.get("ALIBABA_APP_KEY") else "叫你用 A / C",
          "——Arena 沙箱内 1688.com 出域受限，请全程不要随意贴账号密码给 AI。")
    if env.get("ALIBABA_APP_KEY"):
        # 按你应用所授权的 API 名称替换此处（示意：
        # com.alibaba.data.analytics:category.shop.rank.query 等）
        try:
            result = call_open_platform({
                "api": "你的排行接口名",
                "addressLevel": SCOPE["addressLevel"],
                "categoryId": SCOPE["category_id"],
                "period": f'{SCOPE["window_days"]}d',
            })
        except Exception as e:  # 网络/签名失败也落地骨架，便于手填
            print("[Bridge B] 已发起但失败：", e, "→ 退化为预填骨架")
            result = None
    else:
        result = None

    if result is None:
        tpl = {
            "_schema": "rank_export.schema.json",
            "_fill_mode": "manual_or_accio_export",
            "scope": SCOPE,
            "metrics": {
                "rank_now": None,          # 整数，如 2346
                "rank_total": None,        # 类目内有成交店铺总数
                "rank_delta_90d": None,    # 近90天升/降名次，升为正
                "turnover_weekly_gmv_wan": [None] * SCOPE["window_weeks"],
                "rank_trend_90d": [None] * SCOPE["window_days"],
            },
            "diagnosis": {
                "traffic_source_natural_pct": None,
                "pay_conversion_pct": None,
                "rebuy_gmv_pct": None,
                "top_sku_gmv_pct": None,
            },
            "note": "手填或贴 AccioWork 导出；Arena 侧 build_acrylic_case.py 会自动消化。",
        }
        json.dump(tpl, open("rank_export.json", "w"), ensure_ascii=False, indent=2)
        print("[Bridge] 已落地 rank_export.json（骨架 / 或 B 失败后的骨架），"
              "填好后传回 Arena 出真数据版 PDF。")
    else:
        # 真实取到：把 result 映射进同一结构后落地（映射字段因 API 而异，
        # 请按你应用接口返回的 JSON 改这几行）
        data = {
            "_schema": "rank_export.schema.json",
            "_source": "alibaba_open_platform",
            "scope": SCOPE,
            "metrics": {
                "rank_now": result.get("rank"),
                "rank_total": result.get("total"),
                "rank_delta_90d": result.get("rankDelta90d"),
                "turnover_weekly_gmv_wan": result.get("gmvWeekly"),
                "rank_trend_90d": result.get("rankTrend"),
            },
            "diagnosis": result.get("diag", {}),
        }
        json.dump(data, open("rank_export.json", "w"), ensure_ascii=False, indent=2)
        print("[Bridge B] 真实取数成功 → rank_export.json，传回 Arena 即出真数据版。")

if __name__ == "__main__":
    main()
