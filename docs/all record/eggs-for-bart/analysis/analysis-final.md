# eggs-for-bart 分析终稿

> 闭环轮次：run1（2026-08-11 22:51）· 134 翻译 / 0 失败 / 118 写回
>
> eggs-for-bart 是本轮双游戏对中**零失败零修复**的一方——134 条
> 全部一次通过，写回 WARN 为字体运行时验证的预期行为差异（见 §4），
> 无代码问题。本轮修复（F18/F19）由同组 driftapocalypse 暴露，经
> 其真实链路验证，eggs 未受影响。

## 1 失败分类总表（0 条）

无。134 条全部通过质量门一次写回。

## 2 跳过文本判定（316 条，无该翻而跳）

| 类别 | 数量 | 判定 |
|---|---|---|
| UnityEngine 类型引用（MaskableGraphic+CullStateChangedEvent 等） | 168 | structural（type_reference）✓ |
| 输入轴/按键名（Horizontal/Vertical/Submit/Cancel/Mouse X/Mouse Y） | 62 | structural（identifier_without_display_evidence——UGUI EventSystem/InputManager 配置）✓ |
| 按钮状态枚举（Normal/Highlighted/Pressed/Disabled） | 28 | structural（code_heavy_identifier）✓ |
| 调试/日志串（Warning: no main camera / The count is... / Word [） | 20+ | 开发调试路径不进 UI ✓ |
| 游戏名/专名（EggsForBart/Fleebs） | 2 | 专名保留 ✓ |
| 着色器/相机名（__WaterRefraction 等） | 2 | structural ✓ |

逐条抽检无「该翻而跳」。

## 3 写回逻辑层审计（F11 真实输出）

- 知识库 5 条规则启用（fit_bytes_nul_padding / placeholder_preserve /
  textasset_encoding_preserve / unityevent_binding_preserve /
  logic_key_compare）✓
- report 3 条（疑似逻辑键：Continue/Exit/Play——全真按钮文本，复核
  通过）✓
- 扩容 39 条（译文 UTF-8 > 原文，长度头自证通过）✓
- 回显跳过 16 条（L+R+B+A+B+Y 手柄按键串 ×16——按键组合是操作
  指令非翻译对象，跳过正确）· revert 0 ✓
- 四态：container=PASS · object=PASS · **runtime=WARN**（见 §4）

## 4 runtime=WARN 判定（预期行为差异，非缺陷）

- 闸门逻辑：`font.runtime_verified` → PASS；`payload_deployed`
  （已部署未验证）→ WARN；不可用 → BLOCKED
- eggs 是 32 位老 Unity 游戏（UnityCrashHandler32.exe），**静态字体
  替换未命中**（无内嵌 Font/TMP_FontAsset 对象）→ 走 BepInEx 运行时
  插件路径；font-health.json 需游戏实际运行写入，工具不自动启动
  游戏（安全设计）→ payload_deployed → WARN（不阻断发布）
- 对照：同轮 driftapocalypse 静态替换命中 → runtime_verified → PASS
- 处置：WARN 是部署成功但未经运行时确认的中性状态，中文字体插件已
  就位，玩家运行游戏后由插件生效。记录为观察项，不修复。

## 5 质量抽检

- 主菜单/关卡 UI 全部准确（警告：/继续/帮助/退出/播放/新游戏/停止
  按 1 键获取第 1 章的帮助…/0/24 个鸡蛋/巴特的证据！！！）
- 长句完整（警告：这个游戏有闪烁的颜色。极其巨大的噪音，使用血液
  和血腥场景…——容量内完整写入）
- 专名正确保留（Fleebs/L+R+B 按键串）

## 6 结论

**✅ 可闭环**。0 失败、写回 container/object PASS、revert 0、回显
跳过全部合理。runtime WARN 为字体验证预期差异（静态替换未命中 +
运行时插件未经验证），不阻断发布，中文字体插件已部署。
