# death-trips 闭环分析（final）

> 2026-08-11 run1 一次通过闭环。20 条译文 0 失败，写回 PASS。

## 1. 识别

- 文本文件 1（app.info）+ v2 资源 7：识别条目 20，全部 actionable（16 high / 4 medium）。
- 形态：asset_unity 7 文件 127 条（其中 20 条 actionable）、mono_csharp 2 文件 21 条。
- 工具：bmfont / il2cpp_dumper 均 verified。

## 2. 翻译（真实本地模型 Hy-MT2-1.8B）

- 20 条全部翻译成功，0 失败，28 请求 13.4s。
- 20 条译文逐条抽检（见 final-report 附录）：全部合格。
  - 占位符保留：`{0} FPS` → `{0} 帧每秒` ✓
  - 专名合理保留：`FirstPersonCharacter Profile`（脚本类名）✓
  - 格式串：`THANK YOU FOR<br>THESE` → `谢谢你们<br>这些`（<br> 保留）✓
  - 日期本地化：`October 31, 2008` → `2008年10月31日` ✓

## 3. 跳过判定（哑信号治理——130 条逐条审视）

| 原因 | 数量 | 判定 |
|---|---|---|
| type_reference | 62 | 该跳（TMPro.TMP_FontAsset 类类型引用） |
| unverified_user_string | 19 | **逐条审视**（见下） |
| method_name | 17 | 该跳（set_font 等方法名） |
| code_heavy_identifier | 16 | 该跳（代码标识符） |
| identifier_without_display_evidence | 14 | 该跳（无显示证据标识符） |
| shared_resource_config_object | 1 | 该跳（共享资源配置对象） |

**unverified_user_string 19 条逐条判定（全部该跳）**：游戏使用 Unity 官方
Standard Assets（水反射/飞机控制器/第三人称角色控制器），19 条全是其自带
的开发者字符串：

- 脚本错误/警告日志 8 条：`This script need an Image with a readbale
  Texture2D to work.`、`FOVKick camera is null...`、`AeroplaneContoller not
  found in object hierarchy`、`Warning: no main camera found. Ball needs a
  Camera tagged "MainCamera"...` 等——运行时开发者提示，玩家不可见
- 输入轴名 2 条：`Mouse X` / `Mouse Y`
- 输入系统错误提示 3 条：`There is already a virtual axis named...` /
  `There is already a virtual button named...` / `This is not possible to be
  called for standalone input...`
- 内部标识/对象名 4 条：`__WaterReflection`、`Water Refl Camera id`、
  `__WaterRefraction`、`Water Refr Camera id`
- 组件/对象名 2 条：`Rigidbody dragger`、`Waypoint Target`、`Skid Trails -
  Detached`（3 条）
- 纯换行 1 条：`\n`

结论：**无哑信号**——本游戏跳过判定全部成立，无需识别侧修复。

## 4. 写回

- 1 文本文件 20 条译文全部写入，输入保护/重开验证/原子发布全绿，字体
  runtime_verified，总体 PASS。

## 5. 结论

**run1 一次闭环**：0 失败 / 0 该翻而跳 / 写回全绿。无代码修复项。

（注：sweep 库清理出现 WinError 32 残留 project.db——runner 进程退出时
sqlite 连接未及时关闭，不影响本游戏闭环；下个游戏对前统一处理。）
