"""The declared extent, in ONE place.

Both the fetcher and the sightline need to know how far the area of interest goes, and
for a while both declared it. They drifted within the hour: the eastern edge moved to
11.5 in `fetch_extent.py` and stayed at 9.5 in `sightline2.py`, so the windows holding
Skagen were downloaded and then not read, and the calibration failed on a point that was
sitting on disk. That is D-094's shape — a fact written twice, changed once — and the
remedy is the same: one copy, and everything else asks it.

WHICH EDGES ARE DERIVED AND WHICH ARE DECLARED:

    W  -13.24  DERIVED. Kerry, 1,015 m, sees 121 km; plus the 60 km blind-sailing buffer.
    N   62.12  DERIVED. Shetland's Ronas Hill, 450 m, sees 80 km; plus the buffer.
               Faroe is NOT admitted: its buffer reaches another buffer, not water in
               sight, and two blind zones touching is not a route.
    S   44.50  DECLARED. The Gironde.
    E   11.50  DECLARED. Far enough to hold Skagen, which is a CALIBRATION POINT rather
               than scenery: Stephen names London to the northern tip of Denmark as about
               a week's sailing, and an anchor outside the data cannot calibrate anything.

The box is deliberately generous on its declared edges. The bound that actually decides
what belongs is a week's sailing measured through the water (tools/router/reach.py), and
it trims back to what it admits.
"""
EXTENT = (-13.24, 44.50, 11.50, 62.12)
