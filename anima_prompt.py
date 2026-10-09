#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anima 中文提示词转换器（完全离线 / 零第三方依赖）

把一段中文转成 Anima 用的 Danbooru tag 提示词，按三组输出：
    动作姿势 / 场景背景 / 补充细节

设计铁律：
  1. 只翻译，不脑补。输入里没有的概念，绝不添加。
  2. 不编造。中文词在词典里找不到对应 tag 时，列进「未命中」，不猜。
  3. 不联网、不调用任何大模型、不装任何第三方包。

运行：
    python anima_prompt.py              # 打开窗口
    python anima_prompt.py "中文描述"    # 命令行模式
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 词典
# ---------------------------------------------------------------------------
# 结构： 分组 -> [(中文关键词, 英文 tag, 权重)]
#   - 中文关键词用「|」写同义词，任一命中即算命中
#   - 权重 1.0 = 不加权；!=1.0 会输出成 (tag:权重)
#   - 英文 tag 统一小写、词间空格（Anima 规范：不写下划线）

TAG_MAP: dict[str, list[tuple[str, str, float]]] = {}

TAG_MAP["动作姿势"] = [
    # ---- 主体 / 人数 ----
    ("一个女孩|1个女孩|一个女生|一名少女|少女|女孩|女生|女孩子|单人", "1girl", 1.0),
    ("一个男孩|1个男孩|一个男生|少年|男孩|男生|男孩子", "1boy", 1.0),
    ("两个女孩|两个女生|两个人|两人|二人|双人", "2girls", 1.0),
    ("三个女孩|三个人|三人", "3girls", 1.0),
    ("多人|一群人|众人", "multiple girls", 1.0),
    ("独自|孤单一人|孤身", "solo", 1.0),
    # ---- 基本站位 ----
    ("站立|站着|站姿|站着不动|站", "standing", 1.0),
    ("坐|坐着|坐姿", "sitting", 1.0),
    ("跪坐|正坐|鸭子坐", "wariza", 1.0),
    ("单膝跪地|半跪|跪|双膝跪地", "kneeling", 1.0),
    ("蹲|蹲着|蹲下", "squatting", 1.0),
    ("趴|俯卧|趴着|趴在", "on stomach", 1.0),
    ("仰卧|平躺|躺着|躺", "lying", 1.0),
    ("侧躺|侧卧", "on side", 1.0),
    ("爬|爬行|四肢着地", "all fours", 1.0),
    ("蜷缩|缩成一团", "fetal position", 1.0),
    # ---- 身体倾向 ----
    ("向后仰|后仰", "leaning back", 1.0),
    ("前倾|向前倾|俯身", "leaning forward", 1.0),
    ("扶着|倚靠|靠在", "leaning", 1.0),
    ("转身|扭身|身体转向", "turning around", 1.0),
    ("背对|背对镜头|背对着", "facing away", 1.0),
    ("面向|正对", "facing viewer", 1.0),
    # ---- 取景 ----
    ("半身|半身像|上半身", "upper body", 1.0),
    ("特写|面部特写", "portrait", 1.0),
    ("全身|全身像", "full body", 1.0),
    ("大头|头肩|胸像", "cowboy shot", 1.0),
    # ---- 头与视线 ----
    ("回头|回头看|回眸", "looking back", 1.0),
    ("看着镜头|看镜头|看向观众|面对镜头|面向镜头", "looking at viewer", 1.0),
    ("侧脸|侧颜|侧面", "profile", 1.0),
    ("低头|垂下头|低下头", "looking down", 1.0),
    ("抬头|仰头|抬起头", "looking up", 1.0),
    ("闭眼", "closed_eyes", 1.0),
    # 「睁眼」在 Anima 表里没有通用词，只有 unusually_open_eyes／crying_with_eyes_open，
    # 语义不等价，故不收录，让用户自己决定。
    ("单眼闭|眨一只眼|wink", "one_eye_closed", 1.0),
    ("挑眉|扬起眉毛", "raised eyebrows", 1.0),
    ("皱眉|蹙眉", "furrowed brow", 1.0),
    # ---- 手臂 / 手 ----
    ("举单手|举起一只手|抬起手|举手", "arm up", 1.0),
    ("举起双手|双手举起|双手上举", "arms up", 1.0),
    ("抱胸|交叉手臂|环抱双臂|抱臂", "crossed arms", 1.0),
    ("手放胸前|双手放在胸前|捂胸", "hands on own chest", 1.0),
    ("手放腰|手叉腰|扶腰|叉腰", "hand_on_own_hip", 1.0),
    ("手放腿上|手放大腿", "hands on own thighs", 1.0),
    ("手捧脸|托腮|手托下巴|捧着脸|撑着下巴|托着腮", "hand on own face", 1.0),
    ("手放头上|摸头", "hand on own head", 1.0),
    ("手放嘴边|手捂嘴|捂嘴", "hand over own mouth", 1.0),
    ("手指抵唇|食指抵唇|嘘", "finger to mouth", 1.0),
    ("伸出食指|指着|指向", "pointing", 1.0),
    ("指向观众|指向镜头", "pointing at viewer", 1.0),
    ("比耶|剪刀手|V字手", "v", 1.0),
    ("竖大拇指|点赞", "thumbs up", 1.0),
    ("握拳", "clenched hand", 1.0),
    ("双手合十", "own hands together", 1.0),
    ("牵着手|十指相扣|握手", "holding hands", 1.0),
    ("张开手臂|张开双手|展开双臂", "outstretched arms", 1.0),
    ("单臂伸展|伸出一只手", "outstretched arm", 1.0),
    ("手背在身后|双手背后|反手", "arms behind back", 1.0),
    ("双手垂下|手放身体两侧", "arms at sides", 1.0),
    ("张开手臂|拥抱", "hug", 1.0),
    ("抱着自己|抱住自己|双手抱肩", "hugging own legs", 1.0),
    ("抱着|抱在怀里", "hugging_object", 1.0),
    ("抓着|抓住|握住|紧握|拿着", "holding", 1.0),
    ("举着|举起|抬着|托着", "holding", 1.0),
    ("端着|托着盘子", "holding tray", 1.0),
    ("背着|背着包", "carrying", 1.0),
    ("拉着|扯着|拽着", "pulling", 1.0),
    ("推|推开", "pushing", 1.0),
    ("挥舞|挥动|招手", "waving", 1.0),
    ("鼓掌|拍手", "clapping", 1.0),
    ("耸肩", "shrugging", 1.0),
    ("发抖|颤抖", "trembling", 1.0),
    ("害羞遮脸|捂脸", "covering face", 1.0),
    ("手放桌上|双手撑桌|趴在桌上", "on desk", 1.0),
    # ---- 腿 ----
    ("跷二郎腿|双腿交叠|盘腿|盘膝", "crossed legs", 1.0),
    ("赤脚|光脚", "barefoot", 1.0),
    ("踮脚|脚尖点地", "tiptoes", 1.0),
    ("双腿分开|张开腿", "legs apart", 1.0),
    ("抱膝|抱住膝盖|膝盖抱", "knees up", 1.0),
    # ---- 运动 ----
    ("跳跃|跳起|腾空", "jumping", 1.0),
    ("奔跑|跑|跑步", "running", 1.0),
    ("走路|行走|迈步", "walking", 1.0),
    ("跳舞|舞蹈|舞动", "dancing", 1.0),
    ("飘浮|漂浮|悬浮|飞", "floating", 1.0),
    ("伸展|伸懒腰|舒展身体", "stretching", 1.0),
    # ---- 行为 ----
    ("自拍", "selfie", 1.0),
    ("拿手机|看手机|玩手机", "holding phone", 1.0),
    ("打电话", "phone", 1.0),
    ("看书|阅读|读书", "reading", 1.0),
    ("写字|书写|写东西", "writing", 1.0),
    ("打字|敲键盘", "typing", 1.0),
    ("翻书|翻页", "book", 1.0),
    ("吃东西|进食|吃", "eating", 1.0),
    ("喝水|喝饮料|喝", "drinking", 1.0),
    ("睡觉|睡着了|熟睡|睡", "sleeping", 1.0),
    ("醒来|苏醒", "waking up", 1.0),
    ("弹奏|演奏|弹琴", "playing instrument", 1.0),
    ("唱歌|歌唱", "singing", 1.0),
    ("喊|呼喊|大叫", "shouting", 1.0),
    ("耳语|说悄悄话", "whispering", 1.0),
    ("亲吻|接吻|亲", "kiss", 1.0),
    ("舔嘴唇|舔", "licking lips", 1.0),
    ("咬住|咬着|咬", "biting", 1.0),
    ("咬嘴唇", "biting_own_lip", 1.0),
    ("拿着杯子", "holding_cup", 1.0),
    ("拿着饮料", "holding_drink", 1.0),
    ("歪头", "head_tilt", 1.0),
    # ---- 表情 ----
    ("哭|哭泣|流泪|眼泪", "crying", 1.0),
    ("微笑|笑|笑容", "smile", 1.0),
    ("大笑|狂笑", "laughing", 1.0),
    ("生气|愤怒|发怒", "angry", 1.0),
    ("脸红|害羞|羞红脸|脸泛红", "blush", 1.0),
    ("惊讶|吃惊", "surprised", 1.0),
    ("害怕|恐惧|惊恐", "scared", 1.0),
    ("沉思|思考|想着什么", "thinking", 1.0),
    ("叹气", "sigh", 1.0),
    ("打哈欠", "yawning", 1.0),
    ("面无表情|无表情|扑克脸", "expressionless", 1.0),
    ("张嘴|张着嘴", "open mouth", 1.0),
    ("闭嘴|抿嘴", "closed mouth", 1.0),
    ("嘟嘴|撅嘴", "pout", 1.0),
]

