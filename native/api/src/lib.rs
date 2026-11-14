//! Touhou Items Mod (Itutu no Nandai MOD+, by kuro-anco) for Horizon: danmaku and spell cards.
//! A port for personal use; the original's art is in the content mod `thkaguyamod`.
//!
//! Danmaku are not entities here. The server keeps every shot of a level, moves it as
//! `EntityTHShot` did and settles what it hits; each client is told a shot once, as it is fired,
//! runs the same motion and draws it facing the camera. Spell cards are scripts the server runs a
//! tick at a time for whoever cast them.

mod cards;
mod items;
mod pattern;
mod shot;
mod vec;

use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};

use horizon_client::mod_api::{
    ClientLevelUnloadEvent, ClientTickPostEvent, Flow, Hooks, Host, HurtEnemyEvent, InventoryTickEvent,
    LevelTickPostEvent, LivingEntityUseItemFinishEvent, NativeServerPlayer, NetFromServerEvent, ReleaseUsingEvent, Text,
    UseItemEvent, WorldSubmitEvent,
};

use cards::{Actor, Card, Ctx, card_position};
use pattern::Fire;
use shot::{Batch, Shot, form, shot_full, special};
use vec::{Rng, V3, angle, v3};

pub fn hooks() -> Box<dyn Hooks> {
    Box::new(Mod)
}

struct Mod;

const CHANNEL: &str = "thkaguyamod_native:shots";
/// How far a spell card looks for its target, as `checkSpellCardDeclaration` did.
const TARGET_RANGE: f64 = 32.0;

// ---- The server's side ----

/// A shot in flight, and who fired it.
struct Live {
    shot: Shot,
    owner: u32,
    by_player: bool,
}

/// A spell card being cast.
struct Cast {
    card: Card,
    user: u128,
    user_entity: u32,
    dimension: String,
    time: i32,
    level: i32,
    target: Option<u32>,
    target_point: V3,
    card_pos: V3,
    card_yaw: f32,
    state: [f32; 2],
}

struct Server {
    shots: HashMap<String, Vec<Live>>,
    casts: Vec<Cast>,
    /// Shots fired by items between ticks, by level: the next tick sends them.
    queued: Vec<(String, Live)>,
    next_id: u32,
    rng: Rng,
}

static SERVER: LazyLock<Mutex<Server>> = LazyLock::new(|| {
    let seed = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map_or(1, |d| d.as_nanos() as u64);
    Mutex::new(Server { shots: HashMap::new(), casts: Vec::new(), queued: Vec::new(), next_id: 1, rng: Rng::new(seed) })
});

