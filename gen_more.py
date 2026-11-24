"""The rest of the four mods' items and blocks, run by `gen_content.py` in its own namespace (it
uses `write`, `copy`, `lang`, `NS`, `oa`, `od`, `out`, `jar`, `jars`, `CARDS`, `translated`,
`sword`, `weapon`, `CHARGE`).

From Touhou Items Mod (kuro-anco): the Five Impossible Requests, the pearls, shots and lasers, the
remaining character items, the danmaku crafting tables and the divine spirits. From SPELLCARD PLUS:
the Hoshiguma dishes, the Hina dolls, Stockpiling Misfortune and Yukari's yin-yang orb. From
Journey To Gensokyo (Katrix): its ores, ingots, dusts, old spellcards and notes, and the keystone.
From Grimoire of Alice (Arekkuusu): its materials, foods, masks, shields and blocks.

What an item does when used, let go or worn is in `native/api/src/items.rs` (`more` there); one
listed in NO_BEHAVIOUR below is only its art and name so far. The recipes are the originals', read
from their Java (`recipes()` below); one naming something this port lacks is left out and listed.
"""
import re

K = jar / "assets" / "thkaguyamod" / "textures"
GI = jars / "grimoire" / "assets" / "grimoireofalice" / "textures"
JT = jars / "jtg" / "assets" / "journeytogensokyo" / "textures"
SP = jars / "spellcard" / "assets" / "spellcardplusmod" / "textures" / "items"
SRC = jars.parent / "src"
ROOT = {"k": K / "items", "g": GI / "items", "j": JT / "items", "s": SP}

# 1.7.10's potion numbers, as 26.3 names them
POTION = {
    "field_76424_c": "speed", "field_76421_d": "slowness", "field_76422_e": "haste", "field_76419_f": "mining_fatigue",
    "field_76420_g": "strength", "field_76432_h": "instant_health", "field_76433_i": "instant_damage",
    "field_76430_j": "jump_boost", "field_76431_k": "nausea", "field_76428_l": "regeneration",
    "field_76429_m": "resistance", "field_76426_n": "fire_resistance", "field_76427_o": "water_breathing",
    "field_76441_p": "invisibility", "field_76440_q": "blindness", "field_76439_r": "night_vision",
    "field_76438_s": "hunger", "field_76437_t": "weakness", "field_76436_u": "poison", "field_82731_v": "wither",
    "field_76444_x": "absorption",
}


def effects(*es):
    """`(name, seconds-or-ticks as ticks, amplifier)` as a consumable's effects."""
    return [{"type": "minecraft:apply_effects", "effects": [
        {"id": f"minecraft:{n}", "duration": max(t, 1), "amplifier": a} for n, t, a in es]}]


def food(nutrition, modifier, es=(), always=False, drink=False, seconds=1.6, remainder=None):
    """1.7.10's `ItemFood(heal, saturationModifier)`: saturation is heal x modifier x 2."""
    c = {
        "minecraft:food": {"nutrition": nutrition, "saturation": round(nutrition * modifier * 2, 2), "can_always_eat": always},
        "minecraft:consumable": {
            "consume_seconds": seconds, "animation": "drink" if drink else "eat",
            "sound": "minecraft:entity.generic.drink" if drink else "minecraft:entity.generic.eat",
            "on_consume_effects": effects(*es) if es else [],
        },
    }
    if remainder:
        c["minecraft:use_remainder"] = {"id": f"{NS}:{remainder}", "count": 1}
    return c


def drink(es, remainder=None, seconds=1.0):
    """Drunk whenever, fed nothing: a potion in something else."""
    c = {"minecraft:consumable": {"consume_seconds": seconds, "animation": "drink",
                                  "sound": "minecraft:entity.generic.drink", "on_consume_effects": effects(*es)}}
    if remainder:
        c["minecraft:use_remainder"] = {"id": f"{NS}:{remainder}", "count": 1}
    return c


def armor(slot, points, durability):
    """Worn in `slot` for `points` of armour; drawn as nothing on the body (the originals' models are
    not ported)."""
    return {
        "minecraft:max_damage": durability,
        "minecraft:equippable": {"slot": slot},
        "minecraft:attribute_modifiers": [{"type": "minecraft:armor", "id": f"{NS}:armor.{slot}", "amount": points,
                                           "operation": "add_value", "slot": slot}],
        "!minecraft:repairable": {},
    }


HELMET, CHEST = "minecraft:iron_helmet", "minecraft:iron_chestplate"
PAPER = "minecraft:paper"
STACK = lambda n: {"minecraft:max_stack_size": n}

# id, texture ("<root>:<path>"), name, template, components; an optional sixth: a second layer.
MORE = [
    # ---- Touhou Items Mod: the Five Impossible Requests and their kin
    ("hourai_jeweled_branch", "k:houraiEda", "Jeweled Branch of Hourai", PAPER, weapon(CHARGE)),
    ("dragon_neck_jewel", "k:ryuuTama", "Jewel from the Dragon's Neck", PAPER, {"minecraft:max_damage": 64}),
    ("buddha_stone_bowl", "k:hotokeHachi", "Buddha's Stone Bowl", "minecraft:stone_sword", weapon(sword(5, 131))),
    ("fire_rat_robe", "k:hinezumi", "Robe of the Fire Rat", CHEST, armor("chest", 6, 400)),
    ("swallow_cowrie_shell", "k:koyasugai", "Swallow's Cowrie Shell", "minecraft:apple",
     dict(food(4, 0.6, [("regeneration", 600, 1)], always=True), **{"minecraft:enchantment_glint_override": True})),
    ("kinkakuji", "k:kinkakuzi", "Seamless Ceiling of Kinkaku-ji", PAPER, {}),
    ("aja_red_stone", "k:AjaRedStone", "Red Stone of Aja", PAPER, {}),
    # ---- the colour pearls
    *[(f"{c}_pearl", f"k:material/{c.capitalize()}Pearl", f"{c.capitalize()} Pearl", PAPER, STACK(64))
      for c in ("red", "blue", "green", "yellow", "purple", "aqua", "orange", "white")],
    # ---- the character items
    ("yin_yang_orb", "k:material/Onmyoudama", "Yin-Yang Orb", PAPER, STACK(64)),
    ("bloodthirsty_yin_yang_orb", "k:material/Onmyoudama", "Bloodthirsty Yin-Yang Orb", PAPER,
     weapon(dict(CHARGE, **{"minecraft:max_damage": 120}))),
    ("magic_broom", "k:magicBroom", "Magic Broom", PAPER, {}),
    ("marisa_hat", "k:MarisaHat", "Marisa's Hat", HELMET, armor("head", 2, 200)),
    ("silver_knife_blue", "k:shot/SilverKnife_Blue", "Silver Knife", PAPER, STACK(64)),
    ("silver_knife_red", "k:shot/SilverKnife_Red", "Silver Knife (Red)", PAPER, STACK(64)),
    ("silver_knife_green", "k:shot/SilverKnife_Green", "Silver Knife (Green)", PAPER, STACK(64)),
    ("silver_knife_white", "k:shot/SilverKnife_White", "Time Paradox Knife", PAPER, STACK(64)),
    ("sakuya_watch", "k:sakuyaWatch", "Sakuya's Pocket Watch", PAPER, {}),
    ("cursed_decoy_doll", "k:cursedDecoyDoll", "Cursed Decoy Doll", PAPER, STACK(16)),
    ("soul_torch", "k:soulTorch", "Soul Torch", PAPER, STACK(16)),
    ("gap", "k:sukima", "Gap", PAPER, {}),
    ("gap_folding_umbrella", "k:GapFoldingUmbrella_base", "Gap Folding Umbrella", PAPER, {}, "k:GapFoldingUmbrella_ribbon"),
    ("kappa_cap", "k:kappaCap", "Kappa Cap", HELMET, armor("head", 1, 200)),
    ("suwako_hat", "k:Kerobou", "Suwako's Hat", HELMET, armor("head", 2, 200)),
    ("third_eye", "k:thirdEye_0", "3rd Eye", PAPER, {}),
    ("closed_third_eye", "k:closedThirdEye", "Closed 3rd Eye", PAPER, {}),
    ("nazrin_pendulum", "k:pendulum", "Nazrin Pendulum", PAPER, STACK(16)),
    ("ship_ghost_dipper_empty", "k:hisyaku_0", "Ship Ghost's Dipper", PAPER, {}),
    ("ship_ghost_dipper", "k:hisyaku_1", "Ship Ghost's Dipper (Filled)", PAPER, {}),
    ("sorcerer_sutra_scroll", "k:mazinKyoukan", "Sorcerer's Sutra Scroll", PAPER, {}),
    ("wall_passing_chisel", "k:kabenuke", "Wall-Passing Chisel", PAPER, {}),
    ("shot_material", "k:material/ShotMaterial", "Shot Material", PAPER, STACK(64)),
]

