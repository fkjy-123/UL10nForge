# incremental-rts 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：114（跳过回显/未翻译）
- 不合格：25 条（信息完整性 4 条、术语一致性 7 条、语义一致性 9 条、语气 1 条、否定 2 条、人物关系 1 条、语义偏差 1 条）
- 术语沉淀：1 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e97] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/70
  原文：Laser weapons focus extreme heat and precise impact. They shred vehicles and aircraft beautifully, but large static stru
  译文：激光武器能够产生极高的热量和精确的能量打击。它们能轻松摧毁各种车辆和飞机，但大型静态结构则只能吸收这种能量。激光对建筑物仅造成 %s%% 的伤害。
  问题：信息完整性——译文将原文中激光武器对建筑物“仅造成特定百分比伤害”的精确数值限制，错误地泛化为“只会造成损害”，导致关键游戏机制信息丢失。
[e137] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/122
  原文：The source of all evil. They make the games with microtransactions there.
  译文：万恶之源。他们在那里通过微交易制作游戏。
  问题：术语一致性——译文存在术语误用及信息缺失，'source of all evil'未准确传达讽刺含义，且遗漏了原文中关于'制作游戏'的具体行为描述。
[e139] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/124
  原文：The source of all evil. They promise you can make ~100%% income in a week with some crypto schemes right before it crash
  译文：所有邪恶的根源。他们承诺你利用一些加密货币骗局，在一周内就能获得约 100% 的收益，就在其崩溃之前。
  问题：语义一致性——译文严重违背原文逻辑，将'骗局'误译为'手段'，且'约 100%'与'一周'的语序混乱导致含义完全错误。
[e149] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/134
  原文：The source of all evil. They write the TnCs here. Especially the small print.
  译文：所有错误的源头。他们在这里写下用户协议。尤其是那些小字部分。
  问题：术语一致性——术语翻译不准确，'TnCs'应译为'用户协议'而非'禁忌事项'，且'evil'在此处为双关语，译为'邪恶'丢失了原意中'错误'的含义。
[e193] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/197
  原文：<b>Colossus Brood:</b> %s%% chance to spawn with %sx HP and damage
  译文：<b>巨兽世代：</b> %s%% 几率生成 %sx HP 及 %sx 伤害
  问题：信息完整性——译文严重缺失关键信息，将'HP 和伤害'简化为'损害'，导致数值属性丢失，且'损害'一词不符合游戏术语规范。
[e200] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/207
  原文：Supercharged storm cores. Thunderstorms spawn {scale} larger with {health} HP, {damage} damage, {speedPenalty} move spee
  译文：增强版风暴核心。雷暴的规模会增大至{scale}，拥有{health} HP、{damage} 伤害、{speedPenalty} 移动速度惩罚，但雷暴产生速率{productionPenalty}。
  问题：信息完整性——译文严重缺失关键数值占位符，导致信息完全丢失且出现乱码。
[e254] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/278
  原文：Deploy the Lightning unit. Extreme-range laser cannon with devastating damage. Only few vehicles can survive it. Large s
  译文：那些拥有常规装甲的大型建筑，反而能吸收热量（对建筑物仅造成{buildingDamage}点伤害）
  问题：语义一致性——译文严重违背原文逻辑，将‘吸收热量’错误译为‘被高温破坏’，导致语义完全相反。
[e256] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/280
  原文：Rhino warheads cook through armor on contact. Rhino shots always instantly destroy most enemy units. Buildings and some 
  译文：当 Rhino 弹头接触敌人装甲时，会立即将其摧毁。Rhino 炮弹总能瞬间摧毁大多数敌方单位。拥有熔覆护盾的巨型单位则免疫此伤害。由于工程复杂，Rhino 的生产速度会受到惩罚。
  问题：语义一致性——译文严重违背原文逻辑，将‘接触即摧毁’误译为‘接触时摧毁’，且错误地将‘熔岩护盾’译为‘熔岩护盾’（原文为 melt-shielded，指融化护盾或类似机制，此处语境应为免疫特定伤害，译文逻辑混乱），同时遗漏了原文中关于工程复杂性与生产惩罚的具体关联描述。
[e266] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/298
  原文：Restorative protocols knit wounds between volleys. All units regenerate {regen} HP per second
  译文：修复协议在轮次间缝合伤口。所有单位每秒再生 {regen} HP
  问题：语义一致性——译文严重偏离原文含义，将游戏机制描述误译为人际关系，且丢失关键数值信息。
[e270] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/302
  原文：Sacrificial layers flake away instead of hull. Reduce damage taken by {reduction}
  译文：牺牲层会剥落而非外壳，以此减少受到的伤害（{reduction}）
  问题：语气——译文语序生硬且因果逻辑连接词使用不当，不符合游戏 UI 简洁自然的表达习惯。
[e281] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/324
  原文：Disposable impact layers strip kinetic energy before the hull. Mantis units gain {shields} extra shields, but their prod
  译文：一次性冲击层在船体之前就能将动能转化为其他形式。Mantis 单元则能够吸收这种能量，获得 {shields} 额外护盾，但其生产速度 {productionPenalty}。
  问题：信息完整性——译文严重偏离原文，丢失关键信息且错误处理了变量占位符，导致语义不完整。
[e292] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/340
  原文：Refuse to fall. Gain an extra {chance} death defiance chance, but overall production speed {productionPenalty}. Units be
  译文：拒绝倒下。获得额外的死亡反抗机会，但整体生产速度将受到惩罚。低于最大生命值 {minHp} 的单位无法反抗死亡。
  问题：否定——译文严重偏离原文含义，存在否定词缺失、人物/对象关系颠倒、术语误用及信息截断等问题。
