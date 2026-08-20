# Running Issues

| Status | Count |
|---|---:|
| open | 2 |
| resolved | 17 |
| wontfix | 0 |

## #018 — level 哈希只读诊断的 PowerShell 管道语法错误

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `.scratch` 临时只读诊断命令
- Symptom: 构造逐文件哈希 JSON 时，在 `foreach` 语句后直接接管道，PowerShell 报 `An empty pipe element is not allowed`。
- Repro steps: 在表达式块中以 `}; [pscustomobject]$row } | ConvertTo-Json` 形式直接串接管道。
- Root cause: 管道左侧缺少明确的可管道化集合；诊断命令将循环块与管道混写。
- Resolved date: 2026-08-18
- Solution: 将结果先累积至 `$rows`，循环结束后再执行 `$rows | ConvertTo-Json`；仅重跑只读哈希诊断。

## #019 — 只读 SQLite 诊断缺少 sqlite3 命令行程序

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `.scratch` 临时只读诊断命令
- Symptom: PowerShell 调用 `sqlite3 project.db` 报 `The term 'sqlite3' is not recognized`。
- Root cause: 当前 Windows 环境仅提供 Python 标准库 sqlite3，没有 sqlite3 CLI。
- Resolved date: 2026-08-18
- Solution: 使用 Python `sqlite3.connect(...).execute(...)` 只读查询；不修改数据库。

## #020 — 全量 level 审计的统计键不能直接 JSON 序列化

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `.scratch` 临时只读审计命令
- Symptom: 输出 `(script_file, script_pathID, display)` 元组键的 Counter 时触发 `TypeError: keys must be str...`。
- Root cause: JSON 对象键仅允许标量，Python Counter 使用了元组键。
- Resolved date: 2026-08-18
- Solution: 输出前将统计键格式化成字符串或记录数组；重跑只读审计，不写入游戏文件。

## #021 — 正式写回流程未调用非显示 level 对象保护

- Status: open
- Found: 2026-08-18
- Source: manual/runtime report + static object audit
- Files: `hanhua/core/project.py`, `hanhua/core/unity/protect.py`
- Symptom: 故障候选相对写回输入多改 664 个 level 对象，其中 653 个不是显示组件；包含 `@CSVParser` 的 `setyo` 键、EventSystem 的输入轴名、关卡/交互脚本和按钮逻辑字段。用户报告过场后黑屏。
- Repro steps: 对 staging 与写回候选逐 level/pathID 比较 raw data；按 `DEFAULT_DISPLAY_SCRIPT_PIDS` 分类。
- Root cause: `restore_non_display_objects` 已存在但未被 `Project.write_all` 调用，rawstr 写回仍可进入非显示脚本对象。
- Mitigation: 已生成独立 `Rendezvous.rar_汉化_汉化.runtime-staging_汉化.level-guarded`，从 staging 恢复 653 个非显示对象，仅保留 11 个 TMP 文本对象；静态验证通过，未启动游戏。
- Required fix: 将保护步骤接入正式写回，在重开校验及 manifest 前执行，并添加回归测试；实机过场验证后方可标记 resolved。
- Solution ref: S014

## #012 — NotoSerif bundle 已加载但未参与 TMP 渲染

- Status: resolved
- Found: 2026-08-17
- Source: runtime
- Files: `Rendezvous_Data/sharedassets0.assets`, `BepInEx/LogOutput.log`
- Symptom: 更换运行时 NotoSerif bundle 后条纹完全不变。
- Repro steps: 启动游戏并检查日志；`TMP_BUNDLE_READY` 成功，但 `applications.tmp=0`。
- Root cause: 画面继续使用手工组装进 `sharedassets0.assets` 的静态 TMP 字体；运行时 bundle 没有进入实际文本组件。
- Resolved date: 2026-08-17
- Solution: 将条纹版保存为 `sharedassets0.assets.stripe-broken.bak`，恢复 `sharedassets0.assets.pre-sdf.bak`，保留运行时全局 fallback。

## #011 — TMP bundle 构建脚本源字体路径错误

- Status: resolved
- Found: 2026-08-17
- Source: tooling
- Files: `scripts/build_tmp_font_bundles.py`
- Symptom: 构建时从 `fonts/SourceHanSansSC-*.asset` 读取，文件实际位于 `fonts/SDF_Font_Asset/`。
- Resolved date: 2026-08-17
- Solution: WEIGHTS 使用 `SDF_Font_Asset/` 相对路径。

## #001 — Rendezvous 汉化文本大量显示方块

