# Triple Threat

> Une version française de ce document est disponible : [`README.fr.md`](README.fr.md).
> Contenu identique, mot pour mot.

A local Streamlit app for exploring player-level offensive tracking data from the
**2024-2025 Liga ACB** season, built for a basketball analyst or scout.

The name is the three ways this data shows a player threatening a defence:
shooting it, attacking off a screen, and creating for somebody else.

The app is read in that order — **build a list, then explain it**:

| Page | What it is for |
|---|---|
| **Shortlist** | *Who fits?* Stack the bars a player has to clear, export the list, then open anyone on it and read his whole offensive profile in place. |
| **Shot Quality Board** | *How hard are his shots, and does he make them?* |
| **Pick & Roll Board** | *Does a screen create an advantage for him, and what does he do with it?* |

A scout arrives with a search, not with a scatter plot, so the shortlist opens the
app. The two boards go deeper on one question each: they rank the league and explain
what the axes mean in plain language.

**One scope bar runs across all three**, at the top of every page — games played,
shots taken, team, name, traded — and it holds the same answers wherever the reader
goes. It is the working dataset: who counts as a league player, and therefore what
every percentile in the app is measured against. The selected player travels the
same way, so the three pages read as angles on one profile rather than three
reports.

---

## 1. Setup and run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  source .venv/bin/activate on macOS / Linux
pip install -r requirements.txt
streamlit run app.py
```

Python 3.10 or later. Four runtime dependencies: `streamlit`, `pandas`, `plotly`,
`numpy`.

Nothing else is needed: the three season CSVs ship with the repository, in `data/`,
and they are the only source the app has — **no API, no database, no credentials,
no network access at any point**. `data/` is read-only; nothing in the app ever
writes to it.

```bash
pytest -q                       # 66 tests over the analytical core
```

---

## 2. Which metrics, and why

### Two files, two ways to threaten a defence

The brief ships two datasets, and they are not two halves of one thing — they are
two independent axes of a player's offence:

* **`shots_offense`** answers *what kind of shot does he take, and does it go in?*
  — distance, contest, and who created it.
* **`picks_offense`** answers *what happens when a screen is set for him or by
  him?* — the single most-run action in modern basketball, and the one place this
  data measures something a box score cannot reach.

A player can be excellent on one axis and invisible on the other. The app is built
around that: one board per axis, and a shortlist that crosses them. Nothing forces
the two into a single composite rating, because a rating would hide exactly the
gap a scout is looking for.

Of the 827 columns described in the glossary, the app displays around a hundred.
The rest are either dead (see §4), redundant with a column already shown, or a
split so thin that no player clears a defensible minimum on it.

### Shooting: efficiency is never FG%

**eFG% and points per shot, never raw field goal percentage.** A player taking 60%
of his shots from three cannot be compared to a rim finisher on FG%.
`efg_percentage` weights the extra point of a three; `points_per_shot` is a
true-shooting-style figure that also carries free throws.

The three shooting lenses:

| Lens | The question | Plotted against | Minimum applies to |
|---|---|---|---|
| **Shot distance** | Which shots does he take? | Average distance vs points per shot | `attempts` |
| **Shot contestation** | Does he score with a defender on him? | Share of shots guarded vs efficiency on them | `contested_attempts` |
| **Shot creation** | Does he make his own shot? | Share off the dribble vs efficiency on them | `od_attempts` |

#### Guarded shooting is split by shot type, on purpose

Ranking players by contested eFG% puts big men on top, because a contested layup is
still a good shot while a contested three is not. Measured against how often a
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
stays reachable, with the bias stated on screen rather than hidden.

### Pick and roll: one lens per role

Ball handler and screener are two different jobs, and in this data very nearly two
different populations: of 292 players, only **four** record fifty picks in both
roles. So the role is a lens, not a filter — and each lens is built for that role's
own set of coverages, which are **not the same on both sides** (the handler faces
Over / Under / Switch / Blitz / Ice; the screener faces Show / Soft / Switch /
Blitz / Ice).

| Lens | Plotted against | Minimum applies to |
|---|---|---|
| **Ball handler** | Picks he finishes himself vs points generated | `handler_total_picks`, then `handler_picks_vs_<coverage>` |
| **Screener** | Shots from three out of the screen vs points generated | `screener_total_picks`, then `screener_picks_vs_<coverage>` |

**Points per pick counts the points a teammate scored off the player's pass, not
just his own basket.** It measures the offence generated per screen, which is the
right question for a ball handler and the wrong one for a pure shooting comparison
— `points_per_shot` from the shooting file is not its equivalent, and the two are
never put side by side. The scorer-only figure exists separately as
`{role}_points_per_shot_in_pick`.

Four columns carry most of the value of this board:

* **`handler_success_rate`** — the share of screens the tracking judges to have
  created an advantage, **regardless of whether the shot went in**. It separates
  execution from shot-making, which a box score cannot.
* **`handler_pass_to_screener_pct`** — does he actually play with his roll man, or
  does he use the screen to hunt a kick-out?
* **`screener_assist_rate`** — passing out of the short roll. A big-man skill that
  is hard to quantify anywhere else, and this file gives it directly. It is the
  most original thing in the whole dataset.
* **`{role}_shot_rate_3pt`** — separates a roller from a popper in one number.

### What was deliberately not built

* **No composite score, no player rating.** Every number on screen is a column of
  the CSV or a stated division of two of them.
* **No new "per game" family.** The files already ship rates for almost everything
  (`{role}_ppp`, `*_attempt_rate`, `*_fg_percentage`), so inventing a parallel set
  of per-game figures would have doubled the vocabulary without answering a new
  question, and loaded the pages for nothing. Only two per-game columns are derived
  — `{role}_picks_per_game`, used as a volume reference on the card.
* **No position-based comparison.** The data has no position column (§4).

---

## 3. Filtering, thresholds and normalisation

This is where most of the analytical work went, so it is the longest section.

### 3.1 A minimum on games played protects nothing

A player can appear in 34 games and take **11 guarded threes** all season. Showing
his percentage on those 11 shots is showing noise, and no games filter will stop
it — he passes every one of them.

So the rule the whole app is built on:

> **The minimum applies to the count the displayed rate is actually made of, never
> to games played.**

Every displayed rate names its own denominator in `DENOMINATORS`
(`src/core/metrics.py`):

| Rate | Minimum applies to |
|---|---|
| `efg_percentage` | `attempts` |
| `contested_three_fg_percentage` | `contested_three_attempts` |
| `od_efg_percentage` | `od_attempts` |
| `rim_fg_percentage` | `rim_attempts` |
| `handler_ppp_vs_over` | `handler_picks_vs_over` |

The pick side of that table is **generated**, not typed: the picks file repeats the
same metric stems across two roles, ten coverages and three floor spots, so the
regularity does the work and only the stems are listed. A test enforces the whole
map: every rate a view displays must declare a denominator that exists in the data.
A missing denominator fails the test suite rather than falling back silently.

### 3.2 Two stages, two different questions

| Stage | Control | Question | Scope |
|---|---|---|---|
| **The league** | the scope bar: games played, shots taken, traded | *Who counts as a player at all?* | The whole app |
| **The sample** | the view's own count | *Can this one number be trusted?* | Recomputed per metric and per split |

They are never merged. The first decides who is being looked at and what every
standing is measured against; the second decides whether a given number is worth
printing.

**The scope bar is one control over one working dataset.** It sits at the top of all
three pages, it holds the same answers on each — narrow the league on a board and
the shortlist is narrowed with it — and the line under it says what it costs:
*213 of 299 players are the league here.* A reader shown 213 names has no way of
knowing whether the file holds 220 or 500, and the two answers make the same list
mean different things.

Team and the name search sit in the same bar but do **not** define the league; they
narrow what is on screen. Ranking a man against the six team-mates a club filter
left standing — or against himself, after typing his name — would leave every
percentile in the app describing a population nobody can see.

### 3.3 The league bar: fifteen games, one shot a game

Both defaults are **deliberately conventional rather than derived**. Public
leaderboards gate on a round, symbolic number a reader can repeat — the NBA's
three-point percentage title requires **82 made threes**, which is simply *one a
game over an 82-game season*. Nobody computed 82 from a variance argument; it is a
figure people can argue with, which is the point.

Applied here: **one attempt per official game**. Over a 34-round ACB regular season
that is 34 shots, rounded up to **35** so it lands on a notch of a control that
moves five at a time. With fifteen games beside it, **213 of the 299 players in the
two files are the league**.

Two deliberate differences from the NBA convention:

* **The bar is on attempts, not on makes.** Gating a percentage leaderboard on
  *made* shots selects on the outcome being measured — a 30% shooter needs far more
  attempts to qualify than a 45% one. Attempts are neutral.
* **It is low on purpose, and one click from anything else.** It keeps a percentage
  built on five shots out of a ranking; it is not there to reduce the app to volume
  scorers. Games run 0 / 10 / 15 / 20 / 25, shots Any / 15 / 25 / 35 / 50 / 75 / 100.

Stated per game rather than as a bare number, because 35 is not a figure anybody can
place on its own, while *one shot a game* is a bar a reader can agree or disagree
with.

### 3.4 Pick and roll: a split is asked for the share of a season the whole is

**10 picks for the ball handler, 20 for the screener.** A screen is not a shot, and
the two roles are not the same job either: a screener sets screens all game while a
handler runs the ones his team calls for him. Their volumes are not comparable, and
one bar for both would rank two different jobs on a single scale. At 10 and 20, 141
handlers and 150 screeners are measured — a rotation's worth of each, against 102
and 103 at a common bar of 50.

**Then each split gets that bar cut to how often the league plays it.** A flat 25
picks per coverage was the same bar asked five times over, and it asked far more of
a split than the board asks of the whole: a handler is measured from ten screens,
yet needed twenty-five of them played one way.

So the bar is `role bar × the coverage's league share`, rounded **down** to a notch
the slider can reach, never below 1. The shares are measured from the files and a
test recomputes them, so the constants cannot go stale:

| Split | League share | Bar | Eligible (of the 213) | *Was, at a flat 25* |
|---|---|---|---|---|
| Ball handler vs Over | 66.7% | **5** | 122 | 97 |
| Ball handler vs Switch | 16.4% | **1** | 147 | 60 |
| Ball handler vs Under | 15.9% | **1** | 143 | 54 |
| Ball handler vs Ice | 0.6% | **1** | 67 | 0 |
| Ball handler vs Blitz | 0.3% | **1** | 45 | 0 |
| Screener vs Show | 45.1% | **5** | 142 | 83 |
| Screener vs Soft (drop) | 37.1% | **5** | 145 | 67 |
| Screener vs Switch | 16.4% | **1** | 198 | 58 |
| Screener vs Ice | 0.6% | **1** | 55 | 0 |
| Screener vs Blitz | 0.3% | **1** | 37 | 0 |

Every coverage roughly doubles, and the two rare ones go from **nobody at all** to
45 and 67 players. At a bar of one the number is thin and the app says so: the pick
count sits next to every figure, on the board and on the card, so what the reader is
being shown is never hidden from him. Raising it is one drag of the slider.

### 3.5 The controls, and what they are allowed to be

**Every bar in the app is a control the reader owns.** The defaults are opinions,
stated in this file and moveable on screen — no number is applied that cannot be
seen and changed:

* The **scope bar** is two dropdowns at the top of every page, always visible, with
  the league count under them.
* The **view minimum** is a slider in a panel under it, one per view, running from 0
  to the highest value actually present in the CSV for that column — never a
  hard-coded ceiling, so a split where nobody clears 10 events cannot be given a
  misleading 500-wide slider.
* Every slider steps in fives, so **every default sits on a notch it can return to**.
  A bar of eight, reachable from neither five nor ten, is one the reader loses the
  first time he nudges the control. Bars of one are the exception: they open below
  the first stop, and zero — everybody, counts on show — is the way back.
* The panel is **collapsed with its defaults already applied**: the board is useful
  without ever opening it, and complete the moment it is opened.
* Under the slider, a **`Show players below the minimum` toggle**. Left on, everyone
  stays visible — greyed, pushed under the measured players, numbers intact; off,
  they disappear. Hiding them by default would hide the reason they are not
  comparable, and a table that silently drops a third of the league is one nobody
  can audit.

### 3.6 What a minimum does to a player

* He is **greyed out with his numbers intact**, and stays pinned under the measured
  players **whatever the sort order** — sorting is two-tier by construction, so a
  header click never floats a 4-shot player to the top.
* **He keeps his percentile.** The standing comes from the scope bar's league, not
  from the view's bar, so it does not depend on where the slider sits: the grey row
  is what says the sample is thin, and it says it without also deleting the one
  number that places him.
