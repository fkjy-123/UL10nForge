# interdream F13 修复前已写回缺陷译文清单（中间版 186 条）

> 生成：2026-08-13 · interdream/DELTATRAVELER 翻译运行中，F13 修复前旧代码写回
> 复验：修复后代码（F13a 对话词对豁免 + F13b 字面 \n 行首 `* ` 保护 + F13c 裸 ^NN 保护）
> 数量：186 条为 **normalized_output 中间自愈态复验**；translation 列
> 最终写回值复验为 **135 条**（120 条 placeholder_mismatch 单因 =
> 对话符 `* `/计时码丢失或移位）。runner 完成后重生成终版。
> 处置：登记人工重译（本游戏特判，不自动回写）——与 incremental-rts F12 4 条同处理

## 拦截原因分布
- `('placeholder_mismatch',)`: 150
- `('line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch')`: 12
- `('line_content_mismatch', 'newline_mismatch')`: 8
- `('untranslated_text',)`: 6
- `('glossary_mismatch',)`: 4
- `('newline_mismatch', 'placeholder_mismatch')`: 2
- `('line_content_mismatch',)`: 1
- `('newline_mismatch', 'untranslated_text')`: 1
- `('input_token_mismatch',)`: 1
- `('placeholder_mismatch', 'untranslated_text')`: 1

## 清单
### 1. asset#level10#172/str/0  ['placeholder_mismatch']
- 原文：'* Only the fearless may proceed.\\n* Brave ones, foolish ones.\\n* Both walk not the middle road.'
- 写回：'只有无畏的人才能继续前进。* \\n勇敢的人，愚蠢的人……\\n他们都不选择中间的道路。'
- translation 列：'* 只有无畏的人才能继续前进。\\n勇敢的人，愚蠢的人。\\n两者都不选择中间的道路。'

### 2. asset#level100#214/str/0  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："* (There's a katana stuck in the\\n  ground.)^05\\n* (Take it?)"
- 写回：'*(有一把刀卡在地面里了。* )^05*\\n*(要拿走它吗？)'
- translation 列：'* 有一把刀卡住了……\\n  地面。)^05\\n*(接受吗？)*'

### 3. asset#level105#177/str/0  ['placeholder_mismatch']
- 原文：'* (A snow poff?)^05\\n* (In these trying times??!)'
- 写回：'*(A snow poff?* )^05\\n* (在这艰难的时刻??!)'
- translation 列：'* （雪球吗？）)^05\\n（在这艰难的时刻里？？！）'

### 4. asset#level105#188/str/1  ['placeholder_mismatch']
- 原文："* The big guy from the guard\\n  won't let me by cuz they're\\n  on high alert."
- 写回：'那个来自警卫队的大个子* \\n不会让我通过，因为他们\\n处于高度警戒状态。'
- translation 列：'* 那个来自警卫队的大个子男人\\n  他们不会让我通过，因为他们是\\n  处于高度警戒状态。'

### 5. asset#level105#188/str/6  ['untranslated_text']
- 原文：'* Wait,^05 ALPHYS?????'
- 写回：'* Wait, ^05 ALPHYS?????'
- translation 列：'*  等等，^05 ALPHYS?????'

### 6. asset#level105#188/str/7  ['placeholder_mismatch']
- 原文：'* Noel,^05 if you know her,^05 can\\n  you tell her to STOP training\\n  the dogs to be killers???'
- 写回：'* 诺埃尔，如果你认识她的话，她应该会……\\n  你告诉她停止训练。\\n  那些狗竟然能成为杀手？？？'

### 7. asset#level107#147/str/1  ['line_content_mismatch']
- 原文：'*\\ti think i saw my\\n\\tdoppelganger for a\\n\\tsplit second.'
- 写回：'*我觉得有那么一瞬间，我看到了我的\\n\\n分身。'

### 8. asset#level109#148/str/0  ['placeholder_mismatch']
- 原文：'* "Holiday Residence\\n* FOR SALE: CONTACT --- ----\\n  FOR INFORMATION"'
- 写回：'“度假住宅* \\n出售中：请联系我们 --- ----\\n如需更多信息”'
- translation 列：'* 假日住宅\\n出售：请联系我们 --- ----\\n  用于信息获取'

### 9. asset#level11#150/str/0  ['placeholder_mismatch']
- 原文：'* Please press this switch.\\n  too.\\n             - TORIEL'
- 写回：'请按下这个开关。* \\n同上。\\n- TORIEL'
- translation 列：'* 请按下这个开关。\\n  也。\\n             - 托里埃尔'

### 10. asset#level11#152/str/0  ['placeholder_mismatch']
- 原文：'* Please press this switch.\\n\\n            - TORIEL'
- 写回：'请按下这个开关。* \\n\\n——TORIEL'
- translation 列：'* 请按下这个开关。\\n\\n            - 托里埃尔'

### 11. asset#level110#110/str/0  ['placeholder_mismatch']
- 原文：'* (A big,^05 dangerous cannon blocks\\n  the way.)'
- 写回：'* 一支巨大的、极其危险的大炮挡住了去路。\\n  那种方式。'

### 12. asset#level110#115/str/5  ['placeholder_mismatch']
- 原文：'SAY,^05 IF YOU CAN \\nBRING ME SOMETHING \\nINTERESTING...'
- 写回：'说吧，如果可以的话。\\n请给我拿点东西来。\\n有趣……'

### 13. asset#level111#334/str/2  ['placeholder_mismatch']
- 原文：'* When I went inside,^05 I showed\\n  up here???'
- 写回：'* 当我进入室内时，我展示了\\n  在这里吗？？？'

### 14. asset#level111#340/str/0  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："* Jester?^10\\n* No,^05 I'm what some may\\n  call a <color=#FF0000FF>demon</color>."
- 写回：'杰斯特？^10* \\n不，^05我其实是那些人所说的<color=#FF0000FF>恶魔</color>。'
- translation 列：'* 小丑？^10\\n不，^05 我就是有些人所说的那种人。\\n  打电话给 <color=#FF0000FF>恶魔</color>.'

### 15. asset#level111#340/str/3  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* Being called JEVIL II by\\n  someone named...^10\\n  <color=#FFFF00FF>something Quetzalcoatl III</color>.'
- 写回：'被名叫……^10的人称为JEVIL II。* <color=#FFFF00FF>那是个Quetzalcoatl III的名字。</color>'
- translation 列：'* 被称为JEVIL II\\n  名叫……^10的人\\n  <color=#FFFF00FF>奎扎尔科阿特三世</color>.'

### 16. asset#level111#340/str/4  ['placeholder_mismatch']
- 原文：'* I forgot what their first\\n  name was...^05\\n* Something with a G?'
- 写回：'我忘了他们的名字是什* \\n么……^05\\n好像有个“G”字样的名字吧？'
- translation 列：'* 我忘了他们的第一个是什么了。\\n  名字是……^05\\n有 G 符号的东西吗？'

### 17. asset#level111#341/str/0  ['placeholder_mismatch']
- 原文：'* What.^10\\n* What?^10\\n* WHAT!?'
- 写回：'什么。^10* \\n什么？^10\\n什么！？'
- translation 列：'* 什么。^10\\n什么？^10\\n什么！？'

