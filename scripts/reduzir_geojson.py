# -*- coding: utf-8 -*-
"""
Reduz e higieniza os GeoJSONs consumidos pelo DMOB Hub -> geojson/v2/.

Para cada arquivo (SEM renomear chaves — consumidores não mudam):
  - repara mojibake em chaves e valores (UTF-8 lido como latin-1: "AlvarÃ£es" -> "Alvarães")
  - remove colunas 100% vazias
  - trim em strings
  - arredonda coordenadas para 6 casas (~11 cm) e remove dimensão Z
  - grava compacto (sem indentação)

O ramais tem script próprio (normalizar_ramais.py) porque lá as chaves
também são renomeadas.

Uso:  python scripts/reduzir_geojson.py
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.join(RAIZ, "geojson")
DESTINO = os.path.join(RAIZ, "geojson", "v2")

# Arquivos que o hub consome (GEOJSON_FILES do index.html), exceto ramais (já em v2)
ARQUIVOS = [
    "AM_MUNICIPIOS.geojson",
    "UNIDADE_DE_CONSERVACAO.geojson",
    "RODOVIAS_FEDERAIS.geojson",
    "BAIRROS.geojson",
    "HIDROVIAS.geojson",
    "RODOVIAS_ESTADUAIS_AMAZONAS.geojson",
    "SITIOS_ARQ_-_IPHAN.geojson",
    "AERODROMOS_SEINFRA.geojson",
    "TERMINAIS_FLUTUANTES_SEINFRA.geojson",
]

# UTF-8 decodificado como latin-1/cp1252 produz pares começando em Ã/Â/â
MOJI = re.compile("Ã[-¿£©§¡ªí³µºÁ]|Â[-¿°²³ºª]|â[-¿]")


def conserta_moji(s):
    """Reverte UTF-8 lido como latin-1. Se a reversão falhar, mantém original."""
    if not isinstance(s, str) or not MOJI.search(s):
        return s, False
    try:
        return s.encode("latin-1").decode("utf-8"), True
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s, False


def arred_coords(c, casas=6):
    if not c:
        return c
    if isinstance(c[0], (int, float)):
        return [round(c[0], casas), round(c[1], casas)]
    return [arred_coords(x, casas) for x in c]


def processa(fn):
    with open(os.path.join(ORIGEM, fn), encoding="utf-8") as fh:
        gj = json.load(fh)
    feats = gj.get("features", [])

    # colunas com pelo menos um valor útil
    uteis = set()
    for f in feats:
        for k, v in (f.get("properties") or {}).items():
            if v is not None and str(v).strip() != "":
                uteis.add(k)

    reparos = 0
    saida = []
    for f in feats:
        p = f.get("properties") or {}
        novo = {}
        for k, v in p.items():
            if k not in uteis:
                continue
            k2, rk = conserta_moji(k)
            if isinstance(v, str):
                v = v.strip()
                v, rv = conserta_moji(v)
                reparos += rk + rv
                if v == "":
                    continue
            novo[k2] = v
        g = f.get("geometry")
        saida.append({
            "type": "Feature",
            "properties": novo,
            "geometry": g and {"type": g["type"], "coordinates": arred_coords(g.get("coordinates", []))},
        })

    os.makedirs(DESTINO, exist_ok=True)
    dest = os.path.join(DESTINO, fn)
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"type": "FeatureCollection", "name": gj.get("name", fn), "features": saida},
                  fh, ensure_ascii=False, separators=(",", ":"))

    a, d = os.path.getsize(os.path.join(ORIGEM, fn)), os.path.getsize(dest)
    todas = set()
    for f in feats:
        todas.update((f.get("properties") or {}).keys())
    print(f"{fn}: {len(feats)} feats | {a//1024} KB -> {d//1024} KB ({100 - d*100//a}% menor) | "
          f"cols {len(todas)} -> {len(uteis)} | mojibake reparado: {reparos}")


if __name__ == "__main__":
    for fn in ARQUIVOS:
        processa(fn)
