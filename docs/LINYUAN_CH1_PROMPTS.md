# 《临渊御剑》第一章：出图与视频提示词 v0.1

日期：2026-11-24。镜号、出场位和时间结构见 [第一章分镜](LINYUAN_CH1_STORYBOARD.md)。人物与设计语言见 [世界观](LINYUAN_WORLD.md)。

提示词沿用长安的实际做法，用英文书写：关键帧用 ChatGPT 出图，视频用本机 H3。每条可整段复制。`[S]`、`[N]` 等方括号段落是本文第 1 节的公共段，使用时展开成全文。

---

## 1. 使用说明

### 1.1 制作顺序

1. 角色设定图（第 2 节）和敌人设定图（第 3 节）。每张多出几版，挑一张锁定。铁衣卫最先定稿。
2. 场面母版（第 4 节）。PL_ALLEY 是下城的母版，其余下城场面都上传它作风格参考。
3. 剧情首帧和状态锚帧（第 5 节）。按每条写明的参考图上传。
4. 视频（第 6–8 节）。战斗波次和击毁片的首尾帧都用场面母版；击毁片的首帧从已选定的波次成片里取第 28、42、56 帧。

### 1.2 尺寸和存放

- 关键帧输出 16:9 满幅，不留黑边。H3 以 1024 × 576 生成，成片 1280 × 720。重要内容避开画面上下各 5% 的边缘。
- 原图存到 `assets/linyuan/kf_raw/`，文件名用编号，例如 `CH_LUCHEN.png`、`PL_ALLEY.png`。候选加后缀 `_b`、`_c`，不带后缀的是选定版。
- 视频任务写进 `worlds/linyuan/production/c1_jobs.json`，字段沿用长安：`first`、`last`、`length`、`seed`、`prompt`、`prefix`。

### 1.3 检查项

所有图：
- 画面里没有可读的文字和汉字。招牌只能是光带、几何图形或白色眼形图标。模型画出文字就重抽，不靠后期修。
- 没有真实品牌、血、断肢。
- 雨的强度：战斗场面是中雨，剧情可以更大。

角色：
- 陆沉的黄铜义肢在左臂，剑匣斜挎在背上，8 束青色剑穗。
- 青萍是半透明的全息投影，能透过她看见背景。

敌人：
- 一眼看得出是机器，不是穿戏服的人。
- 自发光部件（眼缝、镜头、核心、关节环）清楚，缩到 1280 × 720 仍然醒目。
- 在 1280 × 720 下，普通目标的短边至少 48 像素，远处目标至少 32 像素，弱点至少 20 像素。

场面母版：
- 没有人，没有敌人。
- 分镜表里列出的每个遮挡物都在，位置大致正确。

### 1.4 公共段

**[S] 风格段（所有关键帧）**

```
Original live-action near-future Chinese cyberpunk wuxia film, year 2071, in a fictional vertical megacity built on top of an old Jiangnan water town. Physically believable night lighting: practical neon light bars in magenta and teal, warm tungsten from food stalls and windows, cool diffuse spill from the city levels far above, steady medium rain, wet reflective stone, drifting steam with readable depth. Real materials: weathered granite arch bridges, dark timber arcade houses and stilt houses, rusted steel viaducts, dense cables and pipes, oiled-paper umbrellas and clear plastic umbrellas. Natural skin texture and real fabric when people are visible. Captured on a cinema camera with a real spherical lens, fine 35mm-like grain, restrained halation only on actual light sources, high dynamic range with readable shadow detail. All signage is abstract glowing color bars, simple geometric shapes, or a plain white eye-shaped emblem, never readable letters or Chinese characters.
```

**[N] 负面段（所有关键帧）**

```
No captions, interface, reticle, crosshair, legible text or characters, watermark, real-world brands or logos, poster treatment, black bars, painterly, anime, CGI or video-game-render finish. No blood, no gore, no severed human limbs. No weapon or hands of the viewer in frame.
```

**[F] 出图格式（场面和剧情首帧）**

```
Use case: cinematic-scene. Asset: keyframe for an interactive live-action full-motion video game. Output one single full-bleed 16:9 landscape frame, image only, no borders or letterboxing.
```

**[E] 编辑格式（在已有图上加入人物或敌人）**

```
Use case: compositing. Asset: gameplay-video anchoring frame. The first input image is the edit target and continuity reference. Preserve it as a matched adjacent film keyframe: exactly the same 16:9 camera, framing, angle, focal length, architecture, props, rain, lighting and reflections. Only add or change what is described below.
```

**[C] 设定图格式**

```
Use case: character-reference sheet for a live-action film. Output one 16:9 image on a plain dark grey studio backdrop with soft even key light and a subtle teal rim light. Show the same subject four times side by side at the same scale: front full body, three-quarter full body, back full body, and a large close-up of the face or head. Identical design in every view. Photoreal film costume or practical prop photography, no text labels, no arrows, no color swatches.
```

## 2. 角色设定图

### CH_LUCHEN 陆沉

```
[C]
Subject: Lu Chen, a 24-year-old Chinese man, lean and athletic, 1.80 m. Short black hair, slightly damp. Sharp, tired dark eyes, straight brows, a thin pale old scar along the left side of his jaw, light stubble, natural skin texture. He wears a long black waterproof coat with a high collar, falling to mid-calf, worn and rain-beaded; under it a dark charcoal cross-collar short jacket in the style of traditional Chinese martial-arts clothing, a black cloth belt, black tapered trousers and worn black boots. His left arm, fully visible because the left coat sleeve is cut off at the shoulder, is an old brass-colored mechanical prosthetic: exposed pistons, hand-wound gears, scratched brass plates, leather straps at the shoulder, no screens and no lights. On his right wrist, a plain dark metal band with one tiny teal light. Across his back on a leather strap, worn diagonally: an old dented gunmetal sword case, a long flat box like a rifle case, with eight narrow slots along the top edge; eight thin fiber-optic tassels hang from its lower end and glow soft teal (#4DFFD2). In the close-up he looks slightly past camera, calm and guarded.
[N]
```

