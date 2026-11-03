# FoodFlow — Product Requirements Document (PRD)

| Metadata | Details |
| :--- | :--- |
| **Document Version** | 1.0.0 |
| **Status** | Approved Blueprint (Pre-Implementation) |
| **Target Audience** | Engineering Team (Members 1, 2, 3), Academic Supervisors, Evaluators |
| **System Identity** | FoodFlow — Editorial Culinary Discovery & Cooking Platform |

---

## 1. Executive Summary & Core Philosophy

### 1.1 Purpose
FoodFlow is a comprehensive recipe discovery, pantry matching, and meal planning platform built with transparent, science-backed health personalization. It serves home cooks seeking culinary inspiration, kitchen efficiency, and nutritional clarity.

### 1.2 Core Product Philosophy
FoodFlow is built on the principle of **unconditional utility without forced onboarding**:
- **First-Class Anonymous Access**: A user must never be forced to register, authenticate, or input personal biological data to discover recipes, perform complex searches, view detailed ingredient breakdowns, or utilize the interactive cooking mode.
- **Opt-In Personalization**: Health profiles, biometric calculations, and goal-oriented dietary recommendations exist as an optional utility layer. 
- **Scientific Integrity & Zero Fabrication**: Nutritional facts are derived transparently from authoritative sources (USDA FoodData Central and curated Food.com datasets). If nutritional values cannot be determined for a recipe, FoodFlow explicitly indicates that the data is *uncalculated* rather than generating plausible synthetic numbers.
- **Editorial Craftsmanship**: The platform rejects the visual cliches of modern SaaS dashboards (translucent cards, gradients, floating pill buttons, neon accents) in favor of an authoritative, high-contrast culinary publication aesthetic.

---

## 2. User Personas & Core Journeys

```
+--------------------------------------------------------------------------------------------------+
|                                  FOODFLOW USER EXPERIENCE MODES                                  |
+--------------------------------------------------------------------------------------------------+
                                                   │
         ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
         ▼                                                                                   ▼
+───────────────────────────────────────────────────+   +───────────────────────────────────────────────────+
|               MODE A: UNRESTRICTED GUEST          |   |             MODE B: PERSONALIZED HEALTH           |
|            (Default - No Login Required)          |   |              (Optional - Opt-In Only)             |
+───────────────────────────────────────────────────+   +───────────────────────────────────────────────────+
| • Search & explore ~2.4M recipes                  |   | • Store biometric profile (Age, Height, Weight)   |
| • Filter by cuisine, time, diet, ingredient       |   | • Calculate precise BMI, BMR & TDEE               |
| • Access step-by-step interactive cooking mode    |   | • Set caloric targets (Deficit, Maintenance, Gain)|
| • Match on-hand pantry ingredients                |   | • Screen recipes against personalized macro goals |
| • Build temporary meal plans & shopping lists     |   | • Persist meal plans across browser sessions      |
+───────────────────────────────────────────────────+   +───────────────────────────────────────────────────+
```

### 2.1 Persona Archetypes

1. **The Spontaneous Cook (Elena, 24)**: Wants quick dinner ideas based on 4 random ingredients remaining in her refrigerator. Elena will not sign up or download an app; she needs instant search, pantry matching, and clear instructions.
2. **The Mindful Athlete (Marcus, 31)**: Seeks high-protein, calorie-controlled meals to support muscle gain. Marcus opts into entering his weight, height, and activity level to see transparent caloric targets and recipes that match his macro goals.
3. **The Household Meal Planner (David, 42)**: Needs to organize dinners for a 4-person family for the work week, minimize food waste, and automatically generate a consolidated grocery shopping list.

### 2.2 End-to-End User Journeys

#### Journey 1: Guest Culinary Discovery & Cooking Execution
1. Elena visits FoodFlow. She lands directly on the curated editorial showcase (no modal walls or login banners).
2. She searches for "mushroom risotto", toggling the filter for `< 45 mins` and `Vegetarian`.
3. The catalog returns paginated results sorted by rating and relevance.
4. She clicks a recipe card to view the detail page: ingredients with measurements where available in source data, instructions, estimated prep time (if reported), and source-reported or estimated nutrition indicators (with missing values clearly identified as uncalculated).
5. She clicks **"Start Cooking Mode"**: the screen transitions to a high-contrast, distraction-free view with large typography, step tracking, and ingredient checklists.

