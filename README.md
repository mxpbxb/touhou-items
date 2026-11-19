# Touhou Items

The weapons, tools, blocks, spell cards and point items of **Touhou Items Mod** (Itutu no Nandai
MOD+, by kuro-anco), with the spell cards of **SPELLCARD PLUS** and **Journey To Gensokyo** (by
Katrix), and the weapons, blocks and point items of **Grimoire of Alice** (by Arekkuusu), brought to
[Horizon](https://playhorizon.dev).

Ported with the permission of the original creators. Their art and designs are theirs; this
repository holds the Horizon port's code and the tool that builds its content.

## Two parts

Install both from the release, then press Build in the launcher:

- **`thkaguyamod_native`** (`.hnmod`): the code. A native mod: it runs with your account's
  permissions, so the launcher asks before building it.
- **`thkaguyamod`** (`.hmod`): the items, their textures, the creative tabs and the danmaku sheets.

[Touhou Mobs](https://github.com/mxpbxb/touhou-mobs) drops the point and power items, and
[Alice Dolls Restringed](https://github.com/mxpbxb/alice-dolls-restringed)'s dolls take them as love.

## The items

Every weapon takes the enchantments a sword takes, at an enchanting table or an anvil.

- **Swords and staves:** Laevateinn (sets alight; right-click for a fan of fire), Icicle Sword
  (freezes), Hakurouken and Roukanken (hold and let go to dash; Roukanken cuts the undead deeply),
  Onbashira (heavy, hits again), Rod of Remorse, Sword of Hisou (learns the kind it struck),
  Spear the Gungnir (right-click: a line of light), Scythe of Death (right-click pulls, sneak pushes),
  the Hakurei and Wind Shrine Maiden Sticks (amulets; a gust), Yuuka's Parasol (float down while
  held), the Sacred Sword of Toyosatomimi and the Miracle Mallet (right-click: stronger for a while).
- **Grimoire of Alice's weapons:** the **Mochi Hammer** (craftable: two diamonds and an ancient debris over two
  sticks; it sends what it hits flying, and weighs you down while you hold it), Momiji's Scimitar, the Sword of Kusanagi, Nue's
  Trident, Elly's Scythe, Amenonuhoko, Nazrin's Dowsing Rod and the Shining Needle.
- **Held and let go:** the Mini-Hakkero (Master Spark), Tengu's Fan (a gust), the Nuclear Control
  Rod (a sun of a shot, and its kick).
- **Right-click:** the Homing and Diffusion Amulets, the Spiritual Strike Talisman, Yuyuko's Fan
  (butterflies), Kappa's Water Pistol, Sakuya's Stopwatch (time stops around you), the Ibuki Gourd
  (never runs dry), the Illness Recovery Charm.
- **Point items:** the Doll Point (four of Arcadian Dream's Max Point Items make one), Power and Big Power, Full Power, Extend (an extra life), Bomb (strikes
  everything around), Star, Faith, Cherry, the UFOs and the Time Orb; the Heavenly Peach.
- **Spell cards:** 71 cards from Touhou Items Mod, SPELLCARD PLUS and Journey To Gensokyo, each
  cast at what is in sight, for experience levels. As in the original, a card needs a target: look
  at a mob (or near one) to declare it; with none in sight it isn't cast, and costs nothing. Once
  declared it goes on at its target to the end, even after the target dies.
  A spell card does half the damage it did in the original. **Limited cards** (Stardust Reverie,
  Fantasy Seal, Agni Shine, Mesh of Light and Darkness, Flower Wind Moon and Tail Fin Slap) cast as their card does, levels and all, but wear out after 16 casts; the dolls of
  [Alice Dolls Restringed](https://github.com/mxpbxb/alice-dolls-restringed) give them for a bomb.
- **Shots and lasers:** the danmaku items fire their own shot, in a random colour; the lasers fire
  lines of light.
- **The rest of the items:** the Hoshiguma dishes, Hina's dolls, Journey To Gensokyo's ingots,
  dusts and notes, and Grimoire of Alice's masks (each gives an effect once you are levelled up
  enough), shields, foods and materials. The Fire-Rat Robe keeps you from burning, the Kappa Cap
  lets you breathe underwater.
- **Blocks:** the danmaku and laser crafting tables, the divine spirits, Grimoire of Alice's blocks
  and the Onbashira pillar, and Journey To Gensokyo's ores: gensokium in the Overworld, makaiium in
  the Nether and celestium in the End.
- **The Giga Torch:** Torchmaster's Mega Torch (by Xalcon, MIT). Placed, it stops monsters,
  phantoms, the Touhou Mobs and Arcadian Dream fairies, and village sieges, within 64 blocks.
  Craft it from a torch, two logs, two diamonds and four **Max Doll Points** (four Doll Points in
  a square make one).

About 190 of the originals' recipes are carried over, with the Mochi Hammer, Max Doll Point and Giga
Torch ones; everything is in the creative tabs (Items, Spell Cards and Blocks), and the point and
power items drop from Touhou Mobs.

## Building

`gen_content.py` builds the content mod from the original jars' art (not in this repository), with
`gen_more.py` (the remaining items, blocks, ores and recipes) and `gen_cards.json` (the translated
spell cards):

```
python3 gen_content.py <unpacked thKaguyaMod jar> content <unpacked Grimoire of Alice jar>
cargo horizon-mod build   # in content/
```

`extra/` holds the Giga Torch's and the Max Doll Point's art and Torchmaster's licence
(`LICENSE-Torchmaster.txt`), which the content mod carries too.

The native mod (`native/`) is built by the Horizon launcher (`native-build`), pinned to one Horizon
revision.

Touhou Project is by ZUN; this is a non-commercial fan work. No Minecraft code or assets are included.