# The shots and lasers: crafted from shot material, fired by hand, and what spell cards are made of.
SHOTS = ["small", "tiny", "medium", "big", "star", "small_star", "circle", "scale", "butterfly", "light", "knife",
         "heart", "kunai", "talisman", "big_light", "rice", "oval", "crystal", "arrow"]
for s in SHOTS:
    tex = "".join(w.capitalize() for w in s.split("_")) + "Shot"
    MORE.append((f"{s}_shot", f"k:shot/{tex}", " ".join(w.capitalize() for w in s.split("_")) + " Shot", PAPER, STACK(64)))
for s, name in (("middle", "Laser"), ("short", "Short Laser"), ("long", "Long Laser")):
    MORE.append((f"{s}_laser", f"k:shot/{s.capitalize()}Laser", name, PAPER, STACK(64)))

# ---- SPELLCARD PLUS: Hoshiguma's dish, drunk from with a potion in it, leaves you a little drunk
DISHES = [  # id suffix, name, effect, ticks, amplifier
    ("speed", "Swiftness", "speed", 3600, 0), ("speed_2", "Swiftness II", "speed", 3600, 1),
    ("speed_2_long", "Swiftness II+", "speed", 9600, 1), ("speed_3", "Swiftness III", "speed", 1800, 2),
    ("strength", "Strength", "strength", 3600, 0), ("strength_2", "Strength II", "strength", 3600, 1),
    ("strength_2_long", "Strength II+", "strength", 9600, 1), ("strength_3", "Strength III", "strength", 1800, 2),
    ("healing", "Healing", "instant_health", 1, 0), ("healing_2", "Healing II", "instant_health", 1, 1),
    ("healing_3", "Healing III", "instant_health", 1, 2),
    ("regeneration", "Regeneration", "regeneration", 900, 0), ("regeneration_2", "Regeneration II", "regeneration", 900, 1),
    ("regeneration_2_long", "Regeneration II+", "regeneration", 2400, 1), ("regeneration_3", "Regeneration III", "regeneration", 450, 2),
    ("fire_resistance", "Fire Resistance", "fire_resistance", 9600, 0), ("fire_resistance_long", "Fire Resistance+", "fire_resistance", 15600, 0),
    ("night_vision", "Night Vision", "night_vision", 9600, 0), ("night_vision_long", "Night Vision+", "night_vision", 15600, 0),
    ("water_breathing", "Water Breathing", "water_breathing", 9600, 0), ("water_breathing_long", "Water Breathing+", "water_breathing", 15600, 0),
    ("invisibility", "Invisibility", "invisibility", 9600, 0), ("invisibility_long", "Invisibility+", "invisibility", 15600, 0),
]
MORE.append(("hoshiguma_dish", "s:HoshigumaDish", "Hoshiguma Dish", PAPER, {}))
for suffix, name, e, t, a in DISHES:
    MORE.append((f"hoshiguma_dish_{suffix}", "s:HoshigumaDishWithpotion", f"Hoshiguma Dish of {name}", PAPER,
                 drink([(e, t, a), ("nausea", 400, 2)], remainder="hoshiguma_dish")))
MORE += [
    ("instant_hina_doll", "s:InstantHinaDoll", "Instant Hina Doll", PAPER, STACK(64)),
    ("floating_hina_doll", "s:InstantHinaDoll", "Floating Hina Doll", PAPER, STACK(64)),
    ("stockpiling_misfortune", "s:Stockpilingmisfortune", "Stockpiling Misfortune", PAPER, {}),
    ("yin_yang_orb_yukari", "s:armor/Yin_yang_orb_Yukari", "Yin-Yang Orb Yukari", CHEST, armor("chest", 3, 400)),
]

# ---- Journey To Gensokyo's metals and papers
for metal, name in (("gensokyo", "Gensokium"), ("demon", "Makaiium"), ("celestial", "Celestium")):
    MORE.append((f"{name.lower()}_ingot", f"j:{metal}Ingot", name, PAPER, STACK(64)))
    MORE.append((f"{name.lower()}_dust", f"j:{metal}Dust", f"{name} Dust", PAPER, STACK(64)))
for kind, name in (("Gensokyo", "Gensokyo"), ("Demon", "Demon"), ("Celestial", "Celestial")):
    MORE.append((f"old_{kind.lower()}_spellcard", f"j:old{kind}Spell", f"Old {name} Spellcard", PAPER, STACK(64)))
for i, (tex, name) in enumerate((("Ruined", "Ruined Old Notebook"), ("Patched", "Patched Gensokyo Notes"),
                                 ("Dusty", "Dusty Gensokyo Notes"), ("Normal", "Gensokyo Notes"),
                                 ("Imbued", "Imbued Gensokyo Notes"), ("Arcane", "Arcane Gensokyo Notes"))):
    c = dict(STACK(16))
    if i >= 4:
        c["minecraft:enchantment_glint_override"] = True
    MORE.append((f"gensokyo_notes_{tex.lower()}", f"j:gensokyoNotes{tex}", name, PAPER, c))