#### Journey 2: Pantry Cleanout & Ingredient Overlap
1. Elena has chicken breast, canned tomatoes, garlic, and onions.
2. She navigates to the **Pantry Matcher** tab and inputs her four ingredients.
3. The Recommendation and Meal Planner Service receives the request, normalizes inputs via the Recipe and Ingredient Service's normalization API (e.g., "garlic clove" $\rightarrow$ "garlic"), and queries recipes by canonical ingredients.
4. The system presents candidate recipes sorted by **Match Percentage**:
   - Recipe A (Chicken Cacciatore): 90% Match — *Missing: Rosemary, Olive Oil*.
   - Recipe B (Quick Tomato Chicken Skillet): 100% Match — *All on hand*.
5. Missing ingredients are visually highlighted with one-click options to add them to a shopping list.

#### Journey 3: Health-Conscious Biometric Calibration (Opt-In)
1. Marcus opts to configure a Health Profile.
2. He enters his biological metrics: Male ($s = +5$), 28 years old, 182 cm, 80 kg, Moderately Active (Physical Activity Level multiplier $1.55$), Goal: Lean Muscle Gain ($+300\text{ kcal/day}$ surplus).
3. The system computes his baseline metrics using the Mifflin-St Jeor formula and transparently displays:
   - **BMI**: $24.2\text{ kg/m}^2$ ($80 / 1.82^2 \approx 24.15\text{ kg/m}^2$, within standard WHO adult normal range 18.5–24.9; framed strictly as an anthropometric screening ratio, not a clinical diagnosis or body fat measurement).
   - **BMR (Basal Metabolic Rate Estimate)**: $1,802.5\text{ kcal/day}$ ($10 \times 80 + 6.25 \times 182 - 5 \times 28 + 5 = 800 + 1137.5 - 140 + 5$).
   - **TDEE (Total Daily Energy Expenditure Estimate)**: $2,793.9\text{ kcal/day}$ ($1802.5 \times 1.55$).
   - **Target Daily Caloric Intake**: $3,093.9\text{ kcal/day}$ ($2793.9 + 300\text{ kcal/day}$ surplus; with recommended macro split: 20–30% Protein, 45–55% Carbs, 25–30% Fat).
4. Marcus searches recipes; search results display an editorial nutritional badge indicating how each serving aligns with his personal calorie budget (e.g., "Provides ~28% of target meal calories"). Marcus notes that BMR and TDEE are labeled as estimates based on transparent mathematical assumptions.

#### Journey 4: Structured Weekly Meal Planning & Shopping Generation
1. David plans meals for Monday through Wednesday.
2. He assigns recipes to slots: Monday Dinner, Tuesday Lunch, Tuesday Dinner, Wednesday Dinner.
3. He opens the **Generated Shopping List**. The Recommendation and Meal Planner Service aggregates ingredients across all 4 recipes:
   - Identifies overlapping items (e.g., combines 2 onions from Recipe 1 with 1 onion from Recipe 2 $\rightarrow$ "3 Yellow Onions").
   - Organizes ingredients into pantry staples vs produce vs proteins.
4. David checks off items he already owns and saves/prints the final list.

---

## 3. Detailed Functional Requirements (Three Backend Service Modules)

