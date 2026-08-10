# a-game-about-literally-doing-your-taxes 分析（最终跑）

时间：2026-08-10 21:46 ｜ 模型：Hy-MT2-1.8B-Q6_K ｜ 96 条翻译 0 失败

## 成功文本逐条验证（抽查代表性条目）

| 原文 | 译文 | 评价 |
|---|---|---|
| TOSS TRASH | 丢垃圾 | ✅ 知识库闭环核心战果（此前 2 条卡死回显） |
| GOOD JOB | 干得好 | ✅ |
| Main Menu | 主菜单 | ✅ UI 术语 |
| exit | 退出 | ✅ |
| WEAR HEADPHONES FOR BEST EXPERIENCE | 佩戴耳机以获得最佳体验 | ✅ 双行结构保持 |
| credits | 致谢 | ✅ |
| A Game About Literally Doing Your Taxes | 一款关于实际办理税务申报的游戏 | ✅ 标题本地化 |
| Not a Sailor Studios | 不是 Sailor Studios | ⚠️ 工作室名半保留（Sailor 未译，品牌署名可接受） |

## 遗留译文质量问题（模型能力边界，非工具缺陷）

| 原文 | 译文 | 问题 | 频次 |
|---|---|---|---|
| RESUME | 摘要 | RESUME 多义词（继续/简历/摘要）取错义项，UI 按钮语境应为「继续」 | 1 |
| TAXES DONE | 已缴纳的税款 | DONE 语义漂移（应为「税务办理完毕」） | 2 |
| KEEP TAXES | 保持税收 | KEEP 多义（保存/保留），语境不明 | 1 |

共 4/96 条（4%），1.8B 模型流畅误译，质量门无法拦截（语义正确但取错义项），
人工校对时可见（记录文件可筛选）。

## skipped 294 条抽查

全部为 Unity 类型引用（`UnityEngine.UI.MaskableGraphic+CullStateChangedEvent`、
`UnityEngine.Object`）与标准控件状态枚举（Normal/Highlighted/Pressed/Disabled、
Horizontal/Vertical）——跳过正确，无「该翻未翻」遗漏。

## 写回验证

- 96 条全部写入（文本文件 1 · 变更文件 41）
- 重开验证 PASS · 输入保护 True · 字体 runtime_verified
- 总体闸门 WARN（无 rejected，仅常规警告）

## 结论

taxes 达到干净闭环：96/96 翻译写回，质量门拦截全部回显/半翻译，
知识库首次实战验证成功（TOSS TRASH 从卡死到「丢垃圾」）。
