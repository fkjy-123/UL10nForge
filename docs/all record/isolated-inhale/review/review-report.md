# isolated-inhale 语义审核报告

- 审核模型：Qwen3.5-4B-Q4_K_M
- 审核条数：1372（跳过回显/未翻译）
- 不合格：432 条（数量/单复数 1 条、语义一致性 60 条、术语一致性 280 条、术语/语义一致性 1 条、术语/语义错误 1 条、语法错误 1 条、信息完整性 26 条、语气与完整性 1 条、标点与格式 1 条、否定 11 条、人物关系/因果逻辑 1 条、语言错误 3 条、术语一致性/语义错误 1 条、语气 14 条、人物关系与因果 7 条、语义冗余 1 条、语气与表达 1 条、语言/术语 1 条、语义错误 2 条、条件与因果 5 条、人物关系 4 条、否定与语义 1 条、语气与语义偏差 1 条、语言匹配 3 条、信息完整性与结构 1 条、术语与语气 1 条、术语与语法 1 条、人物关系/逻辑 1 条）
- 术语沉淀：88 条词对 → 全局术语库（C5 门禁拒绝 1 条污染风险词对）

## C5 门禁拒绝清单（高频普通词单 token，无语境强制会误杀其他语境，不入全局库）

- `Load`：拒绝沉淀：'Load' 是高频普通词单 token 词对（无语境可区分动词/名词/方向用法，全局强制会误杀其他语境——F22-4 三连杀实证）

## 不合格清单

[e11] Isolated Inhale_Data/level0:asset#level0#3198/str/0
  原文：Start the game to be able to change theese settings
  译文：启动游戏即可调整这些设置
  问题：数量/单复数——原文中"these"为复数，译文误用单数"这些"，且"change"在设置语境下通常译为"调整"而非"更改"，术语与语感不符。
[e99] Isolated Inhale_Data/level0:asset#level0#3331/str/0
  原文：THRUST:	Input = 0.0, Value = 0.0
STEER:	Input = 0.0, Value = 0.0
  译文：THRUST: 输入 = 0.0，值 = 0.0
STEER: 输入 = 0.0，值 = 0.0
  问题：语义一致性——译文将原文的 Value（值）错误地翻译为输出值，导致数值含义与原文不符。
[e143] Isolated Inhale_Data/level0:asset#level0#3404/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致含义完全错误。
[e167] Isolated Inhale_Data/level0:asset#level0#3444/str/0
  原文：Rebinding key for: Jump
  译文：正在重新绑定跳跃键
  问题：术语一致性——译文将 UI 功能描述误译为名词性短语，丢失了“正在执行”的动作含义，且未使用游戏标准术语。
[e199] Isolated Inhale_Data/level0:asset#level0#3502/str/18
  原文：Capitan Noob
  译文：队长
  问题：术语一致性——术语使用错误，'Captain' 应译为'队长'而非'菜鸟队长'，且原文拼写错误未修正
[e237] Isolated Inhale_Data/level1:asset#level1#87898/str/0
  原文：THRUST:	Input = 0.0, Value = 0.0
STEER:	Input = 0.0, Value = 0.0
  译文：THRUST: 输入值 = 0.0，STEER: 输入值 = 0.0
  问题：语义一致性——原文仅包含输入值，译文错误添加了‘输出值’，导致信息增删不匹配。
[e240] Isolated Inhale_Data/level1:asset#level1#87902/str/0
  原文：Conversator Name
  译文：对话者名称
  问题：术语一致性——术语严重错误，'Conversator' 指游戏角色而非技术设备，'转换器' 完全曲解原意。
[e246] Isolated Inhale_Data/level1:asset#level1#87913/str/0
  原文：Critical
Error
  译文：关键
  问题：术语一致性——原文为游戏术语'Critical'（关键/致命），译文'关键性'为名词且未传达游戏机制含义，属于术语误用导致语义偏差。
[e265] Isolated Inhale_Data/level1:asset#level1#87948/str/0
  原文：THRUST:	Input = 0.0, Value = 0.0
STEER:	Input = 0.0, Value = 0.0
  译文：THRUST: 输入值 = 0.0，值 = 0.0
STEER: 输入值 = 0.0，值 = 0.0
  问题：术语一致性——译文将原文的 Value（数值/值）错误地翻译为输出值，导致语义偏差且不符合游戏调试界面的标准术语规范。
[e272] Isolated Inhale_Data/level1:asset#level1#87958/str/0
  原文：Connection: <color=#BBAAA1>Stable</color>
Access: <color=#BBAAA1>Granted</color>
Executor ID:  <color=#BBAAA1>B-A24
  译文：连接：稳定的
访问方式：已授权
执行者 ID：B-A24
  问题：术语/语义一致性——译文严重偏离原文含义，将'Granted'误译为'当然'，导致信息完全错误。
[e275] Isolated Inhale_Data/level1:asset#level1#87964/str/0
  原文：Connection: <color=#BBAAA1>Stable</color>
Access: <color=#BBAAA1>Granted</color>
Executor ID:  <color=#BBAAA1>B-A24
  译文：访问方式：<color=#BBAAA1>已授权</color>
  问题：术语/语义错误——原文'Granted'意为'已授权'，译文'当然'严重误解原意，导致信息完全错误。
[e288] Isolated Inhale_Data/level1:asset#level1#87984/str/0
  原文：Critical
Error
  译文：关键
  问题：术语一致性——原文为游戏术语'Critical'（关键/致命），译文'关键性'为名词且未传达游戏机制含义，属于术语误用导致语义偏差。
[e298] Isolated Inhale_Data/level1:asset#level1#88000/str/0
  原文：This is the end of the srotyline for now. More in the future updates! This project still exists only thanks to your supp
  译文：目前，Storyline 的更新已经结束。未来会有更多内容更新！这个项目能够继续存在，完全是因为您的支持 <3
  问题：术语一致性——原文专有名词拼写错误未修正，且部分句式结构未能完全对应原文语气。
