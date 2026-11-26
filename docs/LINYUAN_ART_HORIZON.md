# 《临渊御剑》美术风格 v1.0

修订：2026-11-26。本文是《临渊御剑》的美术基准。2026-11-25 按《地平线》系列的美术风格出了九张测试图，需求方确认采用这个方向，[世界观](LINYUAN_WORLD.md)、[策划案](LINYUAN_PLAN.md)、[第一章分镜](LINYUAN_CH1_STORYBOARD.md) 和 [第一章提示词](LINYUAN_CH1_PROMPTS.md) 已按它重写。

测试图在 `output/imagegen/linyuan_art_horizon_20261125/`，每张两个候选。本文先写评审结论和选用，再保留当时的风格要点和九条测试提示词，作为出图的原始依据。

## 评审结论

### 成立的部分

- **世界一眼就成立。** 喀斯特山峰、玉色江水、长满青苔的古镇遗迹和白色机关兽放在一起，武侠山水和机关科技是长在一起的，不是贴在一起的。
- **画面明亮、好看。** 18 张图都是午后或黄金时段，没有一张压抑。
- **机关兽是同一套设计。** 狻猊、毕方、饕餮的陶瓷甲、石墨框架、黑色肌肉纤维和蓝色接缝光完全一致，又各有清楚的动物轮廓。
- **颜色语言成立。** 平静的蓝眼和敌对的红眼一眼可分；琥珀罐在每张图里都是最醒目的部件，被打飞的罐子散落在地上，击毁状态很好读。
- **第一人称战斗帧的轮廓可辨。** AH_POV 里扑来的狻猊占画面约四分之一，两只肩罐和红眼在缩图后仍然清楚。瞄准、命中和接力手感在 A-2 实际出剑时验证。
- **人物的手工艺融合成立。** 陆沉的麻布、皮带、红绳结和绑上去的机关肩甲，云姨缠布条的机关前臂，都是我们要的"江湖人用机关零件"。
- **营地有烟火气。** AH_CAMP 的面摊、蒸汽、孩子和神龛头骨，直接成了九曲渡集市的母版。
- **模型自发画出了天机环。** 多张图的远景里都出现了一座巨大的断环遗迹。它被采纳为全片地标"天机环"。

### 要修的部分

| 问题 | 出现在 | 处理 |
|---|---|---|
| 陆沉的剑匣像箭筒，剑柄像箭杆 | AH_LUCHEN_01、02 | 改成扁宽的木剑匣，8 柄剑柄带小护手（提示词 CH_LUCHEN） |
| 陆沉左右臂的义肢在不同视图里不一致 | AH_LUCHEN_01 | 只有左臂是义肢，右臂是普通的手（提示词 CH_LUCHEN） |
| 青萍的脸偏偶像化 | AH_QINGPING_01、02 | 可选修订：去掉妆感，保留俏皮（提示词 CH_QINGPING） |
| 画面太满：紫色花丛、藤蔓、光柱铺满每个角落 | 所有图 | 战斗母版清理中景，细碎植被只留在画面边缘 |
| 太阳和光柱靠近可打区域，暖光和琥珀罐混在一起 | AH_BAMBOO_02、AH_POV_01 | 太阳移出画外，暖光不靠近出场位（提示词 PL_BAMBOO） |
| 天机环出现在几乎每张图里 | 所有图 | 只在分镜指定的镜头里出现 |
| 布棚和旗帜上可能有像字的纹样 | AH_CAMP_01、02 | 改成素布或编织纹样（提示词 PL_MARKET） |

### 选用

| 测试图 | 选用 | 用作 |
|---|---|---|
| AH_VISTA | 02 | PL_VISTA、KF_C1_01 的风格和玄武造型参考 |
| AH_BAMBOO | 02 | PL_BAMBOO 的底图，按提示词修订 |
| AH_SUANNI | 02 | EN_SUANNI 定稿，所有机关兽的材质基准 |
| AH_BIFANG | 02 | EN_BIFANG 定稿 |
| AH_TAOTIE | 02 | EN_TAOTIE 定稿 |
| AH_LUCHEN | 02 | CH_LUCHEN 的底图，修剑匣和义肢 |
| AH_POV | 01、02 | 战斗帧的构图和可读性参考，不直接入片 |
| AH_QINGPING | 02 | CH_QINGPING 定稿，可选修订脸部 |
| AH_CAMP | 02 | PL_MARKET 的底图；CH_YUNYI 的长相参考 |

### 进入视频前要验证的

