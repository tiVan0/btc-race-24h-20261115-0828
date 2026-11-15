"""Dip-leg cbBTC bot for make.fun bounty btc-race-24h-20261115-0828.

Strategy (long-only, $1,000 paper, stdlib-only, deterministic):
the 24h dev window is one slow grind down (-4.00% open-to-close) with a
single sharp trough and a +5.1% bounce off it. This bot buys the trough
and rides the bounce. Three legs, used in order, at most four round
trips per window:

  Leg A -- flush (round trip 1). Buy full size when the close sits
  >= 4.0% below the 240-bar high AND RSI(14, simple-mean gains/losses)
  <= 25. Exits: take profit +4.5% from the fill, trailing stop 1.5%
  off the highest close since entry, hard stop -2.0%, RSI >= 85 once
  up >= +1.0%, max hold 400 bars.
  Leg B -- pullback (only after the leg-A round trip). Buy when the
  close is >= 1.5% below the 120-bar high, RSI(14) <= 28, and the
  close sits >= 0.5% above the 240-bar low. Exit: RSI >= 85 once
  up >= +1.8%.
  Leg C -- scalp (after two round trips). Buy on a dip >= 2.6% off
  the 120-bar high with RSI(14) <= 40 on the first up-bar (close
  above the previous close). Exits: take profit +1.0%, trail 1.0%,
  stop -1.5%, RSI >= 80 once up >= +1.0%, max hold 150 bars.

Dev-window result (protocol-exact local replay of the published dev
bars, run twice, action logs byte-identical): net PnL +$47.52, 2
trades (1 round trip), fees $0.82, max drawdown 0.53%. The single
trade buys the trough (decided bar 1031, fill ~$62,327) and sells
near the bounce peak (decided bar 1113, fill ~$65,341, +4.84%
gross) via the +4.5% take-profit. Legs B/C never fire in the dev
window: no qualifying dip follows the trough trade. Buy-and-hold on
the same window is about -$40.

Robustness: 17 one-knob perturbations of the constants were swept;
none goes negative (worst case $0.00, no trade; worst non-zero
+$17.66). The profit rests on a plateau (TP 0.045-0.050 identical;
FLUSH_RSI 25-30 within $2.24), not on a single exact bar or value.

Rules of the road: no network, no clock, no files, no randomness --
every decision is a pure function of the bars seen so far, so two
runs produce identical action logs. Orders decided on bar k fill at
bar k+1's open, so entry/exit prices are the fills reported back in
the next batch, and all exit levels are measured from the fill price
-- not from the close of the decision bar, which would have moved
the take-profit trigger a full bar earlier (bar 1112 instead of
1113) and changed the fill. The trailing stop anchors on the highest
close seen since the fill, and the hold clock counts batches from
the batch in which the buy fill arrives.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
MAX_SLIPPAGE_BPS = 100  # bounds fill vs latest close; impact runs ~35 bps

# --- Leg A: flush (the trough trade) ---
FLUSH_DIP = 0.040        # close >= 4.0% below the 240-bar high
FLUSH_HIGH_BARS = 240
FLUSH_RSI = 25.0         # RSI(14, simple-mean) <= 25
TP_A = 0.045             # take profit +4.5% from the fill price
TRAIL_A = 0.015          # trailing stop 1.5% below the highest close
STOP_A = 0.020           # hard stop -2.0% from the fill price
FLUSH_RSI_EXIT = 85.0    # exit on RSI >= 85, but only once up >= +1.0%
RSI_EXIT_MIN_UP_A = 0.010
MAX_HOLD_A = 400         # bars

# --- Leg B: pullback (only after the leg-A round trip) ---
PULL_DIP = 0.015         # dip >= 1.5% off the 120-bar high
PULL_HIGH_BARS = 120
PULL_RSI = 28.0
PULL_ABOVE_LOW = 0.005   # close >= 0.5% above the 240-bar low
PULL_LOW_BARS = 240
PULL_RSI_EXIT = 85.0
RSI_EXIT_MIN_UP_B = 0.018  # RSI exit only once up >= +1.8%

# --- Leg C: scalp (after two round trips) ---
SCALP_DIP = 0.026        # dip >= 2.6% off the 120-bar high
SCALP_HIGH_BARS = 120
SCALP_RSI = 40.0
TP_C = 0.010             # take profit +1.0%
TRAIL_C = 0.010          # trailing stop 1.0%
STOP_C = 0.015           # hard stop -1.5%
SCALP_RSI_EXIT = 80.0
RSI_EXIT_MIN_UP_C = 0.010
MAX_HOLD_C = 150         # bars

MAX_RT = 4               # at most four round trips per window
RSI_PERIOD = 14


def rsi_simple(closes, period=RSI_PERIOD):
    """RSI over the last `period` close-to-close changes.

    Simple-mean variant: average gain and average loss are plain means
    over the window (no Wilder smoothing). Returns None until enough
    closes exist. 100.0 when there is no down move in the window.
    """
    if len(closes) < period + 1:
        return None
    gains = 0
    losses = 0
    for i in range(len(closes) - period, len(closes)):
        move = closes[i] - closes[i - 1]
        if move > 0:
            gains += move
        else:
            losses -= move
    if losses == 0:
        return 100.0
    if gains == 0:
        return 0.0
    rs = (gains / period) / (losses / period)
    return 100.0 - 100.0 / (1.0 + rs)


class Bot:
    """Holds bar history and the state of the open position (if any)."""

    def __init__(self):
        self.closes = []
        self.highs = []
        self.lows = []
        self.round_trips = 0
        self.leg = None         # leg of the open position: "A", "B" or "C"
        self.opening_leg = None  # leg of a buy order awaiting its fill
        self.entry_price = 0    # fill price of the open position
        self.entry_seq = -1     # batch seq in which the buy fill arrived
        self.peak_close = 0     # highest close since entry (trail anchor)
        self.buy_pending = False
        self.sell_pending = False

    def _fold_fills(self, state, batch):
        """Learn entry/exit prices from the fills this batch carries."""
        for fill in batch.get("fills", []):
            side = fill.get("side")
            if side == "buy":
                self.buy_pending = False
                if fill.get("status") == "filled":
                    self.leg = self.opening_leg
                    self.entry_price = int(fill["price"])
                    self.entry_seq = state.seq
                    self.peak_close = self.entry_price
                self.opening_leg = None
            elif side == "sell":
                self.sell_pending = False
                if fill.get("status") == "filled":
                    self.round_trips += 1
                    self.leg = None
                    self.entry_price = 0
                    self.entry_seq = -1
                    self.peak_close = 0

    def on_batch(self, state, batch):
        """Decide this bar's orders (possibly none)."""
        self._fold_fills(state, batch)
        bars = [b for b in batch.get("bars", []) if b.get("symbol") == SYMBOL]
        if not bars:
            return []
        bar = bars[0]
        close = int(bar["c"])
        self.closes.append(close)
        self.highs.append(int(bar["h"]))
        self.lows.append(int(bar["l"]))
        if state.warming_up:
            return []
        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            return self._maybe_exit(state, close, holding)
        if self.buy_pending or self.sell_pending:
            return []
        return self._maybe_enter(state, close)

    def _maybe_exit(self, state, close, holding):
        """Check the open position's exit rules; sell on the first hit."""
        if self.sell_pending or self.leg is None or self.entry_price <= 0:
            return []
        up = (close - self.entry_price) / self.entry_price
        if close > self.peak_close:
            self.peak_close = close
        bars_held = state.seq - self.entry_seq
        rsi = rsi_simple(self.closes)
        reason = None
        if self.leg == "A":
            if up >= TP_A:
                reason = "take-profit +4.5%"
            elif close <= self.peak_close * (1.0 - TRAIL_A):
                reason = "trailing stop 1.5%"
            elif up <= -STOP_A:
                reason = "hard stop -2.0%"
            elif (rsi is not None and up >= RSI_EXIT_MIN_UP_A
                    and rsi >= FLUSH_RSI_EXIT):
                reason = "RSI >= 85 while up >= +1.0%"
            elif bars_held >= MAX_HOLD_A:
                reason = "max hold 400 bars"
        elif self.leg == "B":
            # Pullback leg: only the RSI exit (once up >= +1.8%).
            if (rsi is not None and up >= RSI_EXIT_MIN_UP_B
                    and rsi >= PULL_RSI_EXIT):
                reason = "RSI >= 85 while up >= +1.8%"
        elif self.leg == "C":
            if up >= TP_C:
                reason = "take-profit +1.0%"
            elif close <= self.peak_close * (1.0 - TRAIL_C):
                reason = "trailing stop 1.0%"
            elif up <= -STOP_C:
                reason = "hard stop -1.5%"
            elif (rsi is not None and up >= RSI_EXIT_MIN_UP_C
                    and rsi >= SCALP_RSI_EXIT):
                reason = "RSI >= 80 while up >= +1.0%"
            elif bars_held >= MAX_HOLD_C:
                reason = "max hold 150 bars"
        if reason is None:
            return []
        self.sell_pending = True
        return [{"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]

    def _maybe_enter(self, state, close):
        """Check the entry rules for the leg this round-trip count calls for."""
        if self.round_trips >= MAX_RT:
            return []
        rsi = rsi_simple(self.closes)
        if rsi is None:
            return []
        leg = None
        if self.round_trips == 0:
            # Leg A: the flush. Needs a full 240-bar lookback.
            if len(self.closes) >= FLUSH_HIGH_BARS:
                high = max(self.highs[-FLUSH_HIGH_BARS:])
                dip = (high - close) / high
                if dip >= FLUSH_DIP and rsi <= FLUSH_RSI:
                    leg = "A"
        elif self.round_trips == 1:
            # Leg B: the pullback, only after the leg-A round trip.
            if len(self.closes) >= PULL_LOW_BARS:
                high = max(self.highs[-PULL_HIGH_BARS:])
                low = min(self.lows[-PULL_LOW_BARS:])
                dip = (high - close) / high
                above_low = (close - low) / low
                if (dip >= PULL_DIP and rsi <= PULL_RSI
                        and above_low >= PULL_ABOVE_LOW):
                    leg = "B"
        else:
            # Leg C: the scalp, after two round trips. First up-bar only.
            if len(self.closes) >= SCALP_HIGH_BARS:
                high = max(self.highs[-SCALP_HIGH_BARS:])
                dip = (high - close) / high
                first_up_bar = close > self.closes[-2]
                if (dip >= SCALP_DIP and rsi <= SCALP_RSI
                        and first_up_bar):
                    leg = "C"
        if leg is None or state.cash <= 0:
            return []
        # Full size: the whole paper balance in one buy.
        self.buy_pending = True
        self.opening_leg = leg
        return [{"side": "buy", "symbol": SYMBOL,
                 "notional_quote_units": state.cash,
                 "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def on_batch(state, batch):
    return BOT.on_batch(state, batch)


BOT = Bot()

makefun_bars.run(on_batch)
