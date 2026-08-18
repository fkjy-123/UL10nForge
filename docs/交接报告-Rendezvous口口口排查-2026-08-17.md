# Rendezvous 汉化口口口问题——交接报告

> 生成时间：2026-08-17 16:30
> 交接对象：接手继续排查/修复的 agent
> 工具项目：`C:\Users\mingming\Desktop\AI项目\unity游戏汉化工具`（Unity 游戏智能汉化工具）
> 游戏：`C:\Users\mingming\Downloads\Rendezvous.rar_汉化`（汉化输出目录，用户实机测试用这个目录）
> 原版：`C:\Users\mingming\Downloads\Rendezvous.rar`

---

## 0. 一句话现状

**汉化后的游戏仍大量口口口（中文方块缺字），且全部已知运行时/静态修复手段均未能根除。游戏主程序 `Rendezvous.exe` 从 `Rendezvous.rar_汉化` 目录启动（用户确认）。**

---

## 1. 工具概述

Unity 游戏智能汉化工具（启动器 `启动UL10nForge.bat`，主入口 `main.py`，Python 3.12 + PySide6 GUI）。

### 1.1 汉化流程（runner：`scripts/all_record_runner.py`）
1. **扫描识别**（`project.scan_all`）：Unity 资产解析（UnityPy 1.25.3）提取文本条目 → SQLite 项目库（`~/.hanhua_sweep/projects/<md5slug>/project.db`）
2. **翻译**：本地模型（llama-server，hy-mt2-1.8b）批量翻译
3. **审核**：本地语义审核（可跳过 `--no-review`）
4. **写回**（`project.write_all`）：
   - **静态写回**（`hanhua/core/unity/writer.py`）：把译文写回游戏资产副本（`_patch_asset`/`_patch_textasset`）
   - **字体闭环**（`hanhua/core/font/pipeline.py`）：静态字体替换（`install_static_fonts`）+ 运行时插件部署（`install_font_override`）
5. **发布**：原子发布到 `<游戏名>_汉化` 目录

### 1.2 字体体系（三条链路）
| 链路 | 实现 | 字体源 |
|---|---|---|
| 静态替换（游戏内 TMP_FontAsset/Font 资产替换） | `hanhua/core/unity/font_replace.py` | `fonts/SDF_Font_Asset/*.asset`（SDF，用户导出）+ `fonts/TMP_Font_AssetBundles/`（按 Unity 版本+字重选 bundle） |
| 运行时插件（BepInEx 动态兜底） | `font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs` → 编译 `resources/font_override/Hanhua.FontFallback.dll` → 部署 `BepInEx/plugins/HanhuaFont/` | `fonts/SimplifiedChinese/SourceHanSansSC-Medium.otf`（官方思源黑体 Medium，16.5MB，cmap 44853 码点） |
| 位图字体（NGUI/BMFont） | `hanhua/core/font/providers.py` | 工具链 BMFont |

### 1.3 插件（HanhuaFontPlugin.cs）的字体替换策略
- **legacy/UGUI**：`PatchUiTexts` + `PatchAllFontProperties`（反射替换一切 Font 类型属性 → `dynamicFont`，OS 动态字体 `CreateDynamicFontFromOSFont("Source Han Sans SC")`）
- **TMP**：`PatchTmpTexts`（替换 TMP 文本 `font` 属性 → `dynamicTmpFont`，atlas **4096×4096**）+ `PatchLoadedTmpAssets`（挂 fallback 表）
- **IMGUI**：`OnGUI()` 生命周期里无条件替换 `GUI.skin` 全部样式字体
- **Harmony 补丁**（最新版）：hook `TMP_Text.set_text` / `UnityEngine.UI.Text.set_text` / `LocalizationText.ChangeLanguage` 后置，文本每次更新强制字体=工具字体
- **健康证明**：`font-health.json`（协议 v5，逐码点验证 required-glyphs 集）

---

## 2. 游戏背景（Rendezvous）

