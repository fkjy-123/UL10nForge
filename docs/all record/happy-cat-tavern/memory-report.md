# 经验记忆报告（happy-cat-tavern）

经验记忆（AgentMemory）是跨游戏自动学习的离散知识单元：
只沉淀质量门通过且非回显的译文，多次一致证据才晋升 active；
高置信短语在翻译时直接应用（仍过质量门复查），一般置信注入
prompt 参考；被拒绝的记忆降级直至退休。

## 1 本次会话
- 提案：0（新记忆单元首条证据）
- 证据积累：85（已有记忆再次通过质量门）
- 晋升 active：74（≥2 次一致证据）
- 直接应用：3 条（采纳 3 / 拒绝 0）
- 退休：0（被质量门拒绝 ≥2 次，不可信）

## 2 记忆库状态（按类型 × 状态）

- phrase: active 322 · pending 1351 · retired 3

## 3 TOP 记忆（按命中）

| 原文 | 语境 | 译文 | 证据 | 命中 | 拒绝 | 游戏 |
|---|---|---|---|---|---|---|
| A <#0080ff>simple</color> line of text. | r:display | 一条<#0080ff>简单的</color>文本行。 | 4 | 1 | 0 | goodmorning/happy-cat-tavern |
| You have selected link <#ffff00> ID 01 | r:display | 您选择了链接 <#ffff00>，ID为01。 | 4 | 1 | 0 | goodmorning/happy-cat-tavern |
| You have selected link <#ffff00> ID 02 | r:display | 您选择了链接 <#ffff00>，ID为02。 | 4 | 1 | 0 | goodmorning/happy-cat-tavern |
| subdirectories. This work is published from: Germany. | r:display | 子目录。这项工作发表于德国。 | 3 | 1 | 0 | foxhunt-chapter1/goodmorning |
| Domain Dedication. | r:display | 领域奉献。 | 3 | 1 | 0 | foxhunt-chapter1/goodmorning |

## 4 冲突/待复核