* If he is the player currently loaded, his card explains it and **names the panel
  that would bring him back** — *"Only 12 guarded shots all season"* is his own
  fault only if the reader knows which control he set. Unless the count is zero, in
  which case lowering the bar would not bring him back, and promising it would be a
  lie.
* Context columns carry their own fixed floor, independent of the slider: Open 3PT%
  blanks below 10 open threes. **Greyed and blanked mean two different things** —
  a greyed *row* is "this player is not measured on the metric this view is about";
  a blanked *cell* is "this particular number does not have the sample".

### 3.7 Percentiles: one pool, everywhere

Percentiles were added so a number can be placed against the league instead of read
in a vacuum — a scout reads *86th of 174* faster than *0.412*.

**The pool is the scope bar's league, and it is the same on every page, every view,
every figure and every spoke of the radar.** Three pools were tried first — the
view's eligible players on the boards, the whole file on the shortlist, one
population per radar axis — and it was the wrong answer: a standing that moved
whenever a slider moved is a number the reader cannot carry from one screen to the
next, which is the only thing a percentile is for.

Four rules follow from it:

* **Percentiles are computed on every run, never read from a precomputed file.** The
  pool is whatever the scope bar leaves standing, so a stored percentile would be
  stale the moment it moves — and writing to `data/` is not allowed anyway.
  `rank(pct=True)` on 300 rows costs microseconds.
* **Counts are placed too**, not only rates: shots taken, threes taken, picks run,
  games played. Where a player's volume sits among his peers is a fact a scout
  reads, and *615 picks* means nothing until it is also *96th in the league*. The
  table opens on values, so nothing is replaced — the switch is one click.
* **Values and percentiles order the table identically** — a percentile is the raw
  value re-expressed against the same pool — so the switch changes what is printed,
  never who comes first. Offering two sorts would be a false choice.
* On the radar, an axis a player has too few events for is **left empty rather than
  drawn at zero**, which would read as a weakness he has not shown. A dotted ring at
  the fiftieth percentile marks the middle of the league: outside it is above
  average, inside it below.

**In percentile mode the table is shaded**, one blue deepening with the standing,
with a five-step key above it. A hundred numbers between 0 and 100 is a wall read
line by line; the same table shaded is read at a glance — where the deep cells
cluster is what the player is good at — and the number is still printed underneath.
One hue on one axis, never red-to-green: that would read as good-to-bad, and a high
share of guarded shots is not a virtue.

### 3.8 Normalisation: what is normalised, and what is not

**Rate and volume are kept apart, and the count is always on screen.** Every rate
sits next to the count it was computed from.

**Shares carry no minimum at all.** `rim_attempt_rate`, the pick spots on the
floor, the coverage breakdown — these describe *what a player does*, not how well
he does it, and a breakdown of 40 attempts is still an accurate breakdown of 40
attempts. Only accuracy figures are gated. A total is likewise never gated: a total
is a total.

**No per-36 or per-40 anything.** There is no minutes column in either file (§4),
so minute normalisation is impossible rather than merely unattractive. Everything
is normalised per shot, per pick, or per game.

**Ratios stay on their 0–1 scale everywhere in the code**; multiplication by 100
happens in `src/ui/format.py` and nowhere else.

Five derived normalisations, each with a reason:

| Derived | How | Why not the obvious way |
|---|---|---|
| `avg_shot_distance` → metres | × 0.3048 | The column is stored in feet despite its glossary label (§4). The raw column is never overwritten. |
| Mid-range share | `short_midrange_paint_attempt_rate + long_midrange_attempt_rate` | **Not** `100 − rim − three`. The four zones only cover ~97% of attempts, so the subtraction would inflate the mid-range by 3 to 9 points. |
| Coverage share | `picks_vs_<coverage> / total_picks` | The file ships a share per floor spot but **none per coverage**, though both counts are there to divide. |
| Contested 2PT / 3PT share | `contested_X_attempts / X_attempts` | The file ships the contested share of *all* shots only, which mixes layups and threes. |
| Assisted share | `assisted_shots / mades` | A count in the file, a share nowhere. |

Every division goes through `safe_ratio`, which returns **NaN, not 0**, when the
denominator is zero: a player who never took a corner three has an *unknown*
corner-three percentage, and printing 0% there would invent a fact.

