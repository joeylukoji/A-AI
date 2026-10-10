# Mobilier réaliste — éditeur 2D

Généré le 2026-09-25 avec l’outil imagegen intégré (pas de CLI ni d’appel Gemini).
Sprites originaux copiés sans retouche, PNG RGBA. Usage : décoration du Canvas ;
les dimensions du PlanDocument restent la source géométrique. Ne remplace pas
les dessins techniques cotés. Les petits équipements restent vectoriels.

Sept assets chargés à la demande et mis en cache. La voiture source pointe vers
le haut ; le chargeur applique −90° pour respecter le catalogue (avant à gauche).
La photographie générée comporte des marges transparentes ; l’encre peut occuper
légèrement moins que la boîte contractuelle. Aucun supplément de mobilier n’est créé.

Une première génération du lit simple et sa tentative de détourage ont été
écartées (halo de fond) ; seule la nouvelle génération ci-dessous est intégrée.

## Prompts finaux

### bed-double-v1.png

Use case: product-mockup. One architectural floor-plan sprite: luxurious contemporary DOUBLE BED exactly vertically overhead, orthographic camera, no perspective or visible vertical sides. Vertical bed footprint width 1.6m height 2.0m, headboard at TOP. Warm taupe upholstered slim headboard, two layered white linen pillows, soft ivory duvet with convincing natural folds, a burnt ochre cashmere blanket loosely folded across lower third. Refined neutral interior design catalogue photorealism, detailed fabric textures, soft diffuse upper-left light, restrained shadows entirely under object. Whole isolated bed fills 94 percent of image height, small margin, centered, true transparent alpha background. No floor, no room, no nightstands, no people, no writing, no outlines. Portrait composition. Must be true top-down flat plan, not isometric.

### bed-single-v1.png

A single narrow bed furniture cutout PNG with TRANSPARENT BACKGROUND. EXACT top-down overhead orthographic architectural plan view. One pillow at top, ivory sheets, rust orange throw across bottom. Taupe headboard. Realistic modern textiles. Bed is 90cm wide 200cm long. Isolated object only, transparent empty pixels around silhouette, no backdrop and absolutely NO cast shadow, NO glow or haze. Clean alpha cutout. Entire bed almost fills the portrait frame. No text.

### sofa-l-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan furniture sprite for a professional 2D editor. Create ONE photorealistic premium contemporary L-shaped sectional sofa viewed EXACTLY vertically from above, orthographic plan camera, no visible front elevation or perspective. Sofa footprint width 2.8m, depth 1.7m, horizontal long backrest at the TOP, chaise protruding toward the BOTTOM on the RIGHT. Soft warm ivory woven linen upholstery, three generous softly rounded seat cushions, realistic fine seams and tasteful natural folds, two warm terracotta and one olive small accent cushions resting on the seats near the back. Very refined interior-design catalogue realism, restrained high resolution material detail, softly lit from upper left. Isolated object centered, fill about 92 percent image width, preserve complete silhouette with small consistent margin. Background must be genuinely transparent alpha including empty area inside the L. No ground plane, no floor, no rug, no table, no text, no watermark, no people, no thick outlines. It must look like a real sofa photographed directly overhead, not an icon or cartoon. Output landscape.

### sofa-two-v1.png

Use case: product-mockup. A SINGLE isolated photorealistic modern TWO-SEAT sofa furniture sprite for an architectural plan, exactly vertical orthographic TOP DOWN view, no perspective. Width 1.8m depth 0.85m, horizontal long backrest at TOP. Ivory woven linen upholstery, two generously rounded seats with fine seams, low rounded armrests. One terracotta and one muted olive small accent cushion placed casually against the backrest. Premium designer catalogue realism, convincing fabric texture with subtle folds, soft upper-left diffuse lighting. Entire sofa centered with 3 percent transparent margin, landscape composition. Genuinely transparent alpha background, NO floor, NO rug, NO other furniture, NO text, NO logos, no thick outlines. Do not show front facade or legs.

### armchair-v1.png

Use case: product-mockup. ONE photorealistic premium contemporary armchair architectural floor-plan sprite viewed EXACTLY vertically from above, orthographic. Square footprint .8m by .8m, backrest along TOP edge. Sculptural generously rounded armchair upholstered in warm camel tan leather, softly creased broad seat, thick curved arms and back with subtle stitching, one small ivory lumbar cushion. Elegant modern furniture catalogue, real materials and gentle upper-left diffuse lighting. Entire object centered filling 94 percent of square composition, genuine transparent alpha background, no floor no rug no shadow beyond footprint no text no logos no other objects no perspective no visible front elevation no black outlines.