- ⚠️ `Function`（语境 `—`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Layer 4`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `To the extent possible under law, Christoph Peters has waived all copyright and`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `INFORMATION ON AN "AS-IS" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PROVIDED HEREUNDER, AND DISCLAIMS LIABILITY FOR DAMAGES RESULTING FROM`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The laws of most jurisdictions throughout the world automatically confer`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `exclusive Copyright and Related Rights (defined below) upon the creator`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `the purpose of contributing to a commons of creative, cultural and`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `scientific works ("Commons") that the public can reliably and without fear`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `These owners may contribute to the Commons to promote the ideal of a free`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `works, or to gain reputation or greater distribution for their Work in`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `For these and/or other purposes and motivations, and without any`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `is an owner of Copyright and Related Rights in the Work, voluntarily`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `terms, with knowledge of his or her Copyright and Related Rights in the`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `protected by copyright and related or neighboring rights ("Copyright and`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Related Rights"). Copyright and Related Rights include, but are not`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `likeness depicted in a Work;`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `subject to the limitations in paragraph 4(a), below;`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `vi. database rights (such as those arising under Directive 96/9/EC of the`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `2. Waiver. To the greatest extent permitted by, but not in contravention`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Affirmer's Copyright and Related Rights and associated claims and causes`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `purposes (the "Waiver"). Affirmer makes the Waiver for the benefit of each`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `member of the public at large and to the detriment of Affirmer's heirs and`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `successors, fully intending that such Waiver shall not be subject to`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `equitable action to disrupt the quiet enjoyment of the Work by the public`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `as contemplated by Affirmer's express Statement of Purpose.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `3. Public License Fallback. Should any part of the Waiver for any reason`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `extent the Waiver is so judged Affirmer hereby grants to each affected`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `irrevocable and unconditional license to exercise Affirmer's Copyright and`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Related Rights in the Work (i) in all territories worldwide, (ii) for the`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `maximum duration provided by applicable law or treaty (including future`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `of copies, and (iv) for any purpose whatsoever, including without`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `reason be judged legally invalid or ineffective under applicable law, such`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rights in the Work or (ii) assert any associated claims and causes of`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `action with respect to the Work, in either case contrary to Affirmer's`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `express Statement of Purpose.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `a. No trademark or patent rights held by Affirmer are waived, abandoned,`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `b. Affirmer offers the Work as-is and makes no representations or`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `title, merchantability, fitness for a particular purpose, non`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `c. Affirmer disclaims responsibility for clearing rights of other persons`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `that may apply to the Work or any use thereof, including without`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `limitation any person's Copyright and Related Rights in the Work.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Further, Affirmer disclaims responsibility for obtaining any necessary`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `party to this document and has no duty or obligation with respect to`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `this CC0 or use of the Work.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Lunchtime Doubly So`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `buff`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `debuff`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SCOPE`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `>AROUND PLAYER`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `>PICK ONE<
↓ `（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `CTRL
TO 
SLIDE`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `LMB
TO 
SHOOT`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PSXEffects v1.15.5 - update available (click to update).`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `KILL ENEMIES
TO RESTORE
HEALTH`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pixelization
With every miss`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Blind
Choice`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `No Explosion
Barrels`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Moving
Aim`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Uplayable
FOV`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ATTORNEY-CLIENT RELATIONSHIP. CREATIVE COMMONS PROVIDES THIS`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Statement of Purpose`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `of, applicable law, Affirmer hereby overtly, fully, permanently,`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `LEADERBOARD`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `No Explosion
Damage`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Heal over
Max HP`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Sawblades
Spinning
Around`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Cut 50% HP`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Always
Moving Forward`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `by cnnmon`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THEN move to next scene automatically`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `IF enough is poured into the cup`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `work on a project!`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `isn't,aren't,wasn't,weren't,haven't,hasn't,hadn't,won't,wouldn't,don't,doesn't,didn't,cannot,can't,couldn't,shouldn't,mightn't,mustn't,not,nat`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `OBJECT NOT TWEEENING AT BEGINNING`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `NOTHING TWEEENING AT BEGINNING`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `EVENT ALL REMOVED`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SPLINE POSITIONING AT HALFWAY`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ROTATE AROUND MULTIPLE`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `MOVE TO TRANSFORM WORKS`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SPLINE WITH TWO POINTS SUCCEEDS`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ROTATE AROUND`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `TWO DESTROY ON COMPLETE'S SUCCEED`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `WE CAN RETRIEVE A DESCRIPTION`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `GROUP IDS MATCH`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SOMETHING IS TWEENING`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `BEZIER CLOSED LOOP SHOULD END AT START`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SPLINE CLOSED LOOP SHOULD END AT START`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ON UPDATE FIRED`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `{0} :: This DOTweenAnimation's target is NULL, because the animation was created with a DOTween Pro version older than 0.9.255. To fix this, exit Play mode then simply select this object, and it will update automatically`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The work is made available under the terms of the Creative Commons CC0 Public`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Certain owners wish to permanently relinquish those rights to a Work for`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `part through the use and efforts of others.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Work and the meaning and intended legal effect of CC0 on those rights.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `future claims and causes of action), in the Work (i) in all territories`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `warranties of any kind concerning the Work, express, implied,`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `>BEST`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `TAKE
THIS
↓`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `YOUR MISSION 
IS TO DESTROY
ALL BROKEN ROBOTS `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grenade
Gun`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `No Damage
While Moving`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Leg is Longer
With every hit`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Less
Choice`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Every miss
Is Damage`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Enemy
Aura`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `wake up!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THEN make button to go to next scene appear`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `IF characters inputted increase past 50`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THEN this
happens!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `EVENT GAMEOBJECT REMOVED`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `TWEENED WITH ZERO TIME`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ZERO TIME FINSHES CORRECTLY`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `START IGNORE TIMING`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `CANCEL AFTER RESET SHOULD FAIL`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `VECTOR3 CALLBACK CALLED`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `GROUP FINISH`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Camera Control - <#ffff00>Shift + RMB
</color>Zoom - <#ffff00>Mouse wheel.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Unlockables`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `How to Play`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Word length starts at FOUR with normal bar speed`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Normal mode but all words are mirrored`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rugged Sailor`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Practice your typing with no pressure! Bar removed`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Keystrokes:`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Word Streak:`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Score: `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `High Score: `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Color Grading`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `URP Volume Profile 2`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `25,0,36 POSITION 
78.02 SOMETHING 
1564.879996 POSITION `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Get a score of 130 or more on Normal`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `It’s Meow or Never`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `11 New Achievement`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Climb Every Meow-tain`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach the last level on Hard`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach a word streak of 35 or more on Normal`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Last 1 minute or longer on Hard`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach a word streak of 20 or more on Hard`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Get a score of 50 or more on Mirrored`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You’ve Gotta Be Kitten Me!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach level 3 on Mirrored`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Extra Spicy`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach 8 letters on Mirrored`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Bai Jamjuree Medium`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You’ve gotta be kitten me!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You can't pass a NULL string to DOText: an empty string will be used instead to avoid errors`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Stop continuous haptic pattern`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
