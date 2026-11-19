//! Touhou Items Mod (Itutu no Nandai MOD+, by kuro-anco) for Horizon: danmaku and spell cards.
//! A port for personal use; the original's art is in the content mod `thkaguyamod`.
//!
//! Danmaku are not entities here. The server keeps every shot of a level, moves it as
//! `EntityTHShot` did and settles what it hits; each client is told a shot once, as it is fired,
//! runs the same motion and draws it facing the camera. Spell cards are scripts the server runs a
//! tick at a time for whoever cast them.
//!
//! The Giga Torch (`torch.rs`) is Torchmaster's Mega Torch, by Xalcon (MIT), brought in here.

mod cards;
mod gen_info;
#[cfg(test)]
mod gen_test;
#[rustfmt::skip]
#[allow(non_camel_case_types, non_snake_case, unused)]
mod gen_cards;
mod items;
mod pattern;
mod rt;
mod shot;
mod torch;
mod vec;

use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};

use horizon_client::mod_api::{
    BlockEntityEvent, BlockEntityTickEvent, BlockEntityTicksEvent, ClientLevelUnloadEvent, ClientTickPostEvent, Compound,
    DestroyBlockEvent, EntityJoinLevelEvent, Flow, Hooks, Host, HurtEnemyEvent, InventoryTickEvent, LevelTickPostEvent,
    LivingEntityUseItemFinishEvent, NativeServerPlayer, NetFromServerEvent, PlaceBlockEvent, PotentialSpawnsEvent,
    ReleaseUsingEvent, RightClickBlockEvent, ServerTickEvent, Text, TooltipEvent, UseItemEvent, VillageSiegeEvent,
    WorldSubmitEvent,
};

use cards::{Actor, Card, Ctx, card_position};
use gen_info::GenInfo;
use rt::{Cx, EH, Ent, Hit, SH, World};
use pattern::Fire;
use shot::{Batch, Phase, Shot, form, laser, shot_full, special};
use vec::{Rng, V3, angle, v3};

pub fn hooks() -> Box<dyn Hooks> {
    Box::new(Mod)
}

struct Mod;

const CHANNEL: &str = "thkaguyamod_native:shots";
/// How far a spell card looks for its target, as `checkSpellCardDeclaration` did.
const TARGET_RANGE: f64 = 32.0;

// ---- The server's side ----

