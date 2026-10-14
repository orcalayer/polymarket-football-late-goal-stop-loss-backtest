#!/usr/bin/env python3
"""Recompute every late-goal number of the write-up from data/late_goal_jumps.csv (Python 3.9+, standard library only).

Each row is one late price jump at a level score in a Polymarket football 1X2 market, found on our recorded order book:
about the 70th minute or later, the draw was the favorite 30 seconds before, and one side's Yes mid rose by 0.25 or more within
30 seconds to 0.50 or higher. ask_Ns is that side's best ask N seconds after the detection; side_won is the result.

A bet = buy $10 of the side's Yes at ask_Ns (only asks above 0.02 and up to 0.97), pay the sports taker fee 0.05 x p x (1 - p) per
share, hold to resolution. Polymarket holds a taker order for 1 second in live football, so +2 s is the realistic entry.

Usage: python3 summarize_late_goals.py [path/to/late_goal_jumps.csv]
"""
import csv
import math
import sys


def fee(p):
    return 0.05 * p * (1 - p)


def bet(ask, won):
    if ask is None or not 0.02 < ask <= 0.97:
        return None
    shares = 10.0 / ask
    return shares * won - 10.0 - shares * fee(ask)


def stat(values):
    v = [x for x in values if x is not None]
    if not v:
        return "n0"
    n = len(v)
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1)) if n > 1 else 0.0
    return "%+5.2f per $10 (t %+4.1f) n%-4d total $%+6.0f" % (m, m / (sd / math.sqrt(n)) if sd else 0.0, n, sum(v))


def num(x):
    return float(x) if x not in ("", None) else None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data/late_goal_jumps.csv"
    R = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            x = {k: num(r[k]) for k in r if k.startswith(("ask_", "side_", "other_", "draw_", "minutes"))}
            x["slug"], x["day"] = r["event_slug"], r["detected_utc"][:10]
            x["won"] = int(r["side_won"])
            x["bid0"] = 2 * x["side_mid_at_detection"] - x["ask_0s"]
            x["spread"] = round(x["ask_0s"] - x["bid0"], 2)   # prices are on a 1-cent grid; round away float noise
            R.append(x)

    print("Late jumps at a level score: %d (days %d, matches %d); the jumping side won %d" % (
        len(R), len({x["day"] for x in R}), len({x["slug"] for x in R}), sum(x["won"] for x in R)))
    print("\nBuy the jumping side at the best ask N seconds after the detection:")
    for k in ("ask_0s", "ask_1s", "ask_2s", "ask_5s", "ask_10s", "ask_30s"):
        print("  +%-4s %s" % (k[4:], stat([bet(x[k], x["won"]) for x in R])))
    print("\nEntry +2 s, by entry price:")
    for lo, hi in ((0, 0.5), (0.5, 0.65), (0.65, 0.8), (0.8, 0.9), (0.9, 0.98)):
        print("  %.2f-%.2f %s" % (lo, hi, stat([bet(x["ask_2s"], x["won"]) for x in R if x["ask_2s"] is not None and lo <= x["ask_2s"] < hi])))

    print("\nBy the bid-ask spread at the detection (known at once): a real goal reprices both sides, a vanished side leaves a wide spread")
    for lo, hi in ((0, 2), (3, 4), (5, 8), (9, 19), (20, 100)):                  # cents, both ends included
        X = [x for x in R if lo <= round(100 * x["spread"]) <= hi]
        if X:
            print("  spread %2d-%3d c: %3d jumps, won %3.0f%% | entry +2 s %s" % (
                lo, hi, len(X), 100.0 * sum(x["won"] for x in X) / len(X), stat([bet(x["ask_2s"], x["won"]) for x in X])))

    T = [x for x in R if x["spread"] <= 0.04 and x["bid0"] >= 0.45]
    print("\nTight spread at the jump (spread 4 c or less and bid >= 0.45): %d jumps, won %.0f%%" % (len(T), 100.0 * sum(x["won"] for x in T) / max(1, len(T))))
    for k in ("ask_0s", "ask_1s", "ask_2s", "ask_5s", "ask_10s"):
        print("  +%-4s %s" % (k[4:], stat([bet(x[k], x["won"]) for x in T])))
    gap = sorted(x["ask_60s"] - x["ask_2s"] for x in T if x["ask_60s"] is not None and x["ask_2s"] is not None)
    if gap:
        print("  price 60 s later minus the +2 s entry: median %+.3f (p25 %+.3f, p75 %+.3f)" % (
            gap[len(gap) // 2], gap[len(gap) // 4], gap[3 * len(gap) // 4]))

    # the "level score" itself comes from mids 30 s before; pulled quotes then push the three mids well above 1 in total
    pre = lambda x: x["side_mid_30s_before"] + x["other_side_mid_30s_before"] + x["draw_mid_30s_before"]   # noqa: E731
    print("\nThe book 30 s before the jump (sum of the three mids; about 1.00 when all three books are two-sided):")
    print("  all jumps: sum above 1.10 in %d of %d" % (sum(1 for x in R if pre(x) > 1.10), len(R)))
    print("  tight-spread jumps: sum above 1.10 in %d of %d" % (sum(1 for x in T if pre(x) > 1.10), len(T)))
    C = [x for x in T if 0.95 <= pre(x) <= 1.05]
    print("  tight spread and a clean book before (sum 0.95-1.05): %d jumps, won %d | entry +2 s %s" % (
        len(C), sum(x["won"] for x in C), stat([bet(x["ask_2s"], x["won"]) for x in C])))


if __name__ == "__main__":
    main()
