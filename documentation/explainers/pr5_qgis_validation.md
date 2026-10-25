# PR #5 topology validation (2026-10-25)

Entry head, verified locally and against GitHub after fetch:
`95d3a5d6843e865ae539c3b7ee1192d40400266d` on
`validation/reach-topology-preflight`. Baseline is merged PR #4 at
`106ee9bc964aa0e728d3ac1177e426832e4df6c4` (current main at validation start).
The exact final tested head and Codex review result are recorded in the PR comment.
No changes to main, PR #4, installed packages, virtual environments, or worktrees.

## Findings and corrections

The original branch suite passed: **135 passed, 1 inherited WBNM xfailed, zero
skipped**. Additional targeted tests then demonstrated eight failures:

- At explicitly allowed endpoint distances of 999 and 1000 CRS units, preflight
  accepted a unique connected tree but the legacy nearest-node search silently
  lost the reach. Its hard-coded initial minimum of 999 left both endpoint
  indices at zero. Replacing the two initial minima with infinity removes that
  hidden limit without replacing traversal or incidence-matrix construction.
- A non-finite interior reach vertex escaped endpoint-only checking. Check every
  vertex before connectivity, naming the offending reach and vertex index.
- Three non-finite-node cases were misleadingly reported as disconnected nodes.
  They now explicitly name the node and invalid coordinates.
- An enormous integer tolerance leaked OverflowError. It now produces the same
  descriptive ValueError as other invalid tolerances.
- Ambiguous equidistant-node errors omitted distances. Candidate names and
  distances are now reported together. Cycle/parallel errors include reach IDs.

The first two distance cases, three invalid-node cases, one interior vertex,
one overflow and one ambiguous-error assertion account for those eight failures.
After correction all 40 direct topology tests pass. No coordinate repair or
edge omission is permitted, and tests assert coordinates are unchanged.

## Direction investigation

Line start/end order is **not a hydrological direction constraint in the original
library**. The inherited traversal tests connection-matrix entries for presence
(`> 0`), then roots the undirected tree at the designated outlet. Every node in a
connected tree has a unique path to that outlet.

Eight tests cover every line-direction combination in a three-reach branching
catchment and assert the exact upstream/downstream matrices and edge counts.
All eight pass on both this branch and an archive of the exact merged main
baseline, imported explicitly from that archive. Reversing every line of the
public fixture also leaves incidence and RORB/URBS output bytes unchanged on
both revisions and both adapters. Thus treating digitisation as prescribed flow
would reject existing supported inputs; no directed-graph restriction was added.
This establishes the library's convention, not terrain-derived flow direction or
hydraulic engine acceptance.

## Native runtime and test matrix

Existing OSGeo4W launcher, Python **3.12.15**, QGIS **4.2.3**, GDAL **3.13.3**,
pytest **9.1.1**. Upstream adapter: norman-tom/runoff-model at
`6d18b7419c4b6b3b28b398ac64840ef14fb9932c`, file
`runoff_model/custom_types/qvector_layer.py`, verified blob
`cf6d99adc58569684eab6dc459322324ccc1045b`.

| Check | Final result |
| --- | --- |
| Full native suite | 193 passed, 1 inherited WBNM xfailed, zero skipped |
| Direct topology module | 40 passed |
| New real OGR/QGIS topology module | 32 passed |
| Prior OGR/QGIS attribute module | 52 passed |
| Original public RORB/URBS generation | Passed |
| Direction permutations on exact baseline | 8 passed |
| Model output comparison | Eight parent/candidate file pairs byte-identical |
| Full public harness snapshots | Equal, including incidence matrices and endpoint distances |

The adapter topology module writes synthetic EPSG:28350 shapefiles and verifies
QGIS reads a projected metre CRS. Both backends exercise exact joins, tolerance
zero, a 0.1 micrometre offset, rejected default-tolerance and accepted explicit
0.01 m joins, coincident/equidistant ambiguity, closed-line self-loops, reversed
parallel lines, triangle cycles, isolated nodes, detached subnets, no/multiple
outlets and duplicate IDs. Direct tests additionally cover finite tolerance
boundaries, non-finite coordinates, overflow and larger explicit tolerances.

The tracked public fixture has seven reaches and fourteen endpoints. Every
nearest-node distance is **0 m**; the minimum second-nearest distance is **50 m**
through both adapters. It is accepted at the unchanged 1e-6 default. No previously
accepted public fixture was rejected. This does not establish tolerance adequacy
for every external or proprietary model; none was accessed.

| Output | UTF-8 bytes | SHA-256, both revisions/adapters/digitisation variants |
| --- | --- | --- |
| RORB | 2818 | `67ae955b515a0594298fa1b0e48005d4d12db520e0a7dc582f37e6e06d6ad815` |
| URBS | 619 | `f162ca1ee5f1b1cffa3eee30f910e9632d4a3d783fe0411cbf579428db5ad025` |

WBNM still fails with the inherited missing `Basin._type` on both revisions;
its specific xfail remains separate. Pytest emits one inherited OGR future
warning. No WBNM repair or engine execution is claimed.

## Reproduce

Save the pinned upstream adapter outside the checkout as described in the
[PR #4 evidence](pr4_qgis_validation.md), then run:

```powershell
$env:PYROMB_QGIS_ADAPTER = 'C:\Temp\qvector_layer.py'
& C:\OSGeo4W\bin\python-qgis.bat -c "import sys,os; os.environ['PYTHONPATH']='src'; sys.path.insert(0,'src'); import pytest; raise SystemExit(pytest.main(['-q','--tb=long','-rx']))"
& C:\OSGeo4W\bin\python-qgis.bat scripts/validate_qgis.py . C:\Temp\candidate.json $env:PYROMB_QGIS_ADAPTER C:\Temp\candidate-outputs
```

Archive baseline `106ee9bc964aa0e728d3ac1177e426832e4df6c4` with `git archive`
into a temporary directory. Run the **current** harness against that root and
retain its output in a separate directory. Compare full JSON and each output
file as bytes. Repeat both runs with `$env:PYROMB_REVERSE_REACHES = '1'`, then
remove that environment variable. The harness reverses only the in-memory
reach vertex lists for that explicit experiment; fixture files stay unchanged.
Without the adapter variable QGIS tests explicitly skip, which does not satisfy
this acceptance gate. All reported runs supplied it.

Ruff 0.16.6 passes for both topology test modules. Catchment retains the same
five inherited diagnostics recorded for PR #4 (docstrings, summary formatting,
trailing whitespace and the legacy `l` variable); no traversal cleanup was added.
The validation harness retains its pre-existing lint limitations. Whitespace
checks cover the diff. PR comments record final exact-head checks and delivery.