### CH_QINGPING 青萍

```
[C]
Subject: Qingping, an AI sword spirit who exists only as a hologram. She looks like a young Chinese woman of about 18, slender, a high ponytail tied with a long ribbon, bright lively eyes, an expressive face with a hint of mischief. She wears a traditional narrow-sleeved martial-arts robe with a crossed collar, wrapped belt and wide trousers. Her whole figure is a semi-transparent teal hologram (#4DFFD2 to pale cyan): the backdrop is clearly visible through her body at about 40 percent opacity, fine horizontal scanlines, thin flowing light lines tracing the seams of her clothes, a slight flicker at her outline, her feet fading out a few centimeters above the floor. She emits light and casts a faint teal glow on the floor below her; she has no shadow. Not a solid person, not glossy plastic, not a ghost.
[N]
```

### CH_YUNYI 云姨

```
[C]
Subject: Aunt Yun, a Chinese woman in her early fifties who runs a small noodle shop. Sturdy build, short permed hair with grey streaks, round face, quick sharp eyes, laugh lines, natural skin. A faded dark red work blouse with sleeves pushed up, a stained cream apron, dark trousers, rubber kitchen boots. Her right forearm and hand are an older silver prosthetic, dull brushed metal with simple joints and a few dents, a thin blue status light on the wrist. In the close-up she is mid-scold, eyebrows raised, but warm.
[N]
```

## 3. 敌人设定图

敌人设定图用 [C] 格式，四个视图改为：正面、侧面、蓄力或攻击姿势、被击毁后的样子。

### EN_GUARD 铁衣卫

```
[C]
Views: front standing, side standing, attack pose, destroyed state.
Subject: a Tie Yi Wei repossession android, a remote-controlled humanoid machine 1.85 m tall, slender and upright. Its body is made of glossy off-white porcelain-like ceramic shell plates with a fine crackle glaze, segmented like armor over a black mechanical frame; bundles of black cables are exposed at the neck, elbows, waist and knees. The head is a smooth, faceless mask inspired by Peking opera face painting: a white base with bold red brushstroke lines sweeping over the brows and down the cheeks, a narrow horizontal eye slit glowing red-orange, no mouth, no hair. It holds an electric hook staff: a long black pole ending in a curved steel hook, with blue-white electric arcs crackling between two prongs. Attack pose: hook raised behind the head, arcs flaring, body coiled to lunge. Destroyed state: faceplate cracked across, a few white ceramic shards missing, eye slit dark, kneeling and slumped forward, hook on the ground. Clearly a machine, not a person in costume.
[N]
```

### EN_DRONE 蜂鸟

```
[C]
Views: front, side, diving attack, destroyed.
Subject: a Fengniao surveillance drone, compact, about 45 cm wide. A smooth teardrop body in black lacquer with fine gold hairline trim like Chinese lacquerware, four small ducted rotors at the corners, a single large round red camera lens at the front that glows bright when it locks on, a short stun-dart nozzle under the lens. Diving attack: nose down, lens blazing red, rotors tilted. Destroyed: cracked shell, bent rotor ducts, smoking, lens dark.
[N]
```

### EN_BEAST 狻猊

```
[C]
Views: front, side, crouched before pouncing, destroyed.
Subject: a Suanni guard beast, a quadruped robot the size of a large dog, inspired by Chinese stone guardian lions. Black lacquer armor plates with gold line inlay, a stylized lion-dog head with a curled mane made of overlapping metal plates, two glowing amber eyes, an open jaw with blunt metal teeth, powerful hydraulic legs with visible pistons. Crouched pose: chest low, hind legs tensed, eyes flaring. Destroyed: collapsed on its side, joints smoking, eyes dark.
[N]
```

### EN_CLOAK 隐

```
[C]
Views: cloaked silhouette, revealed front, revealed side lunging with a short blade, destroyed.
Subject: a Yin assassin android, thin and tall, 1.9 m. Cloaked: almost fully invisible, only the raindrops hitting its body reveal a faint glassy human-shaped silhouette with slight refraction. Revealed: matte dark graphite body with a fine hexagonal texture, a smooth egg-shaped featureless head with one thin vertical white light slit, long arms, a short straight blade extending from the right forearm. Destroyed: camouflage glitching in grey patches, fallen.
[N]
```

### EN_LAUNCHER 梨花匣

```
[C]
Views: front, side, back case fully opened and firing, destroyed.
Subject: a Lihua Xia launcher android made by Tang Heavy Industries, squat and heavy, 1.6 m, black lacquer armor with gold filigree. On its back it carries a large rectangular case. When opened, the case unfolds like a fan into rows of short hexagonal launch tubes, with a round glowing gold core at the center of the fan. Firing view: a tight cluster of three small micro-missiles with gold exhaust flames leaving the tubes. Destroyed: the case blown open, core dark, smoking.
[N]
```

### EN_SPIDER 千机蛛

```
[C]
Views: front, side, abdomen opened, head plates opened revealing the core.
Subject: the Qianji Zhu siege machine, a six-legged spider-like machine about 6 m wide and 3 m tall. Heavy black lacquer armor plates with gold filigree patterns like antique Chinese lacquerware. Each leg has a large ring-shaped joint that can glow gold. The abdomen has armored panels that open to reveal rows of micro-missile tubes. The armored head has plates that split apart to expose a round gold core the size of a person's head. Water streams off its body. Menacing but clearly mechanical, no organic parts.
[N]
```

## 4. 场面母版

场面母版里没有人和敌人。先做 PL_ALLEY，其余下城场面上传它作风格参考，并在提示词前加一句 "Match the color, rain, materials and lighting of the reference image."

### PL_ALLEY 九曲巷（S2 战斗）