### 18. asset#level111#342/str/4  ['placeholder_mismatch']
- 原文："* My little sib' loves Undyne,^05\\n  but they aren't awake yet,^05\\n  haha."
- 写回：'我的小弟弟喜欢Undyne，^05* \\n不过他们现在还没醒来呢，^05\\n哈哈。'
- translation 列：'* 我的小弟弟喜欢Undyne，^05\\n  但他们还没醒来呢，^05\\n  哈哈。'

### 19. asset#level111#342/str/7  ['placeholder_mismatch']
- 原文：'* Oh yeah,^05 my bad.'
- 写回：'* 哦，对啊，我的错。'

### 20. asset#level111#342/str/25  ['placeholder_mismatch']
- 原文："* You're acting real\\n  defensive for someone\\n  with nothing to hide."
- 写回：'你表现得好像* \\n真的很害怕似的，\\n对于一个没有任何事情可隐瞒的人。'
- translation 列：'* 你表现得真不错。\\n  为某人提供防御措施\\n  没有什么好隐瞒的。'

### 21. asset#level111#346/str/3  ['placeholder_mismatch']
- 原文："* Cuz Kris's mom's house\\n  was nothing like it\\n  was back home."
- 写回：'因为克里斯妈妈的房子* \\n和家里完全不一样\\n就像在家里一样。'
- translation 列：'* 因为克里斯妈妈的房子\\n  它根本不是那样的东西。\\n  已经回家了。'

### 22. asset#level111#351/str/0  ['untranslated_text']
- 原文：'* Oh my goodness,^05\\n  Kris???'
- 写回：'* Oh my goodness, ^05\\n  Kris???'
- translation 列：'*  哦，天哪，^05\\n 克里斯？？？'

### 23. asset#level111#361/str/3  ['placeholder_mismatch']
- 原文：'* She had fallen down one day,^05\\n  and a doctor healed her\\n  to health.'
- 写回：'* 有一天，她摔倒了。\\n  并且有一位医生治愈了她。\\n  为了健康。'

### 24. asset#level111#369/str/7  ['placeholder_mismatch']
- 原文：'* Okay,^05 so what if instead\\n  of fighting whoever\\n  these weirdos are...'
- 写回：'* 好吧，那么如果相反的话会怎样呢？\\n  与任何对手战斗\\n  这些怪人真是……'

### 25. asset#level111#369/str/9  ['placeholder_mismatch']
- 原文："* They seem like they'd\\n  be normal enough to\\n  actually TALK to."
- 写回：'他们看起来* \\n足够正常，\\n可以真正进行交谈。'
- translation 列：'* 他们看起来好像会……\\n  足够正常到\\n  实际上，是与之进行对话。'

### 26. asset#level113#171/str/2  ['placeholder_mismatch']
- 原文：'* Came by today to make sure\\n  Ice Wolf was still throwing\\n  Ice to cool the CORE.'
- 写回：'今天特意来确认一下，* \\n冰狼是否仍在持续投掷冰块，\\n以冷却核心区域。'
- translation 列：'* 今天特意来确认一下。\\n  冰狼仍在继续扔东西。\\n  冰来冷却核心区域。'

### 27. asset#level113#171/str/5  ['placeholder_mismatch']
- 原文："* I've gotta say,^05 though.^05\\n* There are more moles out today\\n  than I thought there were here."
- 写回：'* 我得说，不过。\\n今天有更多的痣了。\\n  比我想象的要多。'

### 28. asset#level113#174/str/5  ['placeholder_mismatch']
- 原文：'* Ah,^05 the humans were clever.^05\\n* Clever and cruel.'
- 写回：'* 啊，人类真是聪明啊。\\n聪明而残忍。'

### 29. asset#level113#182/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 30. asset#level113#182/str/8  ['placeholder_mismatch']
- 原文："* Say,^05 I hear there's a strange\\n  scientist near the library."
- 写回：'* 据说，我听说有个奇怪的事情发生了。\\n  图书馆附近的科学家。'

### 31. asset#level115#165/str/9  ['placeholder_mismatch']
- 原文："* She doesn't look too comfy in\\n  here,^05 to be honest."
- 写回：'* 她看起来并不太舒服。\\n  说实话，这里需要 0.5。'

### 32. asset#level115#165/str/10  ['placeholder_mismatch']
- 原文：'* Honestly,^05 I was kind\\n  of curious.'
- 写回：'* 说实话，我其实挺友善的。\\n  很奇怪。'

### 33. asset#level115#170/str/5  ['placeholder_mismatch']
- 原文："* Actually,^05 I heard that the fish\\n  lady pays the dogs's tab."
- 写回：'* 实际上，我听说那种鱼……\\n  女士支付了狗的花费。'

### 34. asset#level115#173/str/2  ['placeholder_mismatch']
- 原文：'* Say...^05 like two hours from\\n  now?'
- 写回：'* 说……大约两小时后吧。\\n  现在？'

### 35. asset#level115#173/str/6  ['placeholder_mismatch']
- 原文："* Actually,^05 I heard that the fish\\n  lady pays the dogs's tab."
- 写回：'* 实际上，我听说那种鱼……\\n  女士支付了狗的花费。'

### 36. asset#level115#175/str/9  ['placeholder_mismatch']
- 原文："* Yeah,^05 I don't blame\\n  you."
- 写回：'* 是的，我不怪你。\\n  你。'

### 37. asset#level115#176/str/12  ['placeholder_mismatch']
- 原文：'* O-okay,^05 there might be a\\n  l-l-l-LITTLE bit of\\n  d-drinking...'
- 写回：'哦，好吧。可能會有* \\n一點點的\\n飲酒行為……'
- translation 列：'* 哦，好吧。^05 可能真的有吧。\\n  一小部分\\n  喝…'

### 38. asset#level115#177/str/5  ['untranslated_text']
- 原文：'* Sorry.'
- 写回：'* Sorry.'
- translation 列：'*  对不起。'

### 39. asset#level116#123/str/2  ['placeholder_mismatch']
- 原文：'* We braved harsh cold,^05 damp\\n  swampland,^05 and searing heat...'
- 写回：'* 我们忍受着严寒和潮湿的天气。\\n  沼泽地，^05以及酷热的温度……'

### 40. asset#level116#124/str/0  ['placeholder_mismatch']
- 原文：'* While monsters are mostly made\\n  of magic,^05 human beings are\\n  mostly made of water.'
- 写回：'* 虽然怪物大多是由各种元素组合而成的\\n  在魔法领域，人类其实并不具备什么特殊能力。\\n  主要由水组成。'

### 41. asset#level116#124/str/6  ['placeholder_mismatch']
- 原文："* Well,^05 this book says\\n  we're made of magic,^05\\n  like back home."
- 写回：'嗯，这本书说* \\n我们是由魔法构成的，\\n就像在故乡一样。'
- translation 列：'* 嗯，这本书上写着：\\n  我们是由魔法构成的，^05\\n  就像回到家乡一样。'

