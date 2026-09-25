# Retrospective

Written after seven working days of building this in September 2026. It is a record of
what I decided, what I got wrong, and what I chose not to build.

## The question I was actually trying to answer

I play VGC and I was preparing for locals. The thing I could not do quickly was look at
my six and know how they line up against what people are actually bringing. Existing
tools each answer part of it — a damage calculator here, a usage page there — and none
of them answer it against *my* team in one place, offline.

So the whole tool is pointed at one question: **how does my team line up against the
current meta?** Every tab is a facet of that. When something didn't serve that question,
it went in the parking lot instead of into the code. There are about thirty entries in
there and the tool shipped.

## The two decisions that shaped everything downstream

**Usage comes from tournament teamlists, not the ranked ladder.** The two metas genuinely
differ, and I am prepping for events, not for ladder. This was the first real fork and it
determined the entire ingest pipeline — it meant building around Limitless teamlists and
accepting that official regionals are simply not obtainable, rather than taking the easier
ladder data and quietly answering a different question than the one I asked.

**Offline is a hard requirement, not a nice-to-have.** I wanted to study matchups while
travelling, with no network. That single constraint is why sprites are cached and committed
rather than hotlinked, why spread editing lives in session state, and why there is a test
that blocks network sockets and drives every tab. A visual that silently needs the internet
is worthless on a plane, and "it works on my machine with wifi" would not have caught it.

## How this was built

I did not write the code. I worked with Claude (Opus 5) as a pair: I owned direction,
domain judgement, priorities and acceptance — what the tool should say and whether what it
says is true — and it wrote the Python, SQL, tests and pipeline. Commits it co-authored
carry a `Co-Authored-By` trailer, so the split is visible in `git log` rather than asserted
here.

The part I want to be judged on is the next section.

## Four times the tool was confidently wrong and I caught it

These came from reading output, not from reading code. The test suite was green for all
four.

**1. Sneasler and Rillaboom are not a coincidence.** The cores view reported a lift of
1.03 between them — statistically pure chance. I knew from playing that the pairing is
real, so I pushed back. The data turned out to be emphatic in a way the average had
destroyed: Grassy Seed Sneasler runs Rillaboom **99%** of the time, and Psychic Seed
Sneasler runs Indeedee **100%** of the time. Two mutually exclusive builds wanting opposite
partners, cancelling to nothing when you average them together. That produced the entire
item-conditioned cores view. It was an aggregation failure in the presentation, not a
property of the meta.

**2. "What you would lose by removing each Pokémon" was lying.** The column measured unique
super-effective coverage but was labelled as though it measured everything a Pokémon
contributes. Indeedee scored zero while holding the team together through terrain. A number
that is correct and mislabelled is worse than no number, because you act on it.

**3. Weather belongs in the damage calculator.** Pelipper's rain takes a Fire hit on my
Golisopod-Mega from 4× to 2×. That is a threshold effect — it changes whether something
KOs — and it is invisible to any correlation-based view of the meta.

**4. Mega formes were showing a Choice Scarf benchmark they cannot have.** A Mega is holding
its stone, so it cannot also hold a Scarf. I reported it as a cosmetic problem. It wasn't:
the same flag fed the Speed verdict, so the tool was reading "Depends" where the honest
answer was "You outspeed." It got fixed in the data layer rather than hidden in the display.

A related one worth naming because it was live in the tool and affected real decisions: my
own Choice Scarf was never being applied to my team's Speed. My Basculegion displayed 143
against a true 214, which made **12 of 20 Speed verdicts wrong**.

## Rules I set for how the work got done

Process, not features. Each of these caught something real.

- **All writes go through `scripts/`; the app is strictly read-only.** This came under
  pressure three separate times and held. It is why a second tool of mine can read the same
  warehouse safely, and why the spread editor lives in session state.
- **Every judgement call gets a row in `DECISIONS.md` with its reasoning.** There are 147.
  It repeatedly stopped later sessions from re-deciding settled questions, and it is the
  reason I can still explain why anything in here is the way it is.
- **Loaders are proven idempotent by running them twice and diffing row counts.** An
  explicit check, not an assumption.
- **Actually open the app and look.** Six real bugs were invisible to a green test suite: a
  column scrolled off-screen, unreadable text on light fills, a collapsed chart axis from
  duplicate labels, sprites overlapping their tick labels, and a nature selector silently
  applying Adamant to every unnatured Pokémon.
- **Verify against the reference implementation, not against a reading of it.** The damage
  calculator is checked by *running* Pokémon Showdown's own simulator from a pinned
  checkout, not by agreeing with someone's interpretation of its source. It matches roll
  for roll — all sixteen rolls across 35 cases. That caught two things no amount of reading
  would have: the game uses 4096-step fixed-point arithmetic rather than float multiply,
  and the random roll lands *before* STAB and type effectiveness, not after. Both move a
  result by a point or two, which is invisible to eyeballing and fatal to a KO threshold.

That last rule is the standard the project holds itself to. Most numbers in this tool are
annotations with a stated limit. A damage figure is a claim — "that move takes 112% of your
HP" is either right or it is misinformation — so agreeing with my own reading of the source
is not evidence.

## What it deliberately does not do

- **No composite scores anywhere.** Show the components and let me sort by them. Netting a
  coverage loss against a defensive gain is a statement about my priorities, not a fact
  about the meta, and burying it in a single number takes that judgement away from me.
- **No ability interaction graph.** A model that covers six interactions and silently misses
  the seventh is worse than none, because you stop double-checking it.
- **No multiplying of unpaired distributions.** The source publishes natures and spreads
  separately and never pairs them, so confidence is reported as the weaker of the two
  shares, never their product.
- **No scraping of reference sites, no ML, no hosting.** It runs on one laptop for one user.

The tool also declines to claim a ranking is settled when the sample is thin —
`check_meta_stability.py` exists to answer that question honestly, and the app warns below
400 teams that which names appear matters more than where they sit.

## What is still rough

1. The **"What to add"** tab is not intuitive. It accumulated as I built and reads like a
   changelog rather than a workflow. I flagged it as the highest-value hour available and
   it is still open.
2. `sole_coverage` still overpromises in its label — see wrong-thing #2 above. Renaming it
   honestly and measuring empirical dependency instead is the fix.
3. Sprites exist for the meta (259) but not for all 394 pickable dex entries, so an
   off-meta pick renders thin.
4. One guard test currently fails on my machine. It asserts that at least one Mega's base
   species runs Choice Scarf above the 20% threshold, so the real test beside it cannot pass
   vacuously. The meta has since refreshed and no Mega clears it, so the guard has nothing
   to guard. It is a decision about what that test should assert, not a regression — and I
   would rather leave it visible than delete it quietly.
5. No Tera, screens or crits in the build panel — the three things a full calculator has
   that this visibly lacks.

## What I would do next

Restructure the "What to add" tab around a single question; rename `sole_coverage` and give
it a measure that matches its label; add the damage-relevant abilities (Thick Fat,
Adaptability, Multiscale). Usage-trends-over-time was rated low value when the data spanned
nine days — it now spans thirteen across 58 events, so it has started to earn its rating.
