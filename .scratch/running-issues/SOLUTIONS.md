# Running Issue Solutions

## S014 — 写回后按显示脚本白名单恢复非显示关卡对象

- Keywords: `Rendezvous`, `level`, `rawstr`, `CSVParser`, `EventSystem`, `Cutscene`, `black screen`, `restore_non_display_objects`
- Applicable scenarios: Unity 场景 level 文件中 rawstr 写回后，字符串字段归属不明，且存在过场、输入、交互或状态机脚本。
- Linked issues: #021
- Root cause: rawstr 扫描只能发现可解码字符串，无法判断字段是否是运行时键。写入非显示 MonoBehaviour 后，CSVParser、EventSystem、关卡/交互脚本会把被翻译的键用于查找或分发，导致流程断链。
- Fix:
  1. 以写回输入副本作为同 pathID 基线，逐对象比较写回结果。
  2. 仅保留 `DEFAULT_DISPLAY_SCRIPT_PIDS`（Rendezvous: 2000/795/1267/1195/391）的 MonoBehaviour/ScriptableObject 变化；所有其他类型或脚本对象恢复基线 raw data。
  3. 对全部 level 编号（含高于 49 的文件）执行保护，再重开解析所有容器并验证不存在非显示差异。
  4. 最终 manifest 需在保护后重建；实机过场验证前保持 runtime=WARN。
- Applied cases: 1（2026-08-18：恢复 653 个对象，保留 11 个 TMP 显示对象）

## S009 — 以 argparse 当前声明为准，隔离全局目录改用临时 HOME

- Keywords: `all_record_runner`, `--app-dir`, `unrecognized arguments`, `HOME`
- Applicable scenarios: 需要运行不提供用户目录参数的既有 CLI，且必须隔离项目库、词库和记录状态。
- Linked issues: #013
- Root cause: 使用说明可能滞后于 argparse 的实际选项定义。
- Fix:
  1. 先执行 `python scripts/all_record_runner.py -h` 或读取 `main()` 的 `add_argument`，只使用实际声明的参数。
  2. 在子进程内设置专用 `HOME` 与 `USERPROFILE` 到显式、可删除的工作目录，使 `Path.home()` 指向隔离目录。
  3. 保留游戏目录为只读扫描输入；未通过扫描与验证前不得调用写回。
- Applied cases: 1

## S010 — 审计 ProjectStore 时只使用已定义的查询接口

- Keywords: `ProjectStore`, `AttributeError`, `path`, `diagnostic`
- Applicable scenarios: 临时审计脚本需要列出项目库统计或条目状态。
- Linked issues: #014
- Root cause: 将内部实现细节误认为公开字段。
- Fix:
  1. 先用 `get_entries()`、`get_profile()` 等已定义查询接口取得审计数据。
  2. 若需数据库路径，从调用方构造的项目目录推导，不访问 `ProjectStore` 未声明的属性。
- Applied cases: 1

## S011 — 审计输出统一使用 UTF-8 与 ASCII 转义

- Keywords: `UnicodeEncodeError`, `gbk`, `audit`, `PowerShell`
- Applicable scenarios: Windows 只读诊断需要打印任意游戏原文。
- Linked issues: #015
- Root cause: 控制台代码页不能编码扩展字符。
- Fix: Python 诊断开始时执行 `sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')`，或只输出 `json.dumps(value, ensure_ascii=True)`。
- Applied cases: 2

## S012 — runner 中断时从项目库读取进度，不假定汇总已生成

- Keywords: `all_record_runner`, `summary.md`, `interrupted`, `resume`
- Applicable scenarios: 全流程在翻译、审核或写回前被外部中断。
- Linked issues: #016
- Root cause: 汇总报告是收尾产物，不能作为实时状态源。
- Fix: 读取 `~/.hanhua_sweep/projects/<slug>/project.db` 的 `entries` 状态；待翻译、审核、写回均完成后再读取 summary。
- Applied cases: 1

## S013 — 审计 SQL 明确选择并使用同一列集

- Keywords: `IndexError`, `No item with that key`, `sqlite`, `audit`
- Applicable scenarios: 只读审计脚本从 SQLite 行对象输出字段。
- Linked issues: #017
- Root cause: 读取字段未在 SELECT 中声明。
- Fix: 让 SELECT 列表覆盖所有访问字段，或只读取已选择字段；审计前先运行一条小查询自检列名。
- Applied cases: 1

## S001 — 先检查 dataclass 字段再读取 TMP bundle 字符集

- Keywords: `TmpBundlePayload`, `AttributeError`, `charset`
- Applicable scenarios: 使用 `load_tmp_bundle` 的返回值做诊断时。
- Linked issues: #002
- Root cause: 诊断脚本猜测了不存在的字段名，实际字符集合字段为 `charset`。
- Fix:
  1. 使用 `dataclasses.fields(payload)` 核对字段。
  2. 从 `payload.charset` 读取字符集合。
