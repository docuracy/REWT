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
from landtest import os_land_area           # noqa: E402

OUT = Path("docs/router/check")
OPM = "data/raw/os_open_map_local/extracted/Data/opmplc_gb.gpkg"
RIV = "data/raw/os_open_rivers/extracted/Data/oprvrs_gb.gpkg"


def main() -> None:
    stamp = generation()
    land = os_land_area("EPSG:27700")
    tree = STRtree(land)

    fs = gpd.read_file(OPM, layer="foreshore").to_crs(4326)
    g = shapely.simplify(fs.geometry.values, 0.00005)     # ~5 m; this is context
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
    hit = tree.query(mid, predicate="intersects")
    landward = np.zeros(len(lk), bool)
    landward[np.unique(hit[0])] = True
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
