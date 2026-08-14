# 经验记忆报告（lilys-day-off）

经验记忆（AgentMemory）是跨游戏自动学习的离散知识单元：
只沉淀质量门通过且非回显的译文，多次一致证据才晋升 active；
高置信短语在翻译时直接应用（仍过质量门复查），一般置信注入
prompt 参考；被拒绝的记忆降级直至退休。

## 1 本次会话
- 提案：1013（新记忆单元首条证据）
- 证据积累：10（已有记忆再次通过质量门）
- 晋升 active：5（≥2 次一致证据）
- 直接应用：0 条（采纳 0 / 拒绝 0）
- 退休：0（被质量门拒绝 ≥2 次，不可信）

## 2 记忆库状态（按类型 × 状态）

- phrase: active 1069 · pending 11066 · retired 17

## 3 TOP 记忆（按命中）

| 原文 | 语境 | 译文 | 证据 | 命中 | 拒绝 | 游戏 |
|---|---|---|---|---|---|---|
| **ANY CAMERA** | r:display | 任何相机 | 3 | 16 | 0 | happy-cat-tavern/honorplusplus |
| Floor {0} | r:display | 地面 {0} | 3 | 9 | 0 | hickory/minato |
| Option A | r:display | 选项 A | 6 | 8 | 0 | force-reboot/inch-by-inch/incremental-rts |
| GAME OVER | r:display | 游戏结束 | 5 | 5 | 0 | hickory/inch-by-inch |
| Thank you for playing! | r:display | 谢谢您的表演！ | 5 | 5 | 0 | hickory/isolated-inhale |

## 4 冲突/待复核

