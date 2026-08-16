# ACB Offense Explorer

A local Streamlit app for exploring player-level offensive tracking data from the
**2024-2025 Liga ACB** season, built for a basketball analyst or scout.

The first view, **Shot Quality Board**, answers one scouting question from three
angles: *how hard are this player's shots, and does he make them?*

---

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS / Linux
pip install -r requirements.txt
streamlit run app.py
```

Python 3.10 or later. The app reads only the three CSVs in `data/` — no API, no
database, no credentials, no network access at any point.

```bash
pytest -q                       # tests for the analytical core
```

---

## What the board shows

One page, one player pool, one filter row, three lenses:

| Lens | The question | Plotted against | Minimum applies to |
|---|---|---|---|
| **Where he shoots** | Which shots does he take? | Average distance vs points per shot | `attempts` |
| **How guarded he is** | Does he score with a defender on him? | Share of shots guarded vs efficiency on them | `contested_attempts` |
| **How it was created** | Does he make his own shot? | Share off the dribble vs efficiency on them | `od_attempts` |

Selecting a player keeps him selected across all three, and across every filter
change, so the lenses are angles on one profile rather than three separate
reports. If a filter leaves him out of view his card is replaced by a line saying
so, and he comes back as soon as the filters let him through; unloading him is a
button on the card.

---

## Metrics, and why these

**Efficiency is measured with eFG% and points per shot, never FG%.** A player
taking 60% of his shots from three cannot be compared to a rim finisher on raw
field goal percentage. `efg_percentage` weights the extra point of a three;
`points_per_shot` is a true-shooting-style figure that also carries free throws.
Note that `efg_percentage` legitimately exceeds 1.0 for some players (1.5 is the
observed maximum), so it is never clipped.

**Volume and rate are kept apart.** Every rate on screen sits next to the count it
was computed from. Shot-menu shares (`rim_attempt_rate`, `zone_three_attempt_rate`
and friends) describe *what a player does*, so they carry no minimum at all — a
breakdown of 40 attempts is still an accurate breakdown. Only the accuracy figures
are gated.

**The ball handler / screener label stands in for position.** The datasets contain
no position column. But of 292 players, only **four** record 50 or more picks in
both roles: the handler / screener split is very nearly disjoint, so it acts as a
usable proxy for guard versus big. It is shown on the player card and never used
to filter silently.

### Guarded shooting is split by shot type, on purpose

Ranking players by contested eFG% puts big men on top, because a contested layup
is still a good shot while a contested three is not. Measured against how often a
player shoots at the rim:

| Metric | Correlation with rim attempt rate |
|---|---|
| `contested_efg_percentage` | **+0.17** — favours big men |
| Contested minus uncontested eFG% | **−0.37** — *worse*; the gap is not a fix |
| `contested_three_fg_percentage` | **−0.10** — effectively neutral |

The difference between guarded and open efficiency looks like a natural correction
and is in fact twice as biased as the raw number: a big man's open eFG% is so high
that his gap is mechanically terrible. It is not used.

What works is comparing like with like, so the lens splits into **All shots /
Two-pointers / Threes**. The three-point view is the cleanest read on shot-making
under pressure — it is the same shot for everybody on the floor. The all-shots view
is still reachable, with the bias stated on screen rather than hidden.

---

## Thresholds: the minimum applies to the denominator

**A minimum on games played protects nothing.** A player can appear in 34 games and
take 11 guarded threes all season. Showing his percentage on those 11 shots is
showing noise, and no games filter will stop it.

So every displayed rate names the count it is made of, in `DENOMINATORS`
(`src/core/metrics.py`), and the minimum applies to *that* count:

| Rate | Minimum applies to |
|---|---|
| `efg_percentage` | `attempts` |
| `contested_three_fg_percentage` | `contested_three_attempts` |
| `od_efg_percentage` | `od_attempts` |
| `rim_fg_percentage` | `rim_attempts` |

A test enforces this: every rate a view displays must declare a denominator that
exists in the data. A missing denominator fails the build rather than falling back
silently.

### Two stages, two different questions

| Stage | Control | Question |
|---|---|---|
| **Population** | minimum games, team, traded | *Who is in scope?* |
| **Sample** | the view's own count | *Can this number be trusted?* |

They are never merged. The population stage decides who is being looked at; the
sample stage decides whether a given number is worth printing.

### Chosen defaults

| View | Minimum | Players clearing it | Why |
|---|---|---|---|
| Where he shoots | 100 attempts | 176 of 295 | Roughly three shots a game — a real offensive role |
| How guarded he is — all shots | 60 guarded shots | 182 | Keeps the pool wide; the split views do the precision work |
| — two-pointers | 60 guarded twos | 118 | Enough to separate finishers |
| — threes | 40 guarded threes | 124 | Guarded threes are scarce; higher and the pool collapses |
| How it was created | 50 off the dribble | 135 | Below this, off-dribble efficiency is one hot week |

Every threshold is a slider running from 0 to **the highest value actually present
in the CSV for that column**, never a hard-coded ceiling. The defaults are applied
on load and the sliders sit in a collapsed panel: the board is useful without ever
opening it.

### What a minimum does to a player

* Players below it are shown greyed out, with their raw numbers intact — hiding
  them would hide the reason they are not comparable. A toggle removes them.
* They carry no percentile. A standing they did not earn is worse than none.
* **Percentiles are computed on the eligible pool only.** Including small-sample
  noise would stretch the scale for everybody else — and they are computed on
  every run rather than read from a precomputed file, because the eligible pool is
  whatever the reader's filters and minimum leave standing. A stored percentile
  would be stale the moment a slider moves.
* The table switches between raw values and percentiles. Both orderings are
  identical by construction — a percentile is the raw value re-expressed against
  the same pool — so the switch changes what is printed, never who comes first.
  Counts stay counts in both: replacing a sample size with a standing would hide
  the very thing the minimum exists to show.
* Sorting is two-tier and stays that way: eligible players first, then the rest,
  each group sorted alike. Clicking a column header re-orders the table — the
  column is marked with an arrow and a blue tint — and the greyed players stay
  pinned underneath. Enabling column selection on the table switches off the grid's
  built-in sorting, which is what lets the app own the row order instead of the
  browser.
* Context columns carry their own floor. Open 3PT% blanks below 10 open threes,
  independently of the slider — the rule follows the number, not the control.

### Regression to the mean is deliberately absent

Shrinking percentages toward the league average was considered and left out. Market
scouting tools work on thresholds, a threshold is explainable to a coach, and a
shrunk percentage is not the number anyone will quote. If it returns it will be an
optional "adjusted" column beside the raw one, never in its place.

---

## Data notes and limitations

**`avg_shot_distance` is stored in feet, not metres.** The glossary labels it
metres, but the distribution says otherwise: the most rim-bound big averages 3.78
and the deepest shooter 22.11. Read as metres that puts the whole league beyond
half court. Read as feet, 22.11 converts to **6.74 m — the FIBA three-point line, to
the centimetre**, and 3.78 becomes a 1.15 m layup. The app converts before display
and leaves the raw column untouched; a test guards the conversion.

**Blitz and Ice coverages are unusable in this release.** Across all 292 players the
highest count is 5 picks against a blitz and 7 against an ice (medians of 0). No
player reaches 25 of either. Whatever the cause — genuinely rare in the ACB, or
under-labelled by the tracking — no efficiency against those coverages can be
computed, and none is offered. This affects the pick-and-roll views, not this board.

**There is no position column,** and no minutes column either. Nothing can be
normalised per 36 minutes; everything is per shot, per pick or per game. Note also
that `games_played` counts games with at least one *tracked event in that dataset*,
which is not the same as appearing in the box score.

**`games_played` runs from 1 to 44** for a 34-round regular season: the top of the
range includes play-offs. No total is hard-coded anywhere.

**Traded players hold one row each.** Eight players changed team during the season.
The glossary confirms the row still aggregates their whole season, while
`team_name` shows only the last club — so a team-level total would count them in
the wrong place. A toggle removes them.

**The two files carry different rosters** — 292 pick rows against 295 shot rows,
288 players in common. The join is explicit and its provenance is kept in a
`source` column rather than assumed away.

**Some columns are empty.** `no_outcome_pick` is zero for every player, and 24
pick columns are entirely zero. None of them is displayed.

---

## How the code is organised

Data work and interface are separated by directory, not by intention:

```
app.py                  entry point: page config and navigation, nothing else
pages/                  one view per file — widgets, calls into src, rendering
src/
  data/    schema.py    every raw column name, in one place
           glossary.py  metric_glossary.csv: display names, definitions, units
           loader.py    reading the CSVs and joining them on player_id
  core/    aggregate.py derived columns; pure functions
           metrics.py   the metric catalogue and its denominators
           thresholds.py two-stage filtering and slider bounds
           ranking.py   ranks and ordering over the eligible pool
  ui/      filters.py charts.py tables.py panel.py
           selection.py which player is loaded
           sorting.py   which column the table is ordered on
           format.py theme.py
tests/                  the core only; no Streamlit widget is tested
data/                   the three source CSVs, read-only
```

Rules the code holds to:

* **No pandas in `pages/`.** A page reads widgets, calls `src`, renders. Any
  `groupby`, ratio, quantile or boolean mask lives in `src/core`.
* **No column-name string outside `src/data/schema.py`.**
* **No `st.*` outside `src/ui/` and `pages/`.** Core functions take a DataFrame and
  return a new one.
* **Ratios stay on their 0-1 scale** everywhere; the multiplication by 100 happens
  in `src/ui/format.py` and nowhere else.
* **Caching where it pays**: reading the CSVs and parsing the glossary. Nothing
  that depends on a slider is cached.
* **Interface language stays plain.** No "sample size", "percentile" or "n≥" on
  screen; the reader sees games, shots and attempts. The statistics live in this
  README.

Labels and tooltips are read from `metric_glossary.csv` rather than retyped, so the
interface cannot drift from the data dictionary. The five columns the app computes
itself are documented in `src/data/glossary.py`, beside the ones it reads.
