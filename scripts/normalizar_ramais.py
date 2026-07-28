# -*- coding: utf-8 -*-
"""
Normaliza RAMAIS_SEINFRA.geojson (export cru de shapefile) para geojson/v2/ramais.geojson.

Problemas do arquivo original que este script elimina na origem:
  - chaves truncadas em 10 chars pelo formato DBF ("Descriçã", "Local Term", ...)
  - números como string BR com vírgula ("2,6")
  - 35 colunas 100% vazias + 2 colunas constantes (Und="km", Traçado K="Ok")
  - 3 colunas duplicadas (CÓDIGO_2, Número_2, Descriç_1)
  - coordenadas com 15 casas decimais + dimensão Z inútil (sempre 0.0)

Nomes completos confirmados no cabeçalho da planilha oficial
'Ramais!A1:BK1' (Sheets 1Cr5Qbj_My7oOcIYiIjZ6NgJiCsij4ZAQCSxdP49cffc).

Uso:  python scripts/normalizar_ramais.py
Saída: geojson/v2/ramais.geojson + relatório no stdout
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEM = os.path.join(RAIZ, "geojson", "RAMAIS_SEINFRA.geojson")
DESTINO = os.path.join(RAIZ, "geojson", "v2", "ramais.geojson")

# chave truncada do shapefile -> chave normalizada
# (ordem = ordem das colunas na planilha oficial)
RENOMEAR = {
    "CÓDIGO":     "codigo",
    "Número":     "numero",
    "Descriçã":   "nome",              # "Descrição do Ramal/Estrada"
    "Classifica": "classificacao",
    "Segmentaç":  "segmentacao",
    "Rodovia/Es": "rodovia_acesso",    # "Rodovia/Estrada de acesso"
    "Ponto de r": "ponto_referencia",
    "Local de I": "local_inicio",
    "Local Term": "local_termino",
    "Município":  "municipio",
    "Extensão":   "extensao_km",       # "Extensão (km)"
    "Extensã_1":  "extensao_obra_km",  # "Extensão de Obra (km)"
    "Latitude I": "lat_inicial",       # DMS, ex.: 3°14'9.57"S
    "Longitude":  "lon_inicial",
    "Latitude F": "lat_final",
    "Longitud_1": "lon_final",
    "Fonte":      "fonte",
    "Situação":   "situacao",
    "Revestimen": "revestimento",
    "N° CT/CV":   "contrato",          # "N° CT/CV"
    "RESUMO DO":  "resumo_objeto",     # "RESUMO DO OBJETO"
    "Custo Esti": "custo_estimado",
    "Custo Cont": "custo_contratado",  # "Custo Contratatado" (sic, na planilha)
}

NUMERICAS = {"numero", "extensao_km", "extensao_obra_km", "custo_estimado", "custo_contratado"}

# duplicatas descartadas — divergências são reportadas
DUPLICADAS = ["CÓDIGO_2", "Número_2", "Descriç_1"]


def num_br(v):
    """'2,6' -> 2.6 · '6500000' -> 6500000.0 · lixo -> None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).replace("R$", "").replace(" ", "").strip()
    if not s:
        return None
    # padrão BR: ponto = milhar, vírgula = decimal
    s = s.replace(".", "").replace(",", ".")
    try:
        n = float(s)
        return int(n) if n == int(n) else n
    except ValueError:
        return None


def arred_coords(c, casas=6):
    """Arredonda recursivamente e remove a dimensão Z (posição [lon, lat])."""
    if not c:
        return c
    if isinstance(c[0], (int, float)):
        return [round(c[0], casas), round(c[1], casas)]
    return [arred_coords(x, casas) for x in c]


def main():
    with open(ORIGEM, encoding="utf-8") as fh:
        gj = json.load(fh)

    feats = gj["features"]
    print(f"origem: {len(feats)} features · {os.path.getsize(ORIGEM):,} bytes")

    divergencias = []
    saida = []
    for f in feats:
        p = f.get("properties") or {}

        # audita duplicatas antes de descartar
        a = (p.get("CÓDIGO"), p.get("Número"), p.get("Descriçã"))
        b = (p.get("CÓDIGO_2"), p.get("Número_2"), p.get("Descriç_1"))
        if a != b and any(x is not None for x in b):
            au = tuple(str(x).upper().strip() for x in a)
            bu = tuple(str(x).upper().strip() for x in b)
            if au != bu:
                divergencias.append((a, b))

        novo = {}
        for velha, nova in RENOMEAR.items():
            v = p.get(velha)
            if isinstance(v, str):
                v = v.strip() or None
            if nova in NUMERICAS:
                v = num_br(v)
            if v is not None:
                novo[nova] = v

        saida.append({
            "type": "Feature",
            "properties": novo,
            "geometry": {
                "type": f["geometry"]["type"],
                "coordinates": arred_coords(f["geometry"]["coordinates"]),
            },
        })

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"type": "FeatureCollection", "name": "ramais_seinfra_v2", "features": saida},
                  fh, ensure_ascii=False, separators=(",", ":"))

    print(f"destino: {len(saida)} features · {os.path.getsize(DESTINO):,} bytes "
          f"({100 - os.path.getsize(DESTINO) * 100 // os.path.getsize(ORIGEM)}% menor)")

    # sanidade
    com_nome = sum(1 for f in saida if f["properties"].get("nome"))
    com_ext = sum(1 for f in saida if isinstance(f["properties"].get("extensao_km"), (int, float)))
    com_mun = sum(1 for f in saida if f["properties"].get("municipio"))
    print(f"sanidade: nome={com_nome} · extensao_km numérica={com_ext} · municipio={com_mun}")

    if divergencias:
        print(f"\nAVISO — {len(divergencias)} divergência(s) reais entre colunas duplicadas "
              f"(1ª coluna mantida como canônica; corrigir na planilha oficial):")
        for a, b in divergencias:
            print(f"  mantido: {a}\n  descartado: {b}")


if __name__ == "__main__":
    main()
