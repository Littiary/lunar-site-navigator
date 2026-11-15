Fill light transition of commit 22992b3 against 0f5c953.

Shackleton crater rim crest, played from 2026-12-07 02:58 to 03:10 UTC (the package gives the Sun as
under 1 % visible until 03:00, then hidden, so the fill comes on at 03:00), recorded frame by frame
from the packaged builds with -LsnMovieDir at 960 x 540, -benchmark -fps=30 (1/30 s per frame). The CSV
files give the mean grey (0 to 255) of the ground (rows 300-440) for every frame. An earlier run from
01:00 to 03:00 ends on the sample where the fill starts, so it shows no rise; this stretch includes it.

  0f5c953  0.0 -> 20.6 in one frame (98 % of the final 21.1 in a single step)
  22992b3  5 % -> 95 % of the final 21.1 in 38 frames = 1.27 s; the largest step between two frames
           is 0.9 (4 % of the final); an ease-in-out over 1.5 s, as the smoothstep gives

Benchmark, RTX 5090, 1280 x 720, mean frame time 0f5c953 -> 22992b3 (-LsnBench uses the target at once):
  one site 1.082 -> 1.115 ms (+3 %), one site low 1.093 -> 1.094 ms, two sites 1.578 -> 1.581 ms,
  two sites low 1.385 -> 1.378 ms.