/// What a cast runs: a hand-ported card and its two numbers, or a translated one and its state
/// (made at its first tick, as its constructor needs the world).
enum Script {
    Hand(Card, [f32; 2]),
    Gen(&'static GenInfo, Option<gen_cards::State>),
}

/// A spell card being cast.
struct Cast {
    script: Script,
    user: u128,
    user_entity: u32,
    dimension: String,
    time: i32,
    level: i32,
    /// Ticks it lasts: a translated card may change it (`setEndTime`).
    end: i32,
    target: Option<u32>,
    /// The target as last seen: once it dies a card goes on at it, as the original's keeps its
    /// `EntityLivingBase` (a script's `target != null` stays true).
    last_target: Option<Ent>,
    target_point: V3,
    card_pos: V3,
    card_yaw: f32,
}

struct Server {
    shots: HashMap<String, Vec<Shot>>,
    casts: Vec<Cast>,
    /// Shots fired by items between ticks, by level: the next tick sends them.
    queued: Vec<(String, Shot)>,
    next_id: u32,
    rng: Rng,
}

static SERVER: LazyLock<Mutex<Server>> = LazyLock::new(|| {
    let seed = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(1, |d| d.as_nanos() as u64);
    Mutex::new(Server { shots: HashMap::new(), casts: Vec::new(), queued: Vec::new(), next_id: 1, rng: Rng::new(seed) })
});

/// A limited card's id is its card's and this: the dolls' cards, of a few uses.
const LIMITED: &str = "_limited";
/// How many times a limited card casts.
pub const LIMITED_USES: u32 = 16;

/// A use off the limited card `used` in a hand of `player`; at its last, it is gone. While a player
/// acts the game holds their own slots swapped in (the equipment calls read a stale copy), so the
/// slot holding this very stack is changed where it is; the equipment is the fallback.
fn wear(host: &mut dyn Host, player: &NativeServerPlayer, used: &horizon_client::mod_api::ItemStack) {
    use horizon_client::mod_api::EquipmentSlot;
    let mut broke = None;
    for slot in (0..36).chain([-106]) {
        let Some(s) = host.carried_stack(slot) else { continue };
        if s.item == used.item && s.damage == used.damage && s.count > 0 {
            s.damage += 1;
            if s.damage >= LIMITED_USES {
                s.count = 0;
                broke = Some(true);
            } else {
                broke = Some(false);
            }
            break;
        }
    }
    if broke.is_none() {
        let Some(living) = host.entity(player.entity_id as u32).and_then(|e| host.living(e)) else { return };
        for slot in [EquipmentSlot::MainHand, EquipmentSlot::OffHand] {
            let Some(mut stack) = host.equipment(slot).filter(|s| s.item == used.item) else { continue };
            stack.damage += 1;
            let gone = stack.damage >= LIMITED_USES;
            host.living_set_equipment(living, slot, (!gone).then_some(stack));
            broke = Some(gone);
            break;
        }
    }
    if broke == Some(true)
        && let Some(l) = host.level(&player.dimension)
    {
        host.level_play_sound(l, "minecraft:entity.item.break", player.position, 7, 1.0, 1.0);
    }
}

/// Fires what `f` fires from an item, by entity `owner`, in `dimension`.
fn fire_now(dimension: &str, owner: u32, f: impl FnOnce(&mut Fire)) {
    let Ok(mut server) = SERVER.lock() else { return };
    let mut out = Vec::new();
    f(&mut Fire { out: &mut out, rng: &mut server.rng });
    for mut shot in out {
        shot.owner = owner;
        shot.by_player = true;
        shot.dirty = true;
        let shot = server.give_id(shot);
        server.queued.push((dimension.to_owned(), shot));
    }
}

/// A roll of 0 up to `n`, not counting it.
fn roll(n: u32) -> u32 {
    SERVER.lock().map_or(0, |mut s| s.rng.int(n))
}

fn actor(p: &NativeServerPlayer) -> Actor {
    Actor { pos: V3::from_array(p.position), eye_height: f64::from(p.eye_height), yaw: p.yaw, pitch: p.pitch }
}

/// Experience points in all, at `level` and `progress` into the next, as vanilla counts them.
fn total_xp(level: i32, progress: f32) -> i32 {
    let l = f64::from(level);
    let base = match level {
        ..=16 => l * l + 6.0 * l,
        17..=31 => 2.5 * l * l - 40.5 * l + 360.0,
        _ => 4.5 * l * l - 162.5 * l + 2220.0,
    };
    let next = match level {
        ..=15 => 2 * level + 7,
        16..=30 => 5 * level - 38,
        _ => 9 * level - 158,
    };
    (base + f64::from(progress) * f64::from(next)) as i32
}

/// Animals and villagers are no spell card's target, as in the original.
pub(crate) fn passive(kind: &str) -> bool {
    const PASSIVE: [&str; 28] = [
        "cow", "pig", "sheep", "chicken", "horse", "donkey", "mule", "rabbit", "villager", "wandering_trader", "cat",
        "wolf", "parrot", "fox", "bee", "axolotl", "goat", "llama", "turtle", "frog", "camel", "sniffer", "armadillo",
        "mooshroom", "ocelot", "panda", "polar_bear", "strider",
    ];
    let name = kind.rsplit(':').next().unwrap_or(kind);
    PASSIVE.contains(&name)
}

/// Where the segment from `a` along `d` (a unit vector, up to `reach`) enters the box, if it does.
fn ray_box(a: V3, d: V3, reach: f64, b: [[f64; 3]; 2]) -> Option<f64> {
    let (mut near, mut far) = (0.0f64, reach);
    for (o, v, lo, hi) in [(a.x, d.x, b[0][0], b[1][0]), (a.y, d.y, b[0][1], b[1][1]), (a.z, d.z, b[0][2], b[1][2])] {
        if v.abs() < 1e-12 {
            if o < lo || o > hi {
                return None;
            }
        } else {
            let (t0, t1) = ((lo - o) / v, (hi - o) / v);
            near = near.max(t0.min(t1));
            far = far.min(t0.max(t1));
            if near > far {
                return None;
            }
        }
    }
    Some(near)
}

fn grow(b: [[f64; 3]; 2], by: f64) -> [[f64; 3]; 2] {
    [[b[0][0] - by, b[0][1] - by, b[0][2] - by], [b[1][0] + by, b[1][1] + by, b[1][2] + by]]
}

fn middle(b: [[f64; 3]; 2]) -> V3 {
    v3((b[0][0] + b[1][0]) / 2.0, (b[0][1] + b[1][1]) / 2.0, (b[0][2] + b[1][2]) / 2.0)
}

/// The living things of a level, with their boxes.
fn bodies(host: &mut dyn Host, dimension: &str) -> Vec<(u32, String, [[f64; 3]; 2])> {
    host.level_entities(dimension)
        .into_iter()
        .filter_map(|(id, kind, _)| {
            let e = host.entity(id)?;
            host.living(e)?;
            Some((id, kind, host.entity_bounding_box(e)?))
        })
        .collect()
}

/// The nearest living thing in the caster's sight, as the original picks a spell card's target.
fn find_target(host: &mut dyn Host, p: &NativeServerPlayer) -> Option<(u32, V3)> {
    let user = actor(p);
    let eye = user.pos + v3(0.0, user.eye_height, 0.0);
    let look = user.look();
    let all: Vec<_> = bodies(host, &p.dimension).into_iter().filter(|(id, kind, _)| *id != p.entity_id as u32 && !passive(kind)).collect();
    let looked_at = all
        .iter()
        .filter_map(|(id, _, b)| Some((ray_box(eye, look, TARGET_RANGE, grow(*b, 0.3))?, *id, *b)))
        .min_by(|a, b| a.0.total_cmp(&b.0))
        .map(|(_, id, b)| (id, middle(b)));
    looked_at.or_else(|| {
        // Not one exactly: the nearest to the line of sight within AIM_CONE, of the hostile ones
        // (no player, and no one's doll).
        all.iter()
            .filter(|(_, kind, _)| kind != "minecraft:player" && !kind.starts_with("alice_dolls:"))
            .filter_map(|(id, _, b)| {
                let to = middle(*b) - eye;
                let d = to.length();
                if !(0.5..=TARGET_RANGE).contains(&d) {
                    return None;
                }
                let cos = (to.x * look.x + to.y * look.y + to.z * look.z) / d;
                (cos >= AIM_CONE.cos()).then_some((cos, *id, *b))
            })
            .max_by(|a, b| a.0.total_cmp(&b.0))
            .map(|(_, id, b)| (id, middle(b)))
    })
}

/// How far off the line of sight (radians) a spell card still finds its target.
const AIM_CONE: f64 = 0.26;

pub(crate) fn passable(block: &str) -> bool {
    const SOFT: [&str; 30] = [
        "air", "water", "lava", "grass", "fern", "torch", "vine", "vines", "sapling", "rail", "button", "carpet", "sign",
        "kelp", "kelp_plant", "snow", "bush", "flower", "tulip", "poppy", "dandelion", "orchid", "allium", "bluet",
        "daisy", "cornflower", "lily_of_the_valley", "mushroom", "roots", "sprouts",
    ];
    let name = block.split('[').next().unwrap_or(block);
    SOFT.iter().any(|s| name.ends_with(s))
}

/// The face a shot moving `m` strikes first, as Minecraft numbers faces.
fn side_struck(m: V3) -> i32 {
    let (x, y, z) = (m.x.abs(), m.y.abs(), m.z.abs());
    if y >= x && y >= z {
        if m.y < 0.0 { 1 } else { 0 }
    } else if x >= z {
        if m.x < 0.0 { 5 } else { 4 }
    } else if m.z < 0.0 {
        3
    } else {
        2
    }
}

/// The engine's own block-hit specials (`EntityTHShot.blockHitSpecialProcess`): bouncing shots.
fn bounce(s: &mut Shot) -> bool {
    let (times, next) = match s.special {
        40 => (2, 0),
        41 => (3, 40),
        42 => (4, 41),
        43 => (9999, 43),
        _ => return false,
    };
    s.pos = s.prev;
    s.bound(0.9, times);
    s.special = next;
    s.dirty = true;
    true
}

impl Server {
    fn give_id(&mut self, mut shot: Shot) -> Shot {
        shot.id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1).max(1);
        shot
    }

