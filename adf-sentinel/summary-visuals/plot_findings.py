"""Create a summary from recorded results without changing the frozen campaign."""
from pathlib import Path
import json

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "findings-data.json").read_text())
NAVY, TEAL, GREEN = "#234E70", "#287D8E", "#4B8F72"
AMBER, PALE_AMBER = "#95600C", "#FFF2D9"
INK, MUTED, BORDER, PAPER = "#233D4D", "#58707C", "#D7E1E5", "#F3F6F7"
mpl.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": INK,
    "savefig.facecolor": PAPER,
})
fig = Figure(figsize=(14.8, 10.8), layout="constrained", facecolor=PAPER)
FigureCanvasAgg(fig)
grid = fig.add_gridspec(5, 12, height_ratios=[1.12, 1.02, 3.90, 1.72, .43],
                        hspace=.14, wspace=.14)


def text(ax, x, y, value, size=12, color=INK, weight="normal", **kwargs):
    return ax.text(x, y, value, transform=ax.transAxes, fontsize=size,
                   color=color, fontweight=weight, va="center", **kwargs)


def card(spec, fill="white", edge=BORDER):
    ax = fig.add_subplot(spec)
    ax.set_axis_off()
    ax.add_patch(FancyBboxPatch((.005, .005), .99, .99,
        boxstyle="round,pad=0,rounding_size=.025", facecolor=fill,
        edgecolor=edge, linewidth=1, transform=ax.transAxes))
    return ax


header = fig.add_subplot(grid[0, :])
header.set_axis_off()
text(header, .006, .89, "ADF SENTINEL  /  RECORDED FINDINGS", 11, TEAL, "bold")
text(header, .994, .89, "Run: October 31, 2026 · Los Angeles", 10, MUTED, ha="right")
text(header, .006, .55, "Evidence collected. Local replays checked.", 25, NAVY, "bold")
text(header, .006, .16,
     "Validated accuracy, full ADF assembly and time saved remain unproven.", 13, MUTED)
text(header, .994, .47, f"COLLECTION PARTIAL\n{data['collection']['pending_requests']:,} reader requests pending",
     10.5, AMBER, "bold", ha="right", linespacing=1.6,
     bbox={"facecolor": PALE_AMBER, "edgecolor": "none", "boxstyle": "round,pad=.7"})

c = data["collection"]
metrics = [
    (c["pages"], "CONFLUENCE PAGES", "Actual bodies and metadata read"),
    (c["releases"], "RELEASE ENTRIES", f"Across {len(c['families'])} assay families"),
    (c["validated_issues"], "JIRA ISSUES", f"{c['release_associated_issues']:,} associated with release rows"),
    (c["attachments_downloaded"], "ORIGINALS DOWNLOADED", f"{c['attachments_metadata']:,} attachment metadata records"),
]
for i, (value, label, detail) in enumerate(metrics):
    ax = card(grid[1, i*3:(i+1)*3])
    text(ax, .07, .82, label, 10, TEAL, "bold")
    text(ax, .07, .48, f"{value:,}", 30, NAVY, "bold")
    text(ax, .07, .16, detail, 10.5, MUTED)

work = card(grid[2, :7])
text(work, .04, .92, "What the proposed actions look like", 17, NAVY, "bold")
text(work, .04, .835, f"{data['proposed_actions']:,} automatically proposed action excerpts · all unreviewed", 11.5, AMBER)
labels = {
    "investigation_code": "Investigation / code",
    "verification_only": "Verification only",
    "parameter_metadata": "Parameter / metadata",
    "approved_file": "Add / replace a file",
    "defer_inherit_block": "Retain / defer / block",
    "dependency_pin": "Dependency version",
    "shared_sync": "Shared variant sync",
}
items = sorted(data["proposed_action_counts"].items(), key=lambda item: item[1], reverse=True)
bars = work.inset_axes([.36, .18, .59, .59])
bars.set_facecolor("white")
bars.barh(range(len(items)), [n for _, n in items], height=.62,
          color=[NAVY] + [TEAL] * (len(items)-1), zorder=3)
bars.set_yticks(range(len(items)), [labels[k] for k, _ in items], fontsize=11.5)
bars.invert_yaxis()
bars.set_xlim(0, 3400)
bars.set_xticks([0, 1000, 2000, 3000])
bars.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
bars.tick_params(axis="both", length=0, labelsize=10)
bars.tick_params(axis="y", labelsize=11.5, pad=8)
bars.grid(axis="x", color=BORDER, linewidth=.7, zorder=0)
for spine in bars.spines.values():
    spine.set_visible(False)
for y, (_, n) in enumerate(items):
    suffix = f" · {n/data['proposed_actions']:.0%}" if y == 0 else ""
    bars.text(n+55, y, f"{n:,}{suffix}", va="center", fontsize=10.5,
              color=NAVY, fontweight="bold" if y == 0 else "normal")
