# hotel-paradise 修复记录（2026-08-13）

## 修复 F8：扁平布局 Mono 识别（老 Unity standalone/WebGL 导出）

- **现象**：hotel-paradise 首跑写回预检失败「Unity Mono 游戏结构不完整：
  需要同名 *_Data/Managed/UnityEngine.CoreModule.dll」——字体步骤拒绝，
  写回整体拒绝
- **根因**：游戏为老 Unity 扁平布局（`HotelParadise v1.1 WIN.exe` +
  `Managed/`、`Mono/`、`mainData`、`level0-2`、`resources.assets` 全部
  直接散在游戏根目录，**无同名 *_Data 宿主目录**）——
  `_detect_mono_architecture` 只认 `*_Data/Managed`，扁平布局判定失败
- **修复**（`hanhua/core/font_support.py`）：exe 判定兼认
  `game_dir/Managed`（扁平布局）；标准 `*_Data/Managed` 与扁平布局
  并存支持，老游戏互不干扰
- **验证**：新测试 `test_flat_layout_mono_install_without_data_dir`
  （扁平结构 → bepinex5_mono_x64 + 载荷部署成功）；font_support
  全量 80 passed；hotel-paradise --resume 重跑 → **23 条写回成功**、
  字体载荷部署（payload_deployed）、输入保护/重开验证 True

## 观察项登记（不在本游戏特判）

1. **PlayerConnectionConfigFile 引擎串误入**：`listen 647673994 0 0`
   （Unity 调试连接配置文件，运行时无用）被识别为文本翻译成
   「听 647673994 0 0」——纯文本文件的引擎配置无跳过规则。低影响
   （运行时该文件不参与），登记待统一：文件名/内容形态（listen+
   端口数字）→ 识别层跳过（与待办 A1 技术串豁免同族）
2. **多行致谢缩译+臆造**（审核 e3 实证）：`A Game by Kai Clavier /
   <b>Paintings and Photos</b> / The City of Winnipeg Archives / ...`
   多行 credit 文本被模型缩译为一行并臆造书名号标题——审核正确
   拦截（信息完整性），credit 多行文本翻译策略（保行保项）待优化
3. 4B 审核误判率观察：honorplusplus ~8%（1/13）· hunt 18%（2/11）
   · hotel-paradise 0%——误判集中于术语字面对应/语气词选择，低危

## 全局 F 系列（沿用）

F4 审核链路治本 / F5 UTF-8 / F6 model_name / F7 中置「翻译为」
（详见 honorplusplus fix record）——hotel-paradise 审核 3 条真实判定
（此前该类游戏恒 0）。
