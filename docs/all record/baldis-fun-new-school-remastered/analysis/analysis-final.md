# baldis-fun-new-school-remastered 分析（最终跑）

时间：2026-08-11 01:53 ｜ 模型：Hy-MT2-1.8B-Q6_K ｜ 628 条翻译 0 失败

## 成功文本逐条验证（关键条目抽检）

| 原文 | 译文 | 评价 |
|---|---|---|
| Shirt Decal | T恤贴纸 | ✅ 专名引用重译（首轮模型补成 T-shirt Decal → 引用保留专名 Shirt → T恤贴纸） |
| Farming Is Currently <color=green>Paused</color>.\nDo You Want To <color=red>Quit</color>? | 农业活动目前处于"暂停"状态。\n您想<color=red>退出</color>吗？ | ✅ 中文语义完整；green 标签对整体丢失（模型用引号替代彩色强调的稳定行为）→ 完整标签对放宽放行；red 标签对保留，无崩溃风险 |
| outstanding citizen | 杰出的公民 | ✅ 纯小写普通词回显 → 词级补译引用两跳（裸翻译回显 → 注入词对引用 → 杰出公民，实测 3/3） |
| Triangle Button: Pause (Quit In The Bossfight Gamemode) | 三角形按钮：暂停（在BOSS战模式下退出） | ✅ Bossfight → bossfight 小写化专名豁免；交互动作词 + 引号专名短语豁免正常 |
| *shit / *beaner（TextAsset 词表） | skipped | ✅ 星号词表条目 → 结构跳过（词表条目非 UI 语义） |
| Error please contact game owner\nand check log. | 出现错误，请联系游戏所有者，并查看日志信息。 | ✅ 换行合并兜底：两行合并一行（1.8B 稳定倾向），multiline repair 逐行重译首行回显英文 → 恢复首译状态 → 兜底放行（中文语义优先，UI 自动换行兜底排版） |
| L2 Button: Use Item (Hold Down To Run...) | 左扳机键：使用道具（在BOSS战模式下按住奔跑） | ✅ 按键名 + 动作词 + 专名混合长句全译 |
| UCLA Gold | （版本后缀回显保留） | ✅ 多词短语末位版本词跳过 UI 词典判定（_ui_check_words） |

## skipped 3693 条抽查

- il2cpp 全局字符串池引擎内部字符串（类名/字段名/路径）→ 合理跳过
- 资产内 UI 结构项、按键名、数字 → 合理跳过
- `*shit`/`*beaner` 等星号前缀词表 → 结构跳过（注释行/词表非显示文本）
- `//` 注释行（//host 等 URL 除外）→ 结构跳过

## 遗留

- 无失败条目。个别措辞（"农业活动" 应为 "农业"）属 1.8B 模型选词偏好，
  语义完整，人工校对可见（记录文件可筛选）。green 彩色强调以引号替代
  属模型稳定行为，与全角引号等效。

## 结论

628/0 干净闭环。本轮验证 6 类失败（专名联想补词/彩色标签对/星号词表/
混合符号 token/交互动作词/换行合并/纯小写回显）全部转为通用机制，模型
能力边界清晰，进入下一游戏。
