# FoodFlow

> **An editorial culinary discovery and cooking platform with transparent, health-focused personalization.**

FoodFlow is a university team engineering project designed to deliver a modern, magazine-grade recipe exploration and cooking experience. It bridges large-scale culinary datasets with intelligent pantry matching, step-by-step guided cooking, and an optional, non-intrusive health personalization layer.

---

## Core Product Philosophy

1. **Guest-First Accessibility**: FoodFlow functions completely and elegantly without an account or personal body measurements. Anyone can browse the catalogue, execute full-text and ingredient searches, apply dietary filters, and follow step-by-step cooking workflows immediately.
2. **Optional Health Personalization**: Nutritional targeting, caloric budgeting (BMI, BMR, TDEE), and body-goal alignment are opt-in features. Personal health data is never a barrier to finding good food.
3. **Scientific Transparency & Zero Fabrication**: Nutritional estimates rely strictly on verified ingredient data from the USDA FoodData Central and Food.com datasets. If nutrient values cannot be reliably computed for a recipe, FoodFlow explicitly indicates them as uncalculated rather than generating synthetic or misleading figures.
4. **Editorial Culinary Design**: The interface rejects generic SaaS dashboards, bubbly pill buttons, and glassmorphic gimmicks in favor of a sharp, high-contrast editorial culinary magazine aesthetic with strict 0px border radii and typography-first layouts.

---

## Key Functional Highlights

- **Recipe Catalogue & Discovery**: Access a multi-source catalogue derived from RecipeNLG (~2.23M recipes) and Food.com (~231k recipes). Search by title, keyword, prep time, cuisine, and dietary preferences with scalable pagination.
- **Interactive Step-by-Step Cooking Mode**: Distraction-free, large-type cooking view designed for hands-on kitchen use with stage tracking and ingredient checklists.
- **Pantry & Ingredient Matching**: Input on-hand ingredients to discover achievable recipes, calculate match percentages, identify missing items, and handle common ingredient synonyms.
- **Transparent Health & Nutrition**: Optional profile support calculating BMI, BMR (Mifflin-St Jeor), and TDEE across maintenance, surplus (gain), and deficit (loss) targets without medical pretense.
- **Meal Planning & Shopping Lists**: Assemble structured daily and weekly meal plans (breakfast, lunch, dinner, snack) and compile aggregated, consolidated grocery shopping lists.

---

## Technology Stack

| Domain | Technology | Rationale |
| :--- | :--- | :--- |
| **Frontend** | React 18 + Vite | Fast HMR, desktop-first responsive design, component modularity. |
| **Backend Services** | Python 3.11+ / FastAPI | High-performance asynchronous REST APIs, native Pydantic validation, rapid development. |
| **Database** | PostgreSQL 16 | Relational consistency, robust JSONB support, GIN indexing for full-text search and arrays. |
| **Local Containerization** | Podman (Docker CLI compatible) | Rootless, secure container execution adhering to modern OCI standards. |
| **Local Orchestration** | Podman Compose (`compose.yml`) | Multi-service local networking, shared persistent database storage, 100% functional local runtime. |
| **Cloud Target (Reference)** | Kubernetes Manifests (`k8s/`) | Declarative Deployments, Services, ConfigMaps, and Cinder-backed PVCs for production cloud execution. |
| **Cloud Provisioning (Ref)** | OpenStack Magnum | Infrastructure reference: provisions the underlying Kubernetes cluster using OpenStack core services. |
| **Data Ingestion** | Python CLI Pipeline | Isolated batch processors to clean, normalize, and ingest USDA, RecipeNLG, and Food.com datasets. |

*FoodFlow runs entirely self-contained locally via Podman Compose without requiring active OpenStack accounts, remote cloud endpoints, proprietary LLM APIs (e.g., Claude or Gemini), or paid third-party services.*

---

## Team Structure & Service Ownership

FoodFlow is divided into three distinct, independently maintainable backend microservices alongside shared infrastructure and frontend responsibilities:

