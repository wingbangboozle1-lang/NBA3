# Suggestions — improvements & review queue

Two sections: **(A)** suggested improvements to the site/decision-making, and **(B)** the
suggestion intake table — a dedicated review section where suggestions are listed with status
(proposed / accepted / rejected / in progress) so a reviewer can choose the best path
**before** any change is implemented.

## A. Suggested improvements (from this session's findings)
| # | Suggestion | Why it improves decisions | Effort | Priority |
|---|---|---|---|---|
| S1 | Add an **odds/CLV module**: record daily market lines (manual CSV or feed) next to our originated lines | Converts "model skill" into "market edge" measurement; unlocks the core decision (bet or not) | M | P0 |
| S2 | **Daily auto-regeneration** of picks after the injury report drops (~5:30 PM ET) via scheduled workflow | Picks currently age; injury flags for +2/+3 days go stale | M | P0 |
| S3 | **Equity-curve charts** per strategy (cumulative units over time) on the Strategies page | Makes drawdown and luck visible at a glance | S | P1 |
| S4 | **Game pages** with quarter-by-quarter flow (where available) and rest/B2B context | Supports game-flow analysis beyond summary stats | M | P1 |
| S5 | **Player pages** with rolling 5-game form vs season average before originating props | Props lines currently use season averages only (flagged) | M | P1 |
| S6 | **Weekly data-integrity report**: re-reconcile records, re-run the corrupted-row checks, list new flags | Catches pipeline drift early (this session caught one corrupted fetch) | S | P1 |
| S7 | **Decision log page**: every pick, what the model said, what happened | Creates the audit trail that lets gates be re-evaluated monthly | S | P2 |
| S8 | **Mobile-first tables** (sticky headers, horizontal scroll hints) | Dashboard usability | S | P2 |
| S9 | **Export buttons** (CSV/JSON) on every table | Lets the owner analyze picks elsewhere | S | P2 |
| S10 | **Alerting** when a game's availability flag changes after publish | Prevents acting on stale picks | M | P2 |

## B. Suggestion intake (review before implementing)
| ID | Submitted by | Suggestion | Status | Reviewer notes |
|---|---|---|---|---|
| S1 | arena-0a016df8 | Odds/CLV module | proposed — needs owner decision on feed vs manual logging | Blocked by Open Questions Q2 |
| S2 | arena-0a016df8 | Daily post-injury-report regeneration | proposed — requires scheduled workflow approval | Needs repo owner to enable scheduled Actions |
| S3 | arena-0a016df8 | Equity curves | proposed | — |
| S4 | arena-0a016df8 | Per-game flow pages | proposed | Depends on quarter data availability (Q6-adjacent) |
| S5 | arena-0a016df8 | Player form pages for props | proposed | Depends on Q4 data |
| S6 | arena-0a016df8 | Weekly integrity report | proposed | — |
| S7 | arena-0a016df8 | Decision log | proposed | — |
| S8 | arena-0a016df8 | Mobile table polish | proposed | — |
| S9 | arena-0a016df8 | Table exports | proposed | — |
| S10 | arena-0a016df8 | Availability-change alerts | proposed | — |

> **Review process:** a reviewer (repo owner) sets Status → accepted / rejected with notes.
> Only accepted items move to implementation, and the implementation session claims them in
> `COORDINATION.md` like any other task.
