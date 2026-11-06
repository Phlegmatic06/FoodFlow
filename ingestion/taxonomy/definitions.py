"""Authoritative Canonical Ingredient Seed Definitions and Classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

SEED_VERSION = "1.0.0"

@dataclass(frozen=True)
class CanonicalIngredientSeed:
    """Definition of an authoritative canonical ingredient."""

    name: str
    category: str
    is_pantry_staple: bool = False
    aliases: List[str] = field(default_factory=list)
    notes: str = ""


# Curated baseline canonical seed data adhering strictly to Step 04.5B-2 identity rules:
# 1. Flour vs All-Purpose Flour are distinct.
# 2. Milk vs Whole Milk vs Skim Milk are distinct.
# 3. Garlic vs Garlic Powder are distinct (garlic cloves is an alias of garlic).
# 4. Tomato vs Tomato Paste vs Tomato Sauce are distinct.
# 5. Black Pepper vs White Pepper vs generic Pepper vs Chili Powder vs Paprika are distinct.
# 6. Salt and Pepper compound phrase is strictly excluded (unmatched).
# 7. Salted vs Unsalted vs generic Butter are distinct.
# 8. Fresh vs Dried herbs are distinct.
CANONICAL_SEED: List[CanonicalIngredientSeed] = [
    # -------------------------------------------------------------------------
    # Produce - Vegetables
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="onion",
        category="Produce",
        is_pantry_staple=True,
        aliases=["onions", "yellow onion", "white onion", "yellow onions", "white onions", "sweet onion", "sweet onions"],
        notes="Standard fresh culinary allium."
    ),
    CanonicalIngredientSeed(
        name="green onion",
        category="Produce",
        is_pantry_staple=False,
        aliases=["green onions", "scallions", "scallion", "spring onion", "spring onions"],
        notes="Allium fistulosum; distinct from mature dry onion."
    ),
    CanonicalIngredientSeed(
        name="shallot",
        category="Produce",
        is_pantry_staple=False,
        aliases=["shallots", "fresh shallot", "fresh shallots"],
        notes="Allium cepa var. aggregatum."
    ),
    CanonicalIngredientSeed(
        name="garlic",
        category="Produce",
        is_pantry_staple=True,
        aliases=["garlic cloves", "cloves of garlic", "fresh garlic", "clove garlic", "garlic clove", "whole garlic"],
        notes="Fresh garlic bulbs/cloves. Distinct from garlic powder."
    ),
    CanonicalIngredientSeed(
        name="tomato",
        category="Produce",
        is_pantry_staple=False,
        aliases=["tomatoes", "fresh tomato", "fresh tomatoes", "ripe tomato", "ripe tomatoes", "red tomato", "red tomatoes"],
        notes="Fresh botanical tomato. Paste and sauce are separate."
    ),
    CanonicalIngredientSeed(
        name="potato",
        category="Produce",
        is_pantry_staple=False,
        aliases=["potatoes", "russet potato", "russet potatoes", "baking potato", "baking potatoes", "white potato", "white potatoes"],
        notes="Standard culinary potatoes."
    ),
    CanonicalIngredientSeed(
        name="carrot",
        category="Produce",
        is_pantry_staple=False,
        aliases=["carrots", "fresh carrot", "fresh carrots"],
        notes="Daucus carota."
    ),
    CanonicalIngredientSeed(
        name="celery",
        category="Produce",
        is_pantry_staple=False,
        aliases=["celery ribs", "celery stalks", "celery rib", "celery stalk", "fresh celery"],
        notes="Apium graveolens."
    ),
    CanonicalIngredientSeed(
        name="bell pepper",
        category="Produce",
        is_pantry_staple=False,
        aliases=["bell peppers", "green bell pepper", "green bell peppers", "red bell pepper", "red bell peppers", "sweet bell pepper", "sweet bell peppers"],
        notes="Sweet Capsicum annuum."
    ),
    CanonicalIngredientSeed(
        name="spinach",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh spinach", "baby spinach", "spinach leaves", "fresh baby spinach"],
        notes="Spinacia oleracea."
    ),
    CanonicalIngredientSeed(
        name="mushroom",
        category="Produce",
        is_pantry_staple=False,
        aliases=["mushrooms", "white mushrooms", "button mushrooms", "cremini mushrooms", "fresh mushrooms"],
        notes="Standard edible Agaricus bisporus."
    ),
    CanonicalIngredientSeed(
        name="zucchini",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh zucchini", "zucchinis", "courgette", "courgettes"],
        notes="Summer squash."
    ),
    CanonicalIngredientSeed(
        name="cucumber",
        category="Produce",
        is_pantry_staple=False,
        aliases=["cucumbers", "fresh cucumber"],
        notes="Cucumis sativus."
    ),
    CanonicalIngredientSeed(
        name="avocado",
        category="Produce",
        is_pantry_staple=False,
        aliases=["avocados", "haas avocado", "hass avocado", "fresh avocado"],
        notes="Persea americana."
    ),
    CanonicalIngredientSeed(
        name="ginger",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh ginger", "ginger root", "fresh ginger root"],
        notes="Fresh rhizome; distinct from ginger powder."
    ),
    CanonicalIngredientSeed(
        name="cabbage",
        category="Produce",
        is_pantry_staple=False,
        aliases=["green cabbage", "fresh cabbage", "head cabbage"],
        notes="Brassica oleracea var. capitata."
    ),
    CanonicalIngredientSeed(
        name="broccoli",
        category="Produce",
        is_pantry_staple=False,
        aliases=["broccoli florets", "fresh broccoli"],
        notes="Brassica oleracea var. italica."
    ),
    CanonicalIngredientSeed(
        name="cauliflower",
        category="Produce",
        is_pantry_staple=False,
        aliases=["cauliflower florets", "fresh cauliflower"],
        notes="Brassica oleracea var. botrytis."
    ),

    # -------------------------------------------------------------------------
    # Produce - Fruits
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="lemon",
        category="Produce",
        is_pantry_staple=False,
        aliases=["lemons", "fresh lemon", "fresh lemons"],
        notes="Whole fresh citrus fruit."
    ),
    CanonicalIngredientSeed(
        name="lemon juice",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh lemon juice"],
        notes="Extracted culinary citrus juice."
    ),
    CanonicalIngredientSeed(
        name="lime",
        category="Produce",
        is_pantry_staple=False,
        aliases=["limes", "fresh lime", "fresh limes"],
        notes="Whole fresh lime fruit."
    ),
    CanonicalIngredientSeed(
        name="lime juice",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh lime juice"],
        notes="Extracted culinary lime juice."
    ),
    CanonicalIngredientSeed(
        name="apple",
        category="Produce",
        is_pantry_staple=False,
        aliases=["apples", "fresh apple", "fresh apples"],
        notes="Malus domestica."
    ),
    CanonicalIngredientSeed(
        name="banana",
        category="Produce",
        is_pantry_staple=False,
        aliases=["bananas", "ripe banana", "ripe bananas"],
        notes="Musa acuminata."
    ),
    CanonicalIngredientSeed(
        name="orange",
        category="Produce",
        is_pantry_staple=False,
        aliases=["oranges", "fresh orange", "fresh oranges"],
        notes="Citrus sinensis fruit."
    ),
    CanonicalIngredientSeed(
        name="orange juice",
        category="Produce",
        is_pantry_staple=False,
        aliases=["fresh orange juice"],
        notes="Citrus sinensis juice."
    ),
    CanonicalIngredientSeed(
        name="strawberry",
        category="Produce",
        is_pantry_staple=False,
        aliases=["strawberries", "fresh strawberries"],
        notes="Fragaria ananassa."
    ),
    CanonicalIngredientSeed(
        name="blueberry",
        category="Produce",
        is_pantry_staple=False,
        aliases=["blueberries", "fresh blueberries"],
        notes="Vaccinium corymbosum."
    ),

    # -------------------------------------------------------------------------
    # Dairy & Refrigerated
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="butter",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=["sweet butter"],
        notes="Standard dairy butter baseline."
    ),
    CanonicalIngredientSeed(
        name="unsalted butter",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=["sweet unsalted butter"],
        notes="Explicit unsalted dairy butter; distinct from salted butter."
    ),
    CanonicalIngredientSeed(
        name="salted butter",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=[],
        notes="Explicit salted dairy butter."
    ),
    CanonicalIngredientSeed(
        name="milk",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=[],
        notes="Generic dairy milk."
    ),
    CanonicalIngredientSeed(
        name="whole milk",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=["regular milk", "full fat milk"],
        notes="3.25% milkfat whole dairy milk."
    ),
    CanonicalIngredientSeed(
        name="skim milk",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["nonfat milk", "fat free milk", "fat-free milk"],
        notes="Nonfat dairy milk."
    ),
    CanonicalIngredientSeed(
        name="buttermilk",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["cultured buttermilk"],
        notes="Cultured acidified milk."
    ),
    CanonicalIngredientSeed(
        name="heavy cream",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["heavy whipping cream", "whipping cream"],
        notes="High-fat fluid cream (>36% fat)."
    ),
    CanonicalIngredientSeed(
        name="sour cream",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["cultured sour cream"],
        notes="Cultured fermented cream."
    ),
    CanonicalIngredientSeed(
        name="yogurt",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["plain yogurt", "plain whole milk yogurt"],
        notes="Cultured plain milk yogurt."
    ),
    CanonicalIngredientSeed(
        name="egg",
        category="Dairy & Refrigerated",
        is_pantry_staple=True,
        aliases=["eggs", "large egg", "large eggs", "whole egg", "whole eggs"],
        notes="Whole chicken egg."
    ),
    CanonicalIngredientSeed(
        name="egg white",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["egg whites", "large egg white", "large egg whites"],
        notes="Albumen only."
    ),
    CanonicalIngredientSeed(
        name="egg yolk",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["egg yolks", "large egg yolk", "large egg yolks"],
        notes="Yolk only."
    ),
    CanonicalIngredientSeed(
        name="cheddar cheese",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["shredded cheddar cheese", "sharp cheddar cheese", "mild cheddar cheese", "cheddar"],
        notes="Cheddar curd cheese."
    ),
    CanonicalIngredientSeed(
        name="parmesan cheese",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["grated parmesan cheese", "parmesan", "shredded parmesan cheese"],
        notes="Parmigiano-reggiano style hard grating cheese."
    ),
    CanonicalIngredientSeed(
        name="mozzarella cheese",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["shredded mozzarella cheese", "part-skim mozzarella cheese", "mozzarella"],
        notes="Pasta filata curd cheese."
    ),
    CanonicalIngredientSeed(
        name="cream cheese",
        category="Dairy & Refrigerated",
        is_pantry_staple=False,
        aliases=["philadelphia cream cheese"],
        notes="Soft fresh acid-coagulated cheese."
    ),

    # -------------------------------------------------------------------------
    # Pantry & Dry Goods
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="water",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["cold water", "warm water", "boiling water", "hot water", "tap water"],
        notes="Potable culinary water."
    ),
    CanonicalIngredientSeed(
        name="sugar",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["granulated sugar", "white sugar", "table sugar", "granulated white sugar"],
        notes="Refined sucrose baseline."
    ),
    CanonicalIngredientSeed(
        name="brown sugar",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["light brown sugar", "dark brown sugar", "packed brown sugar"],
        notes="Sucrose with molasses; distinct from granulated white sugar."
    ),
    CanonicalIngredientSeed(
        name="powdered sugar",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["confectioners sugar", "confectioner's sugar", "icing sugar"],
        notes="Finely pulverized sucrose with starch."
    ),
    CanonicalIngredientSeed(
        name="olive oil",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["extra virgin olive oil", "extra-virgin olive oil", "pure olive oil", "virgin olive oil"],
        notes="Olea europaea fruit oil."
    ),
    CanonicalIngredientSeed(
        name="vegetable oil",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["cooking oil"],
        notes="Refined plant cooking oil."
    ),
    CanonicalIngredientSeed(
        name="canola oil",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["pure canola oil"],
        notes="Rapeseed low-erucic oil."
    ),
    CanonicalIngredientSeed(
        name="sesame oil",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=[],
        notes="Sesamum indicum seed oil; toasted sesame oil is excluded as Class B modifier."
    ),
    CanonicalIngredientSeed(
        name="honey",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["pure honey", "clover honey"],
        notes="Natural floral bee nectar."
    ),
    CanonicalIngredientSeed(
        name="soy sauce",
        category="Pantry & Dry Goods",
        is_pantry_staple=True,
        aliases=["light soy sauce", "shoyu"],
        notes="Fermented soy condiment."
    ),
    CanonicalIngredientSeed(
        name="mayonnaise",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["real mayonnaise"],
        notes="Oil and egg yolk emulsion."
    ),
    CanonicalIngredientSeed(
        name="mustard",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["yellow mustard", "prepared mustard"],
        notes="Generic prepared condiment."
    ),
    CanonicalIngredientSeed(
        name="dijon mustard",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["dijon"],
        notes="French style mustard with white wine."
    ),
    CanonicalIngredientSeed(
        name="worcestershire sauce",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=[],
        notes="Fermented vinegar and tamarind condiment."
    ),
    CanonicalIngredientSeed(
        name="tomato paste",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=[],
        notes="Dehydrated concentrated tomato paste; distinct from fresh tomato."
    ),
    CanonicalIngredientSeed(
        name="tomato sauce",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["canned tomato sauce"],
        notes="Cooked pureed seasoned tomato sauce; distinct from fresh tomato."
    ),
    CanonicalIngredientSeed(
        name="chicken broth",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["chicken stock"],
        notes="Poultry liquid base."
    ),
    CanonicalIngredientSeed(
        name="beef broth",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["beef stock"],
        notes="Bovine liquid base."
    ),
    CanonicalIngredientSeed(
        name="vegetable broth",
        category="Pantry & Dry Goods",
        is_pantry_staple=False,
        aliases=["vegetable stock"],
        notes="Plant liquid base."
    ),

    # -------------------------------------------------------------------------
    # Bakery & Grains
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="flour",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["plain flour", "white flour"],
        notes="Generic flour baseline. Kept distinct from all-purpose flour per mandate."
    ),
    CanonicalIngredientSeed(
        name="all-purpose flour",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["all purpose flour", "unbleached all-purpose flour", "bleached all-purpose flour"],
        notes="Explicit all-purpose wheat flour; distinct from generic flour."
    ),
    CanonicalIngredientSeed(
        name="baking powder",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=[],
        notes="Complete chemical leavening mixture with acid; distinct from baking soda."
    ),
    CanonicalIngredientSeed(
        name="baking soda",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["bicarbonate of soda"],
        notes="Pure sodium bicarbonate; distinct from baking powder."
    ),
    CanonicalIngredientSeed(
        name="cornstarch",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["corn starch"],
        notes="Zea mays endosperm starch."
    ),
    CanonicalIngredientSeed(
        name="cocoa powder",
        category="Bakery & Grains",
        is_pantry_staple=False,
        aliases=["unsweetened cocoa powder", "unsweetened cocoa", "baking cocoa"],
        notes="Unsweetened defatted cocoa solids."
    ),
    CanonicalIngredientSeed(
        name="white rice",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["long grain white rice", "jasmine rice", "basmati rice", "uncooked white rice"],
        notes="Milled polished Oryza sativa."
    ),
    CanonicalIngredientSeed(
        name="brown rice",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["long grain brown rice", "uncooked brown rice"],
        notes="Whole grain Oryza sativa with bran layer."
    ),
    CanonicalIngredientSeed(
        name="pasta",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["dry pasta", "spaghetti", "macaroni", "penne", "fettuccine", "rigatoni"],
        notes="Dry extruded semolina pasta baseline."
    ),
    CanonicalIngredientSeed(
        name="bread crumbs",
        category="Bakery & Grains",
        is_pantry_staple=False,
        aliases=["breadcrumbs", "dry bread crumbs", "plain bread crumbs"],
        notes="Dried pulverized bread crumb mixture."
    ),
    CanonicalIngredientSeed(
        name="rolled oats",
        category="Bakery & Grains",
        is_pantry_staple=True,
        aliases=["oats", "old fashioned oats", "oatmeal"],
        notes="Steamed and flaked Avena sativa groats."
    ),

    # -------------------------------------------------------------------------
    # Meat & Seafood
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="chicken breast",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["chicken breasts", "boneless chicken breast", "boneless chicken breasts", "boneless skinless chicken breast", "boneless skinless chicken breasts"],
        notes="Poultry white meat."
    ),
    CanonicalIngredientSeed(
        name="chicken thigh",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["chicken thighs", "boneless chicken thighs", "boneless skinless chicken thighs"],
        notes="Poultry dark meat cut."
    ),
    CanonicalIngredientSeed(
        name="ground beef",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["lean ground beef", "minced beef", "extra lean ground beef"],
        notes="Comminuted bovine muscle tissue."
    ),
    CanonicalIngredientSeed(
        name="bacon",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["bacon strips", "thick cut bacon", "thick-cut bacon"],
        notes="Cured smoked pork belly."
    ),
    CanonicalIngredientSeed(
        name="pork chop",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["pork chops", "center cut pork chops"],
        notes="Fresh swine loin rib cut."
    ),
    CanonicalIngredientSeed(
        name="salmon",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["salmon fillet", "salmon fillets", "fresh salmon"],
        notes="Salmo salar wild or farmed fish."
    ),
    CanonicalIngredientSeed(
        name="shrimp",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["raw shrimp", "fresh shrimp", "large shrimp"],
        notes="Decapod crustacean."
    ),
    CanonicalIngredientSeed(
        name="tuna",
        category="Meat & Seafood",
        is_pantry_staple=False,
        aliases=["canned tuna", "tuna fish", "chunk light tuna"],
        notes="Thunnus canned fish."
    ),

    # -------------------------------------------------------------------------
    # Spices & Seasonings
    # -------------------------------------------------------------------------
    CanonicalIngredientSeed(
        name="salt",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["table salt", "kosher salt", "sea salt", "fine salt", "coarse salt"],
        notes="Standard culinary sodium chloride."
    ),
    CanonicalIngredientSeed(
        name="black pepper",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["ground black pepper", "fresh ground black pepper", "freshly ground black pepper", "cracked black pepper"],
        notes="Piper nigrum ground black peppercorn; distinct from white pepper and paprika."
    ),
    CanonicalIngredientSeed(
        name="pepper",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["ground pepper"],
        notes="Generic culinary pepper descriptor."
    ),
    CanonicalIngredientSeed(
        name="white pepper",
        category="Spices & Seasonings",
        is_pantry_staple=False,
        aliases=["ground white pepper"],
        notes="Piper nigrum without outer fruit pericarp; distinct from black pepper."
    ),
    CanonicalIngredientSeed(
        name="garlic powder",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Dehydrated ground allium; distinct from fresh garlic."
    ),
    CanonicalIngredientSeed(
        name="onion powder",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Dehydrated ground allium; distinct from fresh onion."
    ),
    CanonicalIngredientSeed(
        name="cinnamon",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["ground cinnamon"],
        notes="Cinnamomum verum or cassia bark."
    ),
    CanonicalIngredientSeed(
        name="vanilla extract",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["pure vanilla extract", "vanilla"],
        notes="Alcoholic vanilla bean maceration."
    ),
    CanonicalIngredientSeed(
        name="paprika",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["sweet paprika"],
        notes="Ground Capsicum annuum powder; distinct from chili pepper."
    ),
    CanonicalIngredientSeed(
        name="cayenne pepper",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["cayenne", "ground cayenne pepper", "cayenne powder"],
        notes="Capsicum frutescens pungent ground powder."
    ),
    CanonicalIngredientSeed(
        name="chili powder",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Blend of ground chilis and spices."
    ),
    CanonicalIngredientSeed(
        name="cumin",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["ground cumin"],
        notes="Cuminum cyminum dried ground seeds."
    ),
    CanonicalIngredientSeed(
        name="oregano",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["fresh oregano"],
        notes="Origanum vulgare fresh herb."
    ),
    CanonicalIngredientSeed(
        name="dried oregano",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Origanum vulgare dehydrated herb; distinct from fresh oregano."
    ),
    CanonicalIngredientSeed(
        name="basil",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["fresh basil"],
        notes="Ocimum basilicum fresh leaf."
    ),
    CanonicalIngredientSeed(
        name="dried basil",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Ocimum basilicum dehydrated leaf; distinct from fresh basil."
    ),
    CanonicalIngredientSeed(
        name="parsley",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["fresh parsley"],
        notes="Petroselinum crispum fresh leaf."
    ),
    CanonicalIngredientSeed(
        name="dried parsley",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["parsley flakes"],
        notes="Petroselinum crispum dehydrated leaf; distinct from fresh parsley."
    ),
    CanonicalIngredientSeed(
        name="thyme",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["fresh thyme"],
        notes="Thymus vulgaris fresh herb."
    ),
    CanonicalIngredientSeed(
        name="dried thyme",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Thymus vulgaris dehydrated herb; distinct from fresh thyme."
    ),
    CanonicalIngredientSeed(
        name="rosemary",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["fresh rosemary"],
        notes="Salvia rosmarinus fresh herb."
    ),
    CanonicalIngredientSeed(
        name="dried rosemary",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=[],
        notes="Salvia rosmarinus dehydrated herb; distinct from fresh rosemary."
    ),
    CanonicalIngredientSeed(
        name="nutmeg",
        category="Spices & Seasonings",
        is_pantry_staple=True,
        aliases=["ground nutmeg"],
        notes="Myristica fragrans ground kernel."
    )
]
