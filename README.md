# Bacteria-Based Wastewater Treatment

Research documentation and a working Python tool for analyzing paired wastewater measurements.

**Status:** v0.1.0 software prototype. The analyzer is tested on synthetic data; this repository does not yet contain experimental treatment results, external software validation, or measured adoption.

## Start here

| Resource | Purpose |
| --- | --- |
| [TOOL_GUIDE.md](TOOL_GUIDE.md) | Installation, data schema, calculations, outputs, and limitations |
| [analyze.py](analyze.py) | Python command-line analyzer; no third-party dependencies |
| [synthetic_measurements.csv](synthetic_measurements.csv) | Invented demonstration values; not experimental evidence |
| [measurement_template.csv](measurement_template.csv) | Blank header for your own measurements |
| [test_analyze.py](test_analyze.py) | 20 automated tests |
| [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md) | Cited narrative review and published observations |
| [literature_data.csv](literature_data.csv) | Published summary data, separate from raw measurements |

## Run the demonstration

Requires Python 3.10 or newer. Download the repository, open a terminal in its folder, and run:

```sh
python analyze.py synthetic_measurements.csv --output demo_results --label "SYNTHETIC DEMONSTRATION - NOT EXPERIMENTAL RESULTS"
```

On Windows, use `py` instead of `python` if needed. Open `demo_results/report.html` in your browser. It works offline and includes tables, removal bars, raw replicate trajectories, and calculation notes.

Expected synthetic example: treated COD mean removal **75%**, sample SD **7.071 percentage points**, and **2** defined replicate pairs. The control mean is 10%. These are verification values, not project findings. pH is plotted without a removal percentage.

To run the tests:

```sh
python -m unittest -v test_analyze.py
```

Local validation: all 20 tests passed on Python 3.12. This is not a claim of external validation.

## What the tool does

- Validates required fields, finite values, supported units and parameters.
- Pairs each replicate's latest measurement with its own time-zero baseline.
- Calculates concentration removal without clipping negative values.
- Keeps zero-baseline removal undefined and excludes pH from percentage calculations.
- Normalizes supported concentration units across replicates for summaries.
- Keeps controls and different endpoint times in separate summary groups.
- Produces paired and summary CSVs, SVG plots, an offline HTML report, and SHA-256 provenance.
- Refuses existing output paths, preserving earlier results.

It does not perform significance tests, automatically subtract controls, infer causality, or assess water safety. Details and assumptions are in [the guide](TOOL_GUIDE.md).

## Project goal

Investigate how bacteria can support treatment of domestic and municipal wastewater and make the analysis and communication of treatment measurements more reproducible.

Research questions include how measured parameters change over treatment, how treated samples compare with controls, and how consistent the observations are across independent experimental replicates.

## Measurement design

Possible measurements include COD, BOD5, suspended solids, and nitrogen/phosphorus concentrations, depending on the research design and equipment. Record analytical methods, units, sampling design, pH, temperature, and relevant reactor conditions.

The analyzer uses one row per parameter, replicate, and time point. Required columns are:

```text
experiment_id,treatment,replicate_id,time_h,parameter,value,unit
```

Use consistent analytical bases. Nutrient labels such as NH4-N and PO4-P mean concentration as N or P. Each series needs a time-zero measurement and at least one later point. Missing observations are not zero. See [TOOL_GUIDE.md](TOOL_GUIDE.md) before using experimental data.

Published summary values in `literature_data.csv` cannot be analyzed as if they were paired raw measurements. Synthetic, published-summary, and experimental data must remain separate.

## Calculations

Removal (%) = 100 × (1 − final / baseline).

Initial concentration must be positive for a defined removal percentage. Negative results indicate increased concentration and are retained. Summary percentages are means of defined replicate percentages; sample SD is reported when at least two values exist. Counts expose undefined pairs.

A concentration decrease alone does not establish degradation or mass removal. Volume changes, dilution, adsorption and sampling effects may require a mass balance. The formula does not apply to pH.

## Roadmap

- [x] Document the research goal and limitations.
- [x] Add a cited literature review and separate published-summary dataset.
- [x] Add a blank measurement template.
- [x] Implement validation, paired removal calculations and summaries.
- [x] Add synthetic data, SVG plots and an offline report.
- [x] Test calculation edge cases and the end-to-end demonstration.
- [ ] Add continuous integration and broader platform checks.
- [ ] Validate with appropriately approved experimental datasets.
- [ ] Gather feedback and document actual reuse.
- [ ] Evaluate additional analytical methods when justified by real data.

## Research integrity and limitations

Preserve raw measurements and document processing. Distinguish independent replicates from technical repeats. Report negative and inconclusive findings. Review AI-assisted code and writing against evidence. Only share data you have permission to release.

This is research software, not a validated treatment product or a claim of regulatory compliance. It does not establish pathogen removal, drinking-water safety, or discharge suitability. Biological work should follow institutionally approved procedures and supervision.

## Intended users and contribution

The intended users are students and researchers organizing microbial wastewater treatment data. No adoption, savings, or environmental benefits are claimed as measured.

Issues reporting calculation problems, unclear documentation, or reproducibility concerns are welcome. Include the expected behavior and a small nonconfidential example; label synthetic examples. Do not upload unpublished third-party data without permission.

