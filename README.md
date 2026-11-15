# Dip-Leg cbBTC Bot — btc-race-24h-20261115-0828

![btc-race-24h-20261115-0828](https://make.fun/badge/btc-race-24h-20261115-0828.svg)
![rank](https://make.fun/badge/btc-race-24h-20261115-0828/tiVan0/btc-race-24h-20261115-0828/rank.svg)
![reward](https://make.fun/badge/btc-race-24h-20261115-0828/tiVan0/btc-race-24h-20261115-0828/reward.svg)

Entry for the [make.fun bounty btc-race-24h-20261115-0828](https://make.fun/bounty/btc-race-24h-20261115-0828): a long-only cbBTC trading bot racing 24 hours of minute bars on $1,000 of paper money.

## Strategy

The dev window is one slow grind down (-4.00% open-to-close) with a single sharp trough and a +5.1% bounce off it. This bot buys the trough and rides the bounce, in three legs (at most four round trips):

- **Leg A — flush.** Buy full size when the close sits ≥ 4.0% below the 240-bar high and RSI(14, simple-mean) ≤ 25. Exits: take profit +4.5%, trail 1.5%, stop -2.0%, RSI ≥ 85 once up ≥ +1.0%, max hold 400 bars.
- **Leg B — pullback** (only after the leg-A round trip). Buy on a dip ≥ 1.5% off the 120-bar high with RSI ≤ 28 and the close ≥ 0.5% above the 240-bar low. Exit: RSI ≥ 85 once up ≥ +1.8%.
- **Leg C — scalp** (after two round trips). Buy on a dip ≥ 2.6% off the 120-bar high with RSI ≤ 40 on the first up-bar. Exits: take profit +1.0%, trail 1.0%, stop -1.5%, RSI ≥ 80 once up ≥ +1.0%, max hold 150 bars.

## Dev result

Protocol-exact local replay of the published dev bars, run twice with byte-identical action logs:

| metric | value |
|---|---|
| Net PnL | **+$47.52** |
| Trades | 2 (1 round trip) |
| Fees | $0.82 |
| Max drawdown | 0.53% |

The single trade buys the trough (decided bar 1031, fill ~$62,327) and sells near the bounce peak (decided bar 1113, fill ~$65,341, +4.84% gross) via the +4.5% take-profit. Legs B/C never fire in the dev window. Buy-and-hold on the same window is about -$40; the unretuned base scores $0.00 / 0 trades.

## Files

- `main.py` — the bot (stdlib-only Python 3.13, deterministic, no network/clock/files)
- `vendor/makefun_bars.py` — the kit's bars-replay shim, copied verbatim
- `STRATEGY.md` — short write-up of the idea and its robustness
- `LICENSE` — MIT

## Running it locally

```sh
python3 driver.py --bot <this repo> --bars <dev bars CBBTC.ndjson.gz> --twice
```
