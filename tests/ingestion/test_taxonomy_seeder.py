"""Unit and integration tests for canonical ingredient taxonomy definitions, validation, and seeding."""

import os
import unittest
from pathlib import Path

import psycopg

from ingestion.config import get_database_url
from ingestion.taxonomy.definitions import CANONICAL_SEED, CanonicalIngredientSeed
from ingestion.taxonomy.normalizer import (
    clean_ingredient_token,
    normalize_text,
    strip_quantity_unit_prefix,
)
from ingestion.taxonomy.seeder import TaxonomySeeder
from ingestion.taxonomy.validator import (
    ALLOWED_CATEGORIES,
    TaxonomyValidationError,
    validate_seed_package,
)


class TestTaxonomyDefinitionsAndValidation(unittest.TestCase):
    """Test seed definitions, schema integrity, and taxonomy validation constraints."""

    def test_01_canonical_seed_baseline_validates(self) -> None:
        """Area 1: Valid baseline CANONICAL_SEED passes validation without error."""
        try:
            validate_seed_package(CANONICAL_SEED)
        except TaxonomyValidationError as e:
            self.fail(f"Baseline CANONICAL_SEED failed validation: {e}")

    def test_02_duplicate_canonical_name_raises(self) -> None:
        """Area 2: Duplicate canonical ingredient names trigger TaxonomyValidationError."""
        bad_seed = [
            CanonicalIngredientSeed(name="garlic", category="Produce"),
            CanonicalIngredientSeed(name="garlic", category="Produce"),
        ]
        with self.assertRaises(TaxonomyValidationError) as ctx:
            validate_seed_package(bad_seed)
        self.assertIn("Duplicate canonical ingredient name", str(ctx.exception))

    def test_03_duplicate_synonym_across_items_raises(self) -> None:
        """Area 3: Duplicate synonyms across different canonical items trigger TaxonomyValidationError."""
        bad_seed = [
            CanonicalIngredientSeed(name="onion", category="Produce", aliases=["yellow onion"]),
            CanonicalIngredientSeed(name="shallot", category="Produce", aliases=["yellow onion"]),
        ]
        with self.assertRaises(TaxonomyValidationError) as ctx:
            validate_seed_package(bad_seed)
        self.assertIn("Alias collision", str(ctx.exception))

    def test_04_alias_collides_with_canonical_name_raises(self) -> None:
        """Area 4: Synonym colliding with an existing canonical name triggers TaxonomyValidationError."""
        bad_seed = [
            CanonicalIngredientSeed(name="garlic", category="Produce", aliases=["onion"]),
            CanonicalIngredientSeed(name="onion", category="Produce"),
        ]
        with self.assertRaises(TaxonomyValidationError) as ctx:
            validate_seed_package(bad_seed)
        self.assertIn("Alias collides with canonical ingredient name", str(ctx.exception))

    def test_05_invalid_category_raises(self) -> None:
        """Area 5: Unrecognized categorical classification triggers TaxonomyValidationError."""
        bad_seed = [
            CanonicalIngredientSeed(name="garlic", category="AlienCategory"),
        ]
        with self.assertRaises(TaxonomyValidationError) as ctx:
            validate_seed_package(bad_seed)
        self.assertIn("invalid category", str(ctx.exception))

    def test_06_compound_conjunction_in_name_raises(self) -> None:
        """Area 6: Conjunctions ('and', '&', 'or') in canonical names trigger error."""
        bad_seed = [
            CanonicalIngredientSeed(name="oil and vinegar", category="Pantry & Dry Goods"),
        ]
        with self.assertRaises(TaxonomyValidationError) as ctx:
            validate_seed_package(bad_seed)
        self.assertIn("compound conjunctions", str(ctx.exception))

    def test_07_empty_name_or_alias_raises(self) -> None:
        """Area 7: Empty or whitespace-only names and aliases trigger TaxonomyValidationError."""
        bad_seed_name = [CanonicalIngredientSeed(name="   ", category="Produce")]
        with self.assertRaises(TaxonomyValidationError):
            validate_seed_package(bad_seed_name)

        bad_seed_alias = [CanonicalIngredientSeed(name="garlic", category="Produce", aliases=[""])]
        with self.assertRaises(TaxonomyValidationError):
            validate_seed_package(bad_seed_alias)

    def test_08_mandatory_distinction_flour(self) -> None:
        """Area 8: Flour vs All-Purpose Flour must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("flour", names)
        self.assertIn("all-purpose flour", names)
        # Ensure 'all-purpose flour' is not an alias of 'flour'
        flour_item = next(c for c in CANONICAL_SEED if c.name == "flour")
        self.assertNotIn("all-purpose flour", flour_item.aliases)

    def test_09_mandatory_distinction_milk(self) -> None:
        """Area 9: Milk vs Whole Milk vs Skim Milk must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("milk", names)
        self.assertIn("whole milk", names)
        self.assertIn("skim milk", names)

    def test_10_mandatory_distinction_garlic(self) -> None:
        """Area 10: Garlic vs Garlic Powder must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("garlic", names)
        self.assertIn("garlic powder", names)
        garlic_item = next(c for c in CANONICAL_SEED if c.name == "garlic")
        self.assertNotIn("garlic powder", garlic_item.aliases)

    def test_11_mandatory_distinction_tomato(self) -> None:
        """Area 11: Tomato vs Tomato Paste vs Tomato Sauce must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("tomato", names)
        self.assertIn("tomato paste", names)
        self.assertIn("tomato sauce", names)

    def test_12_mandatory_distinction_pepper(self) -> None:
        """Area 12: Pepper vs Black Pepper vs White Pepper vs Chili Powder vs Paprika distinct."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("pepper", names)
        self.assertIn("black pepper", names)
        self.assertIn("white pepper", names)
        self.assertIn("chili powder", names)
        self.assertIn("paprika", names)

    def test_13_mandatory_distinction_butter(self) -> None:
        """Area 13: Butter vs Unsalted Butter vs Salted Butter must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        self.assertIn("butter", names)
        self.assertIn("unsalted butter", names)
        self.assertIn("salted butter", names)

    def test_14_mandatory_distinction_herbs(self) -> None:
        """Area 14: Fresh vs Dried herbs must be distinct canonical entities."""
        names = {c.name for c in CANONICAL_SEED}
        for herb in ["oregano", "basil", "parsley", "thyme", "rosemary"]:
            self.assertIn(herb, names, f"Fresh/generic herb '{herb}' missing")
            self.assertIn(f"dried {herb}", names, f"Dried herb 'dried {herb}' missing")

    def test_15_salt_and_pepper_strictly_excluded(self) -> None:
        """Area 15: Compound phrase 'salt and pepper' must not exist in canonicals or aliases."""
        for c in CANONICAL_SEED:
            self.assertNotIn("salt and pepper", c.name.lower())
            for a in c.aliases:
                self.assertNotIn("salt and pepper", a.lower())


