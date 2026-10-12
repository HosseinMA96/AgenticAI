# Retrieval leaderboard

One row per (run, search mode). Queries are the raw questions. Scored by main page; any-page shown for comparison (D21, D22). For page chunks the two are identical.

| when | index | mode | split | n | hit@1 | hit@3 | hit@5 | recall@1 | recall@3 | recall@5 | recall@5 any-page |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261011-121922 | finsight-page | keyword | dev | 2 | 0% | 0% | 0% | 0% | 0% | 0% | 0% |
| 20261011-121922 | finsight-page | vector | dev | 2 | 100% | 100% | 100% | 75% | 75% | 100% | 100% |
| 20261011-121922 | finsight-page | hybrid | dev | 2 | 50% | 50% | 50% | 25% | 50% | 50% | 50% |
| 20261011-121922 | finsight-page | hybrid+rerank | dev | 2 | 50% | 50% | 100% | 25% | 50% | 100% | 100% |
| 20261011-122034 | finsight-page | keyword | dev | 42 | 10% | 12% | 14% | 10% | 12% | 13% | 13% |
| 20261011-122034 | finsight-page | vector | dev | 42 | 24% | 50% | 69% | 20% | 43% | 63% | 63% |
| 20261011-122034 | finsight-page | hybrid | dev | 42 | 21% | 36% | 45% | 19% | 31% | 40% | 40% |
| 20261011-122034 | finsight-page | hybrid+rerank | dev | 42 | 29% | 55% | 67% | 24% | 50% | 62% | 62% |
| 20261011-140333 | finsight-fixed | keyword | dev | 42 | 2% | 10% | 14% | 2% | 10% | 13% | 20% |
| 20261011-140333 | finsight-fixed | vector | dev | 42 | 19% | 33% | 50% | 15% | 27% | 43% | 54% |
| 20261011-140333 | finsight-fixed | hybrid | dev | 42 | 12% | 24% | 33% | 11% | 20% | 29% | 33% |
| 20261011-140333 | finsight-fixed | hybrid+rerank | dev | 42 | 14% | 31% | 45% | 13% | 26% | 40% | 50% |
| 20261011-173758 | finsight-page | keyword | dev | 42 | 10% | 12% | 14% | 10% | 12% | 13% | 13% |
| 20261011-173758 | finsight-page | vector | dev | 42 | 24% | 50% | 69% | 20% | 43% | 63% | 63% |
| 20261011-173758 | finsight-page | hybrid | dev | 42 | 21% | 36% | 45% | 19% | 31% | 40% | 40% |
| 20261011-173758 | finsight-page | hybrid+rerank | dev | 42 | 29% | 55% | 67% | 24% | 50% | 62% | 62% |
