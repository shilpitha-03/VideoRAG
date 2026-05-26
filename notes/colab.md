## Collaboration guidelines

---

### Working style

- **One file per edit, one commit per edit.** Don't batch multi-file changes unless I explicitly ask. Each unit of work should map cleanly to a single concise commit message.
- **Commit messages: imperative mood, concise** (e.g., "Add login page" not "Added the login page"). Always propose the commit message *before* the edit so I can sanity-check intent. Before I prompt an edit, the question I ask myself is: "what's the commit message going to be?" — if that isn't crisp, the scope is wrong.
- **Before any edit, explain in plain terms** what you'd change, where, and why. Wait for me to approve before doing it. Pure read-only exploration (reads, greps, lists, `git status`) does not need pre-approval.
- **Show diffs before applying multi-file changes.**
- **Maintain a running build log in this file.** After every commit, append a one-line entry to a `## Build log` section: date, commit subject, file(s) touched, one-line note on the decision behind it. Treat the log entry as part of the same commit as the change it describes.

### Teaching mode

- When I ask "how do I do X," **default to explaining rather than just doing** — I'm learning, not just shipping.
- When you do something non-obvious, **briefly explain why**.
- For any new dependency, library, or build step you add, **tell me what it does and why we need it**.
- Prefer concrete file paths and clickable links over abstract guidance.

### Asking vs. acting

- **When my prompt is ambiguous, ask one clarifying question** instead of guessing.
- **Never make destructive changes (deletes, force-pushes, schema migrations, irreversible config flips) without explicit approval**, even if implied by an earlier instruction.
- **Flag any structural changes before making them.**

### Working with the analysis spec

- The spec at `notes/videorag_analysis_spec.md` describes the desired outputs and where to hook in. It was written from paper reading and code review, not from running the code. **If the spec and the actual code disagree, stop and tell me before deciding which to follow.** Don't silently adapt the spec to match the code or vice versa.
- The spec specifies "where to hook" by referencing functions and files. **If you can't find the referenced location, stop and ask.** Don't invent a hook location.

### Preserving pipeline behavior

- All instrumentation must be additive. **The pipeline must produce identical outputs whether `analysis_output_dir` is set or not.** This is non-negotiable — instrumentation that changes behavior is worse than no instrumentation.
- After any change to `_op.py` or other library files, **verify behavioral equivalence** before committing. The validation step is: pick one query, run with `analysis_output_dir=None`, capture the final response; run again with `analysis_output_dir=Path("/content/test")`, capture the final response; the two responses must be identical (or near-identical accounting for any inherent non-determinism in the LLM calls — but the retrieved clip IDs and chunk IDs should be deterministic and identical).

### Notebook discipline

- The notebook is the runner; library code is the engine. **Don't put logic in the notebook that belongs in a script or module.** If a notebook cell grows beyond a few lines, factor it into `scripts/`.
- Notebook cells should be **idempotent where possible** — running a cell twice should produce the same outcome or fail loudly, not silently double-write or corrupt state.
- **Preserve existing notebook cells unless I ask you to remove them.** New cells can be added; existing cells that work should not be touched without explicit reason.

### My learning goals (apply to every interaction)

Two skills I'm actively practicing:
1. **Writing unambiguous prompts** — when my prompt could have been clearer, gently surface that.
2. **Reviewing diffs intuitively and making informed decisions** — when presenting a diff, point out what to look at and why.

---

## Build log

