# 经验记忆报告（force-reboot）

经验记忆（AgentMemory）是跨游戏自动学习的离散知识单元：
只沉淀质量门通过且非回显的译文，多次一致证据才晋升 active；
高置信短语在翻译时直接应用（仍过质量门复查），一般置信注入
prompt 参考；被拒绝的记忆降级直至退休。

## 1 本次会话
- 提案：3（新记忆单元首条证据）
- 证据积累：133（已有记忆再次通过质量门）
- 晋升 active：8（≥2 次一致证据）
- 直接应用：0 条（采纳 0 / 拒绝 0）
- 退休：0（被质量门拒绝 ≥2 次，不可信）

## 2 记忆库状态（按类型 × 状态）

- phrase: active 141 · pending 1181

## 3 TOP 记忆（按命中）

| 原文 | 语境 | 译文 | 证据 | 命中 | 拒绝 | 游戏 |
|---|---|---|---|---|---|---|
| EXIT | r:display | 退出 | 5 | 0 | 0 | force-reboot/foxhunt-chapter1 |
| QUIT | r:display | 退出 | 5 | 0 | 0 | force-reboot/foxhunt-chapter1 |
| Standard | — | 标准 | 4 | 0 | 0 | force-reboot |
| Force Reboot | — | 强制重启 | 4 | 0 | 0 | force-reboot |
| POW! | r:display | 砰！ | 4 | 0 | 0 | force-reboot |

## 4 冲突/待复核

- ⚠️ `Function`（语境 `—`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `Layer 4`（语境 `r:display`）出现 3 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
- ⚠️ `To the extent possible under law, Christoph Peters has waived all copyright and`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The work is made available under the terms of the Creative Commons CC0 Public`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `ATTORNEY-CLIENT RELATIONSHIP. CREATIVE COMMONS PROVIDES THIS`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `INFORMATION ON AN "AS-IS" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `PROVIDED HEREUNDER, AND DISCLAIMS LIABILITY FOR DAMAGES RESULTING FROM`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Statement of Purpose`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `The laws of most jurisdictions throughout the world automatically confer`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `exclusive Copyright and Related Rights (defined below) upon the creator`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
- ⚠️ `Certain owners wish to permanently relinquish those rights to a Work for`（语境 `r:display`）出现 1 次不同译文——记忆未采纳新译文，需人工裁决（保留译文或人工术语表强制）
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
