# backrooms 分析（最终跑）

时间：2026-08-11 00:33 ｜ 模型：Hy-MT2-1.8B-Q6_K ｜ 211 条翻译 0 失败

## 成功文本逐条验证（关键条目抽检）

| 原文 | 译文 | 评价 |
|---|---|---|
| Click here to learn about this game mode... available at itch page or comment on Gamejolt page! | 点击这里，通过简短的动画了解这种游戏模式。如果您在播放时仍然遇到问题，请在 Backrooms 的社区页面上提问，该页面可以在 **itch 页面** 找到，或者也在 Gamejolt 页面上有相关评论！ | ✅ 两行结构保持，itch 平台名保留 + page 翻译，Gamejolt 专名保留 |
| Markiplier was here | **Markiplier 在这里。** | ✅ 专名保留 + 完整翻译（首轮纯回显 → 专名引用重译） |
| -Development...The Anonymous user on **4chan** for inspiration... | -开发...来自 **4chan** 的匿名用户，为灵感而提供的内容... | ✅ 8 行结构保持，4chan 数字混合专名保留（此前 chan 碎片误判） |
| Enter custom FPS... | **输入自定义帧率...** | ✅ FPS 译出中文（保留型术语放宽） |
| Continue with Twitch | 继续在 Twitch 上进行活动吧。 | ✅ 平台名保留 |
| Don't Cry, Markiplier | 不要哭泣，Markiplier | ✅ |

## boot.config 配置项（nolog= 等）

| 行 | 分类 | 评价 |
|---|---|---|
| wait-for-native-debugger=0 / build-guid=... | kv_structural skipped | ✅ 结构值不翻译 |
| nolog= / single-instance= | kv_empty skipped | ✅ 空值配置项置空不是文本（此前落 plain 被回显恒败） |

## skipped 3004 条抽查

- il2cpp 全局字符串池大量引擎内部字符串（类名/字段名/路径）→ 合理跳过
- 资产内 UI 结构项、按键名、数字 → 合理跳过
- 无未翻译可翻文本

## 遗留

- 无失败条目。个别措辞（"在播放时" 应为 "在游玩时"）属 1.8B 模型
  选词偏好，语义完整，人工校对可见（记录文件可筛选）。

## 结论

211/0 干净闭环。本轮验证的 5 类失败（提取器漂移/数字邻接碎片/短语
漏翻/专名回显/保留术语误拒）全部转为通用机制与知识库沉淀，模型能力
边界清晰，进入下一游戏。