The functional requirements are partitioned strictly across the three independently implemented backend services:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    SERVICE OWNERSHIP BOUNDARIES                                  |
+───────────────────────────────────┬───────────────────────────────────┬──────────────────────────+
| SERVICE MODULE 1                  | SERVICE MODULE 2                  | SERVICE MODULE 3         |
| Profile & Nutrition (Member 1)    | Recipe & Ingredient (Member 2)    | Recommendation & Planner |
+───────────────────────────────────┼───────────────────────────────────┼──────────────────────────+
| • Optional user biometric profile | • Multi-source recipe catalogue   | • Pantry inventory input |
| • BMI calculation & WHO limits    | • Lexical full-text search        | • Overlap match scoring  |
| • Mifflin-St Jeor BMR & TDEE      | • Faceted filtering (tags/time)   | • Missing ingredient ID  |
| • Caloric targets (gain/loss/maint)| • Scalable pagination            | • Pantry staple toggles  |
| • USDA ingredient nutrient lookup | • Recipe details (nullable fields)| • Structured meal plans  |
| • Nutrition transparency policy   | • Step-by-step cooking mode       | • Automated plan builder |
| • Medical disclaimers             | • Historical ratings & reviews    | • Shopping list aggregate|
|                                   | • Ingredient taxonomy/synonyms    | • Progress tracking      |
|                                   | • Batch recipe retrieval API      |                          |
+───────────────────────────────────┴───────────────────────────────────┴──────────────────────────+
```

### 3.1 Service Module 1: Profile & Nutrition Service
*Primary Responsibility: Team Member 1 | Port: 8001 | Database Schema: `profile_nutrition`*

| ID | Requirement | Detailed Specification | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FR-NUT-01** | **Optional User Profile** | Allow entry of biological metrics: Age (years), Biological Sex (for BMR equation coefficient), Height (cm), Weight (kg), and Physical Activity Level (PAL). Explicitly optional; platform is 100% functional without a profile. | If biological sex or other inputs are withheld, sex-specific BMR calculation is omitted. |
| **FR-NUT-02** | **BMI Calculation & Limitations** | Calculate Body Mass Index: $$\text{BMI} = \frac{\text{weight (kg)}}{(\text{height (m)})^2}$$ BMI is an anthropometric ratio independent of sex-specific BMR coefficients. Neutrally display WHO adult classification categories (Underweight $< 18.5$, Normal $18.5\text{--}24.9$, Overweight $25.0\text{--}29.9$, Obese $\ge 30.0$). | Display clear disclaimer clarifying that BMI is a general population screening ratio and does not directly measure body composition or fat-to-muscle distribution. |
| **FR-NUT-03** | **Estimated BMR & TDEE Calculations** | Compute estimated Basal Metabolic Rate using the **Mifflin-St Jeor** formula:<br>• Male: $\text{BMR} = (10 \times W) + (6.25 \times H) - (5 \times A) + 5$<br>• Female: $\text{BMR} = (10 \times W) + (6.25 \times H) - (5 \times A) - 161$<br>Multiply by defined Physical Activity Level (PAL) factors:<br>• Sedentary: $1.2$<br>• Lightly Active: $1.375$<br>• Moderately Active: $1.55$<br>• Very Active: $1.725$<br>• Extra Active: $1.9$ | BMR and TDEE are labeled strictly as mathematical estimates, not clinical diagnostic measurements. Formula coefficients and inputs are transparently presented. |
| **FR-NUT-04** | **Caloric Target Adjustment** | Support user fitness goals:<br>• Maintenance: $\text{Target} = \text{TDEE}$<br>• Weight Loss: Deficit of $-300\text{ to } -500\text{ kcal/day}$<br>• Weight Gain: Surplus of $+300\text{ to } +500\text{ kcal/day}$ | Display transparent daily caloric budget with balanced macronutrient guideline ranges (Protein 10–35%, Carbs 45–65%, Fat 20–35%). |
| **FR-NUT-05** | **USDA Ingredient Nutrient Lookups** | Provide internal REST endpoints to look up food items in the USDA FoodData Central database (`profile_nutrition.usda_*` tables) to retrieve verified macro- and micronutrient quantities per 100g. | Queries return per-100g nutrient breakdowns for mapped canonical ingredients. |
| **FR-NUT-06** | **Nutrition Transparency & Zero Fabrication** | Preserve raw Percentage Daily Values (PDV) from Food.com without presenting them as directly measured grams. If approximate grams are derived, clearly state the reference daily base and label as approximations. For RecipeNLG, nutrition can only be calculated when ingredient quantities, units, and USDA food mappings are sufficiently reliable; if reliable quantities are absent, return `status: "uncalculated"` with nulls. The 80% ingredient mapping threshold is treated as a provisional heuristic rule subject to validation. | Never fabricate missing nutritional values. Never label an estimate as independently "USDA-verified". |
| **FR-NUT-07** | **Permanent Medical Disclaimer** | Embed a permanent, non-dismissible editorial disclaimer across all health views stating: *"FoodFlow provides nutritional estimates for educational and culinary planning purposes only. It is not medical or dietary advice."* | Disclaimer is visible across all profile, calculation, and meal plan views. |

---

### 3.2 Service Module 2: Recipe & Ingredient Service
*Primary Responsibility: Team Member 2 | Port: 8002 | Database Schema: `recipe_catalog`*

| ID | Requirement | Detailed Specification | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FR-REC-01** | **Multi-Source Broad Catalogue** | Ingest and store recipes from RecipeNLG (~2.23M records) and Food.com (~231k records). The platform must operate as a broad, general-purpose cooking resource—spanning everyday weeknight meals, comfort dishes, regional and international cuisines, baking, desserts, snacks, and beverages—rather than a narrow health-only tool. Preserve original source identifiers (`source_id`, `source_dataset`) without collisions. | System maintains immutable source provenance for every recipe record. |
| **FR-REC-02** | **Full-Text Lexical & Trigram Search** | Lexical search across recipe titles, descriptions, and ingredients using PostgreSQL `tsvector` and `tsquery` with GIN indexing, complemented by `pg_trgm` title similarity for typo tolerance. Scored search must prioritize exact title matches ahead of fuzzy or approximate results. If no exact match exists, display a clear empty state with related catalogue suggestions; never fabricate synthetic matches. | Search executes efficiently (benchmark target: $< 200\text{ ms}$ under local testing conditions). Exact title queries rank at position 1. |
| **FR-REC-03** | **Faceted Filtering on Available Metadata** | Support combinable filters operating strictly on available or defensibly derived metadata: prep time thresholds (where reported in Food.com), dietary tags, cuisine tags, and category tags. | Filters operate only on available fields; missing fields are treated as unknown rather than fabricated. |
| **FR-REC-04** | **Scalable Pagination** | Implement deterministic cursor/keyset or offset-limit pagination with user-selectable page sizes (12, 24, 48 items/page). | Browsing scales efficiently across the dataset without database timeout. |
| **FR-REC-05** | **Recipe Detail View with Nullable Fields** | Display title, description, prep time, cook time, total time, servings, structured ingredients, numbered instructions, and source credit. Make prep time, cook time, servings, cuisine, and nutrition fields explicitly nullable. | Missing source metadata is displayed as unavailable rather than fabricated with false defaults. |
| **FR-REC-06** | **Interactive Step-by-Step Cooking Mode** | Provide a distraction-free cooking interface presenting instructions step-by-step with large typography, step progression markers, and an ingredient reference panel. | User can navigate steps sequentially without page reloads. |
| **FR-REC-07** | **Historical Ratings & Reviews** | Surface aggregated user ratings (average star rating and total review count) preserved from the Food.com interaction dataset. | Recipes with historical reviews display average rating; unrated recipes display "Unrated" (no false 5-star defaults). |
| **FR-REC-08** | **Ingredient Taxonomy & Normalization** | Maintain canonical ingredient dictionary and synonym table. Expose internal REST endpoint (`POST /api/v1/ingredients/normalize`) to map raw ingredient strings (e.g., "minced garlic cloves") to canonical tokens (e.g., "garlic"). | Canonical taxonomy belongs exclusively to Member 2 and is consumed by Member 3 via REST. |
| **FR-REC-09** | **Batch Recipe Retrieval API** | Expose internal REST endpoint (`POST /api/v1/recipes/batch`) allowing Service 3 to fetch recipe summaries and ingredient lists for multiple recipe IDs in a single HTTP request. | Enables Service 3 to assemble meal plans and shopping lists without cross-schema database queries. |

---

### 3.3 Service Module 3: Recommendation & Meal Planner Service
*Primary Responsibility: Team Member 3 | Port: 8003 | Database Schema: `meal_planner`*

| ID | Requirement | Detailed Specification | Acceptance Criteria |
| :--- | :--- | :--- | :--- |
| **FR-PLN-01** | **Pantry Inventory Input** | Allow users to enter a list of 1 to 50 on-hand ingredients via an autocomplete-assisted input field. | Accepts and stores on-hand ingredients in user session or local storage. |
| **FR-PLN-02** | **Overlap & Match Scoring Algorithm** | Call Member 2's normalization endpoint (`POST /api/v1/ingredients/normalize`) to convert user pantry items into canonical tokens. Query candidate recipes from Member 2 and compute match percentage: $$\text{Match } \% = \left(\frac{|\text{Matched Canonical Ingredients}|}{|\text{Total Recipe Canonical Ingredients}|}\right) \times 100$$ | Candidate recipes are returned sorted in descending order of match percentage. |
| **FR-PLN-03** | **Missing Ingredient Identification** | Partition recipe ingredients into "In Your Pantry" vs "Missing / Need to Buy". | Missing ingredients are highlighted with an option to add them to a shopping list. |
| **FR-PLN-04** | **Pantry Staple Exclusions** | Allow basic pantry staples (salt, black pepper, water, cooking oil) to be marked as "Always Available" via a toggle, preventing them from penalizing match scores. | Toggling staple assumptions updates match scores dynamically. |
| **FR-PLN-05** | **Structured Meal Schedule** | Allow users to create 1-day or 7-day meal plans allocating recipes to 4 discrete slots: `Breakfast`, `Lunch`, `Dinner`, `Snack`. Store recipe ID references in `meal_planner.meal_plan_slots` without cross-schema foreign keys. | Users can assign recipes to target dates and slots; recipe metadata is fetched via Service 2 REST API. |
| **FR-PLN-06** | **Automated Plan Generation** | Provide a generation utility that queries Member 1 for target daily calories (if profile exists) and Member 2 for candidate recipes to build a daily meal plan fitting user constraints. | Produces a valid, non-overlapping schedule matching caloric and dietary criteria. |
| **FR-PLN-07** | **Consolidated Shopping List** | Aggregates all ingredients across scheduled recipes into a consolidated grocery list, combining identical items and categorizing them (Produce, Dairy, Pantry, Meat, Spices). | Clean consolidated list with checkable items and ability to add custom items. |
| **FR-PLN-08** | **Cooking Progress State** | Allow users to mark planned meals as "Cooked" or "Skipped", updating plan completion tracking. | Visual progress indicator reflects active schedule status. |

---

## 4. Food Photography & Editorial Image Strategy

Because RecipeNLG and Food.com datasets **do not provide an image bundle**, FoodFlow adopts an honest, authentic, and curated photography strategy to avoid false claims or misleading imagery:

```
+──────────────────────────────────────────────────────────────────────────────────────────────────+
|                                  EDITORIAL FOOD PHOTOGRAPHY STRATEGY                             |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
| 1. Curated Editorial Image Set:                                                                  |
|    • Sourced from open-license, high-resolution photography repositories (Unsplash / CC-BY).     |
|    • Dedicated editorial collection for home showcase, major cuisines, and meal categories.     |
|                                                                                                  |
| 2. Image Provenance & Attribution Manifest:                                                      |
|    • Maintain static asset manifest (images_manifest.json) recording:                            |
|      - Image filename / relative path                                                            |
|      - Photographer name & profile link                                                          |
|      - License type (e.g. Unsplash License / CC BY 4.0)                                          |
|      - Associated category tags (e.g., 'pasta', 'soup', 'salad', 'bakery')                       |
|                                                                                                  |
| 3. Honest Category Fallbacks:                                                                    |
|    • Where a specific recipe lacks an authentic photograph, the UI displays:                     |
|      - High-contrast editorial typography card with category badge, or                           |
|      - High-quality category mood photograph clearly labeled as a category illustration.         |
|    • Strictly NO false associations: Never claim a generic stock photo is the exact dish.        |
|    • Strictly NO AI-generated synthetic food illustrations.                                      |
+──────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 5. Visual Design & Typography Specifications

