"""Builds the content mod `thkaguyamod` from Touhou Items Mod's own jar assets: the shot sheets the
native mod draws danmaku with, and an item for each spell card it can cast.

usage: gen_content.py <unpacked thKaguyaMod jar> <content mod folder> [<unpacked Grimoire of Alice jar>]

The Grimoire of Alice weapons and point items (by Arekkuusu) come from the third jar, when given.

Keep CARDS in step with `native/api/src/cards.rs`.
"""
import json
import shutil
import sys
from pathlib import Path

jar, out = Path(sys.argv[1]), Path(sys.argv[2])
grimoire = Path(sys.argv[3]) / "assets" / "grimoireofalice" / "textures" / "items" if len(sys.argv) > 3 else None
NS, VERSION = "thkaguyamod", "0.4.1"
src = jar / "assets" / NS / "textures"
if out.exists():
    shutil.rmtree(out)
oa, od = out / "assets" / NS, out / "data" / NS

# item id, icon, original number, needed level, English name (the original's en_US.lang)
CARDS = [
    ("spell_card_kasho_no_eimin", "Kasho_no_Eimin", 2, 3, 'Deadly Butterfly "Everlasting Nap"'),
    ("spell_card_meteonic_shower", "MeteonicShower", 3, 1, 'Star Sign "Meteonic Shower"'),
    ("spell_card_nami_to_tubu_no_kyoukai", "Nami_to_Tubu_no_Kyoukai", 4, 5, 'Boundary Sign "Boundary between Wave and Particle"'),
    ("spell_card_perfect_freeze", "PerfectFreeze", 9, 1, 'Freeze Sign "Perfect Freeze"'),
    ("spell_card_kerochan_fuuu_ni_makezu", "Kerochan_Fuuu_ni_Makezu", 13, 2, 'Native God "Kero-chan Braves the Wind and Rain"'),
    ("spell_card_moses_miracle", "Moses_no_Kiseki", 17, 2, "Sea Opening \"Moses's Miracle\""),
    ("spell_card_yasaka_no_kamikaze", "Yasaka_no_Kamikaze", 18, 3, "Great Miracle \"Yasaka's Divine Wind\""),
    ("spell_card_eternal_meek", "EternalMeek", 24, 2, 'Conjuring "Eternal Meek"'),
    ("spell_card_houka_kenran", "HoukaKenran", 29, 2, 'Flower Sign "Gorgeous Sweet Flower"'),
]

# The shot sheets: eight colours side by side, and the light shots' glow in two frames.
SHEETS = {
    "small": "SmallShot.png", "pearl": "PearlShot.png", "circle": "CircleShot.png", "heart": "HeartShot.png",
    "talisman": "TalismanShot.png", "big": "BigShot.png", "light": "MusouFuuin.png",
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def copy(a, b):
    b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a, b)


for name, file in SHEETS.items():
    copy(src / "shot" / file, oa / "textures" / "entity" / "shot" / f"{name}.png")

lang = {}
for item, icon, number, need, name in CARDS:
    lv = min(max(need, 1), 5)
    copy(src / "items" / "spellCard" / f"{icon}.png", oa / "textures" / "item" / "spell_card" / f"{icon.lower()}.png")
    write(od / "horizon" / "item" / f"{item}.json", {
        "template": "minecraft:paper",
        "max_stack_size": 16,
        "rarity": "rare",
        "components": {"minecraft:item_name": {"translate": f"item.{NS}.{item}"}},
    })
    write(oa / "items" / f"{item}.json", {"model": {"type": "minecraft:model", "model": f"{NS}:item/{item}"}})
    write(oa / "models" / "item" / f"{item}.json", {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": f"{NS}:item/spell_card/{icon.lower()}", "layer1": f"{NS}:item/spell_card/lv{lv}"},
    })
    lang[f"item.{NS}.{item}"] = name
for lv in range(1, 6):
    copy(src / "items" / "spellCard" / f"spellcard_lv{lv}.png", oa / "textures" / "item" / "spell_card" / f"lv{lv}.png")

# The character items. Only the Mochi Hammer has a recipe; the point and power items drop from the
# Touhou mobs; the rest are in the creative tab only.
# What each does is in `native/api/src/items.rs`.


