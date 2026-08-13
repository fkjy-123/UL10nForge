# interdream 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：571（跳过回显/未翻译）
- 不合格：228 条（信息完整性 50 条、术语一致性 55 条、语义一致性 77 条、否定 14 条、人物关系/语义一致性 1 条、术语/实体错误 1 条、人物关系与动作逻辑 1 条、人物关系 10 条、语气与表达 3 条、人物关系与因果 2 条、语气 5 条、语义错误 1 条、语气与语义 1 条、时间 1 条、语义偏差 2 条、语气与结构 1 条、语气与信息完整性 1 条、人物关系/术语一致性 1 条、术语/专有名词 1 条）
- 术语沉淀：11 条词对 → 全局术语库（C5 门禁拒绝 0 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）


## 不合格清单

[e0] DELTATRAVELER_Data/level0:asset#level0#97/str/1
  原文：This game is unaffiliated
with Toby Fox.
  译文：这款游戏与任何组织或公司无关。
  问题：信息完整性——译文末尾多出一句与原文无关的文本，导致信息不完整且产生歧义。
[e14] DELTATRAVELER_Data/level100:asset#level100#213/str/5
  原文：* (You're more concerned about\n  getting Jerryitus.)
  译文：确认官方译名，若确认为新词可保留音译，但需确保全游戏统一。
  问题：术语一致性——术语'Jerryitus'疑似为游戏特定名词，但译文'杰里图斯'未提供上下文验证，且'concerned about'译为'关心'在口语语境下略显生硬，建议确认专有名词译法并优化口语化表达。
[e16] DELTATRAVELER_Data/level100:asset#level100#214/str/0
  原文：* (There's a katana stuck in the\n  ground.)^05\n* (Take it?)
  译文：* 有一把刀卡在地面上……
*(要拿走吗？)*
  问题：语义一致性——译文存在严重语序混乱导致语义不通，且关键动词“接受”未准确对应原文的询问语气。
[e25] DELTATRAVELER_Data/level100:asset#level100#219/str/4
  原文：* I wonder if we can\n  find a key somewhere.
  译文：* 我想知道我们是否能在某个地方找到钥匙。
  问题：语义一致性——译文将原文的疑问句结构误译为陈述句，且丢失了关键疑问词'if'，导致语义偏差。
[e50] DELTATRAVELER_Data/level105:asset#level105#171/str/2
  原文：* (You try to take the spear,^05\n  but the handle was way too\n  slippery.)
  译文：* 你试图拿起那支长矛，^05
  但是，把手太滑了。
  滑溜溜。
  问题：语义一致性——译文严重偏离原文含义，将'滑溜'误译为'太难用了'，导致语义完全错误。
[e52] DELTATRAVELER_Data/level105:asset#level105#175/str/1
  原文：* (You wonder if you're in a\n  training ground.)
  译文：* 你是否觉得自己仿佛身处某种情境中……
  训练场。
  问题：语义一致性——译文严重偏离原文含义，将'训练场'误译为'某种情境'，且遗漏了关键名词'训练场'。
[e54] DELTATRAVELER_Data/level105:asset#level105#175/str/4
  原文：* (You try to take the spear,^05\n  but the handle was way too\n  slippery.)
  译文：* 你试图拿起那支长矛，^05
  但是，把手太滑了。
  滑溜溜。
  问题：语义一致性——译文严重偏离原文含义，将'滑溜'误译为'太难用了'，导致语义完全错误。
[e60] DELTATRAVELER_Data/level105:asset#level105#180/str/1
  原文：* (You can think of a few\n  ways this could've happened.)^05\n* (None involve the dog.)
  译文：* 你可以想出几种这种方式可能发生的途径。
*（与狗无关。）
  问题：语义一致性——译文存在严重语序混乱导致语义不通，且未准确传达原文的假设语气（could've happened）。
[e65] DELTATRAVELER_Data/level105:asset#level105#187/str/4
  原文：* Susie,^05 it's not just\n  that.
  译文：* 苏西，^05 不仅仅是这样。
  问题：否定——译文将原文的否定含义（not just）错误地处理为肯定（不只是...那个），导致语义逻辑颠倒。
[e70] DELTATRAVELER_Data/level105:asset#level105#188/str/1
  原文：* The big guy from the guard\n  won't let me by cuz they're\n  on high alert.
  译文：* 那个来自警卫队的大个子不会让我通行，因为他们处于高度警戒状态。
  问题：人物关系/语义一致性——译文存在严重语病，主语指代混乱导致逻辑不通，且部分表达不符合游戏 UI 规范。
[e76] DELTATRAVELER_Data/level105:asset#level105#188/str/7
  原文：* Noel,^05 if you know her,^05 can\n  you tell her to STOP training\n  the dogs to be killers???
  译文：* 诺埃尔，如果你认识她的话，你能告诉她停止训练那些狗成为杀手吗？？？
  问题：信息完整性——译文严重缺失原文关键信息，且将原文的疑问句（询问是否知道）错误地处理为陈述句（她应该会），导致语义完全改变。
[e77] DELTATRAVELER_Data/level105:asset#level105#188/str/8
  原文：* She ain't part of the guard,^05\n  and I'm not lookin' to be\n  oppressed.
  译文：* 她不属于那支卫队。^05\n 而且，我并不想成为受压迫的人。
  问题：信息完整性——译文存在严重信息缺失，导致语义不完整且语气不匹配。
[e79] DELTATRAVELER_Data/level105:asset#level105#188/str/21
  原文：* With how people act,^05 I'd be\n  surprised if ANYONE let a\n  human live.
  译文：从人们的行为来看，^05 我可能会惊讶地发现，竟然有人会让人类活下来。
  问题：术语/实体错误——译文严重偏离原文，将'human'误译为'URP'，且'human live'被错误处理为'人类生活'，导致语义完全错误。
[e82] DELTATRAVELER_Data/level105:asset#level105#189/str/1
  原文：* (You try to take the spear,^05\n  but the handle was way too\n  slippery.)
  译文：* 你试图拿起那支长矛，^05
  但是，把手太滑了。
  滑溜溜。
  问题：语义一致性——译文严重偏离原文含义，将'滑溜'误译为'太难用了'，导致语义完全错误。
[e83] DELTATRAVELER_Data/level105:asset#level105#189/str/3
  原文：* (You try to take the spear,^05\n  but the handle was way too\n  slippery.)
  译文：* 你试图拿起那支长矛，^05
  但是，把手太滑了。
  滑溜溜。
  问题：语义一致性——译文严重偏离原文含义，将'滑溜'误译为'太难用了'，导致语义完全错误。
[e85] DELTATRAVELER_Data/level105:asset#level105#191/str/1
  原文：* (Seems like the dog put all\n  the cobwebs in here for the\n  time being.)
  译文：* 看来是那只狗把这里所有的蜘蛛网都弄乱了。
  暂时就这样吧。
  问题：语义一致性——译文严重偏离原文含义，将比喻句误译为字面描述，且丢失关键信息导致语义完全错误。
[e92] DELTATRAVELER_Data/level106:asset#level106#416/str/0
  原文：I THOUGHT YOU WERE \nBETTER THAN THIS,^05 \n^N...
  译文：我以为你比这更好。
^05
^N...
  问题：语义一致性——译文严重偏离原文含义，将原文关于“你不如预期”的抱怨错误地翻译为“你还在”，且丢失了关键比较信息。
[e101] DELTATRAVELER_Data/level107:asset#level107#138/str/2
  原文：* No...^10 it was the skeleton guy\n  himself that cut the rope\n  to town.
  译文：* 不……^10 是那个骷髅人自己割断了绳子
  去镇上。
  问题：语义一致性——译文严重违背原文逻辑，将“骷髅人自己割断绳子”错误译为“他自己切断了绳子去镇上”，导致人物动作与目的关系混乱，且未传达出骷髅人身份的关键信息。
[e107] DELTATRAVELER_Data/level107:asset#level107#138/str/13
  原文：* But I'm pretty sure it\n  wasn't even the government that\n  installed the rope.
  译文：* 但我相当确定，
  甚至政府本身也没
  安装过那根绳索。
  问题：语义一致性——译文严重偏离原文，错误理解并篡改了原文关于“绳索安装者”的核心含义，且存在大量信息缺失与逻辑混乱。
[e137] DELTATRAVELER_Data/level109:asset#level109#148/str/0
  原文：* "Holiday Residence\n* FOR SALE: CONTACT --- ----\n  FOR INFORMATION"
  译文：FOR INFORMATION
  问题：术语一致性——译文存在术语误用及信息缺失，'FOR INFORMATION'被生硬直译为'用于信息获取'，不符合游戏 UI 标准用语习惯。
[e146] DELTATRAVELER_Data/level11:asset#level11#150/str/0
  原文：* Please press this switch.\n  too.\n             - TORIEL
  译文：* 请按下这个开关。
  也。
             - 托里埃尔
  问题：信息完整性——译文严重缺失原文关键信息，导致语义完全错误。
[e164] DELTATRAVELER_Data/level110:asset#level110#115/str/5
  原文：SAY,^05 IF YOU CAN \nBRING ME SOMETHING \nINTERESTING...
  译文：说吧，如果你能的话，请给我带来点有趣的东西……
  问题：人物关系与动作逻辑——译文存在严重语序混乱及信息缺失，导致人物关系与动作逻辑颠倒，不符合游戏 UI 标准。
[e170] DELTATRAVELER_Data/level110:asset#level110#115/str/11
  原文：THOUGH IT IS YOUR \nCHOICE.
  译文：尽管这是你的决定。
  问题：信息完整性——译文末尾多译了“选择”二字，导致语义冗余且不符合原文结构。
[e171] DELTATRAVELER_Data/level110:asset#level110#115/str/36
  原文：YOU DO NOT HAVE \nANYTHING FOR ME \nYET?
  译文：您还没有给我任何东西吗？
  问题：否定——译文严重违背原文逻辑，将'尚未'误译为'都'，导致否定含义完全错误且语意不通。
[e182] DELTATRAVELER_Data/level111:asset#level111#334/str/13
  原文：* But I can't say for sure\n  it's even related.
  译文：* 但我无法确定它是否相关。
  问题：否定——译文后半句漏译了关键否定词 not，导致语义完全相反。
[e188] DELTATRAVELER_Data/level111:asset#level111#340/str/0
  原文：* Jester?^10\n* No,^05 I'm what some may\n  call a <color=#FF0000FF>demon</color>.
  译文：* 小丑？^10
不，^05 我就是有些人所说的那种人。
  我是一名 <color=#FF0000FF>恶魔</color>。
  问题：语义一致性——译文严重错误，将原文的'call a demon'（被称为恶魔）误译为'打电话给恶魔'，导致含义完全颠倒。
[e189] DELTATRAVELER_Data/level111:asset#level111#340/str/1
  原文：* Just because I smile all\n  the time doesn't mean I'm\n  a clown.
  译文：* 仅仅因为我总是微笑
  并不意味着我
  是个小丑。
  问题：语义一致性——译文严重违背原文逻辑，将'微笑'误译为'时间'，导致语义完全错误。
[e193] DELTATRAVELER_Data/level111:asset#level111#340/str/5
  原文：* I don't know,^05 but it keeps\n  showing up and punching me\n  in the face.
  译文：* 我不知道，^05 但它一直在出现，不断打我的脸。
  问题：语义一致性——译文严重偏离原文，丢失关键动作信息，且将'punching me in the face'错误翻译为'打我直面'，导致语义混乱。
[e206] DELTATRAVELER_Data/level111:asset#level111#342/str/3
  原文：* She didn't let me go anywhere\n  near Waterfall earlier!
  译文：* 她之前没让我去瀑布附近！
  问题：语义一致性——译文严重违背原文逻辑，将“没让我去瀑布附近”错误理解为“没让我离开任何地方，且当时在瀑布附近”，导致人物关系与场景描述完全颠倒。
[e213] DELTATRAVELER_Data/level111:asset#level111#342/str/22
  原文：* What?^05\n* You got a secret\n  hide-out or something?
  译文：* 什么？^05\n你得到了一个秘密\n  藏身处之类的东西吗？
  问题：信息完整性——译文遗漏了原文中关键的动词'got'（得到/拥有），导致语义不完整，且'秘密'一词未准确传达'secret'在语境中作为'秘密基地'含义的潜在歧义风险。
[e222] DELTATRAVELER_Data/level111:asset#level111#346/str/1
  原文：* This looks eerily like\n  Sans's house back home...
  译文：* 这看起来简直和……桑斯以前的家一模一样。
  问题：语义一致性——译文语序混乱且信息结构错误，将原文的对比逻辑（像桑斯的家）错误地拆解为两个独立且逻辑不通的句子，破坏了语义连贯性。
[e224] DELTATRAVELER_Data/level111:asset#level111#346/str/3
  原文：* Cuz Kris's mom's house\n  was nothing like it\n  was back home.
  译文：* 因为克里斯妈妈的房子
  跟家乡时完全不一样。
  问题：信息完整性——译文严重偏离原文，丢失关键信息且逻辑混乱，导致含义完全错误。
[e229] DELTATRAVELER_Data/level111:asset#level111#349/str/1
  原文：* Okay,^05 so is Sans\n  popular,^05 or does he\n  not check his mail?
  译文：* 好的，^05那么 Sans 受欢迎吗？^05还是说他根本不检查邮件？
  问题：语义一致性——译文严重偏离原文语义，错误地将'popular'（受欢迎）译为'也是了'，且句式结构混乱，导致含义完全不符。
[e239] DELTATRAVELER_Data/level111:asset#level111#351/str/1
  原文：* Remember when we\n  had a Grillby's at\n  home?
  译文：* 还记得我们以前家里开过 Grillby's 吗？
  问题：语义一致性——译文严重破坏原文语义结构，将'Grillby's'作为专有名词错误地拆解并插入到句子中间，导致'家吗？'成为独立且无意义的结尾，完全丢失了'家里有过 Grillby's 店'这一核心信息。
[e255] DELTATRAVELER_Data/level111:asset#level111#356/str/0
  原文：* It's always so nice visiting\n  Snowdin Town!
  译文：去拜访雪丁镇总是这么愉快啊。
  问题：语义一致性——译文将原文的‘访问/造访’错误地处理为‘拜访别人’，导致语义偏差且不符合游戏 UI 语境，同时‘雪丁镇’译名不规范。
[e259] DELTATRAVELER_Data/level111:asset#level111#356/str/5
  原文：* But Snowdin is a lot bigger\n  than people give it\n  credit for!
  译文：* 但是，Snowdin 的规模大得多，远超人们的预期！
  问题：语义一致性——译文严重偏离原文含义，将“给予的信用/认可”错误地翻译为“功劳归于”，导致语义逻辑混乱且不符合游戏 UI 语境。
[e309] DELTATRAVELER_Data/level113:asset#level113#171/str/2
  原文：* Came by today to make sure\n  Ice Wolf was still throwing\n  Ice to cool the CORE.
  译文：冰狼仍在继续扔冰来冷却核心。
  问题：术语一致性——译文存在严重术语错误，将游戏核心术语 CORE 误译为‘核心区域’，且‘扔东西’未准确传达‘扔冰’的特定动作含义。
[e363] DELTATRAVELER_Data/level115:asset#level115#170/str/0
  原文：* So the fish lady from the\n  guard came to tell the rest\n  of 'em about a human hunt?
  译文：* 所以，那个来自守卫的鱼女郎啊
  来通知其他人了。
  关于他们的人类狩猎行为？
  问题：信息完整性——译文严重缺失原文关键信息（'guard'未译出），且人物关系与逻辑混乱，导致语义偏差。
[e368] DELTATRAVELER_Data/level115:asset#level115#173/str/0
  原文：* I've never heard of the\n  ROYAL GUARD going on a human\n  hunt in the morning.
  译文：* 我从未听说过皇家卫队在早上去猎捕人类。
  问题：语义一致性——译文严重偏离原文含义，将'去进行人类狩猎'错误译为'变成人类形态'，且遗漏了'human'这一关键修饰词，导致语义完全错误。
[e380] DELTATRAVELER_Data/level115:asset#level115#174/str/5
  原文：* Dr. Alphys has studied a lot\n  about humanity.
  译文：* 阿尔菲斯博士已经研究了关于人类的大量内容。
  问题：语义一致性——译文将原文关于人类的研究对象表述为‘很多东西’，导致语义偏差且不符合游戏术语规范。
[e381] DELTATRAVELER_Data/level115:asset#level115#174/str/6
  原文：* I think if there's anyone\n  we can trust about this,^05\n  it's Alphys.
  译文：* 我认为，如果真有谁的话……
  关于这件事，我们可以信任的人。
  那就是阿尔菲斯。
  问题：信息完整性——译文严重偏离原文含义，将'关于这一点'误译为'我们可以放心'，导致信息缺失且逻辑错误。
[e388] DELTATRAVELER_Data/level115:asset#level115#175/str/8
  原文：* I love her Cinnamon Buns,^05 but\n  I'm absolutely NOT getting them\n  from Sans.
  译文：* 我喜欢她的肉桂面包，^05但是
  我绝对不会从 Sans 那里拿到它们。
  问题：人物关系——译文出现严重的人物关系颠倒错误，将原文中 Sans 拒绝提供面包的语境错误地翻译为面包来自 Sans，导致语义完全相反。
[e502] DELTATRAVELER_Data/level118:asset#level118#126/str/1
  原文：* (There are a bunch of job\n  listings.)^05\n* (All taken by Sans.)
  译文：* （有一堆工作职位列表。）^05
* （都被 Sans 抢光了。）
  问题：语义一致性——译文严重偏离原文含义，将'job listings'误译为'工作机会'并错误添加'列表'，将'all taken by'误译为'照片均由...拍摄'，导致人物关系与核心信息完全错误。
[e542] DELTATRAVELER_Data/level12:asset#level12#156/str/1
  原文：* "Perhaps trapping this ghost\n  in a room with <color=#FFFF00FF>FAKE WALLS</color>\n  was a    <color=#FFFF00FF>Mistak
  译文：* 或许把这只鬼魂关在有 <color=#FFFF00FF>虚假墙壁</color> 的房间里
  就是个 <color=#FFFF00FF>错误</color>
  问题：语义一致性——译文严重偏离原文含义，将“陷阱”误译为“抓住”，将“是”误译为“曾经是”，且破坏了原文的讽刺语气。
[e559] DELTATRAVELER_Data/level12:asset#level12#165/str/1
  原文：* Well,^05 I often start with\n  a simple 'how do you\n  do...'
  译文：* 嗯，我通常是从一句简单的‘你好’开始的。
  问题：语义一致性——译文严重偏离原文，将口语化的问候语误译为生硬的书面语，且丢失了原文的互动感和具体语境。
[e567] DELTATRAVELER_Data/level12:asset#level12#165/str/28
  原文：* You can say anything...^10\n* The dummy will not\n  be bothered.
  译文：* 你可以说任何你想说的话……^10\n这个假人不会感到烦恼。
  问题：信息完整性——译文出现严重语序混乱，导致后半句逻辑不通，且未准确传达原文关于假人“不会被打扰”的完整含义。
[e577] DELTATRAVELER_Data/level121:asset#level121#116/str/8
  原文：* It's called an Echo\n  Flower.
  译文：* 它被称为"Echo Flower"。
  花。
  问题：术语一致性——译文将专有名词 Echo 错误地拆解为普通名词，破坏了游戏术语的完整性与一致性。
[e593] DELTATRAVELER_Data/level122:asset#level122#216/str/1
  原文：* The royal guard is going to\n  bring back the rock puzzle\n  that used to be here.
  译文：* 皇家卫队即将出发，
  带回那块曾经在此的石头拼图。
  问题：信息完整性——译文严重偏离原文，丢失关键信息且未准确传达‘带回’及‘曾经在此’的含义。
[e601] DELTATRAVELER_Data/level122:asset#level122#220/str/4
  原文：* What a loser.^05\n* They don't know what\n  they're missing.
  译文：* 真是个失败者啊。^05\n他们不知道自己在失去什么。
  问题：信息完整性——译文严重偏离原文，丢失关键信息并错误添加无关内容，导致语义完全改变。
[e624] DELTATRAVELER_Data/level126:asset#level126#438/str/0
  原文：* If an error is made,^05 the Bell\n  Blossom can call the Bridge\n  Seeds back to where they start.
  译文：* 如果出错的话，^05 贝尔花蕾
  Blossom 可以呼叫'桥梁种子'
  回到它们原来的位置。
  问题：术语一致性——译文严重偏离原文，将专有名词误译为通用词，且错误地添加了原文不存在的‘应’字，导致含义完全改变。
[e644] DELTATRAVELER_Data/level127:asset#level127#314/str/2
  原文：* Kris,^05 get your eye\n  out of the way!!!
  译文：* Kris，^05 把眼睛移开！！！让开！！！
  问题：语义一致性——译文严重违背原文指令，将“让开”误译为“保护好眼睛”，导致人物关系与动作意图完全颠倒。
[e646] DELTATRAVELER_Data/level127:asset#level127#321/str/0
  原文：* Shoot!!!^05\n* I dropped Kris and Noelle!
  译文：我弄掉了克里斯和诺埃尔！
  问题：语气与表达——译文存在严重语病，'让...掉了下去'不符合中文表达习惯，且未能准确传达'掉落'这一动作的被动或意外性质。
[e657] DELTATRAVELER_Data/level128:asset#level128#340/str/1
  原文：- Sprite Artists -
  译文：- 精灵艺术家 -
  问题：术语一致性——术语不一致，'Sprite Artists' 应译为'精灵艺术家'而非'sprite 艺术家'，且格式不统一。
[e676] DELTATRAVELER_Data/level128:asset#level128#366/str/1
  原文：RENREN
LexiTheTT
LazyGales
Frakture
TygressLongheart
gabbo
lex3x
Autumn / WavePrism
TheTuneHero
Eribetra
Sawsk
  译文：Frakture
  问题：术语一致性——原文为英文用户名，译文将部分英文单词错误意译或误译（如 Frakture 译断裂、Autumn 译秋季），破坏了用户名作为标识符的准确性与一致性。
[e677] DELTATRAVELER_Data/level128:asset#level128#367/str/1
  原文：TheFlowerVixen
Beethovenus
YippieTB
Just a BLU Toon
spider8bytes
CyberCorvid
LumaHoneyy
malloryFireflies
parfae
tub
  译文：Beethovenus
  问题：术语一致性——部分玩家 ID 翻译生硬且不符合游戏社区习惯，如'贝多芬'、'帕尔法埃'、'坏心情'、'八'等未采用通用译法或过度意译。
[e683] DELTATRAVELER_Data/level128:asset#level128#376/str/1
  原文：UNITALE Monster Dust Code

Earthbound Distortional Background Shader

Literally everything



Dess Design Help

Inverted
  译文：UNDERTALE 怪物尘埃代码
  问题：术语一致性——存在多处术语翻译错误（如 UNITALE 应为 UNDERTALE、Frostermit 应为 Frostbite、Clover Run 应为 Clover Run 或特定游戏名误译）及专有名词拼写错误，且部分 UI 文本未统一使用行业标准译法。
[e727] DELTATRAVELER_Data/level131:asset#level131#472/str/1
  原文：RENREN
LexiTheTT
LazyGales
Frakture
TygressLongheart
gabbo
lex3x
Autumn / WavePrism
TheTuneHero
Eribetra
Sawsk
  译文：Frakture
  问题：术语一致性——原文为英文用户名列表，译文将部分英文单词错误意译或误译，破坏了用户名作为专有名词的完整性与一致性。
[e739] DELTATRAVELER_Data/level131:asset#level131#489/str/1
  原文：UNITALE Monster Dust Code

Earthbound Distortional Background Shader

Literally everything



Dess Design Help

Inverted
  译文：Undertale Monster Dust Code
  问题：术语一致性——存在多处术语翻译错误及专有名词拼写错误，违反行业标准译法。
[e754] DELTATRAVELER_Data/level15:asset#level15#137/str/5
  原文：* (Use some <color=#FFFF00FF>MERCY,</color>^10 human.)^10\n* Ribbit.
  译文：* 使用一些 <color=#FFFF00FF>怜悯，</color>^10 人。^10\n* 嘎嘎。
  问题：语义一致性——原文为祈使句“使用怜悯”，译文误译为陈述句“怜悯人”，导致语义完全颠倒且人物关系错误。
[e755] DELTATRAVELER_Data/level15:asset#level15#137/str/6
  原文：* Why were they only\n  talking to YOU about\n  this,^05 Kris?
  译文：* 为什么他们只
  跟你聊这个，^05 克里斯？
  问题：语气与表达——译文存在严重语病，'交谈关于'不符合中文表达习惯，且未体现原文中 Kris 作为被称呼对象的自然语感。
[e780] DELTATRAVELER_Data/level19:asset#level19#177/str/6
  原文：* Uhh...^10\n* That's what I\n  thought...?
  译文：* 呃……^10\n那就是我的意思。\n  是吗？
  问题：语义一致性——译文严重偏离原文含义，将对话误译为内心独白，且错误添加了“思考”一词导致语义偏差。
[e794] DELTATRAVELER_Data/level21:asset#level21#102/str/1
  原文：* Hell yeah!^10\n* Table cheese!
  译文：* Absolutely! ^10\n塔塔酱！
  问题：术语一致性——译文存在严重术语错误，'Table cheese' 误译为'表格奶酪'，实际应为'塔塔酱'或'塔塔酱'，且语气不够地道。
[e806] DELTATRAVELER_Data/level23:asset#level23#97/str/1
  原文：* "Spider Donuts - 7G"\n* Leave 7G in the web?
  译文：* 蜘蛛甜甜圈 – 7G\n需预留 7G 存储空间吗？
  问题：术语一致性——术语使用错误，'web'在游戏存储语境下指'存储空间'而非'网页'，且'Leave'译为'留下'不符合游戏提示语习惯。
[e814] DELTATRAVELER_Data/level23:asset#level23#99/str/1
  原文：* "Spider Cider - 18G"\n* Leave 18G in the web?
  译文：* 蜘蛛酒 – 18G
* 将 18G 留在蛛网上吗？
  问题：术语一致性——术语翻译错误，'Spider Cider' 误译为'蜘蛛苹果酒'，应为'蜘蛛酒'或'蜘蛛果酒'；'web' 误译为'网页'，游戏语境下应为'蛛网'。
[e820] DELTATRAVELER_Data/level24:asset#level24#127/str/0
  原文：* Did you miss it?\n* Spider Bakesale down and to\n  the right.
  译文：向右
  问题：术语一致性——原文 'to the right' 意为'向右'，译文误译为'权利'，属于严重术语错误及语义偏差。
[e823] DELTATRAVELER_Data/level24:asset#level24#127/str/7
  原文：* Did you miss it?\n* Spider Bakesale down and to\n  the right.
  译文：蜘蛛烘焙集市向下移动，向右。
  问题：术语一致性——原文'right'指方向'右'，译文误译为'权利'，属于严重术语错误导致含义完全改变。
[e829] DELTATRAVELER_Data/level24:asset#level24#130/str/9
  原文：* Ribbit.\n* (They're scared of you.)
  译文：* 呱呱叫。
*（他们害怕你。）
  问题：语义一致性——原文拟声词与括号内解释的因果关系被完全破坏，导致语义逻辑错误。
[e831] DELTATRAVELER_Data/level24:asset#level24#130/str/11
  原文：* Ribbit, ribbit.\n* (Just a gut feeling that you\n  can't hurt me.)
  译文：*（只是你的直觉而已，你……不会伤害我。）
  问题：信息完整性——译文存在严重信息缺失，导致人物关系与语义逻辑混乱，且术语使用不规范。
[e878] DELTATRAVELER_Data/level32:asset#level32#95/str/0
  原文：* Ribbit,^10 ribbit.\n^10* (Ooh,^10 are you two Kris\n  and Susie?)
  译文：* Ribbit, ribbit.\n*（哦，你们俩就是 Kris 和苏西吗？）
  问题：人物关系——译文将原文的疑问句结构误译为陈述句，导致人物关系和语气完全错误。
[e902] DELTATRAVELER_Data/level34:asset#level34#176/str/0
  原文：* Kris,^10 we should at\n  least check out the\n  surprise,^05 y'know?
  译文：* Kris，^10 我们至少应该去看看那个惊喜，^05 你知道吧？
  问题：人物关系——译文严重偏离原文，将原文的对话对象 Kris 误译为“我们”，且错误地将“惊喜”处理为独立句子，导致人物关系混乱和信息缺失。
[e931] DELTATRAVELER_Data/level36:asset#level36#112/str/2
  原文：* Hey,^05 mind your\n  business,^05 Kris!
  译文：* 嘿，^05 别管你的私事，^05 克里斯！
  问题：语义一致性——译文严重误译，将英文专有名词'business'错误翻译为中文'商业'，导致语义完全错误且破坏游戏语境。
[e938] DELTATRAVELER_Data/level36:asset#level36#114/str/2
  原文：* (You find this alternate\n  universe interpretation of\n  Chairiel to be underwhelming.)
  译文：* 您会发现这种关于 Chairiel 的替代宇宙诠释令人失望。
  问题：语义一致性——译文严重偏离原文，将'alternate universe interpretation'（替代宇宙诠释）误译为'替代方式宇宙的诠释'，且错误地将'underwhelming'（令人失望的）译为'不尽如人意'，导致语义完全错误。
[e993] DELTATRAVELER_Data/level39:asset#level39#129/str/0
  原文：* (Dull gardening tools.)\n* (They don't show much sign\n  of use.)
  译文：* （这些园艺工具看起来没什么用处。）
它们似乎都没怎么被用过。
  问题：语义一致性——译文存在严重语病，'太多迹象有用'不符合中文表达习惯，且未能准确传达原文'显示使用痕迹'的含义。
[e994] DELTATRAVELER_Data/level39:asset#level39#129/str/2
  原文：* (You refuse to believe that\n  this is not Chairiel.)
  译文：* 你拒绝相信这一点。
  这是 Chairiel。
  问题：否定——否定词 not 被错误翻译，导致语义完全相反。
[e995] DELTATRAVELER_Data/level39:asset#level39#134/str/2
  原文：* (You refuse to believe that\n  this is not Chairiel.)
  译文：* 你拒绝相信这一点。
  这是 Chairiel。
  问题：否定——否定词 not 被错误翻译，导致语义完全相反
[e1012] DELTATRAVELER_Data/level4:asset#level4#200/str/1
  原文：* I do believe that a\n  strange human named <color=#FFFF00FF>Sarah</color>\n  removed <color=#FFFF00FF>Player Pronouns<
  译文：* 我确实认为，一个名叫莎拉（Sarah）的奇怪人类已移除了玩家代词（Player Pronouns）。
  问题：语义一致性——译文语序混乱，将原文的修饰结构错误重组，导致语义不通顺且不符合中文表达习惯。
[e1024] DELTATRAVELER_Data/level4:asset#level4#204/str/3
  原文：* SO THAT ["Fun"] IS\n  OFFICIALLY\n  [Eviction Notice]
  译文：* 这样就能让"乐趣"正式
  官方声明
  [驱逐通知]
  问题：语义一致性——译文严重缺失原文核心信息，将"Fun"误译为"有趣"，且未体现"IS OFFICIALLY"的官方确认含义，导致语义完全错误。
[e1037] DELTATRAVELER_Data/level4:asset#level4#210/str/12
  原文：* And here we end off this\n  weird NPC dialogue with\n  <color=#ffff00ff>BATTLE TEXT</color>.
  译文：* 至此，我们结束这部分内容了。
  奇怪的 NPC 对话与
  <color=#ffff00ff>战斗文本</color>.
  问题：语义一致性——译文存在严重信息缺失，原文中'weird'（奇怪的）这一关键修饰语被遗漏，导致语义偏差。
[e1061] DELTATRAVELER_Data/level40:asset#level40#97/str/4
  原文：* (You considered taking it,^10\n  but you didn't want to\n  upset Toriel.)
  译文：* 你考虑过接受它吗？^10
  但你并不想这么做。
  以免让托里尔心烦。
  问题：人物关系——译文存在严重信息缺失，原文中 Toriel 是说话对象，译文将其误作动作承受者，且未传达出“不想让 Toriel 心烦”这一核心因果逻辑。
[e1063] DELTATRAVELER_Data/level40:asset#level40#100/str/2
  原文：* (You considered taking it,^10\n  but you didn't want to\n  upset Toriel.)
  译文：* 你考虑过接受它吗？^10
  但你并不想这么做，
  不想让托里尔心烦。
  问题：人物关系——译文存在严重信息缺失，原文中 Toriel 是说话对象，译文将其误作动作承受者，且漏译了关键信息。
[e1066] DELTATRAVELER_Data/level40:asset#level40#103/str/4
  原文：* (You considered taking it,^10\n  but you didn't want to\n  upset Toriel.)
  译文：* 你考虑过接受它吗？^10 但你并不想这么做，以免让托里尔心烦意乱。
  问题：信息完整性——译文存在严重信息缺失，漏译了原文中关键的转折逻辑和具体对象，导致语义不完整。
[e1068] DELTATRAVELER_Data/level40:asset#level40#104/str/2
  原文：* (You considered taking it,^10\n  but you didn't want to\n  upset Toriel.)
  译文：* 你考虑过接受它吗？^10
  但你并不想这么做，
  不想让托里尔心烦。
  问题：人物关系与因果——译文存在严重信息缺失，原文中 Toriel 是“不想让 Toriel 心烦”的施动者，译文却变成了“让 Toriel 心烦”的独立陈述，导致人物关系和因果逻辑错误。
[e1083] DELTATRAVELER_Data/level46:asset#level46#167/str/1
  原文：HARD MODE was done because
someone in the DELTATRAVELER
Discord Server had the idea
uhhhhhhhhhhhhhhhhhhhhhhh
  译文：困难模式之所以这样设定，是因为 DELTA TRAVELER 的 Discord 服务器里有人提出了这个想法……呃（长停顿）
  问题：语气——原文包含大量拟声词表达犹豫和口语化语气，译文将其完全删除，导致语气严重不符且丢失关键信息。
[e1131] DELTATRAVELER_Data/level5:asset#level5#209/str/0
  原文：* You wanna GO???\n\n         Hell yea    NO!!!!!
  译文：绝对不行！！！
  问题：否定——原文中明确包含否定词 NO，译文将其误译为肯定含义的'绝对不行'，导致语义完全相反。
[e1145] DELTATRAVELER_Data/level51:asset#level51#140/str/0
  原文：* (You and Noelle combined your\n  powers to become familiar with\n  the new world before you.)
  译文：* 你和诺埃尔结合力量，以便在你们面前熟悉这个新世界。
  问题：语义一致性——译文严重偏离原文含义，错误理解'combined your powers'为'合作'，且遗漏关键信息导致语义完全错误。
[e1164] DELTATRAVELER_Data/level53:asset#level53#982/str/14
  原文：* That'll surely make the shroom\n  angry.^05\n* You can keep your money.
  译文：* 那肯定会让蘑菇很生气。
  你可以保留你的钱。
  问题：语义一致性——译文严重偏离原文含义，将‘生气’误译为‘变得更好’，且错误拆分了‘愤怒’一词。
[e1169] DELTATRAVELER_Data/level53:asset#level53#985/str/0
  原文：* (Cross bridge to Happy-Happy\n  Village)
  译文：* （通往快乐村庄的桥梁）
  问题：信息完整性——译文遗漏了原文括号内的完整路径信息，导致游戏内导航指令不完整。
[e1179] DELTATRAVELER_Data/level53:asset#level53#1009/str/0
  原文：* (There's a hard hat inside\n  the box.)\n* (Take it?)
  译文：* 盒子里面有一个安全帽
  *(要拿吗？)
  问题：信息完整性——译文存在严重信息缺失（漏译"the box"）及术语误用（"接受"不符合游戏 UI 规范），且标点格式错误。
[e1181] DELTATRAVELER_Data/level53:asset#level53#1009/str/3
  原文：* (You got the Hard Hat.)
  译文：* (You got the Hard Hat.)
  问题：术语一致性——译文将游戏道具名称误译为中文成语，导致语义完全错误且破坏游戏沉浸感
[e1220] DELTATRAVELER_Data/level54:asset#level54#191/str/8
  原文：* We don't even need a\n  bike.\n* We can run.
  译文：* 我们甚至不需要自行车。
我们可以跑步。
  问题：语义一致性——译文严重偏离原文含义，将'bike'误译为'什么了'，将'run'误译为'继续前进'，导致游戏机制描述完全错误。
[e1257] DELTATRAVELER_Data/level56:asset#level56#515/str/0
  原文：* Welcome to the headquarters of\n  Happy-Happyism.
  译文：欢迎来到总部。
  快乐至上主义。
  问题：术语一致性——专有名词翻译不规范，未采用行业标准译法，且存在信息缺失。
[e1288] DELTATRAVELER_Data/level56:asset#level56#534/str/1
  原文：* People call that place Lilliput\n  Steps,^05 and it makes them feel\n  uneasy.
  译文：人们把那个地方叫做利利普特。
  步骤，^05，这让他们感觉不安。
  问题：语义一致性——译文严重误译，将原文的负面含义（不安）错误地译为正面含义（成就感），且遗漏了关键信息。
[e1295] DELTATRAVELER_Data/level56:asset#level56#547/str/0
  原文：* (All of our products are\n  blessed.)\n         --Blue-Blue Drugstore
  译文：* 我们所有的产品都蒙神祝福。
– 蓝蓝药局
  问题：语义错误——原文 'blessed' 意为'蒙神祝福'，译文将其误译为名词'祝福'，导致语义完全错误且不符合游戏 UI 语境。
[e1303] DELTATRAVELER_Data/level56:asset#level56#573/str/0
  原文：* When I painted everything\n  blue,^05 as Mr. Carpainter said,^05\n  my wife returned home!
  译文：* 当我把一切都涂成蓝色时，正如 Carpainter 先生所说，我的妻子回家了！
  问题：语义一致性——译文严重偏离原文语义，错误地将'涂成蓝色'理解为'涂好之后'，且遗漏了关键信息'蓝色'。
[e1319] DELTATRAVELER_Data/level56:asset#level56#577/str/2
  原文：* Really?\n^05* Sounds to me like you're\n  opposed to peace.
  译文：* 真的吗？
^05* 在我看来，你似乎反对和平。
  问题：语义一致性——译文严重偏离原文含义，将‘反对和平’误译为‘与和平背道而驰’，且漏译了‘opposed to peace'的核心否定逻辑，导致语义完全错误。
[e1326] DELTATRAVELER_Data/level56:asset#level56#579/str/0
  原文：* Kris,^05 I do NOT trust\n  this place.
  译文：* Kris,^05 我根本不信任这里。
  这个地方。
  问题：否定——否定词 NOT 被错误翻译为肯定词，导致语义完全相反
[e1368] DELTATRAVELER_Data/level56:asset#level56#608/str/9
  原文：* Those weren't just for show.^05\n* You can actually do something\n  special to avoid them!
  译文：* 那些并非只是用于展示而已。^05\n你实际上可以做一些特殊的事情来避免它们！
  问题：语气与语义——译文后半句将原文的祈使句“你可以做特殊事情来避免它们”误译为陈述句“请特别注意，避免它们”，导致语义偏差且语气不符。
[e1406] DELTATRAVELER_Data/level6:asset#level6#1088/str/1
  原文：Kris and Susie go places that
they shouldn't be at
  译文：克里斯和苏西去了他们不该去的地方。
  问题：时间——译文将原文的将来时/现在时叙事误译为过去时，且破坏了原文的连贯性，导致语义偏差。
[e1465] DELTATRAVELER_Data/level60:asset#level60#132/str/0
  原文：* (There's a sandwich inside\n  the box.)\n* (Take it?)
  译文：* 盒子里面有一个三明治。
* （要拿走吗？）
  问题：信息完整性——译文严重偏离原文，出现信息错乱、标点错误及术语误用。
[e1529] DELTATRAVELER_Data/level70:asset#level70#497/str/0
  原文：* (For some reason,^05 there's a\n  burger inside.)^05\n* (Take it?)
  译文：*（出于某种原因，^05那里有个汉堡在容器里。）^05
（拿走它吗？）
  问题：语义一致性——译文严重偏离原文语义，将'inside'误译为'里面的'导致逻辑不通，且'Take it?'口语化不足，未传达'拿走它吗'的邀请意味。
[e1543] DELTATRAVELER_Data/level72:asset#level72#116/str/4
  原文：* Are you okay???\n^05* Can you even hear\n  me???
  译文：* 你甚至能听到我吗？？？
  问题：人物关系——译文存在严重语序错误，导致人物关系颠倒，原意是“你能听到我吗”被译成了“你能听到吗？我”，造成逻辑混乱。
[e1570] DELTATRAVELER_Data/level74:asset#level74#129/str/0
  原文：* (You've returned to Snowdin,^05\n  but things seem a bit\n  off from last time.)
  译文：不过，情况似乎有点不对劲。
  问题：信息完整性——译文严重偏离原文含义，错误添加了‘比上次少了些’，且将‘off'误译为‘复杂’，导致信息缺失且语义错误。
[e1573] DELTATRAVELER_Data/level75:asset#level75#135/str/0
  原文：* We Live\n* We Love\n* We lie
  译文：* 我们生活
* 我们爱
* 我们撒谎
  问题：语义一致性——原文 'We lie' 意为‘我们撒谎’，译文误译为‘我们撒谎’并添加未存在的宾语‘你们’，且前两句‘We Live/We Love’的宾语‘我们’被错误替换为‘你们’，严重破坏语义一致性。
[e1584] DELTATRAVELER_Data/level75:asset#level75#138/str/9
  原文：* Kris,^05 your mom warned\n  us about them,^05 but\n  like...
  译文：* Kris，^05 你妈妈警告过我们关于它们，^05 但是
  就像……
  问题：语义一致性——译文严重偏离原文，丢失关键信息并错误处理否定词，导致含义完全改变。
[e1669] DELTATRAVELER_Data/level82:asset#level82#405/str/5
  原文：* (But for real,^05 Noelle\n  doesn't wanna be near\n  you because of this.)
  译文：* 但说真的，^05 Noelle 不想靠近你，因为这件事。
  问题：人物关系与因果——译文存在严重语序混乱，导致因果逻辑与人物关系表达不清，不符合游戏本地化标准。
[e1675] DELTATRAVELER_Data/level83:asset#level83#364/str/1
  原文：* "There's no point to\n  Nice Cream in such a\n  mean world."
  译文：* “在这样一个糟糕的世界里，吃 Nice Cream 毫无意义。”
  问题：信息完整性——译文严重缺失原文核心信息，且将专有名词 Nice Cream 错误处理，导致语义完全改变。
[e1705] DELTATRAVELER_Data/level84:asset#level84#158/str/2
  原文：* Unsuspicious Smell - Puppy\n  <color=#0000FFFF>BLUE</color> Rating\n  Smell of rolling around.
  译文：等级
  问题：术语一致性——术语'Rating'误译为'评分'，游戏 UI 中该词通常指'等级'或'评级'，且'Rolling around'的比喻义翻译生硬。
[e1737] DELTATRAVELER_Data/level86:asset#level86#140/str/0
  原文：* (It's a plate of frozen\n  spaghetti.)
  译文：* 这是一盘冷冻意大利面。
  问题：语义一致性——译文将'frozen spaghetti'错误地泛化为'冷冻食品'，丢失了'意大利面'这一关键具体信息，且语序混乱。
[e1738] DELTATRAVELER_Data/level86:asset#level86#140/str/1
  原文：* Hell yeah!^10\n* Table spaghetti!
  译文：Table spaghetti!
  问题：术语一致性——译文严重违背游戏术语标准，'Table spaghetti'被错误直译为'意大利面表格'，未识别为游戏内特定道具或技能名称，且'Absolutely'语气过于正式，不符合游戏口语风格。
[e1744] DELTATRAVELER_Data/level86:asset#level86#140/str/15
  原文：* It m-^05might actually\n  DESTROY the spaghetti...
  译文：* 它 m-^05实际上可能……
  摧毁那些意大利面……
  问题：语义一致性——原文 'might actually' 表示‘实际上可能’，译文将 'actually' 误译为‘那些’，导致语义完全错误且丢失关键信息。
[e1754] DELTATRAVELER_Data/level86:asset#level86#150/str/0
  原文：* (The seemingly clever spaghetti\n  trap stands before you,^05\n  tempting you to consume it.)
  译文：* （那个看似聪明的通心粉陷阱就摆在你面前，^05
  正引诱你将其吃掉。）
  问题：术语一致性——译文存在术语误用（意大利面应译为通心粉/意面）、语序生硬及口语化表达不当，未完全传达原文幽默感。
[e1785] DELTATRAVELER_Data/level88:asset#level88#151/str/2
  原文：* What if there's a\n  MONSTER under the bed!!!^05\n* Let's NOT!!!
  译文：让我们别！！！
  问题：否定——否定词 NOT 被错误翻译为“不要”，导致原文“让我们不要（做某事）”的否定含义在语境中完全丢失或产生歧义，且第一句严重偏离原文含义。
[e1786] DELTATRAVELER_Data/level88:asset#level88#151/str/3
  原文：* I think Kris would\n  like that, actually.
  译文：* 我其实觉得克里斯会喜欢那样的。
  问题：信息完整性——译文存在严重语序混乱及信息缺失，导致句子逻辑不通且丢失关键信息。
[e1787] DELTATRAVELER_Data/level88:asset#level88#151/str/10
  原文：* Kris,^05 neither me nor\n  Susie want to sleep for\n  only two minutes.
  译文：* Kris，^05 我和苏西都不想睡，
  只想睡两分钟。
  问题：信息完整性——译文严重偏离原文，不仅丢失关键信息，还错误地改变了人物关系和否定含义。
[e1791] DELTATRAVELER_Data/level88:asset#level88#154/str/2
  原文：* Yeah,^05 Kris,^05 why don't\n  we just get something\n  from uh...
  译文：* 是的，Kris，我们干脆从……拿点东西吧？
  问题：语义一致性——译文严重偏离原文含义，将'get something'误译为'得到了一些东西'，且错误添加了'刚刚'，导致语义逻辑混乱。
[e1792] DELTATRAVELER_Data/level88:asset#level88#154/str/3
  原文：* What should we call\n  him?^05\n* Blue Sans?
  译文：* 我们该怎么称呼他？
蓝色 Sans 字体？
  问题：语义一致性——译文将原文的疑问对象（him）错误地拆解为独立问句，导致语义逻辑混乱且不符合游戏 UI 语境。
[e1794] DELTATRAVELER_Data/level88:asset#level88#154/str/13
  原文：* What're we gonna call\n  the bad guy Sans\n  then?
  译文：* 我们该怎么称呼那个坏家伙 Sans 呢？
  然后呢？
  问题：人物关系——译文将原文中针对特定角色'Sans'的提问错误地泛化为对'反派'的提问，导致人物关系和指代对象发生偏差。
[e1795] DELTATRAVELER_Data/level88:asset#level88#154/str/14
  原文：* Prolly Red Sans.
  译文：* 可能是 Red Sans。
  问题：术语一致性——译文将专有名词 Red Sans 误译为普通名词短语，破坏了游戏内角色名称的专有属性，且语气过于口语化不符合 UI 规范。
[e1798] DELTATRAVELER_Data/level88:asset#level88#154/str/18
  原文：* Dunno.^05\n* Just got a feeling\n  he'd be green.
  译文：他会处于那种状态。
  问题：语义偏差——译文将原文中暗示的“绿色”（指代某种状态或属性）误译为字面意义的“变成绿色”，导致语义偏差且不符合游戏术语规范。
[e1809] DELTATRAVELER_Data/level89:asset#level89#361/str/3
  原文：* "This was the only time the\n  Royal Guard was given a direct\n  order of violence by the king."
  译文：这是唯一一次……
  皇家卫队直接接到了国王
  下达的暴力命令。
  问题：语义一致性——译文将原文中‘国王发布命令’这一动作主体与‘卫队获得授权’的被动结构混淆，导致语义逻辑偏差，且‘授权’一词未能准确传达‘暴力命令’的强制性含义。
[e1810] DELTATRAVELER_Data/level89:asset#level89#361/str/4
  原文：* "The queen was banished to the\n  Ruins,^05 to the anguish of his\n  majesty."
  译文：女王被流放到……
  废墟，^05 令陛下陷入无尽的痛苦之中。
  问题：人物关系——人物关系严重颠倒，原文指‘他的 majesty'（国王）痛苦，译文误译为‘陛下’陷入痛苦，导致主宾关系错误。
[e1891] DELTATRAVELER_Data/level94:asset#level94#384/str/0
  原文：* Kris,^05 do you think\n  you can eat the\n  orange tiles?
  译文：* Kris，你觉得呢？
  你可以吃橙色瓷砖。
  问题：信息完整性——译文严重缺失原文关键信息，将'橙色瓷砖'误译为'它'，导致游戏机制描述错误。
[e1913] DELTATRAVELER_Data/level94:asset#level94#385/str/12
  原文：* That's what I took\n  away from that,^05 so\n  I hope that helps,^05 Kris.
  译文：* 那就是我所理解的意思。
  从那里带走了一些东西，^05
  希望这能有所帮助，^05 Kris。
  问题：语义一致性——译文严重偏离原文，将“带走/领悟”误译为“远离”，且错误地将人名 Kris 置于句末作为称呼而非名字本身。
[e1984] DELTATRAVELER_Data/level97:asset#level97#107/str/0
  原文：* (The remains of a Snow\n  Papyrus.)
  译文：* （雪纸莎草的残骸）
  问题：信息完整性——译文将原文中 Snow Papyrus 这一专有名词拆解为两个独立句子，导致语义割裂且未传达完整含义。
[e1992] DELTATRAVELER_Data/level98:asset#level98#136/str/2
  原文：* He's just been making\n  Kris do all of them.
  译文：* 他只是让 Kris 做所有这些。
  Kris 全都做了。
  问题：人物关系——译文严重偏离原文，错误地将第三人称指代（He/Kris）处理为具体人名（克里斯），且将“让 Kris 做”误译为“克里斯参与”，导致人物关系和动作逻辑完全错误。
[e2004] DELTATRAVELER_Data/level99:asset#level99#114/str/1
  原文：* Yup.^05\n* Just bolted outta\n  here.
  译文：* 是的。^05
刚从那里出来而已。
  问题：信息完整性——译文末尾多译了“这里”二字，导致信息冗余且不符合原文逻辑。
[e2031] DELTATRAVELER_Data/resources.assets:asset#resources.assets#34710/str/3
  原文：* I'll make you start\n  REALLY flying if you\n  get more mouthy.
  译文：* 你要是再嘴臭，我就让你体验真正的飞行。
  问题：语义一致性——译文严重偏离原文含义，将威胁性警告误译为鼓励性话语，且未准确传达'get more mouthy'（嘴臭/挑衅）的语义。
[e2049] DELTATRAVELER_Data/resources.assets:asset#resources.assets#34741/str/2
  原文：* Then go meet the great\n  Mr. Carpainter as soon as\n  possible.
  译文：* 然后尽快去见那位了不起的 Carpainter 先生。
  问题：信息完整性——译文严重缺失原文关键信息，导致人物关系与指令含义完全错误。
[e2060] DELTATRAVELER_Data/resources.assets:asset#resources.assets#34815/str/0
  原文：* Would you quit staring at\n  my friend?
  译文：* 你会退出盯着看我的朋友吗？
  问题：术语一致性——术语使用错误，'quit' 在游戏 UI 中应译为'退出'而非'停止'，且'friend'作为宾语位置不当导致语义生硬。
[e2061] DELTATRAVELER_Data/resources.assets:asset#resources.assets#34815/str/1
  原文：* They're not into the "<color=#FFFF00>Devour</color>"\n  ACT.
  译文：* 他们并不喜欢"<color=#FFFF00>吞噬""行动"。
  问题：语气与表达——译文语序生硬且不符合中文游戏 UI 习惯，'并不感兴趣于'应改为'对...不感兴趣'，'行动'作为 ACT 的直译略显生硬。
[e2098] DELTATRAVELER_Data/resources.assets:asset#resources.assets#34966/str/1
  原文：* You strange,^05 unmasked people.^05\n* Don't go to heaven!
  译文：* 你们这些奇怪、不戴面具的人啊，^05 别去天堂！^05
  问题：信息完整性——译文严重缺失原文关键信息，导致语义不完整且语气不当。
[e2180] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35100/str/46
  原文：neutral`*\ti guess it's some kid that's\n\ttryna save the world.
  译文：我猜那可能是某个孩子，正试图拯救世界。
  问题：语气与结构——译文将原文的现在进行时（tryna）错误地处理为独立句子，导致语义断裂且语气不自然。
[e2199] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35167/str/0
  原文：* Devour <color=#00FF00FF>Greens</color>
  译文：* 吞噬 <color=#00FF00FF>绿草</color>
  问题：术语一致性——专有名词翻译错误，将游戏术语'Greens'误译为政治实体'绿党'，导致语义偏差。
[e2200] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35167/str/1
  原文：* Not <color=#FCA600FF>Oranges</color>
  译文：* 不是橙子
  问题：术语一致性——术语使用错误，'Oranges' 在此语境下指水果而非人名，且否定词位置导致语义生硬，不符合游戏 UI 规范。
[e2208] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35210/str/0
  原文：* Ribbit,^10 ribbit.\n^10* (Thank you for sparing\n  me,^10 human and monster.)
  译文：* Ribbit, ^10 ribbit.\n^10*（谢谢你没杀我，人类和怪物。）
  问题：语义一致性——译文严重偏离原文含义，将对话内容错误替换为无关的“耐心等待”，且破坏了人物关系与句子结构。
[e2214] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35210/str/11
  原文：* Ugh!!!^10\n* Why couldn't we just\n  have Ralsei here?!
  译文：* 呃！！！^10\n为什么我们就不能直接把 Ralsei 叫过来呢？！
  问题：语义一致性——译文将原文的疑问句结构误译为两个独立的问句，导致语义逻辑断裂且语气不符。
[e2215] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35212/str/0
  原文：* Robbit, robbit.^10\n* (Are you impressed with how I\n  fly through the air?)
  译文：* 你对我在空中飞行的表现印象深刻吗？
  问题：信息完整性——译文存在信息缺失，将原文中关于“飞行”的疑问句拆分并丢失了后半部分含义。
[e2226] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35273/str/0
  原文：* Robbit, robbit.^10\n* (Greetings,^05 human and monster.)
  译文：* 罗比特，罗比特。^10\n（问候，^05 人类与怪物。）
  问题：术语一致性——译文将原文中针对“人类和怪物”的复数概念误译为“人类与怪物们”，导致语义偏差且不符合游戏 UI 习惯用语。
[e2227] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35273/str/1
  原文：* (You have done wonderfully in\n  the battle.)^05\n* (You were quite mystical.)
  译文：* 你在战斗中表现得非常出色。
  你真是充满神秘感。
  问题：语义一致性——译文严重偏离原文含义，将'战斗'误植为独立句子，且'神秘兮兮'未能准确传达'mystical'的语境含义。
[e2253] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35334/str/0
  原文：* Did You Enjoy\n  <color=#00FF00FF>Tasty Green Snakes</color>
  译文：* 你喜欢吗？
  <color=#00FF00FF>美味绿蛇
  问题：语义一致性——译文将游戏标题误译为食物名称，严重偏离原文含义，且未体现游戏品牌感。
[e2267] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35442/str/0
  原文：* Y'know,^05 I ruined a lot of\n  games of "Ball Game" by being\n  in that hole.
  译文：* 你知道的，我因为身处那个洞，毁掉了很多《Ball Game》的游戏。
  问题：语义一致性——译文严重偏离原文含义，将‘毁掉游戏’误译为‘毁掉东西’，且错误地将‘在那个洞里’处理为对游戏玩法的说明，导致语义完全错误。
[e2295] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35469/str/1
  原文：- Sprite Artists -
  译文：精灵艺术家
  问题：术语一致性——术语不一致，'Sprite Artists' 应译为'精灵艺术家'而非'sprite 艺术家'，且标点符号不统一。
[e2301] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35478/str/1
  原文：RENREN
LexiTheTT
LazyGales
Frakture
TygressLongheart
gabbo
lex3x
Autumn / WavePrism
TheTuneHero
Eribetra
Sawsk
  译文：Frakture, Autumn
  问题：术语一致性——原文为英文用户名列表，译文将部分英文单词错误翻译为中文，破坏了列表的格式一致性。
[e2321] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35621/str/1
  原文：UNITALE Monster Dust Code

Earthbound Distortional Background Shader

Literally everything



Dess Design Help

Inverted
  译文：UNDERTALE 怪物尘埃代码
  问题：术语一致性——存在多处术语翻译错误（如 UNITALE 应为 UNDERTALE、Frostermit 应为 Frostbite）及专有名词翻译不准确，且原文中未出现的英文内容被擅自翻译。
[e2406] DELTATRAVELER_Data/resources.assets:asset#resources.assets#35816/str/1
  原文：* Why did you say "Snowy that\n  I know?"
  译文：* 为什么你说'Snowy that I know'呢？
  问题：信息完整性——译文严重缺失原文关键信息，导致含义完全改变，且未正确翻译引号内的完整句子。
[e2459] DELTATRAVELER_Data/resources.assets:asset#resources.assets#36498/str/1
  原文：* But at this point,^05 it's become\n  a game of "Who will go missing\n  next?"
  译文：* 但到了这个地步，^05情况已经变得……
  “接下来谁会失踪”的游戏
  问题：信息完整性——译文严重缺失原文核心信息，将'Who will go missing next'的疑问句结构完全丢失，导致游戏机制含义改变。
[e2516] DELTATRAVELER_Data/resources.assets:asset#resources.assets#36650/str/59
  原文：neutral`*\tthat'd be like me assuming\n\tyour gender,^05 kris.^10\n*\tit'd be pretty rude.
  译文：这就像是我自己做出的假设一样。
你的性别，克里斯。
这真是太无礼了。
  问题：人物关系——译文严重偏离原文语境，将对话中的角色称呼误译为名词短语，导致人物关系混乱且信息缺失。
[e2529] DELTATRAVELER_Data/resources.assets:asset#resources.assets#36682/str/1
  原文：press [c] to challenge +4 card
  译文：按 [c] 键挑战 +4 卡牌
  问题：语气与信息完整性——译文过度解释导致信息冗余，且将游戏机制中的'加成'具体化为'使其获得'，改变了原文简洁的指令语气。
[e2551] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#23013
  原文：Did you think that 
I'd just RUN AWAY???
  译文：你以为我会直接跑掉吗？？？
  问题：否定——否定含义完全颠倒，原文为反问句强调“不应该跑”，译文误译为“难道应该跑”，导致语义相反。
[e2576] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#43344
  原文：Deals RUDE Damage`50
  译文：造成粗暴伤害`50
  问题：术语一致性——术语使用不规范，'Damage'未统一为游戏标准译法'伤害'，且'RUDE'未准确传达为'粗暴'或'野蛮'，语气不符。
[e2577] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#43428
  原文：Spares TIRED Enemies`32
  译文：为疲惫的敌人提供支援
  问题：语义一致性——原文中 TIRED 为形容词修饰 Enemies，译文误将“疲惫”处理为动词“提供”，导致语义完全颠倒且语法错误。
[e2580] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#43642
  原文：Deals all FIRE Damage`36
  译文：造成所有火属性伤害`36
  问题：术语一致性——译文将英文术语 FIRE 直接保留，未进行本地化翻译，违反术语一致性标准。
[e2585] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#46022
  原文：* Your SOUL shined its power
  onto Susie!
  译文：* 你的灵魂将力量闪耀给了苏西！
  问题：语义一致性——译文存在严重语病，'到苏西那里去'不符合英语原句 'onto' 的介词含义，且句式生硬，未准确传达'力量投射/灌注'的动态感。
[e2586] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#46192
  原文：* Your SOUL shined its power
  onto Noelle!
  译文：* 你的灵魂将力量闪耀给了诺埃尔！
  问题：语气——译文语序生硬且不符合中文表达习惯，导致句子结构不自然。
[e2600] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#48331
  原文：* Paula tried SHIELD...
* Your SOUL was protected by
  a LIGHT shield for 15 hits!
  译文：* 保拉尝试了 SHIELD……
* 你的灵魂得到了保护。
  一个能抵挡 15 次攻击的 LIGHT 护盾！
  问题：信息完整性——译文严重缺失原文关键信息，未传达'15 次攻击'的具体数值及'护盾'的具体名称，导致信息不完整。
[e2616] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#57064
  原文：* You prayed for love and
  hope.
* Its DEFENSE decreased!
  译文：* 你祈祷了爱与希望。
* 其防御降低了！
  问题：术语一致性——术语使用不规范，'DEFENSE'未统一为游戏标准译法'防御'，且'祈求'一词在战斗语境下略显生硬，建议优化为'祈祷'。
[e2631] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#73751
  原文：* Kris used K-ACTION!
* But they could just ACT,
  so nothing happened.
  译文：* Kris 使用了 K-ACTION！
* 但她们完全可以执行 ACT，
  所以什么都没发生。
  问题：语义一致性——译文严重偏离原文含义，将'行动'误译为'行动起来'，导致逻辑矛盾且未传达原文关于'使用特定动作'的意图。
[e2637] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#77741
  原文：* Susie points her weapon
  at Feraldrake.
* Feraldrake became TIRED.
  译文：* 苏西将武器指向费拉德拉克。
  问题：信息完整性——译文严重缺失原文关键信息，导致语义不完整且逻辑混乱。
[e2638] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#78149
  原文：* Noelle flows snow through
  the cold air.
* Feraldrake became TIRED.
  译文：* 诺埃尔让雪花在冰冷的空气中飞舞。
  问题：语义一致性——译文存在严重语病，第一句“让雪流过来寒冷的空气”结构混乱，导致语义不通且信息缺失；第二句语气过于书面化，不符合游戏战斗日志的口语习惯。
[e2642] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#80934
  原文：* You compliment Final Froggit.
* It understood you perfectly.
* Its ATTACK dropped.
  译文：你夸奖了 Final Froggit。
它完全理解了你的意思。
它的攻击下降了。
  问题：术语一致性——术语使用不规范，'ATTACK'未统一为游戏标准译法'攻击'，且'compliment'译为'称赞'在语境中略显生硬，建议调整为更符合游戏对话的'夸奖'。
[e2643] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#81105
  原文：* You threaten Final Froggit.
* It understood you perfectly.
* Its DEFENSE dropped.
  译文：* 你威胁了 Final Froggit。
* 它完全理解了你的意思。
* 它的防御下降了。
  问题：术语一致性——译文存在术语不一致问题，'DEFENSE'未统一为游戏标准译法'防御'，且'Its'指代不明导致人物关系/主宾关系存疑。
[e2644] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#81721
  原文：* Final Froggit recognizes this
  threat.
* It became TIRED.
  译文：* Final Froggit 意识到了这一点威胁。
* 它变得疲惫了。
  问题：信息完整性——译文存在严重信息缺失，原文两处星号后的完整句子被错误截断，导致语义不完整。
[e2672] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#90933
  原文：* ... But haters only make
  Glyde stronger.
* Glyde ATTACK UP+DEFENSE DOWN.
  译文：* ……但那些诋毁者只会让 Glyde 变得更强大。
  问题：语义偏差——原文中'only'作为限定词修饰'make'，强调诋毁者只会产生强化 Glyde 这一单一结果，译文'制造混乱而已'增加了原文未有的负面含义（混乱），且未准确传达'只会让 Glyde 变强'的核心逻辑。
[e2673] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#91357
  原文：* Glyde takes this as a
  challenge!
* It's ATTACK increased!
  译文：* Glyde 将这视为一种挑战！
  问题：信息完整性——译文存在严重信息缺失，原文"takes this as a challenge"被截断为"视为一种……"，导致语义不完整。
[e2680] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#93029
  原文：* You and Noelle called
  for the GREATERDOG,^05 but
  it didn't budge.
  译文：* 你和诺埃尔打电话叫 GREATERDOG，但它一动不动。
  问题：信息完整性——译文严重偏离原文，丢失关键信息（未提及打电话对象、未提及狗名、逻辑混乱），且否定词处理不当。
[e2681] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#93179
  原文：* You and Noelle called
  for the GREATERDOG.
  译文：* 你和诺埃尔叫来了 GREATERDOG。
  问题：语义一致性——译文严重偏离原文含义，将'叫来'误译为'打电话'，且未翻译'GREATERDOG'专有名词。
[e2684] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#94526
  原文：* Aim to grab GREATERDOG's
  {0}!
^05* (Press ^Z to grab!)^10 
  译文：* 目标是抓住 GREATERDOG 的 {0}！
  问题：信息完整性——译文严重缺失原文关键信息，导致指令含义不完整且可能误导玩家。
[e2685] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#94652
  原文：* You and Susie tried
  snatching GREATERDOG's
  {0}...
  译文：* 你和苏西尝试抢走 GREATERDOG 的 {0}...
  问题：信息完整性——译文严重缺失原文核心动词'抢'及宾语'物品'，导致语义完全改变且信息大量丢失。
[e2717] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#110678
  原文：* Its WIND-infused katana is
  its only means of attack.
  译文：其充满风的剑
这是其唯一的攻击方式。
  问题：术语一致性——译文将原文的'剑'（物体）误译为'剑术'（技能/能力），导致语义偏差且不符合游戏术语规范。
[e2731] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#121982
  原文：* Press ^Z to shoot when yellow!
* Hold and release ^Z to fire
  a BIG SHOT!
  译文：太酷了！
  问题：语气——原文强调“按住并释放”的操作机制，译文“按住并释放”虽保留动作，但前句“按...即可射击”未体现“按住”的持续状态要求，且“太棒了”语气过于夸张，不符合游戏 UI 提示的简洁规范。
[e2732] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#122137
  原文：* Press ^Z to shoot when
  yellow! Hold and release
  ^Z to fire a BIG SHOT!
  译文：* 按下 ^Z 键在黄色时射击！按住并释放 ^Z 发射大威力炮弹！
  问题：术语一致性——译文存在术语误用（'用于'应为'按下'）及语序生硬问题，影响操作理解。
[e2733] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#124349
  原文：* You and Susie threatened to
  kill Kris.
* Kris became TIRED.
  译文：* 你和苏西威胁杀死克里斯。
  问题：信息完整性——译文在原文省略处强行补全了“要”，导致语义偏差，且“很累了”口语化严重，不符合游戏 UI 简洁规范。
[e2734] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#124526
  原文：* Everyone brought to Kris
  <color=#FFFF00FF>FOUR WHOLE CHUNGUSSIES</color>.
  译文：* 大家都带来了 Kris。
  <color=#FFFF00FF>四本完整的 Chunguessies。</color>
  问题：人物关系/术语一致性——译文严重篡改原文含义，将游戏内角色名称误译为书名，且遗漏了关键数量词'四本'及形容词'完整的'。
[e2738] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#136037
  原文：* It seems to feel bad.
* It's ATTACK and DEFENSE
  drop!
  译文：* 看起来有点难受。
* 攻击和防御
  掉落！
  问题：语气——译文语气过于书面化，不符合游戏 UI 的口语化风格，且未体现原文的感叹语气。
[e2742] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#139910
  原文：* You lie down and rest.
* Moldessa tucks you in with
  a blanket of <color=#00FF00FF>[MOSS]</color>.
  译文：* 你躺下来休息。
* Moldessa 用 <color=#00FF00FF>[苔藓毯子]</color> 把你盖好。
  问题：信息完整性——译文严重缺失原文关键信息，将“用苔藓毯子盖好你”简化为“盖好被子”，且错误地将专有名词'MOSS'译为通用词‘覆盖物’，导致游戏机制与术语双重错误。
[e2744] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#141872
  原文：* Moldsmal is still
  AFFECTIONATE.
^05* Cannot consume.
  译文：* Moldsmal 仍然充满感情。
^05* 无法消耗。
  问题：术语一致性——原文为游戏内状态描述，译文将'AFFECTIONATE'误译为'继续着'，且'充满感情'语序生硬，严重偏离游戏 UI 语境。
[e2745] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#141987
  原文：* Susie tried to get a bite
  out of Moldsmal.^05
* Moldsmal became AFFECTIONATE!
  译文：* Moldsmal 变得很友好了！
  问题：术语一致性——译文严重违背游戏术语规范，将'AFFECTIONATE'误译为'深情'，且未体现'变得'这一状态变化过程，导致语义偏差。
[e2750] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#149089
  原文：* You can use S-ACTION from
  Susie's MAGIC menu to talk
  to Napstablook.
  译文：* 你可以使用 Susie 的魔法菜单中的 S-ACTION 功能与 Napstablook 对话。
  问题：信息完整性——译文严重缺失原文关键信息，导致功能描述不完整且逻辑混乱。
[e2752] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#151186
  原文：* He starts to understand.
* Ness's ATTACK dropped!
  译文：尼斯的攻击命中！
  问题：术语一致性——术语使用错误，ATTACK 未统一为游戏标准译法，且否定词 dropped 翻译为‘失败’导致语义偏差。
[e2754] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#155440
  原文：* You ordered Susie to cast
  RED BUSTER.
* Susie disobeyed orders!
  译文：红色爆破
  问题：术语/专有名词——译文严重错误，将专有名词'RED BUSTER'误译为'红色上衣'，导致游戏核心指令含义完全丢失。
[e2755] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#155576
  原文：* You ordered Susie to cast
  RED BUSTER.
* Susie hits you!
  译文：你命令苏西发射红爆弹。
红爆弹。
苏西打你了！
  问题：术语一致性——译文严重错误，将游戏术语'RED BUSTER'误译为'红胸鸟'，且未传达'发射'动作含义。
[e2773] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#178567
  原文：What?
Wanna 
FIGHT 
about 
it?
  译文：什么？想为这件事战斗吗？
  问题：语义一致性——译文严重破坏原文语义，将'关于'误译为'它'，导致句子逻辑完全崩塌且不符合游戏 UI 规范。
[e2787] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#186361
  原文：* Use LEFT and RIGHT to change
  weapons. Setting Susie/Noelle
  to None will deactivate them.
  译文：使用'左键'或'左方向键'
  问题：术语一致性——译文存在严重术语错误（'LEFT'误译为'左侧'）及信息缺失（'None'未翻译），导致操作指令含义改变。
[e2790] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#191533
  原文：* Whimsalot was not deterred.
* Its ATTACK went up.
  译文：* Whimsalot 并未被阻止。
  问题：否定——原文包含否定词 not，译文漏译导致语义完全相反，且未体现数值上升的具体属性。
[e2803] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#207493
  原文：* If Kris's mom lets
  me actually fight WITH
  you,^05 that is...
  译文：* 如果克里斯的妈妈让我真正和你一起战斗，那就是……
  问题：语义一致性——译文严重偏离原文逻辑，将'如果妈妈同意'的条件句误译为'实际上'，且错误地将'与之战斗'的主语锁定为'我'，导致人物关系和语义逻辑完全混乱。
[e2809] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#211372
  原文：* You wouldn't let him
  get away from you,
^05  WOULD YOU KRIS?
  译文：* 你不会让他从你身边溜走的。
^05 你会吗，克里斯？
  问题：语义一致性——译文严重偏离原文含义，将‘让他逃脱’错误译为‘让他这么做’，且遗漏了关键动词'get away'。
[e2813] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#215203
  原文：* All of this?^05
* You wanted me to think
  that you were THEM.
  译文：* 你希望我思考一下，
  你其实是他们。
  问题：语义一致性——译文严重偏离原文含义，将'You wanted me to think that you were THEM'错误翻译为'你就是他们'，导致人物关系和逻辑完全混乱。
[e2819] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#220069
  原文：* But...^10 don't you wanna
  know about your SOUL?^15
* About LOVE?
  译文：* 但是……^10 你难道不想了解你的灵魂吗？^15
* 关于爱？
  问题：术语一致性——译文将原文中强调的'LOVE'（爱）误译为'LOVE'（保持原词未汉化），且未体现与'SOUL'（灵魂）对应的'LOVE'（爱）的对比语境，导致信息缺失且术语使用不当。
[e2878] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#238407
  原文：* WHAT'S HAPPENING???^05
* IS KRIS OKAY!?!??!
  译文：* 发生了什么？？？^05
* 克里斯还好吗？！？？！
  问题：语气——译文语气过于随意，未能准确传达原文的焦急与震惊情绪，且未体现原文中强烈的感叹符号堆叠感。
[e2881] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#244224
  原文：* But you can run a
  LITTLE faster than this,^05
  right?
  译文：* 但你可以稍微快一点跑，对吧？
  问题：语义一致性——译文严重偏离原文含义，将‘run'误译为‘运行它’，导致语义逻辑混乱且丢失关键信息。
[e2887] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#250199
  原文：* As a human living in
  the UNDERGROUND,^10
  monsters may attack you.
  译文：作为生活在其中的地底居民，怪物可能会攻击你。
  问题：术语一致性——译文将原文的'Underground'（地下世界/地底）误译为'地下通道'，导致语义偏差且不符合游戏术语规范。
[e2908] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#271001
  原文：* All of you monsters
  abide by the disgusting
  King ASGORE.
  译文：* 你们这些怪物们
  都遵守着令人厌恶的
  国王阿斯戈雷。
  问题：语义一致性——译文严重偏离原文含义，将'遵守'误译为'规定/行为'，且'那些'一词无中生有，破坏语义一致性。
[e2915] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#285710
  原文：GOD DAMN IT KRIS
WHERE THE HELL ARE
WE NOW
  译文：他到底在哪儿呢，我们现在在哪？
  问题：语义一致性——译文严重违背原文含义，将'我们现在在哪'错误翻译为'我们现在可以了'，且遗漏了关键疑问词'where'。
[e2917] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#287970
  原文：(Your SOUL shined its power
onto Noelle.)
  译文：（你的灵魂将力量闪耀在诺埃尔身上。）
  问题：信息完整性——译文严重缺失原文关键信息，导致语义不完整且破坏游戏术语一致性。
[e2919] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#290972
  原文：* Heheheh....
^05* Looks like we taught
  THEM a lesson!
  译文：看来我们确实给他们上了一课！
  问题：语义一致性——译文严重违背原文含义，将“教了教训”误译为“教错了”，且语气从自信挑衅变为自我怀疑。
[e2948] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#326462
  原文：* ... Why didn't you
  do ANYTHING,^05 Ralsei???
  译文：* ……你为什么不做任何事呢，^05 Ralsei???
  问题：否定——译文严重缺失原文核心否定词'ANYTHING'及疑问语气，导致语义完全颠倒，将质问变为祈使句。
[e2963] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#333684
  原文：NOT ONLY DID I 
SAVE YOUR LIFE LAST 
TIME WE MET...
  译文：我不仅在上次我们相遇时救过你的命……
  问题：否定——译文严重偏离原文，将陈述句误译为祈使句，且丢失关键信息并篡改语气。
[e3086] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#355714
  原文：I MUST BECOME A 
MEMBER OF THE ROYAL 
GUARD!!
  译文：我必须成为一名皇家卫队成员！！
  问题：术语一致性——译文将'ROYAL GUARD'（皇家卫队）错误地拆解并翻译为'王室成员'和'守卫'，导致人物身份与组织名称严重偏差，且'守卫'一词在语境中显得多余且不准确。
[e3115] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#383848
  原文：* They'll BOTH run away
  after I beat him
  up.
  译文：* 他们俩都会向上逃跑。
在我打败他之后。
  问题：语义一致性——译文严重缺失原文核心动作'向上冲'，导致人物关系与行为逻辑完全错误，且遗漏关键动词。
[e3116] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#384610
  原文：* And Sans chasing us
  means his eyes were
  kept on SHIT!!!
  译文：* 而桑斯正在追我们
  这意味着他的眼睛
  一直死死盯着 SHIT!!!
  问题：语义一致性——译文严重偏离原文含义，将“盯着看”误译为“眼睛糟糕”，且未传达出原文的愤怒情绪。
[e3134] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#403412
  原文：          IT APPEARS
        WE HAVE RUN OUT
           OF TIME.
  译文：它似乎已经。我们已经没有时间了。
  问题：信息完整性——译文严重缺失原文核心信息，将游戏内资源耗尽的警告误译为无关的陈述句，且完全丢失了'时间'这一关键要素。
[e3192] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#441156
  原文：* Kris,^05 we REALLY didn't
  need to kill that
  dog.
  译文：* Kris，^05 我们真的没必要杀那只狗。
  问题：语义一致性——译文严重缺失原文核心动词'kill'，导致人物关系与动作意图完全颠倒，且否定词处理混乱。
[e3349] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#472658
  原文：SO THESE NEW ONES 
WILL GENERATE A 
BULLET TO ATTACK!
  译文：所以，这些新来的将发射子弹进行攻击！
  问题：术语一致性——译文将游戏术语'Generate'误译为'生成'，未采用行业标准译法'发射'，且'有子弹可以攻击了'口语化严重，不符合游戏 UI 提示的简洁有力要求。
[e3373] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#474844
  原文：YOU CAN KEEP TRACK 
OF KRIS'S SMELL!
  译文：你可以追踪克里斯的气味！
  问题：信息完整性——译文严重丢失原文关键信息，将'追踪'误译为'保持记录'，且未传达'克里斯的'这一所有格关系。
[e3374] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#474918
  原文：IF KRIS STEPS ON 
AN ORANGE TILE,^05 
RAISE THE ORANGE!
  译文：如果克里斯踩到橙色方块，^05 获得橙色道具！
  问题：语义一致性——译文严重偏离原文含义，将游戏机制误译为日常对话，且完全丢失了关键的游戏指令信息。
[e3375] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#475030
  原文：IF KRIS STEPS ON 
A PURPLE TILE,^05 
RAISE THE LEMON!
  译文：如果克里斯没有踩到紫色瓷砖，就举起柠檬！
  问题：否定——否定词缺失导致含义完全相反，且人物关系与动作对象严重错误。
[e3435] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#496699
  原文：* AND I ONLY TRUST
  "THE BOYS" IN THE HANDS
  OF [[Pacifist Route]]
  译文：* 而我只信任"THE BOYS"。"那些男孩"掌握在来自[[和平主义路线]]的手中
  问题：信息完整性——译文存在严重信息缺失，原文中"THE BOYS"作为特定称谓被译为"那些男孩"，导致专有名词含义模糊，且未体现"信任"的对象明确性。
[e3436] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#496837
  原文：* SO THAT [["Fun"]] IS
  OFFICIALLY
  [[Eviction Notice]]
  译文：* 这样 [[Fun]] 就正式成为了 [[驱逐通知]]
  问题：语义一致性——原文为“为了 Fun 正式成为驱逐通知”，译文将“成为”误译为“成立”，导致语义完全相反且逻辑不通。
[e3446] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#501581
  原文：* Human.^05
* Either surrender your
  SOUL now...
  译文：* 要么现在就放弃你的灵魂……
  问题：信息完整性——译文严重缺失原文关键信息，导致语义完全改变，且存在否定词缺失问题。
[e3566] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#529792
  原文：Ruins OBLIT Failsafe
  译文：Ruins OBLIT 故障安全系统
  问题：术语一致性——术语翻译不规范，'OBLIT'作为游戏内特定术语未采用标准译法，且'故障安全系统'表述冗余，不符合游戏 UI 简洁性要求。
[e3568] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#532186
  原文：Napstablook OBLIT Failsafe
  译文：Napstablook OBLIT 故障安全
  问题：术语一致性——术语'Failsafe'译为'安全模式'不准确，游戏语境下应译为'故障安全'或'失效保护'，且'安全模式'易产生歧义。
[e3573] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#539328
  原文：}* This ICERING allows Noelle to
  cast ICE spells when equipped.
  译文：}* 这个冰晶护符使得诺埃尔能够……
  问题：术语一致性——术语翻译不规范，'ICERING'未使用游戏标准译法，且译文存在信息截断。
[e3583] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#548205
  原文：* A sea-based sandwich that
  increases SPEED in battle.}* Additionally,^05 eating it out of
  battle will increase your
  译文：* 一种海边的三明治，能提升战斗中的速度。此外，在战斗外食用它还能提升该房间的基准速度。
  问题：信息完整性——译文严重缺失关键信息，导致游戏机制描述完全错误，且术语使用混乱。
[e3591] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#589719
  原文：UNO!
^10GET BONED, 
BONEHEAD!
  译文：UNO!
  问题：术语一致性——原文为游戏内嘲讽用语，译文误将 UNO 译为联合国，造成严重语义错误。
[e3592] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#589807
  原文：UNO!
^10I CAN SMELL 
VICTORY!
  译文：胜利了！
  问题：术语一致性——严重误译，将游戏胜利提示 UNO 错误翻译为政治组织名称联合国，且完全丢失了胜利含义。
[e3610] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#601863
  原文：* WHAT THE HELL ARE YOU
  LAUGHING ABOUT,^05 KRIS?
  译文：* 你到底在笑什么啊，克里斯？
  问题：语义一致性——译文严重缺失原文核心信息，将‘你在笑什么’误译为‘你在干什么’，导致语义偏差。
[e3611] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#602212
  原文：* Man,^05 Kris,^05 you usually
  don't suck THIS much
  ass at puzzles.
  译文：* 兄弟，Kris，你通常不总是这样啊。别这么差劲了。解决谜题。
  问题：否定——译文严重偏离原文含义，错误地将否定句'不总是'处理为肯定句'总是'，且完全丢失了原文关于'解决谜题'的具体语境。
[e3630] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#613706
  原文：YOU START OUT WITH 
7 CARDS.
  译文：你起始拥有 7 张卡片。
  问题：语义一致性——译文严重偏离原文含义，将“起始拥有”误译为“从以下开始”，且遗漏了介词 with 的核心语义。
[e3669] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#618219
  原文：THAT IS QUITE...^05 
FRISK-LIKE OF YOU.
  译文：那真是……^05 你就是那种‘无头骑士’风格的人。
  问题：术语一致性——术语使用不规范，'Frisk-like' 未采用游戏行业通用译法'无头骑士'，且译文语序生硬，不符合中文表达习惯。
[e3714] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#656930
  原文：* <color=#00A2E8>LIGHT BLUE</color> - "Ball" is "Small."^10
* You waited,^05 still,^05 for
  this opportunity...
  译文：* <color=#00A2E8>浅蓝色</color> “球”是“小”。^10
  问题：术语一致性——术语翻译错误，'Small' 在 RPG 语境下应译为'小'而非'Small'，且'相当于'表述生硬，不符合游戏本地化规范。
[e3716] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#657614
  原文：* <color=#00C000>GREEN</color> - Your concern and care
  for "Ball" led you to a
  delicious victory.
  译文：* <color=#00C000>绿色</color> – 你对'Ball'的关心与呵护让你赢得了这场美味胜利。
  问题：信息完整性——译文存在严重信息缺失（漏译 'led you to' 导致因果断裂）及术语误用（'Ball' 未翻译），且语气不符合游戏成就提示风格。
[e3718] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#658026
  原文：* <color=#FFFF00FF>YELLOW</color> - Your sure-fire
  accuracy put an end to
  the mayhem of "Ball."
  译文：* <color=#FFFF00FF>黄色</color> - 你百发百中的准确性终结了"Ball"带来的混乱局面。
  问题：信息完整性——译文存在严重信息缺失，漏译了原文中关键的形容词'sure-fire'（百发百中/绝对可靠），导致语义力度大幅减弱，且未体现原文对'Ball'这一特定名称的引用语境。
[e3726] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#664118
  原文：NEW SAVE (FORMAT VERSION 
  译文：新建存档（格式化版本）
  问题：术语一致性——术语使用不规范，'NEW SAVE'未采用行业标准译法'新建存档'，且括号内英文原文缺失导致信息不完整。
[e3727] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#664798
  原文：LEGACY SAVE
  译文：旧存档
  问题：术语一致性——术语使用错误，游戏存档应译为“存档”而非“遗产保护”。
[e3734] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#670105
  原文：You look like you 
already did the 
FRISK thing.
  译文：你看起来像是已经做过那个'FRISK'了。
  问题：信息完整性——译文严重缺失原文关键信息，且错误添加了原文不存在的句子，导致语义完全改变。
[e3737] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#670640
  原文：What?^05
Are you waiting for 
EAGLELAND to be a 
place to visit?
  译文：什么？^05 你是在等待 EAGLELAND 成为一个值得去的地方吗？
  问题：信息完整性——译文存在严重信息缺失，原文询问是否等待 EAGLELAND 成为可游之地，译文仅翻译了前半句且后半句逻辑断裂，未传达“成为值得去的地方”这一核心含义。
[e3753] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#681191
  原文：WEAPON: Clean Pan
ARMOR: Big Ribbon
MONEY: 5
  译文：武器：清洁锅
护甲：大丝带
金钱：5
  问题：术语一致性——术语严重错误，游戏内物品名称未采用行业标准译法，且语义表达不符合游戏语境。
[e3757] DELTATRAVELER_Data/Managed/Assembly-CSharp.dll:us#683821
  原文：File Saved
  译文：已保存
  问题：信息完整性——译文添加了原文不存在的限定词'的'，导致语义从'文件已保存'变为'已保存的文件'，改变了原意。