FoodFlow requires an **editorial culinary magazine aesthetic** rather than an interactive software dashboard. It should evoke the tactile authority of an independent food journal.

```
+--------------------------------------------------------------------------------------------------+
|                                    EDITORIAL DESIGN SYSTEM                                       |
+--------------------------------------------------------------------------------------------------+
| [SHARP EDGES ONLY]    border-radius: 0px !important (Cards, Inputs, Buttons, Dialogs)           |
| [NO GIMMICKS]         Zero Glassmorphism | Zero Gradients | Zero Neon Glows | Zero Pill Buttons   |
| [TYPOGRAPHY]          Display Serif (Newsreader/Playfair) + Functional Grotesque/Mono (Inter)   |
| [STRUCTURE]           Stark 1px Solid Borders | Editorial Column Grids | Generous White Space    |
+--------------------------------------------------------------------------------------------------+
```

### 5.1 Strict Design Directives

1. **Geometry — Strict 0px Border Radius**:
   - `border-radius: 0px` globally applied to all UI elements: cards, buttons, text inputs, dropdowns, dialogs, modals, tags, tooltips, and badges.
   - Strictly forbidden: rounded buttons (`rounded-md`, `rounded-full`), pill-shaped tags, rounded card corners.
2. **Surfacing & Lighting**:
   - Strictly forbidden: glassmorphism, translucent acrylic panels, backdrop filters (`backdrop-blur`), neon glow borders, floating elevation drop-shadows.
   - Depth must be established via stark `1px solid` architectural borders and crisp, high-contrast separation.
