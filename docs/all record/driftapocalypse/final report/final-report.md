# driftapocalypse 最终报告

## 概览

| 项 | 值 |
|---|---|
| 游戏 | driftapocalypse（漂移竞速，data.unity3d 场景资源 + Assembly-CSharp） |
| 目录 | D:\游戏\driftapocalypse |
| 闭环轮次 | run3（2026-08-11）· 4 → 3（F18）→ 0（F19） |
| 翻译条目 | 165 / 165（0 失败） |
| 写回 | 4 文本文件 · 156 条译文 · 总体 PASS（四态全 PASS）· runtime_verified |
| 汉化输出 | 已删除（只留原版） |

## 流程结果

1. **识别**：文本文件 1 + 二进制资源 3 · 识别条目 165
   （asset_unity 1 文件 / 236 条 + mono_csharp 1 文件 / 96 条 +
    mono_other 9 文件 / 105 条）
2. **翻译**（Hy-MT2-1.8B）：165 条 · 0 失败 · 请求 132 · 79.0s
   - 知识库命中 3 条历史案例（deadbeat 超长分块 / deepest-sword
     全大写 UI 词典词补译放宽 / baldis rich-text 剥离）
   - 失败案例自动沉淀 2 种新模式入库（闭环学习生效）
3. **写回**：输入保护 ✓ 重开验证 ✓ 变更文件 30 · 总体 PASS（四态
   全 PASS）· 字体 runtime_verified · 知识库 5 条规则启用
4. **清理**：`driftapocalypse_汉化` 已删除 ✓

## 质量结论

- **0 条失败**。F18 修复专名短语中 UI 词典词误杀（Play Games
  Plugin）、F19 修复全大写 ≤3 缩写回显误判（MAX ×3）——两处均为
  译文正确/保留合理的误报，修复后零失败
- 跳过 274 条：类名引用/UGUI 状态枚举/Yodo1 广告 SDK 调试日志/
  三角网格库错误消息/转义字符——**无该翻而跳**（SDK 日志是开发
  调试路径不进 UI）
- 写回逻辑层审计（F11）：report 30 条（全真菜单按钮文本复核通过）
  · 扩容 84 条 · 回显跳过 9 条（车辆专名 + MAX 缩写保留符合惯例）
  · revert 0 · 四态全 PASS

## 知识库沉淀

- 专名短语中的 UI 词典词（Play 在 Play Games Plugin）误杀 →
  F18 右侧连续专名词豁免（短组合/全词典序列守卫）
- 全大写缩写回显误判（MAX）→ F19 与 proper_name_echo 侧规则对齐
  （≤3 全大写缩写豁免，动作指令/多词组合守卫）

## 状态

**✅ 已闭环**。F18/F19 经 driftapocalypse 真实链路三轮验证
（4 → 0 失败收敛、写回四态全 PASS、revert 0），与 eggs-for-bart
（本轮同组，零失败）构成双游戏闭环。