[e316] Isolated Inhale_Data/level1:asset#level1#88035/str/0
  原文：public void LookAt(Vector3 point)
    {
        Vector3 direction = (point - head.position).normalized;
        Vecto
  译文：public void LookAt(Vector3 point) { Vector3 direction = (point - head.position).normalized; Vector3 directionHorizontal = new Vector3(direction.x, 0, direction.z); Vector3 localDirection = body.InverseTransformDirection(direction); float bodyRotationY = Mathf.Atan2(directionHorizontal.x, directionHorizontal.z) * Mathf.Rad2Deg + 90; float headRotationY = Mathf.Atan2(localDirection.x, localDirection.z) * Mathf.Rad2Deg + 90; }
  问题：语法错误——译文严重破坏代码语法结构，导致程序无法运行，且变量名翻译错误。
[e317] Isolated Inhale_Data/level1:asset#level1#88036/str/0
  原文：<Task>SUBJECT 01</>\nStatus: <Inactive>Unknown</>\n\n<Error>Error</>: Protocol execution cannot be continued. New execut
  译文：<Task>主体 01
  问题：术语一致性——术语翻译严重错误，'Subject'误译为'主题'，'Protocol'误译为'协议'，且 UI 按钮动词'Continue'未使用标准译法'继续'。
[e322] Isolated Inhale_Data/level1:asset#level1#88041/str/0
  原文：CurePotion

f11

SIGA, Rain

Munni Massöör, FailCake, Zachary Anderson, corey k, Sophia, FPEBBLESFAN!!, Gabriel Steel, C
  译文：补全所有缺失的玩家名单，确保与原文一一对应。
  问题：信息完整性——译文严重缺失原文大量名单信息，且多处出现标点错误导致人名粘连，信息完整性完全破坏。
[e324] Isolated Inhale_Data/level1:asset#level1#88043/str/0
  原文：<Task>SUBJECT 01</>\nStatus: <Inactive>Unknown</>\n\n<Error>Error</>: Protocol execution cannot be continued. New execut
  译文：<Task>主体 01
状态：<Inactive>未知

<Error>错误：协议执行无法继续。需要新的执行器。

重新启动 T 协议的执行。正在准备冷冻舱。

<Task>主体 02
状态：<Command>就绪
  问题：术语一致性——术语翻译严重错误，'Subject'误译为'主题'，'Protocol'误译为'协议'，且 UI 按钮动词未使用行业标准译法。
[e433] Isolated Inhale_Data/level1:asset#level1#88295/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e499] Isolated Inhale_Data/level1:asset#level1#88396/str/0
  原文：Start the game to be able to change theese settings
  译文：启动游戏即可修改这些设置
  问题：信息完整性——原文中'change'译为'更改'尚可，但'these'指代不明且原文无明确指代对象，译文'这些'属于无中生有，造成信息偏差。
[e562] Isolated Inhale_Data/level1:asset#level1#88509/str/0
  原文：=(
An error has occured. Operation system needs to restart. 
Please, wait...

Don't turn off your pilot panel!
  译文：不要关闭你的驾驶舱！
  问题：术语一致性——原文 'pilot panel' 指飞行模拟游戏中的驾驶舱/操纵台，译文误译为'控制面板'，严重偏离游戏语境且术语错误。
[e612] Isolated Inhale_Data/level1:asset#level1#88572/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e629] Isolated Inhale_Data/level1:asset#level1#88593/str/0
  原文：Pilot Panel
  译文：飞行员面板
  问题：术语一致性——术语严重错误，'Pilot Panel'在游戏 UI 中应译为'飞行员面板'或'驾驶舱面板'，而非'试点小组'。
[e631] Isolated Inhale_Data/level1:asset#level1#88596/str/0
  原文：Pilot Panel
  译文：飞行员面板
  问题：术语一致性——术语严重错误，'Pilot Panel'在游戏 UI 中应译为'飞行员面板'或'驾驶舱面板'，而非'试点小组'。
[e642] Isolated Inhale_Data/level1:asset#level1#88624/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e682] Isolated Inhale_Data/level1:asset#level1#88702/str/0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e683] Isolated Inhale_Data/level1:asset#level1#88703/str/0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e719] Isolated Inhale_Data/level1:asset#level1#88767/str/0
  原文：Rebinding key for: Jump
  译文：正在重新绑定跳跃键
  问题：语气与完整性——译文将 UI 提示语误译为名词性短语，丢失了“正在执行”的动作含义，且未使用游戏标准术语。
[e774] Isolated Inhale_Data/level1:asset#level1#88873/str/0
  原文：THRUST:	Input = 0.0, Value = 0.0
STEER:	Input = 0.0, Value = 0.0
  译文：THRUST: 输入 = 0.0，值 = 0.0
STEER: 输入 = 0.0，值 = 0.0
  问题：语义一致性——译文将原文的 Value（值）错误地翻译为输出值，导致数值含义错误。
[e782] Isolated Inhale_Data/level1:asset#level1#88886/str/0
  原文：<color=#ffa555>[!]</color> If you run out of fuel during a flight, you can call the <color=#1f9>emergency supply deliver
  译文：如果在飞行过程中燃料用尽，您可以呼叫<color=#1f9>紧急物资补给</color>。请参考飞行员手册以获取详细操作指南。
  问题：语义一致性——原文指紧急物资补给而非救援电话，且未提及拨打，译文严重偏离原意。
[e869] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_CONTINUE_BIND
  原文：Appuyez <Key><KeyBind></> pour continuer...
  译文：请按 <Key><KeyBind></> 继续
  问题：术语一致性——术语'Continuer'误译为'以继续操作'，不符合游戏 UI 标准术语'继续'，且句式冗余不地道。
[e871] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_INTRO
  原文：<Task>SUJET 01</>
Statut : <Inactive>Inconnu</>

<Error>Erreur</> : l'exécution du protocole ne peut pas être poursuivie
  译文：<Task>课题 01
状态：<Inactive>未知

<Error>错误：无法继续执行该程序。需要一个新的执行体。

重启 <Key>PROTO 程序执行。冷冻舱准备中

<Task>课题 02
状态：<Command>就绪</>
  问题：术语一致性——术语严重错误（SUJET 译为主题、protocole 译为协议、exécuteur 译为执行者），且否定词与因果逻辑混乱，导致游戏机制含义完全错误。
[e925] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_FORM
  原文：Appuyez sur <Key>[<KeyBind>]</> pour changer la ligne.
  译文：请按 <Key>[<KeyBind>]</> 来更改行。
  问题：信息完整性——译文添加了原文不存在的“内容”二字，导致信息冗余且不符合游戏 UI 简洁规范。
[e984] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/LBL_DIALOG_0
  原文：This is the conversation menu, which is used to communicate with the bot through entered commands.

Press the <color=#ff
  译文：点击<color=#ffcc>高亮按钮</color>以显示可用的命令列表。
  问题：术语一致性——术语翻译不统一，'highlighted' 译为'被高亮显示的'不符合 UI 标准，建议简化为'高亮'
[e985] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少应该有 <color=#aaff>70% 相似</color> 的匹配项与列表中的某个命令。
  问题：信息完整性——译文后半句语义严重缺失，导致指令含义无法传达。
[e1155] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：工坊
  问题：术语一致性——术语翻译严重错误，'workshop'误译为'研讨会'，'airlock'误译为'传送门'，'task dispenser'误译为'任务分配器'，不符合游戏行业标准译法。
[e1156] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_ROUTINE
  原文：Reward:
• <Key><Credits></> credits
• Additional <Key>ship hull upgrade</>
  译文：奖励：
• <Key><Credits></> 金币
• 额外的 <Key>飞船外壳升级</>
  问题：术语一致性——原文'Credits'为游戏货币，译文误译为'致谢'，导致核心数值信息完全错误。
[e1163] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：切换
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'更改选择内容'不符合 UI 标准，'使用滚动轮'重复了原文的'使用'。
[e1247] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语误用，游戏 UI 中 Load 应译为'读取'而非'负载'
[e1284] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：container field 建议译为'容器'或'目标区域'
  问题：术语一致性——术语翻译错误，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中<Error>标签未正确保留。
[e1286] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>点以及最后的船体升级。
  问题：标点与格式——译文存在严重语病、标点缺失及术语格式错误，且关键信息（数量）未准确传达。
[e1292] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：很快，你就不会独自一人在飞船上了。我在那里留下了提示芯片：氧气站、燃料站和太阳能电站。找到它们，你就会知道会发生什么了。
  问题：信息完整性——译文严重缺失关键信息，导致任务目标完全丢失，且术语使用不规范。
[e1309] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须。
  问题：否定——译文将原文的否定含义（I have to）误译为肯定（确实如此），导致语义完全相反。
[e1312] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全改变。
[e1314] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：将'大规模内存单元'改为'质量存储单元'，将'《操作手册》'改为'《飞行员手册》'。
  问题：术语一致性——术语翻译严重错误，'mass memory unit' 译为'大规模内存单元'不符合游戏行业标准，且'pilot manual'译为'操作手册'未加书名号导致格式不规范。
[e1315] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：大容量存储器已成功交付。
注意：该目标未能摧毁那艘飞船……

正在执行解密操作……
正在进行验证……

任务已完成。
奖励：
• <Key><Credits></> 信用点；
• <Secret>“知识就是关键”的标语。

现在，我将允许您访问该<Task>工坊。请按照指示行事。<Task>升级你的飞船。
  问题：术语一致性——术语严重错误：'Mass memory unit' 译为'大容量内存单元'（应为'大容量存储器'），'Credits'译为'致谢'（应为'信用点'），'workshop'译为'研讨会'（应为'工坊'），且句子结构混乱导致含义完全改变。
[e1317] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我的厨房，因为它已经搬到了卧室。
  问题：人物关系/因果逻辑——译文严重违背原文逻辑，将‘因为’误译为‘因为’导致因果倒置，且关键动作‘增加氧气浓度’被错误地处理为被动状态描述。
[e1319] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续执行教程协议并加载第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'，但此处语境下'continue'作动词需结合上下文，主要问题在于'load'译为'加载'虽可接受，但'first task'后多出的'作为'导致语义冗余且不符合 UI 简洁性，同时'corporation'译为'公司'略显生硬，建议统一为'企业'或'集团'以符合游戏语境，此外'指示'一词在教程语境下不够精准。
[e1345] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：保留原文'Null reference exception'或采用标准技术译名'空引用异常'（若游戏风格允许），但必须确保上下文能正确传达这是程序错误而非普通文本。
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序正确识别。
[e1346] Isolated Inhale_Data/resources.assets:asset#resources.assets#1367/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e1362] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/CMD_GOAL
  原文：Nå ditt mål er til å forberede skipet ditt for en viktig misjon. Ifølge mine kalkulasjoner, med nåværende skip verktøy t
  译文：应翻译为：你的目标是为你那艘船准备一次重要任务。根据我的计算，以当前船只的装备状况来看，成功几率大约在 <Key><Success>% 左右。
  问题：语言错误——原文为挪威语，译文为中文，存在严重的语言错误；且原文中动词形式混乱（suksess står），译文虽通顺但未能准确反映原文的语病或特定语境，属于术语/语言规范层面的偏差。
[e1369] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_CONTINUE_BIND
  原文：Trykk <Key><KeyBind></> for å fortsette...
  译文：点击 <Key><KeyBind> 继续...
  问题：术语一致性——术语使用错误，'fortsette' 在挪威语游戏语境下对应中文'继续'而非'下去'，且句式生硬。
[e1371] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_INTRO
  原文：<Task>EMNE 01</>
Status: <Inactive>Ukjent</>

<Error>Feil</>: Protokoll utførelse kan ikke fortsette. Trenger en nye ful
  译文：<Task>EMNE 01</>
状态：<Inactive>未知</>

<Error>错误</>：协议执行无法继续。需要新的全功能版本。

重新开始 <Key>T-协议> 的执行。准备冷冻舱。

<Task>EMNE 02</>
状态：<Command>已准备就绪</>
  问题：术语一致性——术语翻译不统一，原文 EMNE 译为 EMNE 而非标准译法 EMNE，且 Key/T-protokollen 未采用标准术语 T-协议。
[e1378] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_SAVE_OVERRIDE
  原文：Lagringsfilen med det samme navn finnes allerede. Vil du overskrive det?
  译文：存档文件已存在。您希望覆盖它吗？
  问题：术语一致性/语义错误——原文为挪威语，译文错误地将专有名词或文件名直译为中文，导致文件名含义完全错误且不符合游戏本地化规范。
[e1383] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_WORKSHOP
  原文：Tilgang til <Key>verksted</> på den Skipsverft stasjonen
  译文：操作方式：在造船厂内的车间处进行操作。
  问题：术语一致性——术语翻译不准确，'Skipsverft'（造船厂）被错误译为'工厂'，且'verksted'（车间/工坊）与'工厂'语义重复，未体现游戏 UI 标准术语规范。
[e1422] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_BUILDING
  原文：Trykk på <Key>[<KeyBind>]</> for å gå inn i innvendiørmodus.
  译文：点击 <Key> [<KeyBind>] 以进入内建模式。
  问题：术语一致性——术语翻译错误，'innvendiørmodus'（内建模式）被误译为'用户模式'，且'å gå inn i'（进入）未准确传达为'进入'。
[e1423] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_EQUIPMENT
  原文：Trykk på <Key>[<KeyBind>]</> for å åpne utstyrsmenyen.
  译文：点击 <Key>[<KeyBind>] 以开启装备菜单。
  问题：术语一致性——术语翻译不准确，'utstyrsmenyen'应译为'装备菜单'而非'工具菜单'，且'å åpne'直译为'打开'在 UI 语境下不如'开启'地道。
[e1425] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_INTERACTION
  原文：Trykk på <Key>[<KeyBind>]</> for å samhandle.
  译文：按 <Key>[<KeyBind>]</> 进行交互。
  问题：术语一致性——术语翻译不准确，'Trykk på'应译为'按'而非'点击'，且'å samhandle'未准确传达'进行交互'的含义。
[e1426] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_KEYBOARD
  原文：Trykk på <Key>[<KeyBind>]</> for å sende.
  译文：按 <Key>[<KeyBind>]</> 以发送。
  问题：术语一致性——术语翻译不统一，'Trykk på'译为'点击'不符合游戏 UI 标准，应统一为'按'；且原文为挪威语，译文为中文，存在跨语言翻译错误。
[e1427] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_PIN
  原文：Trykk på <Key>[1-9]</> for å skrive inn koden.
  译文：点击 <Key>[1-9] 以输入代码。
  问题：语义一致性——原文为挪威语，译文强行译为中文导致语义不通且未传达原文含义，属于严重语义偏差。
[e1428] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_STEERING
  原文：Trykk på <Key>[<KeyBind>]</> for å kontrollere skipet.
  译文：按下 <Key>[<KeyBind>]</> 以控制船只。
  问题：术语一致性——原文为挪威语，指控制“船”，译文将船误译为“滑块”，且将“按键”误译为“点击”，导致游戏操作指令完全错误。
[e1454] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/DESC_CEREAL_BOX
  原文：Laget av romkorn. Lyder kult, men dette er bare frokostblandet.
  译文：由谷物制成
  问题：术语一致性——原文为瑞典语，译文误将专有名词'Romkorn'（谷物）译为'罗马'，且严重偏离原文关于'谷物'的语义。
[e1479] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/DESC_TROPHY
  原文：Pris "Årets pilot". Tildelt piloten kjent som Kirillfff.
  译文：荣获‘年度最佳飞行员’称号。
  问题：术语一致性——原文中'Årets pilot'为特定奖项名称，译文将其意译为‘年度最佳飞行员’导致奖项名称丢失，且'kjennt som'（被称为/被称为）被误译为‘被命名为’，改变了人物与奖项的关系。
[e1482] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少应该有 <color=#aaff>70% 的相似度</color> 与列表中的某个命令匹配。
  问题：语义一致性——译文后半部分严重偏离原文含义，将'It should be at least 70% similar'错误翻译为'至少应该如此'，导致信息缺失且逻辑不通。
[e1547] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/LBL_END_MSG
  原文：Dette er slutten på historie nå. Mer kommer i fremtidige oppdateringer! Dette prosjektet eksisterer fortsatt kun takket 
  译文：这是故事的结尾了。更多内容将在未来的更新中呈现！这个项目之所以能够继续存在，完全得益于他们的支持 <3
  问题：语义一致性——原文中 'slutten på historie' 指故事结束，译文误译为'继续存在'，导致语义完全相反。
[e1548] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_END_STATS
  原文：Anropsskilt: <0>
Tid spilt: <1>
Opptjente kreditter: <2>
Maks krediter: <3>
Dødsfaller: <4>
Poeng: <5>
  译文：召唤卡
  问题：术语一致性——术语严重错误，'Anropsskilt'（召唤卡）误译为'重新分类'，'Tid spilt'（已用时间）误译为'花费时间'，'Opptjente kreditter'（可用信用）误译为'可使用的信用额度'，'Dødsfaller'（死亡次数）误译为'死亡人数'，未遵循行业标准译法。
[e1646] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：工坊
  问题：术语一致性——术语翻译严重错误，'workshop'译为'研讨会'而非游戏标准'工坊'，'airlock'译为'传送门'而非'气闸'，'task dispenser'译为'任务分配器'不符合该游戏语境下的标准译法。
[e1647] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_ROUTINE
  原文：Reward:
• <Key><Credits></> credits
• Additional <Key>ship hull upgrade</>
  译文：奖励：
• <Key><Credits></> 金币
• 额外的 <Key>飞船外壳升级</>
  问题：术语一致性——原文'Credits'为游戏货币，译文误译为'致谢'，且标签位置颠倒导致严重语义错误。
[e1654] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以更改选择。使用 <Key>滚轮</> 控制距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'使用滚动轮'中'使用'重复且不符合 UI 标准用语习惯。
[e1738] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致功能含义完全相反。
[e1775] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器</>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语翻译不统一，'container field' 误译为'容器字段'，'tablet' 误译为'平板电脑'，且原文末尾标签未正确转义。
[e1777] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：护盾升级
  问题：术语一致性——译文存在严重语病，'……'导致句子结构断裂，且'船体升级'不符合游戏标准术语'护盾升级'。
[e1783] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示芯片
  问题：术语一致性——译文存在术语不规范（如'提示贴'非标准 UI 用语）、信息缺失（未体现'chips'的具体含义）及标点格式错误。
[e1800] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：语气——译文将原文中强烈的自我否定与决绝语气弱化为口语化的确认，且未准确传达“我不得不这么做”的强制性与悲剧色彩。
[e1803] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，且原文奖励列表中的具体数值与项目未完整对应。
[e1805] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船的<Task>大规模内存单元</>。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（毁坏）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e1806] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：将'研讨会'改为'工作间'
  问题：术语一致性——原文中'workshop'被误译为'研讨会'，导致游戏内任务指令含义完全错误，且'upgrade'翻译缺失。
[e1810] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：船坞
  问题：术语一致性——术语使用不规范，'Shipyard' 译为'造船站'不符合游戏行业标准（应为'船坞'），且'load'译为'加载'虽可接受但结合上下文'加载...任务'略显生硬，建议统一为'开始'或'执行'以符合 UI 习惯。
[e1836] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null Reference Exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被玩家理解。
[e1837] Isolated Inhale_Data/resources.assets:asset#resources.assets#1368/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：启用 <color=#8BDFFF>驾驶舱面板</color>
  问题：术语一致性——术语严重错误：将'pilot panel'误译为'控制面板'（应为'驾驶舱面板'或'飞行员面板'），将'undock'误译为'卸载'（应为'脱离'），将'docking area'误译为'对接区域'（应为'对接区'），将'transition button'误译为'过渡按钮'（应为'转换按钮'），且'static'语境下译为'安全状态'导致含义偏差。
[e1863] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_INTRO
  原文：<Task>SUBJECT 01</>
Status: <Inactive>Unknown</>

<Error>Error</>: Protocol execution cannot be continued. New executor 
  译文：<Task>任务 01
状态：<Inactive>未知

<Error>错误：协议执行无法继续。需要新的执行器。

重新启动 <Key>T 协议的执行。正在准备冷冻舱。

<Task>任务 02
状态：<Command>就绪
  问题：术语一致性——术语翻译不统一且部分表达不符合游戏 UI 规范，如'主题'应为'任务'，'准备好了'应为'就绪'。
[e1880] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_DEL_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语翻译不统一且部分表达生硬，未严格遵循行业标准译法。
[e1882] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_DEL_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：护盾升级
  问题：术语一致性——译文存在严重语病，'……'占位符导致句子断裂，且'船体升级'不符合游戏标准术语'护盾升级'。
[e1926] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_EQUIPMENT
  原文：Press <Key>[<KeyBind>]</> to open the equipment menu.
  译文：按下 <Key>[<KeyBind>] 打开设备菜单。
  问题：语气——译文将祈使句误译为陈述句，导致语气不符且指令感缺失。
[e1932] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：保留 <Task> 标签格式，如：<Task>氧气</Task>、<Task>燃料</Task>、<Task>太阳能电站</Task>
  问题：术语一致性——译文存在术语不规范、标点缺失及信息完整性问题，不符合游戏本地化标准。
[e1998] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少需要与列表中的某个命令有 70% 的相似度。
  问题：语义一致性——译文后半句语义严重偏差，丢失了原文关于“与列表中命令相似”的核心逻辑，导致指令含义完全错误。
[e2063] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我不得不。
  问题：语气——译文将原文中强烈的自我否定与决绝语气弱化为口语化的确认，且未准确传达“我不得不这么做”的强制性与悲剧色彩。
[e2182] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：工坊
  问题：术语一致性——严重术语错误：'workshop'误译为'研讨会'（应为'工坊'），'upgrade'误译为'升级'（虽词义相近但语境不符，且前文'workshop'错误导致指令逻辑混乱），同时'access to'后的内容缺失导致句子结构断裂。
[e2183] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非行业标准译法“信用点/金币”，且奖励列表结构缺失数值显示。
[e2184] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（如'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e2200] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回该船上的'大规模内存单元'
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e2202] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，因为它搬到了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将“不喜欢厨房里的灰尘垃圾”误译为“因为搬到了卧室里”，导致人物关系与因果关系完全颠倒。
[e2205] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：并读取
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'，此处语境下'继续'尚可但需结合上下文优化，更严重的是'load'误译为'加载'，游戏 UI 中 Load 应译为'读取'或'载入'，且'first task'后多了一个句号导致语法错误。
[e2208] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以更改选择。使用 <Key>滚轮</> 控制移动距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'使用滚动轮'重复了前文已说明的'使用'，且未严格遵循 UI 标准术语规范。
[e2246] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/CMD_SPEC_RES
  原文：You've completed all the available tasks for now. Great job, <Key><Name></>. I'm giving you the <Key>last hull upgrade</
  译文：护盾升级
  问题：术语一致性——术语使用不规范，'hull upgrade' 译为'升级机会'不符合游戏 UI 标准，应为'护盾升级'
[e2304] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e2339] Isolated Inhale_Data/resources.assets:asset#resources.assets#1369/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null reference exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被游戏系统正确识别。
[e2352] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/CMD_GOAL
  原文：Ye must prepare ye on ship fer a MIGHTY sail! My Tingling Pirate Senses tell me yer chances are <Key><Success></> out of
  译文：你们必须在船上做好准备，迎接一场激烈的航行！我的敏锐海盗直觉告诉我，你们的胜算其实并不大……<Key><Success>一百个人中！
  问题：信息完整性——译文严重缺失原文关键信息，将'out of a hundred'错误截断并遗漏，导致数值含义完全丢失。
[e2355] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/CMD_STOP_FAIL
  原文：<Error>Alas!</> there be no sequence!
  译文：警告：序列不存在！
  问题：语气——译文存在严重语病，'根本没有序列啊'不符合中文表达习惯，且'唉'作为感叹词在此处情感色彩与游戏错误提示的严肃性不匹配。
[e2357] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_DECRYPTER
  原文：Cartographer's Table!
  译文：制图师的桌！
  问题：术语一致性——术语使用错误，'Table'在游戏 UI 中应译为'桌'而非'表格'，且'Cartographer's'作为角色职业头衔处理不当。
[e2358] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_DISPENSER
  原文：Scroll Giver!
  译文：卷轴赠送者！
  问题：术语一致性——术语使用错误，'Scroll' 在游戏 UI 中通常指'卷轴'而非'滚动'，'Giver'指'赠送者'或'给予者'，整体译法不符合游戏行业标准。
[e2362] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_INTRO
  原文：<Task>PIRATE 01</>
Status: <Inactive>Lost To Sea...</>

<Error>Ahoy!</>: new Pirate needed!

I be restarting the <Key>P 
  译文：海盗
  问题：术语一致性——术语严重错误：将'Pirate'（海盗）误译为'盗版'，导致含义完全相反；同时遗漏了'P'作为按键提示的括号说明，造成信息缺失。
[e2373] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_WORKSHOP
  原文：Access to the <Key>Dock</> to upgrade yer vessel!
  译文：访问 <Key>船坞</> 以升级你的舰船！
  问题：术语一致性——术语'Dock'误译为'装备'，且语气过于口语化不符合游戏 UI 规范
[e2405] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_TUT_OBJ_MEET
  原文：Meet Blackbeard!
  译文：欢迎黑胡子！
  问题：语义冗余——译文存在语义冗余与术语不规范问题，且未遵循行业标准译法。
[e2410] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_EQUIPMENT
  原文：Hit yer <Key>[<KeyBind>]</> key to open yer pocket!
  译文：按 <Key>[<KeyBind>] 键打开你的口袋！
  问题：语义一致性——译文严重偏离原文含义，将“打开口袋的钥匙”误译为“打开你口袋的钥匙”，导致语义逻辑混乱且不符合游戏 UI 语境。
[e2412] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_INTERACTION
  原文：Hit <Key>[<KeyBind>]</> to poke with yer hook!
  译文：点击 <Key>[<KeyBind>] 用你的钩子戳它！
  问题：语气——译文将原文的祈使语气（poke with yer hook）误译为陈述句，且未准确传达“用钩子戳”的动作指令，语气不符。
[e2415] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_STEERING
  原文：Hit <Key>[<KeyBind>]</> to control yer ship!
  译文：按 <Key>[<KeyBind>]</> 控制你的飞船！
  问题：语气——原文为游戏指令，译文误用“点击”且未体现游戏操作语境，语气不匹配。
[e2430] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_SAVE_LOAD
  原文：save/recall yer tale
  译文：读取/恢复
  问题：术语一致性——术语使用错误，'recall'在游戏语境中应译为'读取'或'恢复'而非'取消'，且'ver tale'应为'ver your tale'，存在漏译。
[e2469] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_DIALOG_0
  原文：THIS BE YE CONVERSATION WINDOW!

PRESS THE BOTTOM LEFT BUTTON TO SPEAK TO BLACKBEARD
  译文：这是对话窗口！
  问题：语气——原文为感叹句且包含古英语/方言特征，译文语气平淡且未体现原文的强调感，存在语气不匹配问题。
[e2531] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_CONTINUE
  原文：PRESS YE ENTER KEY TO CONTINUE!!!
  译文：请按 Enter 键以继续！！！
  问题：术语一致性——术语使用不规范，'Continue' 未统一为行业标准译法'继续'，且原文感叹号数量与译文不符导致语气强度偏差。
[e2569] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_KEY_QUICK_LOAD
  原文：PIRATE QUICK LOAD!
  译文：海盗快速读取！
  问题：术语一致性——原文为命令式短语，译文误译为名词性短语，且严重违背游戏术语标准（Load 应译为“读取”而非“加载”），导致含义完全错误。
[e2574] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_KEY_SPRINT
  原文：PIRATE RUN!
  译文：海盗奔跑！
  问题：语义一致性——原文为“海盗奔跑”的积极行动描述，译文误译为“逃跑”，导致语义从主动进攻变为被动逃避，且未体现奔跑的动态感。
[e2635] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_START_GAME
  原文：START YE TALE BEFORE CHANGING THESE...
  译文：在更改这些设置之前，先开始吧……
  问题：术语一致性——原文 START 为游戏术语，译文误译为口语化的“开始吧”，且原文省略号后的省略内容被译文强行补全，导致信息缺失。
