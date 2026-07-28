# -*- coding: utf-8 -*-
"""
Simplificação das linhas pesadas do v2 (roda APÓS reduzir_geojson.py).

RODOVIAS_FEDERAIS vem do export com um vértice a cada poucos metros
(167 mil vértices para 237 trechos). Douglas-Peucker por feature
(shapely, preserve_topology) com tolerância de 0.0002° (~22 m) — invisível
no zoom estadual em que a camada é usada.

Linhas não compartilham fronteira como os polígonos, então não precisa
de topologia conjunta (topojson) — cada trecho simplifica sozinho.

Valida por feature: contagem, propriedades intactas e desvio de
comprimento geodésico < 1%.

Uso:  python scripts/simplificar_linhas.py
"""
import json
import os
import sys
from math import radians, sin, cos, asin, sqrt

from shapely.geometry import shape, mapping

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(RAIZ, "geojson", "v2")

# (arquivo, tolerância em graus)
ALVOS = [
    ("RODOVIAS_FEDERAIS.geojson", 0.0002),
]


def _hav_km(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, (lon1, lat1, lon2, lat2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(a))


def comprimento_km(geom):
    c = geom.get("coordinates") or []
    linhas = [c] if geom["type"] == "LineString" else c
    total = 0.0
    for linha in linhas:
        for i in range(1, len(linha)):
            total += _hav_km(linha[i - 1][0], linha[i - 1][1], linha[i][0], linha[i][1])
    return total


def arred(c):
    if not c:
        return c
    if isinstance(c[0], (int, float)):
        return [round(c[0], 6), round(c[1], 6)]
    return [arred(list(x)) for x in c]


def processa(fn, tolerancia):
    caminho = os.path.join(V2, fn)
    with open(caminho, encoding="utf-8") as fh:
        gj = json.load(fh)
    antes = os.path.getsize(caminho)
    feats = gj["features"]

    pior = 0.0
    saida = []
    for i, f in enumerate(feats):
        g0 = f.get("geometry")
        if not g0 or g0["type"] not in ("LineString", "MultiLineString"):
            saida.append(f)
            continue
        g1 = mapping(shape(g0).simplify(tolerancia, preserve_topology=True))
        g1 = {"type": g1["type"], "coordinates": arred(list(g1["coordinates"]))}
        l0, l1 = comprimento_km(g0), comprimento_km(g1)
        if l0 > 0:
            pior = max(pior, abs(l1 - l0) / l0)
        saida.append({"type": "Feature", "properties": f["properties"], "geometry": g1})

    assert len(saida) == len(feats), f"{fn}: contagem de features mudou!"
    for f0, f1 in zip(feats, saida):
        assert f0["properties"] == f1["properties"], f"{fn}: properties mudaram"
    if pior > 0.01:
        raise SystemExit(f"{fn}: desvio de comprimento {pior:.2%} > 1% — tolerância alta demais, abortado")

    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"type": "FeatureCollection", "name": gj.get("name", fn), "features": saida},
                  fh, ensure_ascii=False, separators=(",", ":"))

    depois = os.path.getsize(caminho)
    print(f"{fn}: {antes // 1024} KB -> {depois // 1024} KB ({100 - depois * 100 // antes}% menor) "
          f"| desvio máx. de comprimento {pior:.3%} | tol {tolerancia}°")


if __name__ == "__main__":
    for fn, tol in ALVOS:
        processa(fn, tol)
