"""Fine-tune a contrastive candidate using only human-selected training triplets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contrastive_evaluation import attach_multi_positive_labels
from contrastive_label_packet import validate_completed_packet


def build_triplets(packets: list[dict]) -> list[tuple[str, str, str]]:
    """Return query/positive/hard-negative triplets from completed human labels."""
    triplets = []
    for packet in packets:
        validate_completed_packet(packet)
        evidence = {item["evidence_id"]: item["text"] for item in packet["evidence_chunks"]}
        for claim in packet["claims"]:
            if claim["support_status"] == "supported" and claim.get("hard_negative_evidence_id"):
                positives = claim.get("supporting_evidence_ids") or [claim["supporting_evidence_id"]]
                triplets.extend((claim["text"], evidence[positive], evidence[claim["hard_negative_evidence_id"]]) for positive in positives)
    if not triplets:
        raise ValueError("no supported human hard-negative triplets are available")
    return triplets


def finetune_triplets(triplets: list[tuple[str, str, str]], model_name: str, output_dir: Path, epochs: int = 1, batch_size: int = 8) -> dict:
    """Train a candidate without touching the active model or its manifest."""
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError("sentence-transformers and torch are required for contrastive fine-tuning") from error
    model = SentenceTransformer(model_name)
    # Keep the training loop local to avoid requiring the optional ``datasets``
    # package used by SentenceTransformer.fit in v5.  All inputs retain E5's
    # query/passage prefixes and the loss is cosine triplet margin loss.
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
    model.train()
    batches = [triplets[index:index + batch_size] for index in range(0, len(triplets), batch_size)]
    for _ in range(epochs):
        for batch in batches:
            queries, positives, negatives = zip(*batch)
            def embeddings(texts: tuple[str, ...]):
                features = model.tokenize(list(texts))
                return torch.nn.functional.normalize(model(features)["sentence_embedding"], p=2, dim=1)
            query_vectors = embeddings(tuple(f"query: {text}" for text in queries))
            positive_vectors = embeddings(tuple(f"passage: {text}" for text in positives))
            negative_vectors = embeddings(tuple(f"passage: {text}" for text in negatives))
            loss = torch.relu(0.2 - (query_vectors * positive_vectors).sum(dim=1) + (query_vectors * negative_vectors).sum(dim=1)).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(output_dir))
    manifest = {"candidate_type": "human_hard_negative_triplet_finetune", "base_model": model_name, "triplets": len(triplets), "epochs": epochs, "batch_size": batch_size, "training_split": "case_split_v1.train_only", "status": "candidate_not_promoted"}
    (output_dir / "training_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune a contrastive candidate on only train-split human hard negatives.")
    parser.add_argument("--packet-dir", type=Path, default=Path("data/61_contrastive_diagnostic/label_packets"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/case_split_v1.json"))
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--output-dir", type=Path, default=Path("models/candidates/contrastive_e5_hard_negative_v1"))
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--multi-positive-dir", type=Path)
    args = parser.parse_args()
    split = json.loads(args.split.read_text(encoding="utf-8"))
    train_ids = set(split["assignments"]["train"])
    packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.packet_dir.glob("SYN-*.json")) if path.stem in train_ids]
    if args.multi_positive_dir:
        clarification = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.multi_positive_dir.glob("SYN-*.json")) if path.stem in train_ids]
        packets = attach_multi_positive_labels(packets, clarification)
    print(json.dumps(finetune_triplets(build_triplets(packets), args.model, args.output_dir, args.epochs, args.batch_size), ensure_ascii=False, indent=2))
