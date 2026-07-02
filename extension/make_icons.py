from pathlib import Path
from PIL import Image, ImageDraw
SIZES = [16, 32, 48, 128]
SUP = 512
ORANGE = (230, 126, 34, 255)
BLEU = (52, 152, 219, 255)
BLANC = (255, 255, 255, 255)
COMMENTS_DIR = Path(
    r"C:\dev\ArsenalArguments"
    r"\comments_extension\icons")
CANDIDATURES_DIR = Path(__file__).resolve().parent / "icons"
def _canvas(color):
    img = Image.new("RGBA", (SUP, SUP), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, SUP - 1, SUP - 1],
                        radius=int(SUP * 0.22), fill=color)
    return img, d
def icone_commentaires():
    img, d = _canvas(ORANGE)
    m = SUP * 0.18
    bx0, by0, bx1, by1 = m, m, SUP - m, SUP - m * 1.7
    d.rounded_rectangle([bx0, by0, bx1, by1],
                        radius=int(SUP * 0.14), fill=BLANC)
    tx = bx0 + (bx1 - bx0) * 0.26
    d.polygon([(tx, by1 - 2), (tx + SUP * 0.17, by1 - 2),
               (tx, by1 + SUP * 0.17)], fill=BLANC)
    cy = (by0 + by1) / 2
    rr = SUP * 0.052
    for frac in (0.30, 0.50, 0.70):
        cx = bx0 + (bx1 - bx0) * frac
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=ORANGE)
    return img
def icone_candidatures():
    img, d = _canvas(BLEU)
    px0, py0 = SUP * 0.27, SUP * 0.15
    px1, py1 = SUP * 0.73, SUP * 0.85
    fold = SUP * 0.17
    d.polygon([(px0, py0), (px1 - fold, py0), (px1, py0 + fold),
               (px1, py1), (px0, py1)], fill=BLANC)
    d.polygon([(px1 - fold, py0), (px1, py0 + fold),
               (px1 - fold, py0 + fold)], fill=(200, 220, 236, 255))
    lx0 = px0 + (px1 - px0) * 0.17
    lx1 = px1 - (px1 - px0) * 0.17
    ep = SUP * 0.030
    for frac in (0.40, 0.55, 0.70):
        ly = py0 + (py1 - py0) * frac
        d.rounded_rectangle([lx0, ly - ep, lx1, ly + ep],
                            radius=int(ep), fill=BLEU)
    return img
def exporter(image, dossier):
    dossier.mkdir(parents=True, exist_ok=True)
    for s in SIZES:
        image.resize((s, s), Image.LANCZOS).save(dossier / f"icon{s}.png")
    print(f"  {len(SIZES)} icônes -> {dossier}")
def main():
    print("Génération des icônes Arsenal :")
    if COMMENTS_DIR.parent.exists():
        exporter(icone_commentaires(), COMMENTS_DIR)
    else:
        print(f"  (ignoré : {COMMENTS_DIR.parent} introuvable)")
    exporter(icone_candidatures(), CANDIDATURES_DIR)
    print("Terminé.")
if __name__ == "__main__":
    main()