```
+-----------------------------------------------------------------------------------+
|                                  SHARED FRONTEND                                  |
|                             (React + Vite Single Page App)                        |
+-----------------------------------------------------------------------------------+
                                         │  HTTP / REST (Reverse Proxy)
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
+─────────────────────────+ +─────────────────────────+ +─────────────────────────+
|      Member 1 (M1)      | |      Member 2 (M2)      | |      Member 3 (M3)      |
|  Profile & Nutrition    | |   Recipe & Ingredient   | |  Recommendation & Meal  |
|         Service         | |         Service         | |     Planner Service     |
|       (Port 8001)       | |       (Port 8002)       | |       (Port 8003)       |
+─────────────────────────+ +─────────────────────────+ +─────────────────────────+
         │                               │                               │
         └───────────────────────────────┼───────────────────────────────┘
                                         ▼
                     +───────────────────────────────────────────────────────────+
                     |                       PostgreSQL 16                       |
                     | (Schemas: profile_nutrition, recipe_catalog, meal_planner) |
                     +───────────────────────────────────────────────────────────+
```

| Member | Primary Ownership | Core Module Responsibilities |
| :--- | :--- | :--- |
| **Team Member 1** | **Profile and Nutrition Service** | User body profile, BMR/TDEE calculations, health goals, USDA ingredient nutrient mapping, transparent macro/micronutrient breakdown. |
| **Team Member 2** | **Recipe and Ingredient Service** | Recipe catalogue storage, full-text search, multi-faceted filtering, step-by-step directions, ratings, ingredient taxonomy and synonyms. |
| **Team Member 3** | **Recommendation & Meal Planner Service** | Pantry ingredient matching, missing ingredient calculation, daily/weekly meal plan generation, consolidated shopping list creation. |
| **All Members** | **Shared Coordination** | Frontend view integration, Compose environment, database schemas and migrations, documentation, end-to-end testing. |

---

## Visual Design Manifesto

FoodFlow’s visual aesthetic is directly inspired by print culinary periodicals (such as *The Gentlewoman*, *Lucky Peach*, and *Cereal*):

- **Strict Sharp Edges**: `border-radius: 0px` globally. Absolutely zero rounded corners or pill-shaped buttons on cards, dialogs, tags, inputs, or containers.
- **No Skeuomorphism or Trendy Gimmicks**: Strictly no glassmorphism, blur effects, translucent glass panels, decorative neon glows, or multi-stop gradient backgrounds.
- **Editorial Typography**: Elegant serif headers (e.g., *Newsreader* or *Playfair Display*) paired with stark, functional grotesque/monospace sans-serif body typefaces (e.g., *Inter* or *Space Grotesk*).
- **Restrained Color Palette**: High-contrast editorial monochrome (warm newsprint, deep charcoal/black) elevated with muted earth tones (olive, terracotta, linen).
- **Dual Theme Support**: Dedicated, cohesive light and dark themes designed with clear contrast ratios for readable kitchen cooking.
- **Desktop-First, Mobile-Responsive**: Rich multi-column grid layouts on desktop that fold logically into clean single-column reading flows on mobile screens.

---

## High-Level Execution & Deployment Direction

FoodFlow employs a two-tier deployment architecture:
1. **Local Development (Fully Functional & Primary)**: Powered by **Podman and Podman Compose**. This allows the entire team to build, run, test, and demonstrate the full stack locally on any workstation without requiring an OpenStack account, cloud credentials, or external lab connectivity.
2. **Cloud Production Reference (OpenStack Magnum + Kubernetes)**: For cloud-native deployment, FoodFlow includes production-grade **Kubernetes manifests** (`k8s/`). OpenStack Magnum serves as the infrastructure reference for provisioning the underlying Kubernetes cluster via OpenStack core services (Keystone, Nova, Heat, Neutron, Glance, and Cinder).

