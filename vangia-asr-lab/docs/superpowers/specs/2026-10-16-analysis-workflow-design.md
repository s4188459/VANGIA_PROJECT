# ZIP benchmark and analysis export

The user's supplied implementation request is the accepted design brief. Extend the existing
Tk application, not a separate web app. Users need to supply a ZIP, check pairing, choose local
model presets, run sequential jobs, then export data that remains meaningful in Excel/Python.

Three components keep existing evidence intact: `zip_dataset` validates and stages a dataset;
`benchmark` creates an immutable multi-model/repeat plan and delegates jobs to the existing
runner; `analysis_export` reads audited results and produces a versioned analysis bundle.
`benchmark_ui` provides the wizard and result table. Existing seven views remain available.

ZIP paths are never extracted as executable paths. Validate names/limits first, decode only
approved audio extensions, reject containers with video, preserve originals with hashes.
Pair by relative stem or explicit metadata; unknown grouping remains one unknown cluster.
Rows with unresolved input errors block execution and remain in planned/exported counts.
An empty reference requires explicit silence confirmation. No consent is inferred.

Each repeat creates a fresh model worker and is labeled cold_model_load; OS cache state is
uncontrolled. Do not call later repeats warm. A true warm run needs persistent-worker support
and is explicitly unavailable in this workflow. Never mix modes/repeats in score aggregation.

Exports contain numeric UTF-8-BOM CSV, transcript/alignment JSONL, structured JSON metric
envelopes, data dictionary, failures, report and hashes. All planned rows survive failures
or cancellation. Aggregates distinguish completed-scored subsets from full-corpus metrics.
No physical presentation or word latency is invented. Original evidence stays sealed.

The user explicitly requests implementation and tests now, so the already supplied design
and plan authorize proceeding without a repeated design-approval round. Changes stay only
inside vangia-asr-lab; unrelated dirty files and existing historical runs remain untouched.