- Unity **2019.4.22f1**，Mono（非 IL2CPP），2023-04 构建（印尼开发）
- 场景：49+ 个 level 文件（level0-48），主菜单 = `Assets/Global/MainMenu/S_MainMenu_Release.unity` → **level0**
- 语言体系：**CSV 多语言词典**（resources.assets 内 TextAsset #30-38，13 列 12 语言，表头 ` ,IND,ENG,...,CHN`）；**游戏语言设置只有英文**（Selected Language ID: 1）→ 汉化=覆盖 ENG 列（`--csv-overwrite-source` 模式）
- 游戏自带官方中文（Chapter1，428 行 CHN 列）
- **UI 体系**：
  - 文本组件 = **自定义 MonoBehaviour `LocalizationText`**（反编译确认）：
    ```csharp
    public class LocalizationText : MonoBehaviour {
        public string idText;
        private Text t_text;              // UGUI Text
        private TextMeshProUGUI t_textTMP; // TMP
        private void Awake() { t_textTMP = GetComponent<TextMeshProUGUI>(); t_text = GetComponent<Text>(); }
        private void ChangeLanguage(int index) {
            if ((bool)t_text) t_text.text = CSVParser.UI_GetTextFromID(idText);
            if ((bool)t_textTMP) t_textTMP.text = CSVParser.UI_GetTextFromID(idText);
        }
    }
    ```
  - 主菜单 "Text (TMP)" GameObject = RectTransform + CanvasRenderer + **1 个 MonoBehaviour**（m_Script 引用 pathID=9，**m_fontAsset = fileID=0, pathID=0x100000001（内置引用）**，m_Text 初始空）
  - 即：**游戏文本基本全部走 TMP 渲染**（UGUI Text 组件大多不存在）
- **游戏没有任何 TMP_FontAsset 资产、没有 TMP_Settings、没有 AssetBundle、没有 StreamingAssets**（全量扫描确认）
- **崩溃问题（已修复）**：resources.assets#30（SeaWall 对话 CSV）被 yaml 误判写回破坏 → CSVParser 数组越界崩溃黑屏（见 §3.2）

---

## 3. 已完成并验证有效的修复

### 3.1 字体链路更正（工具侧，代码已改）
- 弃用 `fonts/SimplifiedChinese/SourceHanSansSC-Regular.otf`（历史默认，CFF，已 git 删除）
- 新默认：`fonts/SimplifiedChinese/SourceHanSansSC-Medium.otf`（**官方 OTF**，与 SDF_Font_Asset 同族同字重）
- `FONT_OPTIONS` / `models.FontConfig.filename` / bmfont 路径 / `scripts/mass_writeback_all.py` 全部更新
- 旧 store 配置自动映射（`_normalize_font_filename`，兼容 `...Regular.otf` 与 `...Medium.ttf` 旧值）
- 测试：`tests/test_font_support.py` 等全部同步，**301+ passed**

### 3.2 YAML 误判 CSV 导致黑屏（已修复）
- **根因**：`looks_like_yaml_text` 把含冒号的 CSV 对话表（`SeaWall_D1,Arum: Apa kau...`）误判为 YAML → 表头行被 `_is_script_code_line` 过滤 → 按行号重建丢表头 → 游戏 `CSVParser.UI_GetTextFromID/CutScene_GetTextFromID` 数组越界 → 崩溃黑屏
- **修复**（四层）：CSV 判定排 yaml 前；`looks_like_yaml_text` 硬排除 CSV；yaml 条目不过滤（`_stamp` fmt=="yaml" 跳过代码行过滤）；`apply_format_text` yaml 行数守恒保护 + `_patch_textasset` yaml 组预检（`yaml_line_loss_guard`）
- 回归测试：`tests/test_yaml_csv_guard.py`（6 passed）
- **游戏侧**：汉化版 resources.assets 的 TextAsset#30 已还原为原版 CSV（171 行，验证 0 损坏）

### 3.3 插件 dll 同步
- 游戏内新 dll（含 IMGUI/Update 轮询修复）已同步到 `resources/font_override/`，哈希锁测试已更新

---

## 4. 口口口问题完整排查历程（全部尝试 + 结果）

> 关键监测文件：`Rendezvous.rar_汉化/BepInEx/plugins/HanhuaFont/font-health.json`（插件每 1 秒写）
> 插件日志：`Rendezvous.rar_汉化/BepInEx/LogOutput.log`