### Project Layout
```text
FoodFlow/
├── compose.yml                     # Multi-service Podman/Docker compose definition
├── .env.example                    # Global environment template
├── .gitignore                      # Git exclusion rules (raw data excluded, manifest tracked)
├── database/                       # PostgreSQL 16 DDL & isolation permissions
│   ├── 001_create_schemas.sql
│   ├── 002_create_tables.sql
│   ├── 003_indexes.sql
│   ├── 004_permissions.sql
│   └── migrations/
│       └── 005_add_recipenlg_source_origin.sql
├── contracts/openapi/              # OpenAPI 3.1 YAML service contracts
│   ├── profile-service.yaml
│   ├── recipe-service.yaml
│   └── planner-service.yaml
├── ingestion/                      # Standalone dataset ingestion & seeding framework
│   ├── cli.py                      # CLI entrypoint (doctor, inspect, verify, status)
│   ├── config.py                   # Paths, dataset registry, URL masking
│   ├── database.py                 # PostgreSQL 16 connectivity (psycopg 3, health checks)
│   ├── manifest.py                 # Audit manifest management (data/manifest.json)
│   ├── logging_config.py           # Formatted console & file audit logging
│   ├── requirements.txt            # Minimal dependencies (psycopg[binary])
│   ├── utils/                      # Streaming CSV & chunked SHA-256 utilities
│   ├── datasets/                   # Modular dataset pipelines (usda, foodcom, recipenlg)
│   └── sampling/                   # Stratified sampling engine
├── data/                           # Local data mounts
│   ├── manifest.json               # Persistent dataset manifest (tracked in Git)
│   ├── raw/                        # Raw downloaded archives (gitignored)
│   ├── processed/                  # Sanitized & sampled datasets (gitignored)
│   └── reports/                    # Execution logs & reports (gitignored)
├── docs/                           # Architecture, database, contract, and dataset specs
│   ├── PRODUCT_REQUIREMENTS.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── DATASET_PLAN.md
│   ├── DATABASE_SCHEMA.md
│   ├── API_CONTRACTS.md
│   ├── INGESTION_GUIDE.md
│   ├── STEP_02_VALIDATION_REPORT.md
│   ├── USDA_INGESTION.md
│   ├── FOODCOM_INGESTION.md
│   ├── RECIPENLG_INGESTION.md
│   ├── SAMPLING_GUIDE.md
│   └── IMPLEMENTATION_ROADMAP.md
├── k8s/                            # Production Kubernetes deployment manifests
│   ├── config/                     # ConfigMaps and Secrets (placeholders only)
│   ├── storage/                    # PersistentVolumeClaims (Cinder CSI StorageClass reference)
│   ├── statefulsets/               # PostgreSQL 16 StatefulSet
│   ├── deployments/                # Deployments for 3 microservices & frontend
│   ├── services/                   # ClusterIP definitions
│   └── ingress/                    # Ingress routing rules (requires cluster ingress controller)
├── services/
│   ├── common/                         # Shared foundation models, DB pool, logging & errors
│   │   ├── config.py                   # Environment loader & URL masking
│   │   ├── database.py                 # psycopg_pool.ConnectionPool & role validator
│   │   ├── errors.py                   # OpenAPI-compliant exception handlers
│   │   ├── logging.py                  # Structured logging with credential sanitization
│   │   └── models.py                   # Pydantic schemas (HealthResponse, ReadinessResponse, ErrorResponse)
│   ├── profile_nutrition/              # Member 1 service (FastAPI, Port 8001)
│   │   ├── config.py, database.py, main.py
│   │   └── routers/health.py           # /health, /health/live, /health/ready
│   ├── recipe_ingredient/              # Member 2 service (FastAPI, Port 8002)
│   │   ├── config.py, database.py, main.py
│   │   └── routers/health.py           # /health, /health/live, /health/ready
│   └── recommendation_planner/         # Member 3 service (FastAPI, Port 8003)
│       ├── config.py, database.py, dependencies.py, main.py, schemas.py
│       ├── client.py, repository.py, matcher.py, generator.py, categorizer.py
│       └── routers/                    # health.py, sessions.py, pantry.py, plans.py, shopping.py
├── frontend/                           # Shared React + Vite SPA
└── tests/
    ├── ingestion/                      # Ingestion & sampling unit test suite (122 tests)
    └── services/                       # Backend service test suite (96 tests covering foundations, Recipe Service, Profile Service, and Planner Service)
```

