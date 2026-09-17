# FormuLab CV Pilot Architecture Specification

> **For Hermes:** This is a pilot specification and decision input, not a production-validation plan.

**Goal:** Demonstrate an auditable visual-instability screening workflow for cosmetic-formulation samples using a domain-randomized synthetic image dataset.

**Architecture:** A procedural generator creates image sequences plus provenance metadata. A Kaggle training notebook validates the dataset, trains a small CNN, selects a model using validation data, and evaluates once on a held-out sequence-level split. The model output is explicitly a synthetic-demo screening signal, never a cosmetic stability decision.

**Tech Stack:** Python 3, Pillow, JSONL manifest, PyTorch, torchvision, scikit-learn, Kaggle GPU.

---

## 1. Pilot Objective and Boundary

| Item | Pilot decision |
|---|---|
| Business problem | Early visual triage of possible sample instability during a lab journal workflow |
| Pilot capability | Classify procedural renders into `stable_uniform`, `creaming`, `phase_separation`, or `heterogeneous` |
| Product family | O/W gel-cream moisturizer for oily skin, represented only as a synthetic-demo context |
| Primary user | R&D formulator reviewing a stability checkpoint |
| Decision ownership | Human formulator always owns follow-up, reformulation, and go/no-go decisions |
| Out of scope | Production stability validation, shelf-life prediction from image alone, droplet-size measurement, regulatory approval, automatic journal writeback |

**Required UI disclaimer:** `Synthetic-demo visual screening. Not validated for real cosmetic stability assessment.`

## 2. Architecture at Pilot Stage

```text
Procedural generator V3
  → PNG images + JSONL manifest + SHA-256 hashes
  → manifest/provenance/sequence-split validation
  → Kaggle training notebook
  → TinyVialCNN baseline
  → validation-selected checkpoint
  → held-out test evaluation
  → probability + predicted visual pattern + limitation
  → human review in FormuLab timeline
```

### Components and current artifacts

| Layer | Responsibility | Current artifact |
|---|---|---|
| Synthetic data | Creates domain-randomized sample renders and labels derived only from generator parameters | `cv/generate_dataset_v3.py` |
| Dataset | Four labels, 160 sequence groups, four views per sequence, 640 PNG | `cv/data/synthetic_v3/` |
| Audit manifest | Holds image ID, sequence ID, split, hash, label, render conditions, provenance | `cv/data/synthetic_v3/manifest.jsonl` |
| Dataset validator | Rejects missing files, altered hashes, unknown labels, provenance errors, and sequence leakage | `cv/generate_dataset_v3.py validate` |
| Training | Validates manifest, trains CNN, selects by validation loss, evaluates test once | `cv/notebooks/train_visual_screening.ipynb` |
| Model output | Class probability, predicted class, confidence, model/dataset version, limitation | Kaggle output checkpoint and report |
| Human control | Human review and lab testing must follow any signal | Future UI integration |

## 3. Dataset Design and Split

| Split | Images | Per visual class | Sequence split rule |
|---|---:|---:|---|
| Train | 448 | 112 | Whole `sample_sequence_id` stays in train |
| Validation | 96 | 24 | Whole sequence stays in validation |
| Test | 96 | 24 | Whole sequence stays in test |
| Total | 640 | 160 | No sequence crosses a split |

V3 randomizes vessel type, camera environment, crop, lighting, fill level, liquid palette, blur, contrast, shadow, and visible instability intensity. These nuisance variables are retained in the manifest for auditability.

`uncertain` is deliberately not a model class. It is an abstention or human-review state because training a synthetic visual pattern named “uncertain” would create artificial label leakage.

## 4. Model and Evaluation Contract