### 42. asset#level116#125/str/0  ['newline_mismatch', 'placeholder_mismatch']
- 原文：'* Love,^05 hope,^05 compassion...^05\\n* This is what people say\\n  monster SOULs are made of.'
- 写回：'爱、希望、同情心……^05\n人们就是这样说的。^05\n怪物们是由这些元素构成的。'
- translation 列：'* 爱、希望、同情心……\\n这是人们所说的话。\\n  怪物们的灵魂就是由这些物质构成的。'

### 43. asset#level116#125/str/2  ['placeholder_mismatch']
- 原文："* After all,^05 humans have proven\\n  their SOULs don't need these\\n  things to exist."
- 写回：'* 毕竟，人类已经证明了这一点。\\n  他们的灵魂不需要这些。\\n  事物需要存在。'

### 44. asset#level116#126/str/1  ['placeholder_mismatch']
- 原文：'* Monster funerals,^05 technically\\n  speaking,^05 are cool as heck.'
- 写回：'* 怪物们的葬礼，^05 从技术上讲\\n  说话的方式真是太棒了。'

### 45. asset#level116#126/str/3  ['placeholder_mismatch']
- 原文："* At funerals,^05 we take that\\n  dust and spread it on that\\n  person's favorite thing."
- 写回：'* 在葬礼上，我们都会这样做。\\n  灰尘，然后将其撒在那上面。\\n  某人最喜欢的东西。'

### 46. asset#level116#127/str/10  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："QUITE THE DELTA-\\nTRAVELLING TRIO,^05 \\nAREN'T YOU?"
- 写回：'QUIT 翻译为 退出'

### 47. asset#level116#127/str/12  ['placeholder_mismatch']
- 原文：'* I mean,^05 we kind of\\n  got caught up in\\n  this.'
- 写回：'* 我的意思是，我们某种程度上……\\n  被卷入其中了\\n  这个。'

### 48. asset#level116#130/str/15  ['placeholder_mismatch']
- 原文：'* Susie,^05 you know that\\n  ours was also misspelled.'
- 写回：'* 苏西，你知道的。\\n  我们的那个也拼错了。'

### 49. asset#level116#133/str/3  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："* Sorry,^05 I'm lost.^05\\n* The hell is this\\n  about?"
- 写回：'对不起，我迷路了。^05\n这到底是什么东西啊？^05'
- translation 列：'* 对不起，我迷路了。\\n这到底是什么鬼东西？\\n  关于什么？'

### 50. asset#level117#106/str/1  ['newline_mismatch', 'placeholder_mismatch']
- 原文：'* "ROYAL SCIENCES LABORATORY\\n  LV 10 CLEARANCE\\n  SANS THE SKELETON"'
- 写回：'“皇家科学实验室”\nLV 10  clearance\n“解剖骷髅”'
- translation 列：'* 皇家科学实验室\\n  LV 10 清除\\n  “打破骷髅”'

### 51. asset#level118#127/str/2  ['placeholder_mismatch']
- 原文：'* For only the most\\n  responsible of beings\\n  in the vicinity.'
- 写回：'仅限那些* \\n最负责任的生物\\n在附近。'
- translation 列：'* 仅限最优秀的那些\\n  负责生物的负责人\\n  在附近。'

### 52. asset#level118#130/str/2  ['placeholder_mismatch']
- 原文：'* Say,^05 who exactly WERE\\n  the two that brought\\n  us here?'
- 写回：'* 比如说，究竟是谁呢？\\n  那两个带来了……\\n  我们在这里吗？'

### 53. asset#level12#156/str/0  ['line_content_mismatch', 'newline_mismatch']
- 原文："* (...?!)\\n* (There's a message written\\n  here.)"
- 写回：'* (...?!)\\n*（这里写着一条消息。）'

### 54. asset#level12#164/str/0  ['placeholder_mismatch']
- 原文："* Honestly dude,^05 you're\\n  missing out on\\n  some info."
- 写回：'* 说实话，兄弟，你真是个……\\n  错过/未能获得\\n  一些信息。'

### 55. asset#level12#165/str/1  ['placeholder_mismatch']
- 原文："* Well,^05 I often start with\\n  a simple 'how do you\\n  do...'"
- 写回：'* 嗯，我通常是从…开始的。\\n  简单的“你是怎么……的？”\\n  做……'

### 56. asset#level121#116/str/9  ['placeholder_mismatch']
- 原文："* They grow in marsh areas,^05\\n  and I think they're\\n  adverse to sunlight...?"
- 写回：'* 它们生长在沼泽地带。\\n  我认为它们就是那样。\\n  与阳光相逆……？'

### 57. asset#level122#216/str/1  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* The royal guard is going to\\n  bring back the rock puzzle\\n  that used to be here.'
- 写回：'皇家卫队即将回那块曾经放在这里的石头拼图。'
- translation 列：'* 皇家卫队即将出发。\\n  还原那块石头拼图\\n  那曾经在这里。'

### 58. asset#level123#107/str/0  ['placeholder_mismatch']
- 原文："* (There's an old,^05 dusty tutu\\n  laying here.)"
- 写回：'* 有一套旧的、积满灰尘的芭蕾舞裙\\n就躺在这里吧。'

### 59. asset#level123#107/str/7  ['placeholder_mismatch']
- 原文：'* Susie,^05 you know that\\n  dust is a natural thing\\n  that happens,^05 right?'
- 写回：'苏西，你知道吧，* \\n灰尘是一种自然现象，\\n它总是会发生，对吧？'
- translation 列：'* 苏西，你知道的吧。\\n  灰尘是一种自然现象\\n  那样的情况确实会发生，对吧？'

### 60. asset#level123#107/str/12  ['placeholder_mismatch']
- 原文：'* Actually,^05 good point.'
- 写回：'* 实际上，这确实是个好观点。'

### 61. asset#level128#339/str/1  ['line_content_mismatch', 'newline_mismatch']
- 原文：'hue\n"hue"\n<color=#FFFFFF80>Animation by\ndramgon_</color>'
- 写回：'“hue”\n<color=#FFFFFF80>动画制作：dramgon_</color>'
- translation 列：'“hue”  \n<color=#FFFFFF80>动画制作：dramgon_</color>'

### 62. asset#level128#366/str/1  ['untranslated_text']
- 原文：'RENREN\nLexiTheTT\nLazyGales\nFrakture\nTygressLongheart\ngabbo\nlex3x\nAutumn / WavePrism\nTheTuneHero\nEribetra\nSawsk'
- 写回：'RENREN\nLexiTheTT\nLazyGales\nFrakture\nTygressLongheart\ngabbo\nlex3x\nAutumn / WavePrism\nTheTuneHero\nEribetra\nSawsk'
- translation 列：'RENREN\nLexiTheTT\nLazyGales\n断裂\nTygressLongheart\n加博\nlex3x\n秋季 / WavePrism\nTheTuneHero\n埃里贝特拉\nSawsk'