[e2648] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_FLASHLIGHT
  原文：PRESS <Key>[<KeyBind>]</> to toggle yer <Key>lantern</>
  译文：按 <Key> 键 [<KeyBind>] 切换你的 <Key>lantern
  问题：信息完整性——译文添加了原文不存在的“功能”二字，导致信息冗余，且未严格遵循术语一致性标准。
[e2649] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以更改选择。使用 <Key>滚轮</> 控制距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'使用滚动轮'重复了前文已提及的'使用'，且 UI 文本应更简洁。
[e2733] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致含义完全错误。
[e2770] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：在任何情况下都绝对不要打开这个容器。你不会喜欢里面的东西。
  问题：语气——原文中'UNDER NO CIRCUMSTANCES'意为'在任何情况下都绝对不要'，译文漏译了'绝对'，导致语气严重弱化，不符合游戏警告文本的严肃性要求。
[e2772] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key>信用点以及最后的船体升级。
  问题：术语一致性——译文存在严重语病，将原文的并列结构误译为递进关系，且关键术语'Credits'未采用行业标准译法'信用点'。
[e2778] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：很快，你就不会独自一人在飞船上了。我在那里留下了提示贴：氧气站、燃料站和太阳能电站。找到它们之后，你就会知道会发生什么了。
  问题：信息完整性——译文严重缺失关键信息，将原文中的三个具体站点（氧气、燃料、太阳能）全部遗漏，导致任务指引完全错误。
[e2795] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：语气——译文将原文中强烈的自我否定与决绝语气弱化为口语化的确认，且“确实如此”严重偏离了原文“我必须这么做”的主动意志。
[e2798] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非行业标准“信用点/金币”，且奖励列表结构缺失数值显示。
[e2800] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回该船上的'大规模内存单元'
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e2801] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问<Task>工坊。请按照指示行事。<Task>升级你的飞船。
  问题：术语一致性——严重术语错误：将'workshop'误译为'研讨会'（应为'工坊'），将'upgrade'误译为'升级'（虽词义相近但语境不符，且原文'access'被误译为'允许访问该内容'导致指令缺失），严重破坏游戏 UI 标准术语一致性。
[e2803] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将“因为不喜欢厨房的脏乱而搬进卧室”误译为“因为搬进卧室所以不喜欢脏乱”，导致人物关系与因果关系完全颠倒。
[e2805] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续遵循教程中的指示，并加载<任务>作为第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'，但此处语境下'continue'作动词需结合上下文，主要问题在于'load'译为'加载'虽可接受，但'first task'后多出的'作为'导致语义冗余，且'corporation'译为'公司'略显生硬，建议统一为'企业'或'公司'，整体无明显 CRITICAL 错误，但存在 MAJOR 级术语和语感问题。
[e2832] Isolated Inhale_Data/resources.assets:asset#resources.assets#1370/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（如'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e2855] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_CONTINUE_BIND
  原文：Premi <Key><KeyBind></> per continuare...
  译文：按 <Key><KeyBind></> 继续
  问题：语义一致性——译文严重篡改原文含义，将“继续”误译为“获得奖励”，且错误地添加了原文不存在的“获得奖励”信息，导致语义完全错误。
[e2857] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_INTRO
  原文：<Task>SOGGETTO 01</>
Stato: <Inactive>Sconosciuto</>

<Error>Errore</>: Il protocollo eseguito non può essere continuato
  译文：主体
  问题：术语一致性——否定词'cannot'被误译为'无法'导致语义偏差，且关键术语'Subject'误译为'对象'，'Protocol'误译为'协议'，严重偏离游戏行业标准译法。
[e2869] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_WORKSHOP
  原文：Acceso al <Key>workshop</> sulla stazione Shipyard
  译文：工作间
  问题：术语一致性——译文严重偏离原文含义，将'Access'（访问/进入）误译为'访问权限'，将'workshop'（工作间/工坊）误译为'研讨会'，且遗漏了介词结构导致语义混乱。
[e2906] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_BUILDING
  原文：Premi <Key><KeyBind></> per entrare nella modalità interni.
  译文：按 <Key><KeyBind> 键进入内部模式。
  问题：术语一致性——原文为意大利语游戏指令，译文将游戏术语误译为中文俚语，且完全丢失了原文含义。
[e2907] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_EQUIPMENT
  原文：Premi <Key>[<KeyBind>]</> per entrare nel menu dell'equipaggiamento.
  译文：按 <Key>[<KeyBind>] 进入装备菜单
  问题：语义一致性——译文严重错误，将意大利语指令误译为中文游戏术语，且完全丢失了原文关于“按键进入菜单”的操作含义。
[e2908] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_FORM
  原文：Premi <Key>[<KeyBind>]</> per cambiare la fila.
  译文：按 <Key>[<KeyBind>] 切换行
  问题：语义一致性——原文为意大利语指令，译文完全错误，将操作指令误译为游戏货币，且严重违背术语规范。
[e2909] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_INTERACTION
  原文：Premi <Key>[<KeyBind>]</> per interagire.
  译文：按 [<Key>][<KeyBind>] 以进行交互。
  问题：术语一致性——术语使用错误，'Premi'应译为'按'而非'点击'，且原文为意大利语指令，译文未体现按键操作语境。
[e2910] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_KEYBOARD
  原文：Premi <Key>[<KeyBind>]</> per inviare.
  译文：按 <Key>[<KeyBind>]</> 键发送。
  问题：语义一致性——译文完全错误，将指令性文本误译为名词性说明，且丢失了关键动词'按'和'发送'的含义。
[e2911] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_PIN
  原文：Premi <Key>[1-9]</> per mettere il codice.
  译文：奖金 <Key>[1-9] 用于输入代码。
  问题：语义一致性——原文为意大利语，译文误将游戏指令“输入代码”翻译为“奖金”，导致语义完全错误且严重误导玩家。
[e2912] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_STEERING
  原文：Premi <Key>[<KeyBind>]</> per controllare la nave.
  译文：使用'按'或'按下'
  问题：术语一致性——原文为意大利语，译文误将意大利语单词当作英文单词处理，导致语义完全错误且术语混乱。
[e2928] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_SAVE_LOAD
  原文：Salva/Carica
  译文：保存/读取
  问题：术语一致性——术语使用错误，'Carica'在存档加载语境下应译为'读取'而非'上传'，且'Carica'本身为意大利语，原文应为'Carica'（加载）而非'Salva/Carica'的混合误译。
[e2960] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/DESC_TRASH
  原文：Spazzatura inutile. Vale di più quando compatta.
  译文：无用的垃圾。压缩后效果更好。
  问题：术语一致性——译文存在术语不规范及语序不自然问题，未完全符合游戏 UI 行业标准译法。
[e2962] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/DESC_TROPHY
  原文：Premio "Pilota dell'anno". Dato al pilota con nominativo Kirillfff.
  译文：奖项'年度最佳车手'。授予了名为 Kirillfff 的车手。
  问题：术语一致性——术语翻译不符合游戏行业标准，'Premio'应译为'奖项'而非'奖'，且原文专有名词'Pilota dell'anno'未采用标准译法'年度最佳车手'。
[e2965] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_DIALOG_1
  原文：Tutti i comandi attualmente disponibili sono mostrati qui. La loro disponibilità dipende dal compimento di alcune condiz
  译文：输入的命令必须至少与列表中的某个命令有 70% 的相似度。
  问题：语气与表达——原文为意大利语，译文为中文，但核心语义偏差在于将“至少与...有 70% 相似度”错误地翻译为“至少与...有 70% 的相似度”，导致量词冗余且不符合中文游戏 UI 表达习惯，虽未改变逻辑但不够地道。
[e3021] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_CONTINUE
  原文：Premi Invio per continuare...
  译文：继续提交奖励……
  问题：术语一致性——译文将游戏术语'Invio'（提交/输入）误译为'奖励'，且'Premi'（奖励）与'Invio'（提交）的逻辑关系被完全扭曲，导致语义错误。
[e3031] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_END_MSG
  原文：Questa è la fine della storia per ora. Più aggiornamenti in futuro! Questo progetto esiste solo grazie al vostro support
  译文：目前，这个故事就到此为止了。未来会有更多更新！这个项目的存在离不开你们的支持 <3
  问题：术语一致性——译文存在术语不规范（'情节'应为'故事'）及语序生硬问题，未完全传达原文轻松亲切的语气。
[e3046] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_INFRASOUND_NOTE
  原文：Aggiunge un leggero brontolio durante le sezioni di gioco spaventose per rendere più inquietante il gioco. Questo effett
  译文：在那些恐怖的游戏环节中，添加一些轻微的雷声轰鸣，以让游戏更加令人不安。
  问题：术语一致性——术语翻译错误，'brontolio'（雷声/轰鸣声）被误译为'抱怨声'，严重偏离游戏音效语境。
[e3111] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_ERR_FUEL
  原文：<Error>Errore</>: Valore di carburante critico
  译文：<Error>错误</>: 燃料临界值
  问题：术语一致性——术语使用不规范，'Errore'应统一译为'错误'而非保留原文'错误'，且'Valore di carburante critico'翻译为'临界燃料值'虽语义通顺但不够地道，建议采用更标准的游戏术语表达。
[e3128] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_INVESTIGATION
  原文：L'unità di massa di memoria è stata consegnata con successo.

Il tuo premio: <Key><Credits></> crediti.

Inoltre ti rega
  译文：内存块已成功交付。

您的奖励为：<Key><Credits></> 信用点。

此外，我还将授予您访问 <Key>工坊</>以及本站 <Key>补偿舱</>的权限。

现在，请开始完成 <Task>任务分配</>下的其他任务。
  问题：术语一致性——游戏术语翻译不符合行业标准，如'workshop'应译为'工坊'而非'研讨会'，'camera di compensazione'应译为'补偿舱'而非'补偿室'，且'任务分配者'非标准 UI 术语。
[e3129] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_ROUTINE
  原文：Premio.
• <Key><Credits></> crediti
• Ulteriore <Key>potenziamento dello scafo della nave</>
  译文：奖项。
• <Key><Credits>信用
• 此外 <Key>增强船舶
  问题：语言/术语——原文为意大利语，译文误译为中文，且关键术语'potenziamento'（增强/升级）被错误理解为'船体强度'，导致游戏机制含义偏差。
[e3135] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_FLASHLIGHT
  原文：Premi <Key><KeyBind></> per accendere o spegnere la torcia.
  译文：按<Key><KeyBind></>键开启或关闭手电筒。
  问题：语义一致性——原文为意大利语指令，译文完全错误地将其解读为中文支付费用，导致语义彻底颠倒且包含严重幻觉。
[e3145] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_INHALE
  原文：Inspirazione Isolata
  译文：灵感之源 或 孤立灵感
  问题：术语一致性——术语翻译不符合游戏 UI 行业标准，'Inspirazione Isolata' 作为游戏标题或状态名，直译为'独立灵感'不符合常规游戏术语规范，建议采用更通用的译法。
[e3208] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_NEW_PILOT_HINT
  原文：PER I NUOVI PILOTI:

<color=#ffffff>Mettetevi la tuta da pilota per vedere maggiori instruzioni.
  译文：针对新飞行员：

请穿上飞行员制服，以获取更多说明。
  问题：信息完整性——原文为意大利语，译文未翻译出原文语言，且“针对”一词未能准确传达“针对新飞行员”这一特定对象语境，存在信息缺失。
[e3246] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>标签</>中说明，我已经提供给你了。在这里交付被标记为 <Key>的容器</>。<Error>UNDER NO CIRCUMSTANCES</> 时不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语翻译错误，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中<Error>标签未正确转义为 HTML 实体。
[e3248] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>点信用以及最后的船体升级。
  问题：信息完整性——译文存在严重语病，'……'占位符导致句子断裂，且'出现为止'冗余，不符合游戏 UI 标准表达。
[e3254] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：很快，你就不会独自一人在飞船上了。我在那里留下了提示贴：<Task>氧气</Task>、<Task>燃料</Task> 和 <Task>太阳能电站</Task>。找到它们之后，你就会知道会发生什么了。
  问题：信息完整性——译文严重缺失关键信息，遗漏了原文中关于氧气、燃料和太阳能电站的具体位置提示，导致玩家无法理解任务目标。
[e3271] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：否定——译文将原文的否定含义（I have to）错误地处理为肯定陈述（确实如此），导致语义逻辑完全颠倒。
[e3274] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，且奖励列表格式缺失数值显示。
[e3276] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船上的'大规模内存单元'。
  问题：语义错误——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e3277] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问<工坊>。请按照指示行事。<工坊>升级你的飞船。
  问题：术语一致性——严重术语错误：将'workshop'误译为'研讨会'（应为'工坊'），将'upgrade'误译为'升级'（虽词义相近但语境不符，且原文指令结构混乱导致信息缺失）
[e3279] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将“因为不喜欢厨房的脏乱而搬进卧室”误译为“因为搬进卧室所以不喜欢”，导致人物关系与因果关系完全颠倒。
[e3281] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续遵循教程中的指示，并读取<Task>作为第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'导致逻辑不通，且'load'未规范译为'读取'。
[e3307] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：保留英文原文或译为标准技术术语'空引用异常'（若游戏风格允许），但必须确保上下文逻辑通顺，避免歧义。
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序正确识别。
[e3308] Isolated Inhale_Data/resources.assets:asset#resources.assets#1371/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e3324] Isolated Inhale_Data/resources.assets:asset#resources.assets#1372/json/TXT_INTRO
  原文：<Task>SUBJECT 01</>
状态： <Inactive>未知</>

<Error>错误</>：协议無法继续执行。需要新的执行者。

正在重启 <Key>協議 T</> 的執行。正在准备一个冷凍仓。

<Task>SUBJECT
  译文：协议无法继续执行。需要新的执行者。

正在重启 <Key>协议 T</> 的执行。正在准备一个冷冻仓。
  问题：术语一致性——原文中'协议'被误译为'協議'（繁体/错别字），且'冷冻仓'误译为'冷凍仓'（繁体/错别字），严重违反术语一致性标准。
[e3356] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_INTRO
  原文：<Task>СУБ'ЄКТ 01</>
Статус: <Inactive>Невідомий</>

<Error>Помилка</>: Виконання протоколу не може бути продовжене. Потр
  译文：<Task>主体 01
  问题：术语一致性——术语翻译不统一，'СУБ'ЄКТ'译为'对象'不符合游戏行业标准，应统一为'主体'或'单元'；且译文末尾截断，信息不完整。
[e3366] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_CREDITS
  原文：<Key><Credits></> кредитів
  译文：致谢
  问题：术语一致性——原文为游戏货币单位“信用点”，译文误译为“致谢”，导致语义完全错误且术语严重不符。
[e3647] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_INVESTIGATION
  原文：Лог чіп було успішно доставлено.

Твоя нагорода: <Key><Credits></> кредитів.
Я також надаю тобі доступ до <Key>майстерні
  译文：将'工作室'改为'工坊'，'通道'改为'传送门'，'任务终端'改为'任务终端'。
  问题：术语一致性——术语翻译不符合行业标准，'мастерні'应译为'工坊'而非'工作室'，'шлюзу'应译为'传送门'而非'通道'，且'термінал завдань'未采用标准术语'任务终端'。
[e3648] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_ROUTINE
  原文：Нагорода:
• <Key><Credits></> кредитів
• Додаткове <Key>покращення корпусу корабля</>
  译文：金币
  问题：术语一致性——术语翻译不准确，'Credits' 在 RPG 语境下应译为'金币'而非'积分'，'покращення корпусу корабля'应译为'舰体升级'而非'外观改进'。
[e3655] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_ROW
  原文：Натисніть <Key>[<KeyBind>]</>, щоб змінити вибір. Використовуйте <Key>Колесо миші</> для контролю дистанції.
  译文：点击 <Key>[<KeyBind>]</> 即可更改所选选项。使用 <Key>鼠标滚轮</Key> 来控制距离。
  问题：术语一致性——术语翻译不统一，'Колесо миші' 应译为'鼠标滚轮'而非'鼠标滚轮'（此处原文已正确，但译文多了一个引号且前文'Колесо миші'未体现为游戏标准术语格式），且原文末尾截断导致信息不完整。
[e3689] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/CMD_JOB_RES
  原文：Твоя робота полягає в обслуговуванні космічних станцій. Уся необхідна інформація міститься в <Key>чіпах‑завданнях</>, як
  译文：你的任务就是维护太空站的运行。所有必要的信息都存储在<Key>任务芯片</>中，这些信息可以从<Key>任务终端</>中获取。
  问题：术语一致性——术语翻译不统一，'芯片'应为'芯片'，'终端'应为'终端'，且缺少'任务'二字导致语义不完整。
[e3726] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_SUBJECT_DATA
  原文：ДАНІ СУБ'ЄКТА:

Ідентифікатор: <Key>0<Index></>
Статус: <Command>Готовий</>
Позивний: <Inactive><Name></>
  译文：呼号
  问题：术语一致性——术语翻译不准确，'Позивний'（呼号/代号）被误译为'调用者'，且'Готовий'（就绪）译为'已准备就绪'略显冗余，未严格遵循游戏 UI 标准术语。