**Median reference lines are drawn on the scope bar's league, and on the players who
were measured inside it.** Two conditions, and both matter. The pool is the same one
the percentiles use, so a card's two references agree instead of describing two
different populations. Within it, each line is the median *among the players
clearing that slice's own count*: taken over the whole file,
`screener_ppp_at_stepUp` has a median of **0.09**, while among the players with at
least 25 picks there it is **0.32**. The first number is dragged down by players
with two or three step-up screens who scored on none of them, and comparing a
measured player against it makes almost everybody look good.

### 3.9 Regression to the mean was considered and dropped

Shrinking each percentage toward the league average — adding a few phantom
league-average attempts to every player — was the first idea for handling small
samples, and it was abandoned after looking at what comparable products actually
do.

* **Market scouting tools work on thresholds.** Synergy, InStat and the public
  leaderboards all gate; none of them publishes a shrunk percentage as *the*
  number.
* **A threshold is explainable to a coach.** "He is 39% from three on 120 attempts"
  survives a conversation. "His regularised three-point percentage is 36.8%" does
  not, and it is not a number anyone will quote back.
* **The shrunk value is not the player's value.** It is an estimate of his true
  talent, which is a different question from the one a shot chart answers. Mixing
  the two in one column would make every printed number quietly non-additive.
* **Basketball sample sizes here are small enough that shrinkage would do the
  filtering anyway**, but invisibly: a 5-attempt player pulled to the league mean
  looks *average*, not *unmeasured*, which is strictly worse information than a
  greyed row.

If it ever returns it will be an **optional "adjusted" column beside the raw one,
never in its place**.

### 3.10 Filtering on the shortlist

**A criterion is one condition: the bar the reader typed.** It used to be two — the
value, and a number of events silently required behind it — so asking for 40% from
three also asked, invisibly, for forty attempts. That is a reason a name could be
missing that nobody reading the screen could discover, and no amount of it being
statistically sensible makes an unwritten filter acceptable. It is gone.

What guards the sample instead is **the scope bar at the top of the page**, the same
one the boards answer to: it is visible, it is two clicks wide, and it says how many
players it leaves. One place decides who the league is; the criteria then say which
of them the reader is looking for.

**A bar can be set as a value or as a place in the league**, and the line under it
states both: *39.5% — 80th percentile, keeping the top 20% of the 125 players who
have this number*. Percentages are typed as percentages, and the box opens on the
median rather than at zero. A rate opens in percentile mode ("the top 20%" is the
question a scout arrives with); a count opens in value mode, because nobody asks
for a player in the top 20% of games played.

**The page opens on no criterion at all** — the perimeter every page starts from is
the scope bar above, so the first row is empty and the reader writes the first bar
himself. There is no panel of minimums either: a board gates one metric at a time,
so a panel of sliders makes sense there; a shortlist shows every metric at once, and
a second battery of sliders beside the bars he wrote would be a minimum nobody asked
for. The floors a board applies to its context columns still hold here, so the
shortlist is never the one place a thin number gets through.

---

## 4. Assumptions, and limitations found in the data

### `avg_shot_distance` is stored in feet, not metres

The glossary labels it *metres*. The distribution says otherwise: the **median**
player averages **14.43**. Read as metres, that puts the median shot in this league
beyond half court, on a 28-metre floor.

Read as feet it resolves exactly. Among the 234 players clearing 35 attempts, the
deepest averages **22.20 ft = 6.77 m** — the FIBA three-point line (6.75 m) to the
centimetre — and the most rim-bound averages **3.27 ft = 1.00 m**, a layup. The app
converts before display, leaves the raw column untouched, and a test guards the
conversion.

### Blitz and ice are rare coverages in the ACB

Across all 292 players the highest count is **5 picks against a blitz** (both
roles) and **7 / 9 against an ice**, with medians of 0. This is not missing data:
Spanish defences simply play them very little.

They are shown like every other coverage, with a low default bar and a note on
screen saying the coverage is rare. Hiding a split because it is rare would answer
a scouting question — *how does he handle a blitz?* — with silence.

The one place this forced an exception: on the player card's coverage figure the
bar is **one pick**, not twenty-five. At 25, **not a single player in the league**
had a figure against the blitz or the ice, which reads as broken data rather than
as a rare coverage. That figure is a card, not a ranking: nobody is placed against
anybody, and the pick count is printed beside every slice, so the reader judges the
sample himself.

### No position column, and no minutes column