### Key Architectural Note: VM Images (Glance) vs Container Images
- **Glance VM Disk Images**: In an OpenStack environment, Glance stores base operating system virtual machine disk images (`.qcow2`, `.raw`, e.g., Fedora CoreOS or Ubuntu cloud images) used by Nova and Heat to boot the virtual machines that make up the Kubernetes cluster nodes.
- **Application Container Images**: FoodFlow application container images (FastAPI microservices and React frontend) are lightweight OCI images built using Podman/Docker (`podman build`) and pushed to an OCI container registry (e.g., Docker Hub, Quay.io, or Harbor). Kubernetes pulls these OCI images to run application Pods on the worker nodes. **Application container images are not stored in Glance.**

### Local Workflow (Zero OpenStack Access Required)
1. **Environment Configuration**: Clone the repository and configure service ports and database credentials via `.env` (copied from `.env.example`).
2. **Full-Stack Container Orchestration**: Start the complete platform (PostgreSQL 16, all 3 backend microservices, and React frontend):
   ```bash
   docker compose up -d
   # or with Podman:
   podman compose up -d
   ```
   Inspect container health:
   ```bash
   docker compose ps
   ```
3. **Data Ingestion**: Run the standalone Python ingestion CLI (`python -m ingestion.cli doctor`, `inspect`, `verify`, `status`) to validate environment and seed the database with development datasets.
4. **Running Backend Services Independently**:
   Each service can be launched locally via Uvicorn on its designated port using its restricted database role:
   ```bash
   # Profile & Nutrition Service (Port 8001)
   uvicorn services.profile_nutrition.main:app --host 0.0.0.0 --port 8001 --reload

   # Recipe & Ingredient Service (Port 8002)
   uvicorn services.recipe_ingredient.main:app --host 0.0.0.0 --port 8002 --reload

   # Recommendation & Meal Planner Service (Port 8003)
   uvicorn services.recommendation_planner.main:app --host 0.0.0.0 --port 8003 --reload
   ```
5. **Verifying Health & Readiness**:
   Each service exposes standard OpenAPI health probes and orchestrator readiness checks:
   ```bash
   # Health check (Process alive)
   curl http://localhost:8001/health
   curl http://localhost:8002/health
   curl http://localhost:8003/health

   # Readiness check (Database pool & restricted role schema access)
   curl http://localhost:8001/health/ready
   curl http://localhost:8002/health/ready
   curl http://localhost:8003/health/ready
   ```
6. **Executing Test Suites**:
   ```bash
   # Run all backend service tests (96 tests covering foundations, Recipe Service, Profile Service, and Planner Service business APIs)
   python -m unittest discover -s tests/services -v

   # Run dedicated Recommendation & Meal Planner Service test suite (26 tests)
   python -m unittest tests/services/test_planner_service.py -v

   # Run dedicated Profile & Nutrition Service test suite (20 tests)
   python -m unittest tests/services/test_profile_service.py -v

   # Run dedicated Recipe Service test suite (28 tests)
   python -m unittest tests/services/test_recipe_service.py -v

   # Run backend service foundations test suite (22 tests)
   python -m unittest tests/services/test_service_foundations.py -v

   # Run ingestion & sampling test suite (122 tests)
   python -m unittest discover -s tests/ingestion -v
   ```
