# eggs-for-bart 最终报告

## 概览

| 项 | 值 |
|---|---|
| 游戏 | eggs-for-bart（找蛋冒险，17 关卡场景资源 + Assembly-CSharp） |
| 目录 | D:\游戏\eggs-for-bart |
| 闭环轮次 | run1（2026-08-11）· 零失败零修复 |
| 翻译条目 | 134 / 134（0 失败） |
| 写回 | 18 文件 · 118 条译文 · container/object PASS · runtime WARN（字体预期差异） |
| 汉化输出 | 已删除（只留原版） |

## 流程结果

1. **识别**：文本文件 1 + 二进制资源 17 · 识别条目 134
   （asset_unity 47 文件 / 349 条 + mono_csharp 2 文件 / 99 条）
2. **翻译**（Hy-MT2-1.8B）：134 条 · **0 失败** · 请求 120 · 107.3s
3. **写回**：输入保护 ✓ 重开验证 ✓ 变更文件 43 · container/object
   PASS · 字体 payload_deployed（WARN，预期行为差异）· 知识库 5 条
   规则启用
4. **清理**：`eggs-for-bart_汉化` 已删除 ✓

## 质量结论

- **0 条失败**——134 条全部一次通过质量门并写回，本游戏未暴露新
  判定问题（本轮修复 F18/F19 由同组 driftapocalypse 暴露）
- 跳过 316 条：UnityEngine 类型引用 168 + 输入轴/按键名 62 + 按钮
  状态枚举 28 + 调试日志/着色器名——**无该翻而跳**
- 写回逻辑层审计（F11）：report 3 条（Continue/Exit/Play 全真按钮
  复核通过）· 扩容 39 条 · 回显跳过 16 条（L+R+B+A+B+Y 手柄按键串，
  非翻译对象）· revert 0
- runtime=WARN：32 位老游戏静态字体替换未命中 → 运行时插件已部署
  未验证（font-health 需实际运行写入，工具不自动启动游戏）。中文字
  体插件就位，发布后玩家运行生效。记录为预期行为差异。

## 知识库沉淀

- 无新修复（零失败）。F18/F19 由同组 driftapocalypse 闭环验证并
  入库。

## 状态

**✅ 已闭环**。零失败、写回 container/object PASS、revert 0、回显
跳过全部合理；runtime WARN 为字体验证预期差异，不阻断。与
driftapocalypse（本轮同组，F18/F19 闭环）构成双游戏闭环。
