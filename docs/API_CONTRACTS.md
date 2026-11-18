# NutriPod — Inter-Service REST API Contracts & Architecture Handbook

| Metadata | Details |
| :--- | :--- |
| **Document Version** | 1.0.0 |
| **Status** | Implementation-Ready API Contract Reference (Step 02 Baseline) |
| **Specification Format** | OpenAPI 3.1.0 (JSON Schema 2020-12 Native) |
| **Services Documented** | 3 Microservices (Profile, Recipe, Planner) |
| **Authoritative Sources** | `contracts/openapi/profile-service.yaml`<br>`contracts/openapi/recipe-service.yaml`<br>`contracts/openapi/planner-service.yaml` |

---

## 1. Global API Standards & Architectural Conventions

All NutriPod microservices adhere to unified architectural conventions to ensure seamless frontend and inter-service communication across the container network.

### 1.1 Microservice Registry & Network Topology

| Service Name | Port | Container Hostname | Database Schema | Primary Role |
| :--- | :--- | :--- | :--- | :--- |
| **Profile & Nutrition Service** | `8001` | `profile-service` | `profile_nutrition` | Stateless biometrics, USDA nutrient composition, recipe nutrition estimation |
| **Recipe & Ingredient Service** | `8002` | `recipe-service` | `recipe_catalog` | Multi-source recipe catalogue, faceted lexical search, ingredient taxonomy & normalization |
| **Recommendation & Planner Service** | `8003` | `planner-service` | `meal_planner` | Guest sessions, pantry matching, meal plan scheduling, grocery checklists |

- **Local Host URL**: `http://localhost:<port>` (used for local development and direct frontend calls).
- **Internal Network URL**: `http://<service-name>:<port>` (used for service-to-service calls on the `foodflow-net` bridge network).
- **Base Route Prefix**: `/api/v1/` for domain endpoints; `/health` at root for probes.

---

### 1.2 Public vs. Internal Endpoints
Endpoints are classified into two access tiers:
1. **Public Endpoints**: Accessible directly by the React frontend and client browsers without authentication.
2. **Internal Endpoints** (`x-internal: true` in OpenAPI): Designed specifically for high-throughput service-to-service orchestration over the internal Docker/Podman network.
   - `POST /api/v1/recipes/batch` (Service 2): Bulk recipe lookup by ID list.
   - `POST /api/v1/recipes/search-by-ingredients` (Service 2): Candidate recipe retrieval by canonical ingredient IDs.

---

### 1.3 Uniform Envelope Conventions

