"""Build an offline selection gallery from archived, visually inspected previews."""

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/articles/selection-generations"
# First recent cohort inspected visually; older archives are not classified here.
REVIEWED_NUMBERS = range(4, 22)


def render() -> None:
    """Render original briefs safely, without modifying the archived images."""
    records = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    cards = []
    for row in records:
        if row["number"] not in REVIEWED_NUMBERS:
            continue
        identifier = f"G{row['number']:03d}"
        filename = html.escape(row["file"], quote=True)
        brief = html.escape(row["brief"] or "Brief non archivé")
        constraints = html.escape(json.dumps(row["constraints"], ensure_ascii=False, indent=2))
        cards.append(f'''<article id="{identifier}">
<a class="image" href="{filename}" target="_blank" rel="noopener" aria-label="Agrandir {identifier}">
<img src="{filename}" alt="Plan généré {identifier}" width="{row['width']}" height="{row['height']}"></a>
<section><span class="meta">{row['created_at'][:10]} · {row['width']} × {row['height']} px</span>
<h2>{identifier}</h2><h3>Prompt utilisateur original</h3><p class="brief">{brief}</p>
<details><summary>Contraintes enregistrées</summary><pre>{constraints}</pre></details>
<p><a href="{filename}" target="_blank" rel="noopener">Agrandir le résultat ↗</a></p>
<label><input type="checkbox" value="{identifier}"> Retenir {identifier}</label></section></article>''')
    template = (ROOT / "research/article_gallery_template.html").read_text(encoding="utf-8")
    rendered = template.replace("<!-- CARDS -->", "\n".join(cards)).replace("{{COUNT}}", str(len(cards)))
    (OUTPUT / "index.html").write_text(rendered, encoding="utf-8")
    print(f"Gallery built: {len(cards)} candidates")


if __name__ == "__main__":
    render()