    /// One tick of a level: shots move and hit, casts fire, helpers act. What clients must hear is
    /// returned.
    fn tick(&mut self, host: &mut dyn Host, dimension: &str) -> Batch {
        let mut batch = Batch::default();
        let has_shots = self.shots.get(dimension).is_some_and(|v| !v.is_empty());
        let has_queued = self.queued.iter().any(|(d, _)| d == dimension);
        let has_casts = self.casts.iter().any(|c| c.dimension == dimension);
        if !has_shots && !has_queued && !has_casts && rt::helpers_in(dimension).is_empty() {
            return batch;
        }
        let players = host.server_players();
        let level = host.level(dimension);
        let difficulty = level.and_then(|l| host.level_difficulty(l)).unwrap_or("normal");
        let bodies = if has_shots { bodies(host, dimension) } else { Vec::new() };
        let mut shots = self.shots.remove(dimension).unwrap_or_default();
        let mut i = 0;
        while i < self.queued.len() {
            if self.queued[i].0 == dimension {
                shots.push(self.queued.swap_remove(i).1);
            } else {
                i += 1;
            }
        }
        let seed = u64::from(self.rng.int(u32::MAX)) << 32 | u64::from(self.rng.int(u32::MAX));
        let mut w = World::new(host, dimension, shots, self.next_id);

        // Each shot moves, its card's script steering it where it has one; set lasers follow.
        let moving = w.shots.len();
        for i in 0..moving {
            if w.shots[i].frozen > 0 {
                let s = &mut w.shots[i];
                s.frozen -= 1;
                s.prev = s.pos;
                s.dirty = true;
                continue;
            }
            match w.shots[i].begin() {
                Phase::Gone => w.shots[i].dead = true,
                Phase::Waiting => {}
                Phase::Moving => {
                    let (sp, owner, by_player) = (w.shots[i].special, w.shots[i].owner, w.shots[i].by_player);
                    if gen_cards::owns_special(sp) || sp == rt::special::MUSOU {
                        let owner = w.ent(owner);
                        let mut cx = Cx::new(&mut w, owner, Ent::NONE, V3::ZERO, seed ^ i as u64);
                        cx.by_player = by_player;
                        if sp == rt::special::MUSOU {
                            rt::musou(&mut cx, SH::I(i));
                        } else {
                            gen_cards::special_move(&mut cx, sp, SH::I(i));
                        }
                    } else {
                        w.shots[i].special_motion();
                    }
                    if !w.shots[i].dead {
                        w.shots[i].finish();
                    }
                }
            }
            if w.shots[i].laser == laser::SET && !w.shots[i].dead {
                match rt::anchor_pos(&w, w.shots[i].anchor) {
                    Some(a) => {
                        let s = &mut w.shots[i];
                        let p = a + s.angle * s.set_length + v3(0.0, s.y_offset, 0.0);
                        if p != s.pos {
                            s.pos = p;
                            s.dirty = true;
                        }
                    }
                    None => w.shots[i].dead = true,
                }
            }
        }

        // What each hits: living things (never their own user, nor animals and villagers), then blocks.
        for i in 0..moving {
            let s = w.shots[i].clone();
            if s.dead || !s.solid() {
                continue;
            }
            let owns = gen_cards::owns_special(s.special);
            if s.laser != laser::NONE {
                let width = f64::from(s.size);
                let dir = rt::jnorm(s.angle);
                let start = s.pos + dir * width;
                let reach = (s.length - width).max(1e-6);
                for (id, kind, b) in &bodies {
                    if *id == s.owner || passive(kind) || ray_box(start, dir, reach, grow(*b, width)).is_none() {
                        continue;
                    }
                    if owns {
                        let (owner, target) = (w.ent(s.owner), w.ent(*id));
                        let mut cx = Cx::new(&mut w, owner, Ent::NONE, V3::ZERO, seed ^ i as u64);
                        let _ = gen_cards::special_hit_entity(&mut cx, s.special, SH::I(i), EH::Ent(target));
                    }
                    w.host.hurt_entity(dimension, *id, s.damage_for(s.by_player, difficulty), "minecraft:thrown", Some(s.owner));
                }
                continue;
            }
            let mut hit = false;
            if s.form != form::FAMILIAR {
                let travel = s.pos - s.prev;
                let reach = travel.length();
                let dir = if reach > 1e-9 { travel * (1.0 / reach) } else { v3(0.0, 1.0, 0.0) };
                for (id, kind, b) in &bodies {
                    if *id == s.owner || passive(kind) || ray_box(s.prev, dir, reach.max(1e-6), grow(*b, f64::from(s.size) * 0.5)).is_none() {
                        continue;
                    }
                    let keep = if owns {
                        let (owner, target) = (w.ent(s.owner), w.ent(*id));
                        let mut cx = Cx::new(&mut w, owner, Ent::NONE, V3::ZERO, seed ^ i as u64);
                        cx.by_player = s.by_player;
                        gen_cards::special_hit_entity(&mut cx, s.special, SH::I(i), EH::Ent(target)).unwrap_or(false)
                    } else {
                        if s.special == special::WIND
                            && let Some(e) = w.host.entity(*id)
                        {
                            let v = w.host.entity_velocity(e).unwrap_or([0.0; 3]);
                            let m = s.motion * 1.7;
                            w.host.entity_set_velocity(e, [v[0] + m.x, v[1] + m.y + 2.0, v[2] + m.z]);
                        }
                        false
                    };
                    w.host.hurt_entity(dimension, *id, s.damage_for(s.by_player, difficulty), "minecraft:thrown", Some(s.owner));
                    if !keep {
                        w.shots[i].dead = true;
                    }
                    hit = true;
                    break;
                }
            }
            if hit || w.shots[i].dead {
                continue;
            }
            let Some(l) = level else { continue };
            let at = [s.pos.x.floor() as i32, s.pos.y.floor() as i32, s.pos.z.floor() as i32];
            if !w.host.level_block(l, at).is_some_and(|b| !passable(&b)) {
                continue;
            }
            let keep = if owns {
                let owner = w.ent(s.owner);
                let h = Hit { present: true, entity: EH::None, side: side_struck(s.motion), at: s.pos, bx: at[0], by: at[1], bz: at[2] };
                let mut cx = Cx::new(&mut w, owner, Ent::NONE, V3::ZERO, seed ^ i as u64);
                cx.by_player = s.by_player;
                gen_cards::special_hit_block(&mut cx, s.special, SH::I(i), h).unwrap_or(false)
            } else {
                bounce(&mut w.shots[i])
            };
            if !keep {
                w.shots[i].dead = true;
            }
        }

        // The casts of this level fire.
        let mut casts = std::mem::take(&mut self.casts);
        let rng = &mut self.rng;
        casts.retain_mut(|cast| {
            if cast.dimension != dimension {
                return true;
            }
            let Some(p) = players.iter().find(|p| p.uuid == cast.user && p.dimension == dimension && p.health > 0.0) else {
                return false;
            };
            let mut target = None;
            if let Some(id) = cast.target {
                let e = w.ent(id);
                if e.present && e.living && !e.dead {
                    cast.target_point = v3(e.x, e.y + f64::from(e.height) / 2.0, e.z);
                    cast.last_target = Some(e);
                    target = Some(e);
                }
            }
            match &mut cast.script {
                Script::Hand(card, state) => {
                    let user = actor(p);
                    let ctx = Ctx {
                        time: cast.time,
                        level: cast.level,
                        user,
                        target: cast.target_point,
                        target_alive: target.is_some(),
                        card: cast.card_pos,
                        card_yaw: cast.card_yaw,
                    };
                    let mut fired = Vec::new();
                    card.tick(&ctx, state, &mut Fire { out: &mut fired, rng });
                    if *card == Card::PerfectFreeze && cast.time == 64 {
                        freeze(&mut w.shots, ctx.pos_user(), &mut fired, rng);
                    }
                    for mut s in fired {
                        s.id = w.give_id();
                        s.owner = cast.user_entity;
                        s.by_player = true;
                        s.card = true;
                        s.dirty = true;
                        w.shots.push(s);
                    }
                    if cast.time % 4 == 0 {
                        w.sounds.push(ctx.pos_user());
                    }
                }
                Script::Gen(info, state) => {
                    let user = w.ent(cast.user_entity);
                    let aim = target
                        .or(cast.last_target.map(|e| Ent { dead: true, ..e }))
                        .unwrap_or(Ent { x: cast.target_point.x, y: cast.target_point.y, z: cast.target_point.z, ..Ent::NONE });
                    let seed = u64::from(rng.int(u32::MAX));
                    let mut cx = Cx::new(&mut w, user, aim, cast.card_pos, seed);
                    cx.time = cast.time;
                    cx.level = cast.level;
                    cx.end = cast.end;
                    cx.need = info.need;
                    cx.number = info.number;
                    cx.by_player = true;
                    if state.is_none() {
                        *state = gen_cards::start(&mut cx, info.class);
                    }
                    let Some(st) = state.as_mut() else { return false };
                    gen_cards::tick(&mut cx, st);
                    if let Some(end) = cx.new_end {
                        cast.end = end;
                    }
                }
            }
            cast.time += 1;
            cast.time < cast.end
        });
        casts.append(&mut self.casts);
        self.casts = casts;

        rt::tick_helpers(&mut w, seed);

        // A sound for each place shots were fired from, a few a tick at most.
        let mut sounds: Vec<V3> = Vec::new();
        for p in std::mem::take(&mut w.sounds) {
            if sounds.len() < 4 && !sounds.iter().any(|q| (*q - p).length() < 2.0) {
                sounds.push(p);
            }
        }
        if let Some(l) = level {
            for p in sounds {
                w.host.level_play_sound(l, "minecraft:entity.arrow.shoot", p.array(), 7, 0.6, 1.2);
            }
        }

        // Clients hear of every shot new or changed, and of those gone before their time.
        let (shots, next_id) = w.finish();
        self.next_id = next_id;
        let mut kept = Vec::with_capacity(shots.len());
        for mut s in shots {
            if s.dead {
                if s.count <= s.end {
                    batch.gone.push(s.id);
                }
                continue;
            }
            if s.dirty {
                s.dirty = false;
                batch.fired.push(s.clone());
            }
            kept.push(s);
        }
        if !kept.is_empty() {
            self.shots.insert(dimension.to_owned(), kept);
        }
        rt::sweep_helpers();
        batch
    }
}