[e3769] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_DATA_EXISTS
  原文：Ігрові дані з позивним <Key><Value></> вже існують. Бажаєте їх перезаписати?
  译文：游戏数据
  问题：术语一致性——术语使用错误，'Игрові дані'应译为'游戏数据'而非'游戏数据'，且'перезаписати'应译为'覆盖'或'替换'而非'重新记录'，语气不符合游戏 UI 规范。
[e3777] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_CONT_INTRO
  原文：Твоя наступна ціль це поле <Task>контейнерів</>. Його координати описані на <Key>планшеті</>, який я тобі даю.

Достав <
  译文：在任何情况下
  问题：条件与因果——原文中'ЗА ЖОДНИХ ОБСТАВИН'意为'在任何情况下'，译文误译为'在静止状态下'，导致否定条件逻辑完全错误。
[e3806] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_ANY_REWARD_FIRST
  原文：Попри всі труднощі, тобі все ж вдалося вижити й виконати своє перше завдання. 

Ось твоя нагорода: 
• <Key><Credits></> 
  译文：点数
  问题：术语一致性——术语翻译不准确，'Credits' 译为'点积分'不符合游戏行业标准，应为'点数'或'信用点'；'corpus' 译为'角色外观'虽可理解但不够精准，通常对应'机体'或'载具'，需结合具体游戏类型确认，此处存在术语一致性风险。
[e3807] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_ANY_REWARD_THIRD
  原文：Минулого разу виникли технічні проблеми, тож я видаю тобі нагороду за два завдання:
• <Key><Credits></> кредитів;
• <Key
  译文：点
  问题：术语一致性——译文存在术语不规范（积分应为点数）、语序生硬及信息缺失（遗漏了“任务”二字），需修正以符合游戏本地化标准。
[e3808] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：质量存储单元
  问题：术语一致性——术语翻译严重错误，'mass memory unit' 误译为'大规模内存单元'，'docking bay'误译为'对接站'，且'pilot manual'误译为'操作手册'，不符合游戏行业标准译法。
[e3809] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：大容量存储器已成功交付。
注意：该目标未能摧毁那艘飞船……

正在执行解密操作……
正在进行验证……

任务已完成。
奖励：
• <Key><Credits></> 信用点；
• <Secret>“知识就是力量”的标语。

现在，我将允许您访问该<Task>工坊。请按照指示行事。<Task>升级你的飞船。
  问题：术语一致性——术语严重错误：'Mass memory unit' 译为'大容量内存单元'（应为'大容量存储器'或'内存模块'），且将游戏 UI 中的'workshop'误译为'研讨会'（应为'工坊'），'upgrade'误译为'升级'虽对但语境生硬，整体术语不符合游戏行业标准。
[e3811] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，因为它搬到了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将“不喜欢厨房里的灰尘垃圾”误译为“灰尘垃圾因为搬到了卧室”，导致人物关系与因果关系完全颠倒。
[e3824] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/LBL_DOCKING_NOTE
  原文：Controls are locked, press dock/undock
  译文：控件已锁定，请按 Dock/Undock 按钮。
  问题：术语一致性——译文过度解释且未遵循 UI 标准术语规范，导致信息冗余且不符合行业标准。
[e3838] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：保留原文'Null reference exception'或根据游戏风格采用标准技术译名'空引用异常'（若游戏支持中文技术术语），但需确保上下文逻辑正确。
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序正确识别。
[e3839] Isolated Inhale_Data/resources.assets:asset#resources.assets#1373/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e3864] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_INTRO
  原文：<Task>SUBJEKT 01</>
Status: <Inactive>Unbekannt</>

<Error>Fehler</>: Protokollausführung kann nicht fortgesetzt werden.
  译文：<Task>主题 01
状态：<Inactive>未知

<Error>错误：无法继续执行协议。需要新的执行者。

重新启动 <Key>T-协议执行。冷冻舱已准备就绪。

<Task>主题 02
状态：<Command>准备好了
  问题：术语一致性——术语严重错误，'Protokoll'误译为'日志'，'Vollstrecker'误译为'执行者'，'Kryokapsel'误译为'低温舱'，且'Protokollausführung'误译为'协议实施'，不符合游戏行业标准译法。
[e3869] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_PLANTED
  原文：Dieser Platz ist bereits gepflanzt
  译文：这个位置已经种好了。
  问题：语义一致性——原文指‘已种植’（可能指草坪或灌木），译文特指‘种树’，存在信息偏差且术语‘广场’对应‘Platz’不够精准。
[e3874] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_CREDITS
  原文：<Key><Credits></> Guthaben
  译文：存款
  问题：术语一致性——原文'Guthaben'指'存款/余额'，译文'致谢'完全错误，属于术语误用导致含义完全不同。
[e3876] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_WORKSHOP
  原文：Zugang zur <Key>Werkstatt</> der Werftstation
  译文：进入造船厂的<Key>车间</Key>
  问题：术语一致性——术语翻译不准确，'Werkstatt'在造船厂语境下应译为'车间'或'工坊'，但'Zugang zur'直译为'进入'比'访问'更符合游戏 UI 习惯，且原文结构未完全对应。
[e3880] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_FUEL_OBJ_PRODUCE
  原文：Produziere ein Treibstoff-Fass
  译文：生产一个燃料桶
  问题：术语一致性——译文严重错误，将德语专有名词'Fass'（桶/容器）误译为'燃料'，导致语义完全颠倒且产生重复。
[e3889] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_INV_OBJ_FLY
  原文：Fliege nah genug an das zerstörte Schiff heran
  译文：靠近那艘被摧毁的船只
  问题：术语一致性——原文为德语，译文缺失语言标识且未体现游戏 UI 语境，术语使用不规范。
[e3903] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_OXY_OBJ_DOCK
  原文：Docke an die Sauerstoffstation an
  译文：将文档连接到氧气发生器上
  问题：术语一致性——原文为德语，译文误将专有名词'Docke'（对接舱）译为'文档'，且未体现'氧气'含义，术语严重错误。
[e3907] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_OXY_OBJ_UNSEAL
  原文：Entsiegel einen beliebigen Gewächshausraum über das Kontrollpanel
  译文：通过控制面板解锁任意温室区域
  问题：语义错误——译文完全错误，将德语的“密封/锁定”误译为“照亮”，且严重违背游戏 UI 术语规范，将“Entsiegeln”（解锁/解除封印）错误理解为照明功能。
[e3910] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_TUT_OBJ_FIND
  原文：Finde die Aufgabenausgabe
  译文：请找到任务详情
  问题：术语一致性——原文为德语，译文误将德语单词'Aufgabe'（任务）与' Ausgabe'（输出/出版）混淆，导致语义完全错误且包含严重术语错误。
[e3913] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_TUT_OBJ_PRINT
  原文：Drucke den Task-Chip
  译文：点击任务芯片
  问题：术语一致性——术语使用错误，'Task-Chip' 在游戏语境中通常指任务道具或芯片，而非物理打印设备，且动词'打印'不符合游戏操作逻辑。
[e3978] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少需要与列表中的某个命令有 <color=#aaff>70% 的相似度。</color>
  问题：语义一致性——译文后半部分严重偏离原文含义，将'至少应相似'错误翻译为'至少应该如此'，导致信息缺失且逻辑不通。
[e4132] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_SOURCE
  原文：<Key>Quelle</>:
  译文：根据上下文确认该角色名，若确为'泉源'则译为'泉源'，若为特定 IP 角色请保留原译或采用官方译名。
  问题：术语一致性——原文为德语，译文将专有名词误译为中文通用词，导致游戏内角色名称丢失，严重破坏沉浸感。
[e4147] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_ROUTINE
  原文：Belohnung:
• <Key><Credits></> Guthaben
• Zusätzliches <Key>Schiffsrumpf Upgrade</>

  译文：余额
  问题：术语一致性——术语翻译不准确，'Guthaben'应译为'余额'而非'收益'，'Zusätzliches'应译为'额外的'而非'额外的'（此处虽对但需确认语境，主要问题在余额），且'Credits'作为游戏货币通常译为'信用点'或'金币'而非泛指的'收益'。
[e4154] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_ROW
  原文：Drücke <Key>[<KeyBind>]</> um die Auswahl zu ändern. Nutze das <Key>Mausrad</> um die Distanz zu steuern.
  译文：使用鼠标滚轮来更改选择范围。使用鼠标滚轮来控制距离。
  问题：人物关系——原文德语中 'Auswahl' 指具体选项，译文'选择范围'语义偏差；且原文第二句主语为'滚轮'，译文误将'鼠标'作主语，导致人物关系错误。
[e4159] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_CRITICAL_ERROR
  原文：Kritischer Fehler
  译文：严重错误
  问题：术语一致性——术语误用，'Kritischer' 在德语游戏语境中对应'严重'而非'批判性'，且'错误'一词冗余。
[e4236] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语误用，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e4273] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：在任何情况下都绝对不要打开这个容器。你不会喜欢里面的东西。
  问题：语气——原文中'UNDER NO CIRCUMSTANCES'意为'在任何情况下都绝对不要'，译文漏译了'绝对'，导致语气严重弱化，不符合游戏警告文本的严肃性要求。
[e4275] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：护盾升级
  问题：术语一致性——译文存在严重语病，'……'占位符导致句子断裂，且'船体升级'不符合游戏标准术语'护盾升级'。
[e4281] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：很快，你就不会独自一人在飞船上了。我在那里留下了提示贴：<Task>氧气</Task>、<Task>燃料</Task>和<Task>太阳能电站</Task>。找到它们之后，你就会知道会发生什么了。
  问题：信息完整性——译文严重缺失关键信息，遗漏了原文中关于氧气、燃料和太阳能电站的具体位置描述，导致玩家无法执行任务。
[e4298] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我现在应该已经死了才对。
  问题：人物关系——译文将原文的“我”误译为“确实如此”，导致人物关系颠倒，且语气过于书面化，不符合游戏对话场景。
[e4301] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e4303] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船上的'大规模内存单元'。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e4304] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该<任务>工坊。请按照指示行事。<任务>升级你的飞船。
  问题：术语一致性——译文严重偏离原文含义，关键术语（Workshop/Upgrade）及否定词（not）均错误，导致游戏逻辑与剧情完全混乱。
[e4306] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，因为它搬到了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将'不喜欢厨房里的灰尘和垃圾'错误翻译为'灰尘和垃圾因为它们搬到了卧室'，导致人物关系与因果逻辑完全颠倒。
[e4308] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续执行教程中的指示，并完成第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'，但此处语境下'continue following'指'继续执行'，主要问题在于'load'译为'加载'虽可接受，但'first task'后多出的'作为'导致语义冗余，且'corporation'译为'公司'略显生硬，建议统一为'企业'或'公司'，整体无明显 CRITICAL 错误，但存在 MAJOR 级术语和语序问题。
[e4320] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_DOCKING_NOTE
  原文：Controls are locked, press dock/undock
  译文：控件已锁定，请按下‘Dock’/‘Undock'。
  问题：术语一致性——译文过度解释且未遵循 UI 标准术语规范，导致信息冗余且不符合行业标准。
[e4334] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：空引用异常
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被玩家理解。
[e4335] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（如'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e4340] Isolated Inhale_Data/resources.assets:asset#resources.assets#1374/json/LBL_PILOT_MANUAL_4A
  原文：<b>PILOT SUIT</b>

Designed to provide easy access to the <color=#8BDFFF>pilot's interface</color>. Can protect you from
  译文：设计用于方便飞行员访问操作界面。既能保护你免受寒冷侵袭，但内部也会变得很热。
  问题：术语一致性——术语翻译不统一，'interface' 未采用游戏行业标准译法，且部分口语表达不够地道。
[e4351] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/CMD_GOAL
  原文：Pagaidām tavs mērķis ir sagatavot savu kuģi svarīgai misijai. Saskaņā ar maniem aprēķiniem, ņemot vērā pašreizējo kuģa a
  译文：Pagaid应当能够将其飞船用于重要的任务。根据我的估算，考虑到当前飞船的装备状况，成功的可能性大约在 <Key><Success>% 之间。
  问题：术语一致性——译文出现严重术语错误，将英文 UI 占位符 Key 和 Success 错误翻译为拉脱维亚语词汇，导致信息丢失且不符合行业标准。
[e4359] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_CONTINUE_BIND
  原文：Nospiediet <Key><KeyBind></> lai turpinātu...
  译文：停止等待 <Key><KeyBind>继续...
  问题：否定——原文为“继续”相关提示，译文误译为“停止”，语义完全相反且否定词缺失
[e4361] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_INTRO
  原文：<Task>SUBJEKTS 01</>
Statuss: <Inactive>Nezināms</>

<Error>Kļūda</>: Protokola izpildi nevar turpināt. Nepieciešams jau
  译文：协议无法继续执行。需要新的执行者。
  问题：否定——译文存在严重的否定词误译、人物/对象关系颠倒、术语错误及信息缺失，导致含义完全相反且无法使用。
[e4376] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：在任何情况下都绝对不要打开这个容器。你不会喜欢里面的东西。
  问题：否定——原文中'UNDER NO CIRCUMSTANCES'意为'绝对不要'，译文漏译了'绝对'，导致语气严重弱化，且原文末尾'Error'标签未正确保留。
[e4378] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>点奖励以及最后的船体升级。
  问题：信息完整性——译文严重缺失原文关键信息，且将原文中作为游戏术语的'Credits'误译为'……'，导致数值和奖励内容完全丢失。
[e4397] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_INV_RES_FAIL
  原文：<Error>Kļūda:</> Trūkst datu čipa.
Nav iespējams veikt verifikāciju.

  译文：<Error>问题：缺少数据芯片。
无法完成验证。
  问题：语义一致性——原文为拉脱维亚语，译文完全错误且未传达原文含义，属于严重语义错误。
[e4422] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_BUILDING
  原文：Nospiediet <Key>[<KeyBind>]</> lai ieietu interjera režīmā.
  译文：在“<Key>[<KeyBind>]</>”模式下，请输入命令。
  问题：语义一致性——原文为操作指令（点击某键进入模式），译文误译为状态描述（无法使用该命令），语义完全相反且丢失关键操作信息。
[e4423] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_EQUIPMENT
  原文：Nospiediet <Key>[<KeyBind>]</> lai atvērtu aprīkojuma izvēlni.
  译文：点击 <Key>[<KeyBind>]</> 打开装备菜单。
  问题：语义一致性——原文为拉脱维亚语，译文完全错误且未传达原文含义，属于严重语义错误。
[e4424] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_FORM
  原文：Nospiediet <Key>[<KeyBind>]</>, lai mainītu rindu.
  译文：停止等待 <Key>[<KeyBind]>，现在可以开始。
  问题：语气——原文为游戏内提示语，译文过度口语化且添加了原文不存在的“操作”二字，导致语气与语境不符。
[e4425] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_INTERACTION
  原文：Nospiediet <Key>[<KeyBind>]</>, lai mijiedarbotos.
  译文：不要等待 <Key>[<KeyBind>]>，否则程序将崩溃。
  问题：语义一致性——原文为立陶宛语，译文完全错误且未传达原文含义，属于严重语义错误。
[e4426] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_KEYBOARD
  原文：Nospiediet <Key>[<KeyBind>]</>, lai apstiprinātu.
  译文：继续翻译 <Key>[<KeyBind>], 请继续。
  问题：否定——否定词与动作完全颠倒，原文为“不暂停”（继续），译文误译为“暂停...请继续”，逻辑矛盾且严重违背原文指令。
[e4427] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_PIN
  原文：Nospiediet <Key>[1-9]</>, lai ievadītu kodu.
  译文：请按下 <Key>[1-9]>，然后输入代码。
  问题：否定与语义——原文为拉脱维亚语，译文将否定词'Nospiediet'（按/按）误译为'停止'，导致含义完全相反，且未识别出原文实际含义应为'按下'。
[e4429] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示芯片
  问题：术语一致性——译文存在术语不规范（如'提示贴'非标准 UI 用语）、信息缺失（未体现'chips'的具体含义）及标点格式错误。
[e4430] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_STEERING
  原文：Nospiediet <Key>[<KeyBind>]</>, lai vadītu kuģi.
  译文：不要等待 <Key>[<KeyBind>]，直接等待船只。
  问题：语义一致性——译文将原文的“等待”误译为“操作”，导致动作含义完全相反，属于严重的语义错误。
[e4487] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/DESC_TROPHY
  原文："Gada pilota" apbalvojums. Apbalvots pilots ar segvārdu Kirillfff.
  译文：保留原文'Gada pilota'或根据游戏设定译为'年度飞行员奖'，不可随意解释为'船'。
  问题：术语一致性——译文严重偏离原文，将游戏内特定奖项名称误译为普通词汇，且错误解释了专有名词含义。
[e4488] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/DESC_WEIRD_BOX
  原文：Tas nevar runāt, draudēt tev ar saduršanu vai just sāpes.
  译文：请勿奔跑，否则将因碰撞或疼痛而受到威胁。
  问题：语义一致性——原文为警告语（禁止奔跑、威胁车祸或疼痛），译文完全错误地变成了劝慰语（不要哭泣），语义完全相反且严重误导。