```
[F]
[S]
Scene: Jiuqu Lane in the undercity, seen from the doorway of a small noodle shop at standing eye height, looking straight down the lane with a 28mm lens. A locked-off gameplay frame with clear layered depth. Left: two-story dark timber arcade houses; on the upper floor at about 22 percent width and 30 percent height, a wooden lattice window, closed, dimly lit from inside. Left midground at about 35 percent width and 58 percent height: a small street stall under a striped rain canopy with a waist-high stack of blue plastic crates in front of it. Right foreground and midground: the square stone pillars of an arcade, the nearest at about 78 percent width. Far down the lane at center, about 52 percent width and 40 percent height: a small humpbacked granite arch bridge over a canal. Overhead across the top of the frame: the underside of a huge rusted steel viaduct with pipes and cables; at the upper right near 72 percent width its lower edge is clearly visible; rain pours through gaps in it as thin waterfalls. Every neon sign in the lane shows the same plain white eye-shaped emblem. The wet stone ground fills the lower center and reflects the signs. Nobody is in the street; an abandoned umbrella lies on the ground. Tense, empty, rain-soaked.
[N]
```

### PL_ALLEY_WIDE 九曲巷远景（c1_03）

```
[F]
[S]
Scene: establishing wide shot of Jiuqu Lane at the bottom of the megacity, eye height, 24mm lens. Old two-story timber arcade houses and stilt houses line a narrow canal street; a granite arch bridge crosses in the middle distance. Far overhead, layer upon layer of steel viaducts, pipes and the lit bellies of towers block the sky; rain falls through the gaps as long glittering streams. Neon light bars in magenta and teal, a few hanging lanterns, steam from food stalls. A dozen ordinary residents in raincoats walk with oiled-paper and clear umbrellas, a delivery rider in a yellow raincoat on an e-bike, an old man under an awning. On the right, the warm yellow light of a small noodle shop spills onto the wet street. Lively, poor, warm, crowded.
[N]
```

### PL_NOODLE 面馆内景（c1_04）

```
[F]
[S]
Scene: inside a tiny old noodle shop, side view along a worn wooden counter with four stools, 35mm lens at seated eye height. Warm tungsten bulbs, steam rising from a big pot behind the counter, chipped tiles, a small old radio, condiment jars without labels. Through the open front on the right, the rainy neon lane is visible, softly out of focus. Nobody in the shop.
[N]
```

### PL_DOOR 面馆门口（c1_10 一剑）

```
[F]
[S]
Scene: the front doorway of the same noodle shop seen from the side at eye height, medium-wide, 35mm lens. A wooden door frame with an old cloth curtain pushed aside, the warm interior on the left, the rainy lane on the right. A heavy iron ladle hangs on a hook beside the door frame. Wet stone step. Nobody in frame.
[N]
```

### PL_CANAL 水道拱桥（S5 战斗）

```
[F]
[S]
Scene: a locked-off gameplay frame from a stone walkway on one bank of a narrow canal, standing eye height, 28mm lens, looking across the dark water. Center at about 50 percent width and 38 percent height: a granite humpbacked arch bridge spanning the canal, its top clearly silhouetted. Left bank: a two-story timber stilt house with a wooden balcony at about 18 percent width and 45 percent height and a tiled roof whose ridge is at about 30 percent width and 14 percent height. Right bank: a large rectangular hanging neon light box glowing teal, about 74 percent width and 28 percent height, suspended from a single visible iron bracket arm bolted to a wall; directly below it, about 74 percent width and 64 percent height, a stack of old wooden crates. Far right at about 88 percent width: a massive concrete viaduct pier. The lower part of the frame is the canal surface with rain rings and long neon reflections. The underside of a steel viaduct crosses the top. Nobody in frame.
[N]
```

### PL_JUNCTION 水道交汇处（S6 Boss）

```
[F]
[S]
Scene: a wide canal junction where several waterways meet, a broad open stretch of dark water in the center surrounded by wet granite embankments, low steps down to the water, and enormous concrete viaduct piers rising out of frame on both sides. The camera is on the near embankment slightly below eye height, 24mm lens, locked-off, with plenty of empty water in the center and lower half of the frame for a very large machine to emerge. Neon light bars on distant walls stretch long reflections across the water. Rain hits the surface everywhere. Nobody in frame.
[N]
```

### PL_SKY 云顶（c1_01）

```
[F]
[S]
Scene: above the clouds at night. A sea of silver clouds under a huge full moon. A single colossal glass tower pierces the cloud layer at the center of the frame, its top a pale jade-and-gold structure; near its peak, a large plain eye-shaped emblem glows soft gold. Clear cold air, no rain at this height, stars faint. Calm, distant, beautiful.
[N]
```

### PL_STATION 磁浮站（c1_21、c1_22）

```
[F]
[S]
Scene: a maglev station platform built onto a viaduct high above the canal street, wet steel stairs climbing up to it from the right. A sleek white maglev train with a long continuous band of cool light along its side waits at the platform with doors open. Rain blows across the platform, cool white light, the neon undercity glows far below past the railing. Nobody in frame.
[N]
```

## 5. 剧情首帧和状态锚帧

每条先写上传的参考图，按顺序上传。

### 5.1 S1 开场

**KF_C1_01**　参考：PL_SKY

```
[E]
Keep the reference unchanged; this is the first frame of a slow downward tilt. Only make the gold eye emblem near the top of the tower slightly brighter, as if it has just switched on.
[N]
```

**KF_C1_02**　参考：PL_ALLEY_WIDE（风格）

```
[F]
[S]
Scene: a plunging aerial view just below the cloud base, looking steeply down into the megacity. Sheets of rain rush toward the camera. Two maglev tracks with continuous bands of white light cross diagonally close to the lens, slightly motion-blurred. Far below, a dense maze of neon-lit rooftops, viaducts and canals glows magenta and teal. Vertigo, speed, rain.
[N]
```

**KF_C1_03**　参考：PL_ALLEY_WIDE。直接使用 PL_ALLEY_WIDE，不另出图。

**KF_C1_04**　参考：PL_NOODLE、CH_LUCHEN、CH_QINGPING、CH_YUNYI