/// Perfect Freeze at its sixty-fourth tick: every shot within twenty blocks stops, turns white and
/// faces a random way, to set off again twenty ticks on.
fn freeze(shots: &mut [Shot], at: V3, fired: &mut Vec<Shot>, rng: &mut Rng) {
    for old in shots.iter_mut() {
        let d = old.pos - at;
        if old.dead || d.x.abs() > 20.0 || d.y.abs() > 20.0 || d.z.abs() > 20.0 {
            continue;
        }
        old.dead = true;
        let a = angle(rng.float() * 360.0, rng.float() * 180.0 - 90.0);
        let data = shot_full(old.form, 7, old.size, old.damage, 0, old.end - old.ticks + 50, special::FREEZE);
        fired.push(Shot::new(old.pos, a, 0.0, pattern::rotate_default(), 0.0, 9999, 1e-4, 1e-4, 0.0, V3::ZERO, data));
    }
}

// ---- The client's side: the shots it has been told of ----

static CLIENT: LazyLock<Mutex<HashMap<u32, Shot>>> = LazyLock::new(|| Mutex::new(HashMap::new()));

/// The colours the original tints its shots with (`RenderTHShot.colorR/G/B`).
const TINT: [[u8; 3]; 8] =
    [[224, 0, 0], [0, 0, 224], [0, 224, 0], [224, 224, 0], [224, 0, 224], [0, 224, 224], [255, 128, 0], [255, 255, 255]];