class TestTaxonomyNormalizer(unittest.TestCase):
    """Test quantity/unit prefix stripping and token cleaning utilities."""

    def test_16_strip_quantity_and_unit_prefix(self) -> None:
        """Area 16: Normalizer strips common cooking quantities and units."""
        cases = [
            ("1 tsp. salt", "salt"),
            ("2 large eggs", "large eggs"),
            ("1/2 cup sugar", "sugar"),
            ("3 cloves garlic", "garlic"),
            ("1 (10 oz.) can tomato sauce", "tomato sauce"),
            ("1 1/2 cups all-purpose flour", "all-purpose flour"),
            ("1 lb. ground beef", "ground beef"),
            ("2 tablespoons olive oil", "olive oil"),
        ]
        for inp, expected in cases:
            res = strip_quantity_unit_prefix(inp)
            self.assertEqual(res, expected, f"Failed on input: '{inp}'")

    def test_17_identity_preservation_in_normalizer(self) -> None:
        """Area 17: Normalizer preserves core compound identity qualifiers."""
        self.assertEqual(strip_quantity_unit_prefix("garlic powder"), "garlic powder")
        self.assertEqual(strip_quantity_unit_prefix("baking powder"), "baking powder")
        self.assertEqual(strip_quantity_unit_prefix("baking soda"), "baking soda")
        self.assertEqual(strip_quantity_unit_prefix("1/4 tsp. black pepper"), "black pepper")
        self.assertEqual(strip_quantity_unit_prefix("salt and pepper"), "salt and pepper")


