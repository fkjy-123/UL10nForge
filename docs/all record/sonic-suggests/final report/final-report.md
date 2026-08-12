# sonic-suggests 最终报告

> 2026-08-12 · 汉化写回 PASS（7 文件）+ 启动目录结构修复完成。

## 概览

| 项 | 结果 |
|---|---|
| Unity 版本 | 2017.3.0f3（mono） |
| 识别文件 | 256（文本 1 + v2 资源/场景 6 变更） |
| 写回闸门 | file/container/object/runtime/overall 全 PASS |
| 变更文件 | 7（Assembly-CSharp.dll、resources.assets、sharedassets0.assets、level0-2、app.info） |
| 未变更核对 | 249 文件字节级一致（source==target 哈希） |
| 启动问题 | ✅ 已修（SonicSuggests_Data 目录补齐） |

## 写回说明

四态闸门全部 PASS：1 个文本文件写回并重开核对通过；6 个容器（dll +
2 assets + 3 场景）写回并重开验证通过；全部条目完整写入；
runtime_verified。

## 启动问题处置

汉化版启动报「There should be 'SonicSuggests_Data' folder next to the
executable」——游戏数据被铺在 exe 旁，Unity 2017.3 需要 `SonicSuggests_
Data` 目录。已新建目录并移入 20 项数据（Managed/Mono/Resources/GI/
level0-2/globalgamemanagers*/resources*/sharedassets*/boot.config/
app.info），exe 旁恢复标准 Unity 布局。

**注意**：原版目录 `D:/游戏/sonic-suggests/` 结构相同（同样缺
SonicSuggests_Data），原版启动也会报同样错误——需要时按同一方式修复
（本次未代改原版）。

## 遗留与后续

- [ ] 若原版也需游玩：对原版目录执行同样的 Data 目录修复
- [ ] 闭环后如需重新汉化：先确认扫描器按新目录结构重扫（_Data 内
      rel_path 变化，重扫即重新建档）
