// Ground truth for the damage calculator, from the pinned Showdown build itself.
//
// Reading the source and reimplementing it is one interpretation; running the
// reference implementation is not. This drives vendor/pokemon-showdown's own
// simulator and reports every damage roll, so src/vgc/damage.py can be pinned
// against the thing it is modelling rather than against my reading of it.
//
// Usage: node scripts/showdown_damage.js <cases.json>
// Each case: {name, attacker:{species,evs,nature,item,ability}, defender:{...},
//             move, weather, spread}
'use strict';
const fs = require('fs');
const path = require('path');

const PS = path.resolve(__dirname, '..', 'vendor', 'pokemon-showdown');
const { Battle } = require(path.join(PS, 'dist', 'sim'));
const FORMAT = 'gen9championsvgc2026regmc';
const ROLLS = 16;

const FILLER = ['Ditto', 'Furret', 'Pidgey', 'Rattata'];

function set(spec, name) {
  return {
    name: name || spec.species,
    species: spec.species,
    item: spec.item || '',
    ability: spec.ability || '',
    moves: spec.moves || ['Tackle'],
    nature: spec.nature || 'Serious',
    evs: Object.assign({ hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 }, spec.evs || {}),
    level: 50,
  };
}

function filler(n) {
  return FILLER.slice(0, n).map(s => set({ species: s }));
}

// VGC formats open on team preview, so nothing is active until both sides choose.
function start(c) {
  const battle = new Battle({ formatid: FORMAT, seed: [1, 2, 3, 4], strictChoices: false });
  battle.setPlayer('p1', { name: 'A', team: [set(c.attacker), ...filler(3)] });
  battle.setPlayer('p2', { name: 'B', team: [set(c.defender), ...filler(3)] });
  if (battle.requestState === 'teampreview') {
    battle.makeChoices('team 1234', 'team 1234');
  }
  return battle;
}

function rollsFor(c) {
  const out = [];
  for (let roll = 0; roll < ROLLS; roll++) {
    const battle = start(c);
    const source = battle.p1.active[0];
    const target = battle.p2.active[0];
    // setWeather refuses without a source; the attacker stands in for the setter.
    if (c.weather) battle.field.setWeather(c.weather, source);
    // randomizer() asks for random(16); pin it so each roll is reproducible.
    battle.random = (m) => (m === ROLLS ? roll : 0);

    const move = battle.dex.getActiveMove(c.move);
    if (c.spread) move.spreadHit = true;

    const dmg = battle.actions.getDamage(source, target, move);
    out.push(typeof dmg === 'number' ? dmg : 0);
  }
  return out;
}

function main() {
  const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const results = cases.map(c => {
    const rolls = rollsFor(c);
    const probe = start(c);
    const d = probe.p2.active[0];
    return Object.assign({}, c, {
      rolls: rolls.slice().sort((x, y) => x - y),
      defender_hp: d.maxhp,
      // getStat() already folds in item and ability stat modifiers -- Choice Band
      // shows as 300, not 200 -- so storedStats is reported alongside it. The Python
      // side starts from the raw figure and applies items itself, which is the only
      // way its item handling gets exercised rather than bypassed.
      defender_stats: { def: d.getStat('def'), spd: d.getStat('spd') },
      defender_stats_raw: { def: d.storedStats.def, spd: d.storedStats.spd },
      attacker_stats: {
        atk: probe.p1.active[0].getStat('atk'),
        spa: probe.p1.active[0].getStat('spa'),
      },
      attacker_stats_raw: {
        atk: probe.p1.active[0].storedStats.atk,
        spa: probe.p1.active[0].storedStats.spa,
      },
    });
  });
  process.stdout.write(JSON.stringify(results, null, 2) + '\n');
}

main();
