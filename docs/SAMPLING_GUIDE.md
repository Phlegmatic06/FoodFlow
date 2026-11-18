# NutriPod — Unified Dataset Sampling & Development Data Preparation Guide

This technical guide specifies the architectural design, mathematical formulation, stratification taxonomy, and CLI workflows for the **NutriPod Unified Sampling Engine** (`ingestion/sampling/`), implemented in **Phase 1 (Step 03.5)**.

---

## 1. Why Stratified Sampling is Needed

NutriPod is designed as a broad, general-purpose culinary and nutrition planning platform. The full upstream dataset distributions represent millions of records:
- **Food.com Recipes and Interactions**: ~231,637 recipes and ~1.1M community interaction ratings.
- **RecipeNLG Corpus**: ~2,231,142 recipes (~2.2 GB raw CSV).
- **USDA FoodData Central (FDC)**: ~8,000 reference foods across Foundation Foods and SR Legacy.

For rapid local developer bootstrapping, continuous integration (CI) test runs, and laptop deployment, developers require a compact, highly representative **development catalogue**:
- **Target Size**: Exactly **25,000 Food.com recipes** + **25,000 RecipeNLG recipes** (~50,000 total recipes).
- **Storage Goal**: $< 1.2 \text{ GB}$ total PostgreSQL database footprint.
- **Build Time Goal**: $< 5 \text{ minutes}$ for a fresh dev database seed.

### Failure of Naive Truncation (Top-N Sampling)
A naive approach such as `head -n 25000` or `LIMIT 25000` severely degrades data quality and feature coverage:
1. **Temporal Clustering**: Scraping dumps are often ordered chronologically or by author ID. The first 25,000 rows might originate exclusively from 1999–2001 or from a small handful of power contributors.
2. **Category Starvation**: Niche or specialized culinary strata (e.g., breakfast dishes, beverages, quick weeknight meals under 15 minutes, or recipes with rich NER entity sets) may be severely under-represented or completely absent.
3. **Broken Referential Integrity**: Naively taking the first 25,000 interaction rows from `RAW_interactions.csv` would result in $95\%+$ "ghost reviews" whose referenced `recipe_id` does not exist in the recipe subset.

Stratified sampling solves this by dividing the population into non-overlapping culinary and structural strata, guaranteeing that each stratum receives proportional representation with minimum guaranteed representation for small categories.

---

## 2. Why USDA FoodData Central is NOT Randomly Sampled

The USDA dataset (`profile_nutrition` schema) serves as the **foundational nutritional reference dictionary** for NutriPod:
- It defines standardized macro- and micronutrients per 100g for base commodity ingredients (flours, milks, cooking oils, vegetables, meats, spices).
- If base USDA ingredients were randomly subsampled (e.g., keeping only $10\%$ of foods), recipes in `recipe_catalog` referencing everyday staples (such as "onion", "butter", or "salt") would fail ingredient matching, breaking caloric calculation.
- **Policy**: NutriPod ingests **100% of USDA Foundation Foods and SR Legacy collections** without subsampling. Because the USDA reference dictionary is relatively compact (~8,000 foods and ~500,000 nutrient records), it easily fits within the $< 1.2 \text{ GB}$ local development budget.

---

## 3. Food.com Stratified Sampling Engine

### 3.1 Taxonomy and Tag Mappings
Food.com tags provide rich contextual information. The sampling engine maps raw tags into 7 broad culinary groups using explicit, curated mappings:

| Category | Representative Source Tags |
|---|---|
| **Breakfast** | `breakfast`, `brunch`, `pancakes`, `waffles`, `cereal`, `omelets-and-frittatas`, `french-toast`, `crepes`, `muffins`, `eggs-breakfast` |
| **Lunch** | `lunch`, `sandwiches`, `wraps`, `salads`, `salads-main-dish`, `soups-stews`, `chili`, `soup`, `lunchbox`, `cold-lunches`, `panini`, `quiche` |
| **Dinner / Main Meals** | `dinner`, `main-dish`, `entrees`, `steaks`, `pasta`, `casseroles`, `poultry`, `meat`, `beef`, `chicken`, `pork`, `seafood`, `fish`, `roast`, `stews`, `one-dish-meal`, `curries` |
| **Dessert & Baking** | `desserts`, `baking`, `cookies-brownies`, `cakes`, `pies`, `tarts`, `cupcakes`, `cheesecake`, `puddings-mousses`, `candy`, `pastry`, `breads`, `cobblers`, `ice-cream` |
| **Snacks & Appetizers** | `appetizers`, `snacks`, `finger-food`, `dips-spreads`, `canapes`, `wings`, `nachos`, `chips`, `popcorn`, `snack-mixes`, `nuts-seeds` |
| **Beverages** | `beverages`, `drinks`, `smoothies`, `cocktails`, `coffee-tea`, `tea`, `coffee`, `punch`, `shakes-floats`, `lemonade`, `cider`, `mocktails` |
| **Other / Unclassified** | Fallback for recipes without matching curated category tags |

### 3.2 Deterministic Primary Stratum Assignment
Because a recipe can have dozens of tags (e.g., a recipe tagged both `dinner` and `desserts`), the engine applies a strict **deterministic category precedence order**:
$$\text{Breakfast} \longrightarrow \text{Lunch} \longrightarrow \text{Dinner} \longrightarrow \text{Dessert} \longrightarrow \text{Snack} \longrightarrow \text{Beverage} \longrightarrow \text{Other}$$
The first matching category is selected as the primary category. No record is ever counted in multiple categories.

### 3.3 Cooking Time Buckets
To guarantee diversity across quick weeknight meals and slow-cooked roasts, recipes are further partitioned by source preparation time (`minutes`):
- `time_lte_15`: $\le 15$ minutes (quick prep/snacks)
- `time_16_30`: $16–30$ minutes (fast weeknight meals)
- `time_31_60`: $31–60$ minutes (standard cooking duration)
- `time_gt_60`: $> 60$ minutes (braises, roasts, slow cooking)
- `time_unknown`: Missing, $\le 0$, unparseable, or $> 43,200$ minutes (sentinel threshold)

**Composite Stratum Identifier**: `{category}__{time_bucket}` (e.g., `dinner__time_16_30`, `breakfast__time_lte_15`).

### 3.4 Unique Recipe ID Enforcement
To ensure strict uniqueness in development datasets:
- **Pass 1 Validation**: Observed recipe IDs are tracked during Pass 1. Any record with a duplicate recipe ID is immediately rejected and recorded in `rejected_rows` with a descriptive message (`Duplicate recipe id: {id}`).
- **Pass 2 Reservoir Writes**: Pass 2 maintains a `seen_ids` deduplication set during reservoir writes. Any duplicate recipe ID encountered is skipped, guaranteeing 100% unique recipe IDs in output `RAW_recipes.csv`.

---

## 4. Food.com Referential Interaction Filtering

A core requirement of the development seed is that historical ratings and reviews in `RAW_interactions.csv` must directly belong to selected recipes:

```
+─────────────────────────────────────────────────────────────────────────────────+
|               FOOD.COM REFERENTIAL INTERACTION FILTERING FLOW                   |
+─────────────────────────────────────────────────────────────────────────────────+
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
       [RAW_recipes.csv Stream]                [RAW_interactions.csv Stream]
                    │                                       │
     Pass 1 & 2 Reservoir Sampling                          │
                    │                                       │
                    ▼                                       │
       [Selected 25,000 Recipes]                            │
                    │                                       │
                    ▼                                       │
      selected_recipe_ids (Set[str])                        │
      Capped at 25,000 IDs (~1.5 MB RAM)                    │
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                         For each interaction record:
                      is interaction.recipe_id in set?
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
                     [YES]                            [NO]
               Write to output                  Discard record
            RAW_interactions.csv           (Zero ghost interactions)
```