7. **Profile & Nutrition Service Endpoints (Port 8001)**:
   - `GET /health` & `GET /health/live`: Service health probes
   - `GET /health/ready`: Database readiness check with `foodflow_profile_user` role
   - `POST /api/v1/biometrics/calculate`: Stateless calculation of BMI, BMR (Mifflin-St Jeor), TDEE, goal caloric target (maintain: 0, lose: -400, gain: +400 with 1,200 kcal floor), and FoodFlow default macro distribution (20% protein, 50% carbohydrates, 30% fat = 100% total) without DB persistence. When `sex_for_equation` is omitted, returns BMI and category only without fabricating metabolic rates.
   - `GET /api/v1/nutrition/foods/search`: Paginated search across USDA FoodData Central items with ILIKE / trigram matching and data type filtering
   - `GET /api/v1/nutrition/foods/{fdc_id}`: Complete USDA food nutrient measurements per 100g and household portions
   - `POST /api/v1/nutrition/recipes/estimate`: Ingredient-level nutritional calculation based on USDA tables, returning `calculated` ($\ge 80\%$), `partial` ($>0\%$), or `uncalculated` ($0\%$) status without fabricating missing values
   - `GET /api/v1/nutrition/recipes/{recipe_id}`: Retrieves cached recipe nutrition profile from `profile_nutrition.nutrition_estimates`
8. **Recipe & Ingredient Service Endpoints (Port 8002)**:
   - `GET /health` & `GET /health/live`: Service health probes
   - `GET /health/ready`: Database readiness check with `foodflow_recipe_user` role
   - `GET /api/v1/recipes/search`: Search catalogue with full-text `q`, `cuisine`, `tag`, `diet`, `max_time`, `source_dataset`, and `sort`
   - `GET /api/v1/recipes/{recipe_id}`: Full recipe detail with ordered ingredients, steps, tags, ratings, and raw nutrition (%DV)
   - `POST /api/v1/recipes/batch`: High-throughput batch recipe retrieval (up to 100 IDs) for internal orchestration
   - `POST /api/v1/recipes/search-by-ingredients`: Candidate recipe matching by canonical ingredient IDs
   - `POST /api/v1/ingredients/normalize`: Maps raw ingredient text to canonical taxonomy (graceful handling of empty dictionaries)
   - `GET /api/v1/ingredients/suggestions`: Autocomplete search for canonical ingredients
9. **Recommendation & Meal Planner Service Endpoints (Port 8003)**:
   - `GET /health` & `GET /health/live`: Service health probes
   - `GET /health/ready`: Database readiness check with `foodflow_planner_user` role
   - `POST /api/v1/guest-sessions`: Creates an anonymous 30-day UUID guest session
   - `GET /api/v1/guest-sessions/{session_id}`: Verifies guest session existence, active status, and updates `last_active_at`
   - `GET /api/v1/pantry`: Retrieves active pantry inventory for the current guest session (`X-Guest-Session-ID`)
   - `PUT /api/v1/pantry`: Replaces/clears pantry items; normalizes via Recipe Service or gracefully preserves raw text
   - `POST /api/v1/pantry/match`: Matches pantry inventory against recipe catalogue by ingredient overlap percentage
   - `POST /api/v1/meal-plans/generate`: Stateless multi-day meal schedule proposal matching caloric/macro targets and dietary restrictions without database persistence
   - `POST /api/v1/meal-plans`: Persists a meal plan schedule and slots after validating recipe existence via Recipe Service
   - `GET /api/v1/meal-plans/{plan_id}`: Retrieves meal plan details, ordered slots, and cooking progress
   - `PUT /api/v1/meal-plans/{plan_id}`: Replaces meal plan schedule slots and targets
   - `DELETE /api/v1/meal-plans/{plan_id}`: Deletes a meal plan (cascades to slots and shopping list)
   - `PATCH /api/v1/meal-plans/{plan_id}/progress`: Batch updates slot cooking progress (`pending`, `cooked`, `skipped`)
   - `GET /api/v1/meal-plans/{plan_id}/shopping-list`: Retrieves or generates consolidated grocery checklist grouped by supermarket category (`Produce`, `Dairy & Refrigerated`, `Meat & Seafood`, `Pantry & Dry Goods`, `Bakery & Grains`, `Spices & Seasonings`, `Other`)
   - `PATCH /api/v1/meal-plans/{plan_id}/shopping-list/items/{item_id}`: Toggles shopping list item checked/procurement status
10. **Application Access**: Access the React interface via `http://localhost:5173` with API requests proxied internally to the corresponding backend microservices.


---

## Documentation Roadmap