### 63. asset#level128#367/str/1  ['newline_mismatch', 'untranslated_text']
- 原文：'TheFlowerVixen\nBeethovenus\r\nYippieTB\nJust a BLU Toon\r\nspider8bytes\r\nCyberCorvid\nLumaHoneyy\nmalloryFireflies\r\nparfae\r\ntubba\njevilhumor\r\nShaunt / SeanTG246\r\nasukaaa\nOcto\nsugariimarii\nValor52\nAutumn / WavePrism'
- 写回：'TheFlowerVixen\nBeethovenus\nYippieTB\nJust a BLU Toon\nspider8bytes\nCyberCorvid\nLumaHoneyy\nmalloryFireflies\nparfae\ntubba\njevilhumor\nShaunt / SeanTG246\nasukaaa\nOcto\nsugariimarii\nValor52\nAutumn / WavePrism'
- translation 列：'TheFlowerVixen\n贝多芬\r\nYippieTB\n只是个BLU Toon而已\r\nspider8bytes\r\nCyberCorvid\nLumaHoneyy\nmalloryFireflies\r\n帕尔法埃\r\ntubba\n坏心情\r\nShaunt / SeanTG246\r\nasukaaa\n八\nsugariimarii\nValor52\n秋季 / WavePrism'

### 64. asset#level128#370/str/1  ['line_content_mismatch', 'newline_mismatch']
- 原文：'Sarah Mullins\ncippbone\nCyberCorvid\nLumaHoneyy\njevilhumor\nShaunt\r / SeanTG246\nTheTuneHero\r\nHUECYCLES\r\nA Sick-Ass Werewolf\nLuneyToons\nAutumn / WavePrism\nThe Winterer\nValor52'
- 写回：'莎拉·穆林斯\n西普邦恩\nCyberCorvid\nLumaHoneyy\njevilhumor\nShaunt / SeanTG246\nTheTuneHero\nHUECYCLES\nA Sick-Ass Werewolf\nLuneyToons\nAutumn / WavePrism\nThe Winterer\nValor52'
- translation 列：'莎拉·穆林斯\ncippbone\nCyberCorvid\nLumaHoneyy\n坏心情\n沙恩特\r/ SeanTG246\nTheTuneHero\r\nHUECYCLES\r\n一个生病的小狼人\nLuneyToons\n秋天 / 波浪棱镜\n温特勒\nValor52'

### 65. asset#level130#109/str/0  ['placeholder_mismatch']
- 原文："* (There's an old,^05 dusty tutu\\n  laying here.)"
- 写回：'* 有一套旧的、积满灰尘的芭蕾舞裙\\n就躺在这里吧。'

### 66. asset#level130#109/str/8  ['placeholder_mismatch']
- 原文：'* Susie,^05 you know that\\n  dust is a natural thing\\n  that happens,^05 right?'
- 写回：'* 苏西，你知道的吧。\\n  灰尘是一种自然现象\\n  那样的情况确实会发生，对吧？'

### 67. asset#level130#109/str/13  ['placeholder_mismatch']
- 原文：'* Actually,^05 good point.'
- 写回：'* 实际上，这确实是个好观点。'

### 68. asset#level15#137/str/5  ['placeholder_mismatch']
- 原文：'* (Use some <color=#FFFF00FF>MERCY,</color>^10 human.)^10\\n* Ribbit.'
- 写回：'*（请拿出一些* <color=#FFFF00FF>怜悯之心，</color>^10人类啊。)^10\\n* 开始吧。'
- translation 列：'* 使用一些 <color=#FFFF00FF>怜悯，</color>^10 人。)^10\\n嗨。'

### 69. asset#level15#137/str/16  ['placeholder_mismatch']
- 原文：'* (The human might want to\\n  fight <color=#FFFF00FF>you</color>,^05 next.)'
- 写回：'（这个人可能想要* \\n与<color=#FFFF00FF>你</color>战斗，^05接下来。）'
- translation 列：'* (这个人可能想要)\\n  战斗 <color=#FFFF00FF>你</color>，^05 接下来。）'

### 70. asset#level2#643/str/1  ['line_content_mismatch', 'newline_mismatch']
- 原文：'@SARAH\nREWRITE THE FUCKING BATTLE\nSYSTEM IT SUCKS DICK\n'
- 写回：'@SARAH\n快重新设计一下这该死的战斗系统吧！这系统真是烂透了。\n'
- translation 列：'@SARAH\n重新编写这该死的战斗流程。\n这系统真是糟糕透顶。\n'

### 71. asset#level23#97/str/1  ['glossary_mismatch']
- 原文：'* "Spider Donuts - 7G"\\n* Leave 7G in the web?'
- 写回：'* 蜘蛛甜甜圈 – 7G\\n将 7G 留在网页上吗？'

### 72. asset#level23#97/str/5  ['placeholder_mismatch']
- 原文：'* Why are there spiders\\n  selling stuff,^05 anyway?'
- 写回：'* 为什么会有蜘蛛呢？\\n  卖东西，反正也是这样的吧？'

### 73. asset#level23#98/str/0  ['line_content_mismatch', 'newline_mismatch']
- 原文：'* Spider Bake Sale^10\\n* All proceeds go to real\\n  spiders.'
- 写回：'* 蜘蛛义卖活动^10\\n* 所有收入将捐赠给真正的蜘蛛。'

### 74. asset#level23#99/str/1  ['glossary_mismatch']
- 原文：'* "Spider Cider - 18G"\\n* Leave 18G in the web?'
- 写回：'* 蜘蛛苹果酒 – 18克\\n将 18G 留在网页上吗？'

### 75. asset#level23#99/str/5  ['placeholder_mismatch']
- 原文：'* Why are there spiders\\n  selling stuff,^05 anyway?'
- 写回：'* 为什么会有蜘蛛呢？\\n  卖东西，反正也是这样的吧？'

### 76. asset#level24#127/str/1  ['placeholder_mismatch']
- 原文：'* Come eat food made by\\n  spiders,^10 for spiders,\\n  ^10of spiders!'
- 写回：'* 来吃由我们制作的食品吧。\\n  蜘蛛，^10 关于蜘蛛的。\\n  10%的蜘蛛！'

### 77. asset#level24#127/str/8  ['placeholder_mismatch']
- 原文：'* Come eat food made by\\n  spiders,^10 for spiders,\\n  ^10of spiders!'
- 写回：'* 来吃由我们制作的食品吧。\\n  蜘蛛，^10 关于蜘蛛的。\\n  10%的蜘蛛！'

### 78. asset#level25#198/str/0  ['placeholder_mismatch']
- 原文："* It's an old,^10 faded ribbon.\\n* Pick it up?"
- 写回：'* 这是一条旧的、颜色褪色的丝带。\\n把它拿起来？'

### 79. asset#level26#133/str/0  ['line_content_mismatch', 'newline_mismatch']
- 原文：'* The far door is not an exit.\\n* It simply marks a rotation\\n  in perspective.'
- 写回：'* 那扇远离中心的门并非出口。\\n* 它只是用来标记旋转方向而已。'

### 80. asset#level32#95/str/0  ['placeholder_mismatch']
- 原文：'* Ribbit,^10 ribbit.\\n^10* (Ooh,^10 are you two Kris\\n  and Susie?)'
- 写回：'* Ribbit, ^10 ribbit.\\n^10*（哦，你们俩是Kris吧？）\\n  还有苏西呢？'