[e4490] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/LBL_DIALOG_1
  原文：Šeit tiek parādītas visas pašlaik pieejamās komandas. To pieejamība ir atkarīga no noteiktu nosacījumu izpildes.

Jums n
  译文：目前，所有可用的指令均已展示出来。这种可用性取决于特定条件的满足。\n您无需输入指令的精确格式。列表中至少有一个指令的相似性需达到<color=#aaff>70%</color>。
  问题：术语一致性——原文为游戏指令匹配机制说明，译文将“命令”误译为“命令”（中文语境下易歧义为军事指令），且“精确格式”译为“精确格式”略显生硬，未体现游戏 UI 中“格式”或“结构”的规范译法，存在术语与语感偏差。
[e4548] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：语气与语义偏差——译文将原文中强烈的自我否定与决绝语气弱化为口语化的确认，且“确实如此”严重偏离了原文“我必须这么做”的强制逻辑。
[e4622] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_ERR_FUEL
  原文：<Error>Kļūda</>: Kritisks degvielas līmenis
  译文：燃油不足
  问题：语义一致性——原文为游戏错误提示，译文将错误信息误译为哲学/文学概念，完全偏离原意。
[e4637] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e4638] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e4649] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_INV_OBJ_TALK
  原文：Runājiet ar botu-asistentu
  译文：请使用机器人助手
  问题：术语一致性——术语使用错误，'botu-asistentu'应译为'机器人助手'而非'机器人助理'，且'Runājiet'在 UI 语境下通常指'启动'或'使用'而非字面'运行'。
[e4652] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船上的'大规模内存单元'。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e4653] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该<Task>工坊。请按照指示行事。<Task>升级你的飞船。
  问题：术语一致性——原文中'workshop'被误译为'研讨会'，严重偏离游戏 UI 语境（应为'工坊'），且'access to'后的介词结构导致译文逻辑混乱，信息缺失。
[e4655] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我的厨房里的灰尘和垃圾，因为它已经搬到了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将“因为”误译为“因为”，导致人物关系与因果关系完全颠倒，且关键信息缺失。
[e4658] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/SEQ_TUT_START_REPLY
  原文：Laipni lūgts kuģu būvētavas stacijā, <Key><Name></>! Tagad tu esi viens no korporācijas pilotiem. Tavs kuģis gaida tevi 
  译文：请在飞船建造厂的停靠站登记，<Key><Name></>！现在你就是这家公司的飞行员之一了。你的飞船正在那里等待你。
  问题：语义一致性——原文指代“飞船停靠站”，译文误译为“飞船的停靠站”，导致语义逻辑混乱；且原文“等待你”译为“载着你前往”改变了被动等待的语境。
[e4660] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_FLASHLIGHT
  原文：Nospiediet <Key>[<KeyBind>]</> lai ieslēgtu lukturi.
  译文：取消对 <Key> 的悬停效果。
  问题：语义一致性——原文为立陶宛语，意为“取消对按键的悬停效果”，译文完全错误且未传达原文含义。
[e4661] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_ROW
  原文：Nospiediet <Key>[<KeyBind>]</>, lai mainītu izvēli. Izmantojiet <Key>peles ritenīti</>, lai regulētu attālumu.
  译文：点击 <Key>[<KeyBind>]</> 即可更改选项。使用 <Key>鼠标滚轮</> 来调节距离。
  问题：术语一致性——译文严重偏离原文含义，将“鼠标滚轮调节距离”错误翻译为“耳机图标调节延迟”，涉及术语误用与信息完全错误。
[e4693] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/CMD_GOAL_RES
  原文：Pagaidām tavs mērķis ir sagatavot savu kuģi svarīgai misijai. Saskaņā ar maniem aprēķiniem, ņemot vērā pašreizējo kuģa a
  译文：根据上下文推测原文意为："稍后你将准备飞船执行重要任务。根据我的计算，考虑到当前飞船的装备状况，成功几率约为 <Key><Success>%。"
  问题：语义一致性——译文出现严重乱码，将原文拉脱维亚语错误翻译为中文，且未处理占位符，导致信息完全丢失。
[e4694] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/CMD_JOB_RES
  原文：Tavs uzdevums ir uzturēt kosmosa stacijas. Visa nepieciešamā informācija atrodas <Key>uzdevumu čipos</>, kurus var iegūt
  译文：该任务涉及维持太空站。所有必要信息均在<Key>任务芯片</>中，可通过<Key>任务终端</>获取。
  问题：语义一致性——译文严重偏离原文，包含大量无意义的机器翻译错误、乱码及完全错误的术语替换，导致语义完全混乱。
[e4695] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/CMD_SPEC_RES
  原文：Tu esi pabeidzis pagaidām visus pieejamos uzdevumus. Lieliski pastrādāts, <Key><Name></>. Es tev dodu <Key>pēdējo korpus
  译文：你将等待新任务。
  问题：语义一致性——译文严重偏离原文含义，将“等待新任务”误译为“从事更合适的工作”，且将“不要摧毁”误译为“肯定不会错过”，人物关系与任务逻辑完全颠倒。
[e4713] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/DESC_CANNED_FISH
  原文：Izgatavots no mākslīgi audzētām kosmosa zivīm. Tam ir ļoti ilgs derīguma termiņš.
  译文：伊兹加塔沃茨无法以生物方式培育。其保质期极长。
  问题：语义一致性——译文完全错误，将原文关于“鱼”的陈述误译为“探索宇宙”，且严重误解了否定词含义，导致语义彻底颠倒。
[e4731] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_SUBJECT_DATA
  原文：SUBJEKTA DATI:

Identifikators: <Key>0<Index></>
Statuss: <Command>Gatavs</>
Segvārds: <Inactive><Name></>
  译文：数据对象：
标识：<Key>0<Index></>
状态：<Command>Gatavs</>
名称：<Inactive><Name></>
  问题：术语一致性——原文 Latvian 单词'Identifikators'误译为中文'标识符'（应为'标识'或'ID'），且'Statuss'存在拼写错误未修正，术语与原文对应关系不准确。
[e4738] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/LBL_DOCKING_NOTE
  原文：Controls are locked, press dock/undock
  译文：控件已锁定，请按下'Dock'/'Undock'按钮。
  问题：术语一致性——译文将游戏术语 Dock/Undock 误译为“操作”，导致信息缺失且不符合行业标准译法。
[e4746] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/LBL_NEW_PILOT_HINT
  原文：JAUNAJIEM PILOTIEM:

<color=#ffffff>Uzvelciet pilota tērpu, lai skatītu turpmākus norādījumus.
  译文：若确认飞行员身份，则查看后续指示。
  问题：条件与因果——原文为条件句（若...则...），译文误译为祈使句（请确认...），导致逻辑关系错误。
[e4786] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/LBL_NO_CHIPS
  原文：<Key>Nav pieejamu čipu!</>
Ievietojiet jaunus čipus sānā, lai atjaunotu.
  译文：无法安装芯片了！
  问题：信息完整性——译文严重偏离原文，将游戏 UI 提示误译为小说叙事段落，且包含原文不存在的虚构情节。
[e4788] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_DATA_EXISTS
  原文：Spēles dati ar segvārdu <Key><Value></> jau pastāv. Vai vēlaties tos pārrakstīt?
  译文：游戏数据与密码 <Key><Value> 已存在。是否要覆盖？
  问题：语义一致性——译文完全偏离原文，将“游戏数据已存在”错误翻译为“有趣且富有挑战性的游戏”，且严重篡改了用户输入框的提示功能，导致语义彻底错误。
[e4789] Isolated Inhale_Data/resources.assets:asset#resources.assets#1375/json/TXT_RESET_DATA_WARN
  原文：Vai tiešām vēlaties atiestatīt mijiedarbības datus? Padomi un ievada instrukcijas tiks rādītas vēlreiz.
  译文：你真的想重置交互数据吗？提示和说明将再次显示。
  问题：术语一致性——原文为 Latvian 语言，译文为中文，存在严重的语言错误；且“放弃保存”与“重置数据”含义不符，术语使用错误。
[e4801] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_CONTINUE_BIND
  原文：Prima <Key><KeyBind></> para continuar...
  译文：Prima <Key><KeyBind></> 以继续……
  问题：术语一致性——译文将英文动词 continue 误译为名词‘继续’，导致语义不通且不符合游戏 UI 规范，应使用动词‘继续’。
[e4803] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_INTRO
  原文：<Task>SUJEITO 01</>
Estado: <Inactive>Desconhecido</>

<Error>Erro</>: A execução do protocolo não pode ser continuada. 
  译文：请重新启动<Key>程序 T</>的执行。同时准备冷冻舱。
状态：<Command>就绪</>
  问题：术语一致性——术语翻译不统一，'Protocol' 译为'协议'不符合科幻/游戏语境，且'Command'状态译法不够地道。
[e4815] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_WORKSHOP
  原文：Acesso à <Key>oficina</> na estação do Estaleiro
  译文：访问造船厂站上的<Key>车间>
  问题：术语一致性——术语翻译不准确，'oficina' 在造船厂语境下应译为'车间'或'工作区'而非'工坊'，且原文'na estação do Estaleiro'结构未完全对应。
[e4855] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_BUILDING
  原文：Prima <Key>[<KeyBind>]</> para entrar no modo de interior.
  译文：Prima <Key>[<KeyBind>]</> 用于进入内部模式。
  问题：语言匹配——原文为葡萄牙语，译文误译为中文且未翻译专有名词 Prima，导致语言不匹配且信息缺失。
[e4856] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_EQUIPMENT
  原文：Prima <Key>[<KeyBind>]</> para abrir o menu de equipamento.
  译文：Prima <Key>[<KeyBind>]</>用于打开装备菜单。
  问题：信息完整性——原文为葡萄牙语，译文误译为中文且未翻译专有名词 Prima，导致信息缺失且术语不规范。
[e4857] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_FORM
  原文：Prima <Key>[<KeyBind>]</> para mudar a fila.
  译文：Prima <Key>[<KeyBind>]</>用于切换队伍。
  问题：术语一致性——术语翻译不准确，'fila'在游戏语境下应译为'队伍'而非'队列'，且'para'未准确传达为'用于'的对应功能描述。
[e4859] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_KEYBOARD
  原文：Prima <Key>[<KeyBind>]</> para enviar.
  译文：Prima <Key>[<KeyBind>]</> 用于发送。
  问题：语气——原文为祈使句指令，译文误译为陈述句，导致语气不符且指令感缺失。
[e4860] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_PIN
  原文：Prima <Key>[1-9]</> para introduzir o código.
  译文：请使用 Prima <Key>[1-9]</> 来输入代码。
  问题：信息完整性——原文语法结构混乱导致语义缺失，且译文标点错误将原文括号误写为双括号，严重破坏指令可读性。
[e4861] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_STEERING
  原文：Prima <Key>[<KeyBind>]</> para controlar a nave.
  译文：Prima <Key>[<KeyBind>]</> 用于控制飞船。
  问题：术语一致性——术语使用错误，'nave'（飞船）被误译为'导航'，且'para'（用于）的对应词选择不当，未体现游戏 UI 标准术语规范。
[e4877] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_SAVE_LOAD
  原文：Gravar/Carregar
  译文：保存/加载
  问题：术语一致性——术语严重错误，'Gravar'应译为'保存'而非'录制'，'Carregar'应译为'加载'而非'加载'（此处虽字面似对，但结合游戏语境，Gravar作为存档功能译为录制属于核心术语误用，导致功能含义偏差）。
[e4888] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/DESC_CEREAL_BOX
  原文：Feito de grãos espaciais. Parece fixe, mas ainda é cereal.
  译文：由太空颗粒制成。看起来很稳定，但实际上仍然属于谷物。
  问题：语义一致性——原文为游戏内虚构设定描述，译文错误地将“谷物”解释为现实中的“食品”，导致语义偏差且破坏游戏世界观。
[e4915] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_DIALOG_1
  原文：Todos os comandos atualmente disponíveis são mostrados aqui. A sua disponibilidade depende no cumprimento de certas cond
  译文：你不需要输入任何完整的命令。只需输入与列表中某一条命令 70% 相似的内容即可。
  问题：信息完整性——译文存在严重信息缺失与逻辑错误，将'70% 相似'误译为'70% 相似列表中的一条命令'，导致语义不通且丢失原文关键信息。
[e4916] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_DIALOG_2
  原文：Agora introduz o comando <color=#fad096>“Test”</color>, por exemplo.
  译文：现在，请输入命令'Test'，例如。
  问题：语义一致性——译文将原文的示例说明误作命令内容，导致语义偏差且破坏游戏指令逻辑。
[e4984] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_END_MSG
  原文：Este é o fim da história por agora. Mais em futuras atualizações! Este projeto ainda existe graças ao vosso apoio <3
  译文：目前，本故事暂时告一段落。更多内容将在未来更新中呈现！感谢大家的支持，让这个项目得以延续 <3
  问题：术语一致性——术语使用不规范，'Start'未出现但'Continue'对应'继续'正确，然而'End of story'译为'故事的讲述'过于文学化，不符合游戏 UI 简洁风格，且'vosso'（葡萄牙语）未体现为中文语境下的'你们'，整体语气偏书面。
[e4985] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_END_STATS
  原文：Sinal de chamada: <0>
Tempo jogado: <1>
Créditos ganhos: <2>
Créditos máximos: <3>
Mortes: <4>
Pontuação: <5>
  译文：统一译为'金币'或'积分'，例如：<2>获得的金币，<3>最高金币，<5>得分
  问题：术语一致性——术语翻译不统一，'Créditos' 在中文游戏语境下应统一为'金币'或'积分'，而非混用'积分'和'得分'；'Mortes' 译为'死亡次数'略显生硬，建议统一为'死亡数'。
[e4998] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_INFRASOUND_NOTE
  原文：Adiciona ruídos suaves durante secções para desconforto.
Este efeito é apenas percetível com bons alto-falantes ou auscu
  译文：在某些章节中添加了轻柔的噪音，以营造不适感。
这种效果只有在使用优质的扬声器或耳机时才能感知到。
<color=#F36D6D>注意：</color> 可能会引起头痛或使房间产生晃动。
  问题：术语一致性——术语翻译不准确，'secções'应译为'章节'而非'段落'，且'auscultadores'（助听器）未准确对应'耳机'的语境。
[e5000] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_INTERIOR_MODE
  原文：Modo de Interior
  译文：室内模式
  问题：语义一致性——译文添加了原文不存在的“装饰”概念，导致语义偏差。
[e5066] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_ERR_FUEL
  原文：<Error>Erro</>: Valor crítico de combustível
  译文：<Error>Erro>: 燃料临界值
  问题：术语一致性——术语使用不规范，'Valor crítico'未准确对应行业标准译法，且'关键值'表述生硬。
[e5085] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_INVESTIGATION
  原文：A unidade de memória de massa foi entregue com sucesso.

A tua recompensa: <Key><Credits></> créditos.
Também vou-te dar
  译文：工坊
  问题：术语一致性——术语严重错误，'oficina'误译为'工作室'（应为'工坊'或'修理站'），'câmara de descompressão'误译为'压缩室'（应为'减压室'），且'dispensador de tarefas'误译为'任务分配器'（应为'任务发布台'或'任务分发器'）。
[e5086] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_ROUTINE
  原文：Recompensa:
• <Key><Credits></> créditos
• Nova <Key>melhoria do casco da nave</>
  译文：金币
  问题：术语一致性——原文'Créditos'指游戏内货币（金币/积分），译文'致谢'严重误译；'Nova'作为形容词修饰'改进'，译文'新的'虽可通但略显生硬，整体术语与语境不符。
[e5092] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_FLASHLIGHT
  原文：Pressiona <Key>[<KeyBind>]</> para mudar a lanterna.
  译文：按下 <Key> [<KeyBind>] 以打开手电筒。
  问题：语义一致性——译文严重偏离原文含义，将“切换/打开”误译为“更改样式”，且遗漏了“打开”这一核心动作。
[e5093] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_ROW
  原文：Pressiona <Key>[<KeyBind>]</> para mudar a seleção. Usa a <Key>Roda do rato</> para controlar a distância.
  译文：使用鼠标滚轮来调整选择范围。
  问题：术语一致性——原文为葡萄牙语，译文为中文，但存在严重的术语误用（'Roda do rato'译为'移动距离'而非'滚动距离'）及信息缺失（译文末尾截断）。
[e5125] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/CMD_JOB_RES
  原文：O teu trabalho é manter as estações espaciais. Toda a informação necessária está contida nos <Key>task chips</>, que pod
  译文：移除多余符号，修正为：所有必要的信息都存储在<Key>任务芯片</Key>中
  问题：信息完整性——译文将原文葡萄牙语中的'任务芯片'（task chips）错误地翻译为中文'任务芯片》'，多出了多余的右书名号符号，导致 UI 显示文本格式错误且信息不完整。
[e5146] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/DESC_FIRST_AID_KIT
  原文：Cura feridas. Tem <color=#ffa555>5</color> usos.
  译文：处理伤口。剩余 5 次使用机会。
  问题：语义一致性——译文将游戏机制中的'使用次数'错误地翻译为'用途种类'，导致语义严重偏差。