#### Standardized Error Envelope
Every failure (4xx and 5xx) returns a consistent JSON envelope with diagnostic metadata:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request parameters failed validation",
    "details": [
      {
        "field": "age_years",
        "issue": "Age must be an integer between 1 and 120"
      }
    ],
    "request_id": "d290f1ee-6c54-4b01-90e6-d701748f0851"
  }
}
```

*Common Error Codes*: `VALIDATION_ERROR` (400), `SESSION_EXPIRED` (401/404), `RESOURCE_NOT_FOUND` (404), `SERVICE_UNAVAILABLE` (502/503), `INTERNAL_ERROR` (500).

#### Standardized Pagination Envelope
List endpoints implement deterministic offset-limit pagination wrapped in a consistent metadata structure:

```json
{
  "data": [ "..." ],
  "pagination": {
    "page": 1,
    "limit": 24,
    "total_items": 84,
    "total_pages": 4
  }
}
```

- Default page size: `24` items. Maximum allowed: `48` items.

---

### 1.4 Unified Recipe Identifier Convention
To prevent primary key collisions between Food.com and RecipeNLG records, all services consume and produce **unified recipe IDs**:
$$\text{Format: } \mathbf{rcp\_\{source\_dataset\}\_\{source\_id\}}$$
- Food.com: `rcp_foodcom_5421` (source ID: `5421`)
- RecipeNLG: `rcp_nlg_108294` (source ID: `108294`)
- Validation Pattern: `^rcp_(foodcom|nlg)_[a-zA-Z0-9_-]+$`

---

### 1.5 Guest-First Session Lifecycle & `X-Guest-Session-ID`
NutriPod enforces an editorial philosophy where recipe discovery, cooking modes, pantry matching, and nutrition calculation require **zero user registration**:
- When a guest user wishes to persist an on-hand pantry inventory or save a meal plan, the client initializes a session via `POST /api/v1/guest-sessions`.
- The service returns a 128-bit UUID (`session_id`) with a 30-day expiry window.
- The client stores this UUID in local storage and attaches it to subsequent requests via the HTTP header:
  ```http
  X-Guest-Session-ID: e4eaaaf2-d142-4f01-9e73-b3c990b79f82
  ```
- No passwords, usernames, or PII are collected.

---

### 1.6 Nutrition Data Integrity & Status Categories
NutriPod prohibits the fabrication of missing nutritional metrics. All nutritional responses include an explicit `status` field:
- `calculated`: Mathematical aggregation from mapped USDA FoodData Central items where ingredient coverage is $\ge 80\%$ and gram weights are reliable.
- `reported_approximate`: Sourced from Food.com raw percentage Daily Values (`%DV`) with gram conversions calculated based on FDA 2,000 kcal reference intakes and labeled as approximations.
- `partial`: Nutrient breakdown where coverage is $< 80\%$ or several ingredients lack gram weights.
- `uncalculated`: Insufficient information to calculate nutrition (e.g. RecipeNLG items lacking measurements). All nutrient fields are returned as `null` rather than zero or invented values.

---

### 1.7 Nullable Recipe Metadata Policy
RecipeNLG lacks serving sizes, preparation times, cooking times, and cuisine tags. To preserve data fidelity:
- `servings`: Strictly `null` when unknown. **Never defaulted to 4.**
- `prep_time_minutes`, `cook_time_minutes`, `total_time_minutes`: `null` when not reported.
- `cuisine`: `null` when unclassified.
- `rating_average`: `null` when unreviewed; `rating_count: 0`. **Never defaulted to 5.0.**

---

## 2. Complete Endpoint Inventory

### 2.1 Profile & Nutrition Service (Port 8001)

| Method | Path | Operation ID | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | `getHealth` | Public | Service health check |
| `POST` | `/api/v1/biometrics/calculate` | `calculateBiometrics` | Public | Stateless BMI, BMR, TDEE, and caloric target calculator |
| `GET` | `/api/v1/nutrition/foods/search` | `searchUSDAFoods` | Public | Full-text query against USDA FDC foods |
| `GET` | `/api/v1/nutrition/foods/{fdc_id}` | `getUSDAFoodDetail` | Public | Complete nutrient measurements and portions for an FDC ID |
| `POST` | `/api/v1/nutrition/recipes/estimate` | `estimateRecipeNutrition` | Public/Internal | Computes nutrition profile from raw/canonical ingredients |
| `GET` | `/api/v1/nutrition/recipes/{recipe_id}` | `getCachedRecipeNutrition` | Public/Internal | Retrieves cached recipe nutrition profile |

### 2.2 Recipe & Ingredient Service (Port 8002)

| Method | Path | Operation ID | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | `getHealth` | Public | Service health check |
| `GET` | `/api/v1/recipes/search` | `searchRecipes` | Public | Lexical full-text search with faceted filters |
| `GET` | `/api/v1/recipes/{recipe_id}` | `getRecipeDetail` | Public | Full recipe detail with ingredients, steps, and ratings |
| `POST` | `/api/v1/recipes/batch` | `batchGetRecipes` | **Internal** | Bulk recipe retrieval by ID list |
| `POST` | `/api/v1/ingredients/normalize` | `normalizeIngredients` | Public/Internal | Normalizes ingredient strings to canonical taxonomy |
| `GET` | `/api/v1/ingredients/suggestions` | `getIngredientSuggestions` | Public | Autocomplete suggestions for ingredient names |
| `POST` | `/api/v1/recipes/search-by-ingredients`| `searchRecipesByIngredients`| **Internal** | Candidate retrieval by canonical ingredient IDs |

### 2.3 Recommendation & Meal Planner Service (Port 8003)

| Method | Path | Operation ID | Access | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/health` | `getHealth` | Public | Service health check |
| `POST` | `/api/v1/guest-sessions` | `createGuestSession` | Public | Initializes a new UUID guest session |
| `GET` | `/api/v1/guest-sessions/{session_id}` | `getGuestSession` | Public | Verifies and touches an active session |
| `GET` | `/api/v1/pantry` | `getPantry` | Guest | Retrieves active pantry inventory |
| `PUT` | `/api/v1/pantry` | `updatePantry` | Guest | Replaces entire pantry inventory |
| `POST` | `/api/v1/pantry/match` | `matchPantryRecipes` | Public/Guest | Matches on-hand ingredients against catalogue |
| `POST` | `/api/v1/meal-plans/generate` | `generateMealPlan` | Public/Guest | Proposes automated 1–14 day meal schedule |
| `POST` | `/api/v1/meal-plans` | `saveMealPlan` | Guest | Persists a proposed meal plan |
| `GET` | `/api/v1/meal-plans/{plan_id}` | `getMealPlan` | Guest | Retrieves saved plan with slot cooking progress |
| `PUT` | `/api/v1/meal-plans/{plan_id}` | `updateMealPlan` | Guest | Updates plan slots and targets |
| `DELETE`| `/api/v1/meal-plans/{plan_id}` | `deleteMealPlan` | Guest | Deletes meal plan and associated shopping list |
| `GET` | `/api/v1/meal-plans/{plan_id}/shopping-list` | `getShoppingList` | Guest | Generates or retrieves consolidated grocery list |
| `PATCH`| `.../shopping-list/items/{item_id}` | `updateShoppingListItem` | Guest | Toggles item procurement check state |
| `PATCH`| `/api/v1/meal-plans/{plan_id}/progress` | `updateCookingProgress` | Guest | Updates cooking status on planned slots |