class TestTaxonomySeederLiveAndArtifacts(unittest.TestCase):
    """Test seeder artifact generation, dry-run rollback, and live database linking."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.db_url = get_database_url()
        if not cls.db_url:
            raise unittest.SkipTest("Database URL not available for live seeder tests.")
        cls.seeder = TaxonomySeeder(db_url=cls.db_url)

    def test_18_generate_seed_artifacts(self) -> None:
        """Area 18: Seeder generates all 5 required audit reports with valid schema."""
        artifacts = self.seeder.generate_seed_artifacts()
        required_keys = [
            "canonical_taxonomy_seed",
            "approved_synonyms",
            "excluded_mappings",
            "ingredient_linking_preview",
            "population_manifest",
        ]
        for key in required_keys:
            self.assertIn(key, artifacts)
            path = artifacts[key]
            self.assertTrue(path.exists(), f"Artifact missing: {path}")
            self.assertGreater(path.stat().st_size, 0, f"Artifact empty: {path}")

    def test_19_seeder_dry_run_simulation(self) -> None:
        """Area 19: Dry run executes full simulation without committing changes."""
        stats = self.seeder.seed(dry_run=True)
        self.assertEqual(stats["mode"], "dry_run")
        self.assertGreater(stats["canonical_inserted"], 0)
        self.assertGreater(stats["recipe_ingredients_linked"], 0)

    def test_20_seeder_live_apply_and_integrity(self) -> None:
        """Area 20: Live apply populates tables, resolves IDs, links ingredients, preserves columns."""
        stats = self.seeder.seed(dry_run=False)
        self.assertEqual(stats["mode"], "live")
        self.assertEqual(stats["canonical_inserted"], len(CANONICAL_SEED))
        self.assertGreater(stats["recipe_ingredients_linked"], 200000)

        # Verify live database state
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # 1. Total canonical ingredients
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.canonical_ingredients")
                canonical_count = cur.fetchone()[0]
                self.assertEqual(canonical_count, len(CANONICAL_SEED))

                # 2. Total synonyms
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.ingredient_synonyms")
                synonym_count = cur.fetchone()[0]
                self.assertGreater(synonym_count, 200)

                # 3. Foreign key sanity
                cur.execute("""
                    SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients
                    WHERE canonical_ingredient_id IS NOT NULL
                      AND canonical_ingredient_id NOT IN (
                          SELECT id FROM recipe_catalog.canonical_ingredients
                      )
                """)
                orphans = cur.fetchone()[0]
                self.assertEqual(orphans, 0, "Orphan canonical_ingredient_id references found!")

                # 4. Byte-for-byte preservation: original columns never corrupted
                cur.execute("""
                    SELECT COUNT(*) FROM recipe_catalog.recipe_ingredients
                    WHERE raw_text IS NULL OR LENGTH(raw_text) = 0 OR position IS NULL OR recipe_id IS NULL
                """)
                corrupted = cur.fetchone()[0]
                self.assertEqual(corrupted, 0, "Corrupted recipe_ingredients detected!")

    def test_21_identical_seed_repeated_safely_idempotent(self) -> None:
        """Area 21: Re-running baseline seeder is an idempotent no-op without modification."""
        stats = self.seeder.seed(dry_run=False)
        self.assertEqual(stats["canonical_inserted"], len(CANONICAL_SEED))
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.canonical_ingredients")
                self.assertEqual(cur.fetchone()[0], 106)
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.ingredient_synonyms")
                self.assertEqual(cur.fetchone()[0], 248)

    def test_22_existing_synonym_reassignment_aborts_with_conflict(self) -> None:
        """Area 22: Attempting to reassign an existing synonym to another canonical aborts."""
        # Reassign 'yellow onion' from 'onion' to 'shallot' in seed package
        seed = []
        for c in CANONICAL_SEED:
            if c.name == "onion":
                seed.append(
                    CanonicalIngredientSeed(
                        name=c.name,
                        category=c.category,
                        is_pantry_staple=c.is_pantry_staple,
                        aliases=[a for a in c.aliases if a != "yellow onion"],
                    )
                )
            elif c.name == "shallot":
                seed.append(
                    CanonicalIngredientSeed(
                        name=c.name,
                        category=c.category,
                        is_pantry_staple=c.is_pantry_staple,
                        aliases=c.aliases + ["yellow onion"],
                    )
                )
            else:
                seed.append(c)

        seeder = TaxonomySeeder(db_url=self.db_url, seed_items=seed)
        with self.assertRaises(TaxonomyValidationError) as ctx:
            seeder.seed(dry_run=False)
        self.assertIn("Synonym identity conflict", str(ctx.exception))
        self.assertIn("Silent reassignment is prohibited", str(ctx.exception))

    def test_23_existing_canonical_conflicting_category_aborts(self) -> None:
        """Area 23: Attempting to modify an existing canonical's category aborts."""
        seed = []
        for c in CANONICAL_SEED:
            if c.name == "onion":
                seed.append(
                    CanonicalIngredientSeed(
                        name=c.name,
                        category="Pantry & Dry Goods",  # Baseline is Produce
                        is_pantry_staple=c.is_pantry_staple,
                        aliases=c.aliases,
                    )
                )
            else:
                seed.append(c)

        seeder = TaxonomySeeder(db_url=self.db_url, seed_items=seed)
        with self.assertRaises(TaxonomyValidationError) as ctx:
            seeder.seed(dry_run=False)
        self.assertIn("Canonical metadata conflict", str(ctx.exception))
        self.assertIn("category", str(ctx.exception))

    def test_24_existing_canonical_conflicting_pantry_staple_aborts(self) -> None:
        """Area 24: Attempting to change an existing canonical's is_pantry_staple flag aborts."""
        seed = []
        for c in CANONICAL_SEED:
            if c.name == "onion":
                seed.append(
                    CanonicalIngredientSeed(
                        name=c.name,
                        category=c.category,
                        is_pantry_staple=False,  # Baseline is True
                        aliases=c.aliases,
                    )
                )
            else:
                seed.append(c)

        seeder = TaxonomySeeder(db_url=self.db_url, seed_items=seed)
        with self.assertRaises(TaxonomyValidationError) as ctx:
            seeder.seed(dry_run=False)
        self.assertIn("Canonical metadata conflict", str(ctx.exception))
        self.assertIn("is_pantry_staple", str(ctx.exception))

    def test_25_conflict_causes_complete_transaction_rollback(self) -> None:
        """Area 25: Conflict midway through seed package triggers 100% atomic transaction rollback."""
        new_item = CanonicalIngredientSeed(
            name="test_temp_herb_xyz",
            category="Produce",
            aliases=["test_temp_alias_xyz"],
        )
        seed = [new_item]
        for c in CANONICAL_SEED:
            if c.name == "onion":
                seed.append(
                    CanonicalIngredientSeed(
                        name=c.name,
                        category="Pantry & Dry Goods",  # Causes metadata conflict
                        is_pantry_staple=c.is_pantry_staple,
                        aliases=c.aliases,
                    )
                )
            else:
                seed.append(c)

        seeder = TaxonomySeeder(db_url=self.db_url, seed_items=seed)
        with self.assertRaises(TaxonomyValidationError):
            seeder.seed(dry_run=False)

        # Verify nothing from item 1 was committed to the persistent database
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM recipe_catalog.canonical_ingredients WHERE name = 'test_temp_herb_xyz';"
                )
                self.assertEqual(cur.fetchone()[0], 0, "Uncommitted canonical leaked past rollback!")
                cur.execute(
                    "SELECT COUNT(*) FROM recipe_catalog.ingredient_synonyms WHERE synonym = 'test_temp_alias_xyz';"
                )
                self.assertEqual(cur.fetchone()[0], 0, "Uncommitted synonym leaked past rollback!")

