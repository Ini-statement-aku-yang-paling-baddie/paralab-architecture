# FormuLab AI: Architecture v4

> **Status:** implementation blueprint for the hackathon prototype  
> **Supersedes:** `ARCHITECTURE-V3.md` for MVP scope and data-flow decisions  
> **Preserves:** v3 principles of local-first inference, evidence-grounded RAG, deterministic guardrails, access control before retrieval, human sign-off, and auditable outputs.

---

## 1. Product Decision

### 1.1 MVP domain

The MVP validates one coherent vertical:

> **Oil-in-water gel-cream moisturizer for oily skin.**

The product vision remains broader than this vertical, but the prototype does not claim to model every cosmetic category. One formulation family allows F1, F2, F3, F5, the knowledge pool, and the dataset to share one ontology.

### 1.2 Product positioning

FormuLab AI is not a replacement for Smart Lab. It is a researcher-facing evidence, guardrail, and experimental-memory layer that can sit within a Smart Lab workflow.

> **FormuLab turns a lab journal into an evidence-grounded co-pilot. It retrieves prior experiments, catches known formulation risks, monitors early stability signals, and preserves the learning from every trial.**

### 1.3 Core user loop

```text
Research brief
  → F1 finds evidence and similar trials
  → researcher drafts a formula
  → F2 normalizes ingredients and applies auditable guardrails
  → researcher runs a trial and records checkpoints
  → F3 forecasts long-horizon failure risk from early trends
  → F1 retrieves similar historical failure patterns as evidence
  → researcher decides continue, reformulate, or request review
  → verified outcome becomes a new journal evidence record
```

### 1.4 Scope decision

| Priority | Module | MVP role |
|---|---|---|
| P0 | F1: Evidence Research Copilot | Hybrid RAG with citations and abstention |
| P0 | F2: Formulation Guardrail | Deterministic ingredient/rule screening |
| P0 | F3: Predictive Stability Sentinel | Scenario-based early-risk forecast from longitudinal data |
| P0 | F5: Voice-to-Structured Logging | Confirmed low-friction lab notes |
| P1 | F3 visual upload | Evidence attachment and image quality check only |
| P2 | Computer-vision instability classifier | Deferred pending an appropriate labeled dataset |
| P2 | Active learning / next-best experiment | Roadmap after real historical trajectories are available |

---

## 2. Non-Negotiable Principles

1. **One canonical journal schema.** Modules exchange typed fields, not free-form text.
2. **F1 retrieves evidence.** Its prose does not become an unverified numerical model feature.
3. **F2 produces normalized inputs and guardrail-derived features.** It does not predict scientific truth.
4. **F3 forecasts from formula, process, and actual checkpoint trends.** It must state whether its domain is supported.
5. **RAG evidence explains a forecast after it is made.** It does not silently override the predictive model.
6. **Synthetic data proves integration and workflow, not scientific performance.** Every synthetic record is labelled clearly.
7. **A teacher LLM may generate prose only from controlled seeds.** It must not invent numeric trajectories, measurements, or labels.
8. **Every user-facing claim has provenance.** Rule version, source IDs, model version, confidence, and human review state are stored.
9. **The system may abstain.** Unsupported domain, insufficient observations, or contradictory evidence produce an explicit limitation rather than false precision.
10. **Human sign-off is mandatory.** No AI output automatically finalizes a formula, observation, or compliance decision.

---

