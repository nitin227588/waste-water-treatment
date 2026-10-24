# Wastewater analysis tool — v0.1.0

A command-line tool for paired wastewater measurements. Requires **Python 3.10+**, with no third-party packages.

## Quick start

Keep `analyze.py` and `synthetic_measurements.csv` in the same folder:

```sh
python analyze.py synthetic_measurements.csv --output demo_results --label "SYNTHETIC DEMONSTRATION - NOT EXPERIMENTAL RESULTS"
```

On Windows, `py` can replace `python`. Open `demo_results/report.html` in your browser. The report works offline and loads no external scripts or resources. Choose a new output folder for each run; existing results are refused.

**All demonstration measurements are invented.** Treated COD removals are 80% and 70%, giving a mean of 75% and sample SD of 7.071 percentage points. Control mean removal is 10%. These values are not experimental findings or literature results.

## Input

Start with `measurement_template.csv`. One row represents one measurement:

| Column | Meaning |
| --- | --- |
| experiment_id | Experiment identifier; separate incompatible methods/conditions |
| treatment | Treatment or control label |
| replicate_id | Experimental-unit identifier, consistent across its time points |
| time_h | Time in hours; each series needs a time-zero baseline |
| parameter | COD, BOD, BOD5, TN, TP, TSS, NH4-N, NO2-N, NO3-N, PO4-P, or pH (case-sensitive) |
| value | Finite, nonnegative measurement; blanks are rejected |
| unit | mg/L, ug/L, or g/L for concentrations; pH for pH |
| data_origin | Optional origin label; the report label is supplied with --label |

Extra columns such as sample_id, method, and notes are permitted but do not affect calculations. Each series is keyed by experiment, treatment, replicate, and parameter. Use one unit throughout each series. Between replicates, supported concentration units are converted to mg/L for summaries. Paired results and raw plots retain input units.

NH4-N, NO2-N, NO3-N and PO4-P mean concentrations as N or P, not as the full ion. BOD and BOD5 are separate labels; combine only compatible analytical methods. The software cannot check whether a numerical value actually uses the declared analytical basis.

Establish a scientifically justified pairing design before using the same replicate ID across destructive samples. The tool cannot distinguish independent experimental replicates from technical repeats. Handle technical repeats separately using a documented policy.

The repository's `literature_data.csv` contains published summaries, not paired raw measurements, and is **not compatible input**. Do not transform its entries into fabricated time series.

## Calculation rules

- Final means the latest time point within each series. Earlier measurements remain visible in time-course plots.
- Removal (%) = 100 × (1 − final / baseline). Negative removal is retained.
- Zero-baseline pairs have no removal percentage; their concentrations remain in the paired output and concentration means. They are excluded from percentage means, with the denominator exposed as n_removal.
- pH has raw values and arithmetic differences but no removal percentage. Arithmetic mean pH is descriptive and is not a prediction of mixed-solution pH.
- Summary groups separate experiment, treatment, parameter, and final time. Means use equally weighted replicate percentages, not a percentage calculated from pooled concentrations.
- SD is sample standard deviation of defined replicate percentages, in percentage points. It is blank when fewer than two percentages exist.
- Controls remain separate. There is no automatic control subtraction, significance test, causal inference, or kinetic fit.
- Missing values, nonfinite numbers, negative measurements/times, unsupported parameters/units, duplicate time points, inconsistent units within a series, missing time-zero baselines, and missing follow-up measurements are rejected.
- Below-detection-limit strings such as <0.1 are rejected. Do not substitute zero without a justified preprocessing policy.

## Outputs

| File | Contents |
| --- | --- |
| paired_results.csv | Baseline/final comparison per replicate, including calculation notes |
| summary.csv | Group means, SD, n_pairs, and n_removal |
| timecourses.svg | Raw replicate trajectories, separate panel scales |
| removal.svg | Mean removal bars and counts; SD appears in the summary table |
| report.html | Offline report with inline plots and interpretation notes |
| provenance.json | Input SHA-256, filename, origin label, tool version, UTC timestamp, counts, notes |

The SHA-256 corresponds to the exact input snapshot parsed by the run. Long identifiers or many replicates may crowd plots; use CSV outputs for exact values. Labels are escaped in HTML/SVG. CSV identifiers are not formula-sanitized: when opening user-supplied data in spreadsheets, import identifier columns as text.

## Tests

Keep `test_analyze.py`, `analyze.py`, and `synthetic_measurements.csv` together:

```sh
python -m unittest -v test_analyze.py
```

The 20 tests cover percentages, sample SD, negative/undefined removal, pH, malformed data, pairing, units, endpoint separation, controls, literature-data separation, HTML escaping, valid SVG, preservation of existing output, and the complete synthetic example.

## Scope and research limits

Concentration reduction does not necessarily establish destruction or mass removal. Account for dilution, volume changes, adsorption, sampling losses and analytical uncertainty. Compare compatible wastewater compositions, conditions and methods. This version does not establish water safety, pathogen removal or regulatory compliance.

This is initial research software, tested with synthetic examples, without external validation or demonstrated adoption. See `LITERATURE_REVIEW.md` for background. Keeping code public and adding tests does not establish eligibility for any subscription program.

