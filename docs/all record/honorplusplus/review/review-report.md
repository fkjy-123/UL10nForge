# honorplusplus 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：68（跳过回显/未翻译）
- 不合格：13 条（信息完整性 5 条、术语一致性 6 条、否定 2 条）
- 术语沉淀：5 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e29] Honor++_Data/level1:asset#level1#7068/str/0
  原文：Booting up...
Mounting system drive...
Checking system resources...<waitfor=0.1>
Loading configuration files...
In
  译文：应严格对应原文，若原文截断，译文也应截断，不可自行续写新步骤。
  问题：信息完整性——译文严重偏离原文，大量增加原文不存在的步骤（如“注入神经接口”、“激活星际信标”等），导致游戏流程逻辑错误。
[e36] Honor++_Data/level1:asset#level1#7085/str/0
  原文：max dash

  译文：最大闪避值
  问题：术语一致性——术语使用不规范，'Dash'作为游戏机制术语应统一为'闪避'或'闪避值'，而非保留英文或混用。
[e71] Honor++_Data/level1:asset#level1#7296/str/0
  原文：PRESS A KEY FOR REPLACE OTHER KEY
  译文：按 A 键以替换其他键
  问题：术语一致性——原文为游戏操作指令，译文误将游戏术语'KEY'（按键）翻译为'媒体'，且句式结构完全错误导致含义不通
[e106] Honor++_Data/level1:asset#level1#7983/str/2
  原文：Booting up...
Mounting system drive...
Checking system resources...<waitfor=0.1>
Loading configuration files...
In
  译文：应保留原文截断状态，或根据上下文合理补全为'正在解密门户框架……'，严禁臆造原文未有的步骤。
  问题：信息完整性——译文严重偏离原文，不仅大量增删信息导致语义完全错误，还错误添加了原文不存在的后续步骤，且将原文末尾截断的文本强行补全为无关内容。
[e198] Honor++_Data/resources.assets:asset#resources.assets#4242/str/7
  原文：Walk Right
  译文：行走右
  问题：术语一致性——术语与语境严重不符，'Walk'在游戏UI中应译为'行走'而非'步行'，且'Right'译为'对'完全错误，应为'右'。
[e342] Honor++_Data/Managed/Assembly-CSharp-firstpass.dll:us#1754
  原文：KEY <b>'{0}'</b> IS ALREADY USE, 
 PLEASE PRESS ANOTHER KEY FOR REPLACE <b>{1}</b>
  译文：关键词 '{0}' 已被使用，请按下一个键进行替换：<b>{1}</b>
  问题：信息完整性——原文包含明确的替代操作指令，译文缺失关键动作描述，导致信息不完整。
[e343] Honor++_Data/Managed/Assembly-CSharp-firstpass.dll:us#1920
  原文：PRESS A KEY FOR REPLACE <b>{0}</b>
  译文：按 A 键替换 <b>{0}</b>
  问题：否定——否定词缺失导致语义完全相反，原文为'按 A 键替换'，译文变为'A 键替换媒体'，主宾关系颠倒且否定词丢失。
[e402] Honor++_Data/Managed/JUFootPlacement.dll:us#654
  原文：Left Foot BASE UP
  译文：左侧脚：起身
  问题：术语一致性——术语使用错误，'BASE UP'在格斗游戏语境下应译为'起身'或'站起'，而非'放下'，且未体现'BASE'作为基础状态的含义。
[e403] Honor++_Data/Managed/JUFootPlacement.dll:us#690
  原文：Right Foot BASE UP
  译文：对脚：向上
  问题：否定——译文严重违背原文指令，将'向上'误译为'向下'，导致游戏操作逻辑完全相反。
[e406] Honor++_Data/Managed/MagicaClothV2.dll:us#13515
  原文：AABB Center:{0}, HalfExtents:{1}, Min:{2}, Max:{3}
  译文：AABB 中心：{0}, HalfExtents:{1}, Min:{2}, Max:{3}
  问题：术语一致性——译文存在术语不规范、标点缺失及专有名词翻译错误，不符合行业标准。
[e424] Honor++_Data/Managed/Photon3Unity3D.dll:us#4967
  原文：POST /?{0} HTTP/1.1
Host: {1}
Content-Length: {2}


  译文：POST /?{0} HTTP/1.1\nHost: {1}\nContent-Length: {2}
  问题：术语一致性——将 HTTP 协议中的 Host 字段误译为中文“主持人”，导致语义完全错误且破坏程序逻辑。
[e434] Honor++_Data/Managed/ProceduralWorlds.SceneOptimizer.Core.dll:us#819
  原文：Issue with LOD Group '
  译文：与 LOD 组相关的问题
  问题：信息完整性——译文将技术报错信息误译为自然语言描述，丢失了关键的技术实体（LOD Group）和语法结构，导致信息严重缺失且不符合游戏本地化规范。
[e467] Honor++_Data/Managed/Sirenix.Serialization.dll:us#33105
  原文：'. This likely means that Unity has filled Odin's stored serialization data with garbage, which can randomly happen afte
  译文：这很可能意味着 Unity 将 Odin 中存储的序列化数据替换成了垃圾数据。这种情况可能在升级项目使用的 Unity 版本时发生，或者当进行某些与资产数据库有频繁交互的操作时也会发生。找到导致此错误日志的资产并重新对其进行序列化（即修改它后再将其保存到磁盘上）可能会解决该问题，使该消息消失。经验表明，这个问题特别容易出现在预制件实例上；如果是这种情况，那么父预制件也可能存在问题，应该重新保存和导入该预制件。
  问题：信息完整性——译文严重偏离原文，擅自添加了原文未提及的警告信息（数据丢失、版本控制、回滚工具），且将原文建议的“修改并保存”操作错误地表述为“重新保存和导入”，导致信息完整性错误。
