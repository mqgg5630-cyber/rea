# 爆款案例复刻 · 选品开款 × 视觉优化（演示复盘）

基于 `deliverable/ACCIO_REPLICATION.md`（rounds 12–13 逆向证据）复刻的
Accio/1688 打法演示案例：

- **四维选品**：趋势选品 / 热门关键词选品 / 竞品选品 / 下游选品
- **三法开款**：改款（快）· 创款（中）· 开款（稳）
- **视觉四件套**：主图 / 详情页 / 首页 / 短视频（AI 辅助高效作图）
- **数据复盘**：CTR、询单转化、成本、周期（示例复盘口径，非平台真实数据）

## 交付物

| 文件 | 说明 |
|---|---|
| `HOTCASE_REPLICA.pptx` | 17 页演示稿（16:9，微软雅黑，可编辑） |
| `HOTCASE_REPLICA.pdf` | 同内容 PDF（Noto Sans SC 子集嵌入，跨平台保真） |
| `img/` | AI 生成的案例素材：优化前/后主图、套装矩阵图 |
| `charts/` | 6 张数据图（matplotlib，示例复盘口径） |
| `build/build_deck.py` | 完全可复现的构建脚本（图表 + PPTX + PDF 同一内容源） |

## 案例设定

果趣星礼 · DIY 鞋花 12 枚主题套装（洞洞鞋配饰，1688 源头工厂白牌）。
蓝海定位：供需比 2.4 / 竞争集中度 26%，价格空档带 ¥12.9–15.9。
30 天战役结论（示例）：CTR 1.8%→4.6%，视觉成本 ¥3,200→¥180/套（-94%），
选品周期 14 天→2 天，爆款成功率 18%→34%。

## 合规声明

全部经营数据为**示例复盘口径**，用于演示复刻方法论；图像为 AI 生成的自有
示例素材；不构成任何经营承诺，与任何真实店铺无关。

复现：`python3 build/build_deck.py`（需 venv：python-pptx、matplotlib、
pillow、reportlab、fonttools、brotli；CJK 字体由 @fontsource/noto-sans-sc
woff2 转 TTF，见构建脚本顶部常量）。
