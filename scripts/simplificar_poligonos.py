# -*- coding: utf-8 -*-
"""
Simplificação topológica dos polígonos pesados do v2 (roda APÓS reduzir_geojson.py).

Usa a biblioteca `topojson` (pip install topojson shapely): as fronteiras
compartilhadas entre polígonos vizinhos viram arcos únicos e são simplificadas
juntas — sem frestas nem sobreposições entre municípios/bairros.

Tolerâncias (graus; 0.001° ≈ 110 m no equador) escolhidas pelo zoom de uso:
  - municípios: vistos no zoom estadual (z5–10) -> 0.001
  - UCs: 0.0003 — há UCs de ~1 km² (Parque Tucumã, Cacimba) que colapsam
    com tolerância maior; prevent_oversimplify segura os anéis pequenos
  - bairros: zoom urbano (z12+) -> 0.0002 (~22 m)

Valida por feature: contagem, propriedades intactas e desvio de área < 1%.
"""
import json
import os
import sys

import topojson as tp
from shapely.geometry import shape

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(RAIZ, "geojson", "v2")

# (arquivo, tolerância, área mínima em graus² para simplificar)
# Features menores que a área mínima passam intactas — UCs de ~1 km² colapsam
# em qualquer tolerância útil e quase não pesam no arquivo.
ALVOS = [
    ("AM_MUNICIPIOS.geojson", 0.001, 0.0),
    ("UNIDADE_DE_CONSERVACAO.geojson", 0.001, 0.005),
    # BAIRROS fica fora: são polígonos pequenos vistos em zoom urbano — mesmo
    # tolerância de 11 m gera desvio > 1% nos menores, e o arquivo já caiu 43%
    # só com o arredondamento de coordenadas do reduzir_geojson.py.
]


def processa(fn, tolerancia, area_min):
    caminho = os.path.join(V2, fn)
    with open(caminho, encoding="utf-8") as fh:
        gj = json.load(fh)
    antes = os.path.getsize(caminho)
    feats = gj["features"]

    areas_antes = [shape(f["geometry"]).area if f.get("geometry") else 0 for f in feats]

    # separa: grandes são simplificadas em topologia conjunta; pequenas passam intactas
    idx_grandes = [i for i, a in enumerate(areas_antes) if a >= area_min]
    idx_pequenas = [i for i, a in enumerate(areas_antes) if a < area_min]
    grandes = {"type": "FeatureCollection", "features": [feats[i] for i in idx_grandes]}

    topo = tp.Topology(grandes, prequantize=True, toposimplify=tolerancia,
                       prevent_oversimplify=True)
    simplificadas = json.loads(topo.to_geojson())["features"]

    # reconstrói na ordem original
    novas = list(feats)
    for j, i in enumerate(idx_grandes):
        novas[i] = simplificadas[j]
    saida = {"type": "FeatureCollection", "features": novas}

    # validação
    assert len(saida["features"]) == len(feats), f"{fn}: contagem de features mudou!"
    pior = 0.0
    for i, (f0, f1) in enumerate(zip(feats, saida["features"])):
        assert f0["properties"] == f1["properties"], f"{fn}: properties mudaram na feature {i}"
        a0, a1 = areas_antes[i], shape(f1["geometry"]).area if f1.get("geometry") else 0
        if a0 > 0:
            pior = max(pior, abs(a1 - a0) / a0)
    if pior > 0.01:
        raise SystemExit(f"{fn}: desvio de área {pior:.2%} > 1% — tolerância alta demais, abortado")

    # coordenadas com 6 casas, compacto
    def arred(c):
        if not c:
            return c
        if isinstance(c[0], (int, float)):
            return [round(c[0], 6), round(c[1], 6)]
        return [arred(x) for x in c]

    for f in saida["features"]:
        if f.get("geometry"):
            f["geometry"]["coordinates"] = arred(f["geometry"]["coordinates"])

    with open(caminho, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(saida, fh, ensure_ascii=False, separators=(",", ":"))

    depois = os.path.getsize(caminho)
    print(f"{fn}: {antes // 1024} KB -> {depois // 1024} KB ({100 - depois * 100 // antes}% menor) "
          f"| desvio máx. de área {pior:.3%} | tol {tolerancia}° "
          f"| intactas (pequenas): {len(idx_pequenas)}")


if __name__ == "__main__":
    for fn, tol, amin in ALVOS:
        processa(fn, tol, amin)
