// Export Champions-resolved static data from a local Pokémon Showdown build.
// Usage: node scripts/export_showdown.js <path-to-pokemon-showdown> <out-root>
// Writes <out-root>/<commit7>/{species,moves,items,abilities,typechart,natures,manifest}.json
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const [psDir, outRoot] = process.argv.slice(2);
if (!psDir || !outRoot) {
  console.error('usage: node export_showdown.js <pokemon-showdown dir> <out root>');
  process.exit(1);
}

const MOD = 'champions';
const { Dex } = require(path.resolve(psDir, 'dist', 'sim'));
const d = Dex.mod(MOD);

const commit = execSync('git rev-parse HEAD', { cwd: psDir }).toString().trim();
const commitDate = execSync('git log -1 --format=%cs', { cwd: psDir }).toString().trim();
const outDir = path.join(outRoot, commit.slice(0, 7));
if (fs.existsSync(outDir)) {
  console.error(`Refusing to overwrite existing raw folder: ${outDir}`);
  process.exit(1);
}
fs.mkdirSync(outDir, { recursive: true });

const species = d.species.all().filter(s => s.exists).map(s => ({
  id: s.id, name: s.name, num: s.num, baseSpecies: s.baseSpecies, forme: s.forme || null,
  isMega: !!s.isMega, types: s.types, baseStats: s.baseStats,
  abilities: Object.values(s.abilities), requiredItem: s.requiredItem || null,
  isNonstandard: s.isNonstandard || null, tier: s.tier || null,
}));

const moves = d.moves.all().filter(m => m.exists).map(m => ({
  id: m.id, name: m.name, type: m.type, category: m.category,
  basePower: m.basePower, accuracy: m.accuracy, // true = never misses
  priority: m.priority, target: m.target, isNonstandard: m.isNonstandard || null,
}));

const items = d.items.all().filter(i => i.exists).map(i => ({
  id: i.id, name: i.name, megaStone: i.megaStone || null, // {BaseSpecies: MegaForme}
  isNonstandard: i.isNonstandard || null,
}));

const abilities = d.abilities.all().filter(a => a.exists).map(a => ({
  id: a.id, name: a.name, isNonstandard: a.isNonstandard || null,
}));

// damageTaken codes: 0 = 1x, 1 = 2x, 2 = 0.5x, 3 = 0x. Non-type keys (brn, sandstorm...) kept raw.
const typechart = d.types.all().filter(t => t.exists).map(t => ({
  name: t.name, damageTaken: t.damageTaken, isNonstandard: t.isNonstandard || null,
}));

const natures = d.natures.all().map(n => ({ id: n.id, name: n.name, plus: n.plus || null, minus: n.minus || null }));

const formats = Dex.formats.all().filter(f => /champions/.test(f.id)).map(f => f.id);

const write = (name, obj) => fs.writeFileSync(path.join(outDir, `${name}.json`), JSON.stringify(obj, null, 1));
write('species', species);
write('moves', moves);
write('items', items);
write('abilities', abilities);
write('typechart', typechart);
write('natures', natures);
write('manifest', {
  source: 'pokemon-showdown', mod: MOD, commit, commit_date: commitDate,
  exported_at: new Date().toISOString(), champions_formats: formats,
  counts: { species: species.length, moves: moves.length, items: items.length,
            abilities: abilities.length, types: typechart.length, natures: natures.length },
});

const gz = species.find(s => s.id === 'garchompmegaz');
console.log(`Wrote ${outDir}`);
console.log(JSON.stringify(require(path.join(path.resolve(outDir), 'manifest.json')).counts));
console.log('garchompmegaz:', gz ? `${gz.types} spe=${gz.baseStats.spe} ${gz.abilities}` : 'MISSING');
console.log('VGC formats:', formats.filter(f => /vgc/.test(f)).join(', '));
