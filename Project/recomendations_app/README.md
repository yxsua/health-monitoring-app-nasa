# Legacy maintenance-rule prototype

This misspelled, legacy directory is separate from [`Project/recommendations_app`](../recommendations_app/README.md), which is the recommendation library used by the chatbot. It is not included in Docker Compose and is not called by any deployed service.

## Contents and intended use

- `mantenimiento.py` contains an experimental Spanish-language evaluator for body and cabin rules, corrective guidance, and projected-threshold guidance. It accepts a dictionary of measurement names such as `fc (lpm)`, `spo2 (%)`, and `co2 (ppm)` and returns grouped body/cabin levels and actions.
- `test_mantenimiento.py` contains unit examples for that standalone evaluator.
- `Agregar un título.jpg` and `Agregar un título.png` are reference images, not runtime assets.

The module uses Python's standard library. It can optionally read threshold rows from an Excel workbook when `openpyxl` is installed and a compatible workbook path is supplied. Otherwise it falls back to thresholds embedded in the module. No workbook or deployment configuration is bundled here.

## Run its standalone examples

From this folder:

```sh
python mantenimiento.py
python -m unittest -v test_mantenimiento
```

The test module contains an optional workbook test tied to an example upload path; that case is skipped when the file is absent. Run this code only for prototype evaluation. Thresholds and guidance were assembled for a demonstration and have not been integrated or clinically validated. Do not use these outputs to make real health or flight-safety decisions.
