"""Hierarchical clustering, labelling, and outline construction for litmap.

Pure functions. No I/O. No global state. Consumed by cluster_render.py and
by the `litmap cluster` CLI command.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage

from litmap._text import last_name


def compute_hierarchy(matrix: np.ndarray) -> np.ndarray:
    """Return a scipy linkage matrix from an N×D embedding matrix.

    Uses cosine distance and average linkage — consistent with the cosine
    similarity used elsewhere in litmap, and compatible with non-Euclidean
    metrics (unlike Ward linkage).

    Shape of the returned array: (N-1, 4).
    """
    if matrix.shape[0] < 2:
        raise ValueError("compute_hierarchy requires at least 2 rows")
    return linkage(matrix, method="average", metric="cosine")


def cut_levels(
    linkage: np.ndarray,
    keys: list[str],
    matrix: np.ndarray,
    top_k: int,
    subcluster_threshold: int,
) -> list[dict]:
    """Return [{key, cluster_id, subcluster_id|None}, ...] in input order.

    Level-1 cluster ids come from fcluster(linkage, t=top_k, criterion='maxclust').
    Level-2 sub-clustering runs only on level-1 clusters with size >= threshold;
    for each such cluster we recompute linkage on the subset of rows and cut
    into max(2, round(sqrt(size / 2))) sub-clusters. Papers in smaller clusters
    have subcluster_id = None.
    """
    n = len(keys)
    if matrix.shape[0] != n:
        raise ValueError("keys and matrix must have the same length")

    level1 = fcluster(linkage, t=top_k, criterion="maxclust")

    groups: dict[int, list[int]] = defaultdict(list)
    for idx, cid in enumerate(level1):
        groups[int(cid)].append(idx)

    subcluster_by_idx: dict[int, int | None] = {i: None for i in range(n)}
    for cid, idxs in groups.items():
        size = len(idxs)
        if size < subcluster_threshold:
            continue
        sub_matrix = matrix[idxs]
        sub_linkage = compute_hierarchy(sub_matrix)
        n_sub = max(2, round((size / 2) ** 0.5))
        sub_labels = fcluster(sub_linkage, t=n_sub, criterion="maxclust")
        for local_i, idx in enumerate(idxs):
            subcluster_by_idx[idx] = int(sub_labels[local_i])

    return [
        {
            "key": keys[i],
            "cluster_id": int(level1[i]),
            "subcluster_id": subcluster_by_idx[i],
        }
        for i in range(n)
    ]


def label_clusters(
    items: list,
    assignments: list[dict],
    level: str,
    top_n_terms: int = 3,
) -> dict:
    """Return a label mapping for clusters or subclusters.

    level="cluster":    keys are int cluster_id
    level="subcluster": keys are (cluster_id, subcluster_id) tuples; only
                        papers whose subcluster_id is not None are considered,
                        and labels are computed per-parent (so sub-cluster
                        labels are distinctive within their branch).

    Uses TF-IDF with English stopwords over one document per group.
    Singleton groups fall back to the paper's first 5 title words.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    items_by_key = {i.key: i for i in items}

    if level == "cluster":
        groups: dict = defaultdict(list)
        for a in assignments:
            groups[a["cluster_id"]].append(a["key"])
        return _tfidf_labels(groups, items_by_key, top_n_terms, TfidfVectorizer)

    if level == "subcluster":
        parents: dict = defaultdict(lambda: defaultdict(list))
        for a in assignments:
            if a["subcluster_id"] is None:
                continue
            parents[a["cluster_id"]][a["subcluster_id"]].append(a["key"])
        result: dict = {}
        for parent_cid, sub_groups in parents.items():
            sub_labels = _tfidf_labels(sub_groups, items_by_key, top_n_terms, TfidfVectorizer)
            for sub_cid, lbl in sub_labels.items():
                result[(parent_cid, sub_cid)] = lbl
        return result

    raise ValueError(f"level must be 'cluster' or 'subcluster', got {level!r}")