| Item | Pilot rule |
|---|---|
| Baseline model | TinyVialCNN, trained from scratch and suitable for offline Kaggle execution |
| Model selection | Minimum validation loss only |
| Test discipline | Test split is evaluated after checkpoint selection, not used for tuning |
| Required metrics | Accuracy, per-class precision/recall/F1, confusion matrix, confidence distribution |
| Required follow-up metric | Sequence-level prediction by aggregating the four image probabilities for one `sample_sequence_id` |
| Failure handling | Low confidence, conflicting views, missing image, or poor capture quality routes to human review |
| Valid interpretation | Pipeline integration and synthetic-task separability |
| Invalid interpretation | Real-world cosmetic performance, stability guarantee, production readiness |

## 5. Current Pilot Evidence

| Version | Result | Interpretation |
|---|---|---|
| V2 | 100% image-level test accuracy on 45 images | Smoke-test success only. Classes were too template-like, so it is not persuasive as a generalization metric. |
| V3 | Dataset generated and validated, Kaggle notebook redirected to V3 | Must be trained and evaluated before any performance statement. |

## 6. Resource and Finance Assumptions

| Cost/resource area | Pilot assumption | Finance implication |
|---|---|---|
| Dataset creation | Local procedural generation using Python/Pillow | No external data-license cost at pilot stage |
| Training | Kaggle notebook and available GPU quota | Budget Rp0 if free quota remains; record actual quota/runtime |
| Storage | 640 PNG plus manifest and model artifacts | Low, typically below 20 MB excluding notebook environment |
| Model development | Team engineering time | Primary pilot cost is labor, not cloud inference |
| Inference | Not deployed yet | No recurring serving cost should be claimed |
| External real data | Not acquired | No claim of real-data validation or commercial data value |

### Finance reporting guardrails

- Report costs as prototype assumptions, not production estimates.
- Do not monetize the V2/V3 accuracy result.
- Distinguish zero cash spend from nonzero engineering labor.
- Any proposed production budget requires a separate data-acquisition, labeling, legal, and MLOps estimate.

## 7. Quarterly Pilot Plan

| Period | Deliverable | Exit criterion | Finance/planning input |
|---|---|---|---|
| Q1: Pilot validation | Run V3 Kaggle baseline and archive metrics/artifacts | Manifest passes, sequence-safe evaluation completes, limitations shown | GPU runtime, storage, engineering hours |
| Q2: Robustness | Add controlled stress set: lighting, blur, crop, low-contrast and borderline phase cues | Sequence-level metrics and error analysis reported | Incremental compute and annotation-review estimate |
| Q3: Data-readiness decision | Determine whether permissioned real images can be collected and reviewed | Data governance, consent, capture protocol, and labeling ownership approved or rejected | Data collection, expert labeling, legal/security cost scenarios |
| Q4: Go/no-go | Decide between a constrained demo capability or a real-data validation program | No production launch without real-domain validation | Investment case based on actual Q1-Q3 evidence |

## 8. Risks and Mitigations

| Risk | Pilot impact | Mitigation |
|---|---|---|
| Synthetic shortcut learning | High accuracy without useful real-world behavior | V3 domain randomization, sequence holdout, stress tests, no production claim |
| Label ambiguity | Incorrectly forces uncertain visual states into one class | Keep abstention separate from classifier labels |
| Domain gap | Cosmetics may not resemble procedural renders | State limitation; require real, permissioned images before production validation |
| Small holdout | Metric variance may be high | Report per-class and sequence-level results, not headline accuracy alone |
| Cost optimism | Prototype looks inexpensive but hides real-data costs | Separate free pilot cost from future data/labeling/MLOps cost |
| Human overreliance | AI signal treated as a decision | Human review and lab test remain mandatory |

## 9. Decision Needed After the V3 Kaggle Run

1. **If V3 test accuracy remains near-perfect:** treat it as evidence of remaining synthetic shortcuts, not success. Increase hard negatives and stress testing before changing the model.
2. **If V3 shows meaningful confusion but stable sequence-level performance:** retain TinyVialCNN as the pilot baseline and integrate only a labeled synthetic-demo UI flow.
3. **If V3 is unstable or weak:** inspect errors and dataset parameters first. Do not change to a larger model as the first reaction.
4. **For all outcomes:** no production, scientific, regulatory, or financial benefit claim is permitted without real-domain data and expert review.