### car-v1.png

Use case: product-mockup. One photorealistic architectural plan sprite of a modern dark burgundy-red premium sedan viewed EXACTLY vertically from above with orthographic camera. Car points toward TOP, long axis vertical, footprint 1.8m wide by 4.4m long. Realistic glossy bodywork, dark smoked windshield and rear glass, metallic roof, wing mirrors, headlights. Refined overhead automotive studio realism, balanced soft lighting, subtle reflections not busy, no perspective or front elevation. Isolate whole car on genuinely transparent alpha background, no floor no road no parking marks no text no badge or logo no humans no outline. Fill 94 percent of image height with narrow margin. Portrait image.

### plant-v1.png

Use case: product-mockup. Architectural floor-plan sprite of ONE lush living indoor plant viewed EXACTLY vertically from above, orthographic camera. A compact mature bird-of-paradise/philodendron style plant with long broad beautiful emerald green leaves radiating outward with varied orientations and layered natural foliage, subtle leaf veins, vibrant but natural green, glimpses of a round terracotta pot underneath center. High-end photorealistic botanical overhead catalogue cutout. Square composition, centered complete canopy fills 90 percent width, genuinely transparent alpha background, no floor, no writing, no human, no perspective or visible pot side, no hard outline. Gentle upper-left diffused illumination, soft tiny self shadows.

## Extension cuisine, repas et sanitaires — 27 septembre 2026

Mode : outil imagegen intégré. Les neuf premières sorties simulaient la transparence
avec un damier et ont été rejetées avant intégration. Elles sont conservées sous
`benchmark/rejected-assets/technical-v1/`. Huit objets ont ensuite reçu une
extraction de fond avec `transparent_background: true`. Le WC a nécessité une
nouvelle génération complète après rejet d’une variante avec halo. Les tests
contrôlent RGBA, alpha 0–255 et coin entièrement transparent.

Prompt commun d’extraction appliqué aux huit objets :

> Use case: background-extraction. Edit only the background. Preserve the object,
> its exact overhead geometry, material, color, lighting, proportions and framing.
> Remove every grey-and-white checkerboard pixel and any backdrop outside the object,
> replacing all of it with genuine transparent alpha. Keep a clean anti-aliased
> cutout edge and only the object's restrained self-shadow. Do not redraw, rotate,
> crop, enlarge or add anything. No checkerboard in output.

### table-dining-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan furniture sprite.
Primary request: ONE premium contemporary rectangular dining table viewed EXACTLY vertically from above, orthographic plan camera. Footprint 1.80 m wide horizontally by 1.00 m deep vertically. Rounded rectangular slim solid light-oak tabletop, natural subtle grain, softly bevelled corners, no chairs, no place settings and no decorations. Refined modern interior-design catalogue realism, coherent with warm ivory upholstery and pale oak architecture plans.
Composition: centered, entire object fills about 92% of frame with a small even margin.
Lighting: restrained soft diffuse light from upper left, minimal self-shadow under the tabletop only.
Constraints: genuinely transparent alpha background; no floor, rug, wall, room, text, logo, watermark, people, thick outline, perspective, visible side elevation or extra objects. Landscape image.

### chair-dining-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan furniture sprite.
Primary request: ONE premium contemporary dining chair viewed EXACTLY vertically from above, orthographic plan camera. Footprint 0.45 m wide horizontally by 0.50 m deep vertically, chair faces toward the BOTTOM and its slim curved backrest runs along the TOP edge. Light-oak frame, warm ivory woven upholstered seat, refined rounded geometry and realistic material texture. No table and no other chair.
Composition: centered square image, complete object fills about 88% of frame with even transparent margin.
Lighting: soft diffuse upper-left light, restrained self-shadow contained under the chair.
Constraints: genuinely transparent alpha background; no floor, rug, text, logo, watermark, people, perspective, visible side elevation, black outline or extra objects.

### table-coffee-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan furniture sprite.
Primary request: ONE sculptural modern coffee table viewed EXACTLY vertically from above, orthographic plan camera. Footprint 1.10 m wide horizontally by 0.55 m deep vertically. Rounded organic-rectangle pale travertine tabletop with subtle cream stone veining and a small inset oval dark olive-green stone tray integrated into the right third; no loose accessories. Refined premium interior-design catalogue realism, compatible with ivory sofas and pale oak flooring.
Composition: centered landscape image, complete object fills about 92% of frame with even margin.
Lighting: soft upper-left diffuse light, minimal self-shadow contained under object.
Constraints: genuinely transparent alpha background; no floor, rug, books, cups, plant, text, logo, people, perspective, visible side elevation, thick outline or extra objects.

