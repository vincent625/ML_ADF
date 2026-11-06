"""Rebuild README figures from aggregate data without loading private source text.

Requires Matplotlib (verified with 3.11.2). Run this file directly to use the
adjacent figure-data.json. Optional --refresh-source-root rebuilds aggregates
from an authorized local source snapshot and copies its existing screenshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.ticker import StrMethodFormatter

ROOT = Path(__file__).resolve().parent
COLORS = {
    "green": "#00876A", "green_light": "#EAF6F1",
    "amber": "#B57800", "amber_bar": "#D69B27", "amber_light": "#FFF5DF",
    "gray": "#66727C", "gray_light": "#F1F3F5", "ink": "#1F2933",
    "muted": "#52616D", "line": "#D8DFE4", "white": "#FFFFFF",
}
LABELS = {
    "investigation_code": "Investigation / code",
    "verification_only": "Verification",
    "parameter_metadata": "Parameter / metadata",
    "approved_file": "File addition / replacement",
    "defer_inherit_block": "Retain / defer / block",
    "dependency_pin": "Dependency version",
    "shared_sync": "Shared variant change",
}


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def aggregate_sources(source: Path, requirements_source: Path | None = None) -> dict:
    """Keep source locations relative and store no ticket descriptions or secrets."""
    source = source.resolve()
    requirements_source = (requirements_source or ROOT.parents[1]).resolve()
    names = {
        "issues": "adf-sentinel/data/extracted/issues.jsonl",
        "releases": "adf-sentinel/data/extracted/releases.jsonl",
        "actions": "adf-sentinel/data/labels/weak_actions.jsonl",
        "sentinel_verification": "adf-sentinel/runs/verification/results.json",
        "real_replay": "adf-sentinel/runs/sandbox/fb888a2792a7aeea64b5/manifest.json",
        "synthetic_replay": "adf-sentinel/runs/sandbox/0b4c92a31b3438a045c8/manifest.json",
        "workbench_summary": "adf-review-workbench/results/build-summary.json",
        "workbench_verification": "adf-review-workbench/results/verification/results.json",
        "quality_audit": "adf-review-workbench/results/bottlenecks.json",
        "upstream_readme": "docs/upstream/README.md",
        "upstream_extractor": "src/requirements/extractor.py",
        "upstream_traceability": "src/requirements/traceability.py",
        "screenshot": "adf-review-workbench/results/verification/evidence-desktop.png",
    }
    def source_path(role):
        return (requirements_source if role.startswith("upstream_") else source) / names[role]

    rows = list(read_jsonl(source / names["issues"]))
    releases = list(read_jsonl(source / names["releases"]))
    actions = list(read_jsonl(source / names["actions"]))
    load = lambda key: json.loads((source / names[key]).read_text())
    verification = load("sentinel_verification")
    real, synthetic = load("real_replay"), load("synthetic_replay")
    workbench, quality = load("workbench_summary"), load("quality_audit")
    listed = {key for release in releases for key in release.get("listed_issue_keys", [])}
    associated = {issue["issue_key"] for issue in rows if issue.get("release_ids")}
    if listed != associated:
        raise ValueError("Release-list and issue-association counts disagree")
    screenshot = source / names["screenshot"]
    shutil.copyfile(screenshot, ROOT / "workbench-preview.png")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recorded_run_dates": {"sentinel": "2026-10-31 (America/Los_Angeles)",
                               "workbench": "2026-11-03 (America/Los_Angeles)"},
        "scope": {
            "collected_issue_records": len(rows), "release_listed_issue_keys": len(listed),
            "issue_keys_with_candidate_actions": len({item["issue_key"] for item in actions}),
            "unreviewed_excerpts": len(actions),
            "last_stage_changes_unit_from_issues_to_excerpts": True,
            "interpretation": "Context and software work are included; not a pure ADF-edit corpus.",
        },
        "action_categories": [{"key": key, "label": LABELS.get(key, key), "count": count,
                               "percent": 100 * count / len(actions)}
                              for key, count in Counter(item["category"] for item in actions).most_common()],
        "quality_review": {
            "flagged_excerpts": quality["quality_review_flags"]["flag_count"],
            "counts_by_reason": quality["quality_review_flags"]["counts_by_reason"],
            "interpretation": "Candidates for review; not confirmed wrong labels and not subtracted from totals.",
        },
        "delivered": {
            "upstream": {"numbered_requirement_extraction": True, "exact_artifact_name_linking": True,
                         "output_review_state": "pending",
                         "original_tests_directory_present": False,
                         "test_claim": "No original upstream test suite supplied; combined package checks are separate."},
            "sentinel": {"focused_tests_passed": verification["unit_and_local_http"]["passed"],
                         "real_source_file_replay_actions": real["actions_attempted"],
                         "real_structural_checks_passed": sum(item["passed"] for item in real["checks"]),
                         "synthetic_actions": synthetic["actions_attempted"],
                         "synthetic_checks_passed": sum(item["passed"] for item in synthetic["checks"])},
            "workbench": {"packets": workbench["packets"], "cached_comments_shown": workbench["comments_shown"],
                          "pending_drafts": workbench["drafts"], "review_ready": workbench["review_ready"],
                          "focused_tests_passed": load("workbench_verification")["unit"]["tests"]},
            "unknown_or_pending": {"validated_accuracy": None, "human_time_savings": None,
                                   "genuine_adf_assembly": False, "new_approvals": 0},
        },
        "source_files": [{"role": role, "snapshot_relative_path": relative,
                          "sha256": digest(source_path(role)), "bytes": source_path(role).stat().st_size}
                         for role, relative in names.items()],
        "screenshot": {"file": "workbench-preview.png", "sha256": digest(screenshot),
                       "copied_original_bytes_without_image_editing": True},
        "caveats": ["Labels are unreviewed, and excerpt counts are not engineer hours.",
                    "Category shares are not validated automation eligibility or savings.",
                    "Local structural checks and fixtures do not establish scientific validation.",
                    "All verification counts are recorded completed runs, not newly rerun suites."],
    }


def setup() -> None:
    mpl.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 12, "axes.labelsize": 12,
        "axes.titlesize": 19, "xtick.labelsize": 11, "ytick.labelsize": 13,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "text.color": COLORS["ink"], "axes.labelcolor": COLORS["muted"],
        "xtick.color": COLORS["muted"], "ytick.color": COLORS["ink"],
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.dpi": 180, "savefig.facecolor": "white",
    })


def new_figure(size: tuple[float, float]) -> Figure:
    figure = Figure(figsize=size, layout="constrained")
    FigureCanvasAgg(figure)
    return figure


def save(figure: Figure, name: str) -> list[Path]:
    outputs = []
    for extension in ("png", "svg"):
        path = ROOT / f"{name}.{extension}"
        metadata = {"Creator": "ADF combined README figure builder"}
        if extension == "svg":
            metadata["Date"] = None
        figure.savefig(path, bbox_inches="tight", pad_inches=0.15, metadata=metadata)
        outputs.append(path)
    return outputs


def card(ax, xy, width, height, face, edge):
    patch = FancyBboxPatch(xy, width, height, boxstyle="round,pad=0.012,rounding_size=0.018",
                          transform=ax.transAxes, facecolor=face, edgecolor=edge, linewidth=1.3)
    ax.add_patch(patch)


def scope_flow(data: dict) -> list[Path]:
    figure = new_figure((13.8, 4.8))
    ax = figure.add_subplot()
    ax.set_axis_off()
    ax.text(.02, .96, "From collected tickets to proposed excerpts", transform=ax.transAxes,
            fontsize=22, fontweight="bold", va="top")
    ax.text(.02, .85, "Recorded evidence scope · a change of unit at the last step", transform=ax.transAxes,
            fontsize=13, color=COLORS["muted"])
    scope = data["scope"]
    values = [scope["collected_issue_records"], scope["release_listed_issue_keys"],
              scope["issue_keys_with_candidate_actions"], scope["unreviewed_excerpts"]]
    labels = ["collected Jira\nissue records", "release-listed\nissue keys",
              "issue keys with\ncandidate actions", "unreviewed\naction excerpts"]
    starts = [.025, .275, .525, .775]
    for index, (start, value, label) in enumerate(zip(starts, values, labels)):
        color = COLORS["amber"] if index == 3 else COLORS["green"]
        face = COLORS["amber_light"] if index == 3 else COLORS["green_light"]
        card(ax, (start, .37), .195, .33, face, color)
        ax.text(start + .0975, .60, f"{value:,}", transform=ax.transAxes,
                fontsize=31, fontweight="bold", color=color, ha="center", va="center")
        ax.text(start + .0975, .46, label, transform=ax.transAxes,
                fontsize=13, ha="center", va="center", linespacing=1.35)
        if index < 3:
            arrow = FancyArrowPatch((start + .214, .535), (starts[index + 1] - .02, .535),
                                    transform=ax.transAxes, arrowstyle="-|>", mutation_scale=17,
                                    color=COLORS["gray"], linewidth=1.5)
            ax.add_patch(arrow)
    ax.text(.372, .26, "Tickets / issue keys", transform=ax.transAxes,
            ha="center", fontsize=12, color=COLORS["green"], fontweight="bold")
    ax.text(.872, .26, "Excerpts · different unit", transform=ax.transAxes,
            ha="center", fontsize=12, color=COLORS["amber"], fontweight="bold")
    ax.text(.02, .09, "Equal-size cards show stages, not proportions. One ticket can yield multiple excerpts.",
            transform=ax.transAxes, fontsize=11.5, color=COLORS["muted"])
    ax.text(.02, .02, "The corpus includes contextual software work, investigation and administrative comments.",
            transform=ax.transAxes, fontsize=11.5, color=COLORS["muted"])
    return save(figure, "scope-flow")


def action_mix(data: dict) -> list[Path]:
    figure = new_figure((12.8, 7.5))
    grid = figure.add_gridspec(2, 1, height_ratios=[5.8, 1.2])
    ax, note = figure.add_subplot(grid[0]), figure.add_subplot(grid[1])
    categories = data["action_categories"]
    ax.barh(range(len(categories)), [item["count"] for item in categories],
            color=COLORS["amber_bar"], height=.63, zorder=3)
    ax.set_yticks(range(len(categories)), [item["label"] for item in categories])
    ax.invert_yaxis()
    ax.set_xlim(0, 3150)
    ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.set_xticks([0, 500, 1000, 1500, 2000, 2500, 3000])
    ax.set_xlabel("Number of proposed excerpts")
    ax.set_title("What the proposed excerpts describe", loc="left", pad=39, fontweight="bold")
    ax.text(0, 1.04, "4,922 excerpts · seven proposed categories · labels remain unreviewed",
            transform=ax.transAxes, fontsize=12, color=COLORS["muted"])
    ax.tick_params(axis="y", length=0, pad=12)
    ax.grid(axis="x", color=COLORS["line"], linewidth=.8, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for index, item in enumerate(categories):
        ax.text(item["count"] + 45, index, f"{item['count']:,}  ({item['percent']:.1f}%)",
                va="center", fontsize=12.5, fontweight="bold", color=COLORS["ink"])
    note.set_axis_off()
    card(note, (.015, .09), .97, .78, COLORS["amber_light"], COLORS["line"])
    note.text(.035, .64, "197 quality-review candidates", transform=note.transAxes,
              fontsize=13, fontweight="bold", va="center", color=COLORS["amber"])
    note.text(.035, .31, "Flags are not confirmed corrections; all 4,922 excerpts remain in the denominator.\n"
              "These shares describe excerpt counts. They do not measure engineer hours, automation or savings.",
              transform=note.transAxes, fontsize=11.3, va="center", color=COLORS["muted"], linespacing=1.45)
    return save(figure, "action-mix")


def delivered_results(data: dict) -> list[Path]:
    figure = new_figure((14, 7.8))
    ax = figure.add_subplot()
    ax.set_axis_off()
    ax.text(.02, .975, "Three complementary parts, with explicit evidence limits", transform=ax.transAxes,
            fontsize=22, fontweight="bold", va="top")
    ax.text(.02, .90, "Green: implemented or recorded local check   ·   Amber: pending review   ·   Gray: unknown / unavailable",
            transform=ax.transAxes, fontsize=11.6, color=COLORS["muted"])
    columns = [(.025, "UPSTREAM", "Requirements traceability"),
               (.36, "ADF SENTINEL", "Evidence and local replay"),
               (.695, "REVIEW WORKBENCH", "Prepare and clarify changes")]
    for start, label, title in columns:
        card(ax, (start, .27), .28, .55, COLORS["white"], COLORS["line"])
        ax.text(start + .015, .775, label, transform=ax.transAxes, fontsize=10.5,
                color=COLORS["green"], fontweight="bold")
        ax.text(start + .015, .715, title, transform=ax.transAxes, fontsize=14,
                color=COLORS["ink"], fontweight="bold")
    upstream_rows = [
        ("Numbered requirements extracted", "green"),
        ("Manifest artifact names linked", "green"),
        ("Traceability output: pending review", "amber"),
        ("Original upstream test suite:\nnot supplied", "gray"),
    ]
    sentinel = data["delivered"]["sentinel"]
    sentinel_rows = [
        (f"{sentinel['focused_tests_passed']} focused tests passed", "green"),
        (f"{sentinel['real_source_file_replay_actions']} real source-file replay\n{sentinel['real_structural_checks_passed']} structural checks passed", "green"),
        (f"{sentinel['synthetic_actions']} synthetic operations\n{sentinel['synthetic_checks_passed']} fixture checks passed", "green"),
    ]
    workbench = data["delivered"]["workbench"]
    workbench_rows = [
        (f"{workbench['packets']} evidence packets\n{workbench['cached_comments_shown']} cached comments", "green"),
        (f"{workbench['focused_tests_passed']} focused tests passed", "green"),
        (f"{workbench['pending_drafts']} pending drafts\n{workbench['review_ready']} review-ready records", "amber"),
    ]
    for start, rows in [(columns[0][0], upstream_rows), (columns[1][0], sentinel_rows), (columns[2][0], workbench_rows)]:
        y = .63
        for text, color in rows:
            ax.scatter([start + .019], [y], transform=ax.transAxes, s=32, color=COLORS[color], zorder=3)
            ax.text(start + .034, y, text, transform=ax.transAxes, fontsize=11.8,
                    color=COLORS[color], va="center", linespacing=1.35)
            y -= .09 if "\n" not in text else .115
    card(ax, (.025, .075), .95, .12, COLORS["gray_light"], COLORS["line"])
    ax.text(.045, .14, "Validated classifier accuracy: unavailable   ·   Human time savings: unmeasured",
            transform=ax.transAxes, fontsize=12.2, fontweight="bold", color=COLORS["gray"], va="center")
    ax.text(.045, .098, "Genuine ADF assembly requires additional tooling and inputs. Scientific and physical validation remain separate.",
            transform=ax.transAxes, fontsize=11, color=COLORS["gray"], va="center")
    ax.text(.025, .015, "Sentinel: October 31 recorded run · Workbench: November 3 recorded run · Newly added combined-package tests are separate.",
            transform=ax.transAxes, fontsize=10.5, color=COLORS["muted"])
    return save(figure, "delivered-results")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "figure-data.json")
    parser.add_argument("--refresh-source-root", type=Path)
    parser.add_argument("--requirements-source", type=Path, help="Requirements snapshot root; defaults to this packaged repository")
    args = parser.parse_args()
    if args.refresh_source_root:
        data = aggregate_sources(args.refresh_source_root, args.requirements_source)
        args.data.write_text(json.dumps(data, indent=2) + "\n")
    else:
        data = json.loads(args.data.read_text())
    setup()
    outputs = scope_flow(data) + action_mix(data) + delivered_results(data)
    receipt = {"matplotlib": mpl.__version__,
               "data_file": args.data.name, "data_sha256": digest(args.data),
               "builder_sha256": digest(Path(__file__)),
               "outputs": [{"file": path.name, "sha256": digest(path), "bytes": path.stat().st_size} for path in outputs],
               "screenshot": data.get("screenshot"), "palette": COLORS,
               "source_data_contains_private_ticket_text": False}
    (ROOT / "figure-manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"figures": len(outputs), "screenshot": "workbench-preview.png",
                      "data": args.data.name, "matplotlib": mpl.__version__}))


if __name__ == "__main__":
    main()
