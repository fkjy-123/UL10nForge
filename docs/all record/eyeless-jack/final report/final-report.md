# eyeless-jack 最终报告

## 概览

| 项 | 值 |
|---|---|
| 游戏 | eyeless-jack（无眼杰克，生存恐怖，Assembly-CSharp + 资源） |
| 目录 | D:\游戏\eyeless-jack |
| 闭环轮次 | run1（2 失败）→ run2（1 失败，2026-08-12） |
| 翻译条目 | 193 / 194（1 失败 = 模型能力边界观察项） |
| 写回 | 193 条 · 48 文件变更 · container/object PASS · 字体 runtime_verified |
| 汉化输出 | 已删除（只留原版） |

## 流程结果

1. **识别**：文本文件 1 + 二进制资源 19 · 识别条目 194
   （asset_unity 691 条 / mono_csharp 88 条，跳过 587 条引用类）
2. **翻译**（Hy-MT2-1.8B-Q6_K）：193 / 194 · 请求 132 · 49.2s
   · 235 条/分 · 失败 1（`Look in the mirror` 确定性回显）
3. **写回**：193 条 · 输入保护 ✓ 重开验证 ✓ 变更文件 48 ·
   container/object PASS · 字体 runtime_verified（PASS）· 知识库
   F20 规则启用
4. **清理**：`eyeless-jack_汉化` 已删除 ✓

## 质量结论

- **1 条失败，判定为模型能力边界观察项**（不修复）：`Look in the
  mirror` 两轮逐字相同回显——1.8B 对无上下文短完整句保守回显。
  原文保真、无逻辑风险；无通用规则可表达且不误伤合法回显；随模型
  升级自然消解。其余 193 条全部写回 ✓
- **F20 修复实证**：Pixabay 音乐作者致谢名单（Tim_Kulig_Free_Music
  等 4 条）由失败转成功——下划线标识符组成部分豁免，译文保留用户名
  为正确行为。对照测试确认不掩盖真半翻译（`Open the file` 仍失败）
- 跳过 587 条：UnityEngine 类型引用/输入轴/按钮枚举/日志——
  **无该翻而跳**
- runtime=verified：静态字体替换命中，中文字体运行时生效验证通过

## 知识库沉淀

- **F20**（本轮新增）：下划线标识符组成部分豁免（batch_translator.py
  三处接入 + 2 个测试）。触发：eyeless-jack 致谢名单误杀。
- 观察项入库：`Look in the mirror` 短句确定性回显（模型边界，模型
  升级后重跑验证）

## 状态

**✅ 已闭环**。193 条写回 PASS；1 条失败为确定性模型能力边界（原文
保真、记录观察项、不特判）；F20 修复经 run2 实证。与前组
driftapocalypse（F18/F19）/eggs-for-bart（零失败）累计三游戏闭环。
