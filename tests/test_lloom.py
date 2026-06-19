"""Framework test: every lloom subsystem on synthetic data, zero project
dependencies (no tokenizer training, no corpus). CPU, < 1 min.
Run from repo root: python tests/test_lloom.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lloom.config import Cfg, deep_merge, load_config, parse_overrides
from lloom.data.sft import (block_causal_mask, build_batches, pack_examples,
                           train_val_split)
from lloom.finetune import (inject_lora, load_adapter, merge_lora, save_adapter)
from lloom.infer.checkpoint import export_safetensors, load_safetensors
from lloom.infer.generate import generate, sample_next
from lloom.model import ModelConfig, TransformerLM
from lloom.pipeline import run_pipeline
from lloom.quant import load_quantized, quantize_dynamic_int8, save_quantized
from lloom.train.optim import build_optimizer, zeropower_via_newtonschulz5
from lloom.train.schedules import build_schedule
from lloom.utils import set_seed

TMP = Path(tempfile.mkdtemp())
V, D, T = 128, 64, 32


def tiny_cfg(**kw) -> ModelConfig:
    base = dict(vocab_size=V, d_model=D, n_layers=2, n_heads=4,
                intermediate_size=128, max_seq_len=T, dropout=0.0)
    base.update(kw)
    return ModelConfig(**base)


def data(b=4, t=T):
    g = torch.Generator().manual_seed(0)
    x = torch.randint(0, V, (b, t + 1), generator=g)
    return x[:, :-1], x[:, 1:]


def test_config():
    merged = deep_merge({"a": {"b": 1, "c": 2}, "l": [1, 2]},
                        {"a": {"b": 9}, "l": [3]})
    assert merged == {"a": {"b": 9, "c": 2}, "l": [3]}
    ov = parse_overrides(["training.lr=3e-4", "model.tie=false", "x.y=[1,2]"])
    assert ov["training"]["lr"] == 3e-4 and ov["model"]["tie"] is False
    assert ov["x"]["y"] == [1, 2]
    base, preset = TMP / "b.yaml", TMP / "p.yaml"
    base.write_text("model: {d_model: 896, n_layers: 14}\ntraining: {lr: 6.0e-4}")
    preset.write_text("model: {d_model: 1280}")
    cfg = load_config(base, preset=preset, sets=["training.lr=1e-3"])
    assert cfg.model.d_model == 1280 and cfg.model.n_layers == 14
    assert cfg.training.lr == 1e-3
    print("ok config (merge, presets, overrides)")


def test_schedules():
    t = Cfg(schedule="cosine", max_steps=100, warmup_steps=10, min_lr_fraction=0.1)
    s = build_schedule(t)
    assert abs(s(0) - 0.1) < 1e-9 and abs(s(9) - 1.0) < 1e-9   # warmup ramp
    assert abs(s(99) - 0.1) < 5e-3                              # decayed floor
    t["schedule"] = "wsd"; t["wsd_decay_fraction"] = 0.2
    s = build_schedule(t)
    assert s(40) == 1.0 and s(79) == 1.0                        # stable phase
    assert s(99) < 0.15                                         # decayed
    t["schedule"] = "constant"
    assert build_schedule(t)(50) == 1.0
    print("ok schedules (cosine, wsd, constant)")


def test_newton_schulz():
    g = torch.randn(48, 64, generator=torch.Generator().manual_seed(1))
    sv_in = torch.linalg.svdvals(g)
    sv_out = torch.linalg.svdvals(zeropower_via_newtonschulz5(g).float())
    # quintic NS targets ~[0.7, 1.2], not exactly 1 - speed over precision
    assert sv_in.max() / sv_in.min() > 10                 # input far from orthogonal
    assert 0.55 < sv_out.min() and sv_out.max() < 1.35    # output flattened
    print("ok newton-schulz orthogonalization")


def test_optimizers():
    x, y = data()
    for name in ("adamw", "muon", "lion"):
        set_seed(0)
        model = TransformerLM(tiny_cfg())
        t = Cfg(optimizer=name, lr=1e-3, weight_decay=0.01, betas=[0.9, 0.95],
                eps=1e-8, muon_lr=0.02)
        opt = build_optimizer(model, t)
        first = None
        for _ in range(8):
            opt.zero_grad()
            _, loss = model(x, y)
            loss.backward()
            opt.step()
            first = first if first is not None else loss.item()
        assert loss.item() < first, f"{name} failed to reduce loss"
        sd = opt.state_dict()
        opt.load_state_dict(sd)                         # roundtrip
        assert all("base_lr" in g for g in opt.param_groups)
    print("ok optimizers (adamw, muon, lion reduce loss; state roundtrip)")


def test_arch_variants():
    x, y = data()
    variants = dict(
        gqa=tiny_cfg(n_kv_heads=2, qk_norm=True),
        mqa=tiny_cfg(n_kv_heads=1),
        geglu=tiny_cfg(mlp_type="geglu"),
        gelu_ln=tiny_cfg(mlp_type="gelu", norm_type="layernorm"),
        window=tiny_cfg(sliding_window=8),
        rope_linear=tiny_cfg(rope_scaling={"type": "linear", "factor": 2.0}),
        rope_ntk=tiny_cfg(rope_scaling={"type": "ntk", "factor": 2.0}),
        untied=tiny_cfg(tie_embeddings=False),
        ckpt=tiny_cfg(gradient_checkpointing=True),
        moe=tiny_cfg(n_experts=4, moe_top_k=2),
    )
    for name, cfg in variants.items():
        set_seed(0)
        model = TransformerLM(cfg)
        model.train()
        _, loss = model(x, y)
        loss.backward()
        assert torch.isfinite(loss), name
        if name == "moe":
            assert model.aux_loss is not None and model.aux_loss > 0
        if name.startswith("rope"):
            assert cfg.max_position == 2 * cfg.max_seq_len
    # sliding window with window >= T must equal full attention
    set_seed(0); full = TransformerLM(tiny_cfg())
    set_seed(0); win = TransformerLM(tiny_cfg(sliding_window=T))
    win.load_state_dict(full.state_dict())
    full.eval(); win.eval()
    lf, _ = full(x[:1]); lw, _ = win(x[:1])
    assert torch.allclose(lf, lw, atol=1e-5)
    print(f"ok arch variants ({', '.join(variants)})")


def test_kv_cache_equivalence():
    for cfg in (tiny_cfg(), tiny_cfg(n_kv_heads=2, qk_norm=True),
                tiny_cfg(sliding_window=8)):
        set_seed(0)
        model = TransformerLM(cfg).eval()
        x, _ = data(b=2, t=16)
        # incremental: feed token by token through the cache
        cache = model.new_cache(2)
        for i in range(x.shape[1]):
            inc_logits, _ = model(x[:, i:i + 1], cache=cache)
        full_logits, _ = model(x)            # targets=None -> last position
        assert torch.allclose(inc_logits, full_logits, atol=1e-4), cfg
    print("ok kv-cache == full forward (mha, gqa+qknorm, windowed)")


def test_generation():
    set_seed(0)
    model = TransformerLM(tiny_cfg()).eval()
    x = torch.randint(0, V, (1, 5))
    out = generate(model, x, 12, temperature=0.7, top_k=20, top_p=0.9,
                   min_p=0.05, repetition_penalty=1.2, seed=7)
    assert out.shape == (1, 17)
    g1 = generate(model, x, 8, seed=3)
    g2 = generate(model, x, 8, seed=3)
    assert torch.equal(g1, g2)                       # seeded determinism
    greedy = generate(model, x, 8, temperature=0.0)
    nc = generate(model, x, 8, temperature=0.0, use_cache=False)
    assert torch.equal(greedy, nc)                   # cache-free parity
    logits = torch.tensor([[10.0, 5.0, 1.0, -2.0]])
    assert sample_next(logits, temperature=0.0).item() == 0
    print("ok generation (sampling stack, determinism, greedy cache parity)")


def test_sft_packing():
    examples = [(([1] * p), ([2] * r + [9])) for p, r in
                [(5, 8), (3, 4), (10, 20), (2, 2), (7, 30), (4, 4)]]
    rows = pack_examples(examples, seq_len=24, pad_id=0)
    total_resp = sum(len(r) + 1 for _, r in examples
                     if len(_) < 0.8 * 25)           # responses incl eot
    kept_targets = sum((r["y"] != -100).sum().item() for r in rows)
    assert 0 < kept_targets <= total_resp
    for r in rows:
        live = r["y"] != -100
        assert (r["doc"][live] >= 0).all()           # no loss on padding
        m = block_causal_mask(r["doc"][None])
        assert m.shape == (1, 1, 24, 24)
        assert m[0, 0].diagonal().all()              # no empty attention rows
        d = r["doc"]
        cross = (d[None, :] != d[:, None]) & m[0, 0] # attending across docs?
        assert not cross.any()
    tr, va = train_val_split(list(range(100)), 0.1, seed=1)
    assert len(va) == 10 and len(tr) == 90
    batches = build_batches(rows, batch_size=2)
    assert all(b["x"].shape[1] == 24 for b in batches)
    print(f"ok sft packing ({len(rows)} rows, prompt/pad masked, block-diag attn)")


def test_lora():
    set_seed(0)
    model = TransformerLM(tiny_cfg())
    x, y = data(b=2)
    model.eval()
    base_logits, _ = model(x[:, :8])
    n = inject_lora(model, r=4, alpha=8, dropout=0.0)
    assert n == 2 * 7                                # 2 layers x 7 targets
    trainable = [p for p in model.parameters() if p.requires_grad]
    assert all(p.numel() for p in trainable) and len(trainable) == n * 2
    lora_logits, _ = model(x[:, :8])
    assert torch.allclose(base_logits, lora_logits, atol=1e-6)  # B=0 start
    opt = torch.optim.AdamW(trainable, lr=1e-2)
    model.train()
    for _ in range(3):
        opt.zero_grad(); _, loss = model(x, y); loss.backward(); opt.step()
    model.eval()
    tuned_logits, _ = model(x[:, :8])
    assert not torch.allclose(base_logits, tuned_logits, atol=1e-4)
    save_adapter(model, TMP / "adapter.pt", r=4, alpha=8)
    merged_logits, _ = merge_lora(model)(x[:, :8])
    assert torch.allclose(tuned_logits, merged_logits, atol=1e-5)
    set_seed(0)
    fresh = TransformerLM(tiny_cfg())
    load_adapter(fresh, TMP / "adapter.pt")
    fresh.eval()
    reload_logits, _ = fresh(x[:, :8])
    assert torch.allclose(tuned_logits, reload_logits, atol=1e-5)
    print("ok lora (zero-start, train, merge==wrapped, adapter roundtrip)")


def test_quant_and_export():
    set_seed(0)
    model = TransformerLM(tiny_cfg()).eval()
    x, _ = data(b=1, t=8)
    ref, _ = model(x)
    export_safetensors(model, TMP / "export")
    re = load_safetensors(TMP / "export")
    out, _ = re(x)
    assert torch.allclose(ref, out, atol=1e-6)       # tied head re-tied
    q = quantize_dynamic_int8(model)
    qout, _ = q(x)
    assert torch.isfinite(qout).all()
    save_quantized(q, model.cfg.__dict__, TMP / "q.pt")
    q2 = load_quantized(TMP / "q.pt")
    assert torch.allclose(qout, q2(x)[0], atol=1e-5)
    print("ok quantize (int8 roundtrip) + safetensors export/import")


def test_pipeline():
    recipe = TMP / "recipe.yaml"
    marker = TMP / "stage_ran.txt"
    recipe.write_text(f"""
name: t
stages:
  - name: a
    cmd: [-c, "open(r'{marker.as_posix()}','w').write('hi')"]
  - name: b
    cmd: [-c, "print('b')"]
    pass_overrides: true
  - name: c
    cmd: [-c, "print('c')"]
    skip_if: {marker.as_posix()}
""")
    run_pipeline(recipe, dry_run=True)
    assert not marker.exists()
    run_pipeline(recipe, preset=None, sets=["a.b=1"], until="a")
    assert marker.exists()
    run_pipeline(recipe, from_="c")                   # skip_if now triggers
    print("ok pipeline (dry-run, selection, skip_if)")


if __name__ == "__main__":
    test_config()
    test_schedules()
    test_newton_schulz()
    test_optimizers()
    test_arch_variants()
    test_kv_cache_equivalence()
    test_generation()
    test_sft_packing()
    test_lora()
    test_quant_and_export()
    test_pipeline()
    print("\nLOOM PASS")