## 3. Logical Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                         RESEARCHER WORKSPACE                               │
│ Dashboard · Journal Editor · Formula Table · Stability Timeline · Voice UI │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │ authenticated API
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                     FORMULAB MODULAR BACKEND                               │
│                                                                            │
│ ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐ │
│ │ Journal API │  │ Access/Audit │  │ Ingest/Index   │  │ Model Adapter  │ │
│ │ canonical   │  │ ACL/proven.  │  │ background job │  │ local runtime  │ │
│ └──────┬──────┘  └──────┬───────┘  └──────┬─────────┘  └──────┬─────────┘ │
│        │                │                 │                   │           │
│ ┌──────▼──────┐ ┌───────▼──────┐ ┌────────▼─────────┐ ┌──────▼─────────┐ │
│ │ F1 Evidence │ │ F2 Guardrail │ │ F3 Stability     │ │ F5 Voice       │ │
│ │ Hybrid RAG  │ │ Rule Engine │ │ Sentinel          │ │ Structuring    │ │
│ └──────┬──────┘ └───────┬──────┘ └────────┬─────────┘ └──────┬─────────┘ │
│        └────────────────┴──────────────────┴──────────────────┘           │
│                                  │                                         │
│                  schema validation · coverage gate · explanation layer     │
└──────────────────────────────────┬─────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                    │
│ Canonical journal DB · ingredient KB · rule KB · evidence corpus · audit  │
│ Derived indexes: full-text index · vector index · model feature snapshots  │
└────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Deployment decision

Use a modular monolith in the hackathon:

- web frontend chosen by the team;
- one Python backend for API, ML, and background jobs;
- PostgreSQL for canonical records;
- PostgreSQL full-text search plus pgvector for the MVP retrieval layer;
- local or S3-compatible object storage for permitted audio/images;
- adapter interface for embedding, reranker, LLM, STT, and F3 model.

Microservices are explicitly out of scope.

---

## 4. Canonical Ontology

### 4.1 Ingredient identity

Every ingredient has a stable internal ID. Aliases, supplier names, and spelling variants map to that ID.

```json
{
  "ingredient_id": "ING:NIACINAMIDE",
  "inci_name": "Niacinamide",
  "display_name": "Niacinamide",
  "aliases": ["niasinamida", "vitamin b3", "nicotinamide"],
  "functional_classes": ["active", "sebum_regulator"],
  "phase_compatibility": ["water"],
  "source_ids": ["INGREF-001"]
}
```

### 4.2 Formula snapshot

A formula snapshot is immutable once saved. Any edit creates a new version.

```json
{
  "formula_version_id": "FORM-2026-001-V2",
  "journal_id": "J-2026-001",
  "product_family": "o_w_gel_cream_moisturizer",
  "ingredients": [
    {
      "ingredient_id": "ING:NIACINAMIDE",
      "concentration_pct_w_w": 5.0,
      "phase": "water"
    }
  ],
  "process": {
    "heating_temp_c": 75,
    "homogenization_rpm": 2500,
    "mixing_time_min": 15,
    "cooling_profile": "ambient_agitation",
    "final_ph": 5.7
  },
  "created_at": "ISO-8601"
}
```

### 4.3 Stability checkpoint

```json
{
  "checkpoint_id": "CHK-J-2026-001-T02-W4",
  "trial_id": "J-2026-001-T02",
  "week": 4,
  "storage_condition": {
    "temperature_c": 40,
    "humidity_pct": null
  },
  "measurements": {
    "ph": 5.93,
    "viscosity_cp": 12100,
    "color_delta_e": null
  },
  "observations": {
    "appearance": "slightly_nonuniform",
    "odor": "normal",
    "centrifuge_result": "not_tested",
    "freeze_thaw_result": "not_tested"
  },
  "capture_quality": "acceptable",
  "human_verified": true
}
```

### 4.4 Final outcome

```json
{
  "trial_id": "J-2026-001-T02",
  "final_status": "failed",
  "final_observation_week": 8,
  "failure_mode": "viscosity_collapse",
  "human_verified": true,
  "reviewer_role": "formulator"
}
```

---

## 5. Knowledge Pool

The knowledge pool is not one undifferentiated database. Every record has a source type, domain, quality state, visibility level, and limitation.