Detailed architectural and engineering blueprints are available in the [`docs/`](docs/) directory:

1. [**Product Requirements Document (`docs/PRODUCT_REQUIREMENTS.md`)**](docs/PRODUCT_REQUIREMENTS.md)  
   Comprehensive breakdown of guest workflows, optional profile journeys, functional requirements partitioned across the three services, visual specifications, and explicit MVP boundaries.
2. [**System Architecture Document (`docs/SYSTEM_ARCHITECTURE.md`)**](docs/SYSTEM_ARCHITECTURE.md)  
   Deep-dive into the 3-microservice architecture, database schema isolation with least-privilege roles, inter-service REST contracts, container networking, Kubernetes deployment manifests, and OpenStack Magnum cloud provisioning reference (Keystone, Nova, Heat, Neutron, Octavia, Glance, Cinder).
3. [**Dataset Plan & Ingestion Strategy (`docs/DATASET_PLAN.md`)**](docs/DATASET_PLAN.md)  
   Provenance, schemas, verified licensing terms, deduplication rules, and reproducible ETL utility pipeline for USDA FoodData Central, RecipeNLG, and Food.com.
4. [**Database Schema Reference (`docs/DATABASE_SCHEMA.md`)**](docs/DATABASE_SCHEMA.md)  
   Technical specification of the PostgreSQL 16 physical data model: 3 isolated schemas, 22 tables, 33 indexes, least-privilege roles, and zero cross-schema foreign keys.
5. [**REST API Contracts (`docs/API_CONTRACTS.md`)**](docs/API_CONTRACTS.md)  
   Inter-service REST communication contracts, sequence workflows, and failure fallback behaviors across the 27 OpenAPI 3.1 endpoints.
6. [**Dataset Ingestion Framework Guide (`docs/INGESTION_GUIDE.md`)**](docs/INGESTION_GUIDE.md)  
   Engineering guide for the Phase 1 ingestion CLI, directory layout, streaming reader, chunked SHA-256 validation, manifest auditing, and database connectivity.
7. [**Step 02 Validation Report (`docs/STEP_02_VALIDATION_REPORT.md`)**](docs/STEP_02_VALIDATION_REPORT.md)  
   Audit report detailing static schema and contract validation along with live PostgreSQL 16 container execution and role isolation verification.
8. [**Implementation Roadmap (`docs/IMPLEMENTATION_ROADMAP.md`)**](docs/IMPLEMENTATION_ROADMAP.md)  
   Phased milestone delivery schedule for a 3-person student team, detailing checkpoints, acceptance criteria, integration gates, Kubernetes manifest creation, and evaluation demo scenarios.
9. [**USDA FoodData Central Ingestion Guide (`docs/USDA_INGESTION.md`)**](docs/USDA_INGESTION.md)  
   Technical specification for ingesting Foundation Foods and SR Legacy collections: streaming ZIP archive extraction, field mappings to `profile_nutrition`, and data integrity rules.
10. [**Food.com Ingestion Guide (`docs/FOODCOM_INGESTION.md`)**](docs/FOODCOM_INGESTION.md)  
   Technical specification for ingesting Food.com recipes and user reviews: safe AST parsing, %DV nutrition array preservation, temporary staging table ratings aggregation, and full-text search vector generation.
11. [**RecipeNLG Ingestion Guide (`docs/RECIPENLG_INGESTION.md`)**](docs/RECIPENLG_INGESTION.md)  
   Technical specification for ingesting the RecipeNLG corpus (~2.23M recipes): streaming parser, conservative quantity parsing, NER canonical ingredient linking, and additive migration 005.
12. [**Dataset Sampling & Development Seed Guide (`docs/SAMPLING_GUIDE.md`)**](docs/SAMPLING_GUIDE.md)  
   Technical specification for the unified stratified reservoir sampling engine: proportional stratum quota allocation (Hamilton-Hare largest remainder), Food.com tag and cooking-time bucketing, 100% referential interaction filtering, and RecipeNLG structural stratification ($O(M)$ memory bounded).