### 4.1 时间线 + 证据

| 时间 | 操作 | health 证据（TMP covered/missing） | 用户反馈 |
|---|---|---|---|
| 07:04 | 昨晚 run7 汉化完成（静态写回 5335 条译文 + 插件 3000 条运行时翻译） | — | — |
| 14:07 | level 文件被覆盖回原版（时间戳统一，字节与原版 0 差异）；sharedassets 保留汉化译文 | — | 游戏运行 |
| 14:23 | 插件运行（旧 dll + 旧 font.ttf=CFF Regular.otf 内容） | TMP **1609/160**（缺 160 个常用汉字），legacy 1769/0 | 大量口口 |
| 15:10 | 官方 OTF + atlas 4096 dll | TMP **1765/4**（仅缺波兰字符）| — |
| 15:22-15:31 | 暴力 Font 属性替换、OnGUI IMGUI patch、TMP 文本主字体替换（PatchTmpTexts） | TMP 1765/4 保持 | 用户：主菜单"音量/键盘"的量/盘口口 |
| 15:37-15:44 | **font.ttf 换成 WFM TrueType**（画蛇添足）| TMP **1/1768（灾难）** | 用户：**到处口口** |
| 16:02-16:06 | Harmony 三重补丁（TMP/UGUI set_text + ChangeLanguage 延迟重试） | TMP 1/1768（因 TrueType） | 用户：依然口口口 |
| 16:17 | **font.ttf 换回官方 OTF**（恢复 TMP 1765/4 基线）| 未实测（用户放弃） | — |

### 4.2 已尝试的修复（全部）

**A. 静态替换（游戏资产）**
1. ✅ sharedassets0 全部 15 个 Font 资产（Noto Sans SC ×4、Arial ×8、ShareTechMono、Coda、LiberationSans 等）m_FontData → 工具字体 **TrueType**（验证 OTTO→TrueType 头，303MB 保存成功，重开验证 15/15）——**部分口口消失**（UGUI 文本生效）
2. ✅ resources.assets Font#40（Perfect DOS VGA 像素字体）→ 同上
3. ✅ `Resources/unity default resources` 内置 Arial（m_FontData 空=动态字体）→ 改为静态工具字体（m_FontData=TrueType + 度量同步 13.92/-3.46/17.38）
4. ❌ TMP 文本静态修复**不可行**：游戏无 TMP_FontAsset 资产可改；UnityPy 1.25 无 create_object（不能注入新对象）；TMP_Settings 不存在

**B. 运行时插件（dll 迭代）**
1. atlas 2048→4096（TMP 动态字体容量 4 倍）——**有效**（1765/1769，TMP 字形验证全绿）
2. FindOptionalType 显式 Assembly.Load（含 Unity.TextMeshPro 候选 + 全局命名空间类型 → Assembly-CSharp）
3. PatchTmpTexts（TMP 文本 font → dynamicTmpFont）——**计数器恒 0**（未找到 TMP 文本对象）
4. PatchAllFontProperties（暴力反射替换一切 Font/TMP_FontAsset 类型属性）——**ui 恒 6**（只找到 6 个对象）
5. OnGUI() IMGUI skin 无条件替换——无日志证据（OnGUI 可能未触发）
6. **Harmony 补丁**（最新）：TMP_Text.set_text / UnityEngine.UI.Text.set_text / LocalizationText.ChangeLanguage 后置强制字体——16:04 日志 `HARMONY_PATCHED tmp_text=True ui_text=True change_language=False`（Assembly-CSharp 延迟加载问题，已加重试）

**C. 排查结论（确定的）**
- **TMP 文本 m_fontAsset = 内置引用（0x100000001）/无效 → TMP 用内置默认字体（无中文）→ 中文全口口** ← 主因
- TMP 文本组件**存在**于场景（"Text (TMP)" 60+ 个，level0 已验证）
- **插件 FindObjectsOfTypeAll 找不到这些 TMP 文本**（dump=0、PatchTmpTexts=0、consumers=0）——**原因未明**（疑点：TMP 组件 m_Script 引用 pathID=9 的 MonoScript 在哪个文件未定位；或插件扫描时机/场景加载问题）
- Harmony postfix **是否真正执行从未被验证**（HARMONY_UI/TMP 日志代码是最后才加的，未实机）
- 用户最后测试版本（16:04）TMP covered=1/1768 是 **WFM TrueType 导致**（TMP 创建崩溃），**已换回官方 OTF**