TAG_MAP["场景背景"] = [
    # ---- 室内 ----
    ("教室", "classroom", 1.0),
    ("卧室|房间|室内|屋里", "bedroom", 1.0),
    ("客厅", "living room", 1.0),
    ("厨房", "kitchen", 1.0),
    ("浴室|卫生间|淋浴间|浴室里", "bathroom", 1.0),
    ("图书馆", "library", 1.0),
    ("走廊|过道|楼道", "hallway", 1.0),
    ("天台|屋顶|楼顶", "rooftop", 1.0),
    ("阳台", "balcony", 1.0),
    ("咖啡厅|咖啡馆|咖啡店", "cafe", 1.0),
    ("餐厅|饭店|餐馆", "restaurant", 1.0),
    ("办公室", "office", 1.0),
    ("商店|店铺|店内", "shop", 1.0),
    ("便利店", "convenience store", 1.0),
    ("医院", "hospital", 1.0),
    ("神社", "shrine", 1.0),
    ("寺庙|寺院", "temple", 1.0),
    ("城堡", "castle", 1.0),
    ("宫殿", "castle", 1.0),
    ("废墟", "ruins", 1.0),
    ("地下室", "underground", 1.0),
    ("舞台", "stage", 1.0),
    ("体育馆|体育馆内", "gym", 1.0),
    ("游泳池|泳池", "pool", 1.0),
    ("澡堂|浴场|温泉", "onsen", 1.0),
    # ---- 家具 / 位置 ----
    ("床上|床", "bed", 1.0),
    ("沙发上|沙发", "couch", 1.0),
    ("地板上|地板|地上", "floor", 1.0),
    ("桌子|书桌|课桌", "table", 1.0),
    ("椅子上|椅子", "chair", 1.0),
    ("窗边|窗户|窗前|窗口", "window", 1.0),
    ("门口|门前|门边", "door", 1.0),
    ("楼梯|台阶", "stairs", 1.0),
    ("镜子前|镜子", "mirror", 1.0),
    # ---- 室外 ----
    ("室外|户外", "outdoors", 1.0),
    ("街道|街上|马路|街", "street", 1.0),
    ("城市|都市|城市景观", "city", 1.0),
    ("小巷|胡同|巷子", "alley", 1.0),
    ("公园", "park", 1.0),
    ("花园|花园里", "garden", 1.0),
    ("森林|树林|林子", "forest", 1.0),
    ("海滩|沙滩|海边", "beach", 1.0),
    ("湖畔|湖边|湖", "lake", 1.0),
    ("河边|河畔|河", "river", 1.0),
    ("山上|山间|山", "mountain", 1.0),
    ("田野|原野|田间", "field", 1.0),
    ("草地|草原|草坪", "grass", 1.0),
    ("沙漠", "desert", 1.0),
    ("樱花树|樱花", "cherry blossoms", 1.0),
    ("竹林", "bamboo forest", 1.0),
    ("向日葵田|向日葵", "sunflower", 1.0),
    # ---- 天气 / 时间 ----
    ("天空", "sky", 1.0),
    ("云朵|云", "cloud", 1.0),
    ("星空|繁星|星星", "starry sky", 1.0),
    ("夜晚|晚上|夜里|深夜", "night", 1.0),
    ("白天|日间|白天里", "day", 1.0),
    ("黄昏|傍晚|日落|夕阳西下", "sunset", 1.0),
    ("黎明|日出|清晨|早晨", "sunrise", 1.0),
    ("下雨|雨天|雨中", "rain", 1.0),
    ("下雪|雪天|雪中", "snow", 1.0),
    ("起雾|雾气|雾", "fog", 1.0),
    ("杯子|水杯|杯子里的", "cup", 1.0),
    ("饮料|饮品", "drink", 1.0),
    ("书", "book", 1.0),
    ("礼物", "gift", 1.0),
    ("蛋糕", "birthday_cake", 1.0),
    ("蜡烛", "candle", 1.0),
    ("风|微风吹过", "wind", 1.0),
    # ---- 虚构 / 特殊 ----
    ("科幻|未来", "science_fiction", 1.0),
    ("奇幻|幻想", "fantasy", 1.0),
    ("宇宙|太空|外太空", "space", 1.0),
    ("水下|海底|水中", "underwater", 1.0),
    ("车内|车厢里", "car interior", 1.0),
    ("列车|火车|电车", "train", 1.0),
    ("飞机|机舱", "airplane", 1.0),
    ("宇宙飞船|飞船", "spacecraft", 1.0),
    ("背景虚化|模糊背景", "blurry background", 1.0),
    ("简单背景|纯色背景|白背景", "simple background", 1.0),
]

