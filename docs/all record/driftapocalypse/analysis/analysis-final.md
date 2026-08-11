# driftapocalypse 分析终稿

> 闭环轮次：run3（2026-08-11 23:16）· 165 翻译 / 0 失败 / 156 写回
>
> 本轮暴露**专名短语中 UI 词典词误杀**（Play Games Plugin 的 Play）与
> **全大写缩写回显误判**（MAX ×3）两类判定边界，修复 F18/F19。
> 4 → 3（F18）→ 0（F19）三轮收敛，全部系统性修复无单游戏特判。

## 1 失败分类总表（0 条，收敛过程 3 个唯一原文）

| # | 原文 | 译文 | 分类 | 处置 |
|---|---|---|---|---|
| 1 | `*** [Play Games Plugin 0.10.12] ERROR: Failed to format DateTime.Now`（run1 失败） | `[Play Games Plugin 0.10.12] 错误：无法格式化 DateTime.Now` | **译文正确被误杀**：Play 是 UI 词典词（play→播放）且位于 `Play Games Plugin` 专名短语开头（Google Play Games 插件名，品牌词非按钮动词）——短语分支 left_title=False → 误判 target_script_mismatch；DateTime.Now 是 .NET API 名（驼峰缩写已豁免，非触发词） | **F18 已修复**（run2 译出） |
| 2 | `MAX` ×3（data.unity3d 668/678 + DLL us#116） | `MAX`（回显） | 全大写 ≤3 字母缩写（Maximum）：1.8B 模型对单 token 缩写稳定回显（count-my-coins 'SFX' 先例）；max 在 UI 词典 → untranslated_text 判失败，与 proper_name_echo 侧已有豁免不一致 | **F19 已修复**（run3 放行，回显跳过保留原文——缩写保留符合界面惯例） |

## 2 修复统计

- **F18**（run2 验证）：4 → 3——UI 词典词（TitleCase 形态）右侧连续 ≥2
  个非词典 TitleCase 专名词 → 专名短语豁免（Play Games Plugin；Play
  Button/Play Store 短组合与全词典词序列不受影响）
- **F19**（run3 验证）：3 → 0——译文残留词全为 ≤3 全大写缩写（MAX/
  SFX/UI/OK）回显豁免，与 proper_name_echo 侧规则对齐（动作指令
  TOSS TRASH、多词 GAME OVER 类组合不受影响）

## 3 跳过文本判定（274 条，无该翻而跳）

类名引用（MainMenu/PauseMenu/ShopController ×53）+ UGUI 状态枚举
（Regular/Bold/Vertical/Submit/Cancel ×17）+ Yodo1 Mas 广告 SDK 调试
日志（[Yodo1 Mas] 系列 ×12，含 {0} 占位符）+ 三角网格库（Triangle）
错误消息 + 转义字符（\n \t \r）+ 包名/GUID/版本号。逐条抽检无该翻而跳
——SDK 日志是开发调试路径不进 UI 展示。

## 4 写回逻辑层审计（F11 真实输出）

- 知识库 5 条规则启用（fit_bytes_nul_padding / placeholder_preserve /
  textasset_encoding_preserve / unityevent_binding_preserve /
  logic_key_compare）✓
- report 30 条（疑似逻辑键：SETTINGS/PLAY/CREDITS/RESUME/RESTART/
  PAUSE/CONTINUE 全真菜单按钮文本，复核通过）✓
- 扩容 84 条（译文 UTF-8 > 原文，长度头自证通过）✓
- 回显跳过 9 条（BANDIT/Celica/CELICAR/CARWAII/MOSCAR/UFO 车辆专名 +
  MAX ×3 缩写——保留原文符合惯例）· revert 0 ✓
- 四态全 PASS（file/container/object/runtime）· runtime_verified ✓

## 5 质量抽检

- 主菜单/商店文本全部准确（高级会员资格/移除广告并解锁所有内容）
- 车辆属性描述正常翻译（Octano→辛烷、Prototype→原型、Tank→坦克）
- 车辆专名正确保留（BANDIT/Celica/UFO——竞速游戏车型名，音译/保留
  均为合理选择）
- 观察项：`Grippier`（更抓地）被音译「格里皮尔」——1.8B 对形容词
  化比较级误判专名音译，车辆属性描述轻度误译，不影响逻辑与可玩性
- 知识库命中 3 条历史案例（FAIL-00093 deadbeat 超长分块 /
  FAIL-00098 deepest-sword 全大写 UI 词典词补译放宽 / FAIL-00002
  baldis rich-text 剥离）；失败案例自动沉淀 2 种新模式入库

## 6 结论

**✅ 可闭环**。0 失败、写回四态全 PASS、revert 0。F18/F19 经真实
链路三轮验证（4 → 0 失败收敛），进入下一游戏对。
