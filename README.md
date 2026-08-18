# Triple Threat

A local Streamlit app to explore player-level offensive tracking data from the
**2024-2025 Liga ACB** season. It is made for a basketball scout or analyst.

| Page | What it answers |
|---|---|
| **Shortlist** | *Who fits?* Stack the minimums a player has to clear, export the list, then open anyone on it and read his whole profile. |
| **Shot Quality Board** | *What kind of shots does he take? Are they hard? Does he make them?* |
| **Pick & Roll Board** | *Does a screen create an advantage for him, and what does he do with it?* |
| **Admin** | *What users search for: which pages, which players and which views get opened?* (§5) |

The shortlist opens the app, because a scout arrives with a search.

**One scope bar sits at the top of all three pages**: games played, shots taken, team, name,
traded. It keeps the same answers wherever you go, and it decides who counts as a league
player, so it is also what every percentile is measured against. The selected player follows
you too, so the three pages read as three angles on one profile.

**About 95% of the code was written with an AI assistant.** §7 explains it in detail.

---

## 1. Setup and run

```bash
pip install -r requirements.txt
streamlit run app.py
```
Python 3.10+

The three season CSVs ship with the repo, in `data/`, and they are the only source: **no API,
no database, no credentials, no network**. `data/` is read-only; the app never writes to it.

---

## 2. Which metrics, and why

### Two files, two ways to threaten a defence

The two datasets are not two halves of one thing. They are two independent axes:

* **`shots_offense`** — what kind of shot does he take, and does it go in? Distance, contest,
  who created it.
* **`picks_offense`** — what happens when a screen is set for him or by him?

A player can be excellent on one axis and invisible on the other, so there is one board per
axis and a shortlist that crosses them.

### Shooting: efficiency is never FG%

**eFG% and PPS (points per shot), never raw FG%.** A player taking 60% of his shots from three
cannot be compared to a rim finisher on FG%. `efg_percentage` counts the extra point of a
three; `points_per_shot` also includes free throws.

| Lens | The question | Plotted against | Minimum applies to |
|---|---|---|---|
| **Shot distance** | Which shots does he take? | Average distance vs points per shot | `attempts` |
| **Shot contestation** | Does he score with a defender on him? | Share of shots guarded vs efficiency on them | `contested_attempts` |
| **Shot creation** | Does he make his own shot? | Share off the dribble vs efficiency on them | `od_attempts` |

#### Guarded shooting is split by shot type

Ranking on contested eFG% puts big men on top: a contested layup is still a good shot, a
contested three is not.

So the Shot contestation lens splits into three: **All shots / Two-pointers / Threes**. The
three-point view is the cleanest read on shot-making under pressure, because it is the same
shot for everyone on the floor. All shots stays available, with the bias written on screen.

### Pick and roll: one lens per role

Ball handler and screener are two different jobs, and here almost two different populations:
of 292 players, only **four** record fifty picks in both roles. So the role is a lens, not a
filter. They also face different coverages (handler: Over / Under / Switch / Blitz / Ice;
screener: Show / Soft / Switch / Blitz / Ice).

| Lens | Plotted against | Minimum applies to |
|---|---|---|
| **Ball handler** | Picks he finishes himself vs points generated | `handler_total_picks`, then `handler_picks_vs_<coverage>` |
| **Screener** | Shots from three out of the screen vs points generated | `screener_total_picks`, then `screener_picks_vs_<coverage>` |

**Points per pick counts the points a teammate scored off his pass, not just his own basket.**
It measures the offence generated per screen. That is the right question for a ball handler
and the wrong one for comparing scorers, so it is never put next to `points_per_shot` from the
shooting file. The scorer-only figure is `{role}_points_per_shot_in_pick`.

Four columns carry most of the value of this board:

* **`handler_success_rate`** — the share of screens the tracking judges to have created an
  advantage, **whether or not the shot went in**.
* **`handler_pass_to_screener_pct`** — does he play with his roll man, or use the screen to
  hunt a kick-out?
* **`screener_assist_rate`** — the screener's pass out of the short roll.
* **`{role}_shot_rate_3pt`** — roller or popper, in one number.

### The card: what he did with the ball

A pick hands a player one possession, and there are four things he can do with it: take the
shot, give it up, create one for someone else, or lose it. Those four are the headline figures
on **every** pick view, whichever coverage is on screen, so the card always reads the same way.