---

## 5. 当前部署状态（Rendezvous.rar_汉化，截至本报告）

```
Rendezvous_Data/
  resources.assets        # TextAsset#30 已还原原版（黑屏修复）；Font#40=TrueType 工具字体
  sharedassets0.assets    # 15 个 Font = TrueType 工具字体（303MB）
  Resources/unity default resources  # 内置 Arial → 静态 TrueType 工具字体
  level*                  # 原版字节（14:07 覆盖，未汉化——对话/剧情英文）
BepInEx/plugins/HanhuaFont/
  Hanhua.FontFallback.dll # 最新版 54272B：atlas 4096 + 暴力替换 + Harmony 三重补丁 + 诊断
  font.ttf                # 官方 OTF（SourceHanSansSC-Medium.otf，44853 码点，16.5MB）
  font-family.txt         # "Source Han Sans SC"
  translations.json       # 3000 条精确运行时翻译（07:04 部署）
  required-glyphs.json / runtime-templates.json  # 1769 码点需求集 + 12 模板
```

**关键待验证**：官方 OTF + 最新 Harmony dll 的组合**未实机验证**（TMP 1765 基线 + Harmony postfix 若生效 → TMP 文本应显示中文）。

---

## 6. 未解决问题与给下一 agent 的关键线索

### 6.1 核心谜团：插件 FindObjectsOfTypeAll 找不到场景 TMP 文本
- `Resources.FindObjectsOfTypeAll<TMP_Text>` 返回 0（PatchTmpTexts 恒 0）
- `Resources.FindObjectsOfTypeAll<Object>` 遍历含中文 text 的对象 = 0（TEXT_DIAG dump=0）
- 但 level0 场景文件里确认存在 60+ 个 "Text (TMP)"（RectTransform+CanvasRenderer+MonoBehaviour）
- **可能方向**：
  1. TMP 组件 m_Script 引用 pathID=9 的 MonoScript——**定位它在哪个文件**（fileID=0 语义；globalgamemanagers/level0 都未见）——如果引用断裂，TMP 组件可能被 Unity 当作未知对象加载，运行时行为异常
  2. 插件扫描时机：awake 时场景未加载；Update 轮询（1 秒）是否真的覆盖到主菜单加载完成后的时刻（health last_seen 持续更新=轮询活着，但计数恒 0）
  3. **尝试**：在插件里 dump `Resources.FindObjectsOfTypeAll<TextMeshProUGUI>()`（直接类型）与 `GameObject.FindObjectsOfType<TextMeshProUGUI>()` 的数量对比；dump 场景名 `SceneManager.GetActiveScene().name`（health scenes 恒空=异常信号）
  4. **尝试**：改 dump 上限（当前 80 个对象限制可能漏掉排序靠后的文本对象）——之前 dump=0 可能是 dump 逻辑 bug 而非真找不到

### 6.2 Harmony 补丁未验证
- 最新 dll 含 `HARMONY_UI/HARMONY_TMP` 日志（限 30 条）——**实机启动后看 LogOutput.log 是否有 HARMONY_UI/HARMONY_TMP 输出**，直接判定 postfix 是否执行
- `change_language=False` 问题：SetupHarmonyPatches 已加 Update 重试（frameCount%120==0）——实机看是否变 True
- 若 Harmony 无效：检查 BepInEx 5.4.23 的 Harmony 集成（0Harmony.dll vs 0Harmony20.dll 版本冲突可能）

### 6.3 游戏 DLL 修改（未尝试的终极手段）
- `Assembly-CSharp.dll` 已能反编译（ilspycmd 11.0.0.9375 已装：`dotnet tool install --global ilspycmd`）
- LocalizationText.ChangeLanguage 逻辑已确认——**可直接改 DLL**：
  - 方案 X：ChangeLanguage 里给 `t_textTMP.font` 赋动态创建的 TMP 字体（TMP_FontAsset.CreateFontAsset，从游戏 Font 资产——已替换工具字体）
  - 方案 Y：Awake 里 `gameObject.AddComponent<Text>()` 兜底 + 禁 TMP
  - 风险：重编译 Assembly-CSharp 需完整 Managed 引用链；游戏无强名验证