/// The sheet of eight colours a form is drawn from, if it is one of those.
fn strip(form: u8) -> Option<&'static str> {
    Some(match form {
        form::SMALL | form::TINY | form::MEDIUM => "thkaguyamod:entity/shot/small",
        form::PEARL => "thkaguyamod:entity/shot/pearl",
        form::CIRCLE => "thkaguyamod:entity/shot/circle",
        form::HEART => "thkaguyamod:entity/shot/heart",
        form::TALISMAN => "thkaguyamod:entity/shot/talisman",
        form::BIG => "thkaguyamod:entity/shot/big",
        _ => return None,
    })
}

const LIGHT: &str = "thkaguyamod:entity/shot/light";

fn draw_shot(host: &dyn Host, draw: &mut horizon_client::mod_api::NativeWorldDraw, s: &Shot, right: V3, up: V3) {
    let partial = f64::from(draw.partial);
    let at = s.prev.lerp(s.pos, partial);
    let color = usize::from(s.color % 8);
    let tint = TINT[color];
    // The light it flickers between, two frames.
    let frame = f32::from(u8::from(s.count.rem_euclid(2) == 1)) * 8.0;
    let light_uv = [frame, 0.0, frame + 8.0, 16.0];
    let mut quads: Vec<(&str, [f32; 4], f64, [u8; 4])> = Vec::with_capacity(2);
    if s.count < 0 {
        // Still appearing: a glow that grows.
        let grown = (f64::from((-s.count).min(10)) * 0.3 * f64::from(s.size)).min(1.0);
        quads.push((LIGHT, light_uv, grown, [tint[0], tint[1], tint[2], 128]));
    } else if let Some(sheet) = strip(s.form) {
        let u = color as f32 * 2.0;
        quads.push((sheet, [u, 0.0, u + 2.0, 16.0], f64::from(s.size), [255, 255, 255, 255]));
    } else {
        // Light shots, and for now every shape not yet drawn as its own: a tinted glow with a white core.
        let (outer, inner) = if matches!(s.form, form::LIGHT | form::BIG_LIGHT) { (2.0, 1.0) } else { (1.4, 0.7) };
        let size = f64::from(s.size);
        quads.push((LIGHT, light_uv, size * outer, [tint[0], tint[1], tint[2], 204]));
        quads.push((LIGHT, light_uv, size * inner, [255, 255, 255, 255]));
    }
    draw.push();
    if draw.translate_world(at.array()) {
        for (sprite, uv, half, rgba) in quads {
            let r = right * half;
            let u = up * half;
            let corner = |p: V3| [p.x as f32, p.y as f32, p.z as f32];
            let corners = [corner(-r + u), corner(-r - u), corner(r - u), corner(r + u)];
            host.world_quad(draw, sprite, corners, uv, rgba);
        }
    }
    draw.pop();
}

