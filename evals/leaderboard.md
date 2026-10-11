# Leaderboard

One row per eval run (CLAUDE.md). Cost is the agent only; judge cost is separate.

| when | config | split | n | accuracy | numeric | text | citation hit | citation supported | tokens in / cached / out | $ agent | $ judge | p50 s | p95 s | tool calls avg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261010-194038 | smoke | dev | 3 | 100% | 100% | – | 100% | 100% | 37,777 / 17,792 / 749 | 0.07 | 0.00 | 9 | 9 | 2.7 |
| 20261010-195321 | baseline | dev | 42 | 86% | 100% | 80% | 74% | 88% | 732,601 / 257,024 / 12,747 | 1.44 | 0.05 | 7 | 17 | 3.0 |
| 20261010-200440 | accept-check | dev | 10 | 100% | 100% | 100% | 100% | 100% | 190,209 / 57,216 / 3,307 | 0.40 | 0.01 | 8 | 11 | 3.6 |
| 20261010-200635 | smoke-crosscheck | dev | 2 | 100% | 100% | – | 100% | 100% | 32,693 / 8,448 / 608 | 0.07 | 0.00 | 10 | 10 | 4.0 |
| 20261010-201710 | crosscheck | dev | 42 | 88% | 100% | 83% | 71% | 81% | 1,020,897 / 312,448 / 16,532 | 2.10 | 0.05 | 10 | 21 | 5.5 |