bars.set_xlabel("Proposed action excerpts", fontsize=10.5, labelpad=9)
text(work, .04, .045, "Each proposal still needs evidence and action review.", 11, MUTED)

ready = card(grid[2, 7:])
text(ready, .055, .92, "Readiness for a strict benchmark", 16.5, NAVY, "bold")
text(ready, .055, .835, f"{data['model_fits']} model fits on {data['training_rows']:,} exploratory rows", 11.5, MUTED)
text(ready, .07, .727, "Provisional release-date split", 11, NAVY, "bold")
timeline = ready.inset_axes([.07, .625, .86, .07])
colors = [NAVY, TEAL, GREEN, "#E7D6B9"]
keys = ["train", "validation", "test", "undated"]
left = 0
for key, color in zip(keys, colors):
    n = data["release_date_partitions"][key]
    timeline.barh(0, n, left=left, height=1, color=color)
    timeline.text(left+n/2, 0, str(n), ha="center", va="center", fontsize=10,
                  fontweight="bold", color=NAVY if key == "undated" else "white")
    left += n
timeline.set_xlim(0, left)
timeline.set_ylim(-.5, .5)
timeline.set_axis_off()
for i, (label, color) in enumerate(zip(["Train", "Validation", "Reserved test", "Undated"], colors)):
    x, y = .075 + (i % 2) * .46, .557 - (i // 2) * .061
    ready.add_patch(Rectangle((x, y-.009), .023, .018, transform=ready.transAxes,
                              facecolor=color, edgecolor="none"))
    text(ready, x+.04, y, label, 10.5, MUTED)
undated = data["release_date_partitions"]["undated"]
text(ready, .07, .393,
     f"{undated} / {c['releases']} entries have no reported date.\nAll bundling cutoffs await confirmation.",
     11, MUTED, linespacing=1.8)
text(ready, .085, .225, str(data["reviewed_actions"]), 29, AMBER, "bold")
text(ready, .54, .225, str(data["eligible_strict_cases"]), 29, AMBER, "bold")
text(ready, .085, .133, "reviewed action labels", 10.5, MUTED)
text(ready, .54, .133, "eligible strict cases", 10.5, MUTED)
text(ready, .07, .04, "Automatic execution disabled", 11.5, AMBER, "bold")

execution = card(grid[3, :4], fill="#ECF5F0", edge="#D0E3D8")
text(execution, .06, .84, "CHECKED LOCAL EXECUTION", 10, GREEN, "bold")
text(execution, .06, .61, "1 real file + 4 fixture actions", 17, NAVY, "bold")
text(execution, .06, .35, "9 checks passed across the two replays.", 11, MUTED)
text(execution, .06, .14, "Full ADF: approved core builder missing.", 10.7, AMBER)

checks = card(grid[3, 4:8], fill="#ECF5F0", edge="#D0E3D8")
text(checks, .06, .84, "VERIFICATION", 10, GREEN, "bold")
text(checks, .06, .61, f"{data['unit_tests_passed']} tests passed", 21, NAVY, "bold")
text(checks, .06, .35, f"Browser: {data['browser_chapters']} chapters at {data['browser_viewports']} screen sizes.", 11, MUTED)
text(checks, .06, .14, f"Archives: {data['archive_checks_matched']} / {data['archive_checks_total']} checksum declarations matched.", 10.7, MUTED)

effort = card(grid[3, 8:], fill=PALE_AMBER, edge="#E8D5AE")
text(effort, .06, .84, "ENGINEERING SAVINGS", 10, AMBER, "bold")
text(effort, .06, .61, "Not measured", 21, AMBER, "bold")
text(effort, .06, .35, "0 matched human timing observations.", 11, MUTED)
text(effort, .06, .14, "Labor and calendar-time benefit unknown.", 10.7, MUTED)

footer = fig.add_subplot(grid[4, :])
footer.set_axis_off()
text(footer, .006, .75,
     "Counts come from the recorded run. Weak labels are proposals; local checks establish software behavior and file integrity.", 9.5, MUTED)
text(footer, .006, .18,
     "Sources: RUN_REPORT.md · collection / label / split manifests · training comparison · benchmark, replay and verification receipts", 9.1, MUTED)

for extension in ["png", "pdf", "svg"]:
    fig.savefig(ROOT / f"adf-findings.{extension}", dpi=180, pad_inches=.12)
(ROOT / "plot-environment.json").write_text(json.dumps({"matplotlib": mpl.__version__}, indent=2) + "\n")
print(json.dumps({"png": str(ROOT / "adf-findings.png"), "matplotlib": mpl.__version__}))