[e5147] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/DESC_FIRST_AID_PACK
  原文：Cura feridas. Uso <color=#ffa555>único</color>.
  译文：处理伤口。我使用 <color=#ffa555>唯一</color> 的治疗。
  问题：语义一致性——译文将原文中强调该技能“唯一性”的形容词误译为名词性质的‘方法’，导致语义偏差且不符合游戏 UI 简洁风格。
[e5161] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_SUBJECT_DATA
  原文：DADOS DO SUJEITO:

Identificador: <Key>0<Index></>
Status: <Command>Pronto</>
Nome de chamada: <Inactive><Name></>
  译文：别名
  问题：术语一致性——术语翻译不准确，'Nome de chamada' 译为'调用名称'不符合游戏 UI 标准，应为'别名'或'代号'。
[e5170] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_NEW_PILOT_HINT
  原文：PARA NOVOS PILOTOS:

<color=#ffffff>Coloca o fato de piloto para ver mais instruções.
  译文：将飞行员信息放入，以查看说明。
  问题：语义一致性——原文为葡萄牙语，译文完全错误且未传达原文含义，属于严重语义错误。
[e5201] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_NO_CHIPS
  原文：<Key>Sem chipes disponíveis!</>
Insere novos chipes na lateral para restaurar.
  译文：可用的芯片已耗尽！请在侧面插入新芯片以进行恢复。
  问题：语义一致性——译文将原文的“恢复”功能误译为“用完了”，导致语义完全错误，且未体现插入新芯片的操作指令。
[e5211] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_CONT_INTRO
  原文：O teu próximo objetivo é o <Task>campo de contentores</>. As suas coordenadas estão indicadas no <Key>tablet</> que te v
  译文：你的下一个目标就是…… <Task>“容器场”或“容器区域”。其坐标已标明在 <Key>我将把平板电脑交给你。\n\n请复制到这里。 <Key>已标记的容器。\n\n<Error>在某些特定情况下，你不应该打开那个容器。你不会喜欢里面装有什么东西的。
  问题：术语一致性——原文中'contentores'为拼写错误（应为containers），译文将其误译为'Contentores'并保留为专有名词，导致术语错误且未传达'容器'的正确含义；同时'contentor marcado'译作'已标记的内容器'虽勉强通顺，但结合上下文'contentores'的严重拼写错误，整体术语一致性严重受损，且'contentor'在葡萄牙语中明确指'容器'，译文未能准确对应游戏术语标准。
[e5213] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_CONT_REWARD
  原文：Bom trabalho, <Nickname>. Vou dar-te <Key><Credits></> créditos e a última melhoria do casco.

Não existem mais trabalho
  译文：干得不错，<Nickname>。我会给你<Key><Credits>以及船体的最后一次改进。
  问题：信息完整性——译文严重缺失关键信息，导致语义不完整且语气生硬，不符合游戏 UI 标准。
[e5219] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_MSG_NOTE_CHIPS
  原文：Em breve não estarás sozinho na nave. Eu deixei chipes de notas nas estações de <Task>oxigénio</>, <Task>combustível</> 
  译文：很快，你就不会独自一人在飞船上了。我在各个站点留下了便签：氧气站、燃料站和太阳能站。找到它们之后，你就会知道该期待什么了。
  问题：信息完整性——译文严重缺失原文关键信息，导致任务指令不完整且术语使用错误。
[e5235] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须。
  问题：否定——译文将原文的否定含义（I have to）误译为肯定（确实如此），导致语义完全相反。
[e5238] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e5240] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：质量存储单元
  问题：术语一致性——术语翻译严重错误，'mass memory unit' 误译为'大规模内存单元'，'docking bay'误译为'对接站'，且'pilot manual'误译为'操作手册'，不符合游戏行业标准译法。
[e5241] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：大容量存储器已成功交付。
注意：该目标未能摧毁那艘飞船……

正在执行解密操作……
正在进行验证……

任务已完成。
奖励：
• <Key><Credits></> 信用点；
• <Secret>“知识就是力量”的标语。

现在，我将允许您访问该任务工坊。请按照指示升级您的飞船。
  问题：术语一致性——术语严重错误：'Mass memory unit' 译为'大容量内存单元'（应为'大容量存储器'或'内存模块'），且关键 UI 术语如'workshop'、'upgrade'、'credits'、'key'均使用中文直译而非游戏行业标准译法。
[e5245] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续执行教程中的指示，并加载第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'），且'load'译为'加载'虽可接受但语境下'加载任务'略显生硬，整体语气不够游戏化。
[e5272] Isolated Inhale_Data/resources.assets:asset#resources.assets#1376/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Ativa o <color=#8BDFFF>painel de piloto</color>
<color=#bbbb>2.</color> Prime
  译文：启用 飞行员控制面板
按下 脱离按钮
等待飞船离开 停靠区域

如果正在使用某种设备，请移除该设备。
装备 空间护盾
确保飞船 静止不动（无移动或旋转）
按下 解锁按钮
  问题：术语一致性——译文严重混入葡萄牙语原文，且关键术语（如“脱离按钮”、“空间事实”）翻译错误，导致游戏指令完全不可用。
[e5289] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/CMD_STOP_FAIL
  原文：<Error>Error:</> No se encontró una secuencia para detener.
  译文：错误：未检测到停止序列。
  问题：术语一致性——术语使用不当，'sequence'在游戏语境中通常指'序列'或'链'，而非'停止序列'，且'无法找到'表述生硬，不符合游戏本地化习惯。
[e5344] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_FORM
  原文：Presiona <Key>[<Keybind>]</> para cambiar la fila.
  译文：按 <Key>[<Keybind>]</> 以切换行。
  问题：术语一致性——原文为西班牙语“按”，译文误译为中文“点击”，导致操作指令错误。
[e5345] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_INTERACTION
  原文：Presiona <Key>[<Keybind>]</> para interactuar.
  译文：按 <Key>[<Keybind>] 以进行交互。
  问题：术语一致性——术语翻译不统一，'Presiona'应译为'按'而非'点击'，且未保留原文的西班牙语动词形式以符合游戏本地化规范。
[e5365] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_SAVE_LOAD
  原文：Guardar/Cargar
  译文：保存/读取
  问题：术语一致性——术语使用错误，'Guardar'应译为'保存'，'Cargar'应译为'读取'或'载入'，而非'加载'。
[e5399] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_DIALOG_2
  原文：Ahora ingrese el comando <color=#fad096>“Test”</color>, por ejemplo.
  译文：现在，请输入命令“测试”，例如。
  问题：信息完整性与结构——译文严重破坏原文结构，将示例内容错误地嵌入命令名称内部，导致语义混乱且不符合游戏 UI 规范。
[e5422] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/ITEM_HYENA_PLUSH
  原文：Peluche de Hiena
  译文：鬣狗毛绒玩具
  问题：术语一致性——原文'Hiena'指鬣狗，译文'鸵鸟'物种错误，导致语义完全偏差。
[e5461] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_CULL_INTERIORS
  原文：Sacrificio de Interiores
  译文：房间存档
  问题：术语一致性——术语严重误用，'Sacrificio' 在游戏语境下应为'存档'而非'牺牲'，且'Interiores'译为'内部'不符合存档位置描述习惯。
[e5483] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_INFRASOUND_NOTE
  原文：Añade un sutil retumbo durante las escenas de terror para aumentar la inquietud.

Este efecto solo se notará con buenos 
  译文：可能会让某些人感到头痛，甚至导致房间震动。
  问题：语义一致性——译文严重偏离原文含义，将“头痛”误译为“气氛紧张”，属于信息错误。
[e5535] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_TGL_CROUCH
  原文：Activar/desactivar Agacharse
  译文：启用/禁用 下蹲
  问题：术语一致性——术语使用不规范，游戏 UI 中'Agacharse'应译为'下蹲'而非'蹲下'，且'Activar/desactivar'在技能语境下通常译为'启用/禁用'或'开启/关闭'，'激活/禁用'略显生硬。
[e5537] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_TGL_SPRINT
  原文：Activar/desactivar Correr
  译文：移动
  问题：术语一致性——术语使用不规范，'Correr'在UI语境下应译为'移动'或'奔跑'，而非'运行'；'Activar/desactivar'作为开关按钮，'激活/关闭'语感生硬，建议改为'开启/关闭'。
[e5543] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_ERR_FUEL
  原文：<Error>Error</>: Valor crítico de Combustible
  译文：错误：燃料阈值
  问题：术语一致性——术语翻译不准确，'关键值'未对应游戏 UI 标准术语，且'燃料的关键值'语序生硬。
[e5566] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_ROW
  原文：Pulse <Key>[<KeyBind>]</> para cambiar la selección. Utilice <Key>Rueda de desplazamiento</> para controlar la distancia
  译文：使用 <Key>鼠标滚轮</>
  问题：术语一致性——术语翻译严重错误，'Rueda de desplazamiento'（鼠标滚轮）被误译为'滑鼠滾輪'，且原文为西班牙语，译文未体现语言转换逻辑。
[e5632] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_SUBJECT_DATA
  原文：SUBJECT DATA:

Identifier: <Key>0<Index></>
Status: <Command>Ready</>
Call sign: <Inactive><Name></>
  译文：Subject: 主体/对象；Identifier: 标识 ID；Call sign: 呼号
  问题：术语一致性——术语翻译不统一，'Subject' 未采用游戏行业标准译法'主题'，且'Identifier'、'Call sign'等术语未使用行业通用译法。
[e5647] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致含义完全错误。
[e5684] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器</>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西的。
  问题：术语一致性——术语翻译错误，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中<Error>标签未正确转义导致显示异常。
[e5686] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：护盾升级
  问题：术语一致性——译文存在严重语病，'……'占位符导致句子断裂，且'船体升级'不符合游戏标准术语'护盾升级'，同时'出现为止'冗余累赘。
[e5692] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示卡
  问题：术语一致性——译文存在术语不规范、标点缺失及信息完整性问题，需修正以符合行业标准。
[e5709] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我现在应该已经死了才对。
  问题：人物关系——译文将原文的“我”误译为“确实如此”，导致人物关系颠倒，且语气过于书面化，不符合游戏 UI 对话的口语特征。
[e5712] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e5714] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船的<Task>大规模内存单元</>。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（毁坏）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e5715] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该<任务>工坊。请按照指示行事。<任务>升级你的飞船。
  问题：术语一致性——原文中'workshop'被误译为'研讨会'，导致游戏内任务指令含义完全错误，且'upgrade'后的句式结构混乱，严重破坏游戏逻辑。
[e5717] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：条件与因果——译文严重违背原文逻辑，将“因为不喜欢厨房的脏乱而搬进卧室”误译为“因为搬进卧室导致厨房脏乱”，人物关系与因果关系完全颠倒。
[e5719] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续遵循教程协议，并读取<Task>作为第一个任务。
  问题：术语一致性——术语使用不规范（Resume 误译为继续而非继续/恢复，Load 误译为加载而非读取），且存在标点错误导致句子结构混乱。
[e5745] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null Reference Exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被玩家理解。
[e5746] Isolated Inhale_Data/resources.assets:asset#resources.assets#1377/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e5762] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/CMD_GOAL
  原文：Şimdilik hedefin önemli bir görev için gemini hazırlamak. Hesaplamalarıma göre elimizdeki teçhizatla başarı şansımız yak
  译文：将译文翻译为土耳其语："Şimdilik hedefin önemli bir görev için gemini hazırlamak. Hesaplamalarıma göre elimizdeki teçhizatla başarı şansımız yaklaşık <Key><Success>%".
  问题：语言匹配——原文为土耳其语，译文为中文，存在严重的语言不匹配错误，且原文中未出现“相关装备”这一具体指代，译文擅自添加了原文没有的信息。
[e5765] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/CMD_STOP_FAIL
  原文：<Error>Hata:</> Durdurulacak bir sekans bulunamadı.
  译文：无法找到可暂停的序列。
  问题：术语一致性——术语使用错误，'Durdurulacak' 指可暂停的序列，而非帧，且'帧'为误译。
[e5770] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_CONTINUE_BIND
  原文：Devam etmek için <Key>[<KeyBind>]</> bas...
  译文：继续，请按 <Key>[<KeyBind>]</>…
  问题：术语一致性——术语'Continue'误译为'要继续'，未使用行业标准译法'继续'，且原文省略号与译文省略号符号不一致。
[e5772] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_INTRO
  原文：<Task>DENEK 01</>
Durum: <Inactive>Bilinmiyor</>

<Error>Hata</>: Protokol yürütülmeye devam ettirilemez. Yeni yürütücü 
  译文：T 协议；冷冻舱
  问题：术语一致性——术语翻译不统一，'T 协议'未采用标准译法，且'低温胶囊'不符合游戏 UI 规范术语。
[e5784] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_WORKSHOP
  原文：Tershanedeki <Key>atölyeye</> erişim
  译文：访问位于 Tershan 的 <Key>工作室
  问题：语义一致性——原文为土耳其语，译文将专有名词'Tershanedeki'误译为中文'位于 Tershan'，导致地名与介词结构混乱，且未正确识别原文中'Tershan'作为地名后缀的归属关系，造成语义严重偏差。
[e5799] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_INV_RES_FAIL
  原文：<Error>Hata:</> Kayıt çipi eksik. Doğrulama yapılamıyor.

  译文：<Error>Hata>: 缺少存档芯片。无法读取存档。
  问题：术语一致性——术语使用不规范，'Kayıt çipi'未统一为行业标准译法'存档芯片'，且'验证'在存档语境下通常译为'读取'或'加载'。
[e5825] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_EQUIPMENT
  原文：Ekipman menüsünü açmak için <Key>[<KeyBind>]</> bas.
  译文：要打开装备菜单，请按 <Key>[<KeyBind>]</>。
  问题：术语一致性——原文拼写错误'Ekipman'应为'Equipment'，译文未修正此拼写错误导致术语不规范，且'设备菜单'对'Equipment Menu'的译法在特定语境下可能不够精准（通常为'装备菜单'）。
[e5828] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_KEYBOARD
  原文：Onaylamak için <Key>[<KeyBind>]</> bas.
  译文：为了取消/停止 <Key>[<KeyBind>]</> 按。
  问题：否定——否定词误译导致含义完全相反，原文意为“按...键以取消/停止”，译文却变成了“按...键以表示同意”。
[e5847] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/LBL_SAVE_LOAD
  原文：Kaydet/Yeniden Yükle
  译文：保存/重新加载
  问题：术语一致性——术语'Yeniden Yükle'误译为'重新上传'，游戏标准术语应为'重新加载'或'重新开始'。
[e5885] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少需要与列表中的某个命令有 70% 的相似度。
  问题：语义一致性——译文后半部分严重偏离原文含义，将'It should be at least...'错误地翻译为'至少应该如此'，导致信息缺失且逻辑不通。
[e6055] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：workshop 应译为'工坊'，airlock 应译为'气闸'，task dispenser 应译为'任务分发器'或'任务终端'。
  问题：术语一致性——术语翻译严重错误，'workshop'误译为'研讨会'，'airlock'误译为'传送门'，'task dispenser'误译为'任务分配器'，不符合游戏行业标准译法。
[e6056] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_ROUTINE
  原文：Reward:
• <Key><Credits></> credits
• Additional <Key>ship hull upgrade</>
  译文：奖励：
• <Key><Credits></> 点数
• 额外的 <Key>飞船外壳升级</Key>
  问题：术语一致性——原文'Credits'译为'致谢'导致语义完全错误，且原文'Additional'被遗漏，严重违背游戏术语规范与信息完整性。
[e6063] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以切换选择。使用 <Key>滚动轮</> 控制移动距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'更改选择内容'不符合 UI 标准，'使用滚动轮'重复了原文的'使用'。
[e6147] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e6184] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器</>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语翻译错误，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中'UNDER NO CIRCUMSTANCES'的否定语气在译文中虽存在但整体术语严重偏离行业标准。
[e6186] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>信用点以及最后的船体升级。
  问题：术语一致性——译文存在严重语病，将原文的并列结构误译为递进关系，且关键术语'Credits'未使用行业标准译法'信用点'。
[e6192] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示芯片
  问题：术语一致性——译文存在术语不规范、标点缺失及信息完整性问题，需修正以符合行业标准。
[e6209] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须。
  问题：否定——译文将原文的否定含义（I have to）误译为肯定（确实如此），导致语义逻辑完全相反。
[e6212] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非行业标准译法“信用点/金币”，且奖励列表结构缺失数值显示。
[e6214] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回该船上的'大规模内存单元'
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'distress signal'（求救信号）误译为'求救信号'但后续动作逻辑错误，且多处术语翻译不符合行业标准。
[e6215] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该 <Task>工坊</>。请按照指示行事。 <Task>升级</> 你的飞船。
  问题：术语一致性——译文严重偏离原文含义，关键术语（Workshop/Upgrade）及否定词（not）均错误，导致游戏逻辑与剧情完全混乱。
