# pip install python-pptx
import os
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

HERE = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
TEMPLATE = os.path.join(DOWNLOADS, "temp.pptx")          # company branded template
IMAGES = os.path.join(HERE, "images")
OUT = os.path.join(DOWNLOADS, "leak_detection_liquid_cooled_pcb.pptx")

prs = Presentation(TEMPLATE) if os.path.exists(TEMPLATE) else Presentation()
TITLE_CONTENT = prs.slide_layouts[1]  # adjust index if your template differs


def bullet_slide(title, bullets, image=None):
    s = prs.slides.add_slide(TITLE_CONTENT)
    s.shapes.title.text = title
    tf = s.placeholders[1].text_frame
    tf.word_wrap = True
    tf.text = bullets[0]
    tf.paragraphs[0].font.size = Pt(18)
    for b in bullets[1:]:
        p = tf.add_paragraph()
        p.text = b
        p.font.size = Pt(16)
    img_path = os.path.join(IMAGES, image) if image else None
    if img_path and os.path.exists(img_path):
        s.placeholders[1].width = Inches(6)  # text on left, image on right
        s.shapes.add_picture(img_path, Inches(6.6), Inches(1.8), width=Inches(3.2))
    return s


def comb_diagram(slide, left, top):
    """Draw an interdigitated comb pattern natively (used if no image supplied)."""
    copper = RGBColor(0xB8, 0x73, 0x33)
    w, h, gap = Inches(0.12), Inches(1.0), Inches(0.10)
    for i in range(8):
        x = left + i * (w + gap)
        y = top if i % 2 == 0 else top + Inches(0.3)
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        sh.fill.solid()
        sh.fill.fore_color.rgb = copper
        sh.line.fill.background()


# --- Title & intro ---
bullet_slide("Leak Detection for Liquid-Cooled PCBs\nin Datacenter Systems",
             ["Best practices: detection reliability, cost, board integration",
              "Igor Gurevich \u2014 Sept 2026"])
bullet_slide("Why Leak Detection Matters",
             ["Direct-to-chip liquid cooling is mainstream for high-TDP boards",
              "One undetected leak = board loss, rack downtime, cascading damage",
              "Goals: fast detection, low false positives, low BOM cost, BMC-actionable"])

# --- Methods, each with an optional image from images/ ---
bullet_slide("Method 1: Rope/Cable Sensors",
             ["Cable routed under cold plates, tubing, chassis low points",
              "Detects liquid anywhere along length (R or C change)",
              "+ Wide coverage, flexible, reusable",
              "\u2013 Condensation false positives, routing complexity, moderate cost",
              "Best for: system/chassis-level protection",
              "Examples: Molex, Amphenol, nVent Raychem TraceTek, Vertiv LT500Y"],
             image="rope_sensor.png")
s = bullet_slide("Method 2: Interdigitated PCB Traces",
             ["Exposed comb/grid copper at high-risk locations; liquid bridges gap",
              "+ Near-zero BOM cost, standard PCB process, pinpoint, fast",
              "\u2013 Limited coverage, flux contamination risk, on-board only",
              "Best for: cold plate ports, QD fittings, under connectors",
              "Examples: custom comb (0.3\u20130.5 mm gap, ENIG, no mask); Adafruit (prototype)"],
             image="pcb_traces.png")
if not os.path.exists(os.path.join(IMAGES, "pcb_traces.png")):
    comb_diagram(s, Inches(6.6), Inches(2.2))
bullet_slide("Method 3: Point (Spot) Sensors",
             ["Packaged discrete sensors at key locations",
              "+ High sensitivity, simple readout, off-the-shelf",
              "\u2013 Tiny coverage area; many units needed for wide protection",
              "Best for: critical single-point risks",
              "Examples: Honeywell WLD2, Sensata SC50 (water/glycol), Vertiv LT410"],
             image="spot_sensor.png")
bullet_slide("Method 4: Capacitive Sensors",
             ["Detect liquid via capacitance change on pads",
              "+ Rejects condensation, works through conformal coating",
              "\u2013 More complex electronics, higher cost",
              "Best for: environments intolerant of false positives",
              "Examples: Amphenol/Sensirion custom OEM; Seeed Grove (prototype)"],
             image="capacitive_sensor.png")

# --- Comparison matrix as a real table ---
s = prs.slides.add_slide(TITLE_CONTENT)
s.shapes.title.text = "Comparison Matrix"
rows = [("Method", "Reliability", "Cost", "Integration", "Coverage"),
        ("Rope/Cable", "High", "Mod.", "Mod.", "Large"),
        ("Interdigitated Traces", "Med\u2013High", "Low", "Low", "Localized"),
        ("Point Sensors", "Medium", "Low", "Low", "Localized"),
        ("Capacitive", "High", "Mod\u2013Hi", "Mod.", "Localized/Med")]
tbl = s.shapes.add_table(len(rows), 5, Inches(0.6), Inches(1.8),
                         Inches(9), Inches(3)).table
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val
        cell.text_frame.paragraphs[0].font.size = Pt(14)
        if r == 0:
            cell.text_frame.paragraphs[0].font.bold = True

bullet_slide("Best Practices",
             ["Redundancy: wide-area rope + point-of-risk traces",
              "Placement: under ports, along coolant lines, gravity low points",
              "Validate sensors against coolant chemistry (PG25 vs dielectric)",
              "BMC integration: debounce logic \u2192 alert, pump stop, valve isolation"])
bullet_slide("Recommended Architecture",
             ["PCB comb traces at cold plate fittings & QDs (~free in BOM)",
              "Rope sensor along manifold/tubing path & chassis low points",
              "Signals \u2192 BMC with condensation-rejection logic",
              "Confirmed leak \u2192 automated flow isolation + alert",
              "Industry practice: Dell/HPE/Lenovo hybrid approach"])
bullet_slide("References",
             ["Molex leak detection cables \u2014 molex.com/en-us/products/cable-assemblies/leak-detection-cables",
              "nVent Raychem TraceTek \u2014 nvent.com/en-us/raychem/tracetek",
              "Vertiv Liebert leak detection \u2014 vertiv.com (Monitoring > Liebert Leak Detection Systems)",
              "Honeywell advanced sensing \u2014 sps.honeywell.com; Sensata SC50 \u2014 sensata.com",
              "Seeed Grove water sensor \u2014 wiki.seeedstudio.com/Grove-Water_Sensor",
              "Schneider Electric / ASUS liquid cooling whitepapers"])

prs.save(OUT)
print(f"Saved {OUT}")
