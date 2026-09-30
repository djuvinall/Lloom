# Lloom for HollowDeck

`hollowdeck/lloom/` is a [HollowDeck](https://github.com/djuvinall/Orchestrator)
module: it puts Lloom's training, finetuning, evaluation and judging on HollowDeck's
tool broker, so the Orchestrator's graphs — and any other module — can drive Lloom
runs, wait on them, read what they produced, and act on it.

It is built to HollowDeck's interop contract (`INTEROP.md` in the HollowDeck
checkout): a `kind: process` Python module with a guarded loopback server, tools
declared in `module.json`, one extra node per pipeline recipe declared through a
`tools_file`, the workspace's resources published as Asset Library assets, a
lifecycle hook that keeps it alive while training runs, and a panel built on the
vendored UI kit.

**Lloom calls no model provider.** Which model judges your outputs, and where it runs,
is HollowDeck's to decide (see [Judging](#judging-with-hollowdecks-models)).

## Install

### From the bundle (what you want day to day)

```bash
hollowdeck modules pack hollowdeck/lloom -o hollowdeck/dist/lloom.hmod   # prints the sha256
hollowdeck modules install hollowdeck/dist/lloom.hmod --checksum <that sha256>
hollowdeck modules verify lloom
```

or **Modules → Install** in the HollowDeck window. The bundle is deterministic: packing
the same tree twice gives the same bytes, so the sha256 identifies the version.

**To update**, bump `version` in `module.json`, pack to the **same path**, and update:
`hollowdeck modules update lloom` or `POST /api/modules/lloom/update` on a running core —
both re-install from the path recorded at install, which is why the bundle keeps one
name. Settings and module data survive an update (and an uninstall).

An installed copy lives in `hollowdeck_data/modules/lloom`, away from this checkout, so
**set its `workspace`** (below) — it cannot find Lloom by walking up from itself.

### In place (while developing the module)

Add this repository's `hollowdeck` folder as a scan root (Modules → *Where the core
looks*, or `hollowdeck_data/scan_roots.json`: `{"roots": ["F:\\...\\Lloom\\hollowdeck"]}`)
and reload. The module then finds this checkout by itself, and edits take effect on
the next module reload. Do not use both at once: the same id in two roots is a
`conflict`.

## Settings

Set them in the module manager's details panel (or
`hollowdeck_data/module_settings/lloom.json`); they apply the next time the module
starts (Reload).

| Setting | Meaning | Default |
|---|---|---|
| `workspace` | The Lloom project to drive: the folder holding `scripts/` and `config/` | this checkout, when the module is found in place |
| `python` | The interpreter every job runs under. It needs torch and Lloom's requirements; HollowDeck's own interpreter usually has neither | `LLOOM_PYTHON`, then a `.venv` in the workspace, then the module's own |
| `max_concurrent_jobs` | Training jobs that may run at once (one GPU: 1). Generation never waits behind training | `1` |
| `allow_replace_data` | Lets **Add Lloom SFT Data** overwrite a dataset instead of appending | `false` |
| `report_jobs` | Tell the status bar when a pipeline or stage ends | `true` |
| `keep_jobs` | Finished jobs kept in the panel | `100` |

Press **Check interpreter** in the panel after setting `python`: it reports torch,
CUDA and whether `lloom` imports. For GPU training point `python` at an environment
with a CUDA build of torch (Blackwell needs CUDA 12.8+).

## What it offers

