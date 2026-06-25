"""Plot training + validation loss from a run's metrics CSV.

Lloom's CSVLogger writes train rows (with `loss/total`) and validation rows
(with `val/loss/total` and `val/perplexity/total`) interleaved into one file,
growing the header as new columns appear. This reads whichever columns are
present and renders a loss curve, optionally with validation perplexity on a
second axis.

Usage:
    python scripts/plot_loss.py runs/default/logs/metrics.csv
    python scripts/plot_loss.py runs/default/logs/metrics.csv -o docs/assets/loss_curve.png
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _series(rows, xkey, ykey):
    xs, ys = [], []
    for r in rows:
        xv, yv = r.get(xkey, ""), r.get(ykey, "")
        if xv not in (None, "") and yv not in (None, ""):
            try:
                xs.append(float(xv))
                ys.append(float(yv))
            except ValueError:
                pass
    return xs, ys


def _ema(ys, alpha):
    """Exponential moving average; tames per-micro-batch objective-mix spikes."""
    out, acc = [], None
    for y in ys:
        acc = y if acc is None else (1 - alpha) * acc + alpha * y
        out.append(acc)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="path to a run's metrics CSV")
    ap.add_argument("-o", "--out", default="docs/assets/loss_curve.png",
                    help="output image path (default: docs/assets/loss_curve.png)")
    ap.add_argument("--title", default="Pretraining loss")
    ap.add_argument("--no-ppl", action="store_true",
                    help="don't overlay validation perplexity")
    ap.add_argument("--no-smooth", action="store_true",
                    help="plot raw train loss only (no EMA trend line)")
    ap.add_argument("--alpha", type=float, default=0.08,
                    help="EMA smoothing factor for the train trend (default 0.08)")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit("plotting needs matplotlib: pip install -e \".[viz]\"")

    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"no rows in {args.csv}")

    tr_x, tr_y = _series(rows, "step", "loss/total")
    va_x, va_y = _series(rows, "step", "val/loss/total")
    pp_x, pp_y = _series(rows, "step", "val/perplexity/total")

    if not (tr_y or va_y):
        raise SystemExit("found no 'loss/total' or 'val/loss/total' columns to plot")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if tr_y:
        if not args.no_smooth and len(tr_y) > 5:
            ax.plot(tr_x, tr_y, color="#93c5fd", linewidth=0.9, alpha=0.45,
                    label="train loss (raw)")
            ax.plot(tr_x, _ema(tr_y, args.alpha), color="#2563eb", linewidth=2.0,
                    label="train loss (EMA)")
        else:
            ax.plot(tr_x, tr_y, label="train loss", color="#2563eb", linewidth=1.6, alpha=0.9)
    if va_y:
        ax.plot(va_x, va_y, label="val loss", color="#dc2626", linewidth=1.8,
                marker="o", markersize=3)
    ax.set_xlabel("step")
    ax.set_ylabel("cross-entropy loss")
    ax.set_title(args.title)
    ax.grid(True, alpha=0.25)

    if pp_y and not args.no_ppl:
        ax2 = ax.twinx()
        ax2.plot(pp_x, pp_y, label="val perplexity", color="#16a34a",
                 linewidth=1.2, linestyle="--", alpha=0.8)
        ax2.set_ylabel("val perplexity")
        lines = ax.get_lines() + ax2.get_lines()
        ax.legend(lines, [ln.get_label() for ln in lines], loc="upper right", frameon=False)
    else:
        ax.legend(loc="upper right", frameon=False)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=args.dpi, bbox_inches="tight")
    final = f", final val loss {va_y[-1]:.3f}" if va_y else ""
    print(f"wrote {out} ({len(tr_y)} train pts, {len(va_y)} val pts{final})")


if __name__ == "__main__":
    main()