### Referential Integrity Guarantees:
1. **Zero Random Interaction Subsampling**: All interaction rows matching selected recipes are retained. Interactions are not randomly discarded.
2. **Zero Unmatched Recipes**: No interaction record is retained whose `recipe_id` is missing from the sampled recipes.
3. **Preserved Raw Format**: The output `RAW_interactions.csv` preserves the exact original column structure (`user_id`, `recipe_id`, `date`, `rating`, `review`) without schema rewriting.
4. **Memory Bounded**: The recipe ID set is bounded by the target sample limit ($M = 25,000$ strings, $\approx 1.5 \text{ MB}$ RAM). The interaction stream is evaluated in $O(1)$ memory.

---

## 5. RecipeNLG Stratified Sampling Engine

The RecipeNLG corpus does not contain curated cuisine tags or cooking times. To prevent artificial fabrication, stratification relies exclusively on authentic structural attributes available in `full_dataset.csv`.

### 5.1 Stratification Dimensions
1. **Sub-Corpus Source Origin**:
   - `Gathered`: Recipes mined by Bień et al. across independent culinary web sources (source column value `gathered` or encoded label `1`).
   - `Recipes1M`: Recipes originating from the MIT CSAIL Recipe1M+ collection (source column value `recipes1m`, `recipe1m`, or encoded label `0`).
   - `Unknown`: Unrecognized, non-standard, or missing source column values.
   > [!IMPORTANT]
   > Source origin is derived strictly and exclusively from the original `source` column. The sampling engine never infers, correlates, or substitutes provenance based on recipe IDs. Original recipe IDs are preserved independently.
2. **NER Entity Richness**:
   Named Entity Recognition token availability indicates ingredient tokenization density:
   - `ner_0`: Missing, empty, or unparseable NER tokens ($0$ entities).
   - `ner_1_3`: 1 to 3 ingredient entities (minimalist recipes).
   - `ner_4_8`: 4 to 8 ingredient entities (standard recipes).
   - `ner_gt_8`: $> 8$ ingredient entities (complex, multi-ingredient dishes).
3. **Directions Availability**:
   - `directions_usable`: Valid non-empty cooking instruction steps.
   - `directions_empty`: Empty instruction array `[]` or missing instructions.

**Composite Stratum Identifier**: `{source_origin}__{ner_richness}__{directions_status}` (e.g., `Gathered__ner_4_8__directions_usable`).

### 5.2 Archive Compatibility & Header Normalization
The downloaded RecipeNLG archive (`data/raw/recipenlg/archive.zip`) packages the dataset as `RecipeNLG_dataset.csv` with a header structure originating from pandas `to_csv(index=True)`:
```python
['', 'title', 'ingredients', 'directions', 'link', 'source', 'NER']
```
To process this directly without extracting or mutating the 2.29 GB raw archive:
1. **Dynamic Member Resolution**: `RecipeNLGSource` resolves `full_dataset.csv` queries to the internal member `RecipeNLG_dataset.csv` automatically.
2. **Column 0 ID Recognition**: An empty header `""` or `Unnamed: 0` at index 0 is recognized as the recipe ID column when values validate as non-negative integers.
3. **Empty Header Guard**: Empty headers at any column index $> 0$ are strictly rejected to prevent silent parsing errors.
4. **Sequential ID & Zero Preservation**: Original integer IDs (`0` through `2231141`) are preserved verbatim. Row 0 has ID 0 (`rcp_nlg_0`) and is never shifted or substituted.

---

## 6. Proportional Quota Allocation & Reservoir Sampling

The engine uses a **two-pass streaming algorithm** combining the Hamilton-Hare Largest Remainder Method with Algorithm R reservoir sampling.

### Mathematical Formulation

Let:
- $N$ be the total valid population in the source file: $N = \sum_{s=1}^K N_s$
- $N_s$ be the count of records in stratum $s$
- $M$ be the target sample limit (e.g., $M = 25,000$)
- $n_s$ be the integer sample quota allocated to stratum $s$

