# fix-14 captive 一次通过（无新增修复）

游戏：captive（闭环于 2026-08-11，94/0 干净闭环）

## 背景

captive 首轮 94 条翻译 **0 失败**，一次通过。此前 13 轮修复（baldis 12 项
+ butterflies 9 项）的通用机制在本游戏全部覆盖——纯文本配置文件（app.info）
+ 主菜单 UI 短词条，无新失败模式。

## 失败与修复

无。译文抽查：PLAY GAME→玩游戏吧 / SETTINGS→设置 / QUIT→退出 /
Option A→选项 A / CAPTIVE v0.20→保留原文（版本横幅行业惯例）。

## 验证

- captive 最终跑：**94 条翻译 0 失败**，写回 89 条 PASS
- 术语库学习 1 条专名
- D:/游戏/captive `_汉化` 目录已删（做完一个删一个）