/// A laser: a beam of its colour, a white core down its middle, from where it is along the way it
/// faces, as long as it has grown, turned about its length to face the camera.
fn draw_laser(host: &dyn Host, draw: &mut horizon_client::mod_api::NativeWorldDraw, s: &Shot, forward: V3) {
    if s.length <= 0.01 {
        return;
    }
    let partial = f64::from(draw.partial);
    let at = s.prev.lerp(s.pos, partial);
    let d = rt::jnorm(s.angle);
    let side = rt::cross(d, forward);
    let side = if side.length() < 1e-6 { rt::cross(d, v3(0.0, 1.0, 0.0)) } else { side };
    let side = rt::jnorm(side);
    let end = d * s.length;
    // Form 3 and above are the Master Spark's sort: white light.
    let tint = if s.form >= 3 { [255, 255, 255] } else { TINT[usize::from(s.color % 8)] };
    let width = f64::from(s.size.max(0.05));
    // Still appearing: a thin line where it will be.
    let grown = if s.count < 0 { 0.15 } else { 1.0 };
    let corner = |p: V3| [p.x as f32, p.y as f32, p.z as f32];
    draw.push();
    if draw.translate_world(at.array()) {
        for (half, rgba) in [(width * grown, [tint[0], tint[1], tint[2], 170]), (width * 0.45 * grown, [255, 255, 255, 230])] {
            let r = side * half;
            let corners = [corner(-r), corner(-r + end), corner(r + end), corner(r)];
            host.world_quad(draw, LIGHT, corners, [4.0, 4.0, 4.0, 12.0], rgba);
        }
    }
    draw.pop();
}