```text
Knowledge Pool
├── ingredient_master
│   ├── canonical INCI and aliases
│   ├── functional classes and formulation metadata
│   └── source/version metadata
├── formulation_rule_base
│   ├── compatibility rules
│   ├── pH and concentration constraints
│   ├── allergen and regulatory screening references
│   └── supplier-document / verification state
├── evidence_corpus
│   ├── structured synthetic moisturizer journals
│   ├── public formulation dataset summaries
│   ├── public scientific references
│   └── approved source metadata
├── stability_dataset
│   ├── synthetic formula/process seeds
│   ├── generated numeric checkpoint trajectories
│   ├── verified final outcome labels
│   └── scenario provenance
├── model_registry
│   ├── F3 feature schema
│   ├── model version and training provenance
│   └── metrics and domain coverage
└── journal_store
    ├── user journal/trial records
    ├── saved AI outputs
    └── audit events
```

### 5.1 Public data usage

Public data is used only for the role it supports:

| Source class | Correct use |
|---|---|
| INCI and ingredient references | Canonical names, aliases, functional metadata |
| Regulatory references | Prototype guardrail source, versioned and human-reviewed |
| Public cosmetic/formulation datasets | Methodology reference, feature inspiration, evidence corpus if domain-fit |
| Shampoo formulation dataset | External reference for formulation ML patterns, not a moisturizer model training source |
| mAb longitudinal stability dataset | Reference for early-to-final forecasting methodology, not a cosmetic model training source |
| Synthetic moisturizer data | Demo training and workflow validation only |

No public source is silently represented as Paragon data.

---

## 6. Synthetic Longitudinal Dataset

### 6.1 Purpose

The synthetic dataset proves the end-to-end integration of retrieval, rules, forecasting, voice capture, and auditability. It does not prove that the predictive model is scientifically validated for production.

Every record has:

```json
{
  "data_origin": "synthetic_demo",
  "scenario_generator_version": "v1",
  "scientific_validation_status": "not_validated_for_production"
}
```

### 6.2 Dataset size

| Entity | Count |
|---|---:|
| Journal projects | 200 |
| Trials per project | 3 |
| Total trials | 600 |
| Checkpoints per trial | 7: week 0, 1, 2, 4, 6, 8, 12 |
| Total checkpoint records | 4,200 |

### 6.3 Scenario families

Each trial seed belongs to a controlled trajectory family.

| Scenario family | Intended final outcome |
|---|---|
| `stable` | Passes through week 12 |
| `early_viscosity_drop` | Early decline that may be recoverable or fail later |
| `delayed_phase_separation` | Appears acceptable early, fails after intermediate checkpoints |
| `ph_drift` | Progressive pH movement linked to risk condition |
| `electrolyte_thickener_failure` | High electrolyte load plus sensitive thickener leads to viscosity failure |
| `process_parameter_failure` | Unfavorable mixing/heating process leads to instability pattern |
| `borderline` | Evidence remains insufficient and human review is preferred |

The distribution must include both stable and failed trials. The generator must avoid a trivial rule where a single feature perfectly predicts the final label.

### 6.4 Numeric trajectory generator

A deterministic or seeded stochastic generator creates numeric fields.

```text
Structured formula + process seed
  → scenario assignment
  → latent risk factors
  → baseline pH and viscosity
  → timepoint-specific drift / noise
  → observation state transitions
  → final outcome and failure week
```

Example conceptual relationships:

```text
high electrolyte load
+ electrolyte-sensitive thickener
+ negative viscosity slope at early checkpoints
→ elevated probability of viscosity-collapse trajectory
```

```text
process deviation
+ unstable emulsifier balance
→ elevated probability of delayed visual separation trajectory
```

These are demo assumptions, not universal cosmetic laws.

### 6.5 LLM boundary

The teacher LLM may generate only:

- journal titles;
- researcher observation phrasing;
- short lesson-learned text;
- natural-language query variants;
- explanation drafts constrained by structured values.

The teacher LLM must never generate:

- pH values;
- viscosity values;
- failure weeks;
- final labels;
- concentration values;
- regulatory decisions.

---

## 7. F1: Evidence Research Copilot

### 7.1 Role

F1 finds historical trial evidence, including failure patterns, and exposes evidence coverage. It does not make the stability forecast itself.

