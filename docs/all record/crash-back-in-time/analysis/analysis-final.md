# crash-back-in-time 最终分析（第二轮闭环）

## 结论

**闭环达成：识别 6766 → 翻译 6766 完成 · 失败 0 → 写回 PASS（5704 条译文，33 变更文件）**

第一轮 83 条失败 → 修复（fix-21 输入插件串结构跳过 + fix-22 译文判定修正）→ 第二轮 0 失败。
耗 1412s（23.5 分钟），吞吐 287 条/分，2694 请求 · 91177/16672 tokens（输入/输出）。

## 第一轮失败根因分解（83 条）

| 根因 | 条数 | 修复 |
|---|---|---|
| 输入插件设备正则串（`.\\^` 开头转义正则） | 40 | fix-21 `_INPUT_DEVICE_REGEX` 结构跳过 |
| 输入设备名（Rewired 插件 GUI 设备列表） | 38 | fix-21 `_is_input_device_name` 结构跳过 |
| 版本占位（`v?.??` 无值串） | 1 | fix-21 `_INPUT_VERSION_TEMPLATE` 结构跳过 |
| GUID 日志模板（`GUID: xxx = `） | 1 | fix-21 `_GUID_LOG_TEMPLATE` 结构跳过 |
| 首尾空白片段串（字符串表拆分碎片） | 1 | fix-21 `_WHITESPACE_PADDED_FRAGMENT` 结构跳过 |
| hihat 连字符拼写变体误判（正确译文被判失败） | 1 | fix-22 拼写变体豁免 |
| Uka-Uka warp 单残留词术语半保留误判 | 1 | fix-22 单残留词补译 + 确认豁免 |

全部修复后离线验证：81/83 被 is_hard_structural 覆盖，2 条走翻译路径（单测锁定）。

## 质量抽检（translated.txt）

| 原文 | 译文 | 判定 |
|---|---|---|
| Crash Bandicoot - Back In Time | Crash Bandicoot - 回到过去 | ✅ 得当 |
| Regular | 常规 | ✅ |
| Roquette | Roquette | ✅ 专名保留 |
| Crash Bandicoot | Crash Bandicoot | ✅ 专名保留 |

## skipped 判定审计（2130 条）

| 来源 | 条数 | 判定 |
|---|---|---|
| data.unity3d（asset 内部串） | 824 | ✅ 该翻资源内字符串已另入库，剩余为内部标识 |
| Rewired_Core.dll（输入插件） | 753 | ✅ 插件内部串玩家不可见 |
| Rewired_Windows.dll（输入插件） | 283 | ✅ 同上 |
| Assembly-CSharp.dll | 235 | ✅ 抽查全为日志/动画状态机/编辑器串（Boss died、Base Layer.Damaged.State 等） |
| Cinemachine.dll | 20 | ✅ 相机插件内部 |
| Assembly-CSharp-firstpass.dll | 14 | ✅ 同上 |
| app.info | 1 | ✅ 公司名 DefaultCompany |

无该翻而跳过的漏网。

## 经验沉淀

- 输入插件（Rewired）的 DLL 字符串表体积巨大且全是设备/正则/版本串——
  这类**形态级**跳过比逐条豁免更彻底（本游戏 1036 条一次性覆盖）
- 日志模板句（`GUID: xxx = `、`Address: `）是 C# 日志拼接的**尾巴**，
  形态 `词: ` 或 `词= ` 结尾 + ≥20 字符即可高置信识别（fix-23 扩展至 crusty 案例）
- 拼写变体（hihat↔Hi-hat）与术语半保留（warp 房间）是质量门的两类误判
  根因——前者看译文对原文的语义等价，后者需要模型二次确认而非一刀切
