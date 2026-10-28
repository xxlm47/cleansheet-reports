# CleanSheet Reports

Clean a CSV or Excel file into an auditable analytics bundle: cleaned data, a dashboard, a human-readable report, a transformation log, a data-quality score, and sampled PII flags.

## Features

- Normalizes column names and trims surrounding whitespace.
- Parses common currency, US/EU numeric formats, accounting negatives, and plausible dates only when at least 90% of non-null values parse.
- Logs transformations and avoids coercing mixed text columns into numbers.
- Removes exact duplicate rows and reports missingness.
- Scores completeness, uniqueness, and consistency (0–100).
- Scans a bounded sample for email, phone, SSN, payment-card-like strings, and IPv4 patterns.
- Works locally; the package does not upload input data.

## Install and run

Python 3.9+.

```bash
python -m pip install -e .
cleansheet examples/sample_dirty.csv --out cleansheet_bundle.zip
```

Development and tests:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

In Google Colab, run `cleansheet` with no input argument to open the upload widget. Colab support is optional.

## Bundle contents

- `cleansheet_cleaned.csv` — cleaned UTF-8-SIG CSV
- `cleansheet_dashboard.png` — missingness, quality, correlations/distributions
- `cleansheet_report.md` — summary and column dictionary
- `cleansheet_transformations.csv` — audit trail
- `cleansheet_quality.json` — machine-readable score
- `cleansheet_pii_flags.csv` — sampled PII pattern flags

## Limitations and safe use

PII detection is heuristic and sample-based; no flags does **not** prove that data contains no PII. The quality score is a practical indicator, not a formal standard or compliance certification. Review the transformation log and cleaned output before relying on the results. Outliers are retained. Avoid processing sensitive files on devices or services you do not control.

## Status

Beta, version 0.1.0. The API may change. See GitHub Actions for test results.

## License

MIT. See [LICENSE](LICENSE).