# ---- Grimoire of Alice
GOA_MASK = armor("head", 1, 100)
MORE += [
    ("goa_enchanted_book", "g:EnchantedBook", "Enchanted Book of Alice", PAPER, {}),
    ("grimoire_book", "g:GrimoireBook", "Grimoire Book", PAPER, {"minecraft:enchantment_glint_override": True}),
    ("volatile_string", "g:VolatileString", "Volatile String", PAPER, STACK(64)),
    ("soldified_paper", "g:SoldifiedPaper", "Soldified Paper", PAPER, STACK(16)),
    ("tamahagane", "g:GloriousNipponSteel", "Tamahagane", PAPER, STACK(64)),
    ("shimenawa_rope", "g:ShimenawaRope", "Shimenawa Rope", PAPER, STACK(64)),
    ("youkai_book", "g:YoukaiBook", "Youkai Book", PAPER, {}),
    ("mask", "g:Mask", "Mask", PAPER, STACK(16)),
    ("hihiirokane", "g:Hihiirokane", "Hihi'irokane", PAPER, STACK(64)),
    ("impure_rock", "g:ImpureRock", "Impure Mineral", PAPER, STACK(64)),
    ("shroom_slice", "g:ShroomSlice", "Shroom Slice", "minecraft:apple", dict(food(4, 1.2), **STACK(64))),
    ("grilled_lamprey", "g:GrilledLamprey", "Grilled Lamprey", "minecraft:apple",
     dict(food(6, 2.0, [("night_vision", 2400, 0)]), **STACK(64))),
    ("ibaraki_box_empty", "g:IbarakiBoxEmpty", "Ibaraki Box", PAPER, {}),
    ("ibaraki_box", "g:IbarakiBoxFull", "Ibaraki Box (Filled)", "minecraft:apple",
     food(2, 2.0, [("nausea", 2400, 0)], always=True, drink=True, remainder="ibaraki_box_empty")),
    ("kappas_nostrum", "g:KappasNostrum", "Kappa's Nostrum", "minecraft:apple",
     dict(food(1, 1.0, [("instant_health", 1, 0)], always=True, drink=True), **STACK(16))),
    *[(f"{m}_mask", f"g:{t}Mask", f"{n} Mask", HELMET, GOA_MASK) for m, t, n in (
        ("fox", "Fox", "Fox"), ("raiden", "Raiden", "Raiden"), ("monkey", "Monkey", "Monkey"),
        ("hyottoko", "Hyottoko", "Hyottoko"), ("fuku_no_kami", "FukuNoKami", "Fuku no Kami"), ("uba", "Uba", "Uba"),
        ("hannya", "Hannya", "Hannya"), ("koomote", "Koomote", "Ko-omote"))],
    ("mask_of_hope", "g:MaskOfHope", "Mask of Hope", HELMET, GOA_MASK),
    ("kokoros_masks", "g:KokorosMasks", "Kokoro's Masks", HELMET, armor("head", 3, 500)),
    ("primordial_shield", "g:PrimordialShield", "Primordial Shield", "minecraft:shield", {"minecraft:max_damage": 1000}),
    ("maple_leaf_shield", "g:MapleLeafShield", "Maple Leaf Shield", "minecraft:shield", {"minecraft:max_damage": 500}),
    ("goa_laevatein", "g:Laevatein", "Laevatein", "minecraft:iron_sword", weapon(sword(6, 1000))),
    ("goa_miko_stick", "g:MikoStick", "Toyosatomimi's Stick", "minecraft:iron_sword", weapon(sword(5, 1000))),
    ("crest_of_yggdrasill", "g:CrestOfYggdrasill", "Crest of Yggdrasill", "minecraft:iron_sword", weapon(sword(6, 1000))),
    ("goa_third_eye", "g:3rdEye", "3rd Eye (Satori's)", PAPER, {}),
]

# Used or worn does nothing yet: only art and a name.
NO_BEHAVIOUR = {"kinkakuji", "aja_red_stone", "magic_broom", "sakuya_watch", "gap", "gap_folding_umbrella", "third_eye",
                "nazrin_pendulum", "ship_ghost_dipper_empty", "ship_ghost_dipper", "sorcerer_sutra_scroll",
                "wall_passing_chisel", "stockpiling_misfortune", "yin_yang_orb_yukari", "goa_enchanted_book",
                "youkai_book", "goa_third_eye", "floating_hina_doll", "suwako_hat", "marisa_hat"}


def texture(code):
    root, path = code.split(":", 1)
    return ROOT[root] / f"{path}.png"


more_tab = []
for entry in MORE:
    item, tex, name, template, components = entry[:5]
    layers = [tex] + list(entry[5:])
    model_tex = {}
    for i, t in enumerate(layers):
        p = texture(t)
        suffix = "" if i == 0 else f"_{i}"
        copy(p, oa / "textures" / "item" / f"{item}{suffix}.png")
        meta = p.with_name(p.name + ".mcmeta")
        if meta.exists():
            copy_meta(meta, oa / "textures" / "item" / f"{item}{suffix}.png.mcmeta")
        model_tex[f"layer{i}"] = f"{NS}:item/{item}{suffix}"
    comps = {"minecraft:item_name": {"translate": f"item.{NS}.{item}"}}
    comps.update(components)
    stack = comps.pop("minecraft:max_stack_size", 1 if "minecraft:max_damage" in comps or template in (HELMET, CHEST) else 16)
    write(od / "horizon" / "item" / f"{item}.json", {"template": template, "max_stack_size": stack, "rarity": "rare", "components": comps})
    write(oa / "items" / f"{item}.json", {"model": {"type": "minecraft:model", "model": f"{NS}:item/{item}"}})
    write(oa / "models" / "item" / f"{item}.json", {"parent": "minecraft:item/handheld", "textures": model_tex})
    lang[f"item.{NS}.{item}"] = name
    more_tab.append(f"{NS}:{item}")

# ---- blocks
BLOCKS = []  # ids, for the blocks tab


def block(bid, name, template, props, textures, shape="all", mine="pickaxe", tool=None, light=None):
    """A plain block of `template`'s kind with its own art, dropping itself."""
    files = {}
    for key, (root, path) in textures.items():
        p = root / f"{path}.png"
        files[key] = f"{NS}:block/{bid}_{key}"
        copy(p, oa / "textures" / "block" / f"{bid}_{key}.png")
        meta = p.with_name(p.name + ".mcmeta")
        if meta.exists():
            copy_meta(meta, oa / "textures" / "block" / f"{bid}_{key}.png.mcmeta")
    props = dict(props)
    if light is not None:
        props["light"] = light
    write(od / "horizon" / "block" / f"{bid}.json", {"template": template, "properties": props, "item": True})
    if shape == "all":
        model = {"parent": "minecraft:block/cube_all", "textures": {"all": files["all"]}}
    elif shape == "column":
        model = {"parent": "minecraft:block/cube_column", "textures": {"end": files["end"], "side": files["side"]}}
    else:  # a plant
        model = {"parent": "minecraft:block/cross", "textures": {"cross": files["all"]}}
    write(oa / "models" / "block" / f"{bid}.json", model)
    write(oa / "blockstates" / f"{bid}.json", {"variants": {"": {"model": f"{NS}:block/{bid}"}}})
    if shape == "cross":
        write(oa / "models" / "item" / f"{bid}.json", {"parent": "minecraft:item/generated", "textures": {"layer0": files["all"]}})
    else:
        write(oa / "models" / "item" / f"{bid}.json", {"parent": f"{NS}:block/{bid}"})
    write(oa / "items" / f"{bid}.json", {"model": {"type": "minecraft:model", "model": f"{NS}:item/{bid}"}})
    write(od / "loot_table" / "blocks" / f"{bid}.json", {"type": "minecraft:block", "pools": [{
        "rolls": 1, "entries": [{"type": "minecraft:item", "name": f"{NS}:{bid}"}],
        "conditions": [{"condition": "minecraft:survives_explosion"}]}]})
    lang[f"block.{NS}.{bid}"] = name
    lang[f"item.{NS}.{bid}"] = name
    BLOCKS.append((bid, mine, tool))


