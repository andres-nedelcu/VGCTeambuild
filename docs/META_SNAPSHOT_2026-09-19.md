# M-C meta snapshot — 19 September 2026

**38 tournaments · 2,148 teams · events from 09-09 to 09-17.**
Tournament teamlists from Limitless; builds from Champions Battle Data (ranked ladder).

Two numbers to keep in mind while reading:

- **Top-cut = top 16 finishers**, which is 420 teams. Real, but a fifth of the full
  sample, so treat single-rank moves as noise and look for agreement across columns.
- **Winner stats are 38 teams.** One team is 2.6%. Everything in §4 and §5 is
  suggestive, not settled. I've flagged where it's thinnest.

The meta itself is now reasonably firm: **Rillaboom, Sneasler, Salamence-Mega and
Incineroar never move** in the top four under bootstrap resampling, by team or by
whole tournament. Below that it still shuffles.

---

## 1. Over- and under-performers

Usage is what people bring. The other columns are how those teams did.

### Bringing more than their share

| Pokémon | All teams | Weighted by wins | Top cut | Rank move |
|---|---|---|---|---|
| **Archaludon** | 10.7% | 13.4% | **15.2%** | 14 → 12 |
| **Floette-Mega** | 12.9% | 14.9% | **16.1%** | 13 → **9** |
| Sneasler | 48.9% | 50.5% | 52.6% | 2 → 2 |
| Salamence-Mega | 37.5% | 38.9% | 40.9% | 3 → 3 |
| Gholdengo | 18.8% | 21.5% | 20.4% | 8 → 7 |
| Arcanine-Hisui | 16.8% | 18.0% | 17.9% | 10 → 8 |

Archaludon and Floette-Mega rise on **every** measure. That consistency is what makes
them worth trusting more than a single top-cut jump.

### Bringing less than their share

| Pokémon | All teams | Weighted by wins | Top cut | Rank move |
|---|---|---|---|---|
| **Gardevoir-Mega** | 9.0% | 7.9% | **6.1%** | 18 → **25** |
| **Golisopod-Mega** | 17.2% | 15.8% | 15.1% | 9 → **13** |
| **Indeedee-F** | 20.0% | 17.8% | 15.9% | 7 → **10** |
| Milotic | 9.8% | 9.1% | 7.8% | 17 → 18 |

Gardevoir-Mega is the sharpest fall in the whole list — heavily brought, thinly
represented where it counts. Golisopod-Mega and Indeedee-F have both been consistent
under-performers across two refreshes now, on a sample that has since doubled.

**Caveat worth holding:** usage-vs-placement says nothing about *why*. Indeedee-F is
structural — it sets the terrain that turns Sneasler on — so a lower cut share may
mean the archetype is being out-piloted rather than that the Pokémon is bad.

---

## 2. The build cheat sheet

Top fourteen, most common item / ability / nature and the moves they actually run.