### 6.4 其他遗留
- **英文文本**：level 场景为原版（译文已丢失——昨晚 sweep 项目库被删 + docs/all record 记录被 15:03 重扫覆盖，无法恢复）；如需全汉化需重新翻译（约 5-6 小时，用户已拒绝）
- 项目库：`~/.hanhua/projects/1dbe255992`（GUI 库，38 条译文）；`~/.hanhua_sweep/projects/1dbe255992`（15:03 重扫的新库，5543 条 pending，译文为空）
- 译文恢复脚本 `scripts/_restore_rendezvous_translations.py` 存在但 translated.txt 已被覆盖（解析 0 条）
- `Rendezvous.rar_汉化` 有备份：`resources.assets.pre-fix30.bak`、`sharedassets0.assets.pre-fontfix.bak`

---

## 7. 工具侧代码变更清单（本次会话，未提交）

```
M hanhua/core/font_support.py          # FONT_OPTIONS 新字体 + 旧值映射 + install 规范化
M hanhua/core/models.py                # FontConfig 默认新字体
M hanhua/core/project.py               # bmfont 路径新字体 + scan_all csv_overwrite_source（昨晚）
M hanhua/core/formats/__init__.py      # yaml 行数守恒保护
M hanhua/core/formats/csv_format.py    # （昨晚）覆盖源列模式
M hanhua/core/formats/json_format.py   # （昨晚）
M hanhua/core/formats/yaml_format.py   # looks_like_yaml_text 排除 CSV
M hanhua/core/unity/extractor.py       # CSV 判定优先 + _stamp yaml 不过滤（+昨晚 ink/csv 改动）
M hanhua/core/unity/font_replace.py    # _font_ttf_candidate 兼容映射
M hanhua/core/unity/writer.py          # yaml 组预检 + ink 控制词保护（昨晚）
M font_plugin/Hanhua.FontFallback/HanhuaFontPlugin.cs  # atlas 4096 + 暴力替换 + OnGUI + Harmony + 诊断
M font_plugin/build.ps1                # 0Harmony.dll 引用
M resources/font_override/Hanhua.FontFallback.dll     # 最新编译
M scripts/mass_writeback_all.py        # 新字体名
A fonts/SimplifiedChinese/SourceHanSansSC-Medium.otf   # 官方 OTF（新默认）
A fonts/SimplifiedChinese/SourceHanSansSC-Medium.ttf   # WFM TrueType（备选，勿作插件默认——TMP 创建崩溃）
D fonts/SimplifiedChinese/SourceHanSansSC-Regular.otf  # 弃用
A tests/test_yaml_csv_guard.py         # 回归测试
M tests/*（多处）                       # 字体路径同步 + scan_v2 lambda 修复
.gitignore                             # 字体例外更新
```

**测试状态**：全量 `python -m pytest tests/` → **2700 passed / 11 failed（全部 pre-existing：Crypto 缺失 2 + GUI workbench 9）**

---

## 8. 复现与验证步骤（下一 agent 必读）

1. **启动游戏**：`C:\Users\mingming\Downloads\Rendezvous.rar_汉化\Rendezvous.exe`（用户实机测试）
2. **看证据**（游戏退出后）：
   - `BepInEx/LogOutput.log`：HARMONY_PATCHED（complete 状态）、HARMONY_UI/HARMONY_TMP（postfix 是否执行）、TEXT_DIAG、FONT_APPLY_COUNTS
   - `BepInEx/plugins/HanhuaFont/font-health.json`：TMP covered/missing（当前应恢复 1765/4）
3. **关键判断**：
   - TMP covered=1765 → 字体基线 OK；若口口 → Harmony postfix 未生效（查 §6.2）
   - TMP covered=1 → font.ttf 又变 TrueType（不要用 WFM ttf 做插件字体）
4. **继续方向优先级**：§6.2（Harmony 验证）→ §6.1（FindObjectsOfTypeAll 之谜）→ §6.3（DLL 修改）
