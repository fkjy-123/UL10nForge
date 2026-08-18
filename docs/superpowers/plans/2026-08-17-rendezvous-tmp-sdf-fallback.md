# Rendezvous TMP SDF Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Unity 2019 Mono 游戏的运行时字体插件优先加载版本匹配的静态 TMP SDF bundle，解决 Rendezvous 中动态 TMP 字体仅覆盖 1 个字形导致的大量方块。

**Architecture:** 字体 pipeline 根据 `unity_version` 和字重选择现有 TMP bundle，并把路径显式传给安装器；安装器将其原子部署为 `font-tmp.bundle`。C# 插件优先加载 bundle 中的 `TMP_FontAsset`，统一通过一个字体应用函数替换 TMP 文本并保留原字体 fallback；bundle 失败时回退现有动态 OTF 工厂。健康协议报告真实字体来源及完整逐码点覆盖。

**Tech Stack:** Python 3.12、pytest、C# / BepInEx 5、Harmony、Unity 2019.4、TextMeshPro 2.x、PowerShell 构建脚本。

---

### Task 1: 版本匹配 TMP bundle 的部署链路

**Files:**
- Modify: `hanhua/core/font/pipeline.py`
- Modify: `hanhua/core/font_support.py`
- Modify: `tests/test_font_pipeline.py`
- Modify: `tests/test_font_support.py`

- [ ] **Step 1: 写 pipeline 传递 bundle 的失败测试**

在 `tests/test_font_pipeline.py` 的 fake `install_font_override` 中捕获 `tmp_bundle`，断言 Unity 2019 + medium 选择 `sourcehan_sdf_medium_u2019`；无兼容版本时断言为 `None`。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_font_pipeline.py -q`
Expected: FAIL，`install_font_override` 尚不接受 `tmp_bundle`。

- [ ] **Step 3: 实现 pipeline 选择与显式传参**

在 `deploy_runtime` 中使用 `select_tmp_bundle(inputs.unity_version, weight=inputs.font_config.weight)`，两处 `install_font_override(...)` 均传入 `tmp_bundle=selected_bundle`。选择失败时传 `None`，保持旧游戏行为。

- [ ] **Step 4: 运行 pipeline 测试确认 GREEN**

Run: `python -m pytest tests/test_font_pipeline.py -q`
Expected: PASS。

- [ ] **Step 5: 写安装器原子部署失败测试**

扩展 `_make_assets` 创建测试 bundle，并调用 `install_font_override(..., tmp_bundle=bundle)`；断言插件目录存在内容完全相同的 `font-tmp.bundle`，升级 owned-tree 的精确文件集合也包含它。另测 `tmp_bundle=None` 时不生成文件。

- [ ] **Step 6: 运行安装测试确认 RED**

Run: `python -m pytest tests/test_font_support.py -q -k "tmp_bundle or installs_font_runtime or upgrade_replaces"`
Expected: FAIL，安装器尚未部署 `font-tmp.bundle`。

- [ ] **Step 7: 实现安全读取和原子 staging**

给 `install_font_override` 增加仅关键字参数 `tmp_bundle: Path | None = None`。非空时要求是普通文件、读取 payload，并在现有临时安装树 `plugin_dir` 写入固定名称 `font-tmp.bundle`；读取/校验失败抛 `FontInstallError`，不能留下半部署目录。

- [ ] **Step 8: 运行安装测试确认 GREEN**

Run: `python -m pytest tests/test_font_support.py -q -k "tmp_bundle or installs_font_runtime or upgrade_replaces"`
Expected: PASS。

- [ ] **Step 9: 提交部署链路**

Run: `git commit --only -m "feat: 部署版本匹配的 TMP SDF bundle" -- hanhua/core/font/pipeline.py hanhua/core/font_support.py tests/test_font_pipeline.py tests/test_font_support.py`

### Task 2: 插件优先加载静态 TMP SDF

**Files:**
- Modify: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`
- Modify: `font_plugin/build.ps1`
- Modify: `tests/test_font_plugin_source.py`
- Modify: `tests/test_font_support.py`

- [ ] **Step 1: 写 bundle 优先加载的源契约测试**