| Reading | Ball handler | Screener |
|---|---|---|
| He takes the shot | `shot_taken_pct` | `shot_taken_pct` |
| What he does instead | `only_pass_pick_pct` — he passes out | `shot_rate_3pt` — he rolls or he pops |
| He creates a shot for a teammate | `assist_opportunity_pct` | `assist_opportunity_pct` |
| He loses it | `turnover_rate` | `turnover_rate` |

The second row differs because the jobs differ. A screener passes out of a screen about **once
in eighty picks** (league median), so what matters once he keeps it is whether he rolled to the
rim or popped for three.

### What I deliberately did not build

* **No composite score, no player rating.** Every number on screen is a CSV column, or a stated
  division of two of them. I like composite scores, but there was too little time to think one
  through.
* **No new "per game" metric.** The files already ship rates for almost everything. One pair is
  derived (`{role}_picks_per_game`) and **nothing is ranked or filtered on it**: with no minutes
  column (§4), a per-game number divides by games in which a player may have played two minutes
  or thirty.
* **No position-based comparison.** There is no position column (§4).

---

## 3. Filtering, thresholds and normalisation

This is where most of the analytical work went.

### 3.1 A minimum on games played protects nothing

A player can appear in 34 games and take **11 guarded threes** all season. His percentage on
those 11 shots is noise, and there is nothing worth analysing in it.

Hence the rule the whole app is built on:

> **The minimum applies to the count the displayed rate is made of, never to games played.**

Every rate names its own denominator in `DENOMINATORS` (`src/core/metrics.py`):

| Rate | Minimum applies to |
|---|---|
| `efg_percentage` | `attempts` |
| `contested_three_fg_percentage` | `contested_three_attempts` |
| `od_efg_percentage` | `od_attempts` |
| `rim_fg_percentage` | `rim_attempts` |
| `handler_ppp_vs_over` | `handler_picks_vs_over` |

### 3.2 Minimums and two-level filtering

| Level | Control | Question | Scope |
|---|---|---|---|
| **The whole dataset** | the scope bar: games played, shots taken, traded | *Which players are not to be considered in the dataset (and in the percentile calculation)?* | The whole app |
| **The sample inside it** | the view's own count | *Which players are hidden for now?* | Recomputed per metric and per split |

They are never merged. The first decides which players are admitted into the dataset and into
the percentile calculation, the second whether a number is worth showing.

The scope bar holds the same answers on all three pages, so narrowing the league on a board
narrows the shortlist too. The line under it says what it costs: *213 of 299 players are the
league here.*
Team and name search sit in the same bar but do **not** define the league, otherwise a reader
who typed a name would be ranked against himself (and the percentiles would be wrong).

### 3.3 The league bar: fifteen games, one shot a game

Both defaults are round numbers. The NBA three-point title needs **82 made threes**: one a game
over 82 games. It comes from no variance calculation, which is why it can be discussed.

I decided on one attempt per official game. Over a 34-round ACB regular season that is 34
shots, rounded up to **35** so it lands on a notch of a slider that moves five at a time. With
fifteen games beside it, **213 of the 299 players are kept**.
That number is easy to change, as the brief asks.

### 3.4 Pick and roll: one bar per role, then one per coverage

**10 picks for the ball handler, 20 for the screener.** A screener sets screens all game, a
handler runs the ones his team calls for him, so one bar for both would rank two jobs on a
single scale. At 10 and 20, 141 handlers and 150 screeners are measured, against 102 and 103 at
a common bar of 50.

**Then each pick-and-roll coverage split gets that bar cut to how often the league plays it.**

So the bar is `role bar × the coverage's league share`, rounded **down** to a notch the slider
can reach, never below 1. A test recomputes the shares off the files, so the constants cannot
go stale:

| Split | League share | Bar | Eligible (of the 213) |
|---|---|---|---|
| Ball handler vs Over | 66.7% | **5** | 122 |
| Ball handler vs Switch | 16.4% | **1** | 147 |
| Ball handler vs Under | 15.9% | **1** | 143 |
| Ball handler vs Ice | 0.6% | **1** | 67 |
| Ball handler vs Blitz | 0.3% | **1** | 45 |
| Screener vs Show | 45.1% | **5** | 142 |
| Screener vs Soft (drop) | 37.1% | **5** | 145 |
| Screener vs Switch | 16.4% | **1** | 198 |
| Screener vs Ice | 0.6% | **1** | 55 |
| Screener vs Blitz | 0.3% | **1** | 37 |

### 3.5 The controls