### 81. asset#level32#95/str/2  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* Ribbit,^10 ribbit.\\n^10* (<color=#0000FFFF>TORIEL</color> has been talking about\\n  you two a lot.)'
- 写回：'嗨，^10 嗨。* \\n^10*（<color=#0000FFFF>托里尔</color>一直在谈论你们俩。）'
- translation 列：'* Ribbit, ^10 ribbit.\\n^10* (<color=#0000FFFF>TORIEL</color> 一直在谈论\\n  你们俩经常见面吧。'

### 82. asset#level34#176/str/0  ['placeholder_mismatch']
- 原文："* Kris,^10 we should at\\n  least check out the\\n  surprise,^05 y'know?"
- 写回：'* Kris，^10 我们真的应该这么做。\\n  至少先检查一下。\\n  惊喜，你知道的吧？'

### 83. asset#level36#107/str/1  ['placeholder_mismatch']
- 原文：'* "Typha" - A group of wetland\\n  flowering plants with\\n  brown,^10 oblong seedpods.'
- 写回：'* “Typha” – 一组湿地植物\\n  开花植物，具有\\n  棕色，呈长圆形种子荚状。'

### 84. asset#level36#114/str/2  ['placeholder_mismatch']
- 原文：'* (You find this alternate\\n  universe interpretation of\\n  Chairiel to be underwhelming.)'
- 写回：'(你认为这种对* \\nChairiel的替代性\\n解释并不令人满意。)'
- translation 列：'* 您会发现这种替代方式\\n  宇宙的诠释\\n  Chairiel的表现将会不尽如人意。'

### 85. asset#level37#152/str/0  ['placeholder_mismatch']
- 原文：'* You found the <color=#00FF00FF>[MOSS]</color>!'
- 写回：'你找到了 * <color=#00FF00FF>[MOSS]</color>！'
- translation 列：'* 您找到了 <color=#00FF00FF>[MOSS]</color>!'

### 86. asset#level37#153/str/0  ['placeholder_mismatch']
- 原文：'* (Every time this old tree\\n  grows any leaves,^10 they fall\\n  right off.)'
- 写回：'* 每次这棵老树都……\\n  它们会长出任何种类的叶子，不过这些叶子最终都会掉落。\\n  立刻。'

### 87. asset#level4#198/str/2  ['placeholder_mismatch']
- 原文：'* Talking to^20 ME????'
- 写回：'* 和^20 ME说话？？？'

### 88. asset#level4#200/str/0  ['placeholder_mismatch']
- 原文：'* Well,^10 hello there,\\n  Kris!'
- 写回：'* 嗯，你好。\\n  克里斯！'

### 89. asset#level4#200/str/1  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* I do believe that a\\n  strange human named <color=#FFFF00FF>Sarah</color>\\n  removed <color=#FFFF00FF>Player Pronouns</color>.'
- 写回：'我确实相信，一个名叫 * <color=#FFFF00FF>Sarah</color>的奇怪人类删除了 <color=#FFFF00FF>玩家代词</color>。'
- translation 列：'* 我确实认为，一个\\n  名叫奇怪的人类 <color=#FFFF00FF>莎拉</color>\\n  已移除 <color=#FFFF00FF>玩家代词</color>.'

### 90. asset#level4#203/str/1  ['placeholder_mismatch']
- 原文：'* Want a free test item?\\n\\n         Yes         No'
- 写回：'想要免费测试项吗？* \\n\\n是         否'
- translation 列：'* 想要免费测试项吗？\\n\\n         是         否'

### 91. asset#level4#210/str/13  ['placeholder_mismatch']
- 原文：'* A^02h^02h^02.^02.^02.^10\\n* Battle text...^05\\n* A very crinkly sound.'
- 写回：'A^02h^02h^02.^02.^02.^10* \\n战斗文本……^05\\n一种非常沙哑的声音。'
- translation 列：'* A^02h^02h^02.^02.^02.^10\\n战斗文本……^05\\n一种非常沙哑的声音。'

### 92. asset#level4#211/str/0  ['placeholder_mismatch']
- 原文："* If you touch that really\\n  big red rabbit^05, you'll die."
- 写回：'* 如果你真的触碰那个的话……\\n  大红兔子^05，你会死的。'

### 93. asset#level4#218/str/1  ['input_token_mismatch']
- 原文：'$ - 1G\nSPACE - 1/8'
- 写回：'$-1G$\n空间 – 1/8'
- translation 列：'$-1G\nSPACE - 1/8'

### 94. asset#level5#199/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 95. asset#level5#209/str/0  ['placeholder_mismatch']
- 原文：'* You wanna GO???\\n\\n         Hell yea    NO!!!!!'
- 写回：'你真的想走吗？？？* \\n\\n拜托了，不！！！'
- translation 列：'* 你想去吗？？？\\n\\n         绝对不行！！！'

### 96. asset#level53#982/str/20  ['placeholder_mismatch']
- 原文："* Oh... ^10you don't have enough\\n  money."
- 写回：'* 哦……你拥有的数量不够啊。\\n  钱。'

### 97. asset#level53#1099/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 98. asset#level53#1099/str/12  ['placeholder_mismatch']
- 原文："* Of course,^05 if you choose to\\n  defeat them,^05 then don't worry\\n  about that stuff."
- 写回：'当然，如果你选择* \\n打败他们，\\n那就不用担心那些事情了。'
- translation 列：'* 当然，如果你愿意的话。\\n  打败他们吧，^05 然后就不用担心了。\\n  关于那些事情。'

### 99. asset#level54#186/str/0  ['untranslated_text']
- 原文：'* (Happy-Happy Village ahead.)'
- 写回：'* （Happy-Happy Village ahead.)'
- translation 列：'*  （快乐村在前方。）'

### 100. asset#level54#191/str/9  ['line_content_mismatch', 'newline_mismatch']
- 原文：'* W-what???^10\\n* But I thought my gimmick was\\n  unique!!!'
- 写回：'* 什么？？？^10\\n* 但我以为我的特技很独特啊！！！'

### 101. asset#level56#508/str/1  ['placeholder_mismatch']
- 原文：'* We <color=#FF0000FF>kidnapped Paula</color>.'
- 写回：'我们* <color=#FF0000FF>绑架了 Paula</color>。'
- translation 列：'* 我们 <color=#FF0000FF>绑架了 Paula</color>.'

### 102. asset#level56#508/str/2  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："* She's hidden in the <color=#FFFF00FF>mountain\\n  cabin</color>,^05 you know."
- 写回：'她躲在了* <color=#FFFF00FF>山间小屋</color>里，你知道的。'
- translation 列：'* 她躲藏在……里。 <color=#FFFF00FF>山\\n  小屋</color>^05，你知道的。'

### 103. asset#level56#508/str/5  ['placeholder_mismatch']
- 原文：'* Y-^05you know I was joking,^05\\n  right???'
- 写回：'* 嘿嘿嘿...^10\\n 对吧???'

### 104. asset#level56#508/str/11  ['placeholder_mismatch']
- 原文：'* I think I saw\\n  a cave entrance\\n  down there.'
- 写回：'我觉得我看到了* \\n一个洞穴入口\\n在那下面。'
- translation 列：'* 我觉得我好像看到了\\n  洞穴入口\\n  在下面。'

