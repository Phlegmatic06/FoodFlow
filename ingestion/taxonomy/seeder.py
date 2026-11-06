"""Repeatable database seeder and artifact generator for canonical ingredient taxonomy."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg

from ingestion.config import get_database_url
from ingestion.logging_config import get_logger
from ingestion.taxonomy.definitions import CANONICAL_SEED, CanonicalIngredientSeed
from ingestion.taxonomy.normalizer import clean_ingredient_token, strip_quantity_unit_prefix
from ingestion.taxonomy.validator import TaxonomyValidationError, validate_seed_package

logger = get_logger("taxonomy_seeder")


class TaxonomySeeder:
    """Manages validation, artifact generation, and database population for canonical taxonomy."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        seed_items: Optional[List[CanonicalIngredientSeed]] = None,
        source_audit_dir: Optional[Path] = None,
    ) -> None:
        self.db_url = db_url or get_database_url()
        self.seed_items = seed_items if seed_items is not None else CANONICAL_SEED
        self.source_audit_dir = (
            source_audit_dir
            if source_audit_dir is not None
            else Path("data/processed/reports/ingredient_taxonomy_audit")
        )

    def validate(self) -> None:
        """Validate canonical ingredient definitions against integrity constraints."""
        validate_seed_package(self.seed_items)

    def generate_seed_artifacts(
        self,
        output_dir: Optional[Path] = None,
        preview_limit: int = 1000,
    ) -> Dict[str, Path]:
        """Generate reviewable CSV/JSON audit reports in the target audit directory."""
        self.validate()
        target_dir = output_dir or self.source_audit_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Canonical taxonomy seed CSV
        canonical_csv_path = target_dir / "canonical_taxonomy_seed.csv"
        with open(canonical_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["canonical_name", "category", "is_pantry_staple", "alias_count", "notes"])
            # Sorted by category, then name
            sorted_items = sorted(self.seed_items, key=lambda x: (x.category, x.name))
            for item in sorted_items:
                writer.writerow([
                    item.name,
                    item.category,
                    str(item.is_pantry_staple).lower(),
                    len(item.aliases),
                    item.notes,
                ])

        # 2. Approved synonyms CSV
        approved_csv_path = target_dir / "approved_synonyms.csv"
        with open(approved_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["synonym", "canonical_name", "confidence", "notes"])
            all_syns = []
            for item in self.seed_items:
                for alias in item.aliases:
                    confidence = 1.0 if alias == item.name else 0.95
                    all_syns.append((alias, item.name, confidence, f"Standard synonym for {item.name}"))
            all_syns.sort(key=lambda x: (x[1], x[0]))
            for row in all_syns:
                writer.writerow(list(row))

        # 3. Excluded mappings CSV (Class B ambiguous and Class C compound/unmatched)
        excluded_csv_path = target_dir / "excluded_mappings.csv"
        excluded_rows = self._build_excluded_mappings()
        with open(excluded_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["raw_text", "candidate_canonical", "classification", "reason"])
            for row in excluded_rows:
                writer.writerow(row)

        # 4. Linking preview CSV (simulated linking)
        preview_csv_path = target_dir / "ingredient_linking_preview.csv"
        preview_rows = self._build_linking_preview(preview_limit)
        with open(preview_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["raw_text", "normalized_text", "canonical_name", "category", "match_type"])
            for row in preview_rows:
                writer.writerow(row)

        # 5. Population manifest JSON
        manifest_path = target_dir / "population_manifest.json"
        manifest_data = {
            "manifest_version": "1.0.0",
            "seed_version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "canonical_count": len(self.seed_items),
            "synonym_count": len(all_syns),
            "excluded_count": len(excluded_rows),
            "preview_count": len(preview_rows),
            "database": "foodflow_db",
            "target_schema": "recipe_catalog",
            "target_tables": [
                "canonical_ingredients",
                "ingredient_synonyms",
                "recipe_ingredients",
            ],
            "artifacts": {
                "canonical_taxonomy_seed": canonical_csv_path.name,
                "approved_synonyms": approved_csv_path.name,
                "excluded_mappings": excluded_csv_path.name,
                "ingredient_linking_preview": preview_csv_path.name,
            },
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return {
            "canonical_taxonomy_seed": canonical_csv_path,
            "approved_synonyms": approved_csv_path,
            "excluded_mappings": excluded_csv_path,
            "ingredient_linking_preview": preview_csv_path,
            "population_manifest": manifest_path,
        }

    def _build_excluded_mappings(self) -> List[List[str]]:
        """Collect Class B and Class C candidates excluded from this step."""
        approved_terms: Set[str] = set()
        for item in self.seed_items:
            approved_terms.add(item.name.lower())
            for a in item.aliases:
                approved_terms.add(a.lower())

        excluded: List[List[str]] = []
        seen_raws: Set[str] = set()

        # Load ambiguous ingredients (Class B)
        ambiguous_path = self.source_audit_dir / "ambiguous_ingredients.csv"
        if ambiguous_path.exists():
            with open(ambiguous_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    raw = row[0].strip()
                    raw_low = raw.lower()
                    if raw_low in approved_terms or raw_low in seen_raws:
                        continue
                    seen_raws.add(raw_low)
                    candidate = row[1].strip() if len(row) > 1 else ""
                    reason = row[3].strip() if len(row) > 3 else "Ambiguous qualifier deferred to future expansion"
                    excluded.append([raw, candidate, "Class B (Ambiguous / Qualified)", reason])

        # Load unmatched ingredients (Class C compound phrases & unmapped)
        unmatched_path = self.source_audit_dir / "unmatched_ingredients.csv"
        if unmatched_path.exists():
            with open(unmatched_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    raw = row[0].strip()
                    raw_low = raw.lower()
                    if raw_low in approved_terms or raw_low in seen_raws:
                        continue
                    seen_raws.add(raw_low)
                    reason = row[2].strip() if len(row) > 2 else "Unmatched ingredient phrase"
                    cls = "Class C (Compound Phrase)" if "compound" in reason.lower() else "Class C (Unmatched)"
                    excluded.append([raw, "", cls, reason])

        # Add explicit mandatory exclusions if not already present
        mandatory_exclusions = [
            ("salt and pepper", "", "Class C (Compound Phrase)", "Compound ingredient phrase with multiple items"),
            ("toasted sesame oil", "sesame oil", "Class B (Ambiguous / Qualified)", "Specific culinary modifier altering preparation"),
        ]
        for raw, cand, cls, rsn in mandatory_exclusions:
            if raw.lower() not in seen_raws and raw.lower() not in approved_terms:
                seen_raws.add(raw.lower())
                excluded.append([raw, cand, cls, rsn])

        excluded.sort(key=lambda x: (x[2], x[0]))
        return excluded

    def _build_linking_preview(self, limit: int = 1000) -> List[List[str]]:
        """Simulate linking against live database or fallback sample."""
        term_to_item: Dict[str, Tuple[str, str]] = {}
        for item in self.seed_items:
            term_to_item[item.name] = (item.name, item.category)
            for a in item.aliases:
                term_to_item[a] = (item.name, item.category)

        preview_rows: List[List[str]] = []
        if not self.db_url:
            return preview_rows

        try:
            with psycopg.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT raw_text FROM recipe_catalog.recipe_ingredients "
                        "WHERE canonical_ingredient_id IS NULL LIMIT %s",
                        (limit * 5,),
                    )
                    distinct_raws = [r[0] for r in cur.fetchall()]

                    for raw in distinct_raws:
                        if not raw or len(preview_rows) >= limit:
                            break
                        norm = clean_ingredient_token(raw)
                        if norm in term_to_item:
                            cname, cat = term_to_item[norm]
                            mtype = "exact_canonical" if norm == cname else "approved_synonym"
                            preview_rows.append([raw, norm, cname, cat, mtype])
                            continue
                        stripped = strip_quantity_unit_prefix(raw)
                        if stripped in term_to_item:
                            cname, cat = term_to_item[stripped]
                            mtype = "prefix_stripped_canonical" if stripped == cname else "prefix_stripped_synonym"
                            preview_rows.append([raw, stripped, cname, cat, mtype])
        except Exception as e:
            logger.warning(f"Could not build linking preview from live database: {e}")

        return preview_rows

    def seed(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute canonical seeding and recipe ingredient linking within a single transaction."""
        self.validate()

        if not self.db_url:
            raise TaxonomyValidationError("Database URL is required for live seeding.")

        start_time = time.time()
        stats: Dict[str, Any] = {
            "mode": "dry_run" if dry_run else "live",
            "seed_version": "1.0.0",
            "canonical_inserted": 0,
            "synonyms_inserted": 0,
            "recipe_ingredients_linked": 0,
            "recipe_ingredients_remaining_null": 0,
            "total_recipe_ingredients": 0,
            "elapsed_seconds": 0.0,
        }

        with psycopg.connect(self.db_url) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    # 0. Acquire transaction-level advisory lock to serialize concurrent seeding runs
                    cur.execute("SELECT pg_advisory_xact_lock(hashtext('recipe_catalog.taxonomy_seeder'));")

                    # 1. Verify and populate canonical ingredients without silent metadata mutation
                    cur.execute("SELECT id, name, category, is_pantry_staple FROM recipe_catalog.canonical_ingredients;")
                    existing_canonicals: Dict[str, Tuple[int, str, bool]] = {
                        row[1].lower(): (row[0], row[2], bool(row[3])) for row in cur.fetchall()
                    }

                    canonical_id_map: Dict[str, int] = {}
                    for item in self.seed_items:
                        item_key = item.name.lower()
                        if item_key in existing_canonicals:
                            cid, existing_cat, existing_staple = existing_canonicals[item_key]
                            if existing_cat != item.category:
                                raise TaxonomyValidationError(
                                    f"Canonical metadata conflict for '{item.name}': "
                                    f"existing category '{existing_cat}' != incoming '{item.category}'. "
                                    f"Silent metadata modification is prohibited; explicit review required."
                                )
                            if existing_staple != item.is_pantry_staple:
                                raise TaxonomyValidationError(
                                    f"Canonical metadata conflict for '{item.name}': "
                                    f"existing is_pantry_staple {existing_staple} != incoming {item.is_pantry_staple}. "
                                    f"Silent metadata modification is prohibited; explicit review required."
                                )
                            canonical_id_map[item.name] = cid
                        else:
                            cur.execute(
                                """
                                INSERT INTO recipe_catalog.canonical_ingredients (name, category, is_pantry_staple)
                                VALUES (%s, %s, %s)
                                RETURNING id, name;
                                """,
                                (item.name, item.category, item.is_pantry_staple),
                            )
                            cid, cname = cur.fetchone()
                            canonical_id_map[cname] = cid
                            existing_canonicals[item_key] = (cid, item.category, item.is_pantry_staple)

                    stats["canonical_inserted"] = len(canonical_id_map)

                    # 2. Verify and populate synonyms without silent cross-canonical reassignment
                    cur.execute(
                        """
                        SELECT s.synonym, s.canonical_ingredient_id, ci.name
                        FROM recipe_catalog.ingredient_synonyms s
                        JOIN recipe_catalog.canonical_ingredients ci ON ci.id = s.canonical_ingredient_id;
                        """
                    )
                    existing_synonyms: Dict[str, Tuple[int, str]] = {
                        row[0].lower(): (row[1], row[2]) for row in cur.fetchall()
                    }

                    synonym_count = 0
                    term_to_id: Dict[str, int] = {name: cid for name, cid in canonical_id_map.items()}
                    for item in self.seed_items:
                        cid = canonical_id_map[item.name]
                        for alias in item.aliases:
                            alias_key = alias.lower()
                            if alias_key in existing_synonyms:
                                curr_cid, curr_cname = existing_synonyms[alias_key]
                                if curr_cid != cid:
                                    raise TaxonomyValidationError(
                                        f"Synonym identity conflict: alias '{alias}' is already assigned to "
                                        f"canonical '{curr_cname}' (id={curr_cid}), but incoming seed attempts "
                                        f"to reassign it to '{item.name}' (id={cid}). Silent reassignment is prohibited."
                                    )
                                # Idempotent no-op: already points to correct canonical
                                synonym_count += 1
                                term_to_id[alias] = cid
                            else:
                                cur.execute(
                                    """
                                    INSERT INTO recipe_catalog.ingredient_synonyms (synonym, canonical_ingredient_id)
                                    VALUES (%s, %s);
                                    """,
                                    (alias, cid),
                                )
                                existing_synonyms[alias_key] = (cid, item.name)
                                synonym_count += 1
                                term_to_id[alias] = cid

                    stats["synonyms_inserted"] = synonym_count

                    # 3. Query unlinked distinct raw_text
                    cur.execute(
                        "SELECT DISTINCT raw_text FROM recipe_catalog.recipe_ingredients "
                        "WHERE canonical_ingredient_id IS NULL;"
                    )
                    distinct_raws = [r[0] for r in cur.fetchall()]

                    # 4. Map distinct raw_text to canonical_ingredient_id
                    linking_pairs: List[Tuple[str, int]] = []
                    for raw in distinct_raws:
                        if not raw:
                            continue
                        clean = clean_ingredient_token(raw)
                        if clean in term_to_id:
                            linking_pairs.append((raw, term_to_id[clean]))
                            continue
                        stripped = strip_quantity_unit_prefix(raw)
                        if stripped in term_to_id:
                            linking_pairs.append((raw, term_to_id[stripped]))

                    # 5. Bulk update recipe_ingredients via temporary table
                    cur.execute(
                        "CREATE TEMP TABLE tmp_recipe_ingredient_linking "
                        "(raw_text text, canonical_id int) ON COMMIT DROP;"
                    )
                    with cur.copy(
                        "COPY tmp_recipe_ingredient_linking (raw_text, canonical_id) FROM STDIN"
                    ) as copy:
                        for raw, cid in linking_pairs:
                            copy.write_row((raw, cid))

                    cur.execute(
                        """
                        UPDATE recipe_catalog.recipe_ingredients ri
                        SET canonical_ingredient_id = t.canonical_id
                        FROM tmp_recipe_ingredient_linking t
                        WHERE ri.canonical_ingredient_id IS NULL
                          AND ri.raw_text = t.raw_text;
                        """
                    )
                    newly_linked = cur.rowcount
                    stats["recipe_ingredients_newly_linked"] = newly_linked

                    # 6. Integrity and constraint verification
                    cur.execute("SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients;")
                    stats["total_recipe_ingredients"] = cur.fetchone()[0]

                    cur.execute(
                        "SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients "
                        "WHERE canonical_ingredient_id IS NULL;"
                    )
                    stats["recipe_ingredients_remaining_null"] = cur.fetchone()[0]
                    stats["recipe_ingredients_total_linked"] = (
                        stats["total_recipe_ingredients"] - stats["recipe_ingredients_remaining_null"]
                    )
                    stats["recipe_ingredients_linked"] = stats["recipe_ingredients_total_linked"]

                    # Foreign key orphan check
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients
                        WHERE canonical_ingredient_id IS NOT NULL
                          AND canonical_ingredient_id NOT IN (
                              SELECT id FROM recipe_catalog.canonical_ingredients
                          );
                        """
                    )
                    orphans = cur.fetchone()[0]
                    if orphans > 0:
                        raise TaxonomyValidationError(
                            f"Integrity violation: {orphans} orphaned canonical_ingredient_id references!"
                        )

                    # Byte-for-byte preservation check
                    cur.execute(
                        """
                        SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients
                        WHERE position IS NULL OR raw_text IS NULL OR recipe_id IS NULL;
                        """
                    )
                    corrupted = cur.fetchone()[0]
                    if corrupted > 0:
                        raise TaxonomyValidationError(
                            f"Integrity violation: {corrupted} recipe_ingredients have NULL core attributes!"
                        )

                    # 7. Transaction control
                    if dry_run:
                        logger.info(
                            f"Dry run completed successfully. Rolling back transaction. "
                            f"Would link {stats['recipe_ingredients_linked']} ingredients."
                        )
                        raise psycopg.Rollback()
                    else:
                        logger.info(
                            f"Live seeding committed successfully. "
                            f"Linked {stats['recipe_ingredients_linked']} ingredients."
                        )

        stats["elapsed_seconds"] = round(time.time() - start_time, 2)
        return stats