3. **Typography**:
   - **Display / Editorial Headings**: High-contrast, editorial serif font family (e.g., *Newsreader*, *Playfair Display*, or *Fraunces*).
   - **Body & Functional UI**: Crisp, legible grotesque sans-serif (e.g., *Inter*, *Public Sans*) paired with a tabular monospace for quantities, prep times, and nutritional numbers (e.g., *JetBrains Mono*, *Space Mono*).
4. **Theme Palettes (Light & Dark)**:
   - **Light Theme ("Culinary Newsprint")**:
     - Background: Warm off-white / parchment (`#F9F8F6`).
     - Card / Panel Surface: Crisp white (`#FFFFFF`).
     - Primary Typography: Deep ink charcoal (`#1A1918`).
     - Muted Text: Warm slate (`#5C5955`).
     - Borders & Dividers: Clean newspaper hairline (`#E2DFD8`).
     - Accent: Terracotta (`#C2410C`) or Deep Olive (`#3F4E28`).
   - **Dark Theme ("Dark Kitchen Atelier")**:
     - Background: Pure carbon / obsidian (`#121212`).
     - Card / Panel Surface: Deep matte graphite (`#1C1C1E`).
     - Primary Typography: Warm linen white (`#F2EFEB`).
     - Muted Text: Soft ash (`#8E8D8A`).
     - Borders & Dividers: Dark charcoal rule (`#2C2C2E`).
     - Accent: Warm amber (`#D97706`) or Muted Sage (`#606C38`).