KB, GB, JB = K / "blocks", GI / "blocks", JT / "blocks"
STONE = {"hardness": 2.0, "explosion_resistance": 5.0, "sounds": "minecraft:stone"}
# Touhou Items Mod: its crafting tables (their screens are not ported) and the divine spirits.
block("danmaku_crafting_table", "Danmaku Crafting Table", "minecraft:oak_planks",
      {"hardness": 1.5, "explosion_resistance": 1.5, "sounds": "minecraft:oak_planks"}, {"all": (KB, "danmaku_crafting_table")},
      mine="axe", light=15)
block("laser_crafting_table", "Laser Crafting Table", "minecraft:oak_planks",
      {"hardness": 1.5, "explosion_resistance": 1.5, "sounds": "minecraft:oak_planks"}, {"all": (KB, "danmaku_crafting_table2")},
      mine="axe", light=15)
for c in ("red", "blue", "green", "yellow", "purple", "aqua", "orange", "white"):
    block(f"divine_spirit_{c}", f"Divine Spirit ({c.capitalize()})", "minecraft:glass",
          {"hardness": 0.1, "explosion_resistance": 0.1, "sounds": "minecraft:glass"}, {"all": (KB, f"divinespirit_{c}")},
          mine=None, light=8)
# Journey To Gensokyo
for metal, name, tool in (("gensokyo", "Gensokium", "iron"), ("demon", "Makaiium", "iron"), ("celestial", "Celestium", "iron")):
    block(f"{name.lower()}_ore", f"{name} Ore", "minecraft:stone", STONE, {"all": (JB, f"{metal}Ore")}, tool=tool)
block("keystone", "Keystone", "minecraft:stone", dict(STONE, explosion_resistance=15.0),
      {"all": (JB, "keyStone_side")}, tool="stone")
# Grimoire of Alice
block("holy_key_stone", "Holy KeyStone", "minecraft:stone", dict(STONE, hardness=3.0, explosion_resistance=30.0),
      {"all": (GB, "HolyKeyStone_side")})
block("holy_stone", "Holy Stone", "minecraft:stone", dict(STONE, hardness=3.0, explosion_resistance=30.0),
      {"all": (GB, "HolyKeyStone_side")})
block("sugar_block", "Sugar Block", "minecraft:sand", {"hardness": 0.5, "explosion_resistance": 0.5, "sounds": "minecraft:sand"},
      {"all": (GB, "Sugar0")}, mine="shovel")
block("rope_block", "Enchanted Rope", "minecraft:hay_block", {"hardness": 0.8, "explosion_resistance": 0.8, "sounds": "minecraft:white_wool"},
      {"side": (GB, "Rope"), "end": (GB, "Rope_top")}, shape="column", mine="axe")
block("paper_block", "Enchanted Paper", "minecraft:white_wool", {"hardness": 0.8, "explosion_resistance": 0.8, "sounds": "minecraft:white_wool"},
      {"all": (GB, "Paper0")}, mine="axe")
block("compact_stone", "Compact Stone", "minecraft:stone", dict(STONE, hardness=4.0, explosion_resistance=20.0),
      {"all": (GB, "CompactStone0")})
block("hyperconcentrated_magic", "Hyperconcentrated Magic", "minecraft:iron_block",
      {"hardness": 0.5, "explosion_resistance": 5.0, "sounds": "minecraft:glass"}, {"all": (GB, "HyperconcentratedMagic")},
      tool="diamond", light=10)
block("shroom", "Shroom", "minecraft:red_mushroom", {"hardness": 0.0, "explosion_resistance": 0.0, "sounds": "minecraft:short_grass"},
      {"all": (GB, "Shroom")}, shape="cross", mine=None)
block("kyoumarubotan", "Kyoumarubotan", "minecraft:poppy", {"hardness": 0.0, "explosion_resistance": 0.0, "sounds": "minecraft:short_grass"},
      {"all": (GB, "Kyoumarubotan")}, shape="cross", mine=None)
block("onbashira_pillar", "Onbashira", "minecraft:oak_log", {"hardness": 2.0, "explosion_resistance": 10.0, "sounds": "minecraft:oak_planks"},
      {"side": (GB, "Onbashira_side"), "end": (GB, "Onbashira")}, shape="column", mine="axe")

mineable = {}
for bid, mine, tool in BLOCKS:
    if mine:
        mineable.setdefault(mine, []).append(f"{NS}:{bid}")
    if tool:
        mineable.setdefault(f"needs_{tool}_tool", []).append(f"{NS}:{bid}")
EXTRA_MINEABLE = mineable  # gen_content merges these with the Giga Torch's axe tag

# ---- Journey To Gensokyo's ores in the world: a few small veins low in the overworld, more in the
# Nether's netherrack and the End's stone, as its OreGen.
for name, target, biomes, count, lo, hi in (
        ("gensokium", {"predicate_type": "minecraft:tag_match", "tag": "minecraft:stone_ore_replaceables"}, "#minecraft:is_overworld", 3, -64, 32),
        ("makaiium", {"predicate_type": "minecraft:block_match", "block": "minecraft:netherrack"}, "#minecraft:is_nether", 8, 0, 128),
        ("celestium", {"predicate_type": "minecraft:block_match", "block": "minecraft:end_stone"}, "#minecraft:is_end", 8, 0, 128)):
    # 26.3's ore feature: its fields beside its type (no "config" any more).
    write(od / "worldgen" / "configured_feature" / f"ore_{name}.json", {"type": "minecraft:ore",
        "size": 4, "discard_chance_on_air_exposure": 0.0,
        "targets": [{"target": target, "state": {"Name": f"{NS}:{name}_ore"}}]})
    write(od / "worldgen" / "placed_feature" / f"ore_{name}.json", {"feature": f"{NS}:ore_{name}", "placement": [
        {"type": "minecraft:count", "count": count}, {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": {"type": "minecraft:uniform",
                                                      "min_inclusive": {"absolute": lo}, "max_inclusive": {"absolute": hi}}},
        {"type": "minecraft:biome"}]})
    write(od / "neoforge" / "biome_modifier" / f"ore_{name}.json", {
        "type": "neoforge:add_features", "biomes": biomes, "features": f"{NS}:ore_{name}", "step": "underground_ores"})

