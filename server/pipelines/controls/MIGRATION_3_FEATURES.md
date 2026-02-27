# Migration Guide: 6 Features → 3 Semantic Features

## What Changed

The controls pipeline moved from 6 raw text features to 3 LLM-extracted semantic features. This affects model runners, schema, Qdrant, similarity, search, and the client.

---

## Before → After Summary

| Area | Before | After |
|---|---|---|
| **Features** | `control_title`, `control_description`, `evidence_description`, `local_functional_information`, `control_as_event`, `control_as_issues` | `what`, `why`, `where` (from enrichment `_details` columns) |
| **Model stage name** | `clean_text` | `feature_prep` |
| **DB table** | `ai_controls_model_clean_text` | `ai_controls_model_feature_prep` |
| **Hashes** | 6 (`hash_control_title`, ..., `hash_control_as_issues`) | 3 (`hash_what`, `hash_why`, `hash_where`) |
| **Masks** | 2-pass parent comparison per feature | Simple: L1 Active Key = `True`, everything else = `False` |
| **Qdrant vectors** | 6 named vectors per point | 3 (`what`, `why`, `where`) |
| **Qdrant scope** | All controls | L1 Active Key only |
| **Similarity algorithm** | `0.6*cosine + 0.4*jaccard` with duplicate cap, diversity bonus | `(embedding_cosine + tfidf_cosine) / 2` per feature, averaged |
| **Similarity scope** | All controls | L1 Active Key only |
| **Top-K** | 4 | 3 |
| **Similarity categories** | None | `near_duplicate` (>=0.90), `weak_similar` (0.60-0.89) |
| **Keyword FTS fields** | 6 tsvector columns | 7: `ts_control_title`, `ts_control_description`, `ts_what`, `ts_why`, `ts_where`, `ts_evidence_description`, `ts_local_functional_information` |
| **Enrichment output** | Included `control_as_event`, `control_as_issues` | Removed. Added `roles`, `process`, `product`, `service` narrative fields |
| **New dependency** | — | `scikit-learn>=1.4` (TF-IDF) |

---

## File-by-File Changes

### common.py
`FEATURE_NAMES` changed from 6 to 3:
```python
# Before
FEATURE_NAMES = ["control_title", "control_description", "evidence_description",
                  "local_functional_information", "control_as_event", "control_as_issues"]
# After
FEATURE_NAMES = ["what", "why", "where"]
```
`HASH_COLUMN_NAMES` and `MASK_COLUMN_NAMES` auto-derive from `FEATURE_NAMES`, so they become `hash_what`, `mask_what`, etc.

### run_enrichment_mock.py
- Removed `control_as_event` and `control_as_issues` from `ENRICHMENT_FIELDS` and all payload builders
- `what_details`, `why_details`, `where_details` now populated with meaningful text (from dataset pool or derived from source fields)
- Added `roles`, `process`, `product`, `service` narrative fields
- Added `_inject_similarity_clusters()` for testing — injects 48 controls with shared text (24 near-duplicate, 24 weak-similar)

### run_feature_prep_mock.py (was run_clean_text_mock.py)
- **Renamed** from `run_clean_text_mock.py`
- `MODEL_NAME = "feature_prep"` (was `"clean_text"`)
- No text cleaning — LLM output is already clean
- Reads `what_details`, `why_details`, `where_details` from enrichment output
- Mask logic simplified: `True` if L1 + Active + Key Control and text is non-empty, `False` otherwise
- Passes through `control_title`, `control_description`, `evidence_description`, `local_functional_information` for keyword FTS (not embedded)

### run_embeddings_mock.py
- `EMBEDDING_FIELDS` changed from 6 to 3: `what_embedding`, `why_embedding`, `where_embedding`
- NPZ output has 3 arrays instead of 6
- References `feature_prep` instead of `clean_text`

### schema.py
- Table renamed: `ai_controls_model_clean_text` → `ai_controls_model_feature_prep`
- Old columns dropped: 6 text, 6 hash, 6 tsvector columns for old features
- New columns: `what`, `why`, `where`, `hash_what`, `hash_why`, `hash_where`, plus 7 tsvector columns
- Keyword FTS columns retained: `control_title`, `control_description`, `evidence_description`, `local_functional_information`
- Trigger/function renamed: `update_feature_prep_tsvectors` / `trg_feature_prep_tsvectors`
- `ai_controls_similar_controls`: added `category` column (Text, nullable)

### qdrant_service.py
- `NAMED_VECTORS` changed from 6 to 3: `["what", "why", "where"]`
- Payload uses `hash_what`, `mask_what`, etc.
- Collection must be recreated (drop + create) since vector count changed

