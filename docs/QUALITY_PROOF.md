# Quality proof

The durable public packet is GitHub Release
[`quality-proof-12e116b`](https://github.com/milos-plavsic/continuum/releases/tag/quality-proof-12e116b),
produced by green `main` [CI run 33125745852](https://github.com/milos-plavsic/continuum/actions/runs/33125745852)
for commit `12e116b45c7cad6223e0d235a4583a0ad0d4dfd8`.

It contains:

- `coverage.xml` and detailed `coverage.json`;
- browsable line-by-line HTML;
- exact source and measured inventories for all 39 modules under `src/continuum`;
- 215-test discovery;
- checks for branch measurement, a 100% failure threshold, no configured source
  omissions or report exclusions, and no `pragma: no cover` shortcuts;
- nested `SHA256SUMS`, checked successfully after the CI artifact was downloaded.

Observed totals are 4,152/4,152 statements and 1,154/1,154 branches. The source-tree
digest is
`sha256:b3c3144d76f5699e6d209ad15aef2bcc006bb21712ff8adab21668a878ec0ba2`.
The deterministic release archive is
[`continuum-coverage-12e116b.tar.gz`](https://github.com/milos-plavsic/continuum/releases/download/quality-proof-12e116b/continuum-coverage-12e116b.tar.gz)
with SHA-256
`192a0668c4176f81380aecf54daad2b3da67cd753480b00cf2c0d40e0e95cd76`.

This packet proves execution and measured coverage of the declared source scope. It does
not claim that coverage alone proves semantic correctness; conformance, adversarial,
stress, cloud, supply-chain and independent-verification evidence remain separate gates.
