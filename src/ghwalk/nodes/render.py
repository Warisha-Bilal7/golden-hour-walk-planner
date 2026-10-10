from __future__ import annotations

import base64
import re
import shutil
import subprocess
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .map_fetch import load_green, load_graph

OUT_DIR = Path("output")
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


# ---------- route map image ----------

def _exteriors(geom):
    if geom is None:
        return []
    if geom.geom_type == "Polygon":
        return [geom.exterior]
    if geom.geom_type == "MultiPolygon":
        return [p.exterior for p in geom.geoms]
    return []


def _route_map(G, green_polys, route, start_node, out_path, km=0.0, green_pct=0.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    for poly in green_polys:
        for ext in _exteriors(poly):
            xs, ys = ext.xy
            ax.fill(xs, ys, color="green", alpha=0.22, linewidth=0)
    xs = [nd["x"] for n, nd in G.nodes(data=True)]
    ys = [nd["y"] for n, nd in G.nodes(data=True)]
    ax.plot(xs, ys, ".", color="#555", ms=1.1, alpha=0.4)
    if route:
        px = [G.nodes[n]["x"] for n in route]
        py = [G.nodes[n]["y"] for n in route]
        ax.plot(px, py, color="#d96629", lw=3.2)
    ax.plot(G.nodes[start_node]["x"], G.nodes[start_node]["y"], "r*", ms=26)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")
    ax.set_title(
        f"route map  -  {km:.2f} km  -  {green_pct:.0%} beside green",
        fontsize=12, pad=8,
    )
    fig.savefig(out_path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _map_data_uri(png_path: Path) -> str:
    data = png_path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# ---------- PDF export ----------

def _find_browser():
    for p in EDGE_PATHS:
        if Path(p).exists():
            return p
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def _write_pdf_weasyprint(html_path: Path, pdf_path: Path) -> bool:
    try:
        from weasyprint import HTML
    except Exception:
        return False
    HTML(str(html_path)).write_pdf(str(pdf_path))
    return pdf_path.exists() and pdf_path.stat().st_size > 0


def _write_pdf_browser(html_path: Path, pdf_path: Path) -> bool:
    import tempfile

    browser = _find_browser()
    if not browser:
        return False
    profile = tempfile.mkdtemp(prefix="ghwalk-edge-")
    try:
        subprocess.run(
            [
                browser, "--headless=new", "--disable-gpu", "--no-sandbox",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}", "--print-to-pdf-no-header",
                html_path.resolve().as_uri(),
            ],
            timeout=60, check=True, capture_output=True,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return pdf_path.exists() and pdf_path.stat().st_size > 0


def _write_pdf(html_path: Path, pdf_path: Path) -> bool:
    return _write_pdf_weasyprint(html_path, pdf_path) or _write_pdf_browser(html_path, pdf_path)


# ---------- GPX export ----------

def _gpx(G, route, lat=None, lon=None) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="ghwalk" xmlns="http://www.topografix.com/GPX/1/1">',
        "  <trk><name>golden hour loop</name><trkseg>",
    ]
    if G is not None:
        for n in route:
            nd = G.nodes.get(n)
            if nd and nd.get("lat") is not None and nd.get("lon") is not None:
                lines.append(f'    <trkpt lat="{nd["lat"]}" lon="{nd["lon"]}"></trkpt>')
    elif lat is not None and lon is not None:
        lines.append(f'    <trkpt lat="{lat}" lon="{lon}"></trkpt>')
    lines += ["  </trkseg></trk>", "</gpx>", ""]
    return "\n".join(lines)


# ---------- node ----------

def run(state):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings = []

    graph_path = state.get("graph_path")
    G = None
    if graph_path and Path(graph_path).exists():
        try:
            G = load_graph(graph_path)
        except Exception as exc:
            warnings.append(f"render: could not load graph for map/GPX ({exc})")

    green_path = state.get("green_path")
    green_polys = []
    if green_path and Path(green_path).exists():
        try:
            green_polys = load_green(green_path)
        except Exception as exc:
            warnings.append(f"render: could not load green polygons ({exc})")

    best = state.get("best") or {}
    route = best.get("nodes") or []
    start_node = int(state.get("start_node", 0))
    km = best.get("length_m", 0.0) / 1000
    green_pct = best.get("green_pct", 0.0)

    route_map_png = OUT_DIR / "route_map.png"
    map_data_uri = ""
    if G is not None and route:
        try:
            _route_map(G, green_polys, route, start_node, route_map_png, km, green_pct)
            map_data_uri = _map_data_uri(route_map_png)
        except Exception as exc:
            warnings.append(f"render: route map failed ({exc})")

    card_text = re.sub(r"\[\[(.+?)\]\]", r"\1", state.get("card_text", ""))
    env = Environment(
        loader=PackageLoader("ghwalk", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("card.html.j2")
    html = template.render(
        card_text=card_text,
        km=km,
        minutes=state.get("intake", {}).get("duration_min", 0),
        green_pct=green_pct,
        sunset=state.get("sunset_iso", "")[:16].replace("T", " "),
        walk_start=state.get("walk_start_iso", "")[:16].replace("T", " "),
        weather=state.get("weather", {}),
        map_data_uri=map_data_uri,
        used_fallback=state.get("used_fallback", False),
    )
    html_path = OUT_DIR / "card.html"
    html_path.write_text(html, encoding="utf-8")

    pdf_path = OUT_DIR / "card.pdf"
    pdf_done = _write_pdf(html_path, pdf_path)
    if not pdf_done:
        warnings.append("render: PDF export skipped (no weasyprint/browser); open card.html in a browser and print to PDF")
        pdf_path = None

    gpx_path = OUT_DIR / "route.gpx"
    gpx_path.write_text(
        _gpx(G, route, state.get("start_lat"), state.get("start_lon")),
        encoding="utf-8",
    )

    return {
        "pdf_path": str(pdf_path) if pdf_path else "",
        "gpx_path": str(gpx_path),
        "route_map_path": str(route_map_png) if map_data_uri else "",
        "warnings": warnings,
    }