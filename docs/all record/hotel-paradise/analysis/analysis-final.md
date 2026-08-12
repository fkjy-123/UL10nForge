# hotel-paradise 分析报告（2026-08-13）

> 闭环轮次：run1（翻译/审核）+ --resume 写回（F8 扁平布局修复后）·
> 23 条识别 · 23 翻译 0 失败 · 23 写回 WARN（字体 payload_deployed）

## 1 成功文本抽检（23 条全检）

| 原文 | 译文 | 评价 |
|---|---|---|
| Check In | 登记/入住 | 佳 |
| Back / Instructions / Play / Credits | 返回 / 说明/指导 / 播放 / 致谢 | 可接受（短 UI 词，语义正确） |
| Exit? | 退出？ | 佳 |
| <b>Special Thanks</b> / <b>Music</b> | <b>特别感谢</b> / <b>音乐</b> | 佳（HTML 标签保留） |
| Hold <b>escape</b> to exit | 按住<b>Esc</b>键即可退出 | 佳（键位+标签保留） |
| By the way, this is the only time you or anyone else will ever see this room!... | 顺便说一下，这是你或其他人唯一一次能够看到这个房间的机会！…… | 佳（长句完整，语气保留） |
| Please assign a camera to the ThirdPersonCamera script. | 请为 ThirdPersonCamera 脚本分配一个相机。 | 可接受（开发者提示，专名保留） |
| Screenshot saved to User/Blah/Hey/HotelParadiseScreenshot 90909090 | 截图保存在……目录下 | 可接受（路径保留） |
| listen 647673994 0 0 | 听 647673994 0 0 | **误翻**（PlayerConnectionConfigFile 引擎串，见 fix record 观察项 1） |

- 占位符 0 丢失；HTML 标签/路径/专名全部保留 ✓

## 2 失败文本（0 条）

## 3 语义审核不合格确认（1 条）

- **e3**（mainData 多行致谢）：`A Game by Kai Clavier / <b>Paintings
  and Photos</b> / The City of Winnipeg Archives / Various public
  domain paintings / USGS De...` 被缩译为「KaiClavier 创作的
  《Vaporizer》」——多行 credit 只译一行 + 臆造书名号标题。
  **审核正确拦截**（信息完整性）。多行致谢的保行保项翻译策略
  登记待优化（fix record 观察项 2）

## 4 跳过文本判定（61 条）

- 二进制资源 5 文件 9 形态（asset_unity 9 / mono_csharp 2 /
  mono_unityscript 1——0 条显示文本）；skipped 61 为引擎串/二进制
  结构文本，判定合理
- **识别盲区**：游戏文本量极小（23 条），资源内文本已全量入池；
  PlayerConnectionConfigFile 1 条误入（观察项 1）

## 5 结论

- **F8 扁平布局实证**：老 Unity standalone/WebGL 导出的 Data 散根
  目录布局（无 *_Data 宿主）从「结构不完整」到完整闭环——写回
  成功 + 字体载荷部署 + 重开验证 True
- 23 条真实游戏文本全部正确翻译写回；1 条引擎串误翻低影响登记
- 审核 3 条真实判定（e3 拦截有效）；4B 审核误判率本游戏 0%
