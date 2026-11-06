"""Visualize provisional work categories and the separately verified execution scope."""
from pathlib import Path
import json
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parent
d = json.loads((ROOT / "automation-breakdown.json").read_text())
NAVY, TEAL, GREEN, AMBER = "#234E70", "#287D8E", "#4B8F72", "#95600C"
INK, MUTED, BORDER, PAPER = "#233D4D", "#58707C", "#D7E1E5", "#F3F6F7"
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none"})
fig = Figure(figsize=(14.8, 10.5), layout="constrained", facecolor=PAPER)
FigureCanvasAgg(fig)
gs = fig.add_gridspec(4, 12, height_ratios=[1.65, 3.8, 2.6, .6], hspace=.14, wspace=.14)

def text(ax, x, y, s, size=12, color=INK, weight="normal", **kw):
    return ax.text(x, y, s, transform=ax.transAxes, va="center", fontsize=size,
                   color=color, fontweight=weight, **kw)

def card(spec, fill="white", edge=BORDER):
    ax = fig.add_subplot(spec); ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((.005, .005), .99, .99,
        boxstyle="round,pad=0,rounding_size=.025", transform=ax.transAxes,
        facecolor=fill, edgecolor=edge, linewidth=1))
    return ax

head = fig.add_subplot(gs[0, :]); head.set_axis_off()
text(head, .006, .91, "ADF SENTINEL / AUTOMATION SCOPE", 11, TEAL, "bold")
text(head, .994, .91, "Recorded run: October 31, 2026", 10, MUTED, ha="right")
text(head, .006, .67, "Current proof and candidates for review", 25, NAVY, "bold")
text(head, .006, .40, f"Automatic execution from model suggestions: {d['automatic_eligible_predictions']} of {d['advisory_prediction_count']} eligible", 17, AMBER, "bold")
text(head, .006, .14, "Percentages below describe unreviewed text categories. A validated can / cannot automation split is unknown.", 12.5, MUTED)

mix = card(gs[1, :7])
text(mix, .04, .91, f"Review buckets · {d['proposal_count']:,} proposed excerpts", 16.5, NAVY, "bold")
text(mix, .04, .815, "These are counts of proposals, not engineer time or execution eligibility.", 11, MUTED)
groups = d["groups"]
labels = ["Mechanical-change labels\nReview for potential automation", "Investigation / code\nHuman-led in this prototype", "Verification\nMixed automatic / human scope", "Defer / retain / block\nOwner decisions / missing inputs"]
plot = mix.inset_axes([.46, .20, .49, .54]); plot.set_facecolor("white")
plot.barh(range(4), [g["percent"] for g in groups], color=[TEAL, NAVY, "#7597A9", "#C7A26B"], height=.56, zorder=3)
plot.set_yticks(range(4), labels, fontsize=10.7); plot.invert_yaxis()
plot.set_xlim(0, 67); plot.set_xticks([0, 20, 40, 60]); plot.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
plot.tick_params(axis="both", length=0, pad=8, labelcolor=MUTED)
plot.grid(axis="x", color=BORDER, linewidth=.7, zorder=0)
for s in plot.spines.values(): s.set_visible(False)
for y, g in enumerate(groups):
    plot.text(g["percent"]+1, y, f"{g['percent']:.1f}%\n{g['count']:,}", va="center", fontsize=11, color=NAVY, fontweight="bold")
text(mix, .04, .065, "The remaining 74.1% has not been proven impossible to automate.", 11, AMBER)

detail = card(gs[1, 7:])
text(detail, .055, .91, "Inside the 25.9% mechanical bucket", 15.5, NAVY, "bold")
text(detail, .055, .815, "1,276 labels to review for exact, repeatable changes", 11.2, MUTED)
categories = {c["key"]: c for c in d["categories"]}
for y, key in zip([.68, .55, .42, .29], ["parameter_metadata", "approved_file", "dependency_pin", "shared_sync"]):
    c = categories[key]
    text(detail, .065, y, c["name"], 12, NAVY)
    text(detail, .93, y, f"{c['count']:,}  |  {c['percent']:.1f}%", 12, TEAL, "bold", ha="right")
text(detail, .065, .12, "All shares use the full 4,922-excerpt denominator.\nThis bucket includes false positives and missing inputs.", 10.5, AMBER, linespacing=1.6)

can = card(gs[2, :6], fill="#ECF5F0", edge="#D0E3D8")
text(can, .045, .87, "ALREADY SUPPORTED IN A CONTROLLED LOCAL COPY", 11, GREEN, "bold")
text(can, .045, .69, "Real replay: 1 pinned source-file replacement", 14.5, NAVY, "bold")
text(can, .045, .52, "Fixture replay: 2 parameter edits + 2 shared-file copies", 12.5, INK)
text(can, .045, .35, "Automatic checks: hashes, exact values, paths, variants and diffs", 11.2, MUTED)
text(can, .045, .16, "Other registered edits remain narrow: real actor key or fixture schema.\nA general real-ADF parameter / dependency editor is not established.", 10.7, MUTED, linespacing=1.6)

human = card(gs[2, 6:], fill="#FFF2D9", edge="#E8D5AE")
text(human, .045, .87, "CURRENTLY NEEDS PEOPLE OR ADDITIONAL CAPABILITY", 11, AMBER, "bold")
for y, line in zip([.69, .55, .41, .27, .13], [
    "Diagnose new bugs and develop / approve fixes",
    "Choose scientific values and interpret assay / QC results",
    "Resolve ambiguity; decide release, retain or defer actions",
    "Perform scientific / physical validation",
    "Build a real ADF: approved core builder / inputs still missing",
]):
    text(human, .045, y, "• " + line, 11.4, INK)

foot = fig.add_subplot(gs[3, :]); foot.set_axis_off()
text(foot, .006, .75, "Provisional labels include irrelevant or misclassified commentary—for example, Jira fix-version edits tagged as dependency changes.", 9.8, MUTED)
text(foot, .006, .20, "Sources: weak-action dataset · saved advisory predictions · executor registry · real-source and synthetic-fixture replay manifests. No effort-weighted coverage is available.", 9.3, MUTED)
for ext in ["png", "pdf", "svg"]:
    fig.savefig(ROOT / f"automation-scope.{ext}", dpi=180, pad_inches=.12)
print(str(ROOT / "automation-scope.png"))