- ⚠️ `Additive with Mask`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `So much chaos! Desolo and Benjamin pulled through like always. Jonathan saw for loops in Daniel's shaders. Wirovin's pulled off amazing environments for her first jam. And 47A continues to lend her flexible voice.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The earliest struggle was figuring out how we wanted our character to look. At the time, she was human and we spent a lot of time arguing over her color scheme and her outfit. The Hickory Dickory Dock motif did not come until much later in development.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Development was quite slow in the beginning, with most of the time spent designing and arguing. Lots of placeholders were used. This was our biggest team yet, and everyone seemed to have different ideas.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `As was tradition with most of our jam games (starting around 2022) they've always featured a boss or some sort of huge encounter. Daniel just loves making bosses for some reason. Of course Daniel can't draw like Emiliano or Coco or Yishan or Wirovin so he has to settle with a terrible doodled concept.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Jonathan had an idea for a robot game about maintaining your factory, which we revisited in our brainstorming when Daniel thought of merging it with the theme of a clock tower. We all wanted to do something with a clock tower vibe.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `"But no worker can work forever. Cracks. Hairline fractures. All things break given time. And somewhere below, teeth grind through the brass and something scurries in the dark."`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `"One last worker remains. A contingency if you will. Unwound. Unused. Waiting. A little someone stirs in the wake of it all. Wake up."`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `"High above the rooftops, wrapped in a fog that doesn't clear, looms a great clocktower. A monument that has stood longer than anybody could ever remember."`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `I don’t think I can carry you.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `It’s ok, I’ll get us all up soon. I hope.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Above, the many… made whole.`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Time Slowdown Vol Profile`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Clockwork Scourge`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Click the pipe pieces to change their orientation!`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rapidly scrub your mouse over the crystal to clean it!`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Members of the University of Waterloo Game Development Club
Audrey, Yulian, and Michael
Jasmine and Matthew`（语境 `r:display`）出现 8 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `"Three dolls, wound by its very mechanisms, are duty-bound to its maintenance. Day after day. Month after month. Year after year."`（语境 `r:display`）出现 7 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Function`（语境 `—`）出现 6 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Layer 4`（语境 `r:display`）出现 6 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Main Camera Profile`（语境 `r:display`）出现 5 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `What – clk – happening…`（语境 `r:display`）出现 5 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `To the extent possible under law, Christoph Peters has waived all copyright and`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PROVIDED HEREUNDER, AND DISCLAIMS LIABILITY FOR DAMAGES RESULTING FROM`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The laws of most jurisdictions throughout the world automatically confer`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `exclusive Copyright and Related Rights (defined below) upon the creator`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `the purpose of contributing to a commons of creative, cultural and`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `scientific works ("Commons") that the public can reliably and without fear`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `These owners may contribute to the Commons to promote the ideal of a free`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `works, or to gain reputation or greater distribution for their Work in`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `For these and/or other purposes and motivations, and without any`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `is an owner of Copyright and Related Rights in the Work, voluntarily`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `terms, with knowledge of his or her Copyright and Related Rights in the`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `protected by copyright and related or neighboring rights ("Copyright and`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Related Rights"). Copyright and Related Rights include, but are not`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `likeness depicted in a Work;`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `subject to the limitations in paragraph 4(a), below;`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `vi. database rights (such as those arising under Directive 96/9/EC of the`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `2. Waiver. To the greatest extent permitted by, but not in contravention`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Affirmer's Copyright and Related Rights and associated claims and causes`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `purposes (the "Waiver"). Affirmer makes the Waiver for the benefit of each`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `member of the public at large and to the detriment of Affirmer's heirs and`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `successors, fully intending that such Waiver shall not be subject to`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `equitable action to disrupt the quiet enjoyment of the Work by the public`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `as contemplated by Affirmer's express Statement of Purpose.`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `3. Public License Fallback. Should any part of the Waiver for any reason`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `extent the Waiver is so judged Affirmer hereby grants to each affected`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `irrevocable and unconditional license to exercise Affirmer's Copyright and`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Related Rights in the Work (i) in all territories worldwide, (ii) for the`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `maximum duration provided by applicable law or treaty (including future`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `of copies, and (iv) for any purpose whatsoever, including without`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `reason be judged legally invalid or ineffective under applicable law, such`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rights in the Work or (ii) assert any associated claims and causes of`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `action with respect to the Work, in either case contrary to Affirmer's`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `express Statement of Purpose.`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `a. No trademark or patent rights held by Affirmer are waived, abandoned,`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `b. Affirmer offers the Work as-is and makes no representations or`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `title, merchantability, fitness for a particular purpose, non`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `c. Affirmer disclaims responsibility for clearing rights of other persons`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `that may apply to the Work or any use thereof, including without`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `limitation any person's Copyright and Related Rights in the Work.`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Further, Affirmer disclaims responsibility for obtaining any necessary`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `party to this document and has no duty or obligation with respect to`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `this CC0 or use of the Work.`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `25,0,36 POSITION 
78.02 SOMETHING 
1564.879996 POSITION `（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You still look very well made, given…`（语境 `r:display`）出现 4 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `INFORMATION ON AN "AS-IS" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `When enabled, numbers will also count exploded mines.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pan Left`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Hides extra tooltips about blue hearts, shields, and such.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Count Exploded Mines`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Each class brings a unique ability into the run`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `No Flags`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Use no flags`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Bold Italic`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Win a run at Hard difficulty.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Win a run with every class at Standard difficulty.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Win a run with every class at Hard difficulty.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete a Guardian stage without taking any damage.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete a run without ever using flags.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Buy out an entire shop's items in one visit.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pick up a legendary item.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `One Shot`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants 3 <b>heart fragments</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Highly decreases <b>curses</b>' <b>difficulty</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Consumes 5 <b>gold</b>. Grants 1 <b>golden heart</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Restores 2 <b>empty hearts</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Stage</b> boards have 2 more columns.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Coined heart`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Removes 10 seconds from the timer at the start of each <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Prevents all damage from the first 5 <b>clicks</b> in a <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Chords</b> can be used without counting as a <b>click</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Chord nullifier`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Safe start`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Discover</b> a <b>common</b> <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Consumes all <b>artifact</b> charges. Grants 1 <b>empty heart</b> per lost charge.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reveals the <b>curses</b> of any <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Player madness`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Removes all <b>hearts</b> but one. Removes all <b>shields</b>. Breaks all <b>relics</b>. Grants <b>GGEZ</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Adds 1 empty charge to your <b>artifact</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Breaks a <b>relic</b> of your choice, then <b>discover</b> a new <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Adds 1 <b>gold</b> to the <b>stage rewards</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rerolls item selections.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Loaded dice`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Contains 2 copies of a <b>relic</b>. Hatches after 3 <b>stages</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mana elixir`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Deals 1 damage. Grants 15 <b>gold</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Aegis shard`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Items in <b>chests</b> will always be <b>rare</b> or higher.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Discover</b> an <b>epic</b> <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `No <b>gold</b> from <b>stage rewards</b> for the next 5 <b>stages</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants an empty heart when all fragments are filled.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Discover</b> an <b>uncommon</b> <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Charges your <b>artifact</b> by 2.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants 3 <b>gold</b> for each <b>empty heart</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Flags</b> can be used without counting as a <b>click</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grim lantern`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Consumes 1 <b>blue heart</b>. Clears an area within a radius of {0}.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Breaks a <b>relic</b> of your choice. Grants 20 <b>gold</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Restores 3 <b>hearts</b> upon death, then it breaks.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Charges your <b>artifact</b> by 1 at the start of each <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mana source`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Discounts <b>shop</b> items by 10%.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Restores 1 <b>heart</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Chests</b> always contain a <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Restores all <b>hearts</b> upon death, then it breaks.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants and restores 1 <b>heart</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Breaks a stackable <b>relic</b> of your choice. Grants an <b>Egg</b> that contains 2 copies of it.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Guardian stages</b> have 1 less <b>curse</b>. (can't go below 1)`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Charges your <b>artifact</b> by 1 upon taking damage.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You can pick 1 more item on <b>stage rewards</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reveals the number of hidden <b>chests</b> in the <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Treasure map`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Removes 5 <b>clicks</b> at the start of each <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `All <b>stages</b> have a <b>difficulty</b> of 1. You can't get any hearts or gold anymore.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Items in <b>chests</b> will always be <b>uncommon</b> or higher.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Prevents the first <b>click</b> from hitting a <b>mine</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You find only <b>legendary</b> items. Breaks when you pick a <b>legendary</b> item.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `HUD is hidden.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Blinding seal`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Doubles the amount of <b>hearts</b> gained with items.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Soul cluster`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Destroys all <b>empty hearts</b>. Grants 2 <b>blue hearts</b> for each lost heart.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Shops</b> have 1 more <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Shops</b> have 1 more <b>consumable</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mines deal 1 more damage.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The board will be missing 15% of its cells.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Cursed powder`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Slightly decreases <b>curses</b>' <b>difficulty</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants a curse upon breaking.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Decreases <b>stages</b>' <b>difficulty</b> by 1.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The board may contain cells that cannot be resolved without guessing.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Slows the timer by 10%.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grants 5 <b>gold</b> when a <b>mine</b> explodes.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Adds 1 <b>chest</b> indicator to the map.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Play the standard version of Minato`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Enter seed`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Select a class`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Count exploded mines`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You will lose any progress in the current stage. Continue?`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `When enabled, numbers will also count exploded mines`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pan right`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Hides extra tooltips about blue hearts, shields, and such`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Most gold in a run`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Shop rerolls`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Copy seed to clipboard`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `A customized run will not unlock any collectible`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `This will reset progress in all classes and in the Collection. Continue?`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Select to play a sample sound effect`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reroll items in the shops 10 times in a single run.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete a run with the Oracle.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Win the challenge to earn extra gold, but you get nothing if you fail.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Something blocks the way down. Defeat it to proceed and earn a <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rare`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Used fewer than {0} clicks`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Did not use any flags`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Frozen items are inactive until the next <b>stage</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Contains traps that end the stage with no rewards. Complete it to earn a <b>relic</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Item discovered: <b>{0}</b>`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Proceed to the next floor.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Don't take any damage.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete the stage using as few clicks as possible.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Guardian defeated`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Earned for exploring the crypt`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Hearts are the only currency accepted here.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pay to reroll available items.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Next reward:`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Contains random items.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Welcome to <b>Minato</b>. This grid is the <b>map of the current floor</b>. Each cell represents a <b>stage</b>. Complete a stage to <b>unlock the adjacent ones</b> in the four cardinal directions.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `A cell with a number indicates <b>how many mines surround that cell</b>, including diagonals. Use this information to determine which cells are safe and which conceal mines.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You can <b>flag</b> a cell with <input:Flag> if you suspect it contains a mine. This reduces the mine counter accordingly and prevents the cell from being revealed accidentally.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `When a cell's number matches the count of flags surrounding it, you can select it to perform a <b>chord</b>. Doing so will reveal all non-flagged cells around it, allowing you to clear the board faster and with fewer clicks.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Each floor has a <b>guardian stage</b> with <b>curses</b> that you must overcome. Beat it to advance to the <b>next floor</b>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `If you accidentally reveal a mine, you only lose 1 <b>heart</b>, so it's not an instant loss. You can check your health in the upper left corner. Try to reveal a cell with <input:Reveal>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `If you get stuck, you can use your <b>Artifact</b> to make progress, but use it wisely, as it will consume one charge. You can check its status in the lower left corner.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `In the upper left corner you can check the <b>number of the floor</b> you're currently on. Now select the only available stage, marked with a <b>1</b>, which indicates its difficulty.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Congratulations on clearing your first stage! You'll now receive some <b>bonuses</b> based on your performance. You can always check the click counter and the timer in the upper left corner, but the target numbers aren't displayed until you complete the stage, so don't sweat it. Just play your best!`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Keep in mind that you can drag the board around with <input:Pan> and zoom in and out with <input:ZoomIn> and <input:ZoomOut>.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `These gears are jammed! Move to it to repair it.`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `play`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `LIVES USED:`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `OPTIONS
`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `FLOOR COMPLETE`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `STOMP HIS HEAD UNTIL HE BLEEDS`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `GET THE FUCK OUT OF THERE`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SPACE TO DASH`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `FLOOR`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `With help from:

- Funky (audio assistance)
- DAGGER (design help, early character models)`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `DESIGN, MODELLING, STORY, ANIMATION AND GAMEPLAY BY 

aloe-digital`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `He's always with his mates when he leaves work. I'd get shredded.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `I'd rather get him here while he's sectioned off from them.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `She wasn't doing anything, she just wanted to go home.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `You chose to stay on the line buddy.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `And then they're gonna take me in.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Well because if they somehow bring me back I'm gonna be in hospital.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `And then I'll get fucking arrested and it'll be way worse than being here.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `I get what you're saying I'd just rather die there and then than go to jail.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `STOMP ONCE INSTEAD OF TWICE TO KILL`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Security Ending`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `you're not fucking clever. <delay0.5>we both know you're the ones who robbed my house.<delay0.5>you fucking <delay0.5><shake0>KILLED toby. <delay0.75>and you <i>ALL</i> had guns ready to come and kill me too!`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `you and the-<delay0.6><skip>`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `now that work is over<delay0.2>.<delay0.2>.<delay0.2>. <delay0.7>all of your unpaid fucking interns have gone home.<delay0.2>.<delay0.2>.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `your fucking head, you smell like crack and weed, you're <i>SEEING THINGS</i>. you don't even know what you're doing!`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `shut the <shake0>fuck up! <delay0.5><shake0>shut up! tell me where dave is! i know you and the higher ups are robbing us!`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `+200pts`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Select a Class`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Not editable`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `6000.3/staging`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reach floor 10.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Flawless`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete a run without taking any damage.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Haste charm`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Contains a random item.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mana catalyst`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Discover</b> a <b>rare</b> <b>relic</b>.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Deals 1 damage at the start of each <b>stage</b>.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pieces o' Eight`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Gold pouch`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Rare candy`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mana heart`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Guiding flame`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Swift hands`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Numbers are shuffled.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Consumes all <b>gold</b>. Grants 1 <b>blue heart</b> for every 10 <b>gold</b> lost.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Starting a new game will overwrite your current game. Are you sure?`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Gain 3 shields in a single run.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Already taken`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `After enough repairs, the clock tower will calm down for a little.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Music and SFX`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `There is a version mismatch between the FMOD header and either the FMOD Studio library or the FMOD Low Level library.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `A HTTP error occurred. This is a catch-all for HTTP errors not listed elsewhere.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[FMOD] RuntimeManager accessed outside of runtime. Do not use RuntimeManager for Editor-only functionality, create your own System objects instead.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[FMOD] Cannot open network port for Live Update (in-use), restarting with Live Update disabled.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `FMOD Studio Debug`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[FMOD] Unable to load {0} - bank already loaded. This may occur when attempting to load another localized bank before the first is unloaded, or if a bank has been loaded via the API.`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[FMOD] Could not load bank '{0}' : {1} : {2}`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pan Right`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pan Down`（语境 `r:display`）出现 2 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `Left Hand`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `FLOOR CLEARED`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Because if they didn't fire me earlier over that prick Devin I wouldn't be here right now.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Why not just find Devin?`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Still fucked up that I had to hear that.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `If you get shot here first thing I'm doing is calling 911.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Well sorry for looking out for you.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `GUNS FIRE ON IMPACT`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `you think we've got guns?`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `im sick of you. <delay0.2>if you won't tell me, <delay0.1>be that way.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Security Intro`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THERE YOU ARE!!!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PRESS ESCAPE TO GO BACK`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PRESS ESCAPE TO QUIT`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Mug Grip`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Board Animations`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Board Cleared`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Reset profile data`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Get all 4 bonuses on a single stage.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Contains random items; hidden and revealed on the map after completing all adjacent stages.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Egg`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Restored after every stage.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Stages</b> contain 1 less <b>mine</b>.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Echo orb`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<b>Discover</b> effects offer 1 more choice.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Scrap seller`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Stage`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Complete a run at Standard difficulty with this class`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Pan up`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Type your feedback here.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Are you sure you want to exit?`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Artifact upgrade`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Board cleared`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Crypt`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Floor {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Earned for defeating the Guardian`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Crypt explored`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `In the upper right corner you can see your current <b>Relics</b>, useful tools that alter many aspects of the run.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Press SPACE to skip.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Get – tck – me. Out.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Take – clk – your time.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Sch – saving… energy…`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ragdoll count`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The clock tower has calmed, for a bit.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `<u>Bug Fixes</u>

-Fixed an issue where players could clip through walls

-Resolved a bug causing incorrect hitbox registration for overhead strikes

-Addressed desync issues in online multiplayer matches

<u>Performance Improvements</u>

-Optimized particle effects for better performance on lower-end systems

-Reduced loading times for all maps by approximately 20%

`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Grab and wiggle your mouse over debris to pull it out!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Running...
Status OK.
Host Terminated Connection.
Connection Lost.
Reason 'KICKED'.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `By maintaining its machinery, you will function normally.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `update available`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `If machines deteriorate, your sense of time slows and you cease.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Fixing machines will restore time. So will stamping rats.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `max dash
`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `We hope everyone had a great GMTK jam this year!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Art Director, Art Lead, Character Designer, 
Enviroment Design, Concept Art, Character Artist,
Texture Artist, Lightning Artist, Enviroment Arist,
Prop Artist, Character Animator, VFX Artist,
Shader Artist, UI/UX Artist`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Director,
Game Designer, System Designer, Level Designer
Multiplayer Designer, Lead Programmer, 
Gameplay Programmer,Network Programmer,
 Sound Designer, Composer,
Build Engineer, Project Manager`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `game by`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SHADOW CASCADES`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `EIGHTH RES`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `FRAMES PER SECOND (FPS)`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `AUDIO ENABLE`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `SHADOW ENABLE`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ANISOTROPIC TEXTURES`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `GAME BY`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Private`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `- min`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `WINNER`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `RectSizeModifier, Game`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Booting up...
Mounting system drive...
Checking system resources...<waitfor=0.1>
Loading configuration files...
Initializing modules...
Scanning for network devices...
Status ERROR...<waitfor=0.2>
Establishing connection...
Calculating checksums...
Synchronizing services...
Status ERROR...<waitfor=0.2>
Updating firmware...
Status ERROR...
Configuring peripherals...
Mounting virtual drives...
Initializing encryption...
Establishing connection to the RYFT...<waitfor=0.2>
Aligning the ley lines...
Scanning for anomalies...
Status ERROR...<waitfor=0.1>
Decrypting the portal framework...
Running diagnostics on the interdimensional gateway...
Status ERROR...
Aligning the quantum frequencies...
Injecting the neural interface...
Status ERROR...
Activating the interstellar beacon...
Probing the datastream...
Status ERROR...
Status ERROR...
Status ERROR...<waitfor=0.2>
Status OK...
Loading UI...`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `This file exists to maintain a .meta file that is used to locate this config folder.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Frames Gained: 0`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Menu Camera Blends`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Game Camera Blends`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `TempleGame PostProccessing`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `CastleGame PostProccessing 1`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PRESS A KEY FOR REPLACE <b>{0}</b>`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Booting up...
Mounting system drive...
Checking system resources...<waitfor=0.1>
Loading configuration files...
Initializing modules...
Scanning for network devices...
Status ERROR.<waitfor=0.2>
Establishing connection...
Calculating checksums...
Synchronizing services...
Status ERROR.<waitfor=0.2>
Updating firmware...
Status ERROR.
Configuring peripherals...
Mounting virtual drives...
Initializing encryption...
Establishing connection to the RYFT...<waitfor=0.2>
Aligning the ley lines...
Scanning for anomalies...
Status ERROR.<waitfor=0.1>
Decrypting the portal framework...
Running diagnostics on the interdimensional gateway...
Status ERROR.
Aligning the quantum frequencies...
Injecting the neural interface...
Status ERROR.
Activating the interstellar beacon...
Probing the datastream...
Status ERROR.
Status ERROR.
Status ERROR.<waitfor=0.2>
Status OK.
Loading UI...`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `A HTTP server error occurred.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The HTTP request timed out.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Something in FMOD hasn't been implemented when it should be! contact support!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[FMOD] Max number of listeners reached : {0}.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `MAX_DEPTH EXCEEDED`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `avg per Sample`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[STUN] Unable to find any valid STUN Server, aborting Reflexive Address query.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[STUN] Only one STUN Server found, skip NAT Type Discovery.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Left Foot BASE UP`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Right Foot BASE UP`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `frm={0} WARN {1}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `====== There are possible problems with these meshes that may prevent them from combining well. TREATMENT SUGGESTIONS (copy and paste to text editor if too big) =====
`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `DEAD / id {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `'. Please check that the LOD Group's Screen Size is within [0-1]`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `This text is <color=orange>animated</color> with <b>zero allocations</b>, see <i>'TypewriterAnimatorExample'</i> script for more details.

PrimeTween rocks!`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[Assert] `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `) for object `（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Could not make generic-type definition '`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The serialization format of the data in specially serialized Unity objects. Binary is recommended for builds; JSON has the benefit of being human-readable but has significantly worse performance.

With the special editor-only node format, the serialized data will be formatted in such a way that, if the asset is saved with Unity's text format (Edit -> Project Settings -> Editor -> Asset Serialization -> Mode), the data will be mergeable when using version control systems. This makes the custom serialized data a lot less fragile, but comes at a performance cost during serialization and deserialization. The node format is recommended in the editor.

This setting can be overridden on a per-instance basis.
`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `' failed due to missing AOT support. 

 Please use Odin's AOT generation feature to generate an AOT dll before building, and MAKE SURE that all of the following types were automatically added to the supported types list after a scan (if they were not, please REPORT AN ISSUE with the details of which exact types the scan is missing and ADD THEM MANUALLY): 

`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Option C`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `wibble`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `- {0}: {1}x{2}, {3} sample(s).`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `- {0}: {1}x{2}, {3} sample(s).
`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Key: {0} is not present in the NativeParallelHashMap.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Number of bits in the NativeBitArray {0} is not sufficient to cast to NativeArray<T> {1}.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Performance level CPU={0}/{1} GPU={2}/{3} thermal warn={4}({5}) thermal level={6} mode={7}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The Enumeration constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The FractionDigits constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The MaxExclusive constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The MaxLength constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The MinExclusive constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The MinInclusive constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The MinLength constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The Pattern constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The TotalDigits constraining facet is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The value of the namespace attribute of the element or attribute wildcard is invalid - {0}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `To fix this error either change the JSON to a {1} or change the deserialized type so that it is a normal .NET type (e.g. not a primitive type like integer, not a collection type like an array or List<T>) that can be deserialized from a JSON object. JsonObjectAttribute can also be added to the type to force it to deserialize from a JSON object.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `To fix this error either change the JSON to a {1} or change the deserialized type to an array or a type that implements a collection interface (e.g. ICollection, IList) like List<T> that can be deserialized from a JSON array. JsonArrayAttribute can also be added to the type to force it to deserialize from a JSON array.`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Web request failed, retrying ({0}/{1})...
{2}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[UI Toolkit] Could not retrieve the value at path '<b>{0}</b>' for source of type '<b>{1}</b>':`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[UI Toolkit] Could not bind target of type '<b>{0}</b>' at path '<b>{1}</b>':`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `[UI Toolkit] Could not set value for target of type '<b>{0}</b>' at path '<b>{1}</b>':`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `exp:{0} completedRequest:{1}`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
