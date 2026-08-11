# dollhouse 修复记录

> 闭环轮次：run1（2026-08-11 20:12）· 2 条翻译全成功 · 0 失败
>
> dollhouse 本体无修复需求（文本极少），本轮价值是**验证 F14**：
> boot.config 引擎配置文件整体跳过——该修复由 dollhouse 的
> scripting-runtime-version=legacy 被翻译成「遗产」实证触发。

## F14 Unity 引擎配置文件整体跳过

**现象**：`boot.config` 的 `scripting-runtime-version=legacy` 中 legacy
是合法英文单词，通过 should_skip 判定被当显示文本翻译成「遗产」写回
——Unity 引擎配置值域（gfx-enable-*/wait-for-*/scripting-runtime-version/
vr-enabled/hdr-display-enabled）是引擎枚举，翻译即破坏引擎解析。

**根因**：识别层对 boot.config 的防护只存在于 scanner `SKIP_DIRS`
（目录级排除 `Boot.config`）；一旦该文件以任何路径进入
`extractor.parse_file`（文本扫描唯一入口，project.py:773），kv 值
没有「引擎配置值域」概念，legacy（合法英文词）当普通显示文本放行。

**修复**（`extractor.py`）：
- `_UNITY_ENGINE_CONFIG_FILES = {"boot.config"}`：文件级整体跳过——
  保留条目保证写回完整性但不翻译（值域是引擎枚举，翻译即破坏解析）
- 位置：parse_file 中 `_is_non_target_language_pack` 之后、智能过滤
  之前——覆盖所有进入解析的路径
- **app.info 不在此列**：内容是作者名/游戏名（元数据记录，引擎不
  解析），翻译成中文是合理的标题本地化——F14 注释明确此边界

**为什么不是单游戏特判**：boot.config 是所有 Unity 游戏打包必带的
引擎配置文件，文件名全引擎通用；任何 Unity 游戏都不得翻译其值。

**验证**：
- `test_boot_config_engine_file_whole_skipped`：boot.config 5 条全
  跳过 + 条目保留（写回完整性）
- `test_boot_config_named_other_ext_not_skipped`：boot.txt 同名逻辑
  不误伤（2 条 pending）
- dollhouse 重跑：app.info 2 条正常翻译写回（对照验证——boot.config
  跳过不影响正常文本路径）

## 观察项（不修复，记录判断依据）

无。dollhouse 无失败、无跳过、无哑信号。