### counter-kitchen-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan fixture sprite.
Primary request: ONE straight modern kitchen counter viewed EXACTLY vertically from above, orthographic plan camera. Footprint 2.40 m wide horizontally by 0.62 m deep vertically. Warm white quartz countertop with faint mineral texture, slim pale-oak cabinet edge visible only subtly along the BOTTOM, one realistic inset brushed-steel rectangular sink with small dark faucet centered left, clear preparation surface on the right. No stove, no food, no utensils.
Composition: centered landscape image, complete counter fills about 94% of frame with a narrow even margin.
Lighting: neutral soft diffuse upper-left light, restrained self-shadow contained under object.
Constraints: genuinely transparent alpha background; no wall, backsplash, floor, room, labels, logo, watermark, people, perspective, visible cabinet front elevation, thick outline or extra objects.

### stove-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan appliance sprite.
Primary request: ONE premium built-in induction cooktop viewed EXACTLY vertically from above, orthographic plan camera. Footprint 0.60 m wide horizontally by 0.55 m deep vertically. Satin near-black glass with four subtle circular cooking zones, discreet brushed-metal edge and tiny unbranded touch controls. Clean contemporary realism, compatible with a high-end white and pale-oak kitchen.
Composition: centered square image, complete appliance fills 90% of frame with even margin.
Lighting: controlled soft upper-left reflections, readable but not glossy black void.
Constraints: genuinely transparent alpha background; no countertop, oven, wall, floor, pot, food, text, brand, logo, people, perspective, visible side elevation, thick outline or extra objects.

### fridge-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan appliance sprite.
Primary request: ONE compact premium refrigerator viewed EXACTLY vertically from above, orthographic plan camera. Square footprint 0.65 m by 0.65 m. Brushed warm-white enamel top surface with a slim graphite rear ventilation line along the TOP edge, subtle rounded corners and a delicate metallic door seam along the BOTTOM edge. Minimal realistic contemporary appliance, clearly distinct from a cabinet when viewed in plan.
Composition: centered square image, complete appliance fills 88% of frame with even transparent margin.
Lighting: soft upper-left diffuse highlight, restrained self-shadow contained under object.
Constraints: genuinely transparent alpha background; no floor, wall, kitchen, food, text, logo, watermark, people, perspective, visible front elevation, handle projecting outside footprint, thick outline or extra objects.

### bathtub-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan sanitary fixture sprite.
Primary request: ONE contemporary freestanding oval bathtub viewed EXACTLY vertically from above, orthographic plan camera. Footprint 1.70 m wide horizontally by 0.75 m deep vertically. Warm matte-white ceramic outer rim, realistic pale blue-grey waterless inner basin, slim brushed-nickel drain near the right end and a compact modern filler aligned at the left inner rim. Refined spa-quality realism, elegant thin rim and softly rounded shape.
Composition: centered landscape image, complete fixture fills about 92% of frame with even margin.
Lighting: soft neutral upper-left illumination, subtle self-shadow contained beneath object.
Constraints: genuinely transparent alpha background; no floor, tiles, wall, towels, plant, bath mat, text, logo, people, perspective, visible side elevation, thick outline or extra objects.

### toilet-v3.png

Use case: product-mockup. Asset type: transparent architectural plan sprite. Generate ONE compact contemporary white ceramic toilet as a clean alpha cutout, viewed EXACTLY vertically overhead with orthographic camera. Footprint 0.48m wide by 0.78m long, vertical portrait orientation. Slim rectangular cistern at TOP with small brushed-metal dual flush button; realistic closed rounded seat and bowl extends toward BOTTOM. Premium matte white ceramic with subtle pale-blue rim separation, soft neutral lighting. Centered, complete fixture fills 88% of frame with a narrow even margin. Background MUST be genuine fully transparent alpha with zero haze, zero backdrop, zero grey glow and zero checkerboard. Object pixels fully opaque. No floor, wall, text, logo, paper, brush, people, perspective, visible side elevation, heavy outline or extra objects.

### sink-basin-v2.png

