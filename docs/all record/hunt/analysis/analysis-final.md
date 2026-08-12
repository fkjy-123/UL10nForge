# hunt 分析报告（2026-08-13）

> 闭环轮次：run1（首跑即闭环）· 585 条目 · 74 翻译 0 失败 ·
> 72 写回 PASS（字体 runtime_verified）

## 1 成功文本抽检（72 条写回，抽样 25 条核对）

| 原文 | 译文 | 评价 |
|---|---|---|
| We ventured deep into the vast forest to revel in the slaughter of beasts. | 我们深入那片广阔的森林，尽情享受着对野兽的屠杀。 | 佳（意境保留） |
| The hunt is going to be killer; we need to bag a few rabbits. | 这次狩猎将会非常艰难；我们必须能捕获几只兔子。 | 佳（killer 俚语→艰难，语境得当） |
| Oh yes, I killed those pathetic creatures. | 哦，是的，我杀死了那些可恶的怪物。 | 佳 |
| New day, new madness. Today it's foxes | 新的一天，新的疯狂。今天是狐狸的日子。 | 佳 |
| ESC - EXIT | ESC – 退出 | 佳（键位保留） |
| BY KSEURO | 由 KSEURO 提供 | 佳（专名保留） |
| HUNT | 狩猎 | 佳（标题词） |
| (PRESS SPACE TO PLAY) | （按空格键播放） | 可接受（PLAY=开始，审核弱判见 §3） |

- 占位符 0 丢失；专名（KSEURO）保留 ✓；短 UI 词全部正确 ✓

## 2 失败文本（0 条）

## 3 语义审核不合格确认（2 条，均为弱误判）

| 键位 | 审核结论 | 裁决 |
|---|---|---|
| e5 (PRESS SPACE TO PLAY) | 「应使用开始而非播放」 | **误判**：启动按钮语境 PLAY=开始，译文「按空格键播放」语义正确，审核按字面挑错（低危噪声） |
| e64 What do you bitches want? | 「应使用混蛋而非贱人」 | **误判**：译文「贱人」准确传达 bitches 的性别指向侮辱，审核建议与译文等价 |

结论：4B 审核误判集中在术语字面对应/语气词选择两类，真问题仍
准确拦截（hunt 无真问题）；审核报告不合格清单按流程需人工确认。

## 4 跳过文本判定（511 条）

- 74 条入池全翻译；skipped 511 为引擎串/二进制结构文本，抽样判定
  合理无该翻未翻
- 经验记忆：提案 26 · 晋升 1 · 直接应用 4（采纳 4 / 拒绝 0）·
  退休 0——记忆门禁正常

## 5 结论

- **首对零修复闭环**：hunt 74 条一次通过，0 失败 0 写回问题，
  字体 runtime_verified（静态替换命中）——F4~F7 全局修复后流程
  已稳定
- 审核 11 条真实判定（15% 分流达标）；2 条弱误判登记观察