```
[E]
Add three characters, matching the character sheets exactly. Lu Chen (image 2) sits on the second stool in profile facing right, bent over a steaming bowl of noodles, chopsticks in his right hand, his brass prosthetic left arm resting on the counter; his long black coat hangs off the stool, and his gunmetal sword case leans against the stool with its eight teal tassels glowing. Qingping (image 3) sits on the counter beside his bowl as a semi-transparent teal hologram, chin in her hands, gazing at the noodles with exaggerated longing; the warm interior is visible through her body. Aunt Yun (image 4) stands behind the counter, ladling broth with her silver prosthetic hand, steam rising. Medium shot, natural warm light, faces clearly visible but not close-ups.
[N]
```

**KF_C1_05**　参考：PL_ALLEY

```
[E]
Change the view slightly to look out through the noodle shop's open front at the lane: the shop's cloth curtain hangs in the left and top edge of frame, out of focus. In the lane, several residents with umbrellas have stopped and look up at the neon signs, which are flickering; half the signs still show varied abstract color bars and half have already turned into the same plain white eye-shaped emblem. A thin electric shimmer runs along the signs.
[N]
```

**KF_C1_06**　参考：PL_ALLEY、EN_GUARD

```
[E]
Low camera, looking up the lane from just above the wet ground. Five Tie Yi Wei androids (image 2, identical design) have just landed from the viaduct above: each is down on one knee in a puddle, one hand on the ground, water splashing outward, hook staffs in their other hands. Their red-orange eye slits are glowing. In the background, blurred residents run away with umbrellas.
[N]
```

### 5.2 S3 一剑

**KF_C1_10**　参考：PL_DOOR、EN_GUARD、CH_YUNYI

```
[E]
At the doorway, a Tie Yi Wei android (image 2) stands on the wet step on the right, gripping Aunt Yun's silver prosthetic right forearm with a heavy mechanical repossession clamp mounted on its left forearm; the clamp's central joint glows blue and is clearly visible between them at about 55 percent width and 45 percent height, separated from her hand by a short gap. Aunt Yun (image 3) is on the left, leaning back with her left hand gripping the door frame, furious and straining. Their bodies do not overlap the clamp joint. Medium shot, side-on.
[N]
```

**KF_C1_11_END**　参考：KF_C1_10

```
[E]
Same frame after the rescue: the Tie Yi Wei kneels slumped on the step on the right, faceplate cracked, eye slit dark, the clamp broken open and hanging. Aunt Yun stands free on the left, rubbing her silver prosthetic forearm with her other hand. The iron ladle is back on its hook.
[N]
```

**KF_C1_12**　参考：KF_C1_11_END、CH_YUNYI

```
[E]
Change to a close shot of Aunt Yun from chest up, slightly to the left of center, looking toward camera with a stern face and the corner of her mouth just starting to smile, rubbing her prosthetic wrist. The slumped android is a soft blur in the background right. Warm light from the shop on her face, rain behind.
[N]
```

### 5.3 S4、S7 剧情

**KF_C1_13**　参考：PL_DOOR、CH_LUCHEN

```
[E]
Lu Chen (image 2) stands under the noodle shop's eave in right profile, medium close shot from the chest up, rain falling just beyond the eave edge behind him. His right hand is raised to press a small earpiece behind his ear; he listens intently, eyes down. Rain water drips from his collar. His sword case strap crosses his chest; two glowing teal tassels are visible at his shoulder.
[N]
```

**KF_C1_14**　参考：KF_C1_13、CH_QINGPING

```
[E]
Widen to a medium shot. Qingping (image 2), a semi-transparent teal hologram, has risen from the sword case and floats beside Lu Chen's right shoulder, facing him, serious for the first time, her ponytail drifting. Rain passes straight through her. Lu Chen turns his head slightly toward her.
[N]
```

**KF_C1_15**　参考：KF_C1_13、CH_LUCHEN

```
[E]
Change to a low angle over Lu Chen's right shoulder looking straight up. Through gaps between the rusted viaducts, pipes and cables far above, high in the clouds, a faint gold glow is visible. Rain falls toward the camera. Lu Chen's shoulder, the sword case and its teal tassels fill the lower left foreground.
[N]
```

**KF_C1_20**　参考：K_SPIDER_END

```
[E]
Same camera. Add a maglev train with a continuous band of white light passing along a viaduct high in the upper part of the frame. Heavy steam rises from the wrecked machine.
[N]
```

**KF_C1_21**　参考：PL_STATION、CH_LUCHEN

```
[E]
Change to a tracking shot from behind and slightly below: Lu Chen (image 2) runs up the wet steel stairs toward the platform, seen from the back, long black coat flying, the sword case with eight glowing teal tassels on his back. The train waits at the top with its doors open.
[N]
```

**KF_C1_22**　参考：PL_STATION、CH_LUCHEN

```
[E]
Side-on wide shot of the platform. The train doors are closing; Lu Chen (image 2) slips sideways through the narrowing gap of the middle door, his coat tail and two teal tassels still outside. Rain slants across the platform.
[N]
```

### 5.4 状态锚帧

**K_LAUNCHER**　参考：PL_CANAL、EN_LAUNCHER

```
[E]
Add one Lihua Xia launcher android (image 2) crouched on the ridge of the stilt house roof at about 30 percent width and 14 percent height, facing camera. Its back case is fully opened into a fan of hexagonal launch tubes, the round gold core glowing at the center. It fits the roof scale: the machine is about 1.6 m tall. Its silhouette is crisp against the dark viaduct behind.
[N]
```

**K_SPIDER_1**　参考：PL_JUNCTION、EN_SPIDER

```
[E]
Add the Qianji Zhu siege machine (image 2) standing in the center of the junction, facing camera, about 60 percent of frame width. Its six legs straddle the water: two on the left embankment, two on the right embankment, two in the water. Water streams off its black-and-gold lacquer armor. All six ring-shaped leg joints are dark. The four front and middle joints are clearly visible and separated from each other. Head plates closed, abdomen panels closed.
[N]
```

