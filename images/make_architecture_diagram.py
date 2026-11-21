"""Generate images/architecture_overview.png for DESIGN.md Section 4.

Layout: two rows.
  Top row (distributed participants):  Operator service -> Budget channel
      -> Workload scheduler -> Admitted power demand
  Bottom row (electrical simulation, one Python process):
      Load-step generator -> Converter+storage model -> SMIB grid model
      -> ZIP baseline -> Metrics -> Output artifacts
Arrows are labeled with the actual data exchanged.
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1900, 1050
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

try:
    F_TITLE = ImageFont.truetype("arialbd.ttf", 30)
    F_BOX = ImageFont.truetype("arialbd.ttf", 24)
    F_TXT = ImageFont.truetype("arial.ttf", 21)
    F_SMALL = ImageFont.truetype("arial.ttf", 18)
except OSError:
    F_TITLE = F_BOX = F_TXT = F_SMALL = ImageFont.load_default()


def box(xy, title, lines, fill, outline="black", tfont=F_BOX, lfont=F_TXT):
    x0, y0, x1, y1 = xy
    d.rounded_rectangle(xy, radius=14, fill=fill, outline=outline, width=3)
    d.text(((x0 + x1) / 2, y0 + 18), title, font=tfont, fill="black",
           anchor="mm")
    for i, ln in enumerate(lines):
        d.text(((x0 + x1) / 2, y0 + 62 + i * 30), ln, font=lfont, fill="#222222",
               anchor="mm")


def arrow(p0, p1, label, color="#1a5276", dashed=False):
    if dashed:
        # simple dashed line
        x0, y0 = p0; x1, y1 = p1
        n = 30
        for i in range(0, n, 2):
            xa = x0 + (x1 - x0) * i / n; ya = y0 + (y1 - y0) * i / n
            xb = x0 + (x1 - x0) * (i + 1) / n; yb = y0 + (y1 - y0) * (i + 1) / n
            d.line([xa, ya, xb, yb], fill=color, width=4)
    else:
        d.line([p0, p1], fill=color, width=4)
    d.polygon([p1,
               (p1[0] - 14, p1[1] - 8), (p1[0] - 14, p1[1] + 8)],
              fill=color)
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    d.text((mx, my - 14), label, font=F_SMALL, fill=color, anchor="mm",
           stroke_width=3, stroke_fill="white")


d.text((W / 2, 40), "Architecture overview - CSC 59866 prototype (one laptop, one Python process)",
       font=F_TITLE, fill="black", anchor="mm")

# ---------- Top row: distributed participants ----------
d.text((60, 110), "DISTRIBUTED PART (two independent participants + failable channel)",
       font=F_BOX, fill="#7d3c98", anchor="lm")

box((80, 160, 430, 360), "Grid operator service",
    ["SIMULATED software module", "decides whether to issue", "a power budget (MW)", "own state: none"],
    "#e8daef")
box((620, 160, 970, 400), "Budget message channel",
    ["SIMULATED channel (not a", "real protocol stack)", "carries {budget_mw,", "seq_number, timestamp}", "configurable delay/loss"],
    "#fdebd0")
box((1160, 160, 1510, 400), "Workload scheduler",
    ["SIMULATED software module", "decides which queued jobs", "to admit under latest", "received budget", "state: job queue + latest seq/budget"],
    "#d5f5e3")
box((1620, 200, 1840, 340), "Admitted power",
    ["P_admitted(t)", "(MW)"], "#f9f9f9")

arrow((430, 260), (620, 260), "budget message")
arrow((970, 260), (1160, 260), "deliver / drop")
arrow((1510, 260), (1620, 270), "admit jobs")

# channel drop indicator
arrow((795, 400), (795, 470), "dropped messages", color="#922b21", dashed=True)
d.text((795, 488), "(loss probability)", font=F_SMALL, fill="#922b21", anchor="mm")

# ---------- Middle: runner ----------
box((700, 500, 1200, 640), "Scenario runner",
    ["reads config (baseline MW, step MW,", "step time, duration, delay/loss)", "coordinates all parts, writes outputs"],
    "#d6eaf8")
arrow((1335, 260), (1100, 500), "P_admitted(t) + job trace", color="#1a5276")
arrow((960, 500), (795, 400), "issue budget?", color="#7d3c98")

# ---------- Bottom row: electrical simulation ----------
d.text((60, 700), "ELECTRICAL PART (one Python process: NumPy/SciPy ODE solve; ZIP baseline analytic)",
       font=F_BOX, fill="#1a5276", anchor="lm")

box((80, 750, 380, 940), "Load-step generator",
    ["P_load(t): 40 MW base", "+ 20 MW step at t=2 s", "deterministic"], "#fdf2e9")
box((480, 750, 800, 990), "Reduced converter",
    ["+ storage model (averaged)", "SIMULATED: cycle-averaged,", "not switching-level", "states: i_g, v_pcc, i_c,", "v_dc, integrator", "BUILT this semester"], "#d5f5e3")
box((900, 750, 1220, 990), "SMIB grid model",
    ["SIMULATED grid (single-", "machine infinite bus,", "not a real network)", "Thevenin source + line", "impedance", "states: i_g, v_pcc"], "#d5f5e3")
box((1320, 750, 1560, 940), "ZIP baseline",
    ["static constant-power", "reference model", "no converter dynamics"], "#f9f9f9")
box((1660, 750, 1860, 940), "Metrics + artifacts",
    ["peak dV, settling time,", "energy balance, exceedance,", "queue delay -> CSV/JSON"], "#fdf2e9")

arrow((380, 845), (480, 845), "P_load(t)")
arrow((800, 845), (900, 845), "converter demand")
arrow((1220, 845), (1320, 845), "V_pcc(t), P_grid(t)")
arrow((1560, 845), (1660, 845), "compare")
arrow((1100, 640), (230, 750), "admitted power caps P_load(t)", color="#7d3c98")

img.save("images/architecture_overview.png")
print("saved images/architecture_overview.png")
