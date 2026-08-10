# deadbeat 分析报告（终版）

> 闭环轮次：run7（2026-08-11 17:15）· 1518 条翻译 0 失败 · 写回 PASS

## 1 成功文本抽检

1518 条全量译文无失败。抽样核对（含全部超长歌词）：

| 原文 | 译文 | 评价 |
|---|---|---|
| (Guh) Give it up, give it up…（3183 字符歌词） | 完整中文译文（分块拼接） | 佳（专名 REAPER/Calli 保留） |
| (Three, two, one, swing it) わたし正体不明レディ…（3183 字符歌词） | 完整中文译文（日英混写全翻） | 佳（死神/月亮意象保留） |
| Modern-day killers really must hate fun…（3183 字符歌词） | 完整中文译文（分块拼接） | 佳（无衰减、无回显） |
| Tonight, the moon has rose in a crimson red（2677 字符歌词） | 完整中文译文 | 佳 |
| slash: 999 / miss: 999 / encore 1（HUD 标签值） | 斩击: 999 / 未命中: 999 / 安可 1 | 佳（译例确定性修复） |
| eNCORE 1 / DeAD\nbEAt（艺术大小写） | 按形态恢复 | 佳 |

- 专名（REAPER、Calliope、Calli、Miss Fire Spitting）全部保留 ✓
- 歌词中日文句（戦争/ごめん、失礼しますが死んでください❤）全部翻译 ✓
- 无占位符丢失、无控制字符、无乱码 ✓

## 2 失败文本（0 条）

run 历程：run1 89 → run2 30 → run3 24 → run4 16 → run5 9 → run6 9 →
run7 **0**（本轮 4 项修复，见 fix record）。

## 3 跳过文本判定（1613 条）

| 类别 | 判定 | 结论 |
|---|---|---|
| timeline_track / type_reference / DLL 结构串 | 运行时按名查找的轨道/类型键 | 不该翻 ✓ |
| 输入设备串（gamepad/controller 形态） | 结构串（_INPUT_DEVICE 规则） | 不该翻 ✓ |
| 纯数字/版本/URL/空串 | 结构值 | 不该翻 ✓ |
| 艺术大小写键形态（eNCORE 等对象键名） | 键风格标识符 | 不该翻 ✓ |

skipped 健康：1613 条全部为结构/键形态，无该翻而跳（与 222am 的
NOTES.txt 纯文本行跳过不同类——deadbeat 的跳过全部来自二进制资源
对象键，非用户可见文本行）。

## 4 写回（1 文件 1430 条）

- 输入保护 True · 重开验证 True · 变更文件 56 · 总体闸门 PASS
- 字体 runtime_verified（运行时中文回退）· 汉化输出已清理，只留原版 ✓

## 5 结论

**deadbeat 闭环达成**：0 失败 · 写回 PASS · 无该翻而跳。
收官修复集中在超长歌词翻译链路（分块/输出预算/换行豁免），
该能力直接惠及后续游戏（death-trips 等歌词型游戏）。