**K_SPIDER_2**　参考：K_SPIDER_1

```
[E]
Same machine, same position. The front-left and front-right legs are broken at the joint and drag in the water, sparking. Its body is lowered. The abdomen armor panels have opened, revealing rows of micro-missile tubes glowing gold inside.
[N]
```

**K_SPIDER_3**　参考：K_SPIDER_2

```
[E]
Same machine, now crouched with its body almost touching the water, the head lowered toward camera. The head armor plates have split apart, exposing a large round glowing gold core at about 50 percent width and 52 percent height. Abdomen panels are closed again.
[N]
```

**K_SPIDER_END**　参考：K_SPIDER_3

```
[E]
Same camera. The machine has collapsed into the water, legs folded under it, armor cracked, the gold core shattered and dark, every light out, thick steam rising from it into the rain.
[N]
```

## 6. H3 视频：剧情

### 6.1 公共前缀

**[P_FILM] 剧情镜头前缀**

```
One continuous photoreal live action near-future Chinese cyberpunk wuxia film shot. Preserve all reference faces, costumes, props, scale and camera framing. Steady rain throughout. Subtle, real movements. Natural ambience of rain and city, no music, no speech unless described, no captions, writing or UI.
```

**[P_PLATE] 场面底片前缀**

```
One continuous photoreal live action shot from a completely locked-off static camera; the camera never moves, zooms or shakes. Preserve the exact location, lighting and every element of the first picture. Steady medium rain at constant intensity. No people, no animals, no machines appear. Only rain, water, steam and flickering lights move. Natural ambience of rain, no music, captions, writing or UI.
```

### 6.2 S1、S3、S4、S7

格式：视频 ID　首帧 → 尾帧 · 长度。没有写尾帧的不锚尾帧。

**c1_01_moon**　KF_C1_01 · 119

```
[P_FILM] Very slow downward tilt from the full moon over the cloud sea, past the glass tower whose gold eye emblem brightens, into the top of the clouds. Clouds drift slowly. High-altitude wind.
```

**c1_02_descent**　KF_C1_02 · 119

```
[P_FILM] The camera plunges steadily downward through the rain toward the city. Two maglev light bands streak past on both sides of the lens. Neon roofs grow larger below. Rushing rain and wind, a train roars past.
```

**c1_03_alley**　PL_ALLEY_WIDE · 119

```
[P_FILM] Locked-off camera. Residents walk through the lane with umbrellas, the delivery rider rides slowly past, steam drifts from the stalls, rain streams through gaps in the viaduct overhead. The noodle shop's warm light flickers once.
```

**c1_04_noodle**　KF_C1_04 · 119

```
[P_FILM] Locked-off camera. Lu Chen eats noodles without looking up, lifting the noodles with his chopsticks. The hologram girl on the counter leans closer to the bowl, then turns her head and speaks to him with a teasing smile; her outline flickers slightly. Behind the counter, the noodle shop owner pours broth with her silver prosthetic hand. Steam rises.
```

**c1_05_takeover**　KF_C1_05 · 119

```
[P_FILM] Locked-off camera looking out of the shop. One by one, the remaining neon signs in the lane flicker and switch to the same plain white eye-shaped emblem until every sign shows it. The residents with umbrellas stop and look up, uneasy. An electric hum rises.
```

**c1_06_drop**　KF_C1_06 · 119

```
[P_FILM] Locked-off low camera. The five kneeling white porcelain androids rise to their feet in unison, raising their hook staffs; blue-white arcs crackle at the hooks. Their red eye slits brighten. Water drips from their shells. Residents scatter in the background.
```

**c1_10_claw**　KF_C1_10 · 119

```
[P_FILM] Locked-off camera, side-on. The android pulls steadily with its clamp; the glowing blue clamp joint grinds and sparks faintly as it tries to detach the woman's silver prosthetic arm. The woman braces against the door frame, shouting at it. The clamp joint stays clearly visible between them for the whole shot. Mechanical grinding, rain.
```

**c1_11_hit**　c1_10_claw 的命中帧 → KF_C1_11_END · 73

```
[P_FILM] Immediately a bright teal streak strikes the glowing clamp joint: sparks burst and the clamp snaps open. The woman yanks her arm free and steps back. A moment later a second teal streak hits the android's faceplate; it cracks, the red eye slit goes dark and the android drops to its knees and slumps.
```

**c1_11_miss**　c1_10_claw 的命中帧 → KF_C1_11_END · 73

```
[P_FILM] A teal streak glances off the android's shoulder plate with a spray of sparks. The woman grabs the heavy iron ladle from its hook and smashes it down on the clamp with her silver arm; the clamp pops open and she pulls free, hanging the ladle back. A second teal streak hits the android's faceplate; it cracks, its eye goes dark, and it drops to its knees and slumps.
```

**c1_12_thanks**　KF_C1_12 · 73

```
[P_FILM] Locked-off close shot. The woman rubs her prosthetic wrist, glares toward camera, then the corner of her mouth lifts into a reluctant smile as she says one short line.
```

**c1_13_radio**　KF_C1_13 · 119

```
[P_FILM] Locked-off medium close shot. The young man presses his earpiece and listens; his jaw tightens, his eyes lift slowly from the ground to the street ahead. Rain drips from the eave behind him.
```

**c1_14_core**　KF_C1_14 · 119

```
[P_FILM] Locked-off medium shot. The teal hologram girl floats beside his shoulder and speaks to him seriously; rain falls through her body, scanlines drift across her. He turns his head to look at her and gives a slight nod.
```

**c1_15_lookup**　KF_C1_15 · 119

```
[P_FILM] Low angle over his shoulder. He tilts his head back and looks up at the faint gold glow far above, then shrugs the sword case higher onto his back; the teal tassels swing. Rain falls toward the camera.
```

**c1_20_steam**　KF_C1_20 · 119