impl Hooks for Mod {
    /// A spell card, used: cast it at whatever living thing is in sight, if its user can pay.
    fn use_item(&self, host: &mut dyn Host, event: &mut UseItemEvent<'_>) -> Flow {
        let limited = event.stack.item.strip_prefix("thkaguyamod:").and_then(|i| i.strip_suffix(LIMITED));
        let translated = event
            .stack
            .item
            .strip_prefix("thkaguyamod:")
            .map(|i| i.strip_suffix(LIMITED).unwrap_or(i))
            .and_then(|i| gen_info::GEN.iter().find(|g| g.item == i));
        let (name, need_level, end, script) = match (Card::by_item(&event.stack.item), translated) {
            (Some(card), _) => {
                let info = card.info();
                (info.name, info.need_level, info.end, Script::Hand(card, [0.0; 2]))
            }
            (None, Some(g)) => (g.name, g.need, g.end, Script::Gen(g, None)),
            (None, None) => return items::use_item(host, &event.stack.item),
        };
        let Some(player) = host.acting_player() else { return Flow::Continue };
        let Ok(mut server) = SERVER.lock() else { return Flow::Continue };
        if server.casts.iter().any(|c| c.user == player.uuid) {
            host.action_bar(player.uuid, Text::literal("A spell card is already declared"));
            return Flow::Cancel;
        }
        let creative = player.game_mode == 1;
        let Some((target, target_point)) = find_target(host, &player) else {
            host.action_bar(player.uuid, Text::literal(format!("{name}: no target in sight")));
            return Flow::Cancel;
        };
        if !creative {
            if player.xp_level < need_level {
                host.action_bar(player.uuid, Text::literal(format!("{name} needs {need_level} levels")));
                return Flow::Cancel;
            }
            let level = player.xp_level - need_level;
            let progress = player.xp_progress;
            host.set_player_status(player.uuid, None, None, Some((level, progress, total_xp(level, progress))));
        }
        let user = actor(&player);
        let target = Some(target);
        server.casts.push(Cast {
            script,
            user: player.uuid,
            user_entity: player.entity_id as u32,
            dimension: player.dimension.clone(),
            time: 0,
            level: 2,
            end,
            target,
            last_target: None,
            target_point,
            card_pos: card_position(&user),
            card_yaw: user.yaw,
        });
        drop(server);
        host.action_bar(player.uuid, Text::literal(name));
        if let Some(l) = host.level(&player.dimension) {
            host.level_play_sound(l, "minecraft:entity.illusioner.cast_spell", player.position, 7, 1.0, 1.0);
        }
        if limited.is_some() && !creative {
            wear(host, &player, event.stack);
        }
        Flow::Cancel
    }

    fn hurt_enemy(&self, host: &mut dyn Host, event: &mut HurtEnemyEvent<'_>) {
        items::hurt_enemy(host, &event.stack.item, event.entity, event.kind);
    }

    fn release_using(&self, host: &mut dyn Host, event: &mut ReleaseUsingEvent<'_>) {
        if items::release(host, &event.stack.item, event.entity, event.time_left) {
            event.used = true;
        }
    }

    fn living_entity_use_item_finish(&self, host: &mut dyn Host, event: &mut LivingEntityUseItemFinishEvent<'_>) {
        if let Some(p) = event.entity.and_then(|id| host.server_players().into_iter().find(|p| p.entity_id == id)) {
            items::eaten(host, &event.stack.item, p.uuid);
        }
    }

    fn inventory_tick(&self, host: &mut dyn Host, event: &mut InventoryTickEvent) {
        items::carried(host, event.slot, event.selected);
    }

    fn level_tick_post(&self, host: &mut dyn Host, event: &mut LevelTickPostEvent<'_>) {
        items::tick(host, event.dimension);
        let batch = match SERVER.lock() {
            Ok(mut server) => server.tick(host, event.dimension),
            Err(_) => return,
        };
        if batch.fired.is_empty() && batch.gone.is_empty() {
            return;
        }
        let messages = batch.encode(30_000);
        for p in host.server_players() {
            if p.dimension != event.dimension {
                continue;
            }
            for m in &messages {
                let _ = host.net_send_to_player(p.uuid, CHANNEL, m);
            }
        }
    }

    fn net_from_server(&self, _host: &mut dyn Host, event: &mut NetFromServerEvent<'_>) {
        if event.channel != CHANNEL {
            return;
        }
        let batch = Batch::decode(event.data);
        if let Ok(mut shots) = CLIENT.lock() {
            for id in batch.gone {
                shots.remove(&id);
            }
            for mut s in batch.fired {
                if let Some(old) = shots.get(&s.id) {
                    s.prev = old.pos;
                }
                shots.insert(s.id, s);
            }
        }
    }

    fn client_tick_post(&self, _host: &mut dyn Host, _event: &mut ClientTickPostEvent) {
        if let Ok(mut shots) = CLIENT.lock() {
            shots.retain(|_, s| s.step());
        }
    }

