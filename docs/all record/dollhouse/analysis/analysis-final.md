# dollhouse 分析终稿

> 闭环轮次：run1（2026-08-11 20:12）——F14 修复后重跑，无失败
>
> 本轮特殊点：dollhouse 是 **2018.3.8f1 老 Unity 模板项目**，文本极少
> 且以引擎配置为主。真实显示文本仅 app.info 2 条；boot.config 引擎
> 配置暴露 F14 修复（值域是引擎枚举，翻译即破坏引擎解析）。

## 1 识别层

- 文本文件 1（app.info）· 二进制资源 0 · 识别条目 2
- **boot.config 未进条目**：scanner `SKIP_DIRS` 已含 `Boot.config`
  （Unity 引擎运行时目录排除）——扫描阶段即剪掉，这是第一层防护
- **F14 是第二层兜底**：若 boot.config 以任何路径进入 parse_file
  （如被改名、位于其他目录、走内容路由），`_UNITY_ENGINE_CONFIG_FILES`
  文件级整体跳过（保留条目保证写回完整性，不翻译）。测试
  `test_boot_config_engine_file_whole_skipped` 直接调 parse_file 验证：
  5 条（gfx-enable-fixed-retina、wait-for-native-debugger、
  scripting-runtime-version=legacy、vr-enabled=0、hdr-display-enabled=0）
  全跳过、条目保留

## 2 翻译层

- 2 条全部成功（无失败）：
  - `Olivia Haines` → `奥利维亚·海恩斯`（作者名，合理本地化）
  - `Dollhouse` → `玩偶屋`（游戏名）
- **app.info 不跳过**：内容是作者名/游戏名（元数据记录，引擎不解析），
  翻译成中文是合理的标题本地化——与 boot.config 的值域是引擎枚举
  形成对照（F14 注释明确此边界）

## 3 写回层

- 1 文本文件 · 2 条译文 · 写入成功（file=PASS / object=PASS）
- **runtime=WARN**：2018.3 老 Unity 的运行时字体验证为警告级——
  老版本引擎字体回退机制差异，属预期（风险：无，文本为标题级元数据）
- 知识库 5 条规则启用（fit_bytes_nul_padding / placeholder_preserve /
  textasset_encoding_preserve / unityevent_binding_preserve /
  logic_key_compare）

## 4 结论

**✅ 无需修复项（除已完成的 F14）**。无失败、无跳过、无哑信号——
条目本身极少（2 条），引擎配置全部在识别层正确剪掉/跳过。dollhouse
的价值在于**暴露 F14 修复**（boot.config 的 legacy →「遗产」翻译破坏
引擎解析的实证来自此前该游戏的翻译记录）。