```
[P_FILM] Very slow push in. The collapsed machine steams in the water; the last faint gold light in one leg joint flickers out. High above, the lit maglev train glides along the viaduct and slows toward a station.
```

**c1_21_stairs**　KF_C1_21 · 119

```
[P_FILM] The camera follows from behind as he runs up the wet steel stairs two at a time, coat flying, water splashing from each step, toward the waiting train at the top.
```

**c1_22_board**　KF_C1_22 · 119

```
[P_FILM] He slips through the closing door; the doors seal. The train accelerates smoothly along the viaduct and climbs into the rain, its light band streaking away. Hold on the empty platform and the rain.
```

### 6.3 场面底片

**c1_alley_plate**　PL_ALLEY → PL_ALLEY · 175

```
[P_PLATE] Rain falls steadily on the empty lane; thin waterfalls pour through gaps in the viaduct; puddles ripple; the white eye emblems on the signs pulse faintly; a little steam drifts from the stall canopy.
```

**c1_canal_plate**　PL_CANAL → PL_CANAL · 175

```
[P_PLATE] Rain rings spread across the canal; the teal light box sways very slightly on its bracket and its reflection wobbles in the water; drops fall from the viaduct overhead.
```

## 7. H3 视频：战斗

### 7.1 公共前缀

**[P_WAVE] 波次前缀**（首尾帧都是场面母版，99 帧）

```
One continuous photoreal live action shot from a completely locked-off static camera; the camera never moves, zooms or shakes. Preserve the exact location, lighting and every background element of the first picture. Steady medium rain at constant intensity. Only the one machine described below moves; no people appear. Timing: the machine appears from behind its cover within the first half second, is fully visible right after, holds its threat pose for about a second, then charges up for about a second, attacks toward the camera, and retreats behind the same cover so the last picture is the empty location again. Real mechanical motion, physical light from its glowing parts on the wet surroundings. Natural ambience of rain and machinery, no music, captions, writing or UI.
```

**[P_KILL] 击毁前缀**（首帧是波次成片的第 28、42 或 56 帧，尾帧是场面母版，47 帧）

```
One continuous photoreal live action shot from a completely locked-off static camera; the camera never moves. Preserve the exact location and lighting of the first picture. Steady medium rain. The machine visible in the first picture reacts on the very first frames, with no pause. Its destruction is fast and complete within the first second; by the last picture the location is empty and unchanged, with no wreck, debris or smoke left in view. Real sparks and physical light. No people, no blood. Natural ambience of rain, no music, captions, writing or UI.
```

### 7.2 S2 波次

**c1_w_drone_win**

```
[P_WAVE] The upper-floor wooden window on the left bursts open and a small black-and-gold lacquered surveillance drone with four ducted rotors flies out and hovers just outside it, about the size of a large bird in frame. Its single round red lens brightens to a glare. It tilts nose-down and dives straight at the camera, pulls up sharply just before reaching it, and flies back in through the window, which swings shut.
```

**c1_w_drone_via**

```
[P_WAVE] From under the lower edge of the steel viaduct at the upper right, a small black-and-gold lacquered surveillance drone flips out and hovers, rain bouncing off its shell. Its red lens brightens to a glare, it dives at the camera, pulls up and darts back under the viaduct.
```

**c1_w_guard_stall**

```
[P_WAVE] Behind the stack of blue crates at the left-center stall, a white porcelain android with a red-lined opera faceplate rises to its full height, its red eye slit glowing. It lifts its hook staff behind its head; blue-white arcs crackle and grow brighter at the hook. It lunges forward and thrusts the crackling hook toward the camera, then steps back and crouches down behind the crates.
```

**c1_w_guard_pillar**

```
[P_WAVE] From behind the nearest square arcade pillar on the right, a white porcelain android with a red-lined opera faceplate steps sideways into view, red eye slit glowing. It raises its electric hook staff, arcs intensifying, then thrusts the hook toward the camera and slides back behind the pillar.
```

**c1_w_guard_bridge**

```
[P_WAVE] A white porcelain android with a red-lined opera faceplate climbs up onto the top of the small arch bridge far down the lane and stands there, small in the distance but clearly silhouetted, red eye slit glowing. It whirls its hook staff and flings a bright blue-white electric arc down the lane toward the camera, then drops down behind the far side of the bridge.
```

**c1_w_rider**

```
One continuous photoreal live action shot from a completely locked-off static camera; the camera never moves, zooms or shakes. Preserve the exact location, lighting and every background element of the first picture. Steady medium rain at constant intensity. No machines appear. Natural ambience of rain, no music, captions, writing or UI. The last picture is the empty location again. A frightened delivery rider in a bright yellow raincoat with a square delivery box on his back rides an e-bike fast through the middle of the lane from the left edge to the right edge, glancing back over his shoulder, spray flying from the tires. He is clearly an ordinary person and is never threatening. He leaves the frame on the right; the lane is empty again.
```

### 7.3 S2 击毁（每条波次在第 28、42、56 帧各一条）

**c1_w_drone_*_kill_28 / 42 / 56**

```
[P_KILL] The black lacquered drone bursts into a shower of bright white-orange sparks and small dark fragments, spins out of control and drops straight down out of view below the window line or behind the stall, with a short splash and a puff of smoke that the rain quickly clears.
```

**c1_w_guard_stall_kill_28 / 42 / 56**

```
[P_KILL] The white porcelain android is hit at once: its red-lined faceplate cracks and a few white ceramic shards break away, its red eye slit flickers out, the electric hook drops, and it buckles at the knees and collapses backward behind the blue crates, completely out of sight.
```

**c1_w_guard_pillar_kill_28 / 42 / 56**

```
[P_KILL] The white porcelain android is hit at once: its faceplate cracks with white shards flying, its eye goes dark, and it staggers and falls back behind the square pillar, completely out of sight.
```

**c1_w_guard_bridge_kill_28 / 42 / 56**