TAG_MAP["补充细节"] = [
    # ---- 光影 ----
    ("逆光|背光", "backlighting", 1.0),
    ("侧光|侧向光", "sidelighting", 1.0),
    ("昏暗|光线暗淡|暗光|光线昏暗", "dim lighting", 1.0),
    ("午后阳光|阳光|日光|暖光", "sunlight", 1.0),
    ("月光|月色", "moonlight", 1.0),
    ("霓虹灯|霓虹", "neon lights", 1.0),
    ("烛光|蜡烛", "candle", 1.0),
    ("发光|光芒|光辉|泛起微光", "glowing", 1.0),
    ("影子|阴影", "shadow", 1.0),
    ("光束|丁达尔效应|光线射入", "light rays", 1.0),
    ("镜头眩光|光斑闪耀", "lens flare", 1.0),
    ("水面反光|倒影|映出", "reflection", 1.0),
    ("散景|光斑", "bokeh", 1.0),
    ("窗光|窗户透过来的光|从窗户照进来", "sunlight", 1.0),
    # ---- 服装 ----
    ("无袖", "sleeveless", 1.0),
    ("长袖", "long sleeves", 1.0),
    ("短袖", "short sleeves", 1.0),
    ("露肩|一字肩", "off-shoulder_shirt", 1.0),
    ("露背", "backless_outfit", 1.0),
    ("低胸|深V", "cleavage", 1.0),
    ("领带", "necktie", 1.0),
    ("蝴蝶结", "bowtie", 1.0),
    ("解开领口|领口敞开|敞开领口", "open collar", 1.0),
    ("外套|夹克", "jacket", 1.0),
    ("风衣|大衣", "coat", 1.0),
    ("连帽衫|卫衣", "hoodie", 1.0),
    ("毛衣|针织衫", "sweater", 1.0),
    ("连衣裙|洋装", "dress", 1.0),
    ("短裙", "skirt", 1.0),
    ("长裙", "long skirt", 1.0),
    ("百褶裙", "pleated skirt", 1.0),
    ("校服", "school uniform", 1.0),
    ("水手服", "sailor dress", 1.0),
    ("和服", "kimono", 1.0),
    ("浴衣", "yukata", 1.0),
    ("女仆装|女仆", "maid", 1.0),
    ("婚纱", "wedding dress", 1.0),
    ("泳装|泳衣|比基尼", "bikini", 1.0),
    ("死库水|竞技泳衣", "school swimsuit", 1.0),
    ("内衣", "underwear", 1.0),
    ("丝袜|连裤袜", "pantyhose", 1.0),
    ("过膝袜|长筒袜", "thighhighs", 1.0),
    ("短袜|袜子", "socks", 1.0),
    ("手套", "gloves", 1.0),
    ("围巾", "scarf", 1.0),
    ("帽子", "hat", 1.0),
    ("贝雷帽", "beret", 1.0),
    ("发带|发箍", "hairband", 1.0),
    ("发饰|头饰", "hair ornament", 1.0),
    ("耳环|耳坠", "earrings", 1.0),
    ("项链", "necklace", 1.0),
    ("戒指", "ring", 1.0),
    ("手链|手镯", "bracelet", 1.0),
    ("眼镜", "glasses", 1.0),
    ("口罩|面具", "mask", 1.0),
    ("披风|斗篷", "cape", 1.0),
    ("腰带", "belt", 1.0),
    ("靴子|长靴", "boots", 1.0),
    ("高跟鞋", "high heels", 1.0),
    ("鞋子", "shoes", 1.0),
    ("背包|双肩包", "backpack", 1.0),
    ("湿透|湿身|衣服湿了", "wet clothes", 1.0),
    ("卷起袖子", "sleeves_rolled_up", 1.0),
    # ---- 发型 / 外貌 ----
    ("长发|长头发", "long hair", 1.0),
    ("短发|短头发", "short hair", 1.0),
    ("中长发", "medium hair", 1.0),
    ("马尾|马尾辫", "ponytail", 1.0),
    ("双马尾", "twintails", 1.0),
    ("侧马尾", "side ponytail", 1.0),
    ("丸子头|发髻", "hair bun", 1.0),
    ("麻花辫|辫子", "braid", 1.0),
    ("双麻花辫", "twin braids", 1.0),
    ("刘海", "blunt_bangs", 1.0),
    ("齐刘海", "blunt bangs", 1.0),
    ("碎发|翘发", "hair between eyes", 1.0),
    ("卷发", "curly hair", 1.0),
    ("直发", "straight hair", 1.0),
    ("染发|挑染", "multicolored hair", 1.0),
    ("银发|白发", "white hair", 1.0),
    ("金发", "blonde hair", 1.0),
    ("黑发", "black hair", 1.0),
    ("棕发", "brown hair", 1.0),
    ("红发", "red hair", 1.0),
    ("蓝发", "blue hair", 1.0),
    ("粉发", "pink hair", 1.0),
    ("绿发", "green hair", 1.0),
    ("紫发", "purple hair", 1.0),
    ("橙发", "orange hair", 1.0),
    ("渐变色头发|渐变色", "gradient hair", 1.0),
    ("呆毛", "ahoge", 1.0),
    ("兽耳", "animal ears", 1.0),
    ("猫耳", "cat ears", 1.0),
    ("狐耳", "fox ears", 1.0),
    ("精灵耳", "pointy ears", 1.0),
    ("天使翅膀|翅膀", "wings", 1.0),
    ("尾巴", "tail", 1.0),
    ("角|犄角", "horns", 1.0),
    ("光环", "halo", 1.0),
    ("蓝眼睛|蓝瞳", "blue eyes", 1.0),
    ("红眼睛|红瞳", "red eyes", 1.0),
    ("绿眼睛|绿瞳", "green eyes", 1.0),
    ("棕色眼睛|棕瞳", "brown eyes", 1.0),
    ("紫色眼睛|紫瞳", "purple eyes", 1.0),
    ("金色眼睛|金瞳", "yellow eyes", 1.0),
    ("异色瞳", "heterochromia", 1.0),
    ("闭着的眼睛", "closed eyes", 1.0),
    # ---- 氛围 ----
    ("孤独|寂寞", "lonely", 1.0),
    # ---- 镜头 / 视角 ----
    ("俯视|从上往下看|高角度", "from above", 1.0),
    ("仰视|从下往上看|低角度", "from below", 1.0),
    ("近景|近距离", "close-up", 1.0),
    ("远景|远距离|广角", "wide shot", 1.0),
    ("背面视角|背面|背影", "from behind", 1.0),
    ("侧面视角", "from side", 1.0),
    ("倾斜构图|斜角构图", "dutch angle", 1.0),
    ("景深|浅景深", "depth of field", 1.0),
    ("动感|动态模糊", "motion blur", 1.0),
    ("机器人", "robot", 1.0),
    ("安卓|人造人", "android", 1.0),
    ("机甲|机械体", "mecha", 1.0),
    ("半机械|改造人", "cyborg", 1.0),
    ("无脸|看不见脸", "faceless", 1.0),
    ("缎带|丝带", "ribbon", 1.0),
    ("闪烁|闪闪发光|星光点点", "sparkle", 1.0),
    ("头发飘起|头发飘动|发丝飞舞", "floating_hair", 1.0),
    # ---- 画质 / 风格 ----
    ("高质量|高画质|高清", "highres", 1.0),
    ("超高细节|细节丰富|巨细无遗", "absurdres", 1.0),
    ("动漫风|二次元风|动画风", "anime", 1.0),
    ("写实风|真实感", "realistic", 1.0),
    ("赛璐璐|赛璐璐风格", "cel shading", 1.0),
    ("水彩风|水彩画风", "watercolor", 1.0),
    ("单色|黑白", "monochrome", 1.0),
    ("复古|怀旧", "retro", 1.0),
    ("厚涂风|厚涂", "impasto", 1.0),
    ("像素风|像素画", "pixel art", 1.0),
    ("Q版|三头身", "chibi", 1.0),
]