测试图都是静帧。H3 视频能不能保持这种风格化写实，以及竹叶、花草在接缝处会不会跳动，要在 [MVP](LINYUAN_MVP.md) 的 A-2 三组动态试片里先验，再批量生成。

## 风格要点（测试时的原始依据）

提示词里不写游戏名，只描述具体的视觉特征，以免模型照抄现成的角色和机器。

- **画面。** 高端 3A 开放世界游戏的风格化写实。黄金时段或晴朗白天，体积光，远景按层次退进蓝色空气里。颜色饱满自然，整体明亮、乐观。
- **世界。** 自然重新接管古代文明的遗迹。这里换成中国山水：喀斯特山峰、竹海、云海、梯田，以及长满青苔的古镇、石桥和塔。
- **机器。** 以动物为原型，轮廓远看能认，块面大。白色陶瓷质感的装甲板，深石墨色框架，露出黑色纤维肌肉。这里的原型换成《山海经》和中国传统瑞兽：玄武、狻猊、毕方、饕餮。
- **颜色就是玩法信息。** 眼睛蓝色表示平静，红色表示敌对。琥珀金色的发光罐体是弱点，可以被打掉。
- **人物。** 部落手工艺加上回收的机器零件：麻布、靛染布、皮带、漆竹甲、红绳结，再配拆下来的白色机器装甲片。

## 九张测试图

| 编号 | 内容 | 检验什么 |
|---|---|---|
| H1 | 山水远景：玄武巨兽涉江 | 世界整体风格和尺度感 |
| H2 | 竹海空场 | 战斗母版是否明亮、好打 |
| H3 | 狻猊四态 | 中型地面敌人 |
| H4 | 毕方四态 | 小型飞行敌人 |
| H5 | 饕餮四态 | 第一章 Boss |
| H6 | 陆沉定妆 | 主角的手工艺和机器零件融合 |
| H7 | 第一人称战斗帧 | 缩到游戏显示大小后，目标和弱点是否一眼可读 |
| H8 | 青萍定妆 | 全息剑灵在白天自然光下是否成立 |
| H9 | 江湖营地 | 人和机器共存的日常生活感 |

## 公共风格段

已经写进下面每条提示词的开头和结尾，单独列在这里方便复用。

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
```

```text
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
```

## 机器的共同设计语言

H3、H4、H5、H7 共用，已经写进各条提示词。

```text
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
```

## H1 · 山水远景 · AH_VISTA

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
One 16:9 panoramic establishing frame. A vast karst landscape: tall limestone peaks with pine trees rise out of a wide jade-green river, early morning golden sun breaking through mist between the peaks. On the near river bank lie the overgrown remains of an ancient Jiangnan water town: a half-collapsed granite arch bridge, tiled roofs carpeted with moss and wild bamboo, a broken stone pagoda wrapped in vines, a toppled carved stone lion half buried in wildflowers in the foreground.
In the middle distance a colossal machine inspired by the mythical Black Tortoise wades slowly across the river, about forty meters long. Its shell is a terraced dome of off-white ceramic-like armor plates with thin pale-blue seam lights, and on top of the shell grows a small grove of trees around an abandoned stone pavilion. A long armored serpentine neck with a calm glowing blue eye, thick pillar-like legs of graphite frame and black muscle fibers, water streaming off them. Birds lift off the river.
On the broken bridge, a few tiny travellers with poles, bundles and plain cloth banners watch it pass, for scale.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_VISTA. Deliver one 16:9 landscape image.
```

## H2 · 竹海空场 · AH_BAMBOO

战斗用的空场母版。画面里不放任何生物，中景留出大片空地给敌人出场。

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
One 16:9 eye-height gameplay plate, 35mm lens. A sunlit clearing in a vast bamboo forest in late afternoon. Warm golden shafts of light between the tall green stalks, drifting pollen and floating leaves in the beams, soft blue haze deeper in the forest. A shallow clear stream crosses the clearing over smooth stones. At mid-left, the mossy ruin of a small stone shrine with a toppled statue and a cracked incense burner; at mid-right, a few fallen bamboo trunks and a large mossy boulder; old stone steps leading away into the forest at the back. Foreground framing at the very edges only: bamboo leaves on the left, ferns on the right. The midground is open, bright and evenly readable, a natural arena.
Empty scene: no people, no animals, no machines.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_BAMBOO. Deliver one 16:9 landscape image.
```

## H3 · 狻猊 · AH_SUANNI

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
Production-design sheet, one 16:9 image showing four views of the same machine creature in a sunlit bamboo-forest clearing, evenly spaced left to right with clear separation: 1) front, calm, standing; 2) side profile, walking; 3) crouched to pounce, hostile; 4) destroyed, collapsed on its side.
Subject: a Suanni, a predator machine the size of a large horse, inspired by Chinese stone guardian lions and big cats but not a literal lion. Broad deep chest, head carried high, a crown of large overlapping curled mane plates that flare outward when hostile. Powerful thick legs with heavy paws.
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
Specifics: in view 1 eyes glow cool blue and the mane lies flat; in view 3 the eyes glow red, mane flared, jaw open. Two amber-gold glowing canisters are mounted on either flank behind the shoulders, and one amber-gold cell glows inside the open mouth in view 3. View 4: eyes dark, one flank canister blown off and lying on the ground, several mane and armor plates knocked loose, muscle fibers slack, thin smoke and sparks.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_SUANNI. Deliver one 16:9 landscape image.
```