* **No position.** The closest available stand-in is the ball handler / screener
  split, which is very nearly disjoint (only 4 of 292 players record 50+ picks in
  both roles). It is shown on the player card and never used to filter silently.
  Consequence: **"compare him to other bigs" is not a question this app can
  answer**, and it does not pretend to.
* **No minutes.** Nothing can be normalised per 36 or per 40 minutes.
  `games_played` counts games with **at least one tracked event in that file**,
  which is not playing time and not the same as appearing in a box score.

### `games_played` runs from 1 to 44

For a 34-round regular season: the top of the range includes play-offs. So 34 is
the **length of the regular season** and is used only to express "one shot per
game"; it is never used as a maximum and no total is hard-coded anywhere.
`games_played` and `appearances` are identical row for row in both files, so only
one of them is exposed.

### The splits do not partition the total

This one is easy to miss and quietly wrong if missed. **None of the shot splits sum
back to the total attempts**, because some shots carry no classification:

| Split | Coverage of total attempts | Worst single player |
|---|---|---|
| Contested + uncontested | 97.5% (1 059 shots unclassified) | 15 shots missing |
| Catch & shoot + off the dribble | 94.1% (2 494 shots) | 31 shots |
| The 5 NBA zones | 96.8% | 25% of his attempts |
| The 4 SkillCorner zones | 96.8% | — |
| The 5 contest levels | 97.5% | 15 shots |
| The 14 shot types | 97.5% | 15 shots |

Consequences the app applies: shares are always computed against the **total**, so
they legitimately fall short of 100% and are never renormalised to it; the
mid-range share is a **sum of two zones, never `100 − rim − three`**; and the shot
chart is described as covering *most* of a player's attempts rather than all.

By contrast, two splits *do* partition: two-pointers plus three-pointers equal
total attempts exactly for all 295 players, and the five coverages account for
98–100% of a player's picks — which is what makes a 100% stacked bar the right
shape for the coverage figure.

`zone_three_attempts` is likewise **≤ `three_attempts`** for 203 players (up to 17
fewer), for the same reason: some threes carry no zone.

### eFG% legitimately exceeds 1.0 — but not on the column you would expect

`efg_percentage` itself tops out at exactly **1.00** (two players, on 6 and 3 shots
all season). The split columns go higher: **`cns_efg_percentage` reaches 1.50**, and
contested and uncontested eFG both reach 1.25 — all three on **two attempts**. eFG
can reach 1.5 by construction (all shots made, all of them threes), so nothing is
clipped at 1.

These values are also the cleanest illustration of why the minimum exists: every
one of them belongs to a player the 35-shot bar removes from the ranking.

### Zero and missing are correctly distinguished in the source

The provider is careful here, and the app matches it. A player with no picks as
ball handler carries **NaN** in `handler_ppp`, not 0 (72 players). The 243 players
who never faced a blitz carry NaN in `handler_ppp_vs_blitz`. The 201 players who
never attempted a heave carry NaN in `cst_heave_fg_percentage`, not 0%.

So the app's own divisions return NaN on a zero denominator (`safe_ratio`), and
NaN prints as a blank rather than as a zero. Treating the two as the same would
turn "never tried" into "tried and failed" on every card in the app.

### Dead and near-empty columns

* **24 pick columns are zero for every player**, including the whole
  `no_outcome_pick` family and `screener_ft_attempts_in_pick` — so the screener's
  points-per-shot in pick is field-goal only, while `handler_ft_attempts_in_pick`
  reaches 79. None is displayed.
* **One pick column is entirely empty**: `handler_fg2_pct_vs_blitz`.
* **89 of the 599 pick columns are over half empty**, almost all of them rare
  coverage × metric combinations.
* **4 shot columns are zero for every player**: `cl_blocked_mades`, `_points`,
  `_fg_percentage`, `_points_per_shot`. That is logically correct rather than a
  defect — a blocked shot is by definition not made — and it is why "blocked" is
  treated as a contest level and not as a shot outcome.
* **8 shot columns are over half empty**: the percentage and points-per-shot of the
  rarest shot types (heave, leaner, lob, post fadeaway), NaN wherever the player
  never attempted one.

### Traded players hold one row each

Eight players changed team during the season. The glossary confirms the row still
aggregates their whole season, while `team_name` shows only the last club — so a
team-level total would count them in the wrong place. **They are not
de-duplicated** (there is nothing to de-duplicate: one row, one player); a toggle
on the boards removes them when the reader is looking at a team.

