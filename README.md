# Federated Spatial Queries over Hierarchical Administrative Data

Code and data supporting:

**Privacy-Communication Trade-offs in Federated Spatial Queries over Hierarchical Administrative Data: A Query-Geometry Lower Bound and a Near-Optimal Construction** (manuscript under review at the International Journal of Geographical Information Science).

## Repository structure

- `code/` — all analysis and reproduction scripts (standard-library only, fixed seeds).
- `code/c2_exp/` — the container-latency experiment harness (Fig. 6): the measurement driver, Dockerfile, docker-compose.yml, and the local-test/measurement scripts that produce `C2_latency_measured.csv` and `C2_latency_network_model.csv`.
- `data/` — aggregated experiment outputs (risk calibration, trade-off, ablation, scalability, latency, and baseline CSVs). Raw entity-level records are **not** published (see the manuscript's ethics statement).
- `figures/` — the six manuscript figures (high-resolution TIFF, LZW).

## Reproduction

Run `code/run_experiments.py` from the repository root. All scripts use fixed seeds and standard-library dependencies only (with optional plotting/numeric libraries).

The real container-latency experiment (Fig. 6) is reproduced through the VM driver `code/_c2_vm_driver.py` together with the harness in `code/c2_exp/` (Dockerfile, docker-compose.yml, measure.py, node.py, ready.py, local_test.py); the driver uploads the container, builds it, starts it, measures the baseline, injects 10/30/80 ms one-way delays, and collects the RTT/query-latency CSVs. `code/C2_latency_profile.py` provides an in-process model of the same protocol for readers who cannot run a VM.

The administrative hierarchy (Countries-States-Cities) is cloned from the dr5hn database and recorded by commit hash. Entity-layer data (job postings and enterprise registry) are commercial listing sources obtained through authorized channels; only aggregate and DP/risk metrics are released.

## Data ethics

Raw entity records are not published because quasi-identifying attributes retained for analysis (region, industry, size bucket) could be re-identified in aggregate. Only non-identifying aggregate counts and DP/risk metrics are released.