### 105. asset#level56#520/str/14  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 106. asset#level56#520/str/15  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 107. asset#level56#521/str/8  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 108. asset#level56#521/str/9  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 109. asset#level56#529/str/0  ['placeholder_mismatch']
- 原文："* (I'm just a plain ol' cow,^05\\n  but Mr. Carpainter's messages\\n  always mo^02o^02o^02o^02ve me.)"
- 写回：'(我不过是一头普通的牛而已，^05* \\n但Carpainter先生的消息\\n总是让我兴奋不已。）'
- translation 列：'* 我不过就是一头普通的牛而已，^05\\n  但卡皮纳特先生的消息\\n  总是让我等待。）'

### 110. asset#level56#534/str/10  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 111. asset#level56#534/str/11  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 112. asset#level56#573/str/0  ['placeholder_mismatch']
- 原文：'* When I painted everything\\n  blue,^05 as Mr. Carpainter said,^05\\n  my wife returned home!'
- 写回：'* 当我把一切都涂好之后\\n  蓝色，正如Carpainter先生所说。\\n  我的妻子回家了！'

### 113. asset#level56#573/str/7  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 114. asset#level56#573/str/8  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 115. asset#level56#577/str/2  ['placeholder_mismatch']
- 原文："* Really?\\n^05* Sounds to me like you're\\n  opposed to peace."
- 写回：'真的吗？* \\n^05*在我看来，你似乎\\n反对和平。'
- translation 列：'* 真的吗？\\n^05* 在我看来，你似乎是在说……\\n  与和平背道而驰。'

### 116. asset#level56#577/str/14  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 117. asset#level56#577/str/15  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 118. asset#level56#585/str/14  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 119. asset#level56#585/str/15  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 120. asset#level56#587/str/9  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 121. asset#level56#587/str/10  ['placeholder_mismatch']
- 原文："* You aren't doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做这件事。\\n  牺牲，对吧？'

### 122. asset#level56#608/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 123. asset#level59#125/str/1  ['placeholder_mismatch']
- 原文：'* Painted blue,^05 of course.'
- 写回：'* 当然是涂成蓝色的。'

### 124. asset#level59#126/str/0  ['placeholder_mismatch']
- 原文：'* I could explain what the\\n  <color=#FFFF00FF>hospital system</color> is about...'
- 写回：'我可以解释一下* \\n<color=#FFFF00FF>医院系统</color>是什么……'
- translation 列：'* 我可以解释一下什么是\\n  <color=#FFFF00FF>医院系统</color> 是关于……'

### 125. asset#level59#126/str/2  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* Yeah...^05 something about you\\n  screams "autoheal when\\n  knocked out..."'
- 写回：'是啊……关于你的一些事情。\n似乎还有“被击倒时会自动恢复”这样的描述……'
- translation 列：'* 嗯……关于你，有一些事情需要说明一下。\\n  发出“自动恢复”的提示音时\\n  “昏倒了……”'

### 126. asset#level59#126/str/12  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 127. asset#level59#126/str/13  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 128. asset#level59#129/str/6  ['placeholder_mismatch']
- 原文："* Dude,^05 if you're doing\\n  stuff like sacrifices,^05\\n  you're in a cult."
- 写回：'* 兄弟，如果你真的这么想的话……\\n  诸如献祭之类的东西，^05\\n  你属于某个邪教组织。'

### 129. asset#level59#129/str/7  ['placeholder_mismatch']
- 原文："* You aren't doing doing\\n  sacrifices,^05 right?"
- 写回：'* 你并没有做任何事情。\\n  牺牲，对吧？'

### 130. asset#level69#144/str/0  ['untranslated_text']
- 原文：'* puter'
- 写回：'* puter'
- translation 列：'*  电脑'

### 131. asset#level7#129/str/7  ['placeholder_mismatch']
- 原文："* ...^05 Yeah,^05 you're right.^05\\n* We should probably\\n  get going."
- 写回：'……^05 是的，^05 你说得对。^05* \\n我们或许应该\\n出发了。'
- translation 列：'* ……^05 是的，^05 你说得对。^05\\n我们或许应该……\\n  开始吧。'

### 132. asset#level72#116/str/5  ['placeholder_mismatch']
- 原文：'* Okay,^05 did we end\\n  up in the crazy\\n  dimension or something?'
- 写回：'* 好的，我们结束了吗？\\n  陷入疯狂状态\\n  维度或什么？'

### 133. asset#level75#135/str/0  ['placeholder_mismatch']
- 原文：'* We Live\\n* We Love\\n* We lie'
- 写回：'我们生活着* \\n我们相爱着\\n我们撒谎着'
- translation 列：'* 我们生活\\n我们爱你们\\n我们撒谎。'

### 134. asset#level75#138/str/1  ['placeholder_mismatch']
- 原文：'* "For whoever may stumble\\n  upon this warning,^05 beware\\n  of the woods\' beasts.'
- 写回：'* 无论谁都可能遇到挫折\\n  听到这个警告后，请务必小心。\\n  森林里的野兽们。'

### 135. asset#level75#138/str/38  ['placeholder_mismatch']
- 原文：'* "For whoever may stumble\\n  upon this warning,^05 beware\\n  of the woods\' beasts.'
- 写回：'* 无论谁都可能遇到挫折\\n  听到这个警告后，请务必小心。\\n  森林里的野兽们。'

### 136. asset#level76#192/str/0  ['placeholder_mismatch']
- 原文：'* ...!?\\n* There\'s a camera behind the...\\n  "sentry station."'
- 写回：'……！？* \\n在……后面有一台摄像机。\\n“哨兵站”那里。'
- translation 列：'* ...!?\\n在……的后面有一个摄像头。\\n  “哨所。”'

### 137. asset#level79#121/str/1  ['placeholder_mismatch']
- 原文："* ...^05 Is there anything\\n  that doesn't sound lame\\n  to smoke...?"
- 写回：'……^05 有没有什么* \\n不会听起来很糟糕的\\n抽烟方式呢……？'
- translation 列：'* …^05 有什么问题吗？\\n  那听起来并不糟糕。\\n  吸烟……？'

### 138. asset#level79#121/str/15  ['line_content_mismatch', 'newline_mismatch']
- 原文："* No!!!^05\\n* You can't even smoke\\n  them!"
- 写回：'* 不！！！^05\\n* 你甚至都不能抽烟来熏它们！'

### 139. asset#level80#156/str/3  ['placeholder_mismatch']
- 原文：'*\\twell,^05 maybe you should\\n\\tknow about some special\\n\\tattacks.'
- 写回：'嗯，也许你该这么做吧。\\n了解一些特殊的情况/知识\\n攻击。'

### 140. asset#level80#156/str/8  ['placeholder_mismatch']
- 原文：'*\\tsimple,^05 right?^10\\n*\\twhen fighting,^05 think\\n\\tabout <color=#FFFF00FF>blue stop signs</color>.'
- 写回：'*\\t简单吧，对吗？\\n*\\t在战斗时，^05 请考虑一下。\\n\\t关于 <color=#FFFF00FF>蓝色停车标志</color>.'