**Nodes** (`lloom/<id>` in the Orchestrator's palette):

| Node | Effects | Does |
|---|---|---|
| Lloom Status | reads | the workspace, interpreter, recipes, presets, stages, runs |
| Run Lloom Pipeline | executes | starts a recipe (`config/pipelines/*.yaml`) as a background job |
| Lloom: *recipe* pipeline | executes | one node per recipe, with the workspace's presets and stages as dropdowns |
| Run Lloom Stage | executes | starts one `scripts/<stage>.py` as a background job |
| Lloom Job Status | reads | a job's status, stage, progress and log tail; can wait up to 280 s |
| Cancel Lloom Job | executes | stops a job and its whole process tree |
| List Lloom Runs / Lloom Run Metrics | reads | runs, checkpoints, losses, perplexity, eval and judge results, eval generations |
| Lloom Generate | executes | completions from a run's checkpoint (`scripts/generate.py`), locally |
| Lloom Judge Request | none | the grading request: instructions, numbered prompt, JSON schema |
| Lloom Judge Scores | writes | reads the grader's answer back; can save it into the run |
| Add Lloom SFT Data | writes | appends `{prompt, response}` pairs to `data/sft/` or `data/test/` |
| Sync Lloom Library | writes | republishes the workspace to the Asset Library |

Every node declares `effects` honestly, so in an **unattended** run (a schedule,
`hollowdeck run`) each needs its *Allow in unattended runs* box ticked — the examples
tick theirs.

**Library assets** (kind → what an Asset node emits): `lloom.recipe` → a recipe name,
`lloom.preset` → a preset name, `script` → a stage name, `lloom.run` → a run name,
`lloom.checkpoint` → a workspace-relative checkpoint path. All `origin: ingested`,
re-derived at start, after every job and on **Sync library**; assets you save yourself
are never touched.

## Long jobs

A node may wait about five minutes; training takes longer. So pipelines and stages
start as **jobs** and answer at once with a `job_id`. Wait on one with a Repeat zone
around **Lloom Job Status** (`wait_seconds: 240`, cap 30 = two hours): each pass waits
up to four minutes and returns immediately once the job has ended. Or set **Then run
graph** (`on_complete_graph`): when the job *succeeds*, the core runs that saved graph,
unattended.

While a job is queued or running the module holds itself alive (`GET /lifecycle`), and
its processes are tied to it: stopping or disabling the module stops them. A job left
running by a stopped module is marked `interrupted`; a pretrain run resumes from its
`last.pt` when started again under the same run name.

## Judging with HollowDeck's models

Lloom writes the request and reads the answer; HollowDeck makes the call:

```
Lloom Generate ──results──▶ Lloom Judge Request ──instructions, prompt, schema──▶ Structured ◀── Model
                                     │                                                │
                                     └───────────items──────▶ Lloom Judge Scores ◀──data──┘
```

The **Model** node (`model/config`) names the grader, e.g. `ollama:qwen3.5:9b`.
**Structured** (`model/structured`) asks it for JSON matching the schema. **Judge
Scores** matches verdicts to items, averages, and — given a run name — saves
`runs/<run>/eval/judge_results.json` and `judgements.jsonl`, which Run Metrics and the
Library then show. Swap the grader by changing only the Model node; when HollowDeck
gains another provider, judging uses it with no change here.

**Point HollowDeck at your Ollama server** once, in the environment HollowDeck starts
from, then restart HollowDeck:

```powershell
setx HDECK_OLLAMA_URL http://10.0.0.215:11434
```

(`10.0.0.215:11434` is the Ollama server on the llab network with the chat models;
`10.0.0.50:11434` is LLMemory's embeddings-only one.) The Model node's picker then
lists that server's models.

For judging from the command line instead, `scripts/judge.py` (configured in
`config/judge_config.yaml`) is Lloom's own CLI judge; it is a workspace script, and the
module runs it only when a graph asks for the `judge` stage.

## Example graphs

`hollowdeck/lloom/examples/` — drop a file on the HollowDeck window to open it in the
editor, then **Save** it (saved graphs live in `hollowdeck_data/graphs/` wrapped in the
editor's own envelope, so copy them in through the editor, not by hand). From a script,
`PUT /m/graph_editor/api/graphs/<slug>` with the file's contents saves it the same way:

- **lloom_train_and_judge** — run the `smoke` recipe (nano, CPU, about a minute),
  wait, sample the model, have a Model node grade the samples, save the score into the
  run, and report.
- **lloom_sft_and_judge** — LoRA-finetune that run with `smoke_sft` (the
  `pipeline_smoke_sft` node), wait, ask it instructions in chat mode, grade the answers,
  and report.
- **lloom_judge_latest** — grade the newest run's evaluation generations (every recipe
  ends by evaluating) and save the score into the run.

Each runs as it is, one after another, in about a minute on a CPU, graded by
`ollama:qwen3.5:9b` — change the Model node to grade with anything else.

> **Test with the `smoke` recipes, not `pretrain`.** `smoke` and `smoke_sft` keep every
> artifact under `runs/`: the tokenizer and token streams in `runs/_smoke/`, the model in
> `runs/<run_name>/`. The `pretrain` recipe writes the shared `data/processed/` and
> `checkpoints/tokenizer/` from whatever is in `data/raw/`, and **skips** those stages
> whenever they exist — so a toy run of `pretrain` on the 16-document sample would leave a
> tokenizer your first real training run silently reuses. If that has happened, delete
> both folders before training on a real corpus.

## When something is wrong

- **The panel** shows the workspace, the interpreter check, every job with its full
  log, runs and the Library.
- **The module's own log** is `hollowdeck_data/module_data/lloom/process.log`; job logs
  are under `module_data/lloom/jobs/<id>/output.log`.
- A node that fails says why in one line: a readable refusal (`no recipe "x" (have:
  pretrain, sft, release)`) or the last line the script printed.

## Development

- Tests: `pytest tests/test_hollowdeck_module.py` — the contract (guard, routes,
  relative URLs, UI-kit rules, vendored bytes) and the behaviour against a fake
  workspace that runs the real `run_pipeline.py`. `HDECK_CHECKOUT=<HollowDeck checkout>`
  also compares the vendored files with upstream.
- **Vendored files** (`VENDORED.json`) are HollowDeck's, copied byte for byte: never edit
  them; re-copy from the HollowDeck checkout and update the hashes.
- Bump `version` in `module.json` for every change you install, then pack to
  `hollowdeck/dist/lloom.hmod` and update (above). Installing over an installed module is
  refused; updating is the verb.