- Status: open
- Found: 2026-08-17
- Source: runtime
- Files: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`, `Rendezvous.rar_汉化/BepInEx/plugins/HanhuaFont/`
- Symptom: 冷启动后保存提示与菜单中文大量显示方块；新会话 `font-health.json` 报告 legacy 1769/1769、TMP 1/1769。
- Repro steps: 完全退出游戏，启动 `Rendezvous.rar_汉化/Rendezvous.exe`，观察启动保存提示并读取新的 `font-health.json`。
- Notes: 本次修改目标；设计与计划必须引用 #001。

## #013 — all_record_runner 帮助注释声明了不存在的 --app-dir 参数

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `scripts/all_record_runner.py`
- Symptom: 按脚本顶部用法传入 `--app-dir` 时，argparse 在解析阶段报 `unrecognized arguments`。
- Repro steps: `python scripts/all_record_runner.py <game_dir> --no-translate --no-writeback --app-dir <dir>`。
- Root cause: 顶部文档遗留了已移除的 CLI 参数，实际运行目录固定为 `~/.hanhua`。
- Resolved date: 2026-08-18
- Solution ref: S009

## #014 — 深度审计诊断错误假定 ProjectStore 暴露 path 属性

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `hanhua/core/storage.py`（API 使用处）
- Symptom: 只读审计脚本读取 `project.store.path` 时触发 `AttributeError`，导致诊断在输出统计前中止。
- Repro steps: `Project.open_game_dir(...).store.path`。
- Root cause: `ProjectStore` 的公开接口未定义 `path`；该值并非审计统计所必需。
- Resolved date: 2026-08-18
- Solution ref: S010

## #015 — PowerShell GBK 输出审计样本文本触发 UnicodeEncodeError

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `.scratch/rendezvous-deep-audit-20260818`（临时诊断命令）
- Symptom: 只读审计在打印包含扩展字符的原文时触发 `UnicodeEncodeError: gbk`。
- Repro steps: 直接 `print(repr(original))` 输出 `Assets/all symbols.txt` 条目。
- Root cause: 临时 Python 标准输出未显式设为 UTF-8。
- Resolved date: 2026-08-18
- Solution ref: S011

## #016 — 中断中的 runner 尚未生成 summary.md

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `docs/all record/Rendezvous.rar_汉化_汉化.runtime-staging/summary.md`
- Symptom: 翻译进程被中断后读取尚未收尾写入的 `summary.md` 会报文件不存在。
- Repro steps: 在 runner 仍处于翻译阶段时读取该汇总文件。
- Root cause: 汇总仅在流水线收尾阶段生成；中间库数据库才是可恢复进度的权威来源。
- Resolved date: 2026-08-18
- Solution ref: S012

## #017 — 审计查询遗漏 status 列导致 Row 访问错误

- Status: resolved
- Found: 2026-08-18
- Source: tooling
- Files: `.scratch/rendezvous-runtime-translate-20260818/project.db`（只读审计命令）
- Symptom: 审计 SQL 未选择 `status`，随后访问 `row['status']` 触发 `IndexError: No item with that key`。
- Repro steps: `select file_id,key_path,original,translation,meta from entries` 后读取 `row['status']`。
- Root cause: 查询列集与输出字段不一致；不影响项目库或发布物。
- Resolved date: 2026-08-18
- Solution ref: S013

## #002 — TMP bundle 检查脚本引用不存在字段

- Status: resolved
- Found: 2026-08-17
- Source: manual
- Files: `hanhua/core/unity/font_replace.py`
- Symptom: 只读检查命令访问 `TmpBundlePayload.character_unicodes`，触发 `AttributeError`。
- Repro steps: 对 `load_tmp_bundle(...)` 返回值访问 `character_unicodes`。
- Resolved date: 2026-08-17
- Solution ref: S001

## #003 — PowerShell GBK 控制台无法打印部分 Unicode 诊断字符

- Status: resolved
- Found: 2026-08-17
- Source: manual
- Files: `.scratch/running-issues/ISSUES.md`
- Symptom: Python 诊断输出包含 `©` 等字符时触发 `UnicodeEncodeError: 'gbk' codec can't encode character`。
- Repro steps: 在当前 PowerShell 控制台直接打印缺失码点对应字符。
- Resolved date: 2026-08-17
- Solution ref: S002

## #004 — 设计提交夹带既有暂存删除