def sword(damage, durability, speed=-2.4, extra=None):
    """A sword of the original's material: 4 + its damage, so the attribute adds that less the fist's 1."""
    c = {
        "minecraft:max_damage": durability,
        "minecraft:attribute_modifiers": [
            {"type": "minecraft:attack_damage", "id": "minecraft:base_attack_damage", "amount": damage - 1,
             "operation": "add_value", "slot": "mainhand"},
            {"type": "minecraft:attack_speed", "id": "minecraft:base_attack_speed", "amount": speed,
             "operation": "add_value", "slot": "mainhand"},
        ],
    }
    c.update(extra or {})
    return c


# Held down like a bow, and let go: an hour-long use that is never finished, with no sound of its own.
CHARGE = {"minecraft:consumable": {"consume_seconds": 3600.0, "animation": "bow", "has_consume_particles": False,
                                   "sound": "minecraft:intentionally_empty"}}
LEAVES = {"minecraft:tool": {"rules": [
    {"blocks": "#minecraft:leaves", "speed": 15.0, "correct_for_drops": True},
    {"blocks": "minecraft:cobweb", "speed": 15.0, "correct_for_drops": True},
], "damage_per_block": 1, "can_destroy_blocks_in_creative": False}}

# Takes the enchantments a sword takes, at an enchanting table or an anvil (see the tags below).
ENCHANT = {"minecraft:enchantable": {"value": 14}}


def weapon(components):
    c = dict(components)
    c.update(ENCHANT)
    return c


POINT = {"minecraft:max_stack_size": 64}
G = "grimoire:"  # a texture from Grimoire of Alice

