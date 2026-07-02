import re
import subprocess
import sys
from pathlib import Path
from scripts.config import XELATEX
_TEX = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
}
def _esc(texte: str) -> str:
    return "".join(_TEX.get(c, c) for c in texte)
def _inline(texte: str) -> str:
    out, i = [], 0
    for m in re.finditer(r"`([^`]+)`|\*\*([^*]+)\*\*", texte):
        out.append(_esc(texte[i:m.start()]))
        if m.group(1) is not None:
            out.append(r"\texttt{%s}" % _esc(m.group(1)))
        else:
            out.append(r"\textbf{%s}" % _esc(m.group(2)))
        i = m.end()
    out.append(_esc(texte[i:]))
    return "".join(out)
PREAMBULE = r"""\documentclass[11pt,a4paper]{article}
\usepackage{fontspec}
\usepackage[french]{babel}
\usepackage[a4paper,margin=2cm]{geometry}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{hyperref}
\setmainfont{Carlito}[Ligatures=TeX, BoldFont={Carlito Bold},
  ItalicFont={Carlito Italic}, BoldItalicFont={Carlito Bold Italic}]
\definecolor{accent}{HTML}{2C3E50}
\definecolor{accent2}{HTML}{3498DB}
\hypersetup{colorlinks=true, urlcolor=accent2, linkcolor=accent2}
\setlist[itemize]{leftmargin=1.4em, itemsep=2pt, topsep=2pt}
\titleskip
\begin{document}
"""
def md_vers_tex(md: str) -> str:
    lignes = md.splitlines()
    corps, dans_liste = [], False
    def fermer_liste():
        nonlocal dans_liste
        if dans_liste:
            corps.append(r"\end{itemize}")
            dans_liste = False
    for ligne in lignes:
        brut = ligne.rstrip()
        if not brut.strip():
            fermer_liste()
            corps.append("")
            continue
        if brut.startswith("### "):
            fermer_liste()
            corps.append(r"\subsection*{%s}" % _inline(brut[4:]))
        elif brut.startswith("## "):
            fermer_liste()
            corps.append(r"\section*{\color{accent}%s}" % _inline(brut[3:]))
        elif brut.startswith("# "):
            fermer_liste()
            corps.append(r"{\LARGE\bfseries\color{accent} %s}\par\vspace{0.4em}"
                         r"{\color{accent2}\hrule height 1pt}\vspace{0.6em}"
                         % _inline(brut[2:]))
        elif re.match(r"^\s*-\s+", brut):
            if not dans_liste:
                corps.append(r"\begin{itemize}")
                dans_liste = True
            item = re.sub(r"^\s*-\s+", "", brut)
            corps.append(r"\item %s" % _inline(item))
        else:
            fermer_liste()
            corps.append(_inline(brut) + r"\par")
    fermer_liste()
    return PREAMBULE.replace(r"\titleskip", "") + "\n".join(corps) + "\n\\end{document}\n"
def main(argv):
    src = Path(argv[0])
    out_pdf = Path(argv[1]) if len(argv) > 1 else src.with_suffix(".pdf")
    tex = md_vers_tex(src.read_text(encoding="utf-8"))
    tex_path = src.with_suffix(".tex")
    tex_path.write_text(tex, encoding="utf-8")
    for _ in range(2):
        r = subprocess.run(
            [XELATEX, "-interaction=nonstopmode", "-halt-on-error",
             "-output-directory", str(src.parent), str(tex_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if not out_pdf.exists():
        sys.stderr.write(r.stdout[-3000:])
        raise SystemExit("Echec compilation XeLaTeX")
    for ext in (".aux", ".log", ".out", ".tex"):
        src.with_suffix(ext).unlink(missing_ok=True)
    (src.parent / "texput.log").unlink(missing_ok=True)
    print(f"PDF genere : {out_pdf}")
if __name__ == "__main__":
    if not sys.argv[1:]:
        raise SystemExit(__doc__)
    main(sys.argv[1:])