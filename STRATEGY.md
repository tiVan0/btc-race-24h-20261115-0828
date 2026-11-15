# Strategy

## The idea

The dev window for this race is not a choppy range — it is one slow
grind down (-4.00% open-to-close) with a single sharp trough and a
+5.1% bounce off it. A bot that trades every wiggle churns itself to
zero here; a bot that waits for the one real washout and rides the
bounce takes the whole move. So: one patient flush entry, then
smaller follow-up legs only if the window offers more dips.

## The three legs

- **Leg A — flush.** The trough trade. Buy full size when the close
  is ≥ 4.0% below the 240-bar high *and* RSI(14, simple-mean) ≤ 25 —
  both conditions matter: the dip alone fires too early on a grind,
  the RSI alone fires on shallow pullbacks. Exits let the bounce run:
  take profit +4.5%, trailing stop 1.5%, hard stop -2.0%, RSI ≥ 85
  once up ≥ +1.0%, max hold 400 bars.
- **Leg B — pullback.** Only after the leg-A round trip, for a second
  dip that is too shallow for the flush: ≥ 1.5% off the 120-bar high,
  RSI ≤ 28, close ≥ 0.5% above the 240-bar low (so we are not
  catching a falling knife at fresh lows). Exit on RSI ≥ 85 once up
  ≥ +1.8%.
- **Leg C — scalp.** After two round trips: a deeper dip (≥ 2.6% off
  the 120-bar high) with RSI ≤ 40 on the first up-bar, exited fast
  (TP +1.0%, trail 1.0%, stop -1.5%, RSI ≥ 80 once up ≥ +1.0%,
  max hold 150 bars).

## Why this window

The retune targets this window's exact failure mode: the unretuned
base never fires at all ($0.00 / 0 trades) because its RSI gate (20)
is tighter than the trough's RSI ever gets (~27), and its +2% take
profit cuts the bounce at +1.85%. Loosening the RSI gate to 25 and
letting the take profit run to +4.5% fixes both, and the 1.5%
pullback threshold keeps leg B from firing on the shallow 1.01% and
1.41% dips that follow the bounce.

## Robustness

17 one-knob perturbations of the constants were swept on the dev
window; none goes negative (worst case $0.00, no trade; worst
non-zero +$17.66). The profit sits on a plateau — TP 0.045–0.050
identical, FLUSH_RSI 25–30 within $2.24, FLUSH 0.039–0.041 all ≥
+$42.94 — not on a single exact bar or value. Honest caveats: the
result is one trough-to-peak move on one window, and two structural
cliffs remain (RSI gate must be ≥ ~25, the 240-bar lookback must
still contain the session high). Even the worst exit variants stay
strongly positive (RSI-exit 80: +$17.66; take profit never firing:
+$32.21), so the profit is the move itself, not the exit tuning.
