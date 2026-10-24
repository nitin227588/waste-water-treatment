"""Paired wastewater analysis. Python 3.10+, standard library only."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile

VERSION = "0.1.0"
REQUIRED = {"experiment_id", "treatment", "replicate_id", "time_h", "parameter", "value", "unit"}
PARAMETERS = {"COD", "BOD", "BOD5", "TN", "TP", "TSS", "NH4-N", "NO2-N", "NO3-N", "PO4-P", "pH"}
UNITS = {"mg/L": 1.0, "ug/L": 0.001, "g/L": 1000.0}
PAIR_FIELDS = ["experiment_id", "treatment", "replicate_id", "parameter", "unit", "final_time_h", "baseline", "final", "change", "removal_percent", "note"]
SUMMARY_FIELDS = ["experiment_id", "treatment", "parameter", "unit", "final_time_h", "n_pairs", "n_removal", "mean_baseline", "mean_final", "mean_removal_percent", "sd_removal_percent"]


class DataError(ValueError):
    """Input cannot be interpreted without guessing."""


def number(text, label):
    try:
        value = float(text)
    except (ValueError, TypeError):
        raise DataError(f"{label}: expected a number, got {text!r}") from None
    if not math.isfinite(value):
        raise DataError(f"{label}: value must be finite")
    return value


def read_measurements(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise DataError("Duplicate CSV column names")
        missing = REQUIRED - set(headers)
        if missing:
            raise DataError("Missing columns: " + ", ".join(sorted(missing)))
        records, seen, group_units = [], set(), {}
        for row in reader:
            line = reader.line_num
            if None in row:
                raise DataError(f"Row {line}: too many fields")
            if all(v is None or not v.strip() for v in row.values()):
                continue
            clean = {k: (v or "").strip() for k, v in row.items()}
            for field in REQUIRED:
                if not clean[field]:
                    raise DataError(f"Row {line}: missing {field}; missing values are not zero")
            parameter, unit = clean["parameter"], clean["unit"]
            if parameter not in PARAMETERS:
                raise DataError(f"Row {line}: unsupported parameter {parameter!r}")
            if (parameter == "pH" and unit != "pH") or (parameter != "pH" and unit not in UNITS):
                raise DataError(f"Row {line}: use mg/L, ug/L, g/L for concentrations; pH for pH")
            time = number(clean["time_h"], f"Row {line} time_h")
            value = number(clean["value"], f"Row {line} value")
            if time < 0 or value < 0 or (parameter == "pH" and value > 14):
                raise DataError(f"Row {line}: nonnegative time/value required; supported pH range is 0-14")
            group = tuple(clean[k] for k in PAIR_FIELDS[:4])
            if group in group_units and group_units[group] != unit:
                raise DataError(f"Row {line}: mixed units within replicate/parameter")
            group_units[group] = unit
            if group + (time,) in seen:
                raise DataError(f"Row {line}: duplicate time point for {group}")
            seen.add(group + (time,))
            records.append(dict(clean, time_h=time, value=value))
    if not records:
        raise DataError("CSV contains no measurements")
    return records


def analyze(records):
    groups = {}
    for row in records:
        key = tuple(row[k] for k in PAIR_FIELDS[:5])
        groups.setdefault(key, []).append(row)
    paired, warnings = [], []
    for key, rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: r["time_h"])
        if len(rows) < 2 or rows[0]["time_h"] != 0 or rows[-1]["time_h"] <= 0:
            raise DataError(f"{key}: requires time-zero baseline and a later measurement")
        baseline, final = rows[0]["value"], rows[-1]["value"]
        removal, note = None, ""
        if key[3] == "pH":
            note = "pH is logarithmic; no removal percentage"
        elif baseline == 0:
            note = "Zero baseline; removal percentage undefined"
        else:
            removal = 100 * (1 - final / baseline)
            if not math.isfinite(removal):
                raise DataError(f"{key}: removal overflow")
            if removal < 0:
                note = "Concentration increased; negative removal retained"
        if note:
            warnings.append(f"{' / '.join(key)}: {note}")
        paired.append(dict(zip(PAIR_FIELDS[:5], key)) | {
            "final_time_h": rows[-1]["time_h"], "baseline": baseline,
            "final": final, "change": final - baseline, "removal_percent": removal, "note": note})
    groups = {}
    for pair in paired:
        unit = "pH" if pair["parameter"] == "pH" else "mg/L"
        key = tuple(pair[k] for k in SUMMARY_FIELDS[:3]) + (unit, pair["final_time_h"])
        groups.setdefault(key, []).append(pair)
    summaries = []
    for key, pairs in sorted(groups.items()):
        removals = [p["removal_percent"] for p in pairs if p["removal_percent"] is not None]
        factor = lambda p: 1 if p["unit"] == "pH" else UNITS[p["unit"]]
        row = dict(zip(SUMMARY_FIELDS[:5], key)) | {
            "n_pairs": len(pairs), "n_removal": len(removals),
            "mean_baseline": statistics.mean(p["baseline"] * factor(p) for p in pairs),
            "mean_final": statistics.mean(p["final"] * factor(p) for p in pairs),
            "mean_removal_percent": statistics.mean(removals) if removals else None,
            "sd_removal_percent": statistics.stdev(removals) if len(removals) > 1 else None}
        if any(v is not None and not math.isfinite(v) for k, v in row.items() if k.startswith(("mean_", "sd_"))):
            raise DataError(f"{key}: summary overflow")
        summaries.append(row)
    return paired, summaries, warnings


def fmt(value):
    return "" if value is None else f"{value:.8g}" if isinstance(value, float) else str(value)


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: fmt(r.get(k)) for k in fields} for r in rows)


def svg(width, height, title, body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(title, quote=True)}" viewBox="0 0 {width} {height}" style="font:13px system-ui,sans-serif;background:white">' + "".join(body) + "</svg>"


def timecourses(records):
    groups = {}
    for row in records:
        key = tuple(row[k] for k in ("experiment_id", "treatment", "parameter", "unit"))
        groups.setdefault(key, []).append(row)
    body, colors = [], ["#176b87", "#b64d23", "#6b4ba1", "#32824e", "#9c365d", "#665d1e"]
    for index, (key, rows) in enumerate(sorted(groups.items())):
        top = index * 260
        x0, x1, y0, y1 = 95, 710, top + 55, top + 205
        maxt = max(r["time_h"] for r in rows)
        maxv = max(r["value"] for r in rows) or 1
        scale = lambda r: (x0 + r["time_h"] / maxt * (x1 - x0), y1 - r["value"] / maxv * (y1 - y0))
        body.append(f'<text x="20" y="{top+25}" font-weight="bold">{html.escape(" / ".join(key))}</text>')
        body.append(f'<path d="M{x0},{y0} V{y1} H{x1}" fill="none" stroke="#657383"/>')
        for tick in range(5):
            y, x = y1 - tick * (y1 - y0) / 4, x0 + tick * (x1 - x0) / 4
            body.append(f'<text x="85" y="{y+4}" text-anchor="end">{maxv*(tick/4):.4g}</text>')
            body.append(f'<text x="{x}" y="{y1+20}" text-anchor="middle">{maxt*(tick/4):.4g}</text>')
        body.append(f'<text x="400" y="{top+248}">Time (h)</text>')
        replicates = sorted({r["replicate_id"] for r in rows})
        for ri, replicate in enumerate(replicates):
            series = sorted((r for r in rows if r["replicate_id"] == replicate), key=lambda r: r["time_h"])
            color = colors[ri % len(colors)]
            points = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(scale, series))
            body.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
            for row in series:
                x, y = scale(row)
                title = html.escape(f"Replicate {replicate}; {row['time_h']} h; {row['value']} {key[3]}")
                body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"><title>{title}</title></circle>')
            if ri < 8:
                body.append(f'<text x="740" y="{top+60+ri*20}" fill="{color}">Replicate {html.escape(replicate)}</text>')
        if len(replicates) > 8:
            body.append(f'<text x="740" y="{top+225}">More series: inspect CSV</text>')
    return svg(960, len(groups) * 260, "Raw measurement time courses", body)


def removal_chart(summaries):
    rows = [r for r in summaries if r["mean_removal_percent"] is not None]
    if not rows:
        return svg(960, 100, "Removal summary", ['<text x="20" y="50">No defined removal percentages.</text>'])
    values = [r["mean_removal_percent"] for r in rows]
    low, high = min(0, min(values)), max(100, max(values))
    divisor = max(abs(low), abs(high), 1)
    lo, hi = low / divisor, high / divisor
    xpos = lambda value: 420 + (value / divisor - lo) / (hi - lo) * 380
    body = ['<text x="20" y="24" font-weight="bold">Mean paired removal (%) - no control subtraction</text>']
    for tick in range(5):
        body.append(f'<text x="{420+380*tick/4}" y="48" text-anchor="middle">{(lo+(hi-lo)*tick/4)*divisor:.4g}</text>')
    for i, row in enumerate(rows):
        y = 70 + 48 * i
        label = f"{row['experiment_id']} / {row['treatment']} / {row['parameter']} / {row['final_time_h']:g} h"
        body.append(f'<text x="15" y="{y+13}">{html.escape(label)}</text>')
        zero, end = xpos(0), xpos(row["mean_removal_percent"])
        color = "#b64d23" if row["mean_removal_percent"] < 0 else "#176b87"
        body.append(f'<rect x="{min(zero,end):.2f}" y="{y}" width="{max(abs(end-zero),0.5):.2f}" height="20" fill="{color}"/>')
        body.append(f'<text x="820" y="{y+14}">{row["mean_removal_percent"]:.3g}% (n={row["n_removal"]})</text>')
    return svg(1080, 95 + 48 * len(rows), "Mean paired removal", body)


def report(summaries, warnings, plots, filename, digest, label):
    fields = ["experiment_id", "treatment", "parameter", "final_time_h", "n_pairs", "n_removal", "mean_removal_percent", "sd_removal_percent"]
    headings = "".join(f"<th>{k}</th>" for k in fields)
    table = "".join("<tr>" + "".join(f"<td>{html.escape(fmt(r.get(k)))}</td>" for k in fields) + "</tr>" for r in summaries)
    notes = "".join(f"<li>{html.escape(w)}</li>" for w in warnings) or "<li>No calculation exceptions.</li>"
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wastewater analysis</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#183346;max-width:1100px;margin:36px auto;padding:0 22px}}h1,h2{{line-height:1.2}}.label{{background:#e6f2f5;padding:16px;border-left:5px solid #176b87}}table{{border-collapse:collapse;font-size:13px}}th,td{{padding:9px;border:1px solid #cbd6dc;text-align:left}}.scroll{{overflow:auto}}svg{{width:100%;min-width:720px}}code{{overflow-wrap:anywhere}}</style>
<h1>Wastewater measurement analysis</h1><p class="label"><strong>Data label: {html.escape(label)}</strong></p>
<p>Input: {html.escape(filename)} / Tool {VERSION}<br>SHA-256: <code>{digest}</code></p>
<p>Removal = 100 x (1 - final / baseline). Each replicate is paired to its time-zero baseline. Summaries separate final times and average defined replicate percentages. SD is sample standard deviation; blank SD means fewer than two defined percentages. n_pairs counts all pairs; n_removal counts defined percentages.</p>
<h2>Paired-removal summary</h2><div class="scroll"><table><thead><tr>{headings}</tr></thead><tbody>{table}</tbody></table></div>
<h2>Removal plot</h2><div class="scroll">{plots[1]}</div><p>Bars show means without error bars; SD is in the table. Controls remain separate and are not subtracted.</p>
<h2>Raw time courses</h2><div class="scroll">{plots[0]}</div><p>Each line is one replicate. Panels have separate vertical scales and retain input units; do not compare heights across panels.</p>
<h2>Calculation notes</h2><ul>{notes}</ul><p>Concentration changes alone do not establish destruction, mass removal, disinfection, discharge compliance or treatment causality. This tool does not handle detection limits or significance testing. Keep synthetic, literature-summary and experimental datasets separate.</p></html>'''


def run(input_path, output_path, label):
    input_path, output_path = Path(input_path), Path(output_path)
    if not label.strip():
        raise DataError("A nonempty data-origin label is required")
    if output_path.exists():
        raise DataError(f"Output already exists: {output_path}; choose a new directory")
    raw = input_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp) / "input.csv"
        snapshot.write_bytes(raw)
        records = read_measurements(snapshot)
    paired, summaries, warnings = analyze(records)
    plots = timecourses(records), removal_chart(summaries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_path.parent) as temp:
        stage = Path(temp) / "result"
        stage.mkdir()
        write_csv(stage / "paired_results.csv", paired, PAIR_FIELDS)
        write_csv(stage / "summary.csv", summaries, SUMMARY_FIELDS)
        (stage / "timecourses.svg").write_text(plots[0], encoding="utf-8")
        (stage / "removal.svg").write_text(plots[1], encoding="utf-8")
        (stage / "report.html").write_text(report(summaries, warnings, plots, input_path.name, digest, label), encoding="utf-8")
        meta = {"tool_version": VERSION, "created_utc": datetime.now(timezone.utc).isoformat(), "input_filename": input_path.name,
                "input_sha256": digest, "data_label": label, "measurement_count": len(records), "pair_count": len(paired), "warnings": warnings}
        (stage / "provenance.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if output_path.exists():
            raise DataError(f"Output was created by another process: {output_path}")
        os.rename(stage, output_path)
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Long-format measurement CSV")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--label", required=True, help="Data origin, e.g. SYNTHETIC DEMONSTRATION")
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args(argv)
    try:
        meta = run(args.input, args.output, args.label)
    except (DataError, OSError, UnicodeError, csv.Error, OverflowError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(f"Saved {meta['pair_count']} paired results to {args.output}")
    for warning in meta["warnings"]:
        print(f"Note: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