# ---- recipes, from the originals' Java
# 1.7.10's item and block fields, by their obfuscated names
VANILLA = {
    "Items.field_151121_aF": "paper", "Items.field_151156_bN": "nether_star", "Items.field_151102_aT": "sugar",
    "Items.field_151044_h": "coal", "Items.field_151007_F": "string", "Items.field_151170_bI": "poisonous_potato",
    "Items.field_151129_at": "lava_bucket", "Items.field_151073_bk": "ghast_tear", "Items.field_151072_bj": "blaze_rod",
    "Items.field_151071_bq": "fermented_spider_eye", "Items.field_151070_bp": "spider_eye", "Items.field_151008_G": "feather",
    "Items.field_151154_bQ": "firework_star", "Items.field_151145_ak": "flint", "Items.field_151144_bL": "skeleton_skull",
    "Items.field_151131_as": "water_bucket", "Items.field_151122_aG": "book", "Items.field_151119_aD": "clay_ball",
    "Items.field_151118_aC": "brick", "Items.field_151115_aP": "cod", "Items.field_151110_aK": "egg",
    "Items.field_151103_aS": "bone", "Items.field_151078_bh": "rotten_flesh", "Items.field_151077_bg": "cooked_chicken",
    "Items.field_151075_bm": "nether_wart", "Items.field_151074_bl": "gold_nugget", "Items.field_151065_br": "blaze_powder",
    "Items.field_151060_bw": "glistering_melon_slice", "Items.field_151045_i": "diamond", "Items.field_151043_k": "gold_ingot",
    "Items.field_151042_j": "iron_ingot", "Items.field_151033_d": "flint_and_steel", "Items.field_151016_H": "gunpowder",
    "Items.field_151009_A": "mushroom_stew", "Items.field_151137_ax": "redstone", "Items.field_151079_bi": "ender_pearl",
    "Items.field_151166_bC": "emerald", "Items.field_151114_aO": "glowstone_dust", "Items.field_151113_aN": "clock",
    "Items.field_151010_B": "golden_sword", "Items.field_151055_y": "stick", "Items.field_151034_e": "apple",
    "Items.field_151153_ao": "golden_apple", "Items.field_151061_bv": "ender_eye", "Items.field_151032_g": "arrow",
    "Items.field_151031_f": "bow", "Items.field_151040_l": "iron_sword", "Items.field_151048_u": "diamond_sword",
    "Items.field_151041_m": "wooden_sword", "Items.field_151052_q": "stone_sword", "Items.field_151054_z": "bowl",
    "Items.field_151133_ar": "bucket", "Items.field_151116_aA": "leather", "Items.field_151117_aB": "milk_bucket",
    "Items.field_151123_aH": "slime_ball", "Items.field_151126_ay": "snowball", "Items.field_151128_bU": "quartz",
    "Items.field_151064_bs": "magma_cream", "Items.field_151069_bo": "glass_bottle", "Items.field_151062_by": "experience_bottle",
    "Items.field_151059_bz": "fire_charge", "Items.field_151057_cb": "name_tag", "Items.field_151058_ca": "lead",
    "Items.field_151012_L": "melon_seeds", "Items.field_151015_O": "wheat", "Items.field_151025_P": "bread",
    "Items.field_151127_ba": "melon_slice", "Items.field_151172_bF": "carrot", "Items.field_151174_bG": "potato",
    "Items.field_151099_bA": "writable_book", "Items.field_151164_bB": "written_book", "Items.field_151111_aL": "compass",
    "Items.field_151143_au": "minecart", "Items.field_151020_U": "chainmail_helmet", "Items.field_151028_Y": "iron_helmet",
    "Items.field_151024_Q": "leather_helmet", "Items.field_151027_R": "leather_chestplate", "Items.field_151030_Z": "iron_chestplate",
    "Items.field_151100_aR": None,  # dye: by its damage
    "Blocks.field_150348_b": "stone", "Blocks.field_150402_ci": "coal_block", "Blocks.field_150451_bX": "redstone_block",
    "Blocks.field_150424_aL": "netherrack", "Blocks.field_150377_bs": "end_stone", "Blocks.field_150371_ca": "quartz_block",
    "Blocks.field_150343_Z": "obsidian", "Blocks.field_150432_aD": "ice", "Blocks.field_150426_aN": "glowstone",
    "Blocks.field_150327_N": "dandelion", "Blocks.field_150328_O": "poppy", "Blocks.field_150325_L": "white_wool",
    "Blocks.field_150344_f": "oak_planks", "Blocks.field_150364_r": "oak_log", "Blocks.field_150347_e": "cobblestone",
    "Blocks.field_150359_w": "glass", "Blocks.field_150339_S": "iron_block", "Blocks.field_150340_R": "gold_block",
    "Blocks.field_150484_ah": "diamond_block", "Blocks.field_150475_bE": "emerald_block", "Blocks.field_150335_W": "tnt",
    "Blocks.field_150462_ai": "crafting_table", "Blocks.field_150460_al": "furnace", "Blocks.field_150486_ae": "chest",
    "Blocks.field_150354_m": "sand", "Blocks.field_150351_n": "gravel", "Blocks.field_150346_d": "dirt",
    "Blocks.field_150349_c": "grass_block", "Blocks.field_150345_g": "oak_sapling", "Blocks.field_150362_t": "oak_leaves",
    "Blocks.field_150338_P": "brown_mushroom", "Blocks.field_150337_Q": "red_mushroom", "Blocks.field_150423_aK": "pumpkin",
    "Blocks.field_150440_ba": "melon", "Blocks.field_150379_bu": "redstone_lamp", "Blocks.field_150381_bn": "enchanting_table",
    "Blocks.field_150368_y": "lapis_block", "Blocks.field_150433_aE": "snow_block", "Blocks.field_150435_aG": "clay",
    "Blocks.field_150336_V": "bricks", "Blocks.field_150342_X": "bookshelf", "Blocks.field_150406_ce": "terracotta",
    "Blocks.field_150425_aM": "soul_sand", "Blocks.field_150479_bC": "tripwire_hook", "Blocks.field_150392_bi": "lily_pad", "Blocks.field_150331_J": "piston",
    "Blocks.field_150403_cj": "packed_ice", "Blocks.field_150434_aF": "cactus", "Blocks.field_150436_aH": "sugar_cane", "Blocks.field_150395_bd": "vine",
}
DYES = ["ink_sac", "red_dye", "green_dye", "cocoa_beans", "lapis_lazuli", "purple_dye", "cyan_dye", "light_gray_dye", "gray_dye",
        "pink_dye", "lime_dye", "yellow_dye", "light_blue_dye", "magenta_dye", "orange_dye", "bone_meal"]
ORE = {"stickWood": "minecraft:stick", "logWood": "#minecraft:logs", "treeSapling": "#minecraft:saplings",
       "stone": "minecraft:stone", "dyeRed": "minecraft:red_dye", "ingotGold": "minecraft:gold_ingot",
       "ingotBrick": "minecraft:brick", "blockEmerald": "minecraft:emerald_block", "dustGlowstone": "minecraft:glowstone_dust",
       "slimeball": "minecraft:slime_ball", "ingotIron": "minecraft:iron_ingot", "gemDiamond": "minecraft:diamond",
       "plankWood": "#minecraft:planks", "dustRedstone": "minecraft:redstone", "cobblestone": "minecraft:cobblestone"}