#### 1. Census & Share Calculation (Pass 1)
If $N \le M$, the engine sets $n_s = N_s$ for all $s$ (full census).
Otherwise, for each active stratum where $N_s > 0$:
$$q_s = M \times \frac{N_s}{N}$$
$$\text{base}_s = \min\left(N_s, \max\left(1, \lfloor q_s \rfloor\right)\right)$$
$$\text{remainder}_s = q_s - \lfloor q_s \rfloor$$

#### 2. Surplus & Deficit Adjustment (Hamilton-Hare Largest Remainder)
To ensure 100% determinism independent of Python dictionary key ordering:
- Active strata are sorted deterministically before allocation.
- In edge cases where target sample size $M < K$ (where $K$ is the number of active strata with population $\ge 1$), each of the top $M$ largest strata by population receives a quota of 1 (tied by stratum ID), while all other strata receive 0.
- When $M \ge K$, every active stratum with population $\ge 1$ receives at least 1 quota slot ($\text{base}_s = \min(N_s, \max(1, \lfloor q_s \rfloor))$).
- If $\sum \text{base}_s < M$, remaining slots are awarded by largest remainder $\text{remainder}_s = q_s - \lfloor q_s \rfloor$ (tied by larger stratum population, then stratum ID).
- If $\sum \text{base}_s > M$ (due to minimum quota guarantees across many small strata), surplus slots are decremented from the largest quotas with $n_s > 1$ (tied by stratum ID).
- **Mathematical Invariant**: $\sum_{s=1}^K n_s = \min(M, N)$, with $0 \le n_s \le N_s$ for all strata.

#### 3. Independent Reservoir Sampling (Pass 2)
In Pass 2, the source stream is read a second time. Each stratum $s$ maintains an independent reservoir of capacity $n_s$.
When record $k$ of stratum $s$ is processed ($1$-indexed):
- If $k \le n_s$: Insert record into `reservoir[k - 1]`.
- If $k > n_s$: Generate pseudo-random integer $j \in [0, k - 1]$. If $j < n_s$, replace `reservoir[j]` with the record.

**Proof of Uniformity**: By induction on $k$, every record in stratum $s$ has an identical probability $P = \frac{n_s}{N_s}$ of being retained in the final reservoir.

#### 4. Deterministic Cross-Process PRNG Seeding
Python's built-in `hash()` function is non-deterministic across independent processes due to randomized per-process SipHash seeding (`PYTHONHASHSEED`). To guarantee absolute cross-process and cross-platform determinism:
- The stratum seed is derived using the first 8 bytes of a cryptographic SHA-256 hash of the canonical stratum identifier string:
$$\text{sha\_int} = \text{int.from\_bytes}(\text{SHA256}(s)[:8], \text{"big"})$$
$$\text{seed}_s = (S \times 1,000,003 + \text{sha\_int}) \pmod{2^{31} - 1}$$
- This guarantees that independent Python processes running under different environments (or different `PYTHONHASHSEED` configurations, including `PYTHONHASHSEED="random"`) produce byte-for-byte identical output files for any given user seed $S$.

---

## 7. Memory & Performance Characteristics

| Operation | Memory Complexity | Time Complexity | Notes |
|---|---|---|---|
| **Pass 1 (Census)** | $O(K)$ where $K \approx 35$ strata | $O(N)$ row iterations | Validates records, updates stratum counts. No records stored. |
| **Pass 2 (Reservoir)** | $O(M)$ where $M = 25,000$ | $O(N)$ row iterations | Maximum 25,000 row dicts stored in RAM ($\approx 15 \text{ MB}$). |
| **Pass 3 (Interactions)** | $O(M)$ selected recipe IDs | $O(I)$ where $I \approx 1.1\text{M}$ | Hash set lookup in $O(1)$ time per row. Streaming output write. |