```
[P_KILL] The distant white porcelain android on top of the bridge is hit at once: a small burst of sparks and white shards at its faceplate, its eye goes dark, and it topples backward off the far side of the bridge with a splash into the canal.
```

### 7.4 S5 波次

**c1_w_cloak_bridge**

```
[P_WAVE] On top of the stone arch bridge, the rain begins to outline a tall, thin human-shaped silhouette that is otherwise invisible, a faint glassy refraction where the drops hit it. A small teal streak of light flies in from the lower right of the frame and sweeps across the silhouette; its optical camouflage flickers and fails, revealing a matte dark graphite android with a smooth egg-shaped head and one thin vertical white light slit. It extends a short blade from its right forearm and lunges forward toward the camera, then flickers invisible again and drops behind the far side of the bridge.
```

**c1_w_cloak_house**

```
[P_WAVE] On the wooden balcony of the stilt house on the left, the rain outlines a tall invisible human-shaped silhouette. A small teal streak of light flies in from the lower right and sweeps across it; the camouflage flickers and fails, revealing the matte dark graphite android with a vertical white light slit. It extends a forearm blade and leaps forward toward the camera, then flickers invisible and retreats into the balcony shadows.
```

**c1_w_drone_water**

```
[P_WAVE] A small black-and-gold lacquered drone bursts up out of the dark canal water in a spray of droplets and hovers above the surface. Its red lens brightens to a glare, it dives at the camera, pulls up and plunges back into the canal with a splash; ripples settle.
```

**c1_w_sign**

```
[P_WAVE] Two black-and-gold lacquered robot guard beasts shaped like Chinese guardian lions are crouched side by side directly beneath the hanging teal light box, in front of the wooden crates. Their amber eyes light up; they slowly rise, lower their chests and pounce together toward the camera, then leap back behind the crates. Above them, the light box hangs from its single iron bracket arm the whole time, swaying slightly, its bracket always clearly visible.
```

**c1_w_beast_crates**

```
[P_WAVE] One black-and-gold lacquered robot guard beast shaped like a Chinese guardian lion leaps out from behind the wooden crates under the light box, lands crouched on the stones with its amber eyes flaring, coils and pounces toward the camera, then springs back behind the crates.
```

**c1_w_guard_pillar2**

```
[P_WAVE] From behind the massive concrete viaduct pier on the right, a white porcelain android with a red-lined opera faceplate steps into view, red eye slit glowing. It raises its electric hook staff, arcs intensifying, thrusts the hook toward the camera and slides back behind the pier.
```

### 7.5 S5 击毁和借势

**c1_w_cloak_*_kill_28 / 42 / 56**

```
[P_KILL] The dark graphite android is hit at once: sparks burst from its chest, its optical camouflage glitches into flickering grey patches across its body, its white light slit goes dark, and it falls backward behind the bridge or into the balcony shadows, completely out of sight.
```

**c1_w_drone_water_kill_28 / 42 / 56**

```
[P_KILL] The lacquered drone bursts into a shower of white-orange sparks, spins and drops into the canal with a splash; the ripples settle and the water is empty.
```

**c1_w_beast_crates_kill_28 / 42 / 56**

```
[P_KILL] The robot guard beast is hit at once: sparks spit from its neck joint, its amber eyes go dark, its legs give way and it slumps and slides down behind the crates, out of sight, with a little smoke that the rain clears.
```

**c1_w_guard_pillar2_kill_28 / 42 / 56**

```
[P_KILL] The white porcelain android is hit at once: its faceplate cracks with white shards flying, its eye goes dark, and it staggers and falls back behind the concrete pier, completely out of sight.
```

**c1_sign_drop_28 / 42**

```
[P_KILL] The iron bracket arm holding the teal light box snaps with a burst of sparks; the heavy light box drops straight down and crashes onto both robot beasts below, crackling with electric light. A flash, their amber eyes go out, and the light box and both beasts tumble down behind the crates into darkness. The bracket stub remains on the wall; the light box is gone from view. Unlike other destruction shots, the last picture is the location without the light box.
```

借势是 S5 的链尾（见分镜 §5.2）。c1_sign_drop 的尾帧用去掉灯箱的 PL_CANAL_X，之后硬切到 S6，其他波次都不需要无灯箱的版本。

**PL_CANAL_X**　参考：PL_CANAL

```
[E]
Remove the hanging teal light box completely and its reflection in the water; only a short broken iron bracket stub remains on the wall. Everything else stays exactly the same.
[N]
```

### 7.6 梨花匣

**c1_w_launcher_roof**　PL_CANAL → K_LAUNCHER · 99

```
[P_WAVE] Override the timing above: a squat black-and-gold lacquered android with a large rectangular case on its back climbs up onto the ridge of the stilt house roof and crouches facing the camera. Its back case unfolds like a fan into rows of hexagonal launch tubes around a glowing gold core. A tight cluster of three small micro-missiles with gold exhaust flames launches from the tubes and flies straight toward the camera, growing larger, and bursts into an orange flash right in front of the lens. The android stays crouched on the roof with its case open in the last picture.
```

**c1_launcher_intercept_early / late**　飞弹飞行中的两个锚帧 → K_LAUNCHER · 47

```
[P_KILL] Override the ending above: the cluster of micro-missiles in mid-air explodes at once in a bright orange-gold burst with scattered sparks and a puff of smoke that the rain clears. The launcher android remains crouched on the roof with its case open in the last picture.
```

**c1_launcher_impact**　飞弹抵达帧 → K_LAUNCHER · 47

```
One continuous photoreal live action shot from a completely locked-off static camera. The micro-missiles burst into an orange fireball right in front of the lens; smoke rolls across the frame and clears in the rain, revealing the launcher android still crouched on the roof with its case open. No people, no music, captions, writing or UI.
```

**c1_launcher_threat**　K_LAUNCHER → K_LAUNCHER · 99

```
One continuous photoreal live action shot from a completely locked-off static camera. The crouched launcher android on the roof re-aims; the gold core at the center of its open case glows brighter for about two seconds, then launches another tight cluster of three micro-missiles that fly toward the camera and burst in an orange flash in front of the lens. It returns to the same crouched pose. Steady rain, no people, no music, captions, writing or UI.
```