# Each mod's own items, by the field its recipes name them by, with the count a named stack carries.
OWN = {
    # Touhou Items Mod
    "THKaguyaItems.hourai_Jeweled_branch": "hourai_jeweled_branch", "THKaguyaItems.dragon_neck_jewel": "dragon_neck_jewel",
    "THKaguyaItems.buddha_stone_bowl": "buddha_stone_bowl", "THKaguyaItems.fire_rat_robe": "fire_rat_robe",
    "THKaguyaItems.swallow_cowrie_shell": "swallow_cowrie_shell", "THKaguyaItems.kinkakuji": "kinkakuji",
    "THKaguyaItems.aja_red_stone": "aja_red_stone", "THKaguyaItems.hakurei_miko_stick": "hakurei_gohei",
    "THKaguyaItems.homing_amulet": ("homing_amulet", 16), "THKaguyaItems.diffusion_amulet": ("diffusion_amulet", 16),
    "THKaguyaItems.yin_yang_orb": "yin_yang_orb", "THKaguyaItems.bloodthirsty_yin_yang_orb": "bloodthirsty_yin_yang_orb",
    "THKaguyaItems.magic_bloom": "magic_broom", "THKaguyaItems.mini_hakkero": "mini_hakkero", "THKaguyaItems.marisa_hat": "marisa_hat",
    "THKaguyaItems.icicle_sword": "icicle_sword", "THKaguyaItems.silver_knife_blue": ("silver_knife_blue", 4),
    "THKaguyaItems.silver_knife_red": ("silver_knife_red", 2), "THKaguyaItems.silver_knife_green": ("silver_knife_green", 2),
    "THKaguyaItems.silver_knife_white": "silver_knife_white", "THKaguyaItems.sakuya_watch": "sakuya_watch",
    "THKaguyaItems.sakuya_stopwatch": "sakuya_stopwatch", "THKaguyaItems.gungnir": "spear_the_gungnir",
    "THKaguyaItems.laevateinn": "laevateinn", "THKaguyaItems.cursedDecoyDoll": "cursed_decoy_doll",
    "THKaguyaItems.hakurouken": "hakurouken", "THKaguyaItems.roukanken": "roukanken", "THKaguyaItems.yuyuko_fan": "yuyuko_fan",
    "THKaguyaItems.soulTorch": "soul_torch", "THKaguyaItems.gap": "gap", "THKaguyaItems.gapFoldingUmbrella": "gap_folding_umbrella",
    "THKaguyaItems.ibuki_gourd": "ibuki_gourd", "THKaguyaItems.yuuka_parasol": "yuuka_parasol",
    "THKaguyaItems.death_scythe": "death_scythe", "THKaguyaItems.remorse_rod": "kaigo_stick", "THKaguyaItems.tengu_fan": "tengu_fan",
    "THKaguyaItems.kappa_cap": "kappa_cap", "THKaguyaItems.kappa_water_pistol": "kappa_water_pistol",
    "THKaguyaItems.wind_miko_stick": "miko_stick", "THKaguyaItems.illness_recovery_charm": "illness_charm",
    "THKaguyaItems.onbashira": "onbashira", "THKaguyaItems.suwako_hat": "suwako_hat", "THKaguyaItems.heavenly_peach": "heavenly_peach",
    "THKaguyaItems.hisou_sword": "hisou_sword", "THKaguyaItems.third_eye": "third_eye",
    "THKaguyaItems.nuclear_control_rod": "nuclear_control_rod", "THKaguyaItems.closed_third_eye": "closed_third_eye",
    "THKaguyaItems.nazrin_pendulum": "nazrin_pendulum", "THKaguyaItems.ship_ghost_dipper_empty": "ship_ghost_dipper_empty",
    "THKaguyaItems.ship_ghost_dipper_fill": "ship_ghost_dipper", "THKaguyaItems.sorcerer_sutra_scroll": "sorcerer_sutra_scroll",
    "THKaguyaItems.wall_passing_chisel": "wall_passing_chisel", "THKaguyaItems.toyosatomimi_sword": "toyosatomimi_sword",
    "THKaguyaItems.miracle_mallet": "miracle_mallet", "THKaguyaItems.spiritual_strike_talisman": "spiritual_strike_talisman",
    "THKaguyaItems.shot_material": "shot_material", "THKaguyaItems.power_item": "small_power_item",
    "THKaguyaBlocks.danmaku_crafting_table": "danmaku_crafting_table", "THKaguyaItems.power_up_item_small": "small_power_item",
    "THKaguyaItems.power_up_item_big": "big_power_item", "THKaguyaItems.point_item": "point_item",
    "THKaguyaItems.bomb_item": "bomb_item", "THKaguyaItems.extend_item": "extend_item",
    "THKaguyaItems.middle_laser": "middle_laser", "THKaguyaItems.short_laser": "short_laser", "THKaguyaItems.long_laser": "long_laser",
    "THKaguyaBlocks.danmaku_crafting_table_shot": "danmaku_crafting_table", "THKaguyaBlocks.danmaku_crafting_table_laser": "laser_crafting_table",
    # SPELLCARD PLUS
    "spellcardplusmodItems.HoshigumaDish": "hoshiguma_dish", "spellcardplusmodItems.InstantHinaDoll": "instant_hina_doll",
    "spellcardplusmodItems.FloatingHinaDoll": "floating_hina_doll", "spellcardplusmodItems.Yin_yang_orb_Yukari": "yin_yang_orb_yukari",
    "spellcardplusmodItems.Stockpilingmisfortune": "stockpiling_misfortune",
    # Journey To Gensokyo
    "JTGBlock.keyStoneBlock": "keystone",
    # Grimoire of Alice
    "GOAItem.volatileString": "volatile_string", "GOAItem.soldifiedPaper": "soldified_paper", "GOAItem.gloriousNipponSteel": "tamahagane",
    "GOAItem.shimenawaRope": "shimenawa_rope", "GOAItem.youkaiBook": "youkai_book", "GOAItem.mask": "mask",
    "GOAItem.Hihiirokane": "hihiirokane", "GOAItem.ibarakiBoxEmpty": "ibaraki_box_empty", "GOAItem.impureRock": "impure_rock",
    "GOAItem.shroomSlice": "shroom_slice", "GOAItem.grilledLamprey": "grilled_lamprey", "GOAItem.ibarakiBoxFilled": "ibaraki_box",
    "GOAItem.kappasNostrum": "kappas_nostrum", "GOAItem.foxMask": "fox_mask", "GOAItem.raidenMask": "raiden_mask",
    "GOAItem.nonkeyMask": "monkey_mask", "GOAItem.hyottokoMask": "hyottoko_mask", "GOAItem.fukuNoKamiMask": "fuku_no_kami_mask",
    "GOAItem.ubaMask": "uba_mask", "GOAItem.hannyaMask": "hannya_mask", "GOAItem.koomoteMask": "koomote_mask",
    "GOAItem.maskOfHope": "mask_of_hope", "GOAItem.kokorosMasks": "kokoros_masks", "GOAItem.primordialShield": "primordial_shield",
    "GOAItem.momijisMapleLeafShield": "maple_leaf_shield", "GOAItem.mochiHammer": "mochi_hammer",
    "GOAItem.momijisScimitarSword": "momiji_scimitar", "GOAItem.laevatein": "goa_laevatein", "GOAItem.nazrinStick": "nazrin_stick",
    "GOAItem.ellyScythe": "elly_scythe", "GOAItem.mikoStick": "goa_miko_stick", "GOAItem.crestOfYggdrasill": "crest_of_yggdrasill",
    "GOAItem.amenonuhoko": "amenonuhoko", "GOAItem.needle": "sukuna_needle", "GOAItem.NueTrident": "nue_trident",
    "GOAItem.swordOfKusanagi": "sword_of_kusanagi", "GOAItem.enchantedBook": "goa_enchanted_book", "GOAItem.grimoireBook": "grimoire_book",
    "GOABlock.holyKeyStone": "holy_key_stone", "GOABlock.sugarBlock": "sugar_block", "GOABlock.ropeBlock": "rope_block",
    "GOABlock.paperBlock": "paper_block", "GOABlock.onbashira": "onbashira_pillar", "GOABlock.holyStone": "holy_stone",
    "GOABlock.compactStone": "compact_stone", "GOABlock.hyperconcentratedMagic": "hyperconcentrated_magic",
    "GOABlock.shroom": "shroom", "GOABlock.kyoumarubotan": "kyoumarubotan",
}
for c in ("red", "blue", "green", "yellow", "purple", "aqua", "orange", "white"):
    OWN[f"THKaguyaItems.{c}_pearl"] = f"{c}_pearl"