- **No 2.23-Million-Row Lists**: The entire 2.2 GB RecipeNLG dataset is never read into a Python list. Memory consumption remains strictly bounded under $50 \text{ MB}$ RSS across all sampling phases.
- **Direct ZIP Streaming**: Supports reading compressed `.zip` archives directly via `io.TextIOWrapper` without uncompressing multi-gigabyte files to disk.

---

## 8. Directory & Output Structure

Sampled datasets are written to `data/processed/dev_sample/`:

```
data/processed/dev_sample/
├── foodcom/
│   ├── RAW_recipes.csv            # Exactly 25,000 sampled recipes (or available valid)
│   ├── RAW_interactions.csv       # 100% of interactions matching sampled recipe IDs
│   └── sampling_report.json       # Audit provenance, checksums, and stratum breakdown
│
└── recipenlg/
    ├── full_dataset.csv           # Exactly 25,000 sampled recipes (or available valid)
    └── sampling_report.json       # Audit provenance, checksums, and stratum breakdown
```

### Git Hygiene
`data/processed/**` is strictly excluded from version control in `.gitignore`. Only the directory structure `.gitkeep` placeholder is committed.

---

## 9. CLI Usage & Command Reference

The ingestion CLI provides the `sample` subcommand:

```bash
# View command help and available options
python -m ingestion.cli sample --help
```

### 9.1 Food.com Sampling Commands

```bash
# Dry-run: profile strata and calculate quotas without writing files
python -m ingestion.cli sample \
  --dataset foodcom \
  --source data/raw/foodcom \
  --limit 25000 \
  --seed 42 \
  --dry-run

# Execute full development sampling
python -m ingestion.cli sample \
  --dataset foodcom \
  --source data/raw/foodcom \
  --output-dir data/processed/dev_sample/foodcom \
  --limit 25000 \
  --seed 42
```

### 9.2 RecipeNLG Sampling Commands

```bash
# Dry-run on RecipeNLG full dataset or ZIP archive
python -m ingestion.cli sample \
  --dataset recipenlg \
  --source data/raw/recipenlg/full_dataset.csv \
  --limit 25000 \
  --seed 42 \
  --dry-run

# Execute full development sampling
python -m ingestion.cli sample \
  --dataset recipenlg \
  --source data/raw/recipenlg/full_dataset.csv \
  --output-dir data/processed/dev_sample/recipenlg \
  --limit 25000 \
  --seed 42
```

---

## 10. Ingesting Development Samples into PostgreSQL

Once samples have been generated, existing importers consume them directly without transformation:

```bash
# 1. Ingest Food.com development sample (recipes + matching interactions)
python -m ingestion.cli ingest-foodcom \
  --source data/processed/dev_sample/foodcom \
  --component all

# 2. Ingest RecipeNLG development sample
python -m ingestion.cli ingest-recipenlg \
  --source data/processed/dev_sample/recipenlg/full_dataset.csv

# 3. Seed USDA reference nutrition dictionary (full dataset, not sampled)
python -m ingestion.cli ingest-usda \
  --data-type foundation \
  --source data/raw/usda/Foundation_Foods.zip

python -m ingestion.cli ingest-usda \
  --data-type sr-legacy \
  --source data/raw/usda/SR_Legacy.zip
```

---

## 11. Known Limitations & Edge Cases

1. **Unclassified Food.com Tags**: Recipes lacking standard meal-type tags are grouped into the `other` stratum. They are preserved in the sample proportionally rather than discarded.
2. **Missing RecipeNLG Directions**: Approximately $0.5\%$ of RecipeNLG records contain empty directions `[]`. The sampler isolates them in the `directions_empty` stratum, ensuring that the development catalogue is not flooded with instruction-less dishes.
3. **Interaction Coverage**: If a sampled Food.com recipe has 0 historical reviews in `RAW_interactions.csv`, its rating columns in PostgreSQL will be recorded as NULL upon ingestion, which is handled gracefully by the catalog service.