Use case: product-mockup.
Asset type: transparent architectural floor-plan sanitary fixture sprite.
Primary request: ONE compact contemporary bathroom basin viewed EXACTLY vertically from above, orthographic plan camera. Footprint 0.55 m wide horizontally by 0.42 m deep vertically. Rounded rectangular warm-white ceramic basin, realistic shallow bowl, centered brushed-nickel drain and minimal slim faucet along the TOP edge. Premium restrained spa realism, thin elegant rim.
Composition: centered landscape image, complete fixture fills about 88% of frame with even transparent margin.
Lighting: soft neutral upper-left diffuse light, restrained self-shadow contained beneath object.
Constraints: genuinely transparent alpha background; no vanity cabinet, counter, wall, mirror, floor, soap, towels, text, logo, people, perspective, visible side elevation, thick outline or extra objects.

## Finalisation du catalogue — 27 septembre 2026

Mode : outil ImageGen intégré, une génération distincte par objet, avec
`transparent_background: true`. La première cheminée, trop frontale, a été
rejetée et conservée sous
`benchmark/rejected-assets/final-v1/fireplace-front-elevation.png`. La seconde
est la variante intégrée. Les six sorties finales ont été copiées dans ce
dossier avant intégration.

Après validation visuelle, les 22 PNG ont été réencodés en PNG RGBA optimisé et
les images dont le grand côté dépassait 1280 px ont généralement été ramenées à
1280 px avec Lanczos. Le meuble TV conserve exceptionnellement 2048 × 512 px
afin de respecter simultanément son ratio contractuel 4:1 et le minimum de
512 px sur chaque axe. Les canevas du meuble TV et du chevet ont été recadrés
sur leurs marges transparentes pour correspondre à leurs empreintes, sans
étirement des pixels.
Les originaux non optimisés sont conservés sous
`benchmark/baselines/editor-final-assets-unoptimized/`. Le poids passe de
39 291 254 à 27 734 479 octets, soit une réduction de 29,41 %.

### nightstand-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
furniture sprite. ONE premium contemporary bedside table viewed exactly
vertically from above with an orthographic plan camera. Footprint 0.45 m wide
by 0.40 m deep. Pale natural-oak rounded-square tabletop, subtle slim drawer
seam along the bottom edge and one tiny centered brushed-brass pull. Centered,
88% of a square frame, soft diffuse upper-left illumination, contained
self-shadow. Genuine transparent alpha; no floor, wall, bed, lamp, books,
decoration, text, logo, people, perspective, front elevation or extra object.

### wardrobe-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
furniture sprite. ONE premium contemporary wardrobe viewed exactly vertically
from above with an orthographic plan camera. Footprint 1.20 m wide by 0.60 m
deep. Long pale natural-oak rectangular top, rounded corners, central two-door
division and two tiny brass pulls readable only along the bottom edge. Centered,
92% of a landscape frame, contained shadow. Genuine transparent alpha; no
wall, floor, clothes, mirror, open door, perspective or extra object.

### desk-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
furniture sprite. ONE refined contemporary writing desk viewed exactly
vertically from above with an orthographic plan camera. Footprint 1.20 m wide
by 0.60 m deep. Slim pale-oak rounded desktop, fine grain and narrow matte
charcoal cable inlay near the top edge. Empty surface, centered at 92% of a
landscape frame. Genuine transparent alpha; no computer, chair, accessories,
floor, perspective, front elevation or extra object.

### fireplace-v2.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
fixture sprite. ONE compact contemporary built-in fireplace footprint seen
directly from above. Footprint 0.70 m wide by 0.55 m deep. Shallow pale
limestone hearth slab surrounding a recessed matte-black fire cavity with dark
charcoal and restrained amber embers. Simple horizontal rounded-rectangle
silhouette, rear wall side at top, 88% of a landscape frame. Genuine transparent
alpha; no facade, elevation, vertical mantel, chimney, wall, floor, smoke,
perspective, isometric angle or extra object.

### rug-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
textile sprite. ONE contemporary rectangular area rug viewed exactly vertically
from above. Footprint 2.20 m wide by 1.60 m deep. Warm ivory wool, restrained
low-contrast pale-greige diamond lattice, fine woven texture and short fringe
only on left and right. Flat, centered at 94%, almost no shadow. Genuine
transparent alpha outside; no floor, furniture, curled corner, perspective or
extra object.

### tv-console-v1.png

Use case: product-mockup. Asset type: transparent architectural floor-plan
furniture sprite. ONE premium contemporary low TV console viewed exactly
vertically from above. Footprint 1.60 m wide by 0.40 m deep. Long pale-oak
rounded top, fine grain, centered charcoal media slot near the bottom edge and
subtle two-door divisions. Empty surface, centered at 94%, contained shadow.
Genuine transparent alpha; no television, speakers, cables, decorations,
floor, wall, perspective, front elevation or extra object.