SHOT_COUNTS = {"tiny": 1, "small": 1, "medium": 2, "big": 3, "star": 1, "small_star": 5, "circle": 3, "scale": 4, "butterfly": 2,
               "light": 1, "knife": 2, "heart": 2, "kunai": 3, "talisman": 2, "big_light": 1, "rice": 2, "oval": 2, "crystal": 2,
               "arrow": 1}
for s, n in SHOT_COUNTS.items():
    java = "bigLight" if s == "big_light" else s
    OWN[f"THKaguyaItems.{java}_shot"] = (f"{s}_shot", n)
JTG_META = {  # (field, damage) -> ours
    ("JTGItem.gensokyoIngotItem", 0): "gensokium_ingot", ("JTGItem.gensokyoIngotItem", 1): "makaiium_ingot",
    ("JTGItem.gensokyoIngotItem", 2): "celestium_ingot", ("JTGItem.gensokyoDustItem", 0): "gensokium_dust",
    ("JTGItem.gensokyoDustItem", 1): "makaiium_dust", ("JTGItem.gensokyoDustItem", 2): "celestium_dust",
    ("JTGBlock.gensokyoOreBlock", 0): "gensokium_ore", ("JTGBlock.gensokyoOreBlock", 1): "makaiium_ore",
    ("JTGBlock.gensokyoOreBlock", 2): "celestium_ore", ("JTGItem.oldGensokyoSpellItem", 0): "old_gensokyo_spellcard",
    ("JTGItem.oldGensokyoSpellItem", 1): "old_demon_spellcard", ("JTGItem.oldGensokyoSpellItem", 2): "old_celestial_spellcard",
    **{("JTGItem.gensokyoNotesItem", i): f"gensokyo_notes_{n}" for i, n in
       enumerate(("ruined", "patched", "dusty", "normal", "imbued", "arcane"))},
}
CARD_BY_NUMBER = {c[2]: c[0] for c in CARDS}
CARD_BY_NUMBER.update({c["number"]: c["item"] for c in translated if c["mod"] == "kaguya"})
CARD_BY_CLASS = {c["class"]: c["item"] for c in translated}


class Skip(Exception):
    pass


def split_top(s):
    """`s` split at its top-level commas."""
    parts, depth, cur, quote = [], 0, "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def resolve(expr, ingredient=True):
    """A Java item expression as `(id or tag or list, count)`."""
    e = re.sub(r"\s+", "", expr)
    count, damage = 1, None
    m = re.fullmatch(r"newItemStack\((.*)\)", e)
    if m:
        args = split_top(m.group(1))
        e = args[0]
        if len(args) > 1:
            count = int(args[1])
        if len(args) > 2:
            damage = int(args[2])
    if e.startswith('"'):
        name = e.strip('"')
        if name not in ORE:
            raise Skip(f"ore name {name}")
        return ORE[name], count
    m = re.fullmatch(r"THKaguyaItems\.getSpellCardForId\((\d+)\)", e)
    if m:
        n = int(m.group(1))
        if n not in CARD_BY_NUMBER:
            raise Skip(f"spell card {n}")
        return f"{NS}:{CARD_BY_NUMBER[n]}", count
    if e.startswith("spellcardplusmodItems.") and "THSC_" + e.split(".", 1)[1] in CARD_BY_CLASS:
        return f"{NS}:{CARD_BY_CLASS['THSC_' + e.split('.', 1)[1]]}", count
    if (e, damage or 0) in JTG_META:
        return f"{NS}:{JTG_META[(e, damage or 0)]}", count
    if e in OWN:
        v = OWN[e]
        if isinstance(v, tuple):
            v, n = v
            if not m:
                count = n
        return f"{NS}:{v}", count
    if e == "Items.field_151100_aR":
        if damage is None:
            return [f"minecraft:{d}" for d in DYES], count
        return f"minecraft:{DYES[damage]}", count
    if e == "Items.field_151068_bn":
        if damage in (0, 16):  # a water bottle, an awkward potion: any potion stands in
            return "minecraft:potion", count
        raise Skip(f"potion {damage}")
    if e in VANILLA and VANILLA[e]:
        return f"minecraft:{VANILLA[e]}", count
    raise Skip(e)


def result(expr):
    item, count = resolve(expr, ingredient=False)
    if not isinstance(item, str) or item.startswith("#"):
        raise Skip(f"result {expr}")
    r = {"id": item}
    if count != 1:
        r["count"] = count
    return r


recipes, skipped = {}, []


def add(key, recipe):
    rid = re.sub(r"[^a-z0-9_]", "_", recipe["result"]["id"].split(":")[1] if "result" in recipe else key)
    base, i = rid, 2
    while rid in recipes:
        rid, i = f"{base}_{i}", i + 1
    recipes[rid] = recipe


def shaped(out_expr, items):
    rows, keys, i = [], {}, 0
    while i < len(items) and items[i].startswith('"'):
        rows.append(items[i].strip('"'))
        i += 1
    while i + 1 < len(items):
        ch = items[i].strip("'")
        keys[ch], _ = resolve(items[i + 1])
        i += 2
    width = max(len(r) for r in rows)
    rows = [r.ljust(width) for r in rows]
    used = {c for r in rows for c in r if c != " "}
    return {"type": "minecraft:crafting_shaped", "category": "misc", "pattern": rows,
            "key": {k: v for k, v in keys.items() if k in used}, "result": result(out_expr)}


