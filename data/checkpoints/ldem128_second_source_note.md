# LDEM_128: the PDS copy differs from the MIT copy in bytes 56-4095 only

Checkpoint 1 requires the second-source SHA-256 to equal the manifest's. For `LDEM_128.IMG` it does not:

| copy | URL | Last-Modified | SHA-256 |
|---|---|---|---|
| ours (MIT mirror) | https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_128.IMG | Wed, 30 Aug 2017 18:30:15 GMT | 0ab81a3e8d20e5528a21bc6c994974726cb486198013085f4c423c86fbd1154b |
| PDS Geosciences Node | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_128.img | Wed, 06 Sep 2017 15:55:04 GMT | 0e4fea9b863e3255f58de15ccbd2bb8b1e248cb09217fd55d23ed37489f764b4 |

Both are 2 123 366 400 bytes. Checked 2026-11-14:

1. 360 rows (every 64th) read from PDS by byte ranges: only row 0 differs, in samples 28-2047 (bytes 56-4095).
2. There the PDS copy holds DN 0 (0 m) at 89.996 N; our copy holds 28-29 m, and row 0 minus row 1 has RMS 1.1 m
   in our copy (1.2 m elsewhere along the row) against 23.3 m in the PDS copy.
3. Our file with bytes 56-4095 set to zero has SHA-256 0e4fea9b...64b4, exactly the PDS hash. So the two copies differ
   in those 4040 bytes and nowhere else, and the PDS copy is the one with the zeroed block.

Consequence: checkpoint 1 for LDEM_128 is formally failed (the rule is not changed); the reason is identified and our
copy is the consistent one. The affected pixels are 2020 cells of the northernmost row (89.996 N, 0.2-16 E), which the
whole-Moon terrain never reads (the north-polar products cover them). Not yet reported to the PDS Geosciences Node.