    fn client_level_unload(&self, _host: &mut dyn Host, _event: &mut ClientLevelUnloadEvent<'_>) {
        if let Ok(mut shots) = CLIENT.lock() {
            shots.clear();
        }
    }

    fn world_submit(&self, host: &dyn Host, event: &mut WorldSubmitEvent<'_>) {
        let Ok(shots) = CLIENT.lock() else { return };
        if shots.is_empty() {
            return;
        }
        let Some(camera) = host.camera() else { return };
        let yaw = f64::from(camera.yaw).to_radians();
        let forward = angle(camera.yaw, camera.pitch);
        let right = v3(-yaw.cos(), 0.0, -yaw.sin());
        let up = v3(
            right.y * forward.z - right.z * forward.y,
            right.z * forward.x - right.x * forward.z,
            right.x * forward.y - right.y * forward.x,
        );
        for s in shots.values() {
            if s.laser == laser::NONE {
                draw_shot(host, event.draw, s, right, up);
            } else {
                draw_laser(host, event.draw, s, forward);
            }
        }
    }

    // ---- The Giga Torch (torch.rs) ----

    fn place_block(&self, host: &mut dyn Host, event: &mut PlaceBlockEvent<'_>) {
        torch::place_block(host, event);
    }

    fn destroy_block(&self, host: &mut dyn Host, event: &mut DestroyBlockEvent) -> Flow {
        torch::destroy_block(host, event);
        Flow::Continue
    }

    fn block_entity(&self, _: &mut dyn Host, event: &mut BlockEntityEvent<'_>) -> Option<(String, Compound)> {
        torch::block_entity(event)
    }

    fn block_entity_ticks(&self, _: &dyn Host, event: &mut BlockEntityTicksEvent<'_>) {
        torch::block_entity_ticks(event);
    }

    fn block_entity_tick(&self, host: &mut dyn Host, event: &mut BlockEntityTickEvent<'_>) {
        torch::block_entity_tick(host, event);
    }

    fn server_tick(&self, host: &mut dyn Host, event: &mut ServerTickEvent<'_>) {
        torch::server_tick(host, event);
    }

    fn potential_spawns(&self, host: &dyn Host, event: &mut PotentialSpawnsEvent<'_>) -> Flow {
        torch::potential_spawns(host, event);
        Flow::Continue
    }

    fn entity_join_level(&self, host: &mut dyn Host, event: &mut EntityJoinLevelEvent<'_>) -> Flow {
        torch::entity_join_level(host, event)
    }

    fn village_siege(&self, host: &mut dyn Host, event: &mut VillageSiegeEvent<'_>) -> Flow {
        torch::village_siege(host, event)
    }

    fn right_click_block(&self, host: &mut dyn Host, event: &mut RightClickBlockEvent) -> Flow {
        torch::right_click_block(host, event);
        Flow::Continue
    }

    fn tooltip(&self, _: &dyn Host, event: &mut TooltipEvent<'_>) {
        if let Some(line) = torch::tooltip_for(&event.stack.item) {
            event.lines.push((Text::legacy(&format!("§7{line}")), u32::MAX));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn experience_adds_up_as_vanilla_counts_it() {
        assert_eq!(total_xp(0, 0.0), 0);
        assert_eq!(total_xp(16, 0.0), 352);
        assert_eq!(total_xp(30, 0.0), 1395);
        assert_eq!(total_xp(1, 0.5), 7 + 4);
    }

    #[test]
    fn a_ray_finds_the_box_in_its_way() {
        let b = [[-0.5, 0.0, 4.0], [0.5, 2.0, 5.0]];
        assert!((ray_box(v3(0.0, 1.0, 0.0), v3(0.0, 0.0, 1.0), 32.0, b).unwrap() - 4.0).abs() < 1e-9);
        assert!(ray_box(v3(0.0, 1.0, 0.0), v3(1.0, 0.0, 0.0), 32.0, b).is_none());
        assert!(ray_box(v3(0.0, 1.0, 0.0), v3(0.0, 0.0, 1.0), 3.0, b).is_none());
    }

    #[test]
    fn soft_blocks_let_shots_through() {
        for b in ["minecraft:air", "minecraft:cave_air", "minecraft:water", "minecraft:short_grass", "minecraft:torch", "minecraft:poppy"] {
            assert!(passable(b), "{b}");
        }
        for b in ["minecraft:stone", "minecraft:oak_planks", "minecraft:grass_block", "minecraft:glass"] {
            assert!(!passable(b), "{b}");
        }
    }

    #[test]
    fn animals_are_never_targets() {
        assert!(passive("minecraft:cow"));
        assert!(passive("minecraft:villager"));
        assert!(!passive("minecraft:zombie"));
        assert!(!passive("minecraft:player"));
    }
}