## H4 · 毕方 · AH_BIFANG

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
Production-design sheet, one 16:9 image showing four views of the same flying machine against a bright sky over misty karst peaks and rice terraces, evenly spaced left to right with clear separation: 1) perched calmly on one leg on a mossy rock; 2) gliding side view, wings fully spread; 3) diving attack toward the viewer, hostile; 4) crashed on the ground, broken.
Subject: a Bifang, a flying machine inspired by the crane and the mythical one-legged fire bird, wingspan about three meters. Long elegant neck, a single strong leg with a large gripping talon, broad segmented wings made of layered off-white vanes with thin pale-blue edges, a tail of long ribbon-like fins.
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
Specifics: one large amber-gold glowing fuel sac sits in the center of its chest, the weak point. In view 3, eyes glow red and small flaming darts fire from under the wings. View 4: lying in the grass, one wing snapped, chest sac cracked and dark, feathers of armor scattered, thin smoke.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_BIFANG. Deliver one 16:9 landscape image.
```

## H5 · 饕餮 · AH_TAOTIE

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
Production-design sheet, one 16:9 image showing four views of the same colossal boss machine on the wide stony bank of a river among karst peaks under a bright sky, evenly spaced left to right with clear separation: 1) front, calm, standing; 2) side profile; 3) charging toward the viewer, hostile, maw open; 4) defeated, kneeling and broken.
Subject: a Taotie, a colossal armored quadruped about eight meters tall, built like a cross between a rhinoceros, a bull and a bear. Its huge head and face are shaped after the taotie mask of ancient Chinese bronze vessels: wide symmetrical brow ridges, curling horns and big round eyes, read clearly in silhouette. Massive shoulders, short pillar legs, a heavy armored back with a ridge of plates.
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
Specifics: in view 3 the jaws open wide to reveal a large amber-gold glowing core deep in the maw, and two amber-gold canisters on its back swing up into view. Each canister is as big as a person and easy to aim at from far away. View 4: kneeling on its front legs, eyes dark, one horn broken, the back canisters blown off and lying on the rocks, armor plates cracked, smoke and sparks.
Add small human travellers at the edge of view 1 for scale.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_TAOTIE. Deliver one 16:9 landscape image.
```

## H6 · 陆沉定妆 · AH_LUCHEN

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
Character reference sheet, one 16:9 image outdoors on a sunlit mossy stone terrace with soft out-of-focus bamboo behind, natural daylight. Four views of the same man, evenly spaced: full-body front, full-body three-quarter, full-body back, and a larger face close-up on the right.
Subject: Lu Chen, a 24-year-old Chinese wandering swordsman of a river clan. A strong, distinctive, slightly asymmetric face with weathered skin, a healed scar along the jaw, short untidy black hair, steady watchful eyes; handsome in a rugged way, not an idol face.
Costume, hand-made from natural materials and salvaged machine parts: layered hand-woven hemp and indigo-dyed cloth with a crossed collar, a wide wrapped sash, leather straps and buckles, lacquered bamboo armor pieces on the thigh, red cord knots and a few carved wood beads. His left shoulder guard is a repurposed off-white machine armor plate, scratched and lashed on with rope. His whole left arm is a mechanical prosthesis built from salvaged machine parts: graphite frame, black muscle fibers and pale ceramic plates, wrapped with cloth strips.
On his back, a long old wooden sword case reinforced with machine parts and rope, its lid open at the top to show the hilts of eight slim flying swords in a row, small pale-blue glowing tassels.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_LUCHEN. Deliver one 16:9 landscape image.
```

## H7 · 第一人称战斗帧 · AH_POV

这张用来检验光枪玩法：目标要大，和背景要有明暗或颜色的反差，琥珀色弱点一眼能找到。画面里不出现玩家的手和武器，准星和界面由引擎绘制。

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
One 16:9 first-person gameplay keyframe at eye height, 35mm lens, in a sunlit bamboo-forest clearing in late afternoon with a shallow stream and a mossy ruined stone shrine at mid-left. A Suanni lion-like predator machine, about the size of a horse, leaps out from behind the shrine and charges straight toward the viewer, filling about a quarter of the frame, mid-stride, water splashing under its heavy paws, mane plates flared.
Faction design language shared by all machines: smooth off-white ceramic-like armor plates with fine thin pale-blue seam lights, a dark graphite load-bearing frame, exposed bundles of black synthetic muscle fibers and cables in the joints and gaps, hydraulic pistons at the limbs. Calm state: eyes glow cool blue. Hostile state: eyes glow red. Weak points are separate glowing amber-gold canisters or cells, clearly attached and visibly detachable; they are the only amber-gold elements on the machine. Animal-like, alive, weighty and believable, with large readable surfaces and no thin spindly limbs.
Specifics: eyes glow red; two amber-gold canisters on its flanks behind the shoulders are clearly visible and lit by the sun. Two more of the same machines prowl further back between the bamboo, eyes red, smaller in frame. The attacking machine is in sharp focus and stands out clearly from the background by its pale armor against the darker green forest. Dust, leaves and spray caught in the golden light.
No hands, weapons or body of the viewer in frame.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_POV. Deliver one 16:9 landscape image.
```