---

## 3. End-to-End Inter-Service Integration Workflows

### 3.1 Workflow A: Pantry Matching Workflow
Orchestrates ingredient normalization, candidate recipe discovery, and mathematical overlap scoring:

```
+──────────+            +────────────────+            +────────────────+
|  CLIENT  |            | PLANNER (:8003)|            | RECIPE (:8002) |
+──────────+            +────────────────+            +────────────────+
     │                          │                              │
     │ 1. POST /pantry/match    │                              │
     │    (raw ingredient list) │                              │
     ├─────────────────────────►│                              │
     │                          │ 2. POST /ingredients/        │
     │                          │    normalize (raw text)      │
     │                          ├─────────────────────────────►│
     │                          │                              │
     │                          │ 3. Return canonical IDs      │
     │                          │    + staple flags            │
     │                          │◄─────────────────────────────┤
     │                          │                              │
     │                          │ 4. POST /recipes/search-     │
     │                          │    by-ingredients (IDs)      │
     │                          ├─────────────────────────────►│
     │                          │                              │
     │                          │ 5. Return candidate recipes  │
     │                          │    + recipe ingredient sets  │
     │                          │◄─────────────────────────────┤
     │                          │                              │
     │                          │ [Compute Overlap Formula]    │
     │                          │ [Exclude Pantry Staples]     │
     │                          │ [Rank Descending Match %]    │
     │                          │                              │
     │ 6. 200 OK (Ranked        │                              │
     │    matches + missing)    │                              │
     │◄─────────────────────────┤                              │
```

#### Exact Matching Formula
The planner calculates match efficiency per candidate recipe using the set-theoretic formula:
$$\text{Match } \% = \left(\frac{|\text{Matched Canonical Ingredients}|}{|\text{Total Recipe Canonical Ingredients}|}\right) \times 100$$
- **Staple Handling**: When `exclude_pantry_staples: true`, items flagged `is_pantry_staple: true` (e.g. salt, black pepper, water, vegetable oil) are excluded from the missing ingredients count so they do not unfairly penalize pantry cooks.

---

### 3.2 Workflow B: Automated Meal Plan Generation
Generates multi-day meal plans matching caloric constraints and dietary preferences without excluding recipes lacking pre-computed nutrition:

```
+──────────+         +────────────────+         +────────────────+         +────────────────+
|  CLIENT  |         | PLANNER (:8003)|         | PROFILE (:8001)|         | RECIPE (:8002) |
+──────────+         +────────────────+         +────────────────+         +────────────────+
     │                       │                          │                          │
     │ 1. POST /meal-plans/  │                          │                          │
     │    generate (days,    │                          │                          │
     │    caloric target)    │                          │                          │
     ├──────────────────────►│                          │                          │
     │                       │ 2. Optional: Translate   │                          │
     │                       │    biometrics targets    │                          │
     │                       ├─────────────────────────►│                          │
     │                       │◄─────────────────────────┤                          │
     │                       │                          │                          │
     │                       │ 3. GET /recipes/search (faceted tags, time limit)   │
     │                       ├────────────────────────────────────────────────────►│
     │                       │◄────────────────────────────────────────────────────┤
     │                       │                          │                          │
     │                       │ [Deterministic Slot Allocation: Breakfast/Lunch/Dinner/Snack]
     │                       │ [Nutrient transparency: uncalculated nutrition retained]
     │                       │                          │                          │
     │ 4. 200 OK (Schedule   │                          │                          │
     │    proposals)         │                          │                          │
     │◄──────────────────────┤                          │                          │
```

---

### 3.3 Workflow C: Recipe Nutrition Estimation
Resolves nutrient profiles for uncalculated recipes using authoritative USDA composition tables:

```
+──────────+         +────────────────+         +────────────────+         +────────────────+
|  CLIENT  |         | PLANNER (:8003)|         | RECIPE (:8002) |         | PROFILE (:8001)|
+──────────+         +────────────────+         +────────────────+         +────────────────+
     │                       │                          │                          │
     │ 1. Request recipe     │                          │                          │
     │    nutrition          │                          │                          │
     ├──────────────────────►│                          │                          │
     │                       │ 2. GET /recipes/{id}     │                          │
     │                       ├─────────────────────────►│                          │
     │                       │ 3. Return ingredients    │                          │
     │                       │◄─────────────────────────┤                          │
     │                       │                                                     │
     │                       │ 4. POST /nutrition/recipes/estimate                 │
     │                       │    (structured ingredients with parsed quantities)  │
     │                       ├────────────────────────────────────────────────────►│
     │                       │                                                     │
     │                       │ 5. Return totals, coverage %, and status            │
     │                       │    ('calculated', 'partial', or 'uncalculated')     │
     │                       │◄────────────────────────────────────────────────────┤
     │ 6. 200 OK (Nutrient   │                          │                          │
     │    breakdown)         │                          │                          │
     │◄──────────────────────┤                          │                          │
```

