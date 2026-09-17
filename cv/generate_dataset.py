#!/usr/bin/env python3
"""Build an auditable procedural synthetic visual-instability demo dataset."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
VERSION = "procedural-cv-v2"
LABELS = (
    "stable_uniform",
    "creaming",
    "phase_separation",
    "heterogeneous",
    "uncertain",
)
SPLITS = ("train", "validation", "test")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_for_sequence(class_sequence_index, sequences_per_class):
    """Assign a split within each visual class without splitting a sequence."""
    if sequences_per_class == 1:
        return "train"
    if sequences_per_class == 2:
        return "train" if class_sequence_index == 0 else "validation"
    train_count = min(sequences_per_class - 2, max(1, round(sequences_per_class * 0.70)))
    validation_count = min(sequences_per_class - train_count - 1, max(1, round(sequences_per_class * 0.15)))
    if class_sequence_index < train_count:
        return "train"
    if class_sequence_index < train_count + validation_count:
        return "validation"
    return "test"


def color_jitter(color, rng, amount=12):
    return tuple(max(0, min(255, value + rng.randint(-amount, amount))) for value in color)


def draw_liquid(draw, label, box, rng):
    left, top, right, bottom = box
    width, height = right - left, bottom - top
    liquid_top = top + int(height * rng.uniform(0.30, 0.38))
    base = color_jitter((218, 227, 221), rng, 7)
    draw.rounded_rectangle((left, liquid_top, right, bottom), radius=max(8, width // 7), fill=base)
    draw.ellipse((left, liquid_top - height // 30, right, liquid_top + height // 30), fill=color_jitter(base, rng, 3))

    if label == "creaming":
        cream_end = liquid_top + int(height * rng.uniform(0.13, 0.20))
        cream = color_jitter((244, 232, 193), rng, 6)
        draw.rounded_rectangle((left, liquid_top, right, cream_end), radius=max(6, width // 10), fill=cream)
        draw.ellipse((left, liquid_top - height // 30, right, liquid_top + height // 30), fill=color_jitter(cream, rng, 3))
        draw.line((left + width // 18, cream_end, right - width // 18, cream_end), fill=(184, 166, 126), width=max(2, height // 95))
    elif label == "phase_separation":
        boundary = liquid_top + int(height * rng.uniform(0.43, 0.55))
        upper = color_jitter((242, 221, 163), rng, 6)
        lower = color_jitter((170, 205, 216), rng, 6)
        draw.rectangle((left, liquid_top, right, boundary), fill=upper)
        draw.rectangle((left, boundary, right, bottom), fill=lower)
        draw.ellipse((left, liquid_top - height // 30, right, liquid_top + height // 30), fill=color_jitter(upper, rng, 3))
        draw.line((left + width // 20, boundary, right - width // 20, boundary), fill=(102, 126, 134), width=max(2, height // 75))
    elif label == "heterogeneous":
        for _ in range(rng.randint(18, 34)):
            radius = rng.randint(max(4, width // 42), max(7, width // 13))
            x = rng.randint(left + radius, right - radius)
            y = rng.randint(liquid_top + radius, bottom - radius)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color_jitter((157, 183, 170), rng, 20))
    elif label == "uncertain":
        for _ in range(rng.randint(5, 9)):
            y = rng.randint(liquid_top + height // 12, bottom - height // 12)
            draw.arc((left + width // 12, y - height // 15, right - width // 12, y + height // 15), 185, 355,
                     fill=color_jitter((165, 181, 174), rng, 12), width=max(1, height // 130))


def render_image(label, rng, image_size):
    scale = 3
    size = image_size * scale
    background_top = color_jitter((239, 242, 239), rng, 4)
    background_bottom = color_jitter((218, 225, 222), rng, 5)
    image = Image.new("RGB", (size, size), background_top)
    draw = ImageDraw.Draw(image)
    for y in range(size):
        mix = y / max(1, size - 1)
        color = tuple(round(background_top[i] * (1 - mix) + background_bottom[i] * mix) for i in range(3))
        draw.line((0, y, size, y), fill=color)

    center_x = size // 2 + rng.randint(-size // 32, size // 32)
    vial_width = int(size * rng.uniform(0.43, 0.49))
    vial_left, vial_right = center_x - vial_width // 2, center_x + vial_width // 2
    body_top, body_bottom = int(size * 0.22), int(size * 0.84)
    neck_width = int(vial_width * 0.58)
    neck_left, neck_right = center_x - neck_width // 2, center_x + neck_width // 2

    shadow = (vial_left - size // 24, body_bottom - size // 36, vial_right + size // 24, body_bottom + size // 22)
    draw.ellipse(shadow, fill=(174, 185, 184))
    draw.ellipse((shadow[0] + size // 40, shadow[1] + size // 80, shadow[2] - size // 40, shadow[3] - size // 90), fill=(193, 202, 200))

    glass = (235, 245, 245)
    outline = (84, 111, 116)
    draw.rounded_rectangle((vial_left, body_top, vial_right, body_bottom), radius=size // 20, fill=glass, outline=outline, width=max(2, size // 160))
    draw.rectangle((neck_left, body_top - size // 15, neck_right, body_top + size // 28), fill=glass, outline=outline, width=max(2, size // 160))
    cap_top, cap_bottom = body_top - size // 11, body_top - size // 24
    draw.rounded_rectangle((neck_left - size // 42, cap_top, neck_right + size // 42, cap_bottom), radius=size // 70,
                           fill=(48, 73, 79), outline=(35, 54, 59), width=max(2, size // 180))
    for x in range(neck_left, neck_right, max(3, size // 35)):
        draw.line((x, cap_top + size // 100, x, cap_bottom - size // 100), fill=(76, 99, 102), width=max(1, size // 260))

    inner = (vial_left + size // 45, body_top + size // 35, vial_right - size // 45, body_bottom - size // 38)
    draw_liquid(draw, label, inner, rng)
    for tick in range(4):
        y = body_top + size // 7 + tick * size // 10
        draw.line((vial_right - size // 27, y, vial_right - size // 47, y), fill=(104, 130, 132), width=max(1, size // 260))
    draw.line((vial_left + size // 33, body_top + size // 18, vial_left + size // 33, body_bottom - size // 16), fill=(255, 255, 255), width=max(2, size // 100))
    draw.arc((vial_left + size // 30, body_top + size // 20, vial_right - size // 22, body_bottom - size // 26), 275, 70,
             fill=(255, 255, 255), width=max(1, size // 230))

    capture = {
        "lighting": rng.choice(("softbox_neutral", "softbox_warm", "softbox_cool")),
        "focus": "sharp",
        "view": "vial_front",
        "rotation_degrees": 0,
        "scene": "studio_vial",
        "render_quality": "supersampled_procedural",
    }
    if capture["lighting"] == "softbox_warm":
        image = ImageEnhance.Color(image).enhance(0.94)
        image = ImageEnhance.Brightness(image).enhance(1.03)
    elif capture["lighting"] == "softbox_cool":
        image = ImageEnhance.Contrast(image).enhance(1.04)
    image = image.resize((image_size, image_size), Image.Resampling.LANCZOS)
    return image, capture


def build(output, seed=2026, sequences_per_class=24, views_per_sequence=3, image_size=256):
    if sequences_per_class < 1 or views_per_sequence < 1 or image_size < 32:
        raise ValueError("sequences_per_class dan views_per_sequence harus positif; image_size minimal 32")
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    total_sequences = len(LABELS) * sequences_per_class
    manifest = []
    sequence_index = 0
    for label in LABELS:
        for class_sequence_index in range(sequences_per_class):
            sequence_seed = seed * 1_000_003 + sequence_index
            sequence_rng = random.Random(sequence_seed)
            sample_sequence_id = f"SYN-BATCH-{sequence_index + 1:04d}"
            split = split_for_sequence(class_sequence_index, sequences_per_class)
            for view_index in range(views_per_sequence):
                image_id = f"SYN-CV-{sequence_index + 1:04d}-{view_index + 1:02d}"
                image_rng = random.Random(sequence_rng.randrange(2**63))
                image, capture = render_image(label, image_rng, image_size)
                relative_path = Path("images") / split / label / f"{image_id}.png"
                image_path = output / relative_path
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(image_path, format="PNG", optimize=False)
                manifest.append({
                    "image_id": image_id,
                    "sample_sequence_id": sample_sequence_id,
                    "split": split,
                    "label": label,
                    "image_path": relative_path.as_posix(),
                    "image_sha256": sha256(image_path),
                    "data_origin": "synthetic_demo",
                    "scientific_validation_status": "not_validated_for_production",
                    "generator_version": VERSION,
                    "generator_seed": seed,
                    "capture_conditions": capture,
                    "annotation_basis": "procedural_generator_parameters",
                    "human_verified": False,
                })
            sequence_index += 1

    manifest.sort(key=lambda row: row["image_id"])
    (output / "manifest.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in manifest), encoding="utf-8"
    )
    result = {
        "dataset_version": VERSION,
        "seed": seed,
        "labels": list(LABELS),
        "image_size": image_size,
        "sequences_per_class": sequences_per_class,
        "views_per_sequence": views_per_sequence,
        "sequence_count": total_sequences,
        "split_unit": "sample_sequence_id; stratified by visual label",
        "image_count": len(manifest),
        "class_counts": {label: sum(row["label"] == label for row in manifest) for label in LABELS},
        "split_counts": {split: sum(row["split"] == split for row in manifest) for split in SPLITS},
        "limitations": [
            "Gambar dibuat secara prosedural untuk demonstrasi, bukan foto sampel kosmetik.",
            "Label berasal dari parameter generator dan bukan scientific ground truth.",
            "Dataset tidak memvalidasi model untuk stability assessment kosmetik nyata.",
        ],
    }
    (output / "dataset_card.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    errors = validate_directory(output)
    if errors:
        raise ValueError(errors)
    return result


def validate_directory(output):
    output = Path(output)
    errors = []
    try:
        manifest_path = output / "manifest.jsonl"
        card_path = output / "dataset_card.json"
        manifest = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]
        card = json.loads(card_path.read_text(encoding="utf-8"))
        if not manifest:
            errors.append("manifest kosong")
            return errors
        ids = [row["image_id"] for row in manifest]
        if len(ids) != len(set(ids)):
            errors.append("image_id duplikat")
        sequence_splits = {}
        for row in manifest:
            if row["label"] not in LABELS:
                errors.append(f"{row['image_id']}: label tidak dikenal")
            if row["data_origin"] != "synthetic_demo" or row["human_verified"] is not False:
                errors.append(f"{row['image_id']}: provenance tidak valid")
            if row["scientific_validation_status"] != "not_validated_for_production":
                errors.append(f"{row['image_id']}: status ilmiah tidak valid")
            if row["generator_version"] != VERSION:
                errors.append(f"{row['image_id']}: generator version tidak valid")
            image_path = output / row["image_path"]
            if not image_path.is_file():
                errors.append(f"{row['image_id']}: file gambar hilang")
            elif sha256(image_path) != row["image_sha256"]:
                errors.append(f"{row['image_id']}: hash gambar tidak cocok")
            existing_split = sequence_splits.setdefault(row["sample_sequence_id"], row["split"])
            if existing_split != row["split"]:
                errors.append(f"{row['image_id']}: sample sequence bocor lintas split")
        if card["image_count"] != len(manifest):
            errors.append("image_count dataset card tidak cocok")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal membaca dataset CV: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--output", type=Path, default=ROOT / "cv" / "data" / "synthetic_v1")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--sequences-per-class", type=int, default=24)
    parser.add_argument("--views-per-sequence", type=int, default=3)
    parser.add_argument("--image-size", type=int, default=256)
    args = parser.parse_args()
    try:
        result = build(args.output, args.seed, args.sequences_per_class, args.views_per_sequence, args.image_size) if args.command == "build" else {"validation_errors": validate_directory(args.output)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return int(bool(result.get("validation_errors")))
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