GROUP_ORDER = ["动作姿势", "场景背景", "补充细节"]

# ---------------------------------------------------------------------------
# Anima 质量前缀 / 负向提示词（默认不加，由界面开关控制）
# ---------------------------------------------------------------------------

QUALITY_PREFIX = (
    "masterpiece, very aesthetic, best quality, score_9, score_8, "
    "highres, absurdres, newest"
)

NEGATIVE_PROMPT = (
    "worst quality, low quality, score_1, score_2, score_3, blurry, "
    "bad anatomy, bad hands, bad fingers, extra fingers, missing fingers, "
    "distorted face, jpeg artifacts, text, watermark, logo, signature"
)

# ---------------------------------------------------------------------------
# 匹配引擎
# ---------------------------------------------------------------------------

# 切段：标点、空白
SPLIT_RE = re.compile(r"[,，、;；。：:.!！?？\n\r\t|/＋+()（）\[\]【】\"'“”‘’]+")

# 纯英文 tag 形态
EN_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9 _\-]*$")

# 中文停用词：这些是语法连接成分，不是画面内容，命中它们不算翻译，也不报未命中
STOPWORDS = {
    "的", "了", "着", "在", "是", "有", "和", "与", "或", "把", "被", "让",
    "给", "对", "从", "向", "往", "到", "就", "都", "也", "还", "很", "太",
    "正在", "一个", "一只", "那个", "这个", "然后", "而且", "但是", "因为",
    "所以", "并且", "接着", "同时", "一起", "一些", "有点", "有些", "非常",
    "穿着", "戴着", "拿着", "画面", "感觉", "样子", "表情", "动作", "姿势",
    "以及", "还有", "另外", "其中", "上面", "下面", "里面", "外面", "旁边",
    "镜头", "观众", "视角",
    # 方位 / 身体部位虚指：这些是定位词，不是画面内容
    "手里", "手中", "嘴上", "嘴角", "背后", "面前", "身旁", "身边", "前面",
    "后面", "左侧", "右侧", "上方", "下方", "对面", "尽头", "之外", "之中",
    "之内", "上下", "左右", "前后", "中间", "空中", "半空", "身上", "脸上",
}