### 7.2 Retrieval pipeline

```text
Natural-language query
  → product/ingredient/failure-mode normalization
  → access control filter
  → parallel lexical retrieval + dense retrieval + metadata filters
  → reciprocal-rank fusion / reranking
  → evidence sufficiency gate
  → grounded summary with source cards
```

### 7.3 Structured F1 output

```json
{
  "query_id": "Q-2026-014",
  "normalized_context": {
    "product_family": "o_w_gel_cream_moisturizer",
    "target_skin": "oily",
    "target_problem": "oil_control",
    "failure_mode": "viscosity_collapse"
  },
  "evidence_status": "sufficient",
  "related_cases": [
    {
      "source_id": "J-2025-044-T02",
      "relevance": 0.89,
      "outcome": "failed",
      "failure_mode": "viscosity_collapse",
      "data_origin": "synthetic_demo"
    }
  ],
  "summary_for_user": "...",
  "limitations": [
    "Demo evidence is scenario-based synthetic data."
  ]
}
```

### 7.4 F1 to F3 integration rule

F1 source IDs and failure patterns are stored as evidence references. F1 prose and raw relevance scores do **not** enter the numerical F3 feature vector.

This prevents the predictive model from depending on unstable RAG behavior or leaking final outcomes through retrieval.

### 7.5 Acceptance criteria

- Exact ingredients, aliases, and trial IDs are retrievable.
- Paraphrased natural-language queries retrieve relevant trials in top-5.
- Every factual sentence includes an evidence card/source ID.
- Insufficient evidence produces abstention.
- Restricted evidence never reaches the candidate set or LLM prompt.

---

## 8. F2: Deterministic Formulation Guardrail

### 8.1 Role

F2 validates formula inputs and emits a stable feature snapshot for F3. F2 is not a regulatory approval engine.

### 8.2 Pipeline

```text
Ingredient input
  → alias / INCI normalization
  → concentration and schema validation
  → compatibility rules
  → pH / emulsifier / electrolyte checks
  → regulatory and supplier-document screening
  → warnings, actions, feature snapshot, audit event
```

### 8.3 F2 output contract

```json
{
  "formula_version_id": "FORM-2026-001-V2",
  "feature_schema_version": "stability-sentinel-v1",
  "derived_features": {
    "oil_phase_ratio": 0.11,
    "electrolyte_load": "high",
    "thickener_sensitivity": "high",
    "emulsifier_balance_status": "watch",
    "ph_compatibility_margin": 0.3,
    "ingredient_count": 9,
    "compatibility_warning_count": 1
  },
  "guardrail_results": [
    {
      "rule_id": "COMPAT-017",
      "severity": "warning",
      "source_id": "RULESRC-012",
      "rule_version": "2026.09",
      "requires_human_review": true
    }
  ],
  "model_coverage": {
    "status": "supported_demo_domain",
    "reason": "Formula maps to the O/W gel-cream synthetic feature schema."
  }
}
```

### 8.4 F2 to F3 integration rule

Only canonical formula/process features and deterministic derived features enter F3. A raw warning message does not become an input feature. The feature schema must be versioned and identical during model training and inference.

### 8.5 Safe statuses

| Status | Meaning |
|---|---|
| `clear_for_current_screening` | No available prototype rule was triggered, not final approval |
| `warning` | Risk or evidence gap exists |
| `blocked_by_rule` | Explicit prototype constraint is violated |
| `unknown` | Insufficient data, human review required |

---

## 9. F3: Predictive Stability Sentinel

### 9.1 Product promise

> **F3 uses early formula and checkpoint signals to estimate the risk that a batch will fail before week 12. It prioritizes researcher attention and earlier reformulation. It does not replace formal stability validation.**

### 9.2 Two F3 modes

#### Mode A: pre-trial risk context

Before lab execution, F3 can expose F2-derived risk context:

```text
High electrolyte-thickener risk detected.
The model cannot make a long-horizon forecast until checkpoints exist.
Recommended action: record baseline measurements and follow the stability test plan.
```