5. **Imagery**:
   - Authentic, natural food photography with realistic kitchen lighting. No artificial, oversaturated, AI-generated surrealist food imagery.

---

## 6. Scope Management & Non-Goals

To guarantee successful delivery within a university semester, strict boundaries are enforced.

### 6.1 MVP Scope (Must Deliver)
- Ingestion of a validated development subset of USDA FoodData Central, RecipeNLG, and Food.com datasets (initial development target: 25,000 Food.com + 25,000 RecipeNLG clean recipes via stratified sampling preserving diverse cuisines and categories). Final target stages the full usable corpora (~231k Food.com and ~2.23M RecipeNLG records).
- Standalone recipe browsing, full-text search, multi-faceted filtering on available metadata, and recipe detail pages with step-by-step cooking mode.
- Pantry matching algorithm with overlap percentages and missing ingredient tracking via cross-service REST communication.
- Optional user profile with BMI, Mifflin-St Jeor BMR/TDEE calculations, and dietary preference filters.
- Daily/weekly meal planner and consolidated grocery shopping list generator.
- Local Podman Compose deployment (3 backend microservices + PostgreSQL + React frontend) and production Kubernetes manifests (`k8s/`).
- Complete light and dark editorial visual themes with strict 0px border radius.

### 6.2 Explicit Non-Goals (Out of Scope)
- **No Complex Social Networks**: No user follower graphs, social feeds, public comment threads, or direct messaging.
- **No Chatbots or Conversational Agents**: No generative AI chatbots ("Chef AI"), conversational recipe generators, or LLM-based assistants.
- **No Runtime Proprietary AI Dependencies**: Zero runtime calls to external Claude, OpenAI, or Gemini APIs. All recommendations, matching, and calculations must run deterministically on local infrastructure.
- **No Native Mobile Apps**: Web application only (responsive desktop-first design).
- **No Commercial E-commerce Integration**: No direct cart synchronization with grocery delivery platforms (Instacart, Amazon Fresh).
- **No Microservices Beyond the 3 Modules**: Maintain exactly the three specified backend services; do not fragment into separate auth, search, or notification microservices.