# 停用词最长长度
MAX_STOP_LEN = max((len(s) for s in STOPWORDS), default=1)


def _build_index() -> dict[str, list[tuple[str, str, float]]]:
    index: dict[str, list[tuple[str, str, float]]] = {}
    for group, entries in TAG_MAP.items():
        for cn, tag, weight in entries:
            for alias in cn.split("|"):
                alias = alias.strip()
                if alias:
                    index.setdefault(alias, []).append((group, tag, weight))
    return index


INDEX = _build_index()
MAX_KEY_LEN = max((len(k) for k in INDEX), default=1)

# 反查表：英文 tag -> 它属于哪个组。
# 用来把用户直接输入的英文 tag 也归到正确分组，而不是一律塞进「直接输入」。
TAG_TO_GROUP: dict[str, str] = {}
for _group, _entries in TAG_MAP.items():
    for _cn, _tag, _w in _entries:
        TAG_TO_GROUP.setdefault(_tag.lower(), _group)


def _normalize(text: str) -> str:
    """全角转半角 + 规整空白。不做任何语义改写。"""
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def match_chinese(
    segment: str,
) -> tuple[list[tuple[str, str, float]], list[tuple[str, str]]]:
    """
    中文片段最长优先匹配。

    返回 (命中列表, 未命中片段列表)。
    未命中片段形如 (类型, 文本)：类型 "miss" 是没命中的原文，
    "stop" 只作为分隔信号（说明两段未命中之间夹的是语法词，不该粘在一起）。
    原文一律不改写、不猜测。
    """
    hits: list[tuple[str, str, float]] = []
    misses: list[tuple[str, str]] = []
    i = 0
    n = len(segment)
    miss_start = -1

    def flush_miss(end: int, kind: str = "miss") -> None:
        nonlocal miss_start
        if miss_start >= 0:
            frag = segment[miss_start:end]
            if frag:
                misses.append((kind, frag))
            miss_start = -1

    while i < n:
        matched = False
        upper = min(MAX_KEY_LEN, n - i)
        for length in range(upper, 0, -1):
            chunk = segment[i : i + length]
            if chunk in INDEX:
                flush_miss(i)
                for entry in INDEX[chunk]:
                    hits.append(entry)
                i += length
                matched = True
                break
            # 停用词：跳过但留下分隔标记
            if length <= MAX_STOP_LEN and chunk in STOPWORDS:
                flush_miss(i, "stop")
                i += length
                matched = True
                break
        if not matched:
            if miss_start < 0:
                miss_start = i
            i += 1

    flush_miss(n)
    return hits, misses


# 未命中片段里只含这些标点时，视为可拼接的分隔
SOFT_SEP = re.compile(r"[,，、;；\s]+")


def merge_misses(misses: list[tuple[str, str]]) -> list[str]:
    """
    把未命中片段整理成可读列表。

    规则：
      - "stop"（停用词）和短碎片可以跨过去拼接
      - 遇到命中的 tag 或硬标点则断开，避免把两个无关概念粘成一坨
      - 长度不足 2 的字不成词，丢弃
    """
    # 第一遍：按分隔信号拼
    buf = ""
    chunks: list[str] = []
    for kind, text in misses:
        if kind == "stop":
            continue
        # 碎片里已经含词典词（说明它本身是个被拆开的实义词），不再往外粘
        contains_key = any(
            text[i : i + ln] in INDEX
            for i in range(len(text))
            for ln in range(min(MAX_KEY_LEN, len(text) - i), 1, -1)
        )
        # 只粘「两段都是短碎片、粘完仍像个词（≤3 字）、且不含已知实义词」的情况
        if (
            buf
            and len(buf) <= 2
            and len(text) <= 2
            and not contains_key
            and len(buf) + len(text) <= 3
        ):
            buf += text
        elif buf:
            chunks.append(buf)
            buf = text
        else:
            buf = text
    if buf:
        chunks.append(buf)

    # 第二遍：用标点切开，去噪
    out: list[str] = []
    for chunk in chunks:
        for piece in SOFT_SEP.split(chunk):
            piece = piece.strip()
            if len(piece) >= 2:
                out.append(piece)
    return out


def convert(text: str) -> dict:
    """主转换入口。"""
    normalized = _normalize(text)
    groups: dict[str, list[str]] = {g: [] for g in GROUP_ORDER}
    seen: set[str] = set()
    misses: list[tuple[str, str]] = []
    en_tags: list[str] = []

    for raw in SPLIT_RE.split(normalized):
        segment = raw.strip()
        if not segment:
            continue

        # 纯英文片段：按英文 tag 处理
        if EN_TAG_RE.match(segment.lower()):
            tag = segment.lower().replace("_", " ")
            tag = re.sub(r"\s+", " ", tag).strip()
            if tag and tag not in seen:
                seen.add(tag)
                # 词典认识的 tag，归到对应分组；不认识的才进「直接输入」
                known = TAG_TO_GROUP.get(tag)
                if known:
                    groups[known].append(tag)
                else:
                    en_tags.append(tag)
            continue

        hits, seg_misses = match_chinese(segment)

        if not hits:
            # 整段没命中：整段报出来，不拆碎
            if segment not in STOPWORDS:
                misses.append(("miss", segment))
            continue

        # 命中旁边剩下的，作为分隔标记保留
        misses.extend(seg_misses)

        for group, tag, weight in hits:
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            groups[group].append(f"({tag}:{weight})" if weight != 1.0 else tag)

    return {
        "groups": {g: v for g, v in groups.items() if v},
        "misses": merge_misses(misses),
        "en_tags": en_tags,
        "raw": normalized.strip(),
    }