This is not a model probability yet.

#### Mode B: longitudinal early-risk forecast

After sufficient observations, F3 predicts:

```text
P(failure by week 12 | formula, process, data observed through current week)
```

At minimum, require baseline plus one post-baseline checkpoint. For the strongest MVP forecast, use data through week 4.

### 9.3 F3 feature vector

```json
{
  "feature_schema_version": "stability-sentinel-v1",
  "formula_features": {
    "oil_phase_ratio": 0.11,
    "electrolyte_load": "high",
    "thickener_sensitivity": "high",
    "emulsifier_balance_status": "watch",
    "final_ph": 5.7
  },
  "process_features": {
    "heating_temp_c": 75,
    "homogenization_rpm": 2500,
    "mixing_time_min": 15
  },
  "trend_features_at_week_4": {
    "viscosity_baseline_cp": 15000,
    "viscosity_current_cp": 12100,
    "viscosity_change_pct": -19.33,
    "viscosity_slope_per_week": -725,
    "ph_baseline": 5.6,
    "ph_current": 5.93,
    "ph_change": 0.33,
    "appearance_warning_count": 1,
    "storage_temperature_c": 40
  }
}
```

### 9.4 MVP model

Use a transparent tabular baseline before deep time-series models:

1. Logistic Regression baseline;
2. Random Forest baseline;
3. XGBoost or LightGBM candidate model;
4. calibration step if probabilities are shown;
5. SHAP or feature-contribution explanation for the chosen model.

An LSTM, GRU, TCN, or Transformer is not part of the MVP. The dataset contains 600 scenario trajectories, so engineered trend features are more appropriate and explainable.

### 9.5 F3 output contract

```json
{
  "trial_id": "J-2026-001-T02",
  "forecast_week": 4,
  "forecast_horizon": "week_12",
  "prediction_type": "synthetic_demo_early_risk_forecast",
  "failure_risk": 0.78,
  "risk_band": "high",
  "likely_failure_mode": "viscosity_collapse",
  "confidence": "medium",
  "key_signals": [
    {
      "feature": "viscosity_change_pct",
      "value": -19.33,
      "interpretation": "Viscosity declined materially from baseline."
    },
    {
      "feature": "electrolyte_thickener_risk",
      "value": "high",
      "source": "COMPAT-017"
    }
  ],
  "evidence_ids": ["J-2025-044-T02", "J-2025-102-T01"],
  "recommended_action": "Request formulator review before continuing to the next test cycle.",
  "limitations": [
    "Forecast is trained and evaluated on scenario-based synthetic demo data.",
    "It does not replace formal stability validation."
  ],
  "model_version": "stability-sentinel-xgb-v1"
}
```

### 9.6 F1, F2, F3 responsibility boundary

```text
F2:
Normalizes formula and states deterministic risks.

F3:
Forecasts risk from F2 features plus observed checkpoint trends.

F1:
Finds the historical cases and evidence cards that explain why the F3 warning deserves attention.
```

### 9.7 F3 safe fallback

| Condition | Behavior |
|---|---|
| No post-baseline checkpoint | Show test plan, no forecast |
| Unsupported formula domain | Show `unsupported_domain`, no probability |
| Missing critical measurement | Show `insufficient_observation`, request missing field |
| Contradictory signals | Lower confidence and request human review |
| Model unavailable | Show deterministic trend deltas and F1 evidence only |

---

## 10. F5: Voice-to-Structured Logging

### 10.1 Pipeline

```text
Push-to-talk audio
  → local speech-to-text
  → ingredient alias and number normalization
  → structured extraction
  → JSON/range validation
  → confidence per field
  → user confirmation
  → journal write and audit event
```

### 10.2 F5 output must target canonical fields