[e301] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/352
  原文：Oversized ordnance cores occasionally produce a walking siege rifle. {chance} chance each Reed unit spawns {scale} large
  译文：大型弹药核心偶尔会生成一种步行式攻城步枪。每有一个 Reed 单位，就有{chance}{scale}个更大、拥有{multiplier}点生命值和伤害值的**武器**被生成；其攻击范围为{rangeMultiplier}，移动速度为{speedPenalty}。这种武器可以发射大型弹药，但 Reed 单位的生产效率会受到{productionPenalty}的影响。
  问题：人物关系——译文将原文中'武器被生成'错误地理解为'Reed单位被生成'，导致人物关系与逻辑对象严重偏差。
[e304] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/356
  原文：Ant units gain an additional {evasion} chance to evade damage, but Ant production rate {productionPenalty}
  译文：蚂蚁单位获得额外的 {evasion} 几率来躲避伤害，但蚂蚁的生产速率会 {productionPenalty}
  问题：语义一致性——译文存在严重语病，将名词误译为动词，且句子结构破碎导致语义不通顺。
[e399] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/462
  原文：Defeat contingency reserves seed the next deployment. After losing, gain {resources} for your next run
  译文：失败带来的应急储备为下一次回合提供了支持。失败后，就能获得{resources}用于你的下一次回合
  问题：术语一致性——译文存在严重术语误用（'部署'应为'回合'，'优势'应为'资源'，'运行'应为'回合'），导致游戏机制含义完全错误。
[e448] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/512
  原文：Expanded fallback allocation keeps production lines funded. After losing, gain {resources} for your next run
  译文：扩展的备用分配机制确保生产线持续运行。若亏损，将在下一轮获得 {resources}。
  问题：语义偏差——译文严重偏离原文逻辑，将'亏损后获得收益'错误地表述为'仍能获得收益'，且遗漏了'用于'这一关键用途信息。
[e459] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/524
  原文：Strategic reserve accounts absorb operational losses. After losing, gain {resources} for your next run
  译文：亏损后，为下一次运行获得 {resources} 收益。
  问题：语义一致性——译文严重偏离原文逻辑，将“亏损后获得收益”误译为“亏损后，再获得收益”，且丢失了“用于你的下一次运行”这一关键信息，导致语义完全错误。
[e485] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/550
  原文：Maximum continuity budget guarantees reconstitution capacity. After losing, gain {resources} for your next run
  译文：最大连续性预算保证重建能力。失败后，获得{resources}用于下一次运行
  问题：语义一致性——译文严重偏离原文含义，将'获得资源'错误译为'获得胜利'，且'重建能力'与'连续性预算'的对应关系生硬，不符合游戏 UI 语境。
[e497] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/564
  原文：Impact-tuned cores breach hardened plating. Increase all unit damage by {damage}
  译文：经过 Impact 调校的核心能够击穿强化装甲。所有单位的伤害都会增加 {damage}。
  问题：术语一致性——术语使用不规范，'Impact-tuned' 未采用游戏行业通用译法，且'镀层'一词在 UI 语境下不够精准。
[e555] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/626
  原文：Replace Bamboo's projectile with a precision laser beam that never misses. The beam's overwhelming temperature and preci
  译文：只有{buildingEffectiveness}对建筑物有效。
  问题：语义一致性——原文中'buildings'指代建筑物，译文将其误译为'巨大建筑物'，导致语义逻辑混乱且与后文'常规装甲'搭配不当，属于严重信息错误。
[e590] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/662
  原文：Extended ballistics tables push Rocks past the horizon. Increase Rock attack range by {range}
  译文：扩展弹道表将岩石推过地平线，并将攻击范围增加至{range}。
  问题：语义一致性——译文将原文两个独立动作合并，导致语义偏差且丢失了关于'弹道表'和'地平线'的关键信息。
[e597] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/670
  原文：Long-range fire solutions lock targets at extreme distance. Increase unit attack range by {range}
  译文：远程火力可锁定极远距离目标。将单位攻击范围增加 {range}
  问题：术语一致性——术语使用不规范，'Long-range fire solutions' 译为'远程射击解决方案'过于生硬且不符合游戏 UI 习惯，应简化为'远程火力'或'远程射击'。
[e599] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/672
  原文：Every perimeter emplacement receives upgraded fire solutions. Increase all base weapon damage by {damage}
  译文：每个防御位置都配备了升级后的火力配置。所有基础武器造成的伤害均增加 {damage}。
  问题：术语一致性——术语严重错误，将游戏术语'fire solutions'误译为消防相关的'灭火装置'，导致含义完全偏离。
[e636] Incremental RTS_Data/resources.assets:asset#resources.assets#209/csv/row/722
  原文：Minor line tuning shaves idle gaps without retooling. Increase production speed by {production}
  译文：微调机制可消除闲置间隙，无需重新配置。
  问题：术语一致性——术语使用不规范，'tuning'译为'微调调整'冗余且非行业标准，'retooling'译为'重新组装'不准确，应为'重新配置'或'重新设计'。
[e668] Incremental RTS_Data/resources.assets:asset#resources.assets#210/line/52
  原文：1) Neither the Font Software nor any of its individual components,
  译文：1) 无论是字体软件还是其任何单个组件，均不得...
  问题：否定——译文遗漏了原文中的否定词'Neither'，导致语义完全相反。
