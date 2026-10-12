"""生成一份双栏、带标题层级的测试 PDF，用于验证 PDF→Markdown 提取。
用法：python tools/make_sample_pdf.py testdata/sample.pdf
"""
import sys, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

OUT = sys.argv[1] if len(sys.argv) > 1 else "testdata/sample.pdf"
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)

TITLE = "Left Atrial Substrate and Ventricular Threshold Variability"
AUTHORS = "Zhao L, Chen H, Wang J, et al."
BODY = 8.2
LEAD = 11.0

LEFT_COLS = [
    [
        ("h2", "1. Introduction"),
        ("b", "Atrial fibrillation is the most common sustained arrhythmia, and pulmonary vein isolation has become the first-line rhythm control strategy for symptomatic paroxysmal AF."),
        ("b", "The substrate that permits recurrence remains incompletely characterised. Circulating proteins may offer a non-invasive window onto this substrate, yet pre-analytical handling has received little attention in existing proteomic reports."),
        ("b", "Two problems limit the literature. First, most cohorts are small and single-centre, so effect sizes remain unstable across studies."),
        ("b", "Second, peri-procedural anticoagulation and sedation shift protein concentrations independently of the ablation itself, and few studies adjust for this confounding."),
        ("h2", "2. Methods"),
        ("h3", "2.1 Study population"),
        ("b", "Patients undergoing first-time pulmonary vein isolation at a single centre were consecutively enrolled between March 2023 and October 2025."),
        ("b", "Exclusion criteria included active infection, autoimmune flare, malignancy within five years, and an estimated glomerular filtration rate below 30 mL per minute."),
    ],
    [
        ("h3", "2.2 Sample collection"),
        ("b", "Blood was drawn immediately before ablation and again at thirty days after the procedure, using an identical venepuncture protocol and fasting window."),
        ("b", "Samples were allowed to clot for thirty minutes, centrifuged at 2000 g for ten minutes, aliquoted, and frozen at minus 80 degrees Celsius within two hours."),
        ("h3", "2.3 Proteomic profiling"),
        ("b", "Protein abundance was measured by mass spectrometry, and protein identifiers were mapped against the 9606 human UniProt reference table."),
        ("b", "Differential abundance was assessed with limma using empirical Bayes moderation, with age, sex, body mass index, and baseline renal function included as covariates."),
        ("h3", "2.4 Verification cohort"),
        ("b", "An independent cohort of sixteen patients, drawn from separate admissions and not overlapping the discovery set, underwent targeted ELISA quantification of the candidate proteins."),
    ],
    [
        ("h2", "3. Results"),
        ("h3", "3.1 Differential abundance"),
        ("b", "Among 658 tested proteins, 41 passed the adjusted significance threshold after correction for multiple testing by the Benjamini-Hochberg procedure."),
        ("b", "Pathway analysis pointed consistently to complement and coagulation cascades, with the largest absolute log fold changes seen in complement component C3."),
        ("h3", "3.2 Recurrence prediction"),
        ("b", "Four proteins measured before ablation were independently associated with recurrence at twelve months in the discovery cohort."),
        ("b", "In the independent verification cohort the direction of effect was preserved for three of the four candidates, and for two the confidence interval excluded unity."),
        ("b", "Discrimination was moderate rather than strong. The area under the ROC curve for the combined panel was 0.71, which is not sufficient to support clinical use without a larger external cohort."),
        ("h2", "4. Discussion"),
        ("b", "Our main contribution is the demonstration that the ablation response itself is detectable in the circulating proteome."),
        ("b", "The discovery cohort is single-centre and modest in size, and the thirty-day window captures an acute response rather than a settled baseline."),
        ("b", "We therefore state a falsifiable prediction: in a cohort of at least two hundred patients followed for eighteen months, the four-protein panel should improve the area under the ROC curve above 0.75 over clinical variables alone."),
        ("h2", "References"),
        ("r", "[1] Van Gelder IC, Groenveld HF, Crijns HJ, et al. Lenient versus strict blood pressure control in patients with atrial fibrillation. N Engl J Med. 2010;362(15):1363-1373."),
        ("r", "[2] Kirchhof P, Camm AJ, Goette A, et al. Early rhythm-control therapy in patients with atrial fibrillation. N Engl J Med. 2020;383(13):1305-1316."),
        ("r", "[3] Heidenreich PA, Solis E, Kramer HM, et al. Predictors of stroke and mortality in patients with atrial fibrillation. Circulation. 2017;135(18):1786-1799."),
    ],
]

c = canvas.Canvas(OUT, pagesize=A4)
W, H = A4
ML, MR, MT, MB = 20 * mm, 20 * mm, 22 * mm, 20 * mm
colgap = 8 * mm
colw = (W - ML - MR - colgap) / 2


def wrap(text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


y = [H - MT, H - MT]
page = 1
cur_col = 0


def newpage():
    global page, y
    c.showPage()
    page += 1
    y = [H - MT, H - MT]


for group in LEFT_COLS:
    for kind, text in group:
        if kind == "h2":
            size, font, gap = 10.4, "Helvetica-Bold", 7
        elif kind == "h3":
            size, font, gap = 9.0, "Helvetica-Bold", 5
        elif kind == "r":
            size, font, gap = 7.0, "Helvetica", 5
        else:
            size, font, gap = BODY, "Helvetica", LEAD
        # 真实期刊双栏：先把左栏排到底，再排右栏（不做"最空栏优先"）
        for ln in wrap(text, font, size, colw):
            ci = cur_col
            if y[ci] < MB + 14:
                if ci == 0:
                    cur_col = 1          # 左栏排满 → 转到右栏
                else:
                    newpage()           # 右栏也满 → 换页，两栏重置
                    cur_col = 0
                ci = cur_col
            c.setFont(font, size)
            c.drawString(ML + ci * (colw + colgap), y[ci], ln)
            y[ci] -= size + (3.2 if kind == "b" else 2.0)
        y[cur_col] -= gap

# 首页顶部标题区（单栏通栏）
c.setFont("Helvetica-Bold", 13)
c.drawString(ML, H - 16 * mm, TITLE)
c.setFont("Helvetica", 8.6)
c.drawString(ML, H - 19.5 * mm, AUTHORS)
c.save()
print("wrote", OUT, os.path.getsize(OUT), "bytes,", page, "pages")