# item id, texture, English name, template, components
ITEMS = [
    # Held and let go: Master Spark.
    ("mini_hakkero", "miniHakkero", "Mini-Hakkero", "minecraft:paper", weapon(CHARGE)),
    # Dropped by fairies and the other Touhou mobs; given to an Alice doll, it is favour.
    ("point_item", "material/THPointItem", "Point Item", "minecraft:paper", POINT),
    ("small_power_item", "material/SmallPowerUpItem", "Power Item", "minecraft:paper", POINT),
    ("big_power_item", "material/BigPowerUpItem", "Big Power Item", "minecraft:paper", POINT),
    ("extend_item", "material/ExtendItem", "Extend Item", "minecraft:paper", {"minecraft:max_stack_size": 16}),
    ("bomb_item", "material/BombItem", "Bomb Item", "minecraft:paper", {"minecraft:max_stack_size": 16}),
    ("star_item", G + "Star", "Star Item", "minecraft:paper", POINT),
    ("faith_item", G + "Faith", "Faith Item", "minecraft:paper", POINT),
    ("cherry_item", G + "Cherry", "Cherry Item", "minecraft:paper", POINT),
    ("full_power_item", G + "FullPower", "Full Power Item", "minecraft:paper", {"minecraft:max_stack_size": 16}),
    ("time_orb", G + "TimeOrb", "Time Orb", "minecraft:paper", {"minecraft:max_stack_size": 16}),
    ("ufo_red", G + "UFORed", "Red UFO", "minecraft:paper", POINT),
    ("ufo_blue", G + "UFOBlue", "Blue UFO", "minecraft:paper", POINT),
    ("ufo_green", G + "UFOGreen", "Green UFO", "minecraft:paper", POINT),
    ("heavenly_peach", "heavenlyPeach", "Heavenly Peach", "minecraft:apple", {
        "minecraft:food": {"nutrition": 2, "saturation": 1.2, "can_always_eat": True},
        "minecraft:max_stack_size": 64}),
    ("ibuki_gourd", "ibukihyou", "Ibuki Gourd", "minecraft:paper", {}),
    ("illness_charm", "ByoukiheiyuMamori", "Illness Recovery Charm", "minecraft:paper", {}),
    ("sakuya_stopwatch", "SakuyaStopWatch", "Sakuya's Stopwatch", "minecraft:paper", {}),
    ("homing_amulet", "homingAmulet", "Homing Amulet", "minecraft:paper", weapon({})),
    ("diffusion_amulet", "diffusionAmulet", "Diffusion Amulet", "minecraft:paper", weapon({})),
    ("spiritual_strike_talisman", "SpiritualStrikeTalisman", "Spiritual Strike Talisman", "minecraft:paper", weapon({})),
    ("yuyuko_fan", "yuyukoOugi", "Yuyuko's Fan", "minecraft:paper", weapon({})),
    ("kappa_water_pistol", "kappaWaterPistol", "Kappa's Water Pistol", "minecraft:paper", weapon({})),
    ("laevateinn", "Laevateinn", "Laevateinn", "minecraft:iron_sword", weapon(sword(7, 95))),
    ("icicle_sword", "IcicleSword", "Icicle Sword", "minecraft:iron_sword", weapon(sword(6, 30))),
    ("hakurouken", "hakurouken", "Hakurouken", "minecraft:iron_sword", weapon(sword(4, 100, extra=CHARGE))),
    ("roukanken", "roukanSword", "Roukanken", "minecraft:iron_sword", weapon(sword(7, 251, extra=CHARGE))),
    ("onbashira", "onbashira", "Onbashira", "minecraft:iron_sword", weapon(sword(8, 500, speed=-3.2))),
    ("kaigo_stick", "kaigoStick_0", "Rod of Remorse", "minecraft:iron_sword", weapon(sword(1, 16, extra={
        "minecraft:repairable": {"items": "minecraft:ink_sac"}}))),
    ("hisou_sword", "hisousword", "Sword of Hisou", "minecraft:iron_sword", weapon(sword(4, 200, extra=LEAVES))),
    ("spear_the_gungnir", "Gungnir", "Spear the Gungnir", "minecraft:iron_sword", weapon(sword(6, 95))),
    ("death_scythe", "deathScythe", "Scythe of Death", "minecraft:iron_sword", weapon(sword(6, 444, speed=-3.0))),
    ("hakurei_gohei", "HakureiOharaibou", "Hakurei Shrine Maiden Stick", "minecraft:iron_sword", weapon(sword(5, 250))),
    ("miko_stick", "mikoStick_S", "Wind Shrine Maiden Stick", "minecraft:iron_sword", weapon(sword(5, 250))),
    ("yuuka_parasol", "yuukaParasol", "Yuuka's Parasol", "minecraft:iron_sword", weapon(sword(6, 500))),
    ("toyosatomimi_sword", "toyosatomimiSword", "Sacred Sword of Toyosatomimi", "minecraft:iron_sword", weapon(sword(7, 300))),
    ("miracle_mallet", "UchidenoKoduchi", "Miracle Mallet", "minecraft:iron_sword", weapon(sword(5, 300, speed=-2.8))),
    ("tengu_fan", "tenguFan", "Tengu's Fan", "minecraft:paper", weapon(dict(CHARGE, **{"minecraft:max_damage": 40}))),
    ("nuclear_control_rod", "nuclearControlRod", "Nuclear Control Rod", "minecraft:paper",
     weapon(dict(CHARGE, **{"minecraft:max_damage": 36}))),
    # Grimoire of Alice's weapons: its "goldyron" swords are 4 + 3, its others 4 (made a little stronger here).
    ("mochi_hammer", G + "MochiHammer", "Mochi Hammer", "minecraft:iron_sword", weapon(sword(8, 1000, speed=-3.0))),
    ("momiji_scimitar", G + "MomijisScimitarSword", "Momiji's Scimitar", "minecraft:iron_sword", weapon(sword(7, 1000))),
    ("sword_of_kusanagi", G + "SwordofKusanagi", "Sword of Kusanagi", "minecraft:iron_sword", weapon(sword(7, 1000, extra=LEAVES))),
    ("nue_trident", G + "NueTrident", "Nue's Trident", "minecraft:iron_sword", weapon(sword(6, 1000, speed=-2.8))),
    ("elly_scythe", G + "EllyScythe", "Elly's Scythe", "minecraft:iron_sword", weapon(sword(6, 1000, speed=-3.0))),
    ("amenonuhoko", G + "Amenonuhoko", "Amenonuhoko", "minecraft:iron_sword", weapon(sword(6, 1000, speed=-2.8))),
    ("nazrin_stick", G + "NazrinStick", "Nazrin's Dowsing Rod", "minecraft:iron_sword", weapon(sword(4, 1000))),
    ("sukuna_needle", G + "Needle", "Shining Needle", "minecraft:iron_sword", weapon(sword(4, 1000, speed=-1.6))),
]
if grimoire is None:
    ITEMS = [i for i in ITEMS if not i[1].startswith(G)]
