# NutriPod — Implementation Roadmap & Delivery Plan

| Metadata | Details |
| :--- | :--- |
| **Document Version** | 1.0.0 |
| **Status** | Approved Project Roadmap (Pre-Implementation) |
| **Team Size** | 3 Engineers (University Project) |
| **Methodology** | Contract-First, Backend-First, Milestone-Gated |

---

## 1. Roadmap Strategy & Team Division

To ensure a smooth, risk-controlled workflow for a 3-person student team, NutriPod adheres to a **Backend-First, Contract-Driven Integration Strategy**:

1. **Shared Foundation (Phase 0)**: Establish database schemas, repository structure, environment standards, and API contracts.
2. **Data Pipeline & Independent Service Builds (Phase 1 & Phase 2)**: Team members develop their respective backend microservices concurrently against shared contracts, using realistic seed data.
3. **Backend Integration & Verification (Phase 3)**: Verify inter-service REST communication and data integrity before writing frontend components.
4. **Editorial Frontend Implementation (Phase 4)**: Build the unified React + Vite application with the strict 0px border-radius editorial design system.
5. **Container Hardening, Compose & Kubernetes Manifests (Phase 5)**: Containerize with Podman multi-stage builds, author `compose.yml` for local execution, write Kubernetes manifests (`k8s/`), and document OpenStack Magnum cluster provisioning.
6. **Testing & Demonstration Scenarios (Phase 6)**: End-to-end evaluation and rehearsal of project demonstration workflows on Podman Compose.

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    DELIVERY TIMELINE & PHASES                                    |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| Phase 0: Setup & Contracts        [Shared Foundation]                                            |
| Phase 1: Data Pipeline & Seeding  [Ingestion Engine + USDA / Food.com / RecipeNLG Subsets]       |
| Phase 2: Independent Services     [M1: Profile/Nutrition | M2: Recipe/Catalog | M3: Planner]    |
| Phase 3: Inter-Service Gates      [REST Contracts Validated & End-to-End Backend Verification]    |
| Phase 4: Editorial Frontend       [React + Vite, 0px Sharp UI, Light/Dark Modes, Workflows]     |
| Phase 5: Containers & K8s Deploy  [Podman Compose + Kubernetes Manifests + Magnum Cloud Ref]     |
| Phase 6: Final Verification & Demo[Academic Evaluation Rehearsal on Local Podman Compose]        |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Phase-by-Phase Implementation Plan

### Phase 0: Project Setup, Tooling & API Contract Baseline
- **Objective**: Establish project layout, shared database configuration, Git conventions, and contract specifications.
- **Current Progress (Step 02 Baseline)**:
  - **Step 2.1 (PostgreSQL DDL)**: Completed. Authoritative SQL files authored and reviewed:
    - `database/001_create_schemas.sql` (Schemas, extensions, least-privilege roles)
    - `database/002_create_tables.sql` (Tables, constraints, schema search paths, comments)
    - `database/003_indexes.sql` (33 operational indexes: GIN FTS, GIN trigram, FK lookups, partial filters)
    - `database/004_permissions.sql` (Least-privilege grants, default privileges, isolation enforcement)
  - **Step 2.2 (OpenAPI 3.1 YAML Specifications)**: Completed. Full OpenAPI 3.1 specs authored:
    - `contracts/openapi/profile-service.yaml` (Member 1, Port 8001: 6 endpoints)
    - `contracts/openapi/recipe-service.yaml` (Member 2, Port 8002: 7 endpoints)
    - `contracts/openapi/planner-service.yaml` (Member 3, Port 8003: 14 endpoints)
  - **Step 2.3 (Engineering Documentation)**: Completed.
    - `docs/DATABASE_SCHEMA.md` (Comprehensive schema, index, role, and isolation reference)
    - `docs/API_CONTRACTS.md` (Inter-service REST contracts, interaction workflows, and failure handling)
  - **Step 2.4 (Cross-Validation & Live Validation)**: Completed (Authoritative PASS). Static AST/regex verification and internal consistency checks 100% passed. Live container execution against real PostgreSQL 16 (`postgres:16-alpine`) executed via disposable container `foodflow-step03a-val-db`. All 22 tables, 33 indexes, 4 roles, dual default privileges, and strict schema isolation (all 6 unauthorized cross-schema queries blocked with `permission denied`) verified live. Disposable container cleanly torn down.
