# sonic-suggests 闭环分析（final）

> 2026-08-12 · 汉化写回 7 文件 PASS + 启动目录结构一次性修复。

## 1. 识别

- Unity 2017.3.0f3 / mono 运行时（`.hanhua-manifest.json`）。
- 文件 256 个，写回变更 7 个：
  - `Managed/Assembly-CSharp.dll`（mono 代码文本）
  - `resources.assets` / `sharedassets0.assets`（v2 资源文本）
  - `level0` / `level1` / `level2`（场景文本）
  - `app.info`（文本文件）

## 2. 写回

- 四态闸门全 PASS：file（1 文本文件写回 + 重开核对）、container（6 容器
  写回并重开验证）、object（全部条目完整写入）、runtime（runtime_verified）。
- 256 个文件哈希核对：仅上述 7 个变更，其余 249 个字节级一致
  （source_sha256 == target_sha256）。

## 3. 启动问题（本次修复）

- **现象**：启动报「There should be 'SonicSuggests_Data' folder next to
  the executable」。
- **根因**：游戏数据文件直接铺在 exe 旁（Managed/Mono/Resources/GI/
  globalgamemanagers/level*/sharedassets* 等 20 项），Unity 2017.3
  按 `<exe 名>_Data` 目录加载数据——缺目录必报错。
- **修复**（一次性目录结构修复）：新建 `SonicSuggests_Data/`，将 20 项
  数据全部移入；exe 旁保留 SonicSuggests.exe / UnityPlayer.dll /
  ScreenSelector.bmp。修复后结构：
  ```
  SonicSuggests.exe
  UnityPlayer.dll
  SonicSuggests_Data/{Managed,Mono,Resources,GI,level0-2,
    globalgamemanagers*,resources.*,sharedassets*,boot.config,app.info}
  ```
- **注意**：原版 `D:/游戏/sonic-suggests/` 目录结构相同（同样缺
  SonicSuggests_Data）——原版启动同样会报该错，需要时按同一方式修复
  （未代改原版目录）。

## 4. 相关代码修复（共用，非本游戏特判）

- `.rgb` 烘焙光照位图被提取成条目 → 写回阻断（`hanhua/core/scanner.py`，
  sonic-suggests/thirstiest 3 游戏实证）：位图二进制不在文本提取范围，
  不再产生伪条目。