**Every bar belongs to the reader.** The defaults are opinions, written here and moveable on
screen:

* The **scope bar**: five controls at the top of every page, always visible, with the league
  count written under it.
* The **view minimum**: one slider per view, in a panel under it, running from 0 to the highest
  value actually present in the CSV for that column.
* Sliders step in fives, so **every default sits on a notch it can return to**.
* The panel is **collapsed with its defaults applied**, so the board is useful without ever
  opening it.
* Under it, a **`Show players below the minimum` toggle**, left on by default. Hiding them would
  hide the reason they are not comparable.

### 3.6 Percentiles: one pool, everywhere

A percentile places a number against the league. A scout reads *86th percentile* faster than
*0.412*.

**The pool is the scope bar's league, on every page, view, figure and radar spoke.**

* **Percentiles are computed on every run, never read from a file.** A stored one would be stale
  as soon as the scope bar moves, and writing to `data/` is not allowed anyway. `rank(pct=True)`
  on 300 rows costs microseconds.
* **Counts are turned into percentiles too**, not just rates: shots, threes, picks, games.
  *615 picks* means nothing until it is also *96th in the league*.
* **Values and percentiles give the same order**, since a percentile is the raw value
  re-expressed against the same pool. The switch changes what is printed, not who comes first.

### 3.7 A blank is not a low number

**Missing values stay at the bottom of a column whichever way it is sorted.** The grid's own
sorting floats empty cells to the top of an ascending column, which reads as *these players are
the worst at this*. A player with no picks against the blitz has no number at all.

So both tables set their own row order. Turning on column selection in `st.dataframe` disables
its built-in sorting, so a header click arrives as an event and the app sorts with
`na_position="last"` in both directions. That is also what keeps greyed players under measured
ones on the boards. The line under each table says so.

### 3.8 Normalisation

**Rate and volume stay apart, and the count is always on screen**, next to the rate it produced.

**Shares carry no minimum.** `rim_attempt_rate`, the pick spots on the floor, the coverage
breakdown — these describe *what a player does*, not how well he does it, and a breakdown of 40
attempts is still an accurate breakdown of 40 attempts. Only accuracy figures are gated, and a
total is never gated: a total is a total.

**No per-36 or per-40.** Neither file has a minutes column (§4), so it is impossible, not a
design choice. Everything is per shot, per pick or per game.

**Ratios stay on their 0–1 scale in the code**; multiplying by 100 happens in
`src/ui/format.py` and nowhere else.

Five derived normalisations:

| Derived | How | Why not the obvious way |
|---|---|---|
| `avg_shot_distance` → metres | × 0.3048 | The column is stored in feet despite its glossary label (§4). The raw column is never overwritten. |
| Mid-range share | `short_midrange_paint_attempt_rate + long_midrange_attempt_rate` | **Not** `100 − rim − three`. The four zones only cover ~97% of attempts, so the subtraction would inflate the mid-range by 3 to 9 points. |
| Coverage share | `picks_vs_<coverage> / total_picks` | The file ships a share per floor spot but **none per coverage**, though both counts are there to divide. |
| Contested 2PT / 3PT share | `contested_X_attempts / X_attempts` | The file ships the contested share of *all* shots only, which mixes layups and threes. |
| Assisted share | `assisted_shots / mades` | A count in the file, a share nowhere. |

Every division goes through `safe_ratio`, which returns **NaN, not 0**, on a zero denominator: a
player who never took a corner three has an *unknown* corner-three percentage, not a 0% one.

**Median lines are drawn on the scope bar's league, and among the players measured inside it.**
Same pool as the percentiles, so a card's two references agree. And each line is the median
*among players clearing that slice's own count*: `screener_ppp_at_stepUp` has a median of **0.09**
over the whole file, but **0.32** among players with at least 25 picks there. The first is
dragged down by players with two or three step-up screens who scored on none of them.

### 3.9 Regression to the mean: considered, then dropped

Shrinking each percentage toward the league average — adding a few phantom league-average
attempts to every player — was my first idea for small samples. I dropped it:

* **Scouting tools work on thresholds.** Synergy, InStat and the public leaderboards all gate;
  none publishes a shrunk percentage as *the* number.
* **A threshold can be explained to a coach.** "39% from three on 120 attempts" survives a
  conversation; "his regularised three-point percentage is 36.8%" does not.
* **The shrunk value is not the player's value.** It estimates his true level, which is a
  different question from the one a shot chart answers.