def shapeless(out_expr, items):
    return {"type": "minecraft:crafting_shapeless", "category": "misc",
            "ingredients": [resolve(x)[0] for x in items], "result": result(out_expr)}


def smelting(args):
    xp = float(args[2].rstrip("Ff")) if len(args) > 2 else 0.1
    return {"type": "minecraft:smelting", "category": "misc", "ingredient": resolve(args[0])[0], "result": result(args[1]),
            "experience": xp, "cookingtime": 200}


def calls(text, name):
    for m in re.finditer(rf"GameRegistry\.{name}\(", text):
        depth, j = 1, m.end()
        while depth:
            depth += text[j] == "("
            depth -= text[j] == ")"
            j += 1
        yield text[m.end():j - 1]


def flat(args):
    """`out, new Object[]{a, b}` or `out, a, b` as `out, [a, b]`."""
    rest = args[1:]
    if len(rest) == 1 and re.match(r"new Object\[\]\s*\{", rest[0]):
        rest = split_top(rest[0][rest[0].index("{") + 1:rest[0].rindex("}")])
    return args[0], rest


def gameregistry(path):
    text = path.read_text(errors="replace")
    for body in calls(text, "addRecipe") :
        try:
            o, items = flat(split_top(body))
            add(o, shaped(o, items))
        except (Skip, ValueError, IndexError) as e:
            skipped.append(f"{path.name}: {str(e)[:70]}")
    for body in calls(text, "addShapelessRecipe"):
        try:
            o, items = flat(split_top(body))
            add(o, shapeless(o, items))
        except (Skip, ValueError, IndexError) as e:
            skipped.append(f"{path.name}: {str(e)[:70]}")
    for body in calls(text, "addSmelting"):
        try:
            add("smelt", dict(smelting(split_top(body)), _smelt=True))
        except (Skip, ValueError, IndexError) as e:
            skipped.append(f"{path.name}: {str(e)[:70]}")


def grimoire(path):
    """Grimoire of Alice's recipe builders: `shaped().grid(..).where('X').mapsTo(..)...outputs(..).build()`."""
    text = path.read_text(errors="replace")
    helper = re.search(r"private static ShapedRecipe mask\(\)\s*\{\s*return new ShapedRecipe\(\)(.*?);\s*\}", text, re.S)
    text = text.replace("mask()", "shaped()" + (helper.group(1) if helper else ""))
    for m in re.finditer(r"(shaped|shapeless)\(\)(.*?)\.build\(\);", text, re.S):
        chain = m.group(2)
        try:
            out_expr = split_top(re.search(r"\.outputs\((.*)\)\s*$", chain, re.S).group(1))[0]
            if m.group(1) == "shaped":
                grid = split_top(re.search(r"\.grid\((.*?)\)\s*\.", chain, re.S).group(1))
                keys = []
                for w in re.finditer(r"\.where\('(.)'\)\s*\.mapsTo\(((?:[^()]|\([^()]*(?:\([^()]*\))?[^()]*\))*)\)", chain):
                    keys += [f"'{w.group(1)}'", w.group(2)]
                add(out_expr, shaped(out_expr, grid + keys))
            else:
                adds = re.findall(r"\.add\(((?:[^()]|\([^()]*\))*)\)", chain)
                add(out_expr, shapeless(out_expr, adds))
        except (Skip, ValueError, IndexError, AttributeError) as e:
            skipped.append(f"{path.name}: {str(e)[:70]}")
    for body in calls(text, "addSmelting"):
        try:
            add("smelt", dict(smelting(split_top(body)), _smelt=True))
        except (Skip, ValueError, IndexError) as e:
            skipped.append(f"{path.name}: {str(e)[:70]}")


gameregistry(SRC / "kaguya" / "thKaguyaMod" / "init" / "THKaguyaRecipe.java")
gameregistry(SRC / "spellcard" / "spellcardplusmod" / "init" / "spellcardplusmodRecipe.java")
gameregistry(SRC / "jtg" / "katrix" / "journeyToGensokyo" / "item" / "crafting" / "CraftingVanilla.java")
grimoire(SRC / "grimoire" / "arekkuusu" / "grimoireOfAlice" / "item" / "crafting" / "VanillaCrafting.java")
# The hand-written ones in gen_content win: the Mochi Hammer's own shape stays.
recipes.pop("mochi_hammer", None)
# Not crafted: the character weapons, what they wear, their treasures and tools, and every spell
# card. They are found, not made; the Mochi Hammer (gen_content's) is the one weapon with a recipe.
UNCRAFTABLE = {
    "amenonuhoko", "crest_of_yggdrasill", "death_scythe", "elly_scythe", "goa_laevatein", "goa_miko_stick",
    "hakurei_gohei", "hakurouken", "hisou_sword", "icicle_sword", "kaigo_stick", "laevateinn",
    "miko_stick", "miracle_mallet", "momiji_scimitar", "nazrin_stick", "nue_trident", "onbashira",
    "roukanken", "spear_the_gungnir", "sukuna_needle", "sword_of_kusanagi", "toyosatomimi_sword", "yuuka_parasol",
    "buddha_stone_bowl", "maple_leaf_shield", "primordial_shield", "silver_knife_blue", "silver_knife_green", "silver_knife_red",
    "fox_mask", "fuku_no_kami_mask", "hannya_mask", "hyottoko_mask", "kappa_cap", "kokoros_masks",
    "koomote_mask", "marisa_hat", "mask_of_hope", "monkey_mask", "raiden_mask", "suwako_hat",
    "uba_mask", "fire_rat_robe", "yin_yang_orb_yukari", "mask", "aja_red_stone", "closed_third_eye",
    "third_eye", "diffusion_amulet", "homing_amulet", "dragon_neck_jewel", "gap", "hoshiguma_dish",
    "hourai_jeweled_branch", "ibaraki_box_empty", "ibuki_gourd", "instant_hina_doll", "kappa_water_pistol", "kinkakuji",
    "magic_broom", "mini_hakkero", "nazrin_pendulum", "nuclear_control_rod", "sakuya_watch", "ship_ghost_dipper",
    "sorcerer_sutra_scroll", "tengu_fan", "wall_passing_chisel", "yin_yang_orb", "youkai_book", "yuyuko_fan",
    "kappas_nostrum", "swallow_cowrie_shell",
}


def crafted(rid, r):
    out = r.get("result", {})
    name = (out.get("id") if isinstance(out, dict) else out or rid).split(":")[-1]
    return name not in UNCRAFTABLE and not name.startswith("spell_card_")


recipes = {rid: r for rid, r in recipes.items() if crafted(rid, r)}
for rid, r in recipes.items():
    smelt = r.pop("_smelt", False)
    write(od / "recipe" / f"{rid}{'_smelting' if smelt else ''}.json", r)
print(f"recipes: {len(recipes)} written, {len(skipped)} left out")
for s in skipped:
    print("  left out:", s)

MORE_TAB = more_tab
BLOCK_TAB = [f"{NS}:{b[0]}" for b in BLOCKS]
