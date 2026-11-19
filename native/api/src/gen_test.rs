//! Every translated card cast from start to end against a stand-in world, its shots moved and made
//! to hit, to find any that panic.

use crate::gen_cards;
use crate::gen_info::{GEN, GenInfo};
use crate::rt::{self, Cx, EH, Ent, Hit, SH, World};
use crate::shot::{Phase, Shot, laser};
use crate::vec::v3;
use horizon_client::mod_api::*;

const DIM: &str = "minecraft:overworld";

/// A flat world of stone below y 60 holding a player (1) and a zombie (2).
struct Fake;

fn epoch() -> NativeWorldEpoch {
    NativeWorldEpoch::new(1)
}

impl Host for Fake {
    fn server_players(&self) -> Vec<NativeServerPlayer> {
        Vec::new()
    }
    fn level(&self, _: &str) -> Option<LevelRef> {
        Some(LevelRef::new(epoch(), DIM))
    }
    fn level_difficulty(&self, _: LevelRef) -> Option<&'static str> {
        Some("normal")
    }
    fn level_entities(&mut self, _: &str) -> Vec<(u32, String, [f64; 3])> {
        vec![(1, "minecraft:player".into(), [0.0, 60.0, 0.0]), (2, "minecraft:zombie".into(), [0.0, 60.0, 8.0])]
    }
    fn entity(&self, id: u32) -> Option<EntityRef> {
        (id == 1 || id == 2).then(|| EntityRef::new(epoch(), id))
    }
    fn entity_position(&self, e: EntityRef) -> Option<[f64; 3]> {
        Some(if e.id() == 1 { [0.0, 60.0, 0.0] } else { [0.0, 60.0, 8.0] })
    }
    fn entity_rotation(&self, _: EntityRef) -> Option<[f32; 2]> {
        Some([0.0, 0.0])
    }
    fn entity_bounding_box(&self, e: EntityRef) -> Option<[[f64; 3]; 2]> {
        let p = self.entity_position(e)?;
        Some([[p[0] - 0.3, p[1], p[2] - 0.3], [p[0] + 0.3, p[1] + 1.8, p[2] + 0.3]])
    }
    fn entity_kind(&self, e: EntityRef) -> Option<String> {
        Some(if e.id() == 1 { "minecraft:player" } else { "minecraft:zombie" }.into())
    }
    fn living(&self, e: EntityRef) -> Option<LivingRef> {
        Some(LivingRef::new(e))
    }
    fn entity_velocity(&self, _: EntityRef) -> Option<[f64; 3]> {
        Some([0.0; 3])
    }
    fn entity_eye_height(&self, _: EntityRef) -> Option<f64> {
        Some(1.62)
    }
    fn entity_is_in_water(&self, _: EntityRef) -> Option<bool> {
        Some(false)
    }
    fn entity_is_crouching(&self, _: EntityRef) -> Option<bool> {
        Some(false)
    }
    fn entity_on_ground(&self, _: EntityRef) -> Option<bool> {
        Some(true)
    }
    fn entity_uuid(&mut self, e: EntityRef) -> Option<u128> {
        Some(u128::from(e.id()))
    }
    fn level_block(&self, _: LevelRef, p: [i32; 3]) -> Option<String> {
        Some(if p[1] < 60 { "minecraft:stone" } else { "minecraft:air" }.into())
    }
    fn hurt_entity(&mut self, _: &str, _: u32, _: f32, _: &str, _: Option<u32>) -> bool {
        true
    }
    fn level_play_sound(&mut self, _: LevelRef, _: &str, _: [f64; 3], _: usize, _: f32, _: f32) -> bool {
        true
    }
    fn run_command(&mut self, _: &str) -> bool {
        true
    }
    fn entity_set_velocity(&mut self, _: EntityRef, _: [f64; 3]) -> bool {
        true
    }
    fn entity_push(&mut self, _: EntityRef, _: [f64; 3]) -> bool {
        true
    }
    fn kill_mob(&mut self, _: &str, _: u32) -> bool {
        true
    }
    fn teleport_player(&mut self, _: u128, _: &str, _: [f64; 3], _: f32, _: f32) -> bool {
        true
    }
    fn entity_teleport_to(&mut self, _: EntityRef, _: [f64; 3], _: Option<[f32; 2]>) -> bool {
        true
    }
}