def render(result: dict, with_quality: bool = False, with_negative: bool = False) -> str:
    """把结果渲染成可直接粘贴的文本。"""
    lines: list[str] = ["【分类结果】"]

    if not result["groups"] and not result["en_tags"]:
        lines.append("（无命中）")

    for group in GROUP_ORDER:
        tags = result["groups"].get(group)
        if tags:
            lines.append("")
            lines.append(f"▍{group}（{len(tags)}）")
            lines.append(", ".join(tags))

    if result["en_tags"]:
        lines.append("")
        lines.append(f"▍直接输入的英文 tag（{len(result['en_tags'])}）")
        lines.append(", ".join(result["en_tags"]))

    flat: list[str] = []
    for group in GROUP_ORDER:
        flat.extend(result["groups"].get(group, []))
    flat.extend(result["en_tags"])

    lines.append("")
    lines.append("")
    lines.append("【完整 prompt（可直接粘贴）】")
    body = ", ".join(flat)
    if with_quality:
        body = f"{QUALITY_PREFIX}, {body}" if body else QUALITY_PREFIX
    lines.append(body if body else "（空）")

    if with_negative:
        lines.append("")
        lines.append("")
        lines.append("【负向 prompt】")
        lines.append(NEGATIVE_PROMPT)

    if result["misses"]:
        lines.append("")
        lines.append("")
        lines.append(f"【未命中 · 词典里没有（{len(result['misses'])}）】")
        for m in result["misses"]:
            lines.append(f"  ? {m}")
        lines.append("")
        lines.append("这些片段没有对应 Danbooru tag，按「不脑补」原则未写入 prompt。")
        lines.append("要补的话，在 data/user_dict.json 里加一条映射即可。")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 用户扩展词典
# ---------------------------------------------------------------------------

USER_DICT = Path(__file__).parent / "data" / "user_dict.json"


