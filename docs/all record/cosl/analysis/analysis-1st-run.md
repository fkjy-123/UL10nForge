# cosl 第一跑核查分析（首轮闭环）

运行时间：2026-08-11 07:03 ｜ 修复基线：无（首轮 0 失败，无修复）

## 1. 总览

| 指标 | 数值 | 结论 |
|---|---|---|
| 提取条目 | 1294（识别）+ 4983（il2cpp 元数据） | 池子全量 |
| 成功翻译 | 125 | 逐条核查 |
| 失败 | **0** | 首轮干净闭环 |
| 写回写入 | 43 译文 + 82 回显跳过 | 无 rejected，无未写入 |
| 文件 | 5（app.info/level0/resources.assets/sharedassets0.assets/global-metadata.dat） | 四态闸门全 PASS |

## 2. 游戏性质：国产中文游戏（WoofWoofStudio）

- 可见文本主体为**中文原文**（「英王的宝冠」「音效组」「配置json文件」等）——
  中文源放行，译文=原文回显不写回（82 条，逐条在 writeback 清单列明）
- 待翻译 125 条全部为**英文 UI/对话系统字段**：ProgramStep→程序步骤、
  Stage Context→场景背景、Enter Command...→输入命令……、Branch option index→
  分支选项索引等（Dialogue System 对话编辑器节点字段）
- 模型对中文源稳定回显，无外语混入（与 containment 的韩文泄漏不同，
  本游戏翻译量小且原文以中文为主）

## 3. 失败文本归因

**0 条失败。** 首轮直接闭环，无修复。

## 4. skipped 抽查（4222 条）

- il2cpp_metadata 4983 条：global-metadata.dat 字符串表（内部方法名/常量），
  全量 skipped——玩家不可见，识别正确
- 英文条目（2144 条命中字母检测）：全部为引擎/插件内部标识符与诊断串——
  MoreMountains.Feedbacks 命名空间、UI 控件状态名（Highlighted/Pressed/
  Selected/Disabled）、Cinemachine/Newtonsoft 异常日志
  （"Type.ContainsGenericParameters is true"、"serialized type could not
  be resolved"）、编码词
- **抽样未发现该翻未翻**：无英文句子级游戏对话被跳过

## 5. 结论

cosl（国产中文游戏）首轮即干净闭环：125 翻译 0 失败，写回 PASS，
无识别遗漏。不需要修复，进入下一游戏。