**c1_launcher_flinch**　K_LAUNCHER → K_LAUNCHER · 47

```
[P_KILL] Override the ending above: the gold core at the center of the open case is hit at once, sparks spray out, and the android rocks back and nearly loses its footing, then steadies and crouches again in exactly the same pose, the core still glowing.
```

**c1_launcher_kill**　K_LAUNCHER → PL_CANAL · 47

```
[P_KILL] The gold core at the center of the open case is hit at once and bursts in a bright gold flash; the case blows apart with sparks and fragments, and the android topples backward off the roof ridge, disappearing behind the roof.
```

## 8. H3 视频：千机蛛

**[P_BOSS] Boss 前缀**

```
One continuous photoreal live action shot from a completely locked-off static camera; the camera never moves, zooms or shakes, even when the machine stomps. Preserve the exact location, lighting and the machine's design and position from the first picture. Steady medium rain. A huge six-legged black-and-gold lacquered spider-like siege machine; heavy, real mechanical weight, water pouring off it. No people. Natural ambience of rain, water, hydraulics and metal, no music, captions, writing or UI.
```

**c1_boss_enter**　PL_JUNCTION → K_SPIDER_1 · 119

```
[P_BOSS] The water at the center of the junction bulges and erupts in a tall column; the machine climbs out of the canal, planting its legs one by one on both embankments and in the water, and rises to face the camera. Its gold leg joints light up one after another and then dim. It ends standing still in the pose of the last picture.
```

**c1_boss_p1**　K_SPIDER_1 → K_SPIDER_1 · 119

```
[P_BOSS] The machine stands still. One at a time, four of its ring-shaped leg joints glow gold, each brightening steadily for about a second: front left, front right, middle left, middle right. As each glow reaches full brightness, that leg lifts and slams down into the water with a heavy shockwave of spray toward the camera, then the joint dims and the next begins. It ends in the same standing pose.
```

**c1_boss_p1_flinch_l / _r**　K_SPIDER_1 → K_SPIDER_1 · 47

```
[P_BOSS] Immediately, sparks burst from a glowing leg joint on the left side (or right side); that leg buckles and the whole body lurches and tilts toward it, then the leg straightens with a hiss of hydraulics and the machine returns to exactly the same standing pose.
```

**c1_boss_break**　K_SPIDER_1 → K_SPIDER_2 · 73

```
[P_BOSS] Both front legs snap at the joints in showers of sparks and collapse into the water; the body drops lower with a heavy splash. The armored abdomen panels grind open, revealing rows of micro-missile tubes glowing gold inside.
```

**c1_boss_p2_launch**　K_SPIDER_2 → K_SPIDER_2 · 99

```
[P_BOSS] Rows of tubes in the open abdomen glow brighter for about a second, then a tight cluster of micro-missiles with gold exhaust flames launches and flies straight toward the camera, growing larger, and bursts in an orange flash right in front of the lens. Smoke clears; the machine is in the same pose.
```

**c1_boss_p2_intercept_early / _mid / _late**　发射片的三个飞行锚帧 → K_SPIDER_2 · 47

```
[P_BOSS] The cluster of micro-missiles in mid-air explodes at once in a bright orange-gold burst with scattered sparks; the smoke drifts and clears in the rain, revealing the machine in the same pose with its abdomen still open.
```

**c1_boss_p2_impact**　发射片的抵达帧 → K_SPIDER_2 · 47

```
[P_BOSS] The missiles burst into a fireball right in front of the lens; smoke rolls across the frame and clears, revealing the machine in the same pose.
```

**c1_boss_expose**　K_SPIDER_2 → K_SPIDER_3 · 73

```
[P_BOSS] The abdomen panels slam shut. The machine sinks lower until its body almost touches the water, lowers its head toward the camera, and the armored head plates split apart, exposing a large round glowing gold core.
```

**c1_boss_p3**　K_SPIDER_3 → K_SPIDER_3 · 99

```
[P_BOSS] The exposed gold core pulses brighter and brighter for about two seconds as the machine gathers itself, then it lunges its whole body forward toward the camera, water exploding around it, stops just short, and pulls back to the same crouched pose with the core still exposed.
```

**c1_boss_p3_flinch**　K_SPIDER_3 → K_SPIDER_3 · 47

```
[P_BOSS] Immediately, sparks and gold light burst from the exposed core; the machine's head jerks back and its whole body shudders, then it settles back into the same crouched pose, the core flickering but still glowing.
```

**c1_boss_kill**　K_SPIDER_3 → K_SPIDER_END · 73

```
[P_BOSS] Immediately the gold core cracks and bursts in a brilliant gold flash; lines of light race out along the armor and die. Every joint goes dark, the legs fold, and the whole machine collapses into the water with a huge splash, then lies still, steaming heavily in the rain.
```

## 9. 配音的音色描述

用于 Qwen3-TTS VoiceDesign 设计音色，再用声音克隆固定。M0-C 与 VoxCPM2 对比后按角色选定。

| 角色 | 音色描述 |
|---|---|
| 陆沉 | 二十多岁的中国男性，低沉、略带沙哑，话少、语速偏慢，平静克制，偶尔冷幽默，普通话 |
| 青萍 | 十七八岁的少女，清亮、灵动、语速快，带一点俏皮和不服气，着急时声音拔高，普通话 |
| 云姨 | 五十岁左右的中国女性，嗓门大、爽快，带一点江南口音的普通话，嘴硬心软 |
| 老九 | 四十岁左右的男性，沙哑、碎嘴、语速很快，无线电里略带失真，普通话 |

老九的台词在混音时加无线电效果（带通 300–3400Hz，轻微失真和底噪）。青萍的台词加一层很轻的数字质感（短延迟、极轻的合唱），只在剧情里使用，战斗喊话保持干声以保证清晰。