### 141. asset#level80#156/str/11  ['placeholder_mismatch']
- 原文：'*\\twell,^05 for <color=#FCA600FF>orange attacks</color>,^05\\n\\tthink of that <color=#FF0000FF>stop sign</color>\\n\\tagain.'
- 写回：'*\\t嗯，对于<color=#FCA600FF>橙色攻击</color>，^05\\n\\t想想那个<color=#FF0000FF>停止标志</color>\\n\\继续前进。'

### 142. asset#level82#405/str/1  ['placeholder_mismatch']
- 原文："* Umm...^10 Noelle's fine."
- 写回：'* 嗯……诺埃尔没事的。'

### 143. asset#level82#405/str/2  ['placeholder_mismatch']
- 原文："* But these two bozos\\n  won't let us through\\n  without you."
- 写回：'但这两个笨蛋* \\n不会让我们通过\\n没有你不行。'
- translation 列：'* 但这两个笨蛋\\n  不会让我们通过\\n  没有你。'

### 144. asset#level82#405/str/7  ['placeholder_mismatch']
- 原文："* (Can't really keep going\\n  like this nonstop,^05\\n  right?)"
- 写回：'无法继续这样下去了* \\n 不能一直这样下去吧，^05\\n 对吗？'
- translation 列：'* (实在无法继续了)\\n  就这样持续下去，^05\\n  对吧？'

### 145. asset#level83#392/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 146. asset#level83#392/str/9  ['placeholder_mismatch']
- 原文："* That's because they're <color=#FF0000FF>HOSTILE</color>!"
- 写回：'那是因为它们* <color=#FF0000FF>具有敌意</color>！'
- translation 列：'* 这是因为它们是 <color=#FF0000FF>敌对</color>!'

### 147. asset#level83#392/str/10  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文："* When they're <color=#FF0000FF>HOSTILE</color>,^05 they\\n  won't even consider mercy\\n  until you calm them down."
- 写回：'当它们处于* <color=#FF0000FF>敌对状态</color>时，^05它们甚至不会考虑给予怜悯，\\n直到你让他们冷静下来为止。'
- translation 列：'* 当他们……时 <color=#FF0000FF>敌对</color>^05 他们\\n  甚至不会考虑给予怜悯\\n  直到你让他们平静下来为止。'

### 148. asset#level83#392/str/14  ['placeholder_mismatch']
- 原文：'* That being said,^05 if a hostile\\n  enemy is <color=#00A2E8FF>TIRED</color>,^05 you can still\\n  make it fall asleep.'
- 写回：'* 话虽如此，如果对方是敌对方的话\\n  敌人是 <color=#00A2E8FF>累了</color>^05，你仍然可以。\\n  让它入睡吧。'

### 149. asset#level84#158/str/3  ['placeholder_mismatch']
- 原文：'* Weird Smell - Humans\\n  <color=#FF0000FF>GREEN</color> Rating\\n  Destroy at all costs!'
- 写回：'奇怪的气味——人类* \\n<color=#FF0000FF>绿色</color>评分\\n不惜一切代价摧毁它！'
- translation 列：'* 奇怪的气味——人类\\n  <color=#FF0000FF>绿色</color> 评级\\n  不惜一切代价摧毁它！'

### 150. asset#level84#158/str/5  ['placeholder_mismatch']
- 原文：'* Okay,^05 so what if instead\\n  of fighting whoever\\n  these weirdos are...'
- 写回：'* 好吧，那么如果相反的话会怎样呢？\\n  与任何对手战斗\\n  这些怪人真是……'

### 151. asset#level87#562/str/0  ['placeholder_mismatch']
- 原文：'* I said RIGHT,^05 not\\n  LEFT!!!'
- 写回：'* 我说的是“对”，而不是“SAI”。\\n  左侧！！！'

### 152. asset#level87#562/str/2  ['placeholder_mismatch']
- 原文：'* Just...^05 go back and\\n  do what you did,^05\\n  but the <color=#FFFF00FF>other way</color>.'
- 写回：'就……^05回去，* \\n做你之前做过的事情吧，^05\\n不过，是那种<color=#FFFF00FF>另一种方式</color>。'
- translation 列：'* 就……^05回去吧。\\n  做你该做的事吧，^05\\n  但是 <color=#FFFF00FF>其他方式</color>.'

### 153. asset#level88#151/str/2  ['placeholder_mismatch']
- 原文："* What if there's a\\n  MONSTER under the bed!!!^05\\n* Let's NOT!!!"
- 写回：'如果床底下有* \\n怪物怎么办！！！^05\\n我们还是不要这么做吧！！！'
- translation 列：'* 如果有什么事情发生的话呢？\\n  床底下有怪物！！！^05\\n我们不要这样做！！！'

### 154. asset#level88#151/str/10  ['placeholder_mismatch', 'untranslated_text']
- 原文：'* Kris,^05 neither me nor\\n  Susie want to sleep for\\n  only two minutes.'
- 写回：'Kris,^05 Neither I nor* \\nSusie want to sleep for\\nonly two minutes.'
- translation 列：'* Kris，^05 我和我都不愿意。\\n  苏西想睡觉了。\\n  只有两分钟。'

### 155. asset#level88#154/str/2  ['placeholder_mismatch']
- 原文："* Yeah,^05 Kris,^05 why don't\\n  we just get something\\n  from uh..."
- 写回：'* 是的，Kris，为什么不行呢？\\n  我们刚刚得到了一些东西。\\n  从……'

### 156. asset#level88#154/str/15  ['placeholder_mismatch']
- 原文："* Then if there's a\\n  really weird jokey one,^05\\n  that'd be like..."
- 写回：'那么，如果有一个* \\n非常奇怪的幽默笑话的话，^05\\n那就会像……'
- translation 列：'* 那么，如果有的话……\\n  真是奇怪的笑话啊，^05\\n  那大概就是……'

### 157. asset#level89#361/str/3  ['placeholder_mismatch']
- 原文：'* "This was the only time the\\n  Royal Guard was given a direct\\n  order of violence by the king."'
- 写回：'“这是唯一一次* \\n皇家卫队得到国王的直接\\n命令使用暴力。”'
- translation 列：'* 这是唯一一次……\\n  皇家卫队获得了直接授权。\\n  国王所发布的暴力命令。'

### 158. asset#level91#175/str/2  ['placeholder_mismatch']
- 原文："* Well,^05 why don't we\\n  find out what to\\n  do ourselves?"
- 写回：'* 嗯，为什么我们不呢？\\n  查明该做什么\\n  我们自己来做吗？'

### 159. asset#level91#175/str/11  ['placeholder_mismatch']
- 原文："* Y'know...^05\\n* Why don't we just\\n  step over the spikes?"
- 写回：'你知道的……^05* \\n我们为什么不干脆\\n跳过那些尖刺呢？'
- translation 列：'* 你知道的……^05\\n我们为什么不就…\\n  跨过那些尖刺吗？'

### 160. asset#level91#175/str/12  ['placeholder_mismatch']
- 原文：'* What if they r-^05raise\\n  higher...'
- 写回：'* 如果他们真的这么做了怎么办？\\n  更高……'

### 161. asset#level93#291/str/21  ['placeholder_mismatch']
- 原文：'WELL,^05 I AM UNSURE \\nOF IF THIS PUZZLE \\nIS DEADLY OR NOT.'
- 写回：'嗯，我不确定。\\n如果这是这个谜题的话\\n是否致命。'