---

## 4. HTTP Client Timeouts & Resilient Failure Handling

To prevent cascading failures across microservices on student hardware:
- **Inter-Service Timeout**: Synchronous HTTP calls between services (using Python `httpx`) enforce a strict **3.0 second connection and read timeout**.
- **Graceful Degradation**:
  - If Recipe Service is unreachable during pantry matching, Planner returns HTTP `502 Bad Gateway` with error code `SERVICE_UNAVAILABLE`.
  - If Profile Service is unreachable during meal plan generation, Planner proceeds with recipe scheduling without caloric constraints, adding a warning note in the response payload.
  - No circuit breaker libraries or message queues are introduced, avoiding fragile architectural bloat.

---

## 5. Representative Request & Response Payloads

### 5.1 Biometrics Calculation (`POST /api/v1/biometrics/calculate`)
```http
POST /api/v1/biometrics/calculate HTTP/1.1
Host: localhost:8001
Content-Type: application/json

{
  "age_years": 28,
  "sex_for_equation": "male",
  "height_cm": 182.0,
  "weight_kg": 80.0,
  "activity_level": "moderately_active",
  "goal": "maintain"
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "bmi": 24.15,
  "bmi_category": "normal_weight",
  "bmr_kcal": 1802.5,
  "tdee_kcal": 2793.88,
  "target_calories_kcal": 2794,
  "formula": "mifflin_st_jeor",
  "activity_multiplier": 1.55,
  "goal": "maintain",
  "goal_adjustment_kcal": 0,
  "macro_targets_grams": {
    "protein_g": 140,
    "carbohydrates_g": 349,
    "fat_g": 93
  },
  "macro_ranges_percent": {
    "protein": { "min_pct": 10, "max_pct": 35 },
    "carbohydrates": { "min_pct": 45, "max_pct": 65 },
    "fat": { "min_pct": 20, "max_pct": 35 }
  },
  "caveats": [
    "BMR calculated using the Mifflin-St Jeor equation (1990).",
    "TDEE applies physical activity level factor 1.55 (moderately active).",
    "Macronutrient target distribution is 20% protein, 50% carbohydrates, and 30% fat based on NutriPod default macro distribution."
  ],
  "disclaimer": "These calculated estimates are provided strictly for educational and culinary planning purposes. They do not constitute medical diagnosis, clinical advice, or individualized nutritional prescription."
}
```

---

### 5.2 Recipe Search (`GET /api/v1/recipes/search`)
```http
GET /api/v1/recipes/search?q=chicken&cuisine=Italian&limit=2 HTTP/1.1
Host: localhost:8002
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "data": [
    {
      "id": "rcp_foodcom_5421",
      "source_dataset": "food_com",
      "source_id": "5421",
      "title": "Classic Rosemary Garlic Roasted Chicken",
      "description": "Succulent whole roasted chicken infused with fresh rosemary and roasted garlic cloves.",
      "prep_time_minutes": 15,
      "cook_time_minutes": 60,
      "total_time_minutes": 75,
      "servings": 4,
      "cuisine": "Italian",
      "source_url": "https://www.food.com/recipe/rosemary-chicken-5421",
      "rating_average": 4.75,
      "rating_count": 28,
      "tag_preview": ["dinner", "chicken", "poultry", "roast", "gluten-free"]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 2,
    "total_items": 42,
    "total_pages": 21
  }
}
```

---

### 5.3 Pantry Matching (`POST /api/v1/pantry/match`)
```http
POST /api/v1/pantry/match HTTP/1.1
Host: localhost:8003
Content-Type: application/json

{
  "ingredients": [
    "chicken thighs",
    "garlic",
    "olive oil",
    "fresh rosemary"
  ],
  "exclude_pantry_staples": true,
  "min_match_pct": 50.0,
  "limit": 1
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "matches": [
    {
      "recipe_id": "rcp_foodcom_5421",
      "title": "Classic Rosemary Garlic Roasted Chicken",
      "match_pct": 75.0,
      "matched_ingredients": [
        "chicken thighs",
        "garlic",
        "olive oil"
      ],
      "missing_ingredients": [
        "fresh rosemary"
      ],
      "total_recipe_ingredients": 4,
      "total_time_minutes": 75,
      "rating_average": 4.75
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 1,
    "total_items": 8,
    "total_pages": 8
  }
}
```