/// Casts `g` at level `level` and runs on until its shots are gone (or a while after). Returns how
/// many shots it had at most.
fn cast(g: &'static GenInfo, level: i32, seed: u64) -> usize {
    let mut host = Fake;
    let user = Ent {
        id: 1,
        present: true,
        x: 0.0,
        y: 60.0,
        z: 0.0,
        eye: 1.62,
        height: 1.8,
        width: 0.6,
        health: 20.0,
        max_health: 20.0,
        living: true,
        player: true,
        on_ground: true,
        ..Ent::NONE
    };
    let mut shots: Vec<Shot> = Vec::new();
    let mut next_id = 1;
    let mut state = None;
    let mut end = g.end;
    let mut most = 0;
    let mut t = 0;
    while t < end.min(3000) + 400 {
        let mut w = World::new(&mut host, DIM, shots, next_id);
        let tick_seed = seed ^ (t as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15);
        for i in 0..w.shots.len() {
            if w.shots[i].frozen > 0 {
                w.shots[i].frozen -= 1;
                continue;
            }
            match w.shots[i].begin() {
                Phase::Gone => w.shots[i].dead = true,
                Phase::Waiting => {}
                Phase::Moving => {
                    let (sp, owner) = (w.shots[i].special, w.shots[i].owner);
                    if gen_cards::owns_special(sp) || sp == rt::special::MUSOU {
                        let owner = w.ent(owner);
                        let mut cx = Cx::new(&mut w, owner, Ent::NONE, v3(0.0, 0.0, 0.0), tick_seed ^ i as u64);
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
            if w.shots[i].laser == laser::SET && !w.shots[i].dead && rt::anchor_pos(&w, w.shots[i].anchor).is_none() {
                w.shots[i].dead = true;
            }
        }
        // Every few ticks each scripted shot strikes the zombie and the ground.
        if t % 5 == 0 {
            for i in 0..w.shots.len() {
                let s = w.shots[i].clone();
                if s.dead || !gen_cards::owns_special(s.special) {
                    continue;
                }
                let owner = w.ent(s.owner);
                let zombie = w.ent(2);
                let mut cx = Cx::new(&mut w, owner, Ent::NONE, v3(0.0, 0.0, 0.0), tick_seed ^ i as u64);
                let keep = if (t / 5 + i as i32) % 2 == 0 {
                    gen_cards::special_hit_entity(&mut cx, s.special, SH::I(i), EH::Ent(zombie))
                } else {
                    let h = Hit { present: true, entity: EH::None, side: 1, at: s.pos, bx: s.pos.x.floor() as i32, by: 59, bz: s.pos.z.floor() as i32 };
                    gen_cards::special_hit_block(&mut cx, s.special, SH::I(i), h)
                };
                if keep == Some(false) {
                    w.shots[i].dead = true;
                }
            }
        }
        if t < end {
            let target = w.ent(2);
            let mut cx = Cx::new(&mut w, user, target, v3(0.0, 61.0, 1.5), tick_seed);
            cx.time = t;
            cx.level = level;
            cx.end = end;
            cx.need = g.need;
            cx.number = g.number;
            cx.by_player = true;
            if state.is_none() {
                state = gen_cards::start(&mut cx, g.class);
                assert!(state.is_some(), "{} has no script", g.class);
            }
            gen_cards::tick(&mut cx, state.as_mut().unwrap());
            if let Some(e) = cx.new_end {
                end = e;
            }
        }
        rt::tick_helpers(&mut w, tick_seed);
        let (s, n) = w.finish();
        shots = s.into_iter().filter(|s| !s.dead).collect();
        next_id = n;
        rt::sweep_helpers();
        most = most.max(shots.len());
        assert!(shots.len() < 20_000, "{} made {} shots", g.class, shots.len());
        for s in &shots {
            assert!(s.pos.x.is_finite() && s.pos.y.is_finite() && s.pos.z.is_finite(), "{} put a shot at {:?}", g.class, s.pos);
        }
        if t >= end && shots.is_empty() {
            break;
        }
        t += 1;
    }
    most
}

#[test]
fn every_translated_card_runs() {
    let mut failed = Vec::new();
    for g in GEN {
        for (level, seed) in [(1, 7), (2, 99), (4, 12345)] {
            let r = std::panic::catch_unwind(|| cast(g, level, seed));
            match r {
                Ok(n) if level == 2 => println!("{:<28} {:>5} shots at most", g.class, n),
                Ok(_) => {}
                Err(e) => {
                    let why = e.downcast_ref::<String>().cloned().or_else(|| e.downcast_ref::<&str>().map(|s| s.to_string())).unwrap_or_default();
                    failed.push(format!("{} (level {level}): {why}", g.class));
                    break;
                }
            }
        }
    }
    assert!(failed.is_empty(), "{} cards failed:\n{}", failed.len(), failed.join("\n"));
}