* **It filters anyway, but invisibly**: a 5-attempt player pulled to the league mean looks
  *average*, not *unmeasured*, which is worse than a greyed row.

### 3.10 Filtering on the shortlist

**A bar can be set as a value or as a place in the league**, and the line under it states both:
*39.5% — 80th percentile, keeping the top 20% of the 125 players who have this number*.
Percentages are typed as percentages, and the box opens on the median rather than at zero. A rate
opens in percentile mode ("the top 20%" is the question a scout arrives with).

---

## 4. Assumptions, and limits found in the data

### `avg_shot_distance` is stored in feet, not metres

The glossary labels it *metres*. The distribution says otherwise: the **median** player averages
**14.43**. Read as metres, the median shot in this league would come from beyond half court, on a
28-metre floor.

Read as feet everything lines up. Among the 234 players clearing 35 attempts, the deepest averages
**22.20 ft = 6.77 m** — the FIBA three-point line (6.75 m) to the centimetre — and the most
rim-bound averages **3.27 ft = 1.00 m**, a layup. The app converts before display, leaves the raw
column untouched, and a test guards the conversion.

### Blitz and ice are rare coverages in the ACB

Across all 292 players the highest count is **5 picks against a blitz** (both roles) and **7 / 9
against an ice**, with medians of 0. This is not missing data: Spanish defences play them very
little.

They are shown like every other coverage, with a low default bar and a note on screen saying the
coverage is rare. *How does he handle a blitz?* is a real scouting question, so hiding the split
would leave it unanswered.

### No position column, and no minutes column

* **No position.** The closest stand-in is the ball handler / screener split, which is very nearly
  disjoint (only 4 of 292 players record 50+ picks in both roles). It is shown on the card and
  never used to filter silently. So **"compare him to other bigs" is not a question this app can
  answer**.
* **No minutes.** Nothing can be normalised per 36 or per 40 minutes. `games_played` counts games
  with **at least one tracked event in that file**, which is not playing time.

### `games_played` runs from 1 to 44

For a 34-round regular season: the top of the range includes play-offs. So 34 is the **length of
the regular season** and is only used to express "one shot per game"; it is never a maximum, and
no total is hard-coded anywhere. `games_played` and `appearances` are identical row for row in
both files, so only one is exposed.

### The splits do not add up to the total

**None of the shot splits sum back to total attempts**, because some shots carry no
classification:

| Split | Coverage of total attempts | Worst single player |
|---|---|---|
| Contested + uncontested | 97.5% (1 059 shots unclassified) | 15 shots missing |
| Catch & shoot + off the dribble | 94.1% (2 494 shots) | 31 shots |
| The 5 NBA zones | 96.8% | 25% of his attempts |
| The 4 SkillCorner zones | 96.8% | — |
| The 5 contest levels | 97.5% | 15 shots |
| The 14 shot types | 97.5% | 15 shots |

So shares are always computed against the **total**, legitimately fall short of 100% and are
never renormalised; the mid-range share is a **sum of two zones, never `100 − rim − three`**; and
the shot chart is described as covering *most* of a player's attempts.

Two splits do add up: two-pointers plus three-pointers equal total attempts exactly for all 295
players, and the five coverages account for 98–100% of a player's picks, which is what makes a
100% stacked bar the right shape for the coverage figure.

### eFG% goes above 1.0, but not on the column you would expect

`efg_percentage` itself tops out at exactly **1.00** (two players, on 6 and 3 shots all season).
The split columns go higher: **`cns_efg_percentage` reaches 1.50**, and contested and uncontested
eFG both reach 1.25 — all three on **two attempts**. eFG can reach 1.5 when every shot is made and
every one is a three, so nothing is clipped at 1.

These values are also the best illustration of why the minimum exists: every one of them belongs
to a player the 35-shot bar removes from the ranking.

### Zero and missing are correctly separated in the source

A player with no picks as ball handler carries **NaN** in `handler_ppp`, not 0 (72 players). The
243 players who never faced a blitz carry NaN in `handler_ppp_vs_blitz`, and the 201 who never
attempted a heave carry NaN in `cst_heave_fg_percentage`, not 0%.

So the app's own divisions return NaN on a zero denominator (`safe_ratio`), and NaN prints as a
blank. Treating the two as the same would turn "never tried" into "tried and failed" on every
card in the app.

### Dead and near-empty columns