- 2026-05-25 — `add analysis dump helper` — `videorag/_analysis.py` — new module housing `dump_analysis(subdir, filename, data, output_dir)`. No-op when `output_dir` is None; preserves additive-only constraint. Lives in its own module so Phase 3's sampling planner and Phase 5's timing/token helpers can land alongside it.
- 2026-05-25 — `wire analysis_output_dir and sample list config` — `videorag/videorag.py` — added `analysis_output_dir: Optional[str]`, `subgraph_sample_chunk_ids: List[str]`, `merge_trace_entity_names: List[str]` to the `VideoRAG` dataclass. Threading is implicit: `asdict(self)` already flows to every callsite that needs `global_config`. Sample lists default empty so they're inert until Phase 3 populates them.
- 2026-05-25 — `add sampling planners and path sanitizer` — `videorag/_analysis.py` — added `plan_chunk_samples` (even-spread positional, 10 chunks), `plan_entity_samples` (extraction-count + type-variance + predicted-synthesis proxies, 30 entities) and `sanitize_for_path`. Planners run only when user-supplied sample lists are empty; spec heuristics that required post-extraction stats were substituted with pre-extraction proxies (documented in docstrings).
- 2026-05-25 — `instrument extraction with sub-graph and merge hooks` — `videorag/_op.py` — added analysis hooks inside `extract_entities._process_single_content` (raw LLM trace, parsed sub-graph, chunk corpus info per sampled chunk) and `_merge_nodes_then_upsert` (merge_group, resolution, corpus_trace per sampled entity, signature gained keyword-only `sample_set`/`dump_dir`). Two refactors used by both pipeline and instrumentation: `type_counter` is named so `vote_counts` reuses it; `description_pre_synthesis` snapshots the joined string before the summary call. All new code paths gated on `analysis_dir is not None` or sample-set membership — pipeline behavior unchanged when analysis is off.
- 2026-05-25 — `add offline indexing analysis extraction script` — `scripts/extract_indexing_analysis.py` — pure post-processing: reads `kv_store_*.json` + `graph_chunk_entity_relation.graphml`, emits the 8 spec 1.1-1.7+1.10 JSON files. CLI takes `--workdir`, `--output-dir`, `--config-name` (deepseek_bge_config / openai_config baked into `KNOWN_CONFIGS`). `indexed_at` uses graphml mtime as proxy. `chunks_with_parsing_failures` set to null with a `_notes` field explaining why (not captured in post-index storage; available per-sampled-chunk in subgraph_samples/). No model calls.
- 2026-05-25 — `add QueryRecorder and query-side helpers` — `videorag/_analysis.py` — added `QueryRecorder` (per-query instrumentation collector with `stage()` context manager for timing, `dump()` for JSON, `finalize_timing()` for timing.json), `fmt_timestamp` and `split_caption_transcript` helpers. Recorder is unconditionally constructed by `videorag_query`; every method short-circuits when `output_dir` or `query_id` is `None`, so callers don't need to guard.
- 2026-05-25 — `add query_id and query_metadata to QueryParam` — `videorag/base.py` — two optional fields default to `None`. Existing callers and the notebook are unaffected; `videorag_query` reads them only when constructing the `QueryRecorder`. Pre-existing quirks in the dataclass (`only_need_context` declared twice, `naive_max_token_for_text_unit` lacking a type annotation) left untouched.
- 2026-05-25 — `instrument videorag_query with retrieval hooks` — `videorag/_op.py` — 10 `rec.stage(...)` timings and 8 `rec.dump(...)` calls cover spec 2.1-2.9. Top-K+5 trick on paths 1 and 3 only fires when `rec.enabled` so retrieval behavior is identical when analysis is off; path 2 emits `clips_below_cutoff=[]` (VDB has `better_than_threshold=-1`). `_find_most_related_segments_from_entities` now returns `(set, trace_dict)`; `videorag_query_multiple_choice` unpacks and discards the trace. Token counts are estimated locally via tiktoken (labeled `estimated_input_tokens` / `estimated_output_tokens`). `videorag_query_multiple_choice` is otherwise uninstrumented — to be mirrored if MCQ-mode runs need analysis.
- 2026-05-25 — `wire notebook to local index and eval-set analysis loop` — `videorag_run.ipynb` — 5 new cells + 1 modified cell, total 57 → 62. Modified the indexing cell to pass `analysis_output_dir=analysis_dir` so Phase 3 hooks fire. New cells: paths setup (workdir + analysis_dir on `/content/`), post-index extraction-script run, eval-set loader (defaults to `/content/VideoRAG/notes/eval_set.json`), eval query loop (passes `query_id` + `query_metadata` for each eval row), zip-for-download. Inspection cells 42-49 left untouched per the preserve-existing-cells rule; they read from `drive_paths['workdir']` and may show empty/missing data since the index now lives on `/content/`.