for item, texture, name, template, components in ITEMS:
    folder = src / "items"
    if texture.startswith(G):
        folder, texture = grimoire, texture[len(G):]
    copy(folder / f"{texture}.png", oa / "textures" / "item" / f"{item}.png")
    meta = folder / f"{texture}.png.mcmeta"
    if meta.exists():
        copy(meta, oa / "textures" / "item" / f"{item}.png.mcmeta")
    comps = {"minecraft:item_name": {"translate": f"item.{NS}.{item}"}}
    comps.update(components)
    write(od / "horizon" / "item" / f"{item}.json", {
        "template": template, "max_stack_size": comps.pop("minecraft:max_stack_size", 1), "rarity": "rare",
        "components": comps,
    })
    write(oa / "items" / f"{item}.json", {"model": {"type": "minecraft:model", "model": f"{NS}:item/{item}"}})
    write(oa / "models" / "item" / f"{item}.json", {"parent": "minecraft:item/handheld", "textures": {"layer0": f"{NS}:item/{item}"}})
    lang[f"item.{NS}.{item}"] = name
lang[f"itemGroup.{NS}.items"] = "Touhou Items"

# Every weapon takes a sword's enchantments; the ones that are swords count as swords.
weapons = [i[0] for i in ITEMS if "minecraft:enchantable" in i[4]]
swords = [i[0] for i in ITEMS if i[0] in weapons and i[3] == "minecraft:iron_sword"]
for tag, members in {
    "swords": swords,
    "enchantable/sword": weapons,
    "enchantable/sharp_weapon": weapons,
    "enchantable/melee_weapon": weapons,
    "enchantable/weapon": weapons,
    "enchantable/fire_aspect": weapons,
    "enchantable/durability": weapons,
    "enchantable/vanishing": weapons,
}.items():
    write(out / "data" / "minecraft" / "tags" / "item" / f"{tag}.json",
          {"replace": False, "values": [f"{NS}:{m}" for m in members]})

# The Mochi Hammer: Grimoire of Alice's shape, with two diamonds and a brick for its head.
if grimoire is not None:
    write(od / "recipe" / "mochi_hammer.json", {
        "type": "minecraft:crafting_shaped", "category": "equipment",
        "pattern": ["DBD", " S ", " S "],
        "key": {"D": "minecraft:diamond", "B": "minecraft:brick", "S": "minecraft:stick"},
        "result": {"id": f"{NS}:mochi_hammer"},
    })
write(od / "horizon" / "creative_tab" / "items.json", {
    "title": "Touhou Items", "icon": f"{NS}:{ITEMS[0][0]}", "items": [f"{NS}:{i[0]}" for i in ITEMS],
})

lang[f"itemGroup.{NS}.spell_cards"] = "Touhou Items: Spell Cards"
write(oa / "lang" / "en_us.json", lang)
write(od / "horizon" / "creative_tab" / "spell_cards.json", {
    "title": "Touhou Items: Spell Cards", "icon": f"{NS}:{CARDS[3][0]}", "items": [f"{NS}:{c[0]}" for c in CARDS],
})
(out / "horizon-mod.toml").write_text(f'''id = "{NS}"
name = "Touhou Items Mod (assets)"
version = "{VERSION}"
description = "The art and items of the Horizon port of Touhou Items Mod (Itutu no Nandai MOD+, by kuro-anco), with weapons and point items from Grimoire of Alice (by Arekkuusu). Needs thkaguyamod_native."
authors = ["kuro-anco (Touhou Items Mod)", "Arekkuusu (Grimoire of Alice)", "mxpbxb (Horizon port)"]
api = "0.2"
side = "both"
capabilities = ["registries"]
''', encoding="utf-8")
print("built", out)
