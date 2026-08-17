#!/usr/bin/env python3
"""Recorta as figuras/tabelas dos PDFs originais para comparação lado a lado.

Saída: docs/replicacao/figuras/artigo/*.png, os recortes citados no RESUMO_EXECUTIVO.md.
Determinístico: pdftoppm a 150 dpi + caixa fixa em pixels. Se o PDF mudar, o
recorte muda; as caixas abaixo valem para os PDFs em docs/replicacao/papers/.

Requer: poppler (pdftoppm) e Pillow.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PAPERS = ROOT / "docs" / "replicacao" / "papers"
OUT = ROOT / "docs" / "replicacao" / "figuras" / "artigo"
DPI = 150

# (pdf, página 1-based, caixa (esq, topo, dir, base) em px @150dpi, arquivo de saída)
CROPS = [
    ("ESEM14.pdf", 3, (85, 100, 1190, 545), "esem14_fig2_artigo.png"),
    ("MSR14.pdf", 3, (85, 95, 660, 470), "msr14_fig2_artigo.png"),
    ("MSR14.pdf", 4, (85, 95, 1210, 410), "msr14_tab2_artigo.png"),
    ("IEICE16.pdf", 4, (95, 555, 620, 870), "ieice16_fig2_artigo.png"),
    ("IEICE16.pdf", 4, (95, 875, 620, 1195), "ieice16_fig3_artigo.png"),
    ("IEICE16.pdf", 5, (630, 140, 1180, 735), "ieice16_fig5_artigo.png"),
    ("IEICE16.pdf", 6, (95, 110, 1190, 1000), "ieice16_fig6_artigo.png"),
    ("IEICE16.pdf", 7, (95, 135, 1150, 430), "ieice16_fig7_artigo.png"),
    ("IEICE16.pdf", 9, (95, 135, 1190, 875), "ieice16_fig8_artigo.png"),
]


def main() -> int:
    faltando = sorted({p for p, *_ in CROPS if not (PAPERS / p).exists()})
    if faltando:
        print(f"PDFs ausentes em {PAPERS}: {', '.join(faltando)}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cache: dict[tuple[str, int], Path] = {}
        for pdf, page, box, nome in CROPS:
            chave = (pdf, page)
            if chave not in cache:
                prefixo = Path(tmp) / f"{Path(pdf).stem}_{page}"
                subprocess.run(
                    [
                        "pdftoppm",
                        "-r",
                        str(DPI),
                        "-f",
                        str(page),
                        "-l",
                        str(page),
                        "-png",
                        str(PAPERS / pdf),
                        str(prefixo),
                    ],
                    check=True,
                )
                rendered = sorted(Path(tmp).glob(f"{prefixo.name}-*.png"))
                if not rendered:
                    print(f"pdftoppm não gerou página {page} de {pdf}", file=sys.stderr)
                    return 1
                cache[chave] = rendered[0]
            with Image.open(cache[chave]) as im:
                im.crop(box).save(OUT / nome)
            print(f"{pdf} p.{page} {box} -> docs/replicacao/figuras/artigo/{nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