- **Milestone Exit Gate**: Database DDL scripts and OpenAPI 3.1 specifications approved and live-verified against PostgreSQL 16; zero cross-schema foreign keys or SQL joins; static cross-validation passed across all three service contracts. No application code, ingestion pipelines, or frontend components have been implemented yet. Ready for Phase 1.

---

### Phase 1: Data Ingestion & Seeding Engine
- **Objective**: Implement the reproducible data pipeline to ingest USDA, RecipeNLG, and Food.com datasets, supporting both development sampling and full production catalogue scaling.
- **Catalogue Scope & Broad Coverage Requirements**:
  - **Broad Cooking Scope**: NutriPod operates as a comprehensive, general-purpose recipe discovery platform (everyday dinners, regional cuisines, baking, desserts, snacks, beverages), not merely a narrow health recommendation tool.
  - **Development Sampling vs. Full Ingestion**:
    - The initial 25,000 Food.com + 25,000 RecipeNLG development subset is a **temporary seed** designed for rapid local builds ($< 1.2\text{ GB}$ DB footprint, $< 5\text{ min}$ seed time).
    - Development sampling must employ **stratified sampling** preserving diverse categories, tags, cuisines, and ingredient complexities, rather than taking the first $N$ sequential rows.
    - The final catalogue architecture targets ingestion of the full usable collections (~231k Food.com recipes and ~2.23M RecipeNLG records), subject to licensing, local disk allocation, and query benchmarking.
  - **Discovery & Search Priorities**:
    - Lexical FTS (`tsv_search`) combined with trigram similarity (`pg_trgm`). Exact title matches are scored and prioritized ahead of fuzzy or related results.
    - No fabricated recipes: if a search yields no matches, the system presents an honest empty state with related suggestions from the actual catalogue, never synthetic records.
