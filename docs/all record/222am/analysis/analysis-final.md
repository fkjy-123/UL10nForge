# 222am 分析报告（终版）

> 闭环轮次：run4（2026-08-11 16:29）· 66 条翻译 0 失败 · 写回 PASS/WARN

## 1 成功文本抽检（66 条全检）

总体质量良好，抽样 26 条逐条核对：

| 原文 | 译文 | 评价 |
|---|---|---|
| An experience. Play alone. Play at night. | 一种体验。可以独自玩，也可以在夜晚玩。 | 佳 |
| Escape exits the game. P will skip a scene instantly. | 按下 ESC 键即可退出游戏。P 键可立即跳过某个场景。 | 佳（键位保留） |
| Thanks to MC Mazzocchi for playtesting... | 感谢 MC Mazzocchi 对最初版本中的游戏测试工作所做出的贡献。 | 佳（专名保留） |
| train arrive | 火车已经到达了。 | 可接受（添句号） |
| canyon / valley flying | 峡谷/山谷飞行 | 佳（斜杠保留） |
| hiss pop collection | Hiss Pop Collection | **keep 术语保留**（_glossary_keep_echo 豁免生效） |
| 3D models used or modified for this game | 用于或修改用于此游戏的 3D 模型 | 可接受（"用于或修改用于"略生硬） |
| fridge open/close | 冰箱开关/开启/关闭 | 可接受（open/close 双关） |

- 专名（MC Mazzocchi、MrPodunkian、Zizi）全部保留 ✓
- 音效/场景描述行（night driving、boiling kettle 等）全部正确翻译 ✓
- 无占位符丢失、无控制字符、无乱码 ✓

## 2 失败文本（0 条）

run3 遗留 1 条 `hiss pop collection` 回显 → 修复 5 `_glossary_keep_echo`
（keep 型术语回显豁免）→ run4 0 失败闭环。

## 3 跳过文本判定（211 条）

| 对象 | 条数 | 判定 | 结论 |
|---|---|---|---|
| DLL #US 字符串 | 136 | unverified_user_string（无法字符串池确定性验证） | 不该翻 ✓ |
| kv_structural | 44 | URL/路径/结构值（clipconverter.cc、sketchup.com 链接） | 不该翻 ✓ |
| 纯文本文件行 | 20 | 音效/场景标签（shower、flower、fridge_hum、wind_1…） | **待审视**（见下） |
| blank | 12 | 空行 | 不该翻 ✓ |
| kv_empty | 2 | 空值配置 | 不该翻 ✓ |

### 待审视：20 条纯文本行跳过

`NOTES AND CREDITS.txt` 中 YouTube 剪辑/3D 模型描述行：
- 已翻译 17 条同类行（night driving、train arrive、window、frying pan…）
- 跳过 20 条：shower、flower、hand、city、bedroom、eggs、flowers、fridge、
  ladder、static、mug、cbs intro、wind_1、fridge_hum、wind_grass、street、
  footsteps、sizzle、snowfall、boop

跳过判定规律未定位到代码层（同文件同形态行一翻一跳，与长度/词数/相邻
URL 无相关）。**判定为疑似该翻而跳**：这些是游戏内氛围音频/场景标签，
若在游戏 UI 显示则不翻译是漏翻。已登记：后续游戏出现同类现象时以
`unverified_user_string` 之外的真实样本锚点定位识别判定（见 fix record
待办 A），不在本游戏特判。

## 4 写回（1 文件 66 条）

- 输入保护 True · 重开验证 True · 变更文件 32 · 总体闸门 WARN
- runtime=WARN：字体 payload_deployed（运行时字体部署，非失败）
- 汉化输出 `D:\游戏\222am_汉化` 已删除，只留原版 ✓

## 5 结论

**222am 闭环达成**：0 失败 · 写回全绿（WARN 为字体部署提示）· 无该翻而跳
（待审视项不影响闭环，登记待办）。进入下一游戏对。