### The two files carry different rosters

292 pick rows against 295 shot rows: **288 players in both, 4 in the picks file
only, 7 in the shooting file only, 299 in total.** The join is explicit, on
`player_id` and never on `player_name`, and its provenance is kept in a `source`
column rather than assumed away. The shortlist joins outer, because dropping either
side would quietly narrow the search; the boards load only the file their lens
needs.

Player names happen to be unique in both files, but the id is still the key —
uniqueness in one season is not a guarantee.

### One thing the data does very well

`metric_glossary.csv` describes **every column of both files, with no orphan rows
in either direction** — 599 + 228 = 827, exactly. That is what makes it safe to
treat the glossary as the single naming authority: every header, tooltip, criterion,
radar spoke and card tile in the app prints the column's own `display_name`, so the
interface cannot say one thing where the data dictionary says another, and a reader
moving between the app and the CSV never has to translate.

---

## 5. How the code is organised

Data work and interface are separated by directory, not by intention:

```
app.py                  entry point: page config and navigation, nothing else
pages/                  one view per file — widgets, calls into src, rendering
src/
  data/    schema.py    every raw column name, in one place
           glossary.py  metric_glossary.csv: display names, definitions, units
           loader.py    reading the CSVs and joining them on player_id
  core/    metrics.py   the vocabulary, and every rate's denominator
           shot_views.py / pick_views.py / catalogue.py    the views themselves
           aggregate.py derived columns; pure functions
           thresholds.py two-stage filtering and slider bounds
           ranking.py   eligibility, percentiles, two-tier sort, pinning
           shortlist.py criteria, pools, percentile bars
           profile.py   the radar axes and the floor spots
  ui/      board.py     the shared page body — one board cannot drift from the other
           filters.py charts.py tables.py columns.py results.py
           panel.py detail.py facets.py profile_charts.py
           selection.py which player is loaded
           sorting.py   which column the table is ordered on
           navigation.py format.py theme.py
tests/                  the core only; no Streamlit widget is tested
data/                   the three source CSVs, read-only
```

Rules the code holds to:

* **No pandas in `pages/`.** A page reads widgets, calls `src`, renders. Any
  `groupby`, ratio, quantile or boolean mask lives in `src/core`. A page is a title
  plus one call to `board.render(...)`.
* **No column-name string outside `src/data/schema.py`**, and the 599 pick column
  names are *constructed* (`schema.pick_column(role, metric, coverage=…)`) rather
  than typed.
* **No `st.*` outside `src/ui/` and `pages/`.** Core functions take a DataFrame and
  return a new one; nothing cached is ever mutated in place.
* **No column label written by hand.** `Column`, `Threshold` and the radar `Axis`
  have no `label` field — it is a property that asks the glossary. The nine columns
  the app computes itself carry a name *and* a definition in
  `src/data/glossary.py`, written in the dictionary's own style, and a test fails if
  a displayed column has neither. Only the sentences are hand-written — plot axis
  labels, quadrant names, view descriptions — because no data dictionary supplies
  those.
* **A board does not repeat in its headers what its own controls already say.**
  `Screener - Points Per Pick (vs Soft (Drop))` spends 28 of its 32 characters
  repeating the lens selector and the view selector directly above it, and seven of
  those across is a table nobody can read without scrolling sideways. The role and
  the coverage come off where the board states them — the coverage only on a view
  that is *about* one coverage — and both stay in the tooltip. **The shortlist keeps
  the names whole**, since both roles are listed there and the prefix is the only
  thing separating two columns called *Points Per Pick*.
* **Caching where it pays**: reading the CSVs, parsing the glossary, and the column
  catalogue (which is configuration, not data). Nothing that depends on a slider is
  cached.
* **Interface language stays plain.** No "sample size", "regularised" or "n≥" on
  screen; the reader sees games, shots and picks. *Percentile* is the single
  statistical word allowed through, because it is the working vocabulary of
  basketball scouting — and it is printed in ordinal form (*86th of 174*). The
  statistics live in this README.

`pytest -q` runs 66 tests over the core: the denominator map, eligibility,
percentiles on the scope bar's pool, the two-tier sort, the feet-to-metres
conversion, the mid-range sum, the glossary naming rules, the notch rule on every
default, the coverage shares — measured back off the CSVs, so the split bars cannot
go stale — and the colour ramp the shot chart shares with the shot menu.