### 162. asset#level93#291/str/25  ['placeholder_mismatch']
- 原文：'* (The hell is so\\n  respectable about\\n  killing things???)'
- 写回：'（到底为什么* \\n杀死生物这种行为\\n会被认为是有价值的呢？）'
- translation 列：'* (这到底是什么鬼东西啊)\\n  值得尊敬\\n  杀死东西？？）'

### 163. asset#level93#292/str/11  ['placeholder_mismatch']
- 原文：'* Okay,^05 so what if instead\\n  of fighting whoever\\n  these weirdos are...'
- 写回：'* 好吧，那么如果相反的话会怎样呢？\\n  与任何对手战斗\\n  这些怪人真是……'

### 164. asset#level94#384/str/0  ['placeholder_mismatch']
- 原文：'* Kris,^05 do you think\\n  you can eat the\\n  orange tiles?'
- 写回：'* Kris，你觉得呢？\\n  你可以吃它。\\n  橙色瓷砖？'

### 165. asset#level94#384/str/19  ['placeholder_mismatch']
- 原文："* You're smart,^05 right?"
- 写回：'* 你很聪明，对吧？'

### 166. asset#level95#151/str/5  ['placeholder_mismatch']
- 原文："* He's uhhhhhh^05 not\\n  important."
- 写回：'* 他呃……^05不是\\n  重要。'

### 167. asset#level95#154/str/3  ['placeholder_mismatch']
- 原文："* Wait,^05 you're right,^05\\n  what the hell?"
- 写回：'* 等等，你是对的。\\n  到底怎么回事？'

### 168. asset#level95#160/str/7  ['placeholder_mismatch']
- 原文：'* Okay,^05 so what if instead\\n  of fighting whoever\\n  these weirdos are...'
- 写回：'* 好吧，那么如果相反的话会怎样呢？\\n  与任何对手战斗\\n  这些怪人真是……'

### 169. asset#level95#169/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 170. asset#level95#169/str/8  ['placeholder_mismatch']
- 原文："* Say,^05 if you're feeling a bit\\n  tired,^05 why not take a break?"
- 写回：'* 比如说，如果你感觉有点不舒服的话。\\n  累了，^05 为什么不休息一下呢？'

### 171. asset#level97#107/str/1  ['placeholder_mismatch']
- 原文：'* (Alas,^05 poor Papyrus...)'
- 写回：'* （唉，可怜的纸莎草文献啊……）'

### 172. asset#level98#136/str/9  ['placeholder_mismatch']
- 原文：'* Then why does he\\n  force us to do\\n  dangerous puzzles?'
- 写回：'那他为什么还要* \\n强迫我们去做\\n那些危险的谜题呢？'
- translation 列：'* 那么，他为什么呢？\\n  迫使我们去做\\n  危险的谜题？'

### 173. asset#level99#114/str/0  ['placeholder_mismatch']
- 原文：'* Oh me,^05 oh my!^10\\n* Did I miss him?'
- 写回：'* 哦，我的天啊！^10\\n我错过他了吗？'

### 174. asset#level99#114/str/9  ['placeholder_mismatch']
- 原文：'* Oh me,^05 oh my!^10\\n* Did I miss him?'
- 写回：'* 哦，我的天啊！^10\\n我错过他了吗？'

### 175. asset#level99#114/str/10  ['placeholder_mismatch']
- 原文：'* Uhhhhhhhhhh^20\\n* Who?'
- 写回：'* 呃……^20\\n* 谁？'

### 176. asset#level99#120/str/0  ['placeholder_mismatch']
- 原文：'* (In the distance,^05 you can see\\n  a small house down below,^05\\n  much like the bunny house.)'
- 写回：'在远处，你可以看到* \\n一座小房子，位于下方，\\n就像兔子屋一样。'
- translation 列：'* 在远处，你可以看到\\n  楼下有一间小房子，^05\\n  就像兔子屋一样。'

### 177. asset#resources.assets#34676/str/1  ['glossary_mismatch']
- 原文：'ITEM'
- 写回：'商品/项目'

### 178. asset#resources.assets#34734/str/0  ['placeholder_mismatch']
- 原文："* Ribbit,^10 ribbit.\\n^10* (I hope you two aren't\\n  stepping on the leaves.)"
- 写回：'嗨，^10 嗨。* \\n^10*（希望你们两个不要\\n踩到叶子。）'
- translation 列：'* Ribbit, ^10 ribbit.\\n^10*（希望你们俩不会这样）\\n  踩到叶子了。）'

### 179. asset#resources.assets#34815/str/1  ['line_content_mismatch', 'newline_mismatch', 'placeholder_mismatch']
- 原文：'* They\'re not into the "<color=#FFFF00>Devour</color>"\\n  ACT.'
- 写回：'他们并不喜欢“* <color=#FFFF00>Devour</color>”这一环节。'
- translation 列：'* 他们并不感兴趣于“<color=#FFFF00>吞噬</color>"\\n  行动。'

### 180. asset#resources.assets#34966/str/2  ['placeholder_mismatch']
- 原文：'* Are we seriously gonna\\n  fight right here,^05\\n  right now?'
- 写回：'我们真的要* \\n在这里打架吗，^05\\n现在吗？'
- translation 列：'* 我们真的要这么做吗？\\n  就在这里战斗，^05\\n  现在吗？'

### 181. asset#resources.assets#35002/str/2  ['placeholder_mismatch']
- 原文：'* Hello,^05 traveller.\n* How can I help you?'
- 写回：'你好，^05 旅客。\n我能为您做些什么呢？'
- translation 列：'* 你好，^05旅行者。\n* 我能帮您什么忙吗？'

### 182. asset#resources.assets#35447/str/3  ['placeholder_mismatch']
- 原文：'*\\twell,^05 maybe you should\\n\\tknow about some special\\n\\tattacks.'
- 写回：'嗯，也许你该这么做吧。\\n了解一些特殊的情况/知识\\n攻击。'

### 183. asset#resources.assets#35447/str/8  ['placeholder_mismatch']
- 原文：'*\\tsimple,^05 right?^10\\n*\\twhen fighting,^05 think\\n\\tabout <color=#FFFF00FF>blue stop signs</color>.'
- 写回：'*\\t简单吧，对吗？\\n*\\t在战斗时，^05 请考虑一下。\\n\\t关于 <color=#FFFF00FF>蓝色停车标志</color>.'

### 184. asset#resources.assets#35447/str/11  ['placeholder_mismatch']
- 原文：'*\\twell,^05 for <color=#FCA600FF>orange attacks</color>,^05\\n\\tthink of that <color=#FF0000FF>stop sign</color>\\n\\tagain.'
- 写回：'*\\t嗯，对于<color=#FCA600FF>橙色攻击</color>，^05\\n\\t想想那个<color=#FF0000FF>停止标志</color>\\n\\继续前进。'

### 185. asset#resources.assets#35613/str/0  ['placeholder_mismatch']
- 原文：'* Hello there,^05 young travellers!'
- 写回：'* 大家好，年轻的旅行者们！'

### 186. us#43318  ['glossary_mismatch']
- 原文：'ITEM'
- 写回：'商品/项目'
