# -*- coding: utf-8 -*-
"""
Nomeia as hidrovias do v2 com a fonte oficial DNIT (roda APÓS reduzir_geojson.py).

O export original (vw_snv_aqa via KML) veio sem a tabela de atributos — só
geometria. A fonte oficial é a própria view do SNV aquaviário no GeoServer
do DNIT, que traz Nome, Código HF, Trecho e Região Hidrográfica:

  https://servicos.dnit.gov.br/dnitgeo/geoserver  (vgeo:vw_snv_aqa)

O match é espacial: as geometrias do nosso export são idênticas às do DNIT
(distância média ~0 nas 12 diretas), então cada feature nossa é atribuída ao
código HF cuja geometria (mesclada por código) minimiza a distância média de
uma amostra de vértices. Feature sem match < LIMIAR fica SEM nome (não
inventamos) e é reportada.

Caso especial verificado em 2026-07-28: a feature da calha principal é a
concatenação dos trechos SNV Rio Solimões (HF-132) e Rio Amazonas (HF-100)
— recebe nome composto.

Grava as chaves que o hub já consome: NOME, CODIGO, TRECHO, BACIA
(mantém 'extensao' calculada pelo reduzir_geojson.py).

Uso:  python scripts/nomear_hidrovias.py
"""
import json
import os
import sys
import urllib.request

from shapely.geometry import shape, Point
from shapely.ops import unary_union

sys.stdout.reconfigure(encoding="utf-8")
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALVO = os.path.join(RAIZ, "geojson", "v2", "HIDROVIAS.geojson")

WFS = ("https://servicos.dnit.gov.br/dnitgeo/geoserver/ows"
       "?service=WFS&version=2.0.0&request=GetFeature"
       "&typeNames=vgeo:vw_snv_aqa&outputFormat=application/json")

# aceita o match se a distância média da amostra ficar abaixo disto (graus)
LIMIAR = 0.005  # ~550 m

# O DNIT publica os nomes sem acento ("Rio Solimoes"); grafia oficial dos rios
ACENTOS = {
    "Rio Solimoes": "Rio Solimões",
    "Rio Jurua": "Rio Juruá",
    "Rio Japura": "Rio Japurá",
    "Rio Tapajos": "Rio Tapajós",
    "Rio Tarauaca": "Rio Tarauacá",
    "Rio Mamore": "Rio Mamoré",
    "Rio Guapore": "Rio Guaporé",
}


def main():
    print("baixando vw_snv_aqa do DNIT...")
    with urllib.request.urlopen(WFS, timeout=300) as resp:
        dnit = json.load(resp)
    print(f"DNIT: {len(dnit['features'])} features")

    # mescla por código HF (um rio pode ter vários trechos no SNV)
    por_cod = {}
    for f in dnit["features"]:
        g = f.get("geometry")
        if not g:
            continue
        p = f["properties"]
        e = por_cod.setdefault(p.get("Codigo"), {"geoms": [], "props": p})
        e["geoms"].append(shape(g))
    cands = []
    for cod, e in por_cod.items():
        p = e["props"]
        nome = ACENTOS.get(p.get("Nome"), p.get("Nome"))
        cands.append({
            "codigo": cod,
            "nome": nome,
            "trecho": (p.get("Trecho") or "").strip(),
            "geom": unary_union(e["geoms"]),
        })

    # candidato composto: calha Solimões+Amazonas concatenada no export SEINFRA
    partes = [c for c in cands if c["codigo"] in ("HF-132", "HF-100")]
    if len(partes) == 2:
        cands.append({
            "codigo": "HF-132 + HF-100",
            "nome": "Rios Solimões / Amazonas",
            "trecho": "Calha principal no Amazonas — junção dos trechos SNV "
                      "Rio Solimões (HF-132) e Rio Amazonas (HF-100).",
            "geom": unary_union([p["geom"] for p in partes]),
        })

    with open(ALVO, encoding="utf-8") as fh:
        gj = json.load(fh)
    feats = gj["features"]

    sem_nome = []
    for i, f in enumerate(feats):
        g = f["geometry"]
        pts = []
        for linha in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
            pts.extend(linha)
        amostra = [Point(x, y) for x, y, *_ in pts[:: max(1, len(pts) // 80)]]
        melhor, dist = None, float("inf")
        for c in cands:
            d = sum(c["geom"].distance(pt) for pt in amostra) / len(amostra)
            if d < dist:
                melhor, dist = c, d
        p = f["properties"]
        if dist < LIMIAR:
            p["NOME"] = melhor["nome"]
            p["CODIGO"] = melhor["codigo"]
            p["BACIA"] = "Amazônica"
            if melhor["trecho"]:
                p["TRECHO"] = melhor["trecho"]
            print(f"feature {i} (ext {p.get('extensao')} km) -> {melhor['codigo']} "
                  f"{melhor['nome']} (dist média {dist:.5f}°)")
        else:
            sem_nome.append((i, p.get("extensao"), melhor["codigo"], melhor["nome"], dist))

    with open(ALVO, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(gj, fh, ensure_ascii=False, separators=(",", ":"))

    nomeadas = sum(1 for f in feats if f["properties"].get("NOME"))
    print(f"\n{nomeadas}/{len(feats)} hidrovias nomeadas · {os.path.getsize(ALVO):,} bytes")
    for i, ext, cod, nome, d in sem_nome:
        print(f"AVISO — feature {i} (ext {ext} km) sem match no SNV "
              f"(mais próximo: {cod} {nome}, dist média {d:.4f}°) — fica sem nome")


if __name__ == "__main__":
    main()