| Pokémon | Item | Ability · Nature | Moves |
|---|---|---|---|
| **Rillaboom** | Miracle Seed 56%, Life Orb 12% | Grassy Surge · Adamant 86% | Grassy Glide 98, Fake Out 96, Wood Hammer 80, U-turn 51 |
| **Sneasler** | Grassy Seed 29%, **Psychic Seed 29%** | Unburden 89% · Adamant 61% | Close Combat 100, Dire Claw 92, Fake Out 59, Rock Slide 29 |
| **Salamence-Mega** | Salamencite 98% | Intimidate 99% · Timid 46% | Hyper Voice 92, Draco Meteor 56, Double-Edge 26 |
| **Incineroar** | Sitrus 66%, Chople 9% | Intimidate · Careful 38% | Fake Out 98, Flare Blitz 92, Throat Chop 41, Darkest Lariat 40 |
| **Kingambit** | **Chople Berry 45%**, Black Glasses 18% | Defiant 97% · Adamant 82% | Kowtow Cleave 99, Sucker Punch 98, Iron Head 79, Low Kick 53 |
| **Basculegion** | Choice Scarf 44%, Life Orb 33% | Adaptability 96% · Adamant 56% | Last Respects 100, Wave Crash 94, Aqua Jet 93, Flip Turn 44 |
| **Indeedee-F** | Colbur 30%, Psychic Seed 24% | Psychic Surge · Relaxed 45% | Psychic 59, Terrain Pulse 21 |
| **Gholdengo** | **Life Orb 77%** | Good as Gold · Modest 68% | Make It Rain 100, Shadow Ball 99 |
| **Golisopod-Mega** | Golisopite 99% | Emergency Exit · Adamant 58% | Leech Life 95, Iron Head 85, Sucker Punch 31 |
| **Arcanine-Hisui** | **Focus Sash 91%** | Rock Head 97% · Jolly 78% | Flare Blitz 100, Head Smash 94, Extreme Speed 90 |
| **Farigiraf** | Sitrus 57%, Colbur 21% | Armor Tail · Bold 35% | Psychic 50, Thunderbolt 47 |
| **Pelipper** | Focus Sash 46%, Sitrus 34% | Drizzle · Modest 58% | Hurricane 98, Weather Ball 88 |
| **Floette-Mega** | Floettite 99% | Flower Veil · Modest 64% | Dazzling Gleam 97, Moonblast 72, Light of Ruin 36 |
| **Archaludon** | **Leftovers 88%** | Stamina 96% · Modest 55% | Electro Shot 95, Flash Cannon 89, Dragon Pulse 78 |

### Things in that table worth acting on

- **Kingambit's Chople Berry at 45%.** Nearly half of them are built to eat one
  Fighting move. Plan the Close Combat that "obviously" kills it.
- **Arcanine-Hisui's Focus Sash at 91%.** It effectively always takes one hit. It is
  also Rock Head, so Head Smash and Flare Blitz cost it nothing.
- **Gholdengo's Life Orb at 77%** with only two moves, both 100%. Utterly predictable
  and hits like a truck anyway.
- **Archaludon's Leftovers at 88%** — Stamina plus recovery, not a glass cannon. It
  is built to sit there.
- **Sneasler's seed is a 29/29 coin flip**, and which one it is tells you the rest of
  the team: Grassy Seed means Rillaboom (99% of the time), Psychic Seed means Indeedee
  (100%). You can read half their team off one item.
- **Rillaboom's Miracle Seed at 56%** over Life Orb — the Grassy Glide boost, chosen
  for consistency rather than power.

---

## 3. Cores that are real, not just popular

Ranked by lift — how much more often a pair appears together than two Pokémon of
those usage rates would meet by chance. Lift near 1 is coincidence.

| Core | Lift | Read |
|---|---|---|
| Excadrill + Tyranitar | **13.0** | Sand. 96% of Excadrill run it |
| Gengar-Mega + Politoed | 18.7 | Rain Gengar |
| Charizard + Venusaur | 7.9 | Sun |
| Swampert-Mega + Archaludon | 8.0 | Rain |
| Archaludon + Pelipper | 5.5 | Rain — 76% of Archaludon |
| Gardevoir + Indeedee-F | 4.4 | Psychic terrain |

**The trap:** Rillaboom + Sneasler is the most common pair in the entire format at 431
teams — and a lift of **1.03**, pure chance. Both are just popular. The actual
relationship only appears once you condition on Sneasler's item.

---

## 4. Surprise performers

Pokémon outside the top 20 by usage that appear in top cut far above their rate.
**Small samples — read as leads, not conclusions.**

| Pokémon | Usage rank | All teams | Top cut | Ratio |
|---|---|---|---|---|
| **Swampert-Mega** | 41 | 3.1% | 4.5% | **1.48×** |
| **Gengar-Mega** | 40 | 3.1% | 4.3% | 1.39× |
| **Politoed** | 37 | 4.1% | 5.5% | 1.35× |
| **Venusaur** | 43 | 2.8% | 3.7% | 1.32× |
| Annihilape | 42 | 3.0% | 3.5% | 1.17× |
| Grimmsnarl | 32 | 4.6% | 5.3% | 1.15× |