* **24 pick columns never carry a number.** 23 are zero for every player, including the whole
  `no_outcome_pick` family and `screener_ft_attempts_in_pick` — so the screener's points-per-shot
  in pick is field-goal only, while `handler_ft_attempts_in_pick` reaches 79. The twenty-fourth,
  `handler_fg2_pct_vs_blitz`, is empty in every row. None is displayed.
* **89 of the 599 pick columns are over half empty**, almost all rare coverage × metric.
* **4 shot columns are zero for every player**: `cl_blocked_mades`, `_points`, `_fg_percentage`,
  `_points_per_shot`. That is correct rather than a defect — a blocked shot is by definition not
  made — and it is why "blocked" is treated as a contest level and not as a shot outcome.

### Traded players hold one row each

Eight players changed team during the season. The glossary confirms the row still aggregates their
whole season, while `team_name` shows only the last club, so a team-level total would count them in
the wrong place. **They are not de-duplicated** (one row, one player); a toggle on the boards
removes them when the reader is looking at a team.

### The two files carry different rosters

292 pick rows against 295 shot rows: **288 players in both, 4 in the picks file only, 7 in the
shooting file only, 299 in total.** The join is explicit, on `player_id` and never on
`player_name`, and where each row came from is kept in a `source` column. The shortlist joins
outer, because dropping either side would narrow the search. A board loads its own file plus
**exactly one column from the other**: the season shot total, so the scope bar can ask its second
question on every page. The 4 players who exist only in the picks file therefore fall outside a
scope that asks for shots, which is right, since they have no shooting events.

Player names happen to be unique in both files, but the id is still the key.

### The glossary covers every column

`metric_glossary.csv` describes **every column of both files, with no orphan rows in either
direction** — 599 + 228 = 827, exactly. That is what makes it safe to treat the glossary as the
single naming authority: every header, tooltip, criterion, radar spoke and card tile prints the
column's own `display_name`, so the interface cannot say one thing where the data dictionary says
another.

---

## 5. The admin page

A prototype for whoever owns the tool: what it is used for, and whether the opinions baked into it
are right.

### A disclosure, and it belongs at the top of this section

**This page was designed by an AI assistant, not by me.** I have very little experience with
product analytics, so rather than guess, I described the app and asked the assistant which
readings were worth putting on screen. I reviewed what came back and kept it.

§7 says how the whole repository was written, and most of the code came from the same assistant.
The difference is that everywhere else I made the calls: the thresholds and why they sit where they
do, which pool percentiles are measured on, the rule that no label is ever typed by hand. Here I
made none.

### What is on the page

Each block answers a decision rather than filling space.

| Block | What it shows | The decision behind it |
|---|---|---|
| **Journal** | Where the file is, how many screens it holds, and a **Record this session** checkbox that stops the writing. | Recording has to be visible and reversible. |
| **Activity** | Sessions, screens, median session length and screens per session, over a daily chart. | Is anyone using it, and do they stay? |
| **Which views are used** | The ten most-visited page-and-view pairs. | A lens nobody ever selects is a lens to rethink — invisible from inside the code. |
| **Who gets opened** | The ten players opened in the most sessions. | The closest thing here to interest in a player. |
| **Are the bars set where they should be?** | Two tables — the scope bar, then one row per view — with what it opens on, the median choice, how often it was moved, and a plain reading. | The main reason for the page. |
| **Did the visit go anywhere?** | Sessions → narrowed something → opened a player. | A session that stops at step one found nothing, or could not work out how to. |
| **Recent sessions** | A folded table: when each session ran, how long, how many screens, pages and players. | Enough detail to check a strange day. |

**The threshold reading is the main block.** Every default in this README is a guess written into
the source. If readers move the same slider the same way every time, the guess is wrong, and only
a record of what they did can show it. So the table prints, per view, what it opens on, the median
choice, how often it was moved, and a sentence saying what to do: *"Moved up most of the time —
consider 25"*, or *"Left alone — the default holds"*.

**It runs on a local journal and nothing else.** One JSONL line per state a reader put the app in,
appended to `logs/usage.jsonl` — never to `data/`, and the folder is out of version control. No
network call, no account, no login. The only identifier is a **random twelve-character string drawn
once per browser session**, and the search box is never written down: the journal records *that* a
name was searched for, never which.

**One line per state, not per rerun.** Streamlit re-runs the whole script on every widget touch, so
writing unconditionally would fill the file with copies of the same screen. Each event is compared
with the last one written and dropped if it matches, so a line means the reader changed something.