- Status: resolved
- Found: 2026-08-17
- Source: review
- Files: `docs/superpowers/specs/2026-08-17-rendezvous-tmp-sdf-fallback-design.md`, `fonts/SimplifiedChinese/SourceHanSansSC-Regular.otf`
- Symptom: 普通 `git commit` 同时提交了此前已经 staged 的旧字体删除。
- Repro steps: 工作区已有 staged 改动时，对新文件执行 `git add` 后直接 `git commit`。
- Resolved date: 2026-08-17
- Solution ref: S003

## #005 — 未跟踪计划文件不能直接 pathspec-only 提交

- Status: resolved
- Found: 2026-08-17
- Source: manual
- Files: `docs/superpowers/plans/2026-08-17-rendezvous-tmp-sdf-fallback.md`
- Symptom: `git commit --only -- <untracked>` 报 pathspec 未匹配已知文件。
- Repro steps: 对尚未 `git add` 的新文件直接执行 pathspec-only commit。
- Resolved date: 2026-08-17
- Solution ref: S004

## #006 — 已部署插件 DLL 与测试哈希锁不一致

- Status: resolved
- Found: 2026-08-17
- Source: test
- Files: `resources/font_override/Hanhua.FontFallback.dll`, `tests/test_font_support.py`
- Symptom: 聚焦基线 118 passed / 1 skipped / 1 failed；测试期望 SHA-256 `506007...`，实际为 `2c60e9...`。
- Repro steps: `python -m pytest tests/test_font_pipeline.py tests/test_font_support.py tests/test_font_plugin_source.py -q`
- Notes: 与 #001 同阶段处理；重新构建最终 DLL 后更新哈希锁，并用真实构建输出校验。
- 2026-08-17 Task 1 复核：`python -m pytest tests/test_font_pipeline.py tests/test_font_support.py -q` 仍仅此失败（实际 `2c60e9...`）；其余 `120 passed, 1 skipped`。
- Resolved date: 2026-08-17
- Solution: 用指定 Rendezvous 游戏真实构建最终 DLL；代码审查补齐 bundle 验证失败的延迟动态回退后，最终锁定 SHA-256 `89ea17ce44eed42189adcbf9162dc6bd3ed38ee22989b3a21f33086efb9a23e8`。

## #007 — 静态 Harmony postfix 直接访问实例 Logger 导致编译失败

- Status: resolved
- Found: 2026-08-17
- Source: compile
- Files: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`
- Symptom: 真实游戏构建报两处 `CS0120`，静态 postfix 直接调用 `BaseUnityPlugin.Logger`。
- Repro steps: 按 Task 2 指定参数运行 `font_plugin/build.ps1`。
- Solution ref: S005
- Resolved date: 2026-08-17

## #008 — CLR 验证锁住临时 DLL 且拒绝 Unity 2019 mscorlib 4

- Status: resolved
- Found: 2026-08-17
- Source: compile
- Files: `font_plugin/build.ps1`
- Symptom: Roslyn 编译成功后，路径式 ReflectionOnlyLoad 锁住临时 DLL，finally 清理报 Access denied 并掩盖原始验证结果；同时验证仅接受 major ≤2，无法用指定 Unity 2019 游戏构建。
- Repro steps: 按 Task 2 指定参数运行 `font_plugin/build.ps1`，观察临时目录清理失败；Rendezvous 的 `mscorlib.dll` 为 CLR 4 家族。
- Solution ref: S006
- Resolved date: 2026-08-17

## #009 — TMP 原字体 fallback 与全局扫描形成直接环

- Status: resolved
- Found: 2026-08-17
- Source: review
- Files: `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs`, `tests/test_font_plugin_source.py`
- Symptom: `PatchLoadedTmpAssets` 先把工具字体追加到原字体 fallback，导致 `AttachOriginalTmpFallback` 拒绝保留原字体；Harmony 先保留时，后续扫描又会形成直接环。
- Repro steps: 检查 `ApplyFonts` 中 `PatchLoadedTmpAssets` / `PatchTmpTexts` 顺序，以及前者追加 fallback 前是否读取工具字体的 fallback 表。
- Solution ref: S007
- Resolved date: 2026-08-17

## #010 — 交互式隔离索引脚本被执行策略拒绝

- Status: resolved
- Found: 2026-08-17
- Source: tooling
- Files: `.scratch/task3-hash.patch`, `.scratch/task3-commit.index`
- Symptom: 包含 `git add -p` 管道或脚本内子进程的 PowerShell 命令在进程创建前被策略拒绝。
- Repro steps: 在单一 `exec_command` 中通过管道驱动 `git add -p`，或通过 `ProcessStartInfo` 调用 `git hash-object`。
- Solution ref: S008
- Resolved date: 2026-08-17
