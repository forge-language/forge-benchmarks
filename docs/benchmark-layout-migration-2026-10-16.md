# Benchmark ownership and untracked-file cleanup

Standalone compiler, platform and web benchmark tools now live in this repository.
The migration covers 55 original entries (17,084,780 bytes), including two generated
Python bytecode files subsequently discarded. The 53 source/report/evidence entries
are retained. Every move verified a canonical copy before unlinking its source.

Current locations:

| Previous location | Canonical location here |
| --- | --- |
| forge/tests/*_lookup_bench.py, modular_power_bench.py | benchmark/compiler/ |
| forge/docs/benchmarks/ | docs/compiler/ |
| forge-platform/benchmarks/ | benchmark/platform/ |
| forge-platform/docs measured platform reports | docs/platform/ |
| forge-web/benchmarks/ | benchmark/web/ |

The removed forge/tests/selfhost_bench.py is superseded by
`benchmark/selfhost_compare.py`. Its exact original is retained in the archive
and Git history. Current and historical schemas are not identical.
No new submodule is needed: component builds do not consume these tools, and
source-dependent runners receive explicit checkout paths. Dependency pins retain
published revisions rather than naming unpublished moved files.

Validation executed after relocation:

- Function/local/constant lookup runners: 10/29/23 scenarios with two AB/BA pairs,
  identical frozen compiler hashes, generated C/JS identity checks. These are
  smoke checks, not new performance measurements.
- All eight moved Python CLIs returned help successfully. Invalid source roots
  were rejected by registry, Redis and web runners before Docker fixture creation.
- The web harness built against an explicit bridge path and executed buffer,
  ownership, rate-limit and 300-request loopback HTTP checks for both variants.
  Both used the same source and reused one connection. Security C checks rejected
  all five unsafe inputs and 20,000 forged JWTs.
- 65 local Markdown links resolved. All ten moved raw archive SHA256 checks passed.
- All 30 tracked `forge-platform/content/reports` projections matched their original
  bytes; these served assets were retained. No benchmark public-data file existed
  under frontend/public in this checkout.

Cargo caches `benchmark/http-v2/target` (41 MiB) and `benchmark/mailbox/target`
(592 KiB) had Cargo cache tags and .rustc_info.json, with no open process handles.
They and regenerated benchmark Python bytecode were deleted. The automatic command
review rejected `rm -f`; deletion succeeded with exact paths and no force option.
The ignore file now covers benchmark target directories and ephemeral agent state.
Raw observations, versioned V1/V2 fixture inputs and unrelated user files remain.

The [receipt](benchmark-layout-migration-2026-10-16.json) contains original hashes,
target hashes at verification and the recovery location for every changed original.
The [archive](benchmark-layout-migration-2026-10-16.raw.tar.gz) preserves pre-link
report prose, moved README originals, the superseded runner and CLI smoke results;
verify it with the [checksum](benchmark-layout-migration-2026-10-16.sha256).
Dated report code blocks keep their historical paths; current commands are indexed
in [compiler](../benchmark/compiler/README.md), [platform](../benchmark/platform/README.md)
and [web](../benchmark/web/README.md) runner guides.