- **Workstream Steps**:
  - **Step 03.1 (Ingestion Framework & CLI Foundation)**: **Completed (Authoritative PASS)**.
    - Implemented clean `ingestion/` package (`cli.py`, `config.py`, `database.py`, `manifest.py`, `logging_config.py`, `utils/checksums.py`, `utils/csv_utils.py`).
    - Standard library streaming CSV readers, bounded memory usage ($O(1)$ memory per process), chunked SHA-256 hashing.
    - PostgreSQL 16 connectivity using `psycopg` 3 with context management, schema validation, and database health diagnostics under administrative identity (`foodflow_admin`).
    - Audit manifest (`data/manifest.json`) initialized with verifiable upstream metadata and zero fabricated values.
    - 27 unit tests (`tests/ingestion/`) written and 100% passed using Python's standard `unittest`.
    - Created comprehensive engineering documentation: `docs/INGESTION_GUIDE.md`.
  - **Step 03.2 (USDA FoodData Central Ingestion)**: **Completed (Authoritative PASS)**.
    - Implemented `ingestion/datasets/usda/` (`parser.py`, `validator.py`, `loader.py`, `importer.py`).
    - Multi-source support: streams directly from official ZIP archives via `zipfile` (zero disk extraction) or extracted directory trees.
    - Full relational mapping to `profile_nutrition`: `usda_foods`, `usda_nutrients`, `usda_food_nutrients`, `usda_food_portions`, and `ingestion_provenance`.
    - Strict data integrity: preserves source nutrient units verbatim, preserves NULLs without zero-substitution, enforces foreign keys in memory before DB load, and preserves shared nutrient dictionary consistency with `ON CONFLICT (id) DO NOTHING`.
    - Extended CLI with `python -m ingestion.cli ingest-usda` supporting `--data-type`, `--source`, `--batch-size`, `--dry-run`, and `--limit`. Corrected `doctor` command reporting.
    - 41 unit tests passing (27 framework + 14 USDA integration tests).
    - Created comprehensive engineering documentation: `docs/USDA_INGESTION.md`.
  - **Step 03.3 (Food.com Ingestion & Ratings Aggregation)**: **Completed (Authoritative PASS)**.
    - Implemented `ingestion/datasets/foodcom/` (`parser.py`, `validator.py`, `ratings.py`, `loader.py`, `importer.py`).
    - Multi-source support: streams directly from uncompressed directory or ZIP archive without prior disk extraction.
    - Full relational mapping to `recipe_catalog`: `recipes`, `recipe_ingredients`, `recipe_instructions`, `recipe_tags`, `recipe_nutrition_raw`, `recipe_ratings`, and `ingestion_provenance`.
    - Safe AST parsing (`ast.literal_eval` via `safe_parse_python_list`) strictly prohibiting `eval()`.
    - Preserves 7-element raw %DV nutrition array verbatim in `recipe_nutrition_raw` without fabricated gram-weight conversions.
    - Memory-bounded streaming ratings aggregation via PostgreSQL session temporary staging table (`temp_foodcom_ratings_staging`), keeping Python memory $O(\text{batch\_size})$ for ~1.1M interaction records and preventing rounded average drift.
    - Extended CLI with `python -m ingestion.cli ingest-foodcom` supporting `--source`, `--component`, `--batch-size`, `--dry-run`, `--limit-recipes`, `--limit-interactions`.
    - 59 unit tests passing (27 framework + 14 USDA + 18 Food.com integration tests).
    - Created comprehensive engineering documentation: `docs/FOODCOM_INGESTION.md`.
  - **Step 03.4 (RecipeNLG Ingestion & NER Linking)**: **Completed (Authoritative PASS)**.
    - Implemented `ingestion/datasets/recipenlg/` (`parser.py`, `validator.py`, `loader.py`, `importer.py`).
    - Bounded-memory streaming reader supporting ZIP archives, uncompressed directories, and direct CSV file inputs with UTF-8 BOM handling and high field size limits.
    - Dual-engine list parsing (fast JSON first, fallback `ast.literal_eval`), strictly prohibiting `eval()`.
    - Created additive migration `database/migrations/005_add_recipenlg_source_origin.sql` to record sub-corpus origin (`Gathered` vs `Recipes1M`) without altering existing Food.com records.
    - Conservative quantity and unit parsing for raw ingredient strings.
    - Ambiguity-free canonical ingredient linking using pre-extracted NER entities.
    - Generated weighted full-text search vector `tsv_search` (title: A, ingredients: B).
    - Extended CLI with `python -m ingestion.cli ingest-recipenlg` supporting `--source`, `--batch-size`, `--dry-run`, `--limit`, `--force`.
    - 76 unit tests passing (27 framework + 14 USDA + 18 Food.com + 17 RecipeNLG integration tests).
    - Created comprehensive engineering documentation: `docs/RECIPENLG_INGESTION.md`.
  - **Step 03.5 (Unified Stratified Sampling Engine & Dev Data Preparation)**: **Completed (Authoritative PASS)**.
    - Implemented `ingestion/sampling/` (`base.py`, `foodcom_sampler.py`, `recipenlg_sampler.py`, `reports.py`).
    - Two-pass memory-bounded streaming architecture ($O(M)$ memory where $M$ is sample size, $O(1)$ stream buffering).
    - Proportional stratum quota allocation using the Hamilton-Hare Largest Remainder Method with guaranteed minimum representation.
    - Food.com: Stratified across 7 primary meal categories and 5 cooking time buckets.
    - Food.com Interaction Filtering: 100% referential integrity with zero ghost interactions by retaining all reviews matching sampled recipe IDs.
    - RecipeNLG: Stratified across sub-corpus origin (`Gathered` vs `Recipes1M`), 4 NER richness tiers, and directions availability.
    - Preserves exact original CSV column headers and raw data formats.
    - Extended CLI with `python -m ingestion.cli sample` supporting `--dataset`, `--source`, `--output-dir`, `--limit`, `--seed`, `--dry-run`.
    - 115 unit tests passing (27 framework + 14 USDA + 18 Food.com + 18 RecipeNLG + 38 sampling tests).
    - Created comprehensive engineering documentation: `docs/SAMPLING_GUIDE.md`.