`src/data/usage.py` is pure functions over one frame plus a single append; `src/ui/tracking.py` owns
the session identifier and calls it; the page only reads and renders. A failed append is ignored,
so a logging problem cannot break the app.

---

## 6. How the code is organised

Data work and interface are separated by directory, not by intention:

```
app.py                  entry point: page config and navigation, nothing else
pages/                  one view per file — widgets, calls into src, rendering
src/
  data/    schema.py    every raw column name, in one place
           glossary.py  metric_glossary.csv: display names, definitions, units
           loader.py    reading the CSVs and joining them on player_id
           usage.py     the local journal: one append, everything else pure
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
           criteria.py  the shortlist's stacked bars
           selection.py which player is loaded
           sorting.py   which column the table is ordered on
           tracking.py  the session identifier, and what is worth recording
           navigation.py format.py theme.py usage_charts.py
tests/                  the core only; no Streamlit widget is tested
data/                   the three source CSVs, read-only
logs/                   the usage journal; out of version control
```

Rules the code holds to:

* **No pandas in `pages/`.** A page reads widgets, calls `src`, renders. Any `groupby`, ratio,
  quantile or boolean mask lives in `src/core`. A page is a title plus one call to
  `board.render(...)`.
* **No column-name string outside `src/data/schema.py`**, and the 599 pick column names are *built*
  (`schema.pick_column(role, metric, coverage=…)`) rather than typed.
* **No `st.*` outside `src/ui/` and `pages/`, with one exception**: the `@st.cache_data` decorator
  on the five CSV reads in `src/data/`. Core functions take a DataFrame and return a new one;
  nothing cached is ever mutated in place.
* **No column label written by hand.** `Column`, `Threshold` and the radar `Axis` have no `label`
  field — it is a property that asks the glossary. The nineteen columns the app computes itself
  carry a name *and* a definition in `src/data/glossary.py`, and a test fails if a displayed column
  has neither. Only the sentences are hand-written — axis labels, quadrant names, view descriptions
  — because no data dictionary supplies those.
* **A board does not repeat in its headers what its own controls already say.**
  `Screener - Points Per Pick (vs Soft (Drop))` spends 28 of its 32 characters repeating the two
  selectors above it, and seven of those across need sideways scrolling. The role and the
  coverage come off, and both stay in the tooltip. **The shortlist keeps the names whole**, since
  both roles are listed there and the prefix is the only thing separating two columns called
  *Points Per Pick*.
* **What is cached**: reading the CSVs, parsing the glossary, and the column catalogue, which is
  configuration rather than data. Nothing that depends on a slider is cached.
* **Interface language stays plain.** No "sample size", "regularised" or "n≥" on screen; the reader
  sees games, shots and picks. *Percentile* is the one statistical word allowed through, because it
  is the working vocabulary of basketball scouting, and it is printed in ordinal form (*86th
  percentile*). The statistics live in this README.

---

## 7. How this was built

**About 95% of the code in this repository was written by an AI assistant (Claude Code). I decided
what it had to do.** The job posting I applied to says AI-assisted development is part of how the
team works, so this was not a problem for me, but I would rather write it down than let it be
assumed.

### Why I worked this way

I had never used Streamlit before this test. The brief suggests around six hours; I am closer to
eight. Learning the framework by hand would have come out of the analysis, which is the biggest part
of the grade. I would still have preferred my hands on more of the code, as I normally work.

### Who decided what

**Mine.** Which metrics reach the screen and which are dropped. Where every bar sits and what it
counts. One percentile pool instead of three. What each page shows, and in what order. And what got
sent back: the tinted percentile columns, the panel of minimums on the shortlist and the second
condition hidden inside a criterion were all built, then removed on my call.

**The assistant's.** The exploration passes over the CSVs, and every line of Streamlit and Plotly.

This README was written the same way: I wrote it in French with Claude's help, then had Claude
translate it into English, which was faster than writing it twice.

One rule I set at the start: **modular code, split across files by what it does, and no analysis
inside a page file.** §6 is that rule written out. It is the part that goes wrong first in an
AI-written repo, because a model will keep appending to one long script.

### The two things I watched for

**Speed.** This is the real risk, and I ran into it. The glossary was re-parsed for every tooltip,
around 300 rebuilds per rerun and 293 ms, until it was indexed once at 2.4 ms.

**Security.** There is very little surface here. No network call, no database, no credential, no
login, no path or query typed by a user. The three CSVs ship with the repo and are only ever read.
The one thing the app writes is its own usage journal: a local JSONL file, out of version control.