[e6217] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：条件与因果——译文严重违背原文逻辑，将“因为不喜欢厨房的脏乱而搬进卧室”误译为“因为搬进卧室导致厨房脏乱”，人物关系与因果关系完全颠倒。
[e6219] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：欢迎来到造船厂，<Key><Name></>！你现在已成为这家公司的飞行员之一。
下一个任务者已经能够阅读和行走了，这让我感到很欣慰……
你的飞船正在对接区等待着你。
不过首先，你需要继续遵循教程协议并加载第一个任务。
  问题：术语一致性——术语使用不规范，'Shipyard' 译为'造船站'不符合游戏行业通用译法，且'指示'一词冗余。
[e6245] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null reference exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被玩家理解。
[e6246] Isolated Inhale_Data/resources.assets:asset#resources.assets#1378/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离按钮
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e6262] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/CMD_GOAL
  原文：Deocamdată, obiectivul tău este să pregătești nava ta pentru o misiune importanta. Conform calculelor mele, cu dotările 
  译文：保留原文罗马尼亚语，或根据上下文准确翻译为中文（如：现在，你的目标就是为执行这项重要任务做好准备。根据我的计算，以当前舰船的装备水平来看，成功完成这项任务的概率大约为 <Key><Success>%</Key>。）
  问题：术语一致性——原文为罗马尼亚语，译文误译为中文，且存在术语不统一及标点错误。
[e6265] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/CMD_STOP_FAIL
  原文：<Error>Eroare:</> nu a putut fi găsită o secvență pentru oprire.
  译文：若目标语言为中文，应翻译罗马尼亚语原文含义；若原文确为罗马尼亚语，则不应出现中文译文。建议核实项目语言设置。
  问题：术语一致性——原文为罗马尼亚语，译文使用了中文，且存在术语不匹配问题，需确认是否为多语言环境下的错误翻译。
[e6272] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_INTRO
  原文：<Task>SUBIECT 01</>
Stare: <Inactive>Necunoscut</>

<Error>Eroare</>: Executarea protocolului nu poate fi continuată. Es
  译文：<Task>受试者 01</>
  问题：术语一致性——术语严重错误，'SUBJECT'误译为'主题'，'胶囊'误译为'胶囊'（应为'冷冻舱'或'冷冻舱'），且句子结构混乱导致含义不清。
[e6284] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_WORKSHOP
  原文：Acces la <Key>atelierul</> de pe şantierul naval
  译文：将译文翻译为中文：访问海军基地上的工坊
  问题：语言错误——原文为罗马尼亚语，译文为中文，存在严重的语言错误；且关键术语'atelier'（工坊/车间）被误译为'工作室'，未体现海军基地的工业属性。
[e6299] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_INV_RES_FAIL
  原文：<Error>Eroare:</> Lipsește cipul de jurnal.
Nu se poate efectua verificarea.

  译文：日志文件缺少。
  问题：语义一致性——原文为罗马尼亚语，译文将'Lipsește'（缺少）误译为'有空格'，导致语义完全相反且信息严重错误。
[e6385] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少需要与列表中的某个命令有 70% 的相似度。
  问题：语义一致性——译文后半部分严重偏离原文含义，将'至少应相似'错误翻译为'至少应该如此'，导致信息缺失且逻辑不通。
[e6555] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：workshop 应译为'工坊'，airlock 应译为'气闸'，task dispenser 应译为'任务分发器'或'任务终端'。
  问题：术语一致性——术语翻译严重错误，'workshop'误译为'研讨会'，'airlock'误译为'传送门'，'task dispenser'误译为'任务分配器'，不符合游戏行业标准译法。
[e6556] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_ROUTINE
  原文：Reward:
• <Key><Credits></> credits
• Additional <Key>ship hull upgrade</>
  译文：额外的 <Key>飞船外壳升级</>
  问题：术语一致性——原文'Credits'为游戏货币，译文误译为'致谢'，导致核心数值信息完全错误。
[e6563] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以切换选择。使用 <Key>滚动轮</> 控制移动距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'更改选择内容'不符合 UI 标准，'使用滚动轮'重复了原文的'使用'。
[e6647] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致功能含义完全错误。
[e6684] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器>。其坐标已在<Key>平板电脑>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语翻译不统一且存在冗余，'container field' 未采用标准 UI 术语，且末尾重复了原文标签导致语句不通顺。
[e6692] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示芯片
  问题：术语一致性——译文存在术语不规范（如'提示贴'非标准 UI 用语）、信息缺失（未体现'chips'的具体含义）及标点格式错误。
[e6709] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：语气——译文将原文中强烈的自我否定与决绝语气弱化为口语化的确认，且“确实如此”严重偏离了原文“我必须这么做”的主动意志。
[e6712] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非行业标准译法“信用点/金币”，且原文奖励数量信息缺失。
[e6714] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船的<Task>大规模内存单元</>。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e6715] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该车站的工作间。请按照指示升级你的飞船。
  问题：术语一致性——原文中'workshop'被误译为'研讨会'，导致游戏内任务指令含义完全错误，且'upgrade'后的句式结构混乱，严重破坏游戏逻辑。
[e6717] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢……<Key>我厨房里的灰尘和垃圾，因为它搬到了卧室里。
  问题：人物关系——译文严重违背原文逻辑，将'因为'误译为'因为'导致因果倒置，且错误地将'灰尘和垃圾'拟人化为'它们'，造成人物关系混乱。
[e6719] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：移除'第一个任务。'中的句号，改为'第一个任务。'
  问题：信息完整性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'推进'，此处语境下'继续'尚可但需结合上下文，主要问题在于'load'译为'加载'虽对但语境生硬，且'first task'后多了一个句号导致语法错误，最严重的是'continue following'译为'继续遵循'略显累赘，但核心错误在于'load'在任务语境下通常译为'加载'或'载入'，此处尚可接受。然而，'first task'后的句号位置错误，导致句子结构断裂。
[e6745] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null reference exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序识别。
[e6746] Isolated Inhale_Data/resources.assets:asset#resources.assets#1380/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e6764] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/CMD_STOP_FAIL
  原文：<Error>Error:</> Kon geen reeks vinden om te stoppen.
  译文：错误：找不到可停止的序列。
  问题：术语一致性——术语使用不当，'series'在此语境下指'序列'而非'系列'，且'无法找到要停止的序列'语序生硬，不符合游戏本地化习惯。
[e6771] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_INTRO
  原文：<Task> ONDERWERP 01 </>
Status: <Inactive>Onbekend</>

<Error>Error</>: Protocol uitvoering kan niet door gaan. Nieuwe u
  译文：<Task>任务 01</> 状态：<Inactive>未知</> <Error>错误：协议执行无法继续。需要新的执行者。 重新启动 <Key>T 协议</> 的执行。准备一个冷冻舱。 <Task>任务 02</> 状态：<Command>完成</>
  问题：术语一致性——原文为荷兰语游戏本地化文本，译文将专有名词误译为中文通用词，且严重混淆了游戏术语标准译法。
[e6783] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_WORKSHOP
  原文：Toegang tot de <Key>workshop</> op de Scheepswerf
  译文：进入权限 <Key>工坊</Key> 在造船厂
  问题：术语一致性——术语翻译不统一且未遵循行业标准，'workshop' 译为'研讨会'不符合游戏 UI 规范，应统一为'工坊'或'工作区'。
[e6818] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_TUT_OBJ_LOAD
  原文：Geprinte chip laden met behulp van de Decoderingstafel
  译文：若需保留原文语言，应翻译为：‘已通过解码板充电的打印芯片’；若需本地化，需先确认原文意图，通常此类物品描述应译为：‘已用解码板充电的打印芯片’。
  问题：语义一致性——原文为荷兰语，译文误将荷兰语当作中文翻译，且严重违背了游戏本地化中“不增删信息”及“术语一致性”原则，导致语义完全错误。
[e6824] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_EQUIPMENT
  原文：Druk op <Key>[<KeyBind>]</> om het uitrustingsmenu te openen.
  译文：点击 <Key>[<KeyBind>] 以打开装备菜单。
  问题：术语一致性——术语翻译错误，'uitrustingsmenu'（装备/装备菜单）被误译为'设备菜单'，且原文为荷兰语，译文未体现语言背景。
[e6827] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_KEYBOARD
  原文：Druk op <Key>[<KeyBind>]</> om in te dienen.
  译文：点击 <Key> [<KeyBind>] 以提交。
  问题：术语与语气——原文为游戏指令，译文将“输入”误译为“进行输入”，且未体现“提交/执行”的动作含义，语气不符合游戏 UI 规范。
[e6828] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_PIN
  原文：Druk op <Key>[1-9]</> om de code in te voeren.
  译文：请按 <Key>[1-9]》继续输入代码。
  问题：术语一致性——译文存在严重语病且术语不规范，'以输入'为错误搭配，且未使用标准术语'继续'。
[e6884] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：您不需要完全输入相同的命令。至少需要与列表中的某个命令有 70% 的相似度。
  问题：语义一致性——译文后半部分严重偏离原文含义，将'It should be at least...'错误地翻译为'至少应该如此'，导致信息缺失且逻辑不通。
[e7054] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：workshop 应译为'工坊'，airlock 应译为'气闸'，task dispenser 应译为'任务分发器'。
  问题：术语一致性——术语翻译严重错误，将游戏标准术语'workshop'误译为'研讨会'，'airlock'误译为'传送门'，且'任务分配器'译名不规范。
[e7055] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_ROUTINE
  原文：Reward:
• <Key><Credits></> credits
• Additional <Key>ship hull upgrade</>
  译文：额外的 <Key>飞船外壳升级</>
  问题：术语一致性——原文'Credits'指游戏货币，译文误译为'致谢'，导致核心数值信息完全错误。
[e7062] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以更改选择。使用 <Key>滚轮</> 控制移动距离。
  问题：术语一致性——译文存在术语不规范及信息冗余问题，'Scroll wheel'未采用标准译法'滚轮'，且'使用'一词导致句子结构冗余。
[e7146] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语误用，游戏 UI 中 Load 应译为“读取”而非“负载”，导致含义偏差。
[e7183] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>任务容器</>。
  问题：术语一致性——术语翻译不统一且存在冗余，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且'UNDER NO CIRCUMSTANCES'翻译为'在任何情况下都不要'导致语气冗余，不符合游戏 UI 标准。
[e7185] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>点奖励以及最后的船体升级。
  问题：信息完整性——译文存在严重语病，'……'占位符导致句子断裂，且'出现为止'冗余，不符合游戏 UI 简洁规范。
[e7191] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：很快，你就不会独自一人在飞船上了。我在那里留下了提示芯片。<Task>氧气</Task>、<Task>燃料</Task>和<Task>太阳能电站</Task>。找到它们之后，你就会知道会发生什么了。
  问题：术语一致性——译文存在术语不规范、标点缺失及信息完整性问题，不符合游戏本地化标准。
[e7211] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非行业标准“信用点/金币”，且奖励列表格式缺失数值显示。
[e7213] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回该处的<Task>mass memory unit</>。
  问题：语义一致性——译文严重偏离原文含义，将'获取'误译为'救回来'，且多处术语使用错误。
[e7214] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问该<Task>工坊。请按照指示行事。<Task>升级你的飞船。
  问题：术语一致性——严重术语错误：将'workshop'误译为'研讨会'（应为'工坊'），将'upgrade'误译为'升级'（虽词义相近但语境不符，且原文'access to the workshop'结构被破坏导致语义混乱）
[e7216] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：人物关系与因果——译文严重违背原文逻辑，将‘不喜欢厨房里的脏乱’错误翻译为‘因为搬到了卧室里’，导致人物关系与因果关系完全颠倒。
[e7218] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续执行教程中的指示，并读取<Task>作为第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'完成'），且'load'误译为'加载'（游戏语境下通常指'读取'或'载入'任务），存在术语一致性风险。
[e7230] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/LBL_DOCKING_NOTE
  原文：Controls are locked, press dock/undock
  译文：控件已锁定，请按'Dock'/'Undock'按钮
  问题：术语一致性——译文过度解释且未遵循 UI 术语规范，'Dock'/'Undock'应直接使用标准译法而非加引号解释。
[e7244] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null reference exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序正确识别。
[e7245] Isolated Inhale_Data/resources.assets:asset#resources.assets#1382/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e7270] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_INTRO
  原文：<Task>SUBJECT 01</>
Status: <Inactive>Nieznany</>

<Error>Błąd</>: Wykonywanie protokołu nie może być kontynuowane. Wyma
  译文：休眠舱；执行器
  问题：术语一致性——术语翻译不统一，'Kapsuła hibernacyjnej' 译为'休眠舱'不符合游戏 UI 标准术语（应为'休眠舱'或'休眠室'需确认，但此处主要问题在于'执行者'与'执行器'的潜在歧义及'协议'的语境适配，以及'准备'与'启动'的语序微调，整体语义基本通顺但术语规范性存疑
[e7381] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/DESC_TROPHY
  原文：Nagroda „Pilot Roku”. Przyznana pilotowi o kryptonimie Kirillfff.
  译文：年度飞行员奖。授予了绰号 Kirillfff 的飞行员。
  问题：术语一致性——专有名词翻译不准确，波兰语奖项名称未直译，且未体现‘最佳’含义。
[e7468] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_INFRASOUND_NOTE
  原文：Dodaje subtelne dudnienie podczas strasznych sekcji, aby spotęgować niepokój. Efekt ten będzie zauważalny tylko na dobry
  译文：在那些恐怖的段落中，它添加了微妙的震动，从而加剧了不安感。
  问题：术语一致性——术语翻译错误，'dudnienie' 应译为'震动'而非'不稳定感'，且 UI 警告词'Uwaga'应译为'注意'而非'注意'（重复/冗余），信息完整性不足。
[e7534] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_ERR_FUEL
  原文：<Error>Błąd</>: Krytyczny poziom paliwa
  译文：错误：燃油耗尽
  问题：术语一致性——术语'临界水平'不符合游戏 UI 标准，且'燃料'在特定语境下可能指代不明，建议统一使用行业通用译法。
[e7552] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_INVESTIGATION
  原文：Chip z logami został pomyślnie dostarczony.

Twoja nagroda: <Key><Credits></> kredytów.
Przyznaję Ci również dostęp do <
  译文：包含徽章的组件已成功送达。

您的奖励为：<Key><Credits></>信用点。
我还授予您使用本站的<Key>工坊</Key>以及<Key>气闸</Key>的权限。

现在，您可以开始通过“任务分发器”来执行后续任务了。<Task>
  问题：术语一致性——术语翻译不统一，'warsztatu'和'słuzy powietrznej'未使用游戏行业标准译法，且原文专有名词'Chip z logami'译法生硬。
[e7553] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_ROUTINE
  原文：Nagroda:
• <Key><Credits></> kredytów
• Dodatkowe <Key>ulepszenie kadłuba statku</>
  译文：成就：
• <Key><Credits></> 点数
• 额外的 <Key>船体升级</>
  问题：术语一致性——术语翻译不准确，'Nagroda'应译为'奖项'而非'荣誉'，且'kredytów'作为游戏货币单位未明确具体名称，'ulepszenie kadłuba'直译生硬，建议采用行业通用译法。
[e7560] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_ROW
  原文：Naciśnij <Key>[<KeyBind>]</> , aby zmienić wybór. Użyj <Key>Kółka myszy</> aby kontrolować odległość.
  译文：点击 <Key>[<KeyBind>]</> 以更改选择范围。使用 <Key>鼠标滚轮</> 来控制距离。
  问题：语义一致性——原文 'odległość' 指距离/范围，译文误译为'移动距离'，导致控制对象含义偏差。
[e7570] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_INHALE
  原文：Odizolowany Wdech
  译文：隔离呼吸模式
  问题：术语一致性——术语翻译不准确，'Odizolowany' 并非标准游戏术语，且'Wdech'直译为'呼吸'在 UI 语境下易产生歧义，建议采用更通用的'隔离模式'或'呼吸模式'。
[e7578] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_PAUSE_MENU
  原文：Menu Pauzy
  译文：暂停菜单
  问题：术语一致性——原文拼写错误且术语使用不当，'Pauzy'应为'Pause'，且'Menu Pause'并非标准游戏术语，应译为'暂停菜单'。
[e7594] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/CMD_JOB_RES
  原文：Twoim zadaniem jest utrzymanie stacji kosmicznych. Wszystkie niezbędne informacje znajdują się na <Key>chipach z zadania
  译文：你的任务就是维护这些空间站。所有必要的信息都存储在<Key>任务芯片>上，你可以从<Key>任务分发器>处获取这些芯片。
完成任务后，你将获得<Key>积分>，你可以随意使用这些积分。但请记住我们的主要目标。
  问题：术语一致性——术语翻译严重错误，将'chip'误译为'芯片'（应为'芯片'或'数据芯片'以符合游戏语境，但此处主要问题是'供应商'和'信用点'的误译），且'任务供应商'完全不符合游戏 UI 术语规范。
[e7645] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e7682] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器</>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西的。
  问题：术语一致性——术语翻译错误，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中<Error>标签未正确转义导致显示异常。
[e7684] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：信用点
  问题：术语一致性——译文存在严重语病，将原文的并列结构误译为递进关系，且关键术语'Credits'未使用标准译法'信用点'。
[e7690] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_MSG_NOTE_CHIPS
  原文：Soon you won't be alone on your ship. I left note chips at the <Task>oxygen</>, <Task>fuel</>, and <Task>solar</> statio
  译文：提示芯片
  问题：术语一致性——译文存在术语不一致、标点缺失及信息完整性问题，不符合行业标准译法。