def load_user_dict() -> int:
    """
    加载 data/user_dict.json：
        {"中文词": ["组名", "english tag"], ...}
        {"中文词": "english tag"}          → 默认归入「补充细节」
    """
    global INDEX, MAX_KEY_LEN, TAG_TO_GROUP

    if not USER_DICT.exists():
        return 0
    try:
        data = json.loads(USER_DICT.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[warn] user_dict.json 解析失败：{exc}", file=sys.stderr)
        return 0

    count = 0
    for cn, val in data.items():
        if isinstance(val, str):
            group, tag = "补充细节", val
        elif isinstance(val, list) and len(val) == 2:
            group, tag = val[0], val[1]
        else:
            continue
        if group not in TAG_MAP:
            group = "补充细节"
        TAG_MAP[group].append((cn, tag, 1.0))
        count += 1

    INDEX = _build_index()
    MAX_KEY_LEN = max((len(k) for k in INDEX), default=1)

    # 重建英文反查表
    TAG_TO_GROUP = {}
    for group, entries in TAG_MAP.items():
        for _cn, tag, _w in entries:
            TAG_TO_GROUP.setdefault(tag.lower(), group)

    return count


# ---------------------------------------------------------------------------
# 界面
# ---------------------------------------------------------------------------
# 设计口径：长时间阅读中文文本的生产力工具。
#   - 浅色冷灰基底，不用纯黑也不跳深色块
#   - 只用一个强调色（深青绿），不做渐变，不用 AI 紫蓝
#   - 输出区卡片化：折叠给完整 prompt，展开追加分类明细，每卡自带复制
#   - 卡片边框处显示该卡片的 tag 数与字数

C = {
    "bg": "#F2F4F6",
    "card": "#FFFFFF",
    "field": "#FBFCFD",
    "border": "#DFE4E8",
    "border_soft": "#E9EDF0",
    "text": "#1B2733",
    "text2": "#5A6874",
    "text3": "#93A1AD",
    "accent": "#0F5257",
    "accent_hover": "#16676D",
    "accent_down": "#0A3D41",
    "accent_tint": "#E6F0EF",
    "warn": "#A15C00",
    "ok": "#2E7D5B",
    # 分类色 = 强调色的深浅变体，不引入新色相
    "g1": "#0F5257",
    "g2": "#2A6F74",
    "g3": "#4A8C90",
}

F = {
    "title": ("Microsoft YaHei UI", 19, "bold"),
    "sub": ("Microsoft YaHei UI", 10),
    "h2": ("Microsoft YaHei UI", 12, "bold"),
    "lab": ("Microsoft YaHei UI", 9),
    "body": ("Microsoft YaHei UI", 11),
    "mono": ("Consolas", 11),
    "mono_sm": ("Consolas", 9),
}

PAD = 16
GAP = 12


def _enable_dpi() -> None:
    """高分屏下不让文字发虚。失败不影响功能。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _round_rect(cv, x1, y1, x2, y2, r, **kw):
    """tkinter 没有原生圆角，用平滑多边形近似。"""
    r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


def _flatten_scroll(widget, tk) -> None:
    widget.vbar.configure(width=10, relief="flat", borderwidth=0)


def build_positive(result: dict) -> str:
    """组装正面提示词：质量前缀 + 三个分组 + 直接输入的英文 tag。"""
    body: list[str] = []
    for group in GROUP_ORDER:
        body.extend(result["groups"].get(group, []))
    body.extend(result["en_tags"])
    core = ", ".join(body)
    if not core:
        return ""
    return f"{QUALITY_PREFIX}, {core}"


def count_tags(text: str) -> int:
    return len([t for t in text.split(",") if t.strip()])


def run_gui(demo: str = "") -> None:
    import tkinter as tk
    from tkinter import scrolledtext

    _enable_dpi()
    n_user = load_user_dict()

    root = tk.Tk()
    root.title("Anima 中文提示词转换器")
    root.configure(bg=C["bg"])
    root.geometry("1180x900")
    root.minsize(1000, 720)

    # ---------------- 顶部 ----------------
    head = tk.Frame(root, bg=C["bg"])
    head.pack(fill="x", padx=PAD, pady=(PAD, 6))
    tk.Label(head, text="Anima 提示词转换器", font=F["title"], bg=C["bg"], fg=C["text"]).pack(side="left")
    status = tk.Label(head, text="", font=F["lab"], bg=C["bg"], fg=C["ok"])
    status.pack(side="right", pady=(8, 0))

    # ---------------- 主体 ----------------
    body = tk.Frame(root, bg=C["bg"])
    body.pack(fill="both", expand=True, padx=PAD, pady=(GAP + 2, 0))
    body.columnconfigure(0, weight=4, uniform="col")
    body.columnconfigure(1, weight=6, uniform="col")
    body.rowconfigure(0, weight=1)

    # ---- 左：输入 ----
    left = tk.Frame(body, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, GAP // 2))

    lh = tk.Frame(left, bg=C["card"])
    lh.pack(fill="x", padx=PAD, pady=(PAD - 4, 6))
    tk.Label(lh, text="输入", font=F["h2"], bg=C["card"], fg=C["text"]).pack(side="left")
    counter = tk.Label(lh, text="0 字", font=F["lab"], bg=C["card"], fg=C["text3"])
    counter.pack(side="right")

    src = scrolledtext.ScrolledText(
        left, height=10, wrap="word", font=F["body"], bg=C["field"], fg=C["text"],
        insertbackground=C["accent"], relief="flat", borderwidth=0, padx=10, pady=8,
        highlightthickness=1, highlightbackground=C["border"], highlightcolor=C["accent"],
    )
    src.pack(fill="both", expand=True, padx=PAD)
    _flatten_scroll(src, tk)

    tk.Label(
        left,
        text=f"正面提示词已默认带质量前缀，负向提示词默认输出。",
        font=F["lab"], bg=C["card"], fg=C["text3"], anchor="w", justify="left",
    ).pack(fill="x", padx=PAD, pady=(GAP, PAD))

    # ---- 右：输出 ----
    right = tk.Frame(body, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
    right.grid(row=0, column=1, sticky="nsew", padx=(GAP // 2, 0))

    rh = tk.Frame(right, bg=C["card"])
    rh.pack(fill="x", padx=PAD, pady=(PAD - 4, 6))
    tk.Label(rh, text="输出", font=F["h2"], bg=C["card"], fg=C["text"]).pack(side="left")
    totals = tk.Label(rh, text="", font=F["lab"], bg=C["card"], fg=C["text3"])
    totals.pack(side="left", padx=(10, 0), pady=(3, 0))

    body_out = tk.Frame(right, bg=C["card"])
    body_out.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))
    body_out.columnconfigure(0, weight=1)

    state = {"result": None, "cards": [], "row": 0, "expanded": False}

    def set_status(text: str, color: str = None) -> None:
        status.configure(text=text, fg=color or C["ok"])

    # ---------------- 通用按钮（Canvas 圆角） ----------------
    def make_button(parent, label, command, primary: bool, width=132, height=38, bg=None):
        base = bg or C["bg"]
        hover = C["accent_hover"] if primary else C["field"]
        down = C["accent_down"] if primary else C["border_soft"]
        fg = "#FFFFFF" if primary else C["text2"]

        cv = tk.Canvas(parent, width=width, height=height, bg=base, highlightthickness=0, bd=0)
        cv.pack(side="left", padx=(0, 8))

        def draw(fill):
            cv.delete("all")
            _round_rect(cv, 0, 0, width - 1, height - 1, 8 if height > 30 else 6,
                        fill=fill, outline="" if primary else C["border"])
            cv.create_text(width // 2, height // 2, text=label,
                           font=("Microsoft YaHei UI", 10, "bold") if primary else F["lab"], fill=fg)

        cv.bind("<Enter>", lambda e: draw(hover))
        cv.bind("<Leave>", lambda e: draw(base if not primary else C["accent"]))
        cv.bind("<ButtonPress-1>", lambda e: draw(down))
        cv.bind("<ButtonRelease-1>", lambda e: (draw(hover), command()))
        cv.configure(cursor="hand2")
        draw(C["accent"] if primary else base)
        return cv

    # ---------------- 输出卡片 ----------------
    def copy_glyph(cv, x, y, color):
        """复制图标：两个错位矩形，不依赖字体符号。"""
        cv.create_rectangle(x - 7, y - 8, x + 3, y + 2, outline=color, width=1)
        cv.create_rectangle(x - 3, y - 4, x + 7, y + 6, outline=color, width=1, fill=C["field"])

    def make_card(parent, key, title, rows, mono=True) -> tuple:
        card = tk.Frame(parent, bg=C["card"], highlightbackground=C["border_soft"], highlightthickness=1)
        card.grid(row=state["row"], column=0, sticky="ew", pady=(0, 8))
        state["row"] += 1
        card.columnconfigure(0, weight=1)

        hd = tk.Frame(card, bg=C["card"])
        hd.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 2))

        meta = tk.Label(hd, text=title, font=F["lab"], bg=C["card"], fg=C["text2"], anchor="w")
        meta.pack(side="left")

        icv = tk.Canvas(hd, width=24, height=20, bg=C["card"], highlightthickness=0, bd=0, cursor="hand2")
        icv.pack(side="right")

        def draw_icon(hover=False):
            icv.delete("all")
            copy_glyph(icv, 9, 10, C["accent"] if hover else C["text3"])

        icv.bind("<Enter>", lambda e: draw_icon(True))
        icv.bind("<Leave>", lambda e: draw_icon(False))
        icv.bind("<ButtonRelease-1>", lambda e: copy_card())
        draw_icon()

        txt = tk.Text(
            card, height=rows, wrap="word", font=F["mono"] if mono else F["body"],
            bg=C["field"], fg=C["text"], relief="flat", borderwidth=0, padx=8, pady=6,
            highlightthickness=1, highlightbackground=C["border_soft"],
        )
        txt.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        def copy_card(_e=None):
            content = txt.get("1.0", "end").strip()
            if not content:
                set_status("这张卡片还没有内容", C["warn"])
                return
            root.clipboard_clear()
            root.clipboard_append(content)
            label = meta.cget("text").split("　·　")[0]
            set_status(f"已复制「{label}」", C["ok"])

        entry = {"key": key, "card": card, "txt": txt, "meta": meta, "title": title}
        state["cards"].append(entry)
        return card, txt, meta

    def render_cards(result: dict, expanded: bool) -> None:
        for w in body_out.winfo_children():
            w.destroy()
        state["cards"] = []
        state["row"] = 0

        groups = result["groups"]
        make_card(body_out, "positive", "正面提示词", 4 if expanded else 3, mono=True)
        make_card(body_out, "negative", "负向提示词", 4, mono=True)

        if expanded:
            for g, _col in (("动作姿势", C["g1"]), ("场景背景", C["g2"]), ("补充细节", C["g3"])):
                tags = groups.get(g, [])
                if tags:
                    make_card(body_out, f"g::{g}", g, min(4, max(1, len(tags) // 6 + 1)))
            if result["misses"]:
                make_card(body_out, "miss", "未命中", min(5, max(1, len(result["misses"]) // 2 + 1)), mono=False)

        for item in state["cards"]:
            key = item["key"]
            if key == "positive":
                body = build_positive(result)
            elif key == "negative":
                body = NEGATIVE_PROMPT
            elif key == "miss":
                body = "\n".join(f"? {m}" for m in result["misses"])
            elif key.startswith("g::"):
                body = ", ".join(groups.get(key[3:], []))
            else:
                body = ""

            txt = item["txt"]
            txt.delete("1.0", "end")
            if body:
                txt.insert("1.0", body)

            # 卡片边框统计：未命中卡报「条数」，其余报「tag 数 + 字数」
            if key == "miss":
                stat = f"{item['title']}　·　{len(result['misses'])} 条　·　{len(body)} 字"
            else:
                stat = f"{item['title']}　·　{count_tags(body) if body else 0} tag　·　{len(body)} 字"
            item["meta"].configure(text=stat)

    # ---------------- 展开 / 收起 ----------------
    exp_holder = tk.Frame(rh, bg=C["card"])
    exp_holder.pack(side="right")

    def toggle_expand() -> None:
        state["expanded"] = not state["expanded"]
        refresh()

    def draw_expand_btn() -> None:
        for w in exp_holder.winfo_children():
            w.destroy()
        make_button(
            exp_holder,
            "收起分类" if state["expanded"] else "展开分类",
            toggle_expand,
            primary=False,
            width=92,
            height=26,
            bg=C["card"],
        )

    def refresh() -> None:
        result = state["result"] or {"groups": {}, "misses": [], "en_tags": []}
        draw_expand_btn()
        render_cards(result, state["expanded"])
        n_hit = sum(len(v) for v in result["groups"].values()) + len(result["en_tags"])
        if n_hit:
            totals.configure(text=f"{n_hit} tag · {len(result['misses'])} 未命中")
        else:
            totals.configure(text="")

    # ---------------- 行为 ----------------
    def update_counter(_e=None):
        counter.configure(text=f"{len(src.get('1.0', 'end').strip())} 字")

    def do_convert(event=None) -> None:
        text = src.get("1.0", "end").strip()
        if not text:
            set_status("先粘一段中文进来", C["warn"])
            src.focus_set()
            return
        state["result"] = convert(text)
        refresh()
        set_status("")

    def clear_all() -> None:
        src.delete("1.0", "end")
        state["result"] = None
        refresh()
        update_counter()
        set_status("")

    bar = tk.Frame(root, bg=C["bg"])
    bar.pack(fill="x", padx=PAD, pady=(GAP, PAD))
    make_button(bar, "转换", do_convert, primary=True, width=140)
    make_button(bar, "清空", clear_all, primary=False, width=76)

    hint = "Ctrl+Enter 转换"
    if n_user:
        hint = f"已加载扩展词库 {n_user} 条 · {hint}"
    tk.Label(bar, text=hint, font=F["lab"], bg=C["bg"], fg=C["text3"]).pack(side="right", pady=10)

    refresh()
    src.bind("<Control-Return>", do_convert)
    src.bind("<KeyRelease>", update_counter)
    root.bind("<Escape>", lambda e: root.destroy())
    update_counter()
    src.focus_set()

    # --demo：预填示例并自动转换，供截图验收
    if demo:
        src.delete("1.0", "end")
        src.insert("1.0", demo)
        update_counter()
        actual = src.get("1.0", "end").strip()
        if actual != demo:
            print(f"[demo] 输入框内容与预期不一致\n  预期: {demo!r}\n  实际: {actual!r}", file=sys.stderr)
        src.after(250, do_convert)
        if "--expand" in sys.argv:
            src.after(700, toggle_expand)

    root.mainloop()


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_gui(demo="一个女孩站在天台边缘，风吹起短发，手里拿着饮料，夜空中星星闪烁，霓虹灯的光打在她脸上")
        return
    if len(sys.argv) > 1:
        load_user_dict()
        print(render(convert(" ".join(sys.argv[1:]))))
    else:
        run_gui()


if __name__ == "__main__":
    main()
