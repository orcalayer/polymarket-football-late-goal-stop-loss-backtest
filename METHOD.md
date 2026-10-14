# Method and pitfalls

How the numbers in this repository were produced, and the traps we hit on the way. If you build your own in-play football tests on
Polymarket, most of these will bite you too.

## 1. The data: a recorded order book

Public Polymarket APIs give you trades and the current book, not the book as it was a second ago. For both tests we needed the best
bid and ask around every late jump and every goal signal, so we recorded the CLOB WebSocket market channel for every football
market from 2026-09-17: `book` snapshots, `price_change` updates and `last_trade_price` events, each stored with the exchange
timestamp.

We checked the recording against on-chain trades before using it: 99.9% of on-chain trades appear in the recording, and 97.6% of
them happened at the best price the recording showed at that moment (2.2% deeper in the book).

**Pitfall: event order.** The exchange can send the `price_change` for a level that a trade just ate before the
`last_trade_price` of that same trade. Read the events in arrival order and fills look about 25% worse than they were. Put each
trade's `last_trade_price` ahead of the `price_change` it caused before you measure fills.

## 2. Late jumps

For every 1X2 market group ("Will X win on ...", "... end in a draw?") we followed each team's Yes mid. A detection needs all of:

- wall clock at least 87 minutes after the scheduled kick-off (about the 70th minute of play; the wall clock runs about 17 minutes
  ahead because of half-time and stoppages);
- 30 seconds earlier, the draw had the highest mid of the three (a mid as well, so pulled quotes can fake a level score; see
  the pitfall below);
- the team's Yes mid rose by 0.25 or more within 30 seconds, to 0.50 or higher;
- at most one detection per team per match per 10 minutes.

We then stored the team's best ask after the first book update at or after the detection and 1, 2, 5, 10, 30 and 60 seconds
later (left empty if the book did not change within 120 seconds), and the market's result.

**Pitfall: the mid is not a price you can trade.** A mid jumps when one side of the book is pulled. Store the ask and the spread,
not just the mid: in our data 627 of 837 jumps had a spread of 20 cents or more, and those were mostly pulled quotes
([CASES.md](CASES.md), case 1).

**Pitfall: the level score can be fake too.** The condition "the draw was the favorite 30 seconds before" is read from mids, so
pulled quotes can produce it in a match one team already leads. When all three books are two-sided the three mids add up to about
1.00; in 142 of 837 jumps they added up to more than 1.10, and in 51 of the 85 jumps with a tight spread at the jump. Case 2 in
[CASES.md](CASES.md) is one of them. Check the sum before you trust a level score.

**Pitfall: overlapping day files.** We ran the scan one day at a time, and each day file also covered the first hours after midnight
UTC. Jumps after midnight landed in two files: 47 exact duplicates and one pair 49 seconds apart, out of 885 raw rows. The
published CSV has the 837 jumps left after removing them. If you split any time series by day, check the joins.

## 3. Bets

$10 at the recorded best ask N seconds after the detection, only asks above 0.02 and up to 0.97, sports taker fee
`0.05 x p x (1 - p)` per share, held to resolution:

```
shares = 10 / ask
result = shares x (1 if the team won else 0) - 10 - shares x 0.05 x ask x (1 - ask)
```

**Pitfall: the +0 s entry is not reachable.** Polymarket holds every taker order for 1 second in live football before it can match
(`secondsDelay` = 1 on football markets in the Gamma API; the delay itself is described on the Order Lifecycle page). The +0 and +1 second rows are there to show the shape;
+2 seconds is the earliest realistic entry for a fast bot.

## 4. Stop-loss on goal signals

Signals came from our goal detector, which watches all linked markets of a match and fires when several of them reprice at once
(three sensitivity settings). Replay on the recording from 2026-09-17 to
09-29 is the sample; the detector running live from 2026-09-30 to 10-06 is the test.

- Entry: the recorded ask 1 second after the signal, $10.
- Stop: X cents below the entry (3, 5, 8, 10, 15, 20, 30), watched for W minutes (2, 5, 15, to the end of the match).
- Trigger: the first on-chain trade on that outcome at or below the stop level. Polymarket has no stop orders, so a bot has to
  watch and then sell.
- Exit: the lower of the trigger price and the volume-weighted trade price of the next 10 seconds (the 1-second taker delay plus
  reaction time), minus 1 cent, and the taker fee again.
- No trigger: hold to resolution.

**Pitfall: repeated signals.** One goal can fire more than one detector setting, and every signal counts as a separate bet here.
Bets on the same goal are not independent, which is one more reason to read the t values with care.

**Pitfall: in-play noise.** A 3-cent stop fired on 86 to 96% of all replayed bets. The same bets returned -$0.55 per $10 when held
and -$2.75 with a 3-cent stop watched for 5 minutes: the stop turned swings during play into realized losses and paid the fee twice.

## 5. Statistics

Mean result per $10 bet and the plain t-statistic (mean divided by its standard error). Bets in the same match share the match
result, so treat t values near 2 with caution. The sample / test split for the stop-loss is by date: the test week was never used
to choose anything.

## 6. Reproduce it with your own data

1. Record the Polymarket CLOB WebSocket market channel for the football markets you care about, with exchange timestamps, and
   check the recording against on-chain trades.
2. Detect late jumps with the rule in section 2 and store asks after each detection and the resolution.
3. Run `scripts/summarize_late_goals.py` on a CSV with the same columns as `data/late_goal_jumps.csv`.

To look at live markets and wallets without recording anything, use the free [OrcaLayer MCP server](https://orcalayer.com/docs/mcp)
or the [OrcaLayer API](https://orcalayer.com/docs/api).