- Applied cases: 1

## S002 — Windows 控制台诊断输出使用 ASCII 转义

- Keywords: `UnicodeEncodeError`, `gbk`, PowerShell, Unicode
- Applicable scenarios: Python 只读诊断需要输出当前代码页不支持的字符。
- Linked issues: #003
- Root cause: 当前 PowerShell 标准输出编码为 GBK，部分 Unicode 字符不可编码。
- Fix: 用 `json.dumps(..., ensure_ascii=True)` 输出，保留码点信息并避免控制台编码失败。
- Applied cases: 1

## S003 — 脏暂存区中使用 pathspec-only 提交

- Keywords: Git, staged, commit, unrelated changes
- Applicable scenarios: 工作区已有用户暂存改动，只需提交本次明确文件。
- Linked issues: #004
- Root cause: `git commit` 默认提交索引中的全部 staged 变更。
- Fix: 在提交前检查 `git diff --cached --name-status`；使用 `git commit --only -- <本次路径>`。若刚生成的本地提交夹带改动，使用 soft 回退后以 `--only` 重建，保留原索引和工作树状态。
- Applied cases: 1

## S004 — 新文件先精确 add 再 pathspec-only 提交

- Keywords: Git, untracked, pathspec, commit only
- Applicable scenarios: 脏暂存区中只提交一个新建文件。
- Linked issues: #005
- Root cause: `git commit --only` 只能提交 Git 已知路径，未跟踪文件尚不在索引中。
- Fix: 先执行 `git add -- <新文件>`，检查 cached diff，再执行 `git commit --only -- <新文件>`。
- Applied cases: 1

## S005 — 静态 Harmony postfix 通过插件实例访问 Logger

- Keywords: `CS0120`, `Harmony`, postfix, `BaseUnityPlugin.Logger`, static
- Applicable scenarios: 静态 Harmony 回调需要写 BepInEx 插件日志。
- Linked issues: #007
- Root cause: `Logger` 是 `BaseUnityPlugin` 实例属性，静态方法没有隐式 `this`。
- Fix: 在已完成空值检查的插件单例上调用 `plugin.Logger.LogInfo(...)`。
- Applied cases: 1

## S006 — 用字节反射验证 DLL 并显式允许 Unity CLR 2/4 家族

- Keywords: `ReflectionOnlyLoadFrom`, file lock, temp cleanup, mscorlib 4, Unity 2019
- Applicable scenarios: PowerShell 构建后需读取程序集引用，同时立即删除临时 DLL。
- Linked issues: #008
- Root cause: 路径式反射加载在 Windows 进程内保持文件锁；旧验证还把 CLR 2 当作唯一合法家族，与现代 Unity 2019 的 CLR 4 冲突。
- Fix:
  1. 用 `ReadAllBytes` + `ReflectionOnlyLoad(byte[])` 检查元数据，避免路径锁。
  2. 仍要求唯一 `mscorlib` 引用，只接受 major 2 或 4，其他 major 一律拒绝。
- Applied cases: 1

## S007 — TMP 双向 fallback 扫描前检查工具字体表

- Keywords: TMP, fallback, cycle, `PatchLoadedTmpAssets`, `AttachOriginalTmpFallback`
- Applicable scenarios: 主字体保留原字体 fallback，同时全局扫描会给其他 TMP 字体追加工具字体。
- Linked issues: #009
- Root cause: 全局扫描不知道某字体已是工具字体的 fallback，仍追加反向边。
- Fix:
  1. 先让 TMP 文本应用边界把原字体保留到工具字体 fallback 表。
  2. `PatchLoadedTmpAssets` 追加前只读检查工具字体 fallback 表，若候选已在其中则跳过，不修改原字体。
- Applied cases: 1

## S008 — 用非交互小补丁构造隔离 Git 索引

- Keywords: Git, alternate index, dirty worktree, policy rejection, partial hunk
- Applicable scenarios: 同一文件同时有用户改动和本任务单一 hunk，且真实索引还有不相关 staged 改动。
- Linked issues: #010
- Root cause: 执行策略拒绝含交互管道或显式子进程创建的复合命令。
- Fix:
  1. 用 `apply_patch` 在 `.scratch` 创建仅目标 hunk 的补丁。
  2. 为临时 `GIT_INDEX_FILE` 执行 `git read-tree HEAD`，精确 add 完整任务文件，再用 `git apply --cached` 加入单 hunk。
  3. 检查隔离 staged diff 后提交，对真实索引仅 reset 本任务路径到新 HEAD，保留其他 staged 状态。
- Applied cases: 1
