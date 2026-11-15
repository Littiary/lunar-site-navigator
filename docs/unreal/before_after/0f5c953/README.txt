Before and after for commit 0f5c953 (no earthshine light; night light as in 0b1cb68), taken from the
packaged builds at 1920 x 1080; each picture: left 0b1cb68, right 0f5c953, halved in size. Arguments as
in ../32bb3fe/README.txt.

The earthshine light, its blue colour and the note "Lit by earthshine, shown brighter than real" are
gone. The zenith fill is on while the Sun is hidden, white, at the level of 0b1cb68.

Mean grey, 0b1cb68 -> 0f5c953 (0 to 255):
  1  two sites, Shackleton half                        31.98 -> 31.48
     Shackleton hillside (x 0-950, y 560-820)          22.64 -> 21.72   (394a738 with earthshine: 28.5)
     de Gerlache half                                  46.10 -> 46.37
     far ridges, de Gerlache rows 560-740, pixels lit in 0b1cb68 (grey > 30): 54.2 -> 63.3,
     99.9 % at least as bright
  2  Shackleton 2026-12-07 04:00, scene (y 120-900)    19.75 -> 18.80
  3  night, lander camera 06:00, scene (y 120-900)     26.83 -> 25.39
  4  sunlit lander 2027-09-19 13:00, scene             100.89 -> 102.60

The small difference in the dark frames is the regolith detail textures (kept): their ambient occlusion
darkens the fill a little in the hollows; the fill's own intensity is that of 0b1cb68. The far-ridge
figure uses a different mask from ../394a738/README.txt (grey > 30), so it is not comparable with the
59.9 / 71.6 there. All card numbers are those of 0b1cb68.