测试要求源码包含固定文件名 `font-tmp.bundle`、`AssetBundle.LoadFromFile`、`LoadAllAssets(tmpFontAssetType)`、成功日志 `TMP_BUNDLE_READY`、失败日志 `TMP_BUNDLE_FALLBACK`，且 `InitializeTmpFont` 先尝试 bundle、失败才进入 `CreateFontAsset` 工厂。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_font_plugin_source.py tests/test_font_support.py -q -k "bundle or plugin"`
Expected: FAIL，源码尚无 AssetBundle 加载链路。

- [ ] **Step 3: 实现最小 bundle 生命周期**

在插件中增加 `AssetBundle tmpFontBundle`、`string tmpFontSource`。新增 `TryLoadBundledTmpFont()`：从插件目录读取固定文件，加载全部 TMP_FontAsset，要求恰好选择一个非空字体，设置 `dynamicTmpFont` 和来源 `bundle`，保持 bundle 存活。`InitializeTmpFont` 成功时直接返回；异常卸载容器并记录 fallback 日志。`OnDestroy` 在销毁动态对象前区分 bundle 资产，并调用 `tmpFontBundle.Unload(false)`。

- [ ] **Step 4: 为构建加入 AssetBundle 引用**

在 `font_plugin/build.ps1` 的 Unity 引用列表加入 `UnityEngine.AssetBundleModule.dll`，继续使用游戏 Managed 程序集编译，保持 mscorlib 2.0 兼容检查。

- [ ] **Step 5: 运行源契约测试确认 GREEN**

Run: `python -m pytest tests/test_font_plugin_source.py tests/test_font_support.py -q -k "bundle or plugin"`
Expected: PASS。

- [ ] **Step 6: 编译真实插件**

Run: `powershell -ExecutionPolicy Bypass -File font_plugin/build.ps1 -GameDir "C:\Users\mingming\Downloads\Rendezvous.rar_汉化" -BepInExZip "C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具\resources\font_override\BepInEx_win_x64_5.4.23.5.zip"`
Expected: exit 0，输出新的 DLL size 和 SHA-256。

- [ ] **Step 7: 提交插件加载链路**

Run: `git commit --only -m "feat: 运行时优先加载 TMP SDF bundle" -- font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs font_plugin/build.ps1 tests/test_font_plugin_source.py tests/test_font_support.py resources/font_override/Hanhua.FontFallback.dll`

### Task 3: 统一 TMP 字体应用并保留原字体 fallback

**Files:**
- Modify: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`
- Modify: `tests/test_font_plugin_source.py`

- [ ] **Step 1: 写幂等 fallback 契约测试**

测试要求 `TmpSetTextPostfix`、`ChangeLanguagePostfix`、`PatchTmpTexts` 共用 `ApplyTmpFontToText`；该函数先读取原字体，在非空且不同于工具字体时调用 `AttachOriginalTmpFallback`，fallback 表包含检查后才追加。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest tests/test_font_plugin_source.py -q -k "fallback or apply_tmp"`
Expected: FAIL，三条链路仍各自直接写 `font` 属性。

- [ ] **Step 3: 实现共用字体应用边界**

新增静态 `ApplyTmpFontToText(object target)` 返回是否发生替换；它读取 `font`，调用实例方法 `AttachOriginalTmpFallback(original)`，再设置主字体。fallback 方法反射获取 `dynamicTmpFont.fallbackFontAssetTable`，仅在原字体非空、类型兼容且列表中不存在时追加。三条链路改为调用此函数。

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `python -m pytest tests/test_font_plugin_source.py -q -k "fallback or apply_tmp"`
Expected: PASS。

- [ ] **Step 5: 编译并运行插件测试**

Run: `python -m pytest tests/test_font_plugin_source.py tests/test_font_support.py -q`
Expected: PASS。

Run: `powershell -ExecutionPolicy Bypass -File font_plugin/build.ps1 -GameDir "C:\Users\mingming\Downloads\Rendezvous.rar_汉化" -BepInExZip "C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具\resources\font_override\BepInEx_win_x64_5.4.23.5.zip"`
Expected: exit 0。

- [ ] **Step 6: 提交字体应用链路**

Run: `git commit --only -m "fix: 保留 TMP 原字体 fallback" -- font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs tests/test_font_plugin_source.py resources/font_override/Hanhua.FontFallback.dll`

### Task 4: 健康协议报告真实 TMP 来源与覆盖

**Files:**
- Modify: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`
- Modify: `hanhua/core/font_support.py`
- Modify: `tests/test_font_support.py`