```json
{
  "trial_id": "J-2026-001-T02",
  "proposed_checkpoint_patch": {
    "measurements": {
      "ph": 5.93,
      "viscosity_cp": 12100
    },
    "observations": {
      "appearance": "slightly_nonuniform"
    }
  },
  "field_confidence": {
    "ph": 0.97,
    "viscosity_cp": 0.91,
    "appearance": 0.78
  },
  "requires_confirmation": true
}
```

F5 must not write directly to F3. It updates the canonical checkpoint after user confirmation. F3 runs only after the checkpoint is valid.

---

## 11. F3 Image Attachment, Not CV Prediction

F3 still accepts images as evidence attached to a stability checkpoint.

```text
Image upload
  → image quality check
  → object storage
  → attach to checkpoint timeline
  → human observation
```

The MVP may check blur, exposure, and framing, but it must not claim to classify phase separation unless a properly validated visual model is later activated.

UI label:

> **Visual evidence capture. AI visual screening is pending domain validation.**

---

## 12. Dataset Generation and Corpus Generation

### 12.1 Generation order

```text
1. Ingredient master and rule KB
2. Structured formula/process seeds
3. Numeric stability trajectories and final outcomes
4. Synthetic journal metadata
5. LLM-generated narrative fields constrained by seeds
6. F1 query variants and synthetic voice transcripts
7. Embedding/index creation
8. Train/validation/test split by trial family
```

### 12.2 Required split discipline

Never split checkpoint rows randomly. All timepoints from one trial must remain in one partition.

```text
Train: trial families A–N
Validation: separate trial families
Test: separate trial families and human-authored queries
```

This prevents the model from seeing the same latent trajectory in train and test.

### 12.3 Dataset records

Recommended files:

```text
data/
├── ingredient_master.json
├── formulation_rules.json
├── formula_seeds.jsonl
├── trial_trajectories.jsonl
├── checkpoints.jsonl
├── final_outcomes.jsonl
├── evidence_corpus.jsonl
├── rag_dev_queries.jsonl
├── rag_blind_test_queries.jsonl
└── metadata.json
```

### 12.4 Synthetic-data guardrail

All synthetic UI content and API responses include a hidden machine-readable field and an available user-visible disclaimer. The demo script must say that the prototype uses scenario-based synthetic data because Paragon's historical formulation data is proprietary and unavailable to participants.

---

## 13. Evaluation

### 13.1 F1 evaluation

| Metric | Requirement |
|---|---|
| Recall@5 | Relevant evidence is retrieved in top 5 |
| MRR@5 or nDCG@5 | Relevance ranking quality |
| Citation precision | Claims map to source IDs |
| Unsupported-claim rate | Must be measured |
| Correct abstention rate | Must be measured |
| Permission leakage | Must be zero in access-control tests |

### 13.2 F2 evaluation

| Test | Requirement |
|---|---|
| Rule determinism | Same input produces same output |
| Alias normalization | Ambiguous cases request confirmation |
| Source provenance | Every warning includes rule/source/version |
| Override audit | Human overrides are stored |

### 13.3 F3 evaluation

Evaluate retrospective forecasts at a fixed landmark, such as week 4.

```text
Input: formula/process + week 0–4 checkpoints
Target: final pass/fail outcome by week 12
```

| Metric | Why it matters |
|---|---|
| Recall for failed trials | High-risk batches should not be missed |
| False-negative rate | Most costly forecasting failure |
| Precision for high-risk alert | Avoid stopping healthy trials too often |
| PR-AUC / ROC-AUC | Classification discrimination |
| Brier score / calibration curve | Whether displayed probability is meaningful |
| Lead-time proxy | Whether warnings occur before final failure |
| Coverage/abstention rate | Whether model admits unsupported situations |

Every reported metric must say `synthetic-demo evaluation`, not production validation.

### 13.4 F5 evaluation

- ingredient normalization accuracy;
- exact concentration extraction accuracy;
- pH extraction accuracy;
- unsafe auto-fill rate;
- confirmation correction rate;
- latency.

---

## 14. Security, Privacy, and Auditability

### 14.1 Access control

Apply permission filtering before lexical retrieval, vector retrieval, reranking, and prompt construction.