- **Milestone Exit Gate**: Deterministic stratified development sampling operational via CLI. 115 unit tests passing. Full-scale ingestion pipeline verified on staging.

---

### Phase 2: Independent Backend Microservice Development
- **Objective**: Team members implement their respective microservices concurrently without blocking each other.

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    PARALLEL WORKSTREAM MATRIX                                    |
+──────────────────────────┬──────────────────────────┬────────────────────────────────────────────+
| TEAM MEMBER              | MICROSERVICE             | CORE PHASE 2 DELIVERABLES                  |
+──────────────────────────┼──────────────────────────┼────────────────────────────────────────────+
| **Member 1**             | Profile & Nutrition      | • Mifflin-St Jeor BMR & TDEE calculators   |
|                          | Service (:8001)          | • BMI & WHO classification logic           |
|                          |                          | • Caloric deficit/surplus goal adjuster    |
|                          |                          | • USDA ingredient nutrient mapping endpoint|
|                          |                          | • Zero-fabrication nutrition serializer    |
+──────────────────────────┼──────────────────────────┼────────────────────────────────────────────+
| **Member 2**             | Recipe & Ingredient      | • Fast full-text search API (tsquery)      |
|                          | Service (:8002)          | • Multi-faceted filtering (diet, time)     |
|                          |                          | • Recipe detail with step-by-step payloads |
|                          |                          | • Ingredient canonical taxonomy & synonyms |
|                          |                          | • Ratings summary serializer               |
+──────────────────────────┼──────────────────────────┼────────────────────────────────────────────+
| **Member 3**             | Recommendation & Meal    | • Pantry matching overlap algorithm        |
|                          | Planner Service (:8003)  | • Missing ingredient calculation           |
|                          |                          | • Meal plan CRUD (Breakfast/Lunch/Dinner)  |
|                          |                          | • Consolidated grocery shopping aggregator |
|                          |                          | • Cooking progress tracker                 |
+──────────────────────────┼──────────────────────────┼────────────────────────────────────────────+
```

- **Milestone Exit Gate**: Each service passes its individual test suite (`pytest`) and serves interactive Swagger documentation (`/docs`) on its designated port.

---

### Phase 3: Inter-Service Integration & Contract Verification
- **Objective**: Wire up cross-service HTTP calls and verify end-to-end backend data workflows.
- **Key Tasks**:
  - Connect Member 3's Pantry Matcher to Member 2's Ingredient Normalizer (`POST /api/v1/ingredients/normalize`).
  - Connect Member 3's Meal Plan Generator to Member 1's Target Caloric Budget endpoint (`GET /api/v1/profiles/{id}/targets`).
  - Implement defensive error handling (fallback behavior when dependent services are slow or down).
  - Write automated end-to-end integration tests using `pytest` and `httpx`.
- **Milestone Exit Gate**: All cross-service integration tests pass seamlessly across the internal container network.

---

### Phase 4: Editorial Frontend Implementation (React + Vite)
- **Objective**: Build the user-facing web platform adhering strictly to the editorial design specification.
- **Key Tasks**:
  - Initialize React 18 + Vite project with TypeScript.
  - Enforce the global design rules: `border-radius: 0px` globally, no glassmorphism, no gradients, no neon glows.
  - Implement typography system: Editorial serif headers paired with grotesque body and tabular monospace numerals.
  - Build light ("Culinary Newsprint") and dark ("Dark Kitchen Atelier") themes with smooth switching.
  - Develop core UI views:
    - **Editorial Recipe Showcase & Search View**: Responsive grid, faceted filter sidebar, scalable pagination.
    - **Recipe Detail & Step-by-Step Cooking View**: Clean layout, ingredient checklist, distraction-free cooking mode.
    - **Pantry Matcher Interface**: Autocomplete ingredient input, match percentage indicators, missing item highlights.
    - **Optional Health Profile & Biometrics Panel**: BMI, BMR, TDEE calculator cards with full mathematical transparency.
    - **Meal Planner & Consolidated Shopping List**: Drag-and-drop or slot-based calendar, checkable shopping items.
- **Milestone Exit Gate**: All user journeys (Guest, Pantry Cook, Health-Conscious, Meal Planner) are fully functional in the browser.

---

### Phase 5: Container Hardening, Compose Orchestration & Kubernetes Manifests
- **Objective**: Package the entire system into robust, self-contained OCI containers using Podman, provide local Compose orchestration, author production Kubernetes manifests (`k8s/`), and document OpenStack Magnum cluster provisioning.
- **Key Tasks**:
  - **Local Podman Containerization**:
    - Write optimized, multi-stage `Dockerfile` for each of the 3 backend services (Python 3.11-slim, non-root user).
    - Write multi-stage `Dockerfile` for the React frontend (Node.js build step $\rightarrow$ Nginx lightweight server).
    - Author production-ready `compose.yml` specifying service dependencies, healthchecks, bridge network `foodflow-net`, and persistent volume `foodflow-db-data`.
    - Validate clean local spin-up: `podman compose up --build`.
  - **Production Kubernetes Deployment Manifests (`k8s/`)**:
    - Author declarative Kubernetes resources in `k8s/`:
      - `k8s/namespace.yaml`: Dedicated `foodflow` namespace.
      - `k8s/config/`: `configmap.yaml` and `secret.yaml` (placeholder-only secret template; production credentials never committed).
      - `k8s/storage/`: `postgres-pvc.yaml` requesting persistent block storage (referencing an available and configured Cinder CSI `StorageClass`).
      - `k8s/statefulsets/`: `postgres-statefulset.yaml` for deterministic PostgreSQL persistence.
      - `k8s/deployments/`: Deployments for the 3 FastAPI backend services and the React frontend.
      - `k8s/services/`: ClusterIP services exposing internal ports (:8001, :8002, :8003, :5432, :80).
      - `k8s/ingress/`: Ingress routing definitions mapping HTTP paths to services (requiring an active Ingress Controller such as `ingress-nginx`).
  - **Cloud Infrastructure Documentation (OpenStack Magnum Reference)**:
    - Document the provisioning pipeline: how OpenStack Magnum invokes Heat templates to orchestrate Nova VMs, Neutron networking, and Cinder storage into an operational Kubernetes cluster.
    - Document the roles of Keystone (IAM/Auth), Nova (VM Compute), Heat (Orchestration), Neutron (SDN/Routing), Octavia (Dedicated Load Balancing), Glance (VM Disk Images), and Cinder (Block Storage).
    - Document the strict architectural distinction: **Glance stores base operating system VM disk images (e.g. a supported Fedora CoreOS or Ubuntu cloud image) used by Nova to boot cluster node VMs, whereas NutriPod application container images are OCI artifacts built with Podman and pulled from an OCI container registry.**
    - Document that while local Podman Compose serves as the active, zero-dependency environment for team development and demonstration, the Kubernetes manifests and Magnum reference provide deployment readiness if a cloud environment is provided for grading.
- **Milestone Exit Gate**: 
  - Complete stack builds and runs 100% locally via `podman compose up --build`.
  - All Kubernetes manifests in `k8s/` pass linting and dry-run syntax validation (`kubectl apply --dry-run=client -f k8s/`).

---

### Phase 6: System Verification, Demonstration Prep & Documentation
- **Objective**: Rehearse evaluation scenarios, polish documentation, and conduct stress testing on the local Podman Compose environment.
- **Key Tasks**:
  - Run performance audits on recipe search and pantry matching queries (benchmark target $< 200 \text{ ms}$ under local testing conditions).
  - Verify complete attribution notices for RecipeNLG, Food.com, and USDA FDC.
  - Prepare pre-recorded fallback walkthroughs and rehearse the live university demonstration on Podman Compose.
- **Milestone Exit Gate**: Flawless live demonstration execution of the three prescribed assessment scenarios.

---

## 3. University Evaluation Demonstration Scenarios

To demonstrate NutriPod to course evaluators, the team will present three end-to-end scenarios running on the local Podman Compose environment:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    DEMONSTRATION SCENARIOS                                       |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| SCENARIO 1: The Guest Discovery & Step-by-Step Cooking Experience                                |
| • Show immediate home access with NO login or onboarding popups.                                |
| • Execute faceted search for "Pasta" with "Vegetarian" and "Under 30 minutes" filters.           |
| • Open recipe detail, demonstrate nutrient transparency (source-reported vs calculated values).   |
| • Launch "Step-by-Step Cooking Mode" with keyboard-driven progression and checklist.             |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| SCENARIO 2: The Pantry Cleanout Challenge                                                        |
| • Input 4 ingredients: Chicken breast, garlic, soy sauce, and white rice.                        |
| • Toggle "Assume basic pantry staples (salt, pepper, water, oil)".                               |
| • Inspect match ranking: Show 100% matched recipe vs 80% matched recipe with missing scallions.  |
| • Click missing scallions to add directly to temporary shopping list.                           |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| SCENARIO 3: Health Biometrics Calibration & Meal Planning                                        |
| • Input Profile: Male (s = +5), Age = 30, Height = 180cm, Weight = 78kg, Moderate Activity      |
|   (PAL = 1.55), Goal = Weight Loss with a transparent -328 kcal/day deficit.                     |
| • Verify transparent Mifflin-St Jeor math displayed on screen:                                   |
|   - BMI: 78 / (1.80)^2 ≈ 24.1 kg/m² (WHO adult normal range: 18.5–24.9)                         |
|   - BMR Estimate: 10(78) + 6.25(180) - 5(30) + 5 = 780 + 1125 - 150 + 5 = 1,760 kcal/day        |
|   - TDEE Estimate: 1,760 × 1.55 = 2,728 kcal/day                                                 |
|   - Target Daily Budget: 2,728 - 328 = 2,400 kcal/day (transparent deficit goal)                |
| • Generate a 1-day meal plan allocating recipes to Breakfast, Lunch, and Dinner totaling ~2,400  |
| • Open generated grocery list, demonstrating aggregated quantities (e.g. 5 cloves garlic).       |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 4. Technical Trade-Offs & Architectural Decisions

| Decision | Chosen Alternative | Rejected Alternative | Justification |
| :--- | :--- | :--- | :--- |
| **Local Runtime vs. Cloud Infrastructure** | **Podman Compose for local execution** + **Kubernetes manifests (`k8s/`) with OpenStack Magnum documentation**. | Requiring active OpenStack cluster access or installing OpenStack locally on student laptops. | Students have no OpenStack credentials, lab endpoints, or 32GB+ RAM hardware to run DevStack. Podman Compose provides a 100% functional, zero-cost local environment, while K8s manifests provide cloud readiness. |
| **Database Topology** | Single PostgreSQL instance with 3 isolated schemas (`profile_nutrition`, `recipe_catalog`, `meal_planner`). | 3 separate physical PostgreSQL container instances. | A single instance minimizes RAM consumption on student laptops (avoiding running 3 DB engines) while strictly enforcing logical boundary rules (no cross-schema joins). |
| **Inter-Service Communication** | Synchronous REST APIs over internal container network. | Asynchronous message queues (Kafka, RabbitMQ). | Event brokers introduce unnecessary operational complexity and failure states for a 3-person team without meaningful throughput benefits. |
| **Authentication Strategy** | Client-side session / UUID guest token; optional lightweight JWT. | Complex OAuth2 / Social login providers. | NutriPod prioritizes guest-first accessibility. Heavy authentication walls violate the core philosophy and add fragile external dependencies. |
| **Development Data Volume vs. Full Scale** | **50,000 stratified recipe seed** (25k Food.com + 25k RecipeNLG) with complete USDA SR-Legacy dictionary for development; **full-scale ingestion targeting ~2.4M usable records** staged for production/benchmarking. | Immediate ingestion of all 2.4 million recipes during local initial development, or restricting the final application to a tiny hardcoded list. | Stratified sampling allows rapid local builds, fast schema migrations, and quick test execution while maintaining diversity across everyday meals, desserts, and regional cuisines. The identical Python CLI ingestion pipeline processes the full dataset for production scaling. |