- [ ] **Step 1: 写协议失败测试**

把有效 fixture 升级为协议 v6，增加 `tmp_font_source`（`bundle|dynamic|failed`）和 `tmp_bundle_loaded`。测试拒绝未知来源、类型错误，以及 `tmp_font_source=bundle` 但 bundle 未加载；同时接受 bundle 覆盖未达到需求全集但 `tmp_missing` 被如实报告的 pending 状态。

- [ ] **Step 2: 运行协议测试确认 RED**

Run: `python -m pytest tests/test_font_support.py -q -k "font_health"`
Expected: FAIL，Python 与插件仍为 v5。

- [ ] **Step 3: 实现协议 v6**

插件版本升为 1.5.0、health protocol 升为 6，在 JSON 顶层写入来源与 bundle 状态。只有完整逐码点计数完成后才将 TMP adapter 标为 ready；存在缺字时保持可用但健康验证不声称全覆盖。Python 校验器同步字段白名单、版本和一致性规则。

- [ ] **Step 4: 运行协议测试确认 GREEN**

Run: `python -m pytest tests/test_font_support.py -q -k "font_health"`
Expected: PASS。

- [ ] **Step 5: 编译并提交协议**

Run: `powershell -ExecutionPolicy Bypass -File font_plugin/build.ps1 -GameDir "C:\Users\mingming\Downloads\Rendezvous.rar_汉化" -BepInExZip "C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具\resources\font_override\BepInEx_win_x64_5.4.23.5.zip"`
Expected: exit 0。

Run: `git commit --only -m "fix: 如实报告 TMP bundle 字形覆盖" -- font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs hanhua/core/font_support.py tests/test_font_support.py resources/font_override/Hanhua.FontFallback.dll`

### Task 5: 自审、部署与 Rendezvous 冷启动回归

**Files:**
- Modify: `.scratch/running-issues/ISSUES.md`
- Modify: `.scratch/running-issues/SOLUTIONS.md`
- Deploy: `C:/Users/mingming/Downloads/Rendezvous.rar_汉化/BepInEx/plugins/HanhuaFont/`

- [ ] **Step 1: 按 dev-issue-tracker 逐文件自审**

逐个完整读取本次修改文件；确认 C# 无调试残留、签名一致、命名空间一致。运行 `Get-Content font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs -First 3`，确认 UTF-8 无 BOM 且首行正常。核对 #001 未被其他改动重新引入。

- [ ] **Step 2: 运行聚焦和全量自动验证**

Run: `python -m pytest tests/test_font_plugin_source.py tests/test_font_support.py tests/test_font_pipeline.py -q`
Expected: 0 failed。

Run: `python -m pytest tests/ -q`
Expected: 仅允许交接报告已确认的既有 Crypto 2 项与 GUI workbench 9 项失败；任何新增失败都必须修复并记录。

- [ ] **Step 3: 原子部署新插件载荷**

确认 Rendezvous 进程不存在。备份当前插件目录到带时间戳的同级目录，然后部署新 DLL 与 `sourcehan_sdf_medium_u2019` 为 `font-tmp.bundle`；保留 `font.ttf`、翻译和 required glyph 文件。

- [ ] **Step 4: 冷启动反馈循环**

完全冷启动游戏，等待启动提示和主菜单。读取新 nonce 的日志与 health，要求日志出现 `TMP_BUNDLE_READY`，`tmp_font_source=bundle`，TMP 覆盖至少 1727/1769，且不再是 1/1769。

- [ ] **Step 5: 视觉验收**

截图检查启动自动保存提示、主菜单“音量/键盘”等已知位置；大量方块必须消失。剩余单字符缺失需对应 health 的 42 个已知 bundle 外字符，不得出现需求集内大面积缺失。

- [ ] **Step 6: 清理与问题台账**

移除所有 `[DEBUG-...]` 探针；#001 验收通过后标记 resolved，填写时间和新方案编号。每次测试/构建的新问题按规则写入台账并更新统计。

- [ ] **Step 7: 代码审查与分支收尾**

使用 `requesting-code-review` 对本次提交范围审查；修复 Critical/Important 后重新验证。随后使用 `finishing-a-development-branch`，保留分支供用户决定合并方式。