### similarity.py
- **Algorithm**: TF-IDF cosine + embedding cosine, averaged per feature, averaged across 3 features
- **Scope**: L1 Active Key controls only (loads `hierarchy_level`, `control_status`, `key_control` from ver_control)
- **Top-K**: 3 (was 4)
- **Thresholds**: >= 0.90 = `near_duplicate`, 0.60-0.89 = `weak_similar`, < 0.60 = discarded
- **New dependency**: `TfidfVectorizer` from scikit-learn
- **Event loop fix**: `await asyncio.sleep(0)` added periodically in CPU-bound loops to prevent blocking
- Writes `category` column to DB
- Old constants removed: `DUP_THRESHOLD`, `DUP_CAP_SCORE`, `SEMANTIC_WEIGHT`, `KEYWORD_WEIGHT`, `DIVERSITY_BONUS`

### ingest/service.py
- Import: `ai_controls_model_feature_prep` (was `ai_controls_model_clean_text`)
- Variables renamed: `feature_prep_rows`, `existing_feature_prep_hashes`, etc.
- Loads `feature_prep` model output (was `clean_text`)
- Row building uses new column names: `what`, `why`, `where`, `hash_what`, etc.

### readiness.py
- Model check: `{"name": "feature_prep"}` (was `"clean_text"`)

### storage.py / settings.py
- Directory: `model_runs/feature_prep` (was `model_runs/clean_text`)

---

## Server Explorer Changes

### shared/models.py
- `SEMANTIC_FIELD_NAMES = ["what", "why", "where"]`
- `KEYWORD_FIELD_NAMES = ["control_title", "control_description", "what", "why", "where", "evidence_description", "local_functional_information"]`
- `SimilarControlResponse`: added `category: str | None`
- `AIEnrichmentDetailResponse`: added `roles`, `process`, `product`, `service` fields
- `AIEnrichmentResponse` / `AIEnrichmentDetailResponse`: `control_as_event` and `control_as_issues` still present for backward compat but no longer populated by new enrichment runs

### controls/service.py
- Import alias: `ai_controls_model_feature_prep as ai_feature_prep`
- Search queries reference new tsvector column names
- Semantic search uses 3 named vectors
- Detail endpoint loads `roles`, `process`, `product`, `service` from enrichment

---

## Client Changes

### types.ts
- `SEMANTIC_FEATURES`: 3 features (`what`, `why`, `where`)
- Added `KEYWORD_FIELDS`: 7 fields with L1/L2 grouping
- `SimilarControl`: added `category?: string | null`
- `AIEnrichmentDetail`: added `roles`, `process`, `product`, `service`
- `ReadinessInfo`: `feature_prep` (was `clean_text`)

### ControlsSearchBar.tsx
- Semantic mode: 3 feature checkboxes
- Keyword mode: 7 field checkboxes grouped by L1/L2

### AITab.tsx
- New "Narratives" section showing `roles`, `process`, `product`, `service`

### LinkedControlCard.tsx / ControlCardAI.tsx
- Category badges: `near_duplicate` → red badge, `weak_similar` → amber badge

### Processing.tsx
- Model label: `feature_prep: 'Feature Prep'` (was `clean_text: 'Clean Text'`)

### explorerApi.ts
- `ApiSimilarControl`: added `category: string | null`

---

## Alembic Migrations

| Migration | What |
|---|---|
| **014** | Drop old 6-feature columns from clean_text, add 3 semantic + 7 FTS columns, add `category` to similar_controls |
| **015** | Rename table `ai_controls_model_clean_text` → `ai_controls_model_feature_prep`, rename constraints/indexes/trigger |

**Note**: asyncpg requires `CREATE FUNCTION` and `CREATE TRIGGER` as separate `op.execute()` calls (cannot combine multiple statements).

---

## Migration Steps for Teams

1. **Add `scikit-learn>=1.4`** to dependencies
2. **Run alembic**: `alembic upgrade head` (applies 014 + 015)
3. **Recreate Qdrant collection**: Drop and recreate with 3 named vectors instead of 6
4. **Re-run model pipeline**: enrichment → feature_prep → embeddings (in order)
5. **Re-ingest**: Full rebuild to populate new schema and similarity
6. **Rename imports** in any custom code: `clean_text` → `feature_prep` everywhere
7. **Update API consumers**: `search_fields` now accepts `what`, `why`, `where` for semantic; 7 fields for keyword
8. **Update UI**: Similar controls now have `category` field; search field checkboxes changed