[e7707] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须。
  问题：否定——译文将原文的否定含义（I have to）错误地处理为肯定陈述（确实如此），导致语义逻辑完全颠倒。
[e7710] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e7712] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：请前往那里，取回那艘船的<Task>大规模内存单元</>。
  问题：语义一致性——译文严重违背原文含义，将'retrieve'（取回）误译为'救回来'，将'wreck'（摧毁）误译为'毁掉'，且关键术语'mass memory unit'翻译错误。
[e7713] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：现在，我将允许您访问任务工坊。请按照指示升级你的飞船。
  问题：术语一致性——译文严重偏离原文含义，关键术语（Workshop/Upgrade）翻译错误，且句子结构混乱导致信息丢失。
[e7714] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_NOTE_00
  原文：Note No. 1. At first, I started noticing unusual activity on my ship. <Key>Food</> began to disappear. I clearly remembe
  译文：补给开始短缺了
  问题：术语一致性——术语'Food'误译为'食物'，在科幻/游戏语境下通常指'补给'或'能源'，且原文'Food'为单数名词，译文'短缺了'虽通顺但未能精准对应游戏内资源消耗机制，存在术语不严谨问题。
[e7715] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬进了卧室。
  问题：条件与因果——译文严重违背原文逻辑，将“因为不喜欢厨房的脏乱而搬进卧室”误译为“因为搬进卧室导致厨房有灰尘”，人物关系与因果关系完全颠倒。
[e7717] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：不过首先，你需要继续执行教程协议，并加载第一个任务。
  问题：术语一致性——术语使用不规范，'continue' 误译为'继续'（应为'继续'或'继续执行'，但此处语境下'continue'作动词需结合上下文，主要问题在于'load'译为'加载'虽可接受，但'first task'后多出的'作为'导致语义冗余且不符合 UI 简洁性，同时'corporation'译为'公司'略显生硬，建议统一为'企业'或'公司'视游戏风格，但最严重的是'continue'在教程语境下通常指'继续'，此处翻译尚可，但'load the first task'译为'加载...作为第一个任务'语序混乱，建议改为'加载第一个任务'。
[e7729] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_DOCKING_NOTE
  原文：Controls are locked, press dock/undock
  译文：控件已锁定，请按 Dock/Undock 按钮。
  问题：术语一致性——译文过度解释且未遵循 UI 标准术语规范，导致信息冗余且术语不统一。
[e7744] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e7749] Isolated Inhale_Data/resources.assets:asset#resources.assets#1383/json/LBL_PILOT_MANUAL_4A
  原文：<b>PILOT SUIT</b>

Designed to provide easy access to the <color=#8BDFFF>pilot's interface</color>. Can protect you from
  译文：设计用于方便飞行员访问操作界面。既能保护你免受寒冷侵袭，但内部也会变得很热。
  问题：术语一致性——术语翻译不统一，'interface' 未采用游戏行业标准译法，且部分描述略显冗余。
[e7769] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_INTRO
  原文：<Task>SUJEITO 01</>
Status: <Inactive>Desconhecido</>

<Error>Erro</>: Execução do protocolo não pode ser continuada. No
  译文：Protocol 译为'程序'，Key 加引号显示为'PROTO T'
  问题：术语一致性——术语翻译不统一，'Protocol' 译为'协议'而非游戏行业标准'程序'，且'Key'未加引号导致格式不规范。
[e7776] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_SAVE_OVERRIDE
  原文：Arquivo salvo com o mesmo nome já existe. Gostaria de substituí-lo?
  译文：已存在同名文件。是否覆盖？
  问题：语言匹配——原文为葡萄牙语，译文为中文，存在语言不匹配问题，且未体现游戏本地化中“替换”的确认语气。
[e7781] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_WORKSHOP
  原文：Acesso à <Key>oficina</> na estação do Estaleiro
  译文：访问造船厂站上的车间
  问题：术语一致性——术语翻译不准确，'oficina' 在造船厂语境下应译为'车间'或'工作区'，而非'工坊'；且原文包含'na estação do'（在...站），译文漏译了'站'这一关键信息。
[e7796] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_INV_RES_FAIL
  原文：<Error>Erro:</> Unidade de memória em massa faltando.
Incapaz de realizar a verificação.

  译文：错误：缺少大容量存储单元。
无法完成验证。
  问题：术语一致性——术语使用不规范，'Unidade de memória em massa' 应译为'大容量存储单元'而非'大容量内存单元'，且'Erro'在葡萄牙语中意为'错误'，此处语境下通常指'错误'或'故障'，但结合上下文'falta'（缺少）更倾向于硬件故障提示，建议统一为'错误'或'故障'以符合游戏 UI 标准。
[e7822] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_EQUIPMENT
  原文：Pressione <Key>[<KeyBind>]</> para abrir o menu de equipamento.
  译文：按下 <Key>[<KeyBind>] 以打开设备菜单。
  问题：否定——原文为葡萄牙语动词'Pressione'（按下），译文误译为中文名词'压力'，导致语义完全错误且无法操作。
[e7826] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_PIN
  原文：Pressione <Key>[1-9]</> para inserir o código.
  译文：请按 <Key>[1-9]》以输入代码。
  问题：术语与语法——译文存在严重术语错误，将'Pressione'误译为'按'（应为'按'或'按下'但需结合语境），且'para inserir'误译为'以输入'导致语法结构混乱，未准确传达'按下...以输入'的指令逻辑。
[e8130] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/TXT_SUBJECT_DATA
  原文：DADOS DO SUJEITO:

Identificador: <Key>0<Index></>
Status: <Command>Pronto</>
Indicativo de chamada: <Inactive><Name></>
  译文：数据信息：

标识符：<Key>0<Index></>
状态：<Command>准备就绪</>
呼叫指示：<Inactive><Name></>
  问题：术语一致性——术语翻译不统一，'Status' 译为'状态'而非游戏 UI 标准'状态'，且'Indicativo de chamada'译名生硬，未采用行业标准'呼叫指示'。
[e8181] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_CONT_INTRO
  原文：Seu próximo alvo é o <Task>campo de contêineres</>. Suas coordenadas estão descritas no <Key>tablet</> que estou te dand
  译文：在任何情况下都绝对不要打开该容器。你不会喜欢里面所包含的内容的。
  问题：语气——原文中明确警告“在任何情况下都不应打开该容器”，译文却将其作为普通信息陈述，完全丢失了禁止操作的强制语气，导致严重误导。
[e8210] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_ANY_REWARD_THIRD
  原文：Houve alguns problemas técnicos da última vez, então estou te dando uma recompensa por duas tarefas:
• <Key><Credits></>
  译文：信用点
  问题：术语一致性——术语严重错误：Credits 译为‘致谢’而非‘信用点’；人物关系混乱：原文‘Subject 继续执行任务’译为‘主体/对象...他’，导致主语指代不明且多余；语气不当：‘完成两项任务而给予你奖励’逻辑不通，原文意为‘因完成两项任务而给予奖励’。
[e8211] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_INV_RES_START
  原文：Recentemente recebi um sinal de socorro de uma das nossas naves. Voe até lá e recupere a <Task>unidade de memória em mas
  译文：必须使用中文翻译葡萄牙语原文。
  问题：语言错误——严重错误：原文为葡萄牙语，译文为中文；关键术语翻译错误（如'baia de acoplagem'译为'连接舱'应为'对接舱'）；否定词缺失（'Não se preocupe'译为'不必担心'正确，但整体语境混乱）；任务目标描述不准确（'recupere'译为'救出他们'错误，应为'回收'）。
[e8212] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_INV_RES_SUCCESS
  原文：Unidade de memória em massa entregue com sucesso.
<Inactive>Nota: O sujeito conseguiu não destruir a nave...</>

Executa
  译文：现在我可以让你访问空间站中的<Secret><Task>工坊>了。请按照说明来改进你的飞船。<Task>
  问题：术语一致性——术语翻译不统一且部分关键信息缺失，导致游戏机制理解错误。
[e8213] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_NOTE_00
  原文：Nota N° 1. No início, comecei a notar atividade incomum na minha nave. <Key>Comida</> começou a desaparecer. Lembro clar
  译文：笔记 1：起初，我注意到我的飞船上出现了异常活动。<Key>补给</>开始逐渐消失。我清楚地记得，在离开飞船之前，我没有关闭任何设备……最近，生物扫描仪也开始工作起来。我还不知道发生了什么，但我会继续观察下去。
  问题：术语一致性——术语翻译不统一，'Comida' 译为'食物'不符合游戏 UI 标准，且'Nota'译为'注意'不符合游戏内日志/编号规范。
[e8216] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/SEQ_TUT_START_REPLY
  原文：Bem-vindo à estação do Estaleiro, <Key><Name></>! Você agora é um dos pilotos da corporação.
<Inactive>O fato que o próx
  译文：欢迎来到造船厂，<Key><Name></>！你现在已成为公司的驾驶员之一。
<Inactive>能够阅读并行走的下一个人，这让我充满了希望……
你的飞船正在对接舱里等待着你。
不过在此之前，你必须继续遵循教程中的规则，完成第一项任务。
  问题：术语一致性——术语翻译不统一，'Estaleiro' 译为'造船厂站'不符合游戏 UI 标准，且'任务'未使用标准术语'Task'。
[e8245] Isolated Inhale_Data/resources.assets:asset#resources.assets#1384/json/LBL_PILOT_MANUAL_0
  原文：<b>Desacoplando:</b>

<color=#bbbb>1.</color> Ative o <color=#8BDFFF>painel de piloto</color>
<color=#bbbb>2.</color> Pr
  译文：1. 等待飞船离开<color=#8BDFFF>对接区域</color>
2. 按下<color=#8BDFFF>脱离按钮</color>
  问题：术语一致性——术语翻译不统一，原文'acoplagem'译作'连接区域'，而后续步骤'botão de desacoplagem'译作'切换按钮'，导致逻辑混乱且术语错误。
[e8383] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/LBL_DIALOG_1
  原文：All currently available commands are displayed here. Their availability depends on the fulfillment of certain conditions
  译文：至少应该与列表中的某个命令有 70% 的相似度。
  问题：信息完整性——译文后半句语义严重缺失，导致指令含义无法传达，属于信息完整性问题。
[e8553] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/TXT_INVESTIGATION
  原文：The mass memory unit has been successfully delivered.

Your reward: <Key><Credits></> credits.
I am also granting you ac
  译文：工坊
  问题：术语一致性——术语翻译严重错误，'workshop'译为'研讨会'、'airlock'译为'传送门'、'task dispenser'译为'任务分配器'均不符合游戏行业标准译法。
[e8561] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/TXT_ROW
  原文：Press <Key>[<KeyBind>]</> to change selection. Use <Key>Scroll wheel</> to control the distance.
  译文：按下 <Key>[<KeyBind>] 以更改选择内容。使用 <Key>滚动轮</> 控制移动距离。
  问题：术语一致性——译文存在术语误用和信息冗余，'Scroll wheel'被错误译为'使用滚动轮'导致语义重复且不符合 UI 标准。
[e8645] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/LBL_LOAD
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为“读取”而非“负载”。
[e8682] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_CONT_INTRO
  原文：Your next target is the <Task>container field</>. Its coordinates are described on the <Key>tablet</> I am giving you.


  译文：你的下一个目标是 <Task>容器区域</>。其坐标已在<Key>平板</>中说明，我已经提供给你了。

在这里交付被标记为 <Key>的容器</>。

在任何情况下都不要打开这个容器。你不会喜欢里面的东西。
  问题：术语一致性——术语使用不规范，'container field'误译为'容器字段'，'tablet'误译为'平板电脑'，且原文中'UNDER NO CIRCUMSTANCES'的否定语气在译文中虽保留但整体术语错误导致专业度下降。
[e8684] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_CONT_REWARD
  原文：Good job, <Nickname>. I'm giving you <Key><Credits></> credits and the last hull upgrade.

There's no more work for you 
  译文：干得好，<Nickname>。我正在给你<Key><Credits>点信用和最后的船体升级。
  问题：信息完整性——译文严重缺失原文关键信息，且将原文中的'没有更多工作'错误地翻译为'没有新的任务'，导致语义完全相反。
[e8707] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/TXT_DEATH_NOTE
  原文：There's no point in continuing anymore. The feelings of loneliness and the weight of responsibility I feel when making t
  译文：我必须这么做。
  问题：人物关系/逻辑——译文将原文的“我不得不这么做”误译为“确实如此”，导致人物关系与逻辑含义发生严重偏差。
[e8710] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_ANY_REWARD_FIRST
  原文：Against all odds, you still managed to survive and complete your first task.

Here is your reward:
• <Key><Credits></> c
  译文：• <Key><Credits></> 信用点
  问题：术语一致性——术语翻译错误，Credits 译为“致谢”而非“信用点/金币”，导致奖励信息含义完全错误。
[e8712] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_INV_RES_START
  原文：I recently received a distress signal from one of our ships. Fly there and retrieve the <Task>mass memory unit</>.

Here
  译文：将'大规模内存单元'改为'质量存储单元'，将'《操作手册》'改为'《飞行员手册》'
  问题：术语一致性——术语翻译严重错误，'mass memory unit' 译为'大规模内存单元'不符合游戏行业标准，且'pilot manual'译为'操作手册'未加书名号导致格式不规范。
[e8713] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_INV_RES_SUCCESS
  原文：Mass memory unit delivered successfully.
<Inactive>Note: The subject managed not to destroy the ship...</>

Executing de
  译文：大容量存储器已成功交付。
  问题：术语一致性——译文严重偏离原文含义，包含术语误用、信息缺失及逻辑错误。
[e8715] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_NOTE_01
  原文：Note No. 2. It’s a sentient being. It seems it didn’t like the <Key>dirt and trash</> in my kitchen because it moved int
  译文：看起来它不喜欢我厨房里的灰尘和垃圾，所以搬到了卧室。现在我不敢再进去……
  问题：语义一致性——译文严重偏离原文逻辑，错误地将“灰尘和垃圾”解释为“生物搬走的原因”，导致人物关系与因果关系完全颠倒。
[e8717] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/SEQ_TUT_START_REPLY
  原文：Welcome to the Shipyard station, <Key><Name></>! You are now one of the corporation's pilots.
<Inactive>The fact that th
  译文：欢迎来到船坞站，<Key><Name></>！
  问题：术语一致性——术语使用不规范，'Shipyard' 译为'造船站'不符合游戏行业标准，且'任务者'指代不明，'指示'与'任务'搭配不当。
[e8743] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/TXT_NULL_EXCEPTION
  原文：<Error>Null reference exception</>
  译文：Null reference exception
  问题：术语一致性——原文为编程错误提示，译文将技术术语误译为中文日常用语，导致含义完全错误且无法被程序识别。
[e8744] Isolated Inhale_Data/resources.assets:asset#resources.assets#1386/json/LBL_PILOT_MANUAL_0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（如'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e8811] Isolated Inhale_Data/resources.assets:asset#resources.assets#17039/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语使用错误，游戏 UI 中 Load 应译为'读取'而非'负载'。
[e8828] Isolated Inhale_Data/resources.assets:asset#resources.assets#17308/str/0
  原文：Load
  译文：读取
  问题：术语一致性——术语严重错误，Load 在游戏 UI 中意为“读取”而非“负载”，导致含义完全错误。
[e8870] Isolated Inhale_Data/resources.assets:asset#resources.assets#17685/str/0
  原文：Start the game to be able to change theese settings
  译文：启动游戏即可更改这些设置
  问题：信息完整性——原文中"these"为复数，译文漏译了"这些"，导致信息不完整。
[e8982] Isolated Inhale_Data/resources.assets:asset#resources.assets#19212/str/0
  原文：<b>Undocking:</b>

<color=#bbbb>1.</color> Enable the <color=#8BDFFF>pilot panel</color>
<color=#bbbb>2.</color> Press t
  译文：脱离接触
  问题：术语一致性——多处严重术语错误（如'卸载'应为'脱离'，'西装'应为'宇航服'，'过渡'应为'转换'），且存在信息缺失与语序混乱。
[e9041] Isolated Inhale_Data/resources.assets:asset#resources.assets#19897/str/0
  原文：<color=#ffa555>[!]</color> If you run out of fuel during a flight, you can call the <color=#1f9>emergency supply deliver
  译文：如果在飞行过程中燃料用尽，您可以呼叫<color=#1f9>紧急物资补给</color>。请参考飞行员手册以获取详细操作指南。
  问题：语义一致性——原文指紧急物资补给而非救援电话，且未提及拨打，译文严重偏离原意。
[e9109] Isolated Inhale_Data/Managed/FMODUnity.dll:us#3224
  原文：There is a version mismatch between the FMOD header and either the FMOD Studio library or the FMOD Low Level library.
  译文：FMOD 头文件与 FMOD Studio 库或 FMOD 低级别库之间存在版本不匹配。
  问题：信息完整性——译文结构混乱，将错误信息中的关键部分（低级别库）错误地作为独立句子截断，导致语义不完整且不符合技术报错规范。
