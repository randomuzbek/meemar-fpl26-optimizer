# The scoring model, and what it does to search strategy

## The formula

Each benchmark scores

```
score = max(0, α − 0.1·α·(β + γ))
```

- **α** — f_max improvement in MHz, output minus input
- **β** — LLM spend in US dollars for that benchmark
- **γ** — wall-clock hours for that benchmark, clamped at 1.0 (a hard 3600-second cap)

The suite total is the sum. The hidden-suite ranking is the arithmetic mean of per-benchmark
ranks, which is a different quantity and is discussed at the end.

The differential form is the one worth internalising:

```
Δscore = Δα − 0.1·α·(Δβ + Δγ)
```

## Consequence 1: a dollar costs exactly what an hour costs

β and γ enter the formula through the same coefficient. One dollar of model spend and one hour of
wall clock are charged identically. There is no exchange rate to reason about and no separate
budget to balance — there is one resource, and its price is `0.1·α` per unit.

## Consequence 2: the price of a second is proportional to α

This is the counter-intuitive one, and it is where a full day of optimization work went in the
wrong direction before the arithmetic was done properly.

Since γ is charged as `0.1·α·hours`, a second is worth the most on the designs that are **already
fast and high-α** — not on the slowest benchmark. Concretely, from the public suite:

| design | wall clock | α | γ cost in points |
|---|---|---|---|
| a 442-second, α = 103 design | 442 s | 103 | **1.246** |
| a 3600-second, α = 12.5 design | 3600 s | 12.5 | 1.167 |

The fast design burns *more* points on runtime than the one that runs eight times longer, purely
because its α is eight times higher. A second saved on the fast design is worth roughly **8×** a
second saved on the slow one.

Every intuition says to hunt for savings on the slowest benchmark. Every one of those candidates
priced out at 0.01–0.1 points. The question to ask before looking for seconds anywhere is *what is
α on this design?*

This also generalises in the right direction: on a hidden suite, the designs where a prepass finds
a large improvement are exactly the high-α ones, so runtime work aimed at them transfers.

## Consequence 3: the γ cap is a cliff, not a slope

γ is clamped at 1.0 hour, and the evaluation stops the run at 3600 seconds. The naive reading is
that exceeding the cap costs at most the γ term — bounded, and small on a low-α design.

That reading is wrong, and it is the most expensive mistake available in this contest. A run
truncated at 3600 seconds loses **everything it had not yet banked**. Measured on the public
suite: a benchmark finishing in 3388–3451 s hit the cap on a roughly 6 % slower evaluation
machine, and α fell from 12.539 to 9.976 — a loss of 2.381 points, where the γ term alone would
have been 1.167.

Two things follow.

**"It only costs γ, so it cannot lower α" is false near the cap.** Seconds added at the end of a
cap-adjacent run cost α outright.

**Machine speed is a confounder in every comparison.** The same measurement showed a benchmark
that no change of ours touched running 16 % slower on that instance. Before attributing any
difference to a change, check `wall_time_seconds` on a benchmark the change cannot affect.

The design response is `_autosave_best`: bank every improvement to disk the moment it is proven,
so that truncation costs the *unfinished* work only. On the final suite, the one benchmark that
did hit the cap had its last improvement at t = 3240 s and lost only the γ term.

## Consequence 4: price a runtime lane by what it lets finish

On a slow, low-α design the α term dominates the γ term by a wide margin. Saving 150 seconds is
worth about 0.05 points through γ; the 2.56 MHz that the run fails to bank when the cap truncates
it is worth about 2.4.

So seconds on such a design pay only if they change **which phase completes**, and that is decided
by placement, routing and physical optimization — not by report generation, checkpoint writes or
checkpoint opens. A runtime lane should be priced by the phase it unlocks, not by the seconds it
removes.

## Ranking is not scoring

The hidden suite ranks by the arithmetic mean of per-benchmark ranks, and points-per-rank varies
enormously across benchmarks — measured at **54×** between the least and most rank-dense benchmark
in the public suite. A change worth 0.5 points can be worth three ranks on one design and zero
ranks on another.

Rank density is also *local*: it depends on where the current score sits in the field, so a table
computed a week ago is not valid today. Any decision framed in points should be re-checked in
ranks, and any lane killed on points arithmetic deserves a second look in rank units. One lane
here was killed on points and only later shown to have been worth reopening in ranks.

## Where this lives in the code

`_gamma_fill_breakeven_mhz` implements the break-even directly: given the current α and a proposed
number of seconds, it returns the MHz the spend would have to produce in order to pay for itself.
`_gamma_aware_fill` will not spend below that threshold. The early exit after the deterministic
prepass is the same calculation applied to the whole model stage. See
[architecture.md](architecture.md).
