"""Embedding-space clustering quality, dependency-free (torch only):
k-means (greedy k-means++ init, multi-restart), silhouette, Davies-Bouldin,
and NMI against reference labels when available.
"""
from __future__ import annotations

import math

import torch


def _kmeans_pp_init(x: torch.Tensor, k: int, gen: torch.Generator) -> torch.Tensor:
    """Greedy k-means++ (Arthur & Vassilvitskii + candidate trials a la
    scikit-learn): sample several D^2-weighted candidates per step, keep the
    one that minimizes the resulting potential. Much more robust than plain
    k-means++ single draws."""
    N = x.shape[0]
    n_trials = 2 + int(math.log(k + 1)) * 2
    centroids = x[torch.randint(N, (1,), generator=gen)].clone()
    closest = torch.cdist(x, centroids).min(1).values.pow(2)
    for _ in range(1, k):
        probs = closest / closest.sum().clamp(min=1e-12)
        cand = torch.multinomial(probs, min(n_trials, N), replacement=True,
                                 generator=gen)
        d_cand = torch.cdist(x, x[cand]).pow(2)             # (N, T)
        pot = torch.minimum(closest[:, None], d_cand).sum(0)
        j = int(pot.argmin())
        centroids = torch.cat([centroids, x[cand[j]][None].clone()])
        closest = torch.minimum(closest, d_cand[:, j])
    return centroids


def kmeans(x: torch.Tensor, k: int, n_iters: int = 100, seed: int = 0,
           n_init: int = 4):
    """x: (N, d) -> (assignments (N,), centroids (k, d)). Runs n_init
    restarts, returns the lowest-inertia solution."""
    best = None
    for trial in range(n_init):
        gen = torch.Generator().manual_seed(seed + trial)
        c = _kmeans_pp_init(x, k, gen)
        assign = torch.full((x.shape[0],), -1, dtype=torch.long)
        for _ in range(n_iters):
            new = torch.cdist(x, c).argmin(1)
            if torch.equal(new, assign):
                break
            assign = new
            for ci in range(k):
                sel = x[assign == ci]
                if len(sel):
                    c[ci] = sel.mean(0)
        inertia = (x - c[assign]).pow(2).sum().item()
        if best is None or inertia < best[0]:
            best = (inertia, assign, c)
    return best[1], best[2]


def silhouette(x: torch.Tensor, assign: torch.Tensor, max_n: int = 2000,
               seed: int = 0) -> float:
    """Mean silhouette coefficient; subsamples beyond max_n (O(n^2) distances)."""
    if x.shape[0] > max_n:
        idx = torch.randperm(x.shape[0],
                             generator=torch.Generator().manual_seed(seed))[:max_n]
        x, assign = x[idx], assign[idx]
    D = torch.cdist(x, x)
    scores = []
    for i in range(x.shape[0]):
        same = (assign == assign[i])
        same[i] = False
        if same.sum() == 0:
            continue
        a = D[i][same].mean()
        b = min(D[i][assign == c].mean() for c in assign.unique() if c != assign[i])
        scores.append(((b - a) / max(a, b)).item())
    return sum(scores) / max(len(scores), 1)


def davies_bouldin(x: torch.Tensor, assign: torch.Tensor,
                   centroids: torch.Tensor) -> float:
    k = centroids.shape[0]
    scatter = torch.stack([
        (x[assign == c] - centroids[c]).norm(dim=1).mean()
        if (assign == c).any() else torch.tensor(0.0) for c in range(k)])
    sep = torch.cdist(centroids, centroids)
    db = 0.0
    for i in range(k):
        ratios = [(scatter[i] + scatter[j]) / sep[i, j]
                  for j in range(k) if j != i and sep[i, j] > 0]
        if ratios:
            db += max(ratios).item()
    return db / k


def nmi(assign: torch.Tensor, labels: torch.Tensor) -> float:
    """Normalized mutual information between cluster assignments and labels."""
    n = len(assign)
    eps = 1e-12

    def entropy(a):
        p = torch.bincount(a).float() / n
        p = p[p > 0]
        return -(p * p.log()).sum().item()

    h_a, h_l = entropy(assign), entropy(labels)
    mi = 0.0
    for c in assign.unique():
        for l in labels.unique():
            joint = ((assign == c) & (labels == l)).sum().item() / n
            if joint > 0:
                pc = (assign == c).sum().item() / n
                pl = (labels == l).sum().item() / n
                mi += joint * math.log(joint / (pc * pl + eps) + eps)
    return mi / max(math.sqrt(h_a * h_l), eps)


def clustering_eval(emb: torch.Tensor, k: int,
                    labels: torch.Tensor | None = None, seed: int = 0) -> dict:
    assign, centroids = kmeans(emb, k, seed=seed)
    out = {"silhouette": silhouette(emb, assign, seed=seed),
           "davies_bouldin": davies_bouldin(emb, assign, centroids)}
    if labels is not None:
        out["nmi"] = nmi(assign, labels)
    return out