def _tfidf_labels(
    groups: dict,
    items_by_key: dict,
    top_n: int,
    Vectoriser,
) -> dict:
    """Return {group_id: 'term1 · term2 · term3'}; singleton fallback."""
    out: dict = {}

    multi_ids = []
    multi_docs = []
    for gid, keys in groups.items():
        if len(keys) == 1:
            itm = items_by_key[keys[0]]
            first_words = " ".join((itm.title or "").split()[:5])
            out[gid] = first_words if first_words else f"cluster {gid}"
        else:
            doc = " ".join(
                f"{items_by_key[k].title} {items_by_key[k].abstract}" for k in keys
            )
            multi_ids.append(gid)
            multi_docs.append(doc)

    if multi_docs:
        vec = Vectoriser(
            stop_words="english",
            min_df=1,
            max_df=0.8,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z-]{2,}\b",
        )
        try:
            X = vec.fit_transform(multi_docs)
            vocab = vec.get_feature_names_out()
            for row, gid in enumerate(multi_ids):
                scores = X[row].toarray().ravel()
                top_idx = scores.argsort()[::-1][:top_n]
                terms = [vocab[i] for i in top_idx if scores[i] > 0]
                out[gid] = " · ".join(terms) if terms else f"cluster {gid}"
        except ValueError:
            for gid in multi_ids:
                out[gid] = f"cluster {gid}"
    return out


def build_outline(
    items: list,
    assignments: list[dict],
    cluster_labels: dict,
    subcluster_labels: dict,
    existing_subcollections: dict[str, list[str]],
    input_meta: dict,
    params: dict,
) -> dict:
    """Assemble the canonical JSON-shaped outline dict."""
    items_by_key = {i.key: i for i in items}
    assign_by_key = {a["key"]: a for a in assignments}

    by_cluster: dict = defaultdict(list)
    for a in assignments:
        by_cluster[a["cluster_id"]].append(a["key"])

    clusters_out = []
    for cid in sorted(by_cluster.keys()):
        keys_in_cluster = by_cluster[cid]
        sub_ids = {assign_by_key[k]["subcluster_id"] for k in keys_in_cluster}
        is_subclustered = sub_ids != {None}

        if is_subclustered:
            sub_groups: dict = defaultdict(list)
            for k in keys_in_cluster:
                sub_groups[assign_by_key[k]["subcluster_id"]].append(k)
            sub_out = []
            for sub_id in sorted(sub_groups.keys()):
                sub_out.append({
                    "subcluster_id": sub_id,
                    "label": subcluster_labels.get((cid, sub_id), f"subcluster {sub_id}"),
                    "size": len(sub_groups[sub_id]),
                    "papers": [_paper_dict(items_by_key[k], existing_subcollections) for k in sub_groups[sub_id]],
                })
            clusters_out.append({
                "cluster_id": cid,
                "label": cluster_labels.get(cid, f"cluster {cid}"),
                "size": len(keys_in_cluster),
                "subclusters": sub_out,
                "papers": [],
            })
        else:
            clusters_out.append({
                "cluster_id": cid,
                "label": cluster_labels.get(cid, f"cluster {cid}"),
                "size": len(keys_in_cluster),
                "subclusters": [],
                "papers": [_paper_dict(items_by_key[k], existing_subcollections) for k in keys_in_cluster],
            })

    return {
        "input": input_meta,
        "params": params,
        "clusters": clusters_out,
    }


def _paper_dict(item, existing_subcollections: dict[str, list[str]]) -> dict:
    authors = [last_name(a) for a in getattr(item, "authors", [])]
    return {
        "zotero_key": item.key,
        "title": item.title,
        "authors": authors,
        "year": getattr(item, "year", ""),
        "doi": getattr(item, "doi", ""),
        "existing_subcollections": list(existing_subcollections.get(item.key, [])),
    }
