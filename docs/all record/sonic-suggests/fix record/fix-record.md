# sonic-suggests fix record

> 2026-08-12 · 启动目录结构一次性修复（非代码级规则，无 F 编号）。

## 历程

| 阶段 | 结果 | 说明 |
|---|---|---|
| 汉化写回 | 7 文件变更，四态闸门全 PASS | Assembly-CSharp.dll + resources/sharedassets0 + level0-2 + app.info |
| 实测启动 | 报「There should be 'SonicSuggests_Data' folder」 | 游戏数据铺在 exe 旁，无 _Data 目录 |
| 目录修复 | ✅ 完成 | 20 项数据移入 SonicSuggests_Data/，exe 旁结构恢复 Unity 布局 |

## 本场修复

### 目录结构：SonicSuggests_Data（一次性修复，非代码改动）

- **现象**：汉化版启动即报错退出（UnityPlayer 找不到数据目录）。
- **根因**：目录被「铺平」——Managed/Mono/Resources/GI/level0-2/
  globalgamemanagers*/resources*/sharedassets*/boot.config/app.info 全在
  exe 旁；Unity 2017.3 mono 必须 `SonicSuggests_Data/`。
- **修复**：新建目录并整体移入 20 项；exe/UnityPlayer.dll/
  ScreenSelector.bmp 留在根。
- **遗留提示**：原版 `D:/游戏/sonic-suggests/` 同构（原版也报同样错），
  未代改原版，需要时按同一方式处理。

## 关联代码修复（本游戏暴露的通用问题，已在工具层修复）

### `.rgb` 位图排除（`hanhua/core/scanner.py`）

- **现象**：GI/level0/*.rgb 烘焙光照位图被提取成文本条目 → 写回时文件
  被改写/阻断。
- **根因**：位图二进制含可扫描字符串形态，通用文本扫描未排除图形资源。
- **修复**：3 游戏实证（sonic-suggests/thirstiest）统一排除，非本游戏
  特判。
