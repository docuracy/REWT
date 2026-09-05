"""OS foreshore, and the river links and nodes the high water line masked out.

STEPHEN'S REQUEST, for /check. The `high_water` stage classifies every survey link as
landward, crossing or seaward of the OS High Water Mark, and `repair` retires the seaward
ones — so the published network stops at high water and everything below it is invisible.
This puts back what was taken out, as context rather than as network:

  the OS Open Map Local FORESHORE polygons — the intertidal ground itself, 35,677
  features and 3,341 km2;
  the raw OS Open Rivers links whose midpoint lies SEAWARD of high water, which is the
  population the trim removes;
  the hydro nodes on those links.

None of it is routable and none of it is joined to anything. It is here so the intertidal
can be seen against the mesh and the skeleton rather than inferred from their absence.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import geopandas as gpd, numpy as np, shapely
from shapely import STRtree
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generation import generation           # noqa: E402
from landtest import _subdivide, os_land_area   # noqa: E402

OUT = Path("docs/router/check")
OPM = "data/raw/os_open_map_local/extracted/Data/opmplc_gb.gpkg"
RIV = "data/raw/os_open_rivers/extracted/Data/oprvrs_gb.gpkg"


def main() -> None:
    stamp = generation()
    # SUBDIVIDE, as landtest.py does. Testing 193,040 midpoints against an unsubdivided
    # mainland polygon of 218,000 km2 is the trap that made the exact land test take 133 s
    # instead of 0.14 s: an STRtree is only selective if its members are small.
    # RASTERISE, DO NOT SUBDIVIDE. Testing 193,040 midpoints against the mainland polygon
    # is slow because the polygon is huge, and subdividing it into tiles is slow for the
    # same reason: every tile must be intersected with it. A 100 m raster answers "is this
    # point on land" in constant time and builds in seconds, and 100 m is far finer than
    # the question needs — which side of the coast a midpoint falls on, not where the
    # coast is to the metre.
    import rasterio.features, rasterio.transform
    land_poly = os_land_area("EPSG:27700")
    b = shapely.total_bounds(land_poly)
    PX = 100.0
    W = int((b[2] - b[0]) / PX) + 2
    H = int((b[3] - b[1]) / PX) + 2
    ltr = rasterio.transform.from_origin(b[0], b[3], PX, PX)
    LAND = rasterio.features.rasterize(((g_, 1) for g_ in land_poly), out_shape=(H, W),
                                       transform=ltr, fill=0, dtype="uint8").astype(bool)
    print(f"  land raster {W:,} x {H:,} at {PX:.0f} m, {100*LAND.mean():.1f}% land")

    def on_land(pts):
        x = np.array([q.x for q in pts]); y = np.array([q.y for q in pts])
        c = ((x - b[0]) / PX).astype(int); r = ((b[3] - y) / PX).astype(int)
        ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
        out = np.zeros(len(pts), bool)
        out[ok] = LAND[r[ok], c[ok]]
        return out

    fs = gpd.read_file(OPM, layer="foreshore").to_crs(4326)
    g = shapely.simplify(fs.geometry.values, 0.0003)      # ~30 m; 5 m gave 51.5 MB
    fsf = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(x)),
            "properties": {}} for x in g if not x.is_empty]
    (OUT / "foreshore.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "features_": len(fsf),
                        "what": "OS Open Map Local foreshore — the intertidal ground.",
                        "attribution": "Contains OS data (c) Crown copyright and database "
                                       "right, OGL v3."},
         "features": fsf}, separators=(",", ":")))
    print(f"  foreshore.geojson {len(fsf):,} polygons "
          f"({(OUT/'foreshore.geojson').stat().st_size/1e6:.1f} MB)")

    lk = gpd.read_file(RIV, layer="watercourse_link")
    mid = shapely.centroid(lk.geometry.values)
    landward = on_land(mid)
    sea = lk[~landward].to_crs(4326)
    print(f"  {len(sea):,} of {len(lk):,} raw links lie seaward of high water")
    lf = [{"type": "Feature", "geometry": json.loads(shapely.to_geojson(x)),
           "properties": {"form": f}} for x, f in zip(sea.geometry.values, sea.form.values)]
    (OUT / "foreshore_links.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "features_": len(lf),
                        "what": "OS Open Rivers links whose midpoint is SEAWARD of the OS "
                                "High Water Mark — the population the high_water stage "
                                "classifies as seaward and repair retires, so they are "
                                "absent from the published network.",
                        "not_routable": "Context only. Not joined to the mesh, the skeleton "
                                        "or the river network.",
                        "attribution": "Contains OS data (c) Crown copyright and database "
                                       "right, OGL v3."},
         "features": lf}, separators=(",", ":")))
    print(f"  foreshore_links.geojson {len(lf):,} links "
          f"({(OUT/'foreshore_links.geojson').stat().st_size/1e6:.1f} MB)")

    nd = gpd.read_file(RIV, layer="hydro_node")
    ids = set(sea.start_node) | set(sea.end_node)
    sn = nd[nd.id.isin(ids)].to_crs(4326)
    nf = [{"type": "Feature",
           "geometry": {"type": "Point", "coordinates": [round(p.x, 6), round(p.y, 6)]},
           "properties": {}} for p in sn.geometry.values]
    (OUT / "foreshore_nodes.geojson").write_text(json.dumps(
        {"type": "FeatureCollection",
         "properties": {"generation": stamp, "features_": len(nf),
                        "what": "Hydro nodes on the seaward links."},
         "features": nf}, separators=(",", ":")))
    print(f"  foreshore_nodes.geojson {len(nf):,} nodes")


if __name__ == "__main__":
    main()
