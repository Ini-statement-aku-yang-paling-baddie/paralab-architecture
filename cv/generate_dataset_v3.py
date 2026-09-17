#!/usr/bin/env python3
"""Generate the diverse procedural v3 visual-instability demo dataset."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
VERSION = "procedural-cv-v3"
LABELS = ("stable_uniform", "creaming", "phase_separation", "heterogeneous")
SPLITS = ("train", "validation", "test")
PALETTES = (
    (220, 225, 215), (232, 214, 184), (202, 220, 225), (212, 205, 227),
    (220, 194, 196), (199, 218, 193), (225, 207, 170), (190, 211, 203),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jitter(color, rng, amount=12):
    return tuple(max(0, min(255, value + rng.randint(-amount, amount))) for value in color)


def blend(first, second, fraction):
    return tuple(round(first[index] * (1 - fraction) + second[index] * fraction) for index in range(3))


def split_for_sequence(index, count):
    if count < 3:
        return "train" if index == 0 else "validation"
    train_count = min(count - 2, max(1, round(count * 0.70)))
    validation_count = min(count - train_count - 1, max(1, round(count * 0.15)))
    return "train" if index < train_count else "validation" if index < train_count + validation_count else "test"


def draw_gradient(draw, size, top, bottom):
    for y in range(size):
        draw.line((0, y, size, y), fill=blend(top, bottom, y / max(1, size - 1)))


def draw_texture(draw, box, color, rng, count, radius_range):
    left, top, right, bottom = box
    for _ in range(count):
        radius = rng.randint(*radius_range)
        x = rng.randint(left + radius, right - radius)
        y = rng.randint(top + radius, bottom - radius)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=jitter(color, rng, 14))


def draw_vessel(draw, size, rng, vessel_type, liquid_box, label, palette):
    left, top, right, bottom = liquid_box
    width, height = right - left, bottom - top
    liquid_top = top + int(height * rng.uniform(0.22, 0.42))
    base = jitter(palette, rng, 12)
    glass_outline = (77, 92, 96)
    glass_highlight = (248, 252, 250)
    draw.rounded_rectangle((left, top, right, bottom), radius=max(8, width // 9), fill=(228, 237, 235), outline=glass_outline, width=max(2, size // 145))

    if vessel_type == "wide_jar":
        cap_box = (left - width // 12, top - height // 14, right + width // 12, top + height // 28)
    elif vessel_type == "amber_vial":
        cap_box = (left + width // 6, top - height // 11, right - width // 6, top + height // 35)
    else:
        cap_box = (left + width // 5, top - height // 10, right - width // 5, top + height // 35)
    draw.rounded_rectangle(cap_box, radius=max(3, width // 20), fill=(48, 61, 63), outline=(28, 37, 39), width=max(1, size // 180))

    if vessel_type == "amber_vial":
        base = blend(base, (104, 76, 43), 0.28)
    inner = (left + width // 18, top + height // 18, right - width // 18, bottom - height // 18)
    il, it, ir, ib = inner
    draw.rounded_rectangle((il, liquid_top, ir, ib), radius=max(6, width // 11), fill=base)
    draw.ellipse((il, liquid_top - height // 38, ir, liquid_top + height // 38), fill=jitter(base, rng, 3))

    parameters = {"fill_fraction": round((ib - liquid_top) / max(1, ib - it), 3)}
    if label == "creaming":
        layer_height = int(height * rng.uniform(0.06, 0.20))
        strength = rng.uniform(0.10, 0.33)
        cream = blend(base, (246, 239, 205), strength)
        draw.rounded_rectangle((il, liquid_top, ir, liquid_top + layer_height), radius=max(4, width // 15), fill=cream)
        draw.line((il + width // 20, liquid_top + layer_height, ir - width // 20, liquid_top + layer_height), fill=blend(cream, base, 0.55), width=max(1, size // 220))
        parameters.update({"top_phase_strength": round(strength, 3), "top_phase_height": round(layer_height / height, 3)})
    elif label == "phase_separation":
        boundary = liquid_top + int((ib - liquid_top) * rng.uniform(0.33, 0.68))
        contrast = rng.uniform(0.14, 0.42)
        upper = blend(base, (243, 224, 179), contrast)
        lower = blend(base, (154, 192, 205), contrast * rng.uniform(0.55, 0.95))
        draw.rectangle((il, liquid_top, ir, boundary), fill=upper)
        draw.rectangle((il, boundary, ir, ib), fill=lower)
        wave = max(2, size // 110)
        points = [(il, boundary)]
        for x in range(il, ir + 1, max(2, size // 40)):
            points.append((x, boundary + rng.randint(-wave, wave)))
        points.append((ir, boundary))
        draw.line(points, fill=blend(upper, lower, 0.50), width=max(2, size // 140))
        parameters.update({"interface_contrast": round(contrast, 3), "boundary_height": round((boundary - liquid_top) / max(1, ib - liquid_top), 3)})
    elif label == "heterogeneous":
        density = rng.randint(7, 30)
        blob_color = blend(base, (106, 139, 123), rng.uniform(0.18, 0.42))
        draw_texture(draw, (il, liquid_top, ir, ib), blob_color, rng, density, (max(2, size // 85), max(4, size // 32)))
        parameters.update({"texture_density": density, "texture_contrast": round(abs(blob_color[1] - base[1]) / 255, 3)})
    else:
        bubble_count = rng.randint(0, 4)
        draw_texture(draw, (il, liquid_top, ir, ib), blend(base, (255, 255, 255), 0.25), rng, bubble_count, (max(1, size // 150), max(2, size // 85)))
        parameters.update({"bubble_count": bubble_count})

    draw.line((left + width // 12, top + height // 8, left + width // 12, bottom - height // 10), fill=glass_highlight, width=max(1, size // 115))
    if vessel_type != "amber_vial":
        draw.arc((left + width // 10, top + height // 8, right - width // 12, bottom - height // 12), 276, 82, fill=glass_highlight, width=max(1, size // 240))
    for tick in range(3):
        y = top + height // 3 + tick * height // 7
        draw.line((right - width // 12, y, right - width // 20, y), fill=(100, 116, 117), width=max(1, size // 260))
    return parameters


def render_image(label, rng, image_size):
    scale = 3
    size = image_size * scale
    camera_profile = rng.choice(("studio_neutral", "benchtop_warm", "shelf_dim", "cool_lab"))
    backgrounds = {
        "studio_neutral": ((237, 240, 237), (205, 215, 211)),
        "benchtop_warm": ((239, 229, 213), (190, 176, 158)),
        "shelf_dim": ((76, 83, 84), (33, 39, 40)),
        "cool_lab": ((221, 232, 236), (173, 194, 203)),
    }
    top, bottom = backgrounds[camera_profile]
    image = Image.new("RGB", (size, size), top)
    draw = ImageDraw.Draw(image)
    draw_gradient(draw, size, jitter(top, rng, 5), jitter(bottom, rng, 5))

    vessel_type = rng.choice(("cylindrical_vial", "wide_jar", "amber_vial"))
    width = int(size * rng.uniform(0.35, 0.52))
    height = int(size * rng.uniform(0.53, 0.68))
    center_x = size // 2 + rng.randint(-size // 10, size // 10)
    bottom_y = int(size * rng.uniform(0.78, 0.88))
    box = (center_x - width // 2, bottom_y - height, center_x + width // 2, bottom_y)
    shadow = (box[0] - width // 9, box[3] - size // 44, box[2] + width // 9, box[3] + size // 30)
    draw.ellipse(shadow, fill=blend(bottom, (35, 42, 43), 0.35))

    palette = rng.choice(PALETTES)
    condition_parameters = draw_vessel(draw, size, rng, vessel_type, box, label, palette)
    blur_radius = rng.choice((0.0, 0.0, 0.0, 0.18, 0.35)) * scale
    if blur_radius:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.90, 1.10))
    image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.88, 1.12))
    image = image.resize((image_size, image_size), Image.Resampling.LANCZOS)
    return image, {
        "vessel_type": vessel_type,
        "camera_profile": camera_profile,
        "liquid_palette": list(palette),
        "condition_parameters": condition_parameters,
        "focus": "soft" if blur_radius else "sharp",
        "render_quality": "domain_randomized_procedural",
    }


def build(output, seed=2026, sequences_per_class=40, views_per_sequence=4, image_size=256):
    if sequences_per_class < 3 or views_per_sequence < 1 or image_size < 64:
        raise ValueError("sequences_per_class minimal 3, views_per_sequence positif, image_size minimal 64")
    output = Path(output).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    rows, sequence_index = [], 0
    for label in LABELS:
        for class_sequence_index in range(sequences_per_class):
            split = split_for_sequence(class_sequence_index, sequences_per_class)
            sequence_id = f"SYN-V3-BATCH-{sequence_index + 1:04d}"
            sequence_rng = random.Random(seed * 1_000_003 + sequence_index)
            for view_index in range(views_per_sequence):
                image_id = f"SYN-V3-{sequence_index + 1:04d}-{view_index + 1:02d}"
                image, metadata = render_image(label, random.Random(sequence_rng.randrange(2**63)), image_size)
                relative_path = Path("images") / split / label / f"{image_id}.png"
                path = output / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                image.save(path, format="PNG", optimize=False)
                rows.append({
                    "image_id": image_id, "sample_sequence_id": sequence_id, "split": split, "label": label,
                    "image_path": relative_path.as_posix(), "image_sha256": sha256(path),
                    "data_origin": "synthetic_demo", "scientific_validation_status": "not_validated_for_production",
                    "generator_version": VERSION, "generator_seed": seed, "human_verified": False,
                    "annotation_basis": "procedural_generator_parameters", **metadata,
                })
            sequence_index += 1
    rows.sort(key=lambda row: row["image_id"])
    (output / "manifest.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    result = {
        "dataset_version": VERSION, "seed": seed, "labels": list(LABELS), "image_size": image_size,
        "sequences_per_class": sequences_per_class, "views_per_sequence": views_per_sequence,
        "sequence_count": sequence_index, "image_count": len(rows),
        "split_unit": "sample_sequence_id; stratified by visual label",
        "class_counts": {label: sum(row["label"] == label for row in rows) for label in LABELS},
        "split_counts": {split: sum(row["split"] == split for row in rows) for split in SPLITS},
        "limitations": [
            "Gambar adalah domain-randomized procedural renders, bukan foto kosmetik nyata.",
            "Label hanya merepresentasikan parameter generator, bukan scientific ground truth.",
            "Dataset tidak memvalidasi generalisasi ke stability assessment kosmetik nyata.",
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
        rows = [json.loads(line) for line in (output / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        card = json.loads((output / "dataset_card.json").read_text(encoding="utf-8"))
        sequence_splits = {}
        by_split = {split: set() for split in SPLITS}
        for row in rows:
            if row["label"] not in LABELS or row["split"] not in SPLITS:
                errors.append(f"{row['image_id']}: label/split invalid")
            if row["generator_version"] != VERSION or row["data_origin"] != "synthetic_demo" or row["human_verified"] is not False:
                errors.append(f"{row['image_id']}: provenance invalid")
            if row["scientific_validation_status"] != "not_validated_for_production":
                errors.append(f"{row['image_id']}: scientific status invalid")
            if not {"vessel_type", "camera_profile", "liquid_palette", "condition_parameters"} <= set(row):
                errors.append(f"{row['image_id']}: nuisance metadata missing")
            path = output / row["image_path"]
            if not path.is_file() or sha256(path) != row["image_sha256"]:
                errors.append(f"{row['image_id']}: image missing or hash mismatch")
            prior = sequence_splits.setdefault(row["sample_sequence_id"], row["split"])
            if prior != row["split"]:
                errors.append(f"{row['image_id']}: sequence leakage")
            by_split[row["split"]].add(row["label"])
        for split, labels in by_split.items():
            if labels != set(LABELS):
                errors.append(f"{split}: class coverage invalid")
        if card["image_count"] != len(rows) or card["dataset_version"] != VERSION:
            errors.append("dataset card invalid")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"gagal membaca dataset v3: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--output", type=Path, default=ROOT / "cv" / "data" / "synthetic_v3")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--sequences-per-class", type=int, default=40)
    parser.add_argument("--views-per-sequence", type=int, default=4)
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