Look at what that list *is*: Swampert, Politoed, Gengar-Mega — rain. Venusaur — sun.

**The weather archetypes are over-performing as a group**, not as individuals. That is
a much stronger signal than any single line here, because four independent entries
point the same way.

---

## 5. What actually wins

Across all 38 event winners. **38 teams total — one team is 2.6%.**

| Pokémon | On winning teams | Usage overall | Ratio |
|---|---|---|---|
| Rillaboom | **63%** | 55% | 1.15× |
| Salamence | 45% | 38% | 1.2× |
| Sneasler | 45% | 49% | 0.9× |
| **Archaludon** | **26%** | 11% | **2.4×** |
| **Raichu** | **21%** | 12% | 1.75× |
| **Swampert** | 11% | 3% | **3.7×** |
| **Venusaur** | 8% | 3% | 2.7× |
| **Annihilape** | 8% | 3% | 2.7× |
| Froslass | 13% | 7% | 1.9× |
| Politoed | 8% | 4% | 2× |

Archaludon appearing on **a quarter of all winning teams** off 11% usage is the
single most striking number in this snapshot, and it agrees with everything in §1
and §4.

### Real winning teams, biggest events first

```
148p  Tenki's Cart Weekly #117
      Metagross / Indeedee / Sneasler / Arcanine-Hisui / Salamence / Milotic

127p  VGC Reg M-C Ingame Tour #6
      Froslass / Raichu / Sneasler / Arcanine-Hisui / Kingambit / Rillaboom

123p  TARTAN TAKEDOWN #38
      Salamence / Annihilape / Raichu / Gholdengo / Arcanine-Hisui / Rillaboom

120p  Tenki's Cart Weekly #118
      Salamence / Arcanine-Hisui / Rillaboom / Kingambit / Farigiraf / Sylveon

102p  INGAGE FRONTIER SERIES #4
      Swampert / Pelipper / Archaludon / Grimmsnarl / Charizard / Venusaur

99p   Intimidators Champions Challenge #43
      Venusaur / Charizard / Grimmsnarl / Archaludon / Basculegion / Pelipper

98p   Talon's FIGHT CLUB #101
      Floette-Eternal / Sneasler / Incineroar / Rillaboom / Gholdengo / Raichu

91p   Talon's FIGHT CLUB #102
      Raichu / Salamence / Incineroar / Sneasler / Rillaboom / Gholdengo
```

### The oddity worth staring at

Look at the 102-player and 99-player winners. Both carry **a rain setter and a sun
setter on the same team** — Pelipper alongside Charizard and Venusaur.

Only **1.7% of all teams (37 of 2,148)** do that. Two of them won large events.

That is two data points and I am not going to pretend it is more. But the shape is
interesting: bring both weathers, set whichever ruins the opponent's plan, and deny
them theirs. Against a format where rain and sun archetypes are both over-performing,
a team that can flip the weather either way in Team Preview is a genuinely nasty
proposition. Worth watching whether it recurs as more events land.

Also: **Metagross won the single biggest event of the window** off a 5% usage rate,
and **Raichu is on 21% of winners** while sitting 16th in usage.

---

## 6. If I were picking something up

In rough order of how much the data supports it:

1. **Archaludon.** Rises on every measure, on a quarter of winning teams, Leftovers
   and Stamina so it is built to stay in. Pairs with Pelipper 76% of the time.
2. **A weather archetype**, rain especially. Four separate entries in §4 point there.
3. **Floette-Mega**, the biggest riser in the top 16 and the one fewest people are
   respecting yet.
4. **Watch Gardevoir-Mega** — if you are running it, its cut share is the worst fall
   in the format right now.

And the thing this snapshot cannot tell you: none of it accounts for *how* teams win.
Usage and placement are the shadow, not the shape.