/// Fires what `f` fires from an item, by entity `owner`, in `dimension`.
fn fire_now(dimension: &str, owner: u32, f: impl FnOnce(&mut Fire)) {
    let Ok(mut server) = SERVER.lock() else { return };
    let mut out = Vec::new();
    f(&mut Fire { out: &mut out, rng: &mut server.rng });
    for shot in out {
        let shot = server.give_id(shot);
        server.queued.push((dimension.to_owned(), Live { shot, owner, by_player: true }));
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
fn passive(kind: &str) -> bool {
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
    bodies(host, &p.dimension)
        .into_iter()
        .filter(|(id, kind, _)| *id != p.entity_id as u32 && !passive(kind))
        .filter_map(|(id, _, b)| Some((ray_box(eye, look, TARGET_RANGE, grow(b, 0.3))?, id, b)))
        .min_by(|a, b| a.0.total_cmp(&b.0))
        .map(|(_, id, b)| (id, middle(b)))
}

fn passable(block: &str) -> bool {
    const SOFT: [&str; 30] = [
        "air", "water", "lava", "grass", "fern", "torch", "vine", "vines", "sapling", "rail", "button", "carpet", "sign",
        "kelp", "kelp_plant", "snow", "bush", "flower", "tulip", "poppy", "dandelion", "orchid", "allium", "bluet",
        "daisy", "cornflower", "lily_of_the_valley", "mushroom", "roots", "sprouts",
    ];
    let name = block.split('[').next().unwrap_or(block);
    SOFT.iter().any(|s| name.ends_with(s))
}

impl Server {
    fn give_id(&mut self, mut shot: Shot) -> Shot {
        shot.id = self.next_id;
        self.next_id = self.next_id.wrapping_add(1).max(1);
        shot
    }

    /// One tick of a level: shots move and hit, casts fire. What clients must hear is returned.
    fn tick(&mut self, host: &mut dyn Host, dimension: &str) -> Batch {
        let mut batch = Batch::default();
        let has_shots = self.shots.get(dimension).is_some_and(|v| !v.is_empty());
        let has_queued = self.queued.iter().any(|(d, _)| d == dimension);
        if !has_shots && !has_queued && !self.casts.iter().any(|c| c.dimension == dimension) {
            return batch;
        }
        let players = host.server_players();
        let level = host.level(dimension);
        if has_shots {
            let difficulty = level.and_then(|l| host.level_difficulty(l)).unwrap_or("normal");
            let bodies = bodies(host, dimension);
            let shots = self.shots.entry(dimension.to_owned()).or_default();
            let mut kept = Vec::with_capacity(shots.len());
            for mut live in shots.drain(..) {
                if !live.shot.step() {
                    continue;
                }
                let s = &live.shot;
                let mut hit = false;
                if s.solid() {
                    let travel = s.pos - s.prev;
                    let reach = travel.length();
                    let dir = if reach > 1e-9 { travel * (1.0 / reach) } else { v3(0.0, 1.0, 0.0) };
                    for (id, _, b) in &bodies {
                        if *id == live.owner {
                            continue;
                        }
                        if ray_box(s.prev, dir, reach.max(1e-6), grow(*b, f64::from(s.size) * 0.5)).is_some() {
                            host.hurt_entity(dimension, *id, s.damage_for(live.by_player, difficulty), "minecraft:thrown", Some(live.owner));
                            if s.special == special::WIND
                                && let Some(e) = host.entity(*id)
                            {
                                let v = host.entity_velocity(e).unwrap_or([0.0; 3]);
                                let m = s.motion * 1.7;
                                host.entity_set_velocity(e, [v[0] + m.x, v[1] + m.y + 2.0, v[2] + m.z]);
                            }
                            hit = true;
                            break;
                        }
                    }
                    if !hit
                        && let Some(l) = level
                    {
                        let at = [s.pos.x.floor() as i32, s.pos.y.floor() as i32, s.pos.z.floor() as i32];
                        hit = host.level_block(l, at).is_some_and(|b| !passable(&b));
                    }
                }
                if hit {
                    batch.gone.push(live.shot.id);
                } else {
                    kept.push(live);
                }
            }
            *shots = kept;
        }

        let mut casts = std::mem::take(&mut self.casts);
        casts.retain_mut(|cast| {
            if cast.dimension != dimension {
                return true;
            }
            let Some(p) = players.iter().find(|p| p.uuid == cast.user && p.dimension == dimension && p.health > 0.0) else {
                return false;
            };
            let user = actor(p);
            let mut target_alive = false;
            if let Some(id) = cast.target
                && let Some(e) = host.entity(id)
                && host.living(e).is_some()
                && let Some(b) = host.entity_bounding_box(e)
            {
                cast.target_point = middle(b);
                target_alive = true;
            }
            let ctx = Ctx {
                time: cast.time,
                level: cast.level,
                user,
                target: cast.target_point,
                target_alive,
                card: cast.card_pos,
                card_yaw: cast.card_yaw,
            };
            let mut fired = Vec::new();
            cast.card.tick(&ctx, &mut cast.state, &mut Fire { out: &mut fired, rng: &mut self.rng });
            if cast.card == Card::PerfectFreeze && cast.time == 64 {
                self.freeze(dimension, ctx.pos_user(), &mut fired, &mut batch.gone);
            }
            for s in fired {
                let s = self.give_id(s);
                batch.fired.push(s.clone());
                self.shots.entry(dimension.to_owned()).or_default().push(Live { shot: s, owner: cast.user_entity, by_player: true });
            }
            if cast.time == 0 || cast.time % 4 == 0 {
                if let Some(l) = level {
                    host.level_play_sound(l, "minecraft:entity.arrow.shoot", ctx.pos_user().array(), 7, 0.6, 1.2);
                }
            }
            cast.time += 1;
            cast.time < cast.card.info().end
        });
        casts.append(&mut self.casts);
        self.casts = casts;
        let mut i = 0;
        while i < self.queued.len() {
            if self.queued[i].0 == dimension {
                let (_, live) = self.queued.swap_remove(i);
                batch.fired.push(live.shot.clone());
                self.shots.entry(dimension.to_owned()).or_default().push(live);
            } else {
                i += 1;
            }
        }
        batch
    }

    /// Perfect Freeze at its sixty-fourth tick: every shot within twenty blocks stops, turns white and
    /// faces a random way, to set off again twenty ticks on.
    fn freeze(&mut self, dimension: &str, at: V3, fired: &mut Vec<Shot>, gone: &mut Vec<u32>) {
        let Some(shots) = self.shots.get_mut(dimension) else { return };
        let mut frozen = Vec::new();
        shots.retain(|live| {
            let d = live.shot.pos - at;
            let near = d.x.abs() <= 20.0 && d.y.abs() <= 20.0 && d.z.abs() <= 20.0;
            if near {
                frozen.push(live.shot.clone());
                gone.push(live.shot.id);
            }
            !near
        });
        for old in frozen {
            let a = angle(self.rng.float() * 360.0, self.rng.float() * 180.0 - 90.0);
            let data = shot_full(old.form, 7, old.size, old.damage, 0, old.end - old.ticks + 50, special::FREEZE);
            fired.push(Shot::new(old.pos, a, 0.0, pattern::rotate_default(), 0.0, 9999, 1e-4, 1e-4, 0.0, V3::ZERO, data));
        }
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

impl Hooks for Mod {
    /// A spell card, used: cast it at whatever living thing is in sight, if its user can pay.
    fn use_item(&self, host: &mut dyn Host, event: &mut UseItemEvent<'_>) -> Flow {
        let Some(card) = Card::by_item(&event.stack.item) else { return items::use_item(host, &event.stack.item) };
        let Some(player) = host.acting_player() else { return Flow::Continue };
        let info = card.info();
        let Ok(mut server) = SERVER.lock() else { return Flow::Continue };
        if server.casts.iter().any(|c| c.user == player.uuid) {
            host.action_bar(player.uuid, Text::literal("A spell card is already declared"));
            return Flow::Cancel;
        }
        let creative = player.game_mode == 1;
        if !creative {
            if player.xp_level < info.need_level {
                host.action_bar(player.uuid, Text::literal(format!("{} needs {} levels", info.name, info.need_level)));
                return Flow::Cancel;
            }
            let level = player.xp_level - info.need_level;
            let progress = player.xp_progress;
            host.set_player_status(player.uuid, None, None, Some((level, progress, total_xp(level, progress))));
        }
        let user = actor(&player);
        let (target, target_point) = match find_target(host, &player) {
            Some((id, at)) => (Some(id), at),
            None => (None, user.pos + v3(0.0, user.eye_height, 0.0) + user.look() * 16.0),
        };
        server.casts.push(Cast {
            card,
            user: player.uuid,
            user_entity: player.entity_id as u32,
            dimension: player.dimension.clone(),
            time: 0,
            level: 2,
            target,
            target_point,
            card_pos: card_position(&user),
            card_yaw: user.yaw,
            state: [0.0; 2],
        });
        host.action_bar(player.uuid, Text::literal(info.name));
        if let Some(l) = host.level(&player.dimension) {
            host.level_play_sound(l, "minecraft:entity.illusioner.cast_spell", player.position, 7, 1.0, 1.0);
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
            for s in batch.fired {
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
            draw_shot(host, event.draw, s, right, up);
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