| Visibility level | Access |
|---|---|
| Private | Named researcher only |
| Team | Project team members |
| Cross-team summary | Aggregated lesson, no formula detail |
| Restricted | Explicit role and approval |

### 14.2 Audit events

Store:

- input formula version;
- F2 rules triggered and rule versions;
- F3 feature-schema/model version;
- checkpoint IDs used in each forecast;
- F1 evidence source IDs;
- generated output;
- user corrections, acceptance, override, and sign-off.

### 14.3 Privacy boundary

Synthetic demo data may use external teacher APIs only if it contains no proprietary or personal information. Future internal Paragon data requires an approved private environment.

---

## 15. Demo Flow

### Three-minute primary story

1. Researcher enters an oily-skin gel-cream brief.
2. F1 retrieves two relevant prior trials, including a delayed viscosity-collapse case.
3. Researcher creates a formula based on the journal context.
4. F2 flags an electrolyte-thickener risk and stores a normalized formula snapshot.
5. Researcher records a week-4 checkpoint by voice, then confirms parsed pH, viscosity, and observation.
6. F3 detects an early downward viscosity trend, forecasts elevated week-12 failure risk, and states its synthetic-demo limitation.
7. F1 opens historical evidence cards supporting the warning.
8. Researcher requests review/reformulation instead of waiting for the final test window.

### Judge-facing statement

> FormuLab does not replace formal stability testing. It brings the go/no-go decision forward for high-risk batches by combining structured formula constraints, early measurement trends, and institutional evidence. The prototype validates this workflow on a clearly labelled scenario-based dataset and is designed to retrain on Paragon historical stability trajectories.

---

## 16. Definition of Done

### Core data

- [ ] 200 projects, 600 trials, and 4,200 checkpoint records generated.
- [ ] All numeric values come from a seeded trajectory generator.
- [ ] Every synthetic record is labelled with provenance.
- [ ] Train/validation/test split is by trial family.

### F1

- [ ] Hybrid lexical+dense retrieval works.
- [ ] Evidence cards with source IDs are shown.
- [ ] Insufficient evidence abstains.
- [ ] Synthetic source status is shown.

### F2

- [ ] Ingredient aliases normalize to canonical IDs.
- [ ] Deterministic rules return source/versioned warnings.
- [ ] A versioned F3 feature snapshot is emitted.
- [ ] Human override is audited.

### F3

- [ ] Inputs use only versioned F2 features and verified checkpoints.
- [ ] Week-4 forecast runs against week-12 outcome labels.
- [ ] Output includes risk, confidence, signals, action, evidence IDs, and limitation.
- [ ] Unsupported/missing-data cases abstain.
- [ ] Evaluation is labelled synthetic-demo.

### F5

- [ ] Voice extraction proposes structured checkpoint updates.
- [ ] User confirmation is mandatory before writing.
- [ ] F3 only runs after valid checkpoint storage.

---

## 17. Deferred Roadmap

1. Replace synthetic trajectories with permissioned Paragon historical stability data.
2. Calibrate F3 against true product-family-specific failure labels.
3. Add survival analysis or dynamic landmark models for time-to-failure.
4. Add active-learning recommendations for the next measurement or trial.
5. Add validated visual instability classification after a domain-appropriate labeled image dataset is obtained.
6. Expand from O/W gel-cream to other product families only after model coverage tests.

---

## 18. Final Architecture Decision

FormuLab v4 chooses **one coherent end-to-end demo universe** rather than several disconnected models:

```text
Synthetic O/W gel-cream formulation trajectories
    ↓
F1 retrieves structured historical evidence
    ↓
F2 creates a deterministic and versioned feature snapshot
    ↓
F3 forecasts week-12 failure risk from early checkpoints
    ↓
F5 captures valid observations that update the forecast
    ↓
Human review owns every consequential decision
```

This architecture demonstrates the real product loop without pretending that synthetic data provides production-grade cosmetic stability validation.