## H8 · 青萍定妆 · AH_QINGPING

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
Character reference sheet, one 16:9 image outdoors on the same sunlit mossy stone terrace with soft bamboo behind, natural daylight. Four views of the same character, evenly spaced: full-body front, full-body three-quarter, full-body back, and a larger face close-up on the right.
Subject: Qingping, a sword spirit who exists only as a projected light-form, appearing as a Chinese girl of about eighteen with a lively, cheeky, distinctive face, a high ponytail tied with a long ribbon, a narrow-sleeved martial-arts robe with a crossed collar, wrapped belt and wide trousers. Her figure is made of pale-blue light that holds up in bright sunlight: semi-transparent so the bamboo and stones behind are visible through her, edges defined by fine flowing light lines along the seams of her clothes, a faint shimmer of tiny light particles around her outline, her feet hovering a hand's width above the stones. She casts no shadow.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_QINGPING. Deliver one 16:9 landscape image.
```

## H9 · 江湖营地 · AH_CAMP

```text
High-end AAA open-world action-adventure game key art in stylized realism with a hand-crafted feel. Rich, saturated but natural color; clean, highly detailed, physically based materials; crisp, strong, readable silhouettes; bright daylight or golden-hour sun with volumetric light rays; deep atmospheric perspective with layered blue haze in the distance; lush vegetation reclaiming ancient ruins; beautiful, adventurous and optimistic mood. Original fictional world inspired by Chinese landscapes, Chinese mythology and wuxia, centuries after a lost high-tech age.
One 16:9 establishing frame at golden hour. A river clan's camp built inside and around the overgrown ruins of an ancient water-town square, beside a jade river with karst peaks behind. Houses are rebuilt from old stone walls, bamboo, woven mats and salvaged off-white machine armor plates used as roofing and walls. In the center, a busy open-air noodle stall under a large patched cloth awning: steam rising from big pots heated by a salvaged machine power cell glowing soft blue, bowls on long wooden tables, lanterns of paper and machine parts. A middle-aged woman cook with a cloth-wrapped mechanical forearm serves noodles; villagers in hand-woven clothes eat, talk, mend nets. A huge horned machine skull, long dead and overgrown with moss and flowers, stands at the edge of the square as a shrine, decorated with red cord and offerings. Children play on a fallen machine plate. Smoke, warm sunlight and long shadows.
No captions, interface, HUD, reticle, crosshair, legible text, letters, numbers or Chinese characters, watermark, logos, real-world brands, existing game characters or creatures, black bars, borders or panel frames. No anime, no cartoon or cel shading, no toy or figurine finish, no painterly brushwork. No night, no underexposure, no grimdark mood, no neon cyberpunk city, no steampunk brass or gold filigree on machines. No blood, no gore.
Asset AH_CAMP. Deliver one 16:9 landscape image.
```

## 后续出图的用法

- 公共风格段、负面段和机关兽设计语言已并入 [第一章提示词 §1.4](LINYUAN_CH1_PROMPTS.md#14-公共段)，正式出图以那里为准。本文的九条测试提示词只作为原始依据保留。
