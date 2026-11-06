"""PostgreSQL repository for meal_planner schema tables."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import psycopg

from services.common.database import ServiceDatabaseManager
from services.recommendation_planner.config import settings
from services.recommendation_planner.schemas import (
    GuestSessionResponse,
    MealPlanDetail,
    MealPlanSlotDetail,
    PantryItem,
    SavedMealPlanSummary,
    SaveMealPlanRequest,
    ShoppingListCategoryGroup,
    ShoppingListItem,
    ShoppingListResponse,
    SlotCookingProgressUpdate,
    UpdatePantryItemInput,
)

logger = logging.getLogger(f"foodflow.{settings.service_name}")


class PlannerRepository:
    """Encapsulates all SQL persistence for the recommendation and meal planner service."""

    def __init__(self, db_manager: ServiceDatabaseManager) -> None:
        self.db = db_manager

    # =========================================================================
    # GUEST SESSIONS
    # =========================================================================

    def create_guest_session(self, ttl_days: int = 30) -> GuestSessionResponse:
        """Create a new anonymous guest session token in meal_planner.guest_sessions."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meal_planner.guest_sessions (expires_at)
                    VALUES (NOW() + (%s || ' days')::INTERVAL)
                    RETURNING id, created_at, expires_at, last_active_at;
                    """,
                    (str(ttl_days),),
                )
                r = cur.fetchone()
                session_id = str(r[0])
                created_at = r[1]
                expires_at = r[2]
                last_active_at = r[3]

                # Initialize empty pantry session for convenience
                cur.execute(
                    """
                    INSERT INTO meal_planner.pantry_sessions (guest_session_id)
                    VALUES (%s);
                    """,
                    (session_id,),
                )
                conn.commit()

                return GuestSessionResponse(
                    session_id=session_id,
                    created_at=created_at,
                    expires_at=expires_at,
                    last_active_at=last_active_at,
                )

    def get_guest_session(self, session_id: str) -> Optional[GuestSessionResponse]:
        """Fetch an existing guest session, verifying it exists and has not expired."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, created_at, expires_at, last_active_at
                    FROM meal_planner.guest_sessions
                    WHERE id = %s;
                    """,
                    (session_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None

                expires_at: datetime = r[2]
                if expires_at < datetime.now(timezone.utc):
                    logger.info("Guest session %s has expired at %s", session_id, expires_at)
                    return None

                return GuestSessionResponse(
                    session_id=str(r[0]),
                    created_at=r[1],
                    expires_at=r[2],
                    last_active_at=r[3],
                )

    def touch_guest_session(self, session_id: str) -> Optional[GuestSessionResponse]:
        """Update last_active_at timestamp for a valid, non-expired session."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE meal_planner.guest_sessions
                    SET last_active_at = NOW()
                    WHERE id = %s AND expires_at > NOW()
                    RETURNING id, created_at, expires_at, last_active_at;
                    """,
                    (session_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None
                conn.commit()

                return GuestSessionResponse(
                    session_id=str(r[0]),
                    created_at=r[1],
                    expires_at=r[2],
                    last_active_at=r[3],
                )

    # =========================================================================
    # PANTRY INVENTORY
    # =========================================================================

    def _get_or_create_pantry_session(self, cur: psycopg.Cursor, guest_session_id: str) -> str:
        """Helper to get existing or create new pantry session id."""
        cur.execute(
            """
            SELECT id FROM meal_planner.pantry_sessions
            WHERE guest_session_id = %s;
            """,
            (guest_session_id,),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])

        cur.execute(
            """
            INSERT INTO meal_planner.pantry_sessions (guest_session_id)
            VALUES (%s)
            RETURNING id;
            """,
            (guest_session_id,),
        )
        return str(cur.fetchone()[0])

    def get_pantry_items(self, guest_session_id: str) -> List[PantryItem]:
        """Retrieve all active pantry items for a given guest session."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT psi.id, psi.raw_name, psi.canonical_ingredient_id, psi.created_at
                    FROM meal_planner.pantry_session_items psi
                    JOIN meal_planner.pantry_sessions ps ON ps.id = psi.pantry_session_id
                    WHERE ps.guest_session_id = %s
                    ORDER BY psi.id ASC;
                    """,
                    (guest_session_id,),
                )
                return [
                    PantryItem(
                        id=r[0],
                        raw_name=r[1],
                        canonical_ingredient_id=r[2],
                        created_at=r[3],
                    )
                    for r in cur.fetchall()
                ]

    def replace_pantry_items(
        self,
        guest_session_id: str,
        items: List[UpdatePantryItemInput],
    ) -> List[PantryItem]:
        """Replace the entire pantry contents for a guest session atomically."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                pantry_id = self._get_or_create_pantry_session(cur, guest_session_id)

                # Clear existing items
                cur.execute(
                    """
                    DELETE FROM meal_planner.pantry_session_items
                    WHERE pantry_session_id = %s;
                    """,
                    (pantry_id,),
                )

                if not items:
                    conn.commit()
                    return []

                # Deduplicate by raw_name (case-insensitive) to adhere to unique constraint
                seen: set[str] = set()
                unique_items: List[UpdatePantryItemInput] = []
                for it in items:
                    clean = it.raw_name.strip()
                    if clean.lower() not in seen:
                        seen.add(clean.lower())
                        unique_items.append(it)

                result_items: List[PantryItem] = []
                for it in unique_items:
                    cur.execute(
                        """
                        INSERT INTO meal_planner.pantry_session_items
                            (pantry_session_id, raw_name, canonical_ingredient_id)
                        VALUES (%s, %s, %s)
                        RETURNING id, raw_name, canonical_ingredient_id, created_at;
                        """,
                        (pantry_id, it.raw_name.strip(), it.canonical_ingredient_id),
                    )
                    r = cur.fetchone()
                    result_items.append(
                        PantryItem(
                            id=r[0],
                            raw_name=r[1],
                            canonical_ingredient_id=r[2],
                            created_at=r[3],
                        )
                    )

                conn.commit()
                return result_items

    # =========================================================================
    # MEAL PLANS
    # =========================================================================

    def create_meal_plan(
        self,
        guest_session_id: str,
        plan_data: SaveMealPlanRequest,
    ) -> SavedMealPlanSummary:
        """Create and persist a multi-day meal plan with scheduled recipe slots."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO meal_planner.meal_plans (guest_session_id, name, target_calories_kcal, days)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, name, days, created_at;
                    """,
                    (
                        guest_session_id,
                        plan_data.name.strip(),
                        plan_data.target_calories_kcal,
                        plan_data.days,
                    ),
                )
                r = cur.fetchone()
                plan_id = str(r[0])
                plan_name = r[1]
                days = r[2]
                created_at = r[3]

                # Insert slots (deduplicated by entry key to respect constraint)
                seen_slots: set[tuple[int, str, str]] = set()
                for slot in plan_data.slots:
                    slot_key = (slot.day_index, slot.slot_type, slot.recipe_id)
                    if slot_key in seen_slots:
                        continue
                    seen_slots.add(slot_key)

                    cur.execute(
                        """
                        INSERT INTO meal_planner.meal_plan_slots
                            (plan_id, day_index, slot_type, recipe_id, recipe_title, cooking_status)
                        VALUES (%s, %s, %s, %s, %s, 'pending');
                        """,
                        (
                            plan_id,
                            slot.day_index,
                            slot.slot_type,
                            slot.recipe_id,
                            slot.recipe_title.strip(),
                        ),
                    )

                conn.commit()
                return SavedMealPlanSummary(
                    plan_id=plan_id,
                    name=plan_name,
                    days=days,
                    created_at=created_at,
                )

    def get_meal_plan(
        self,
        plan_id: str,
        guest_session_id: str,
    ) -> Optional[MealPlanDetail]:
        """Fetch complete meal plan details and scheduled slots owned by guest."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, target_calories_kcal, days, created_at, updated_at
                    FROM meal_planner.meal_plans
                    WHERE id = %s AND guest_session_id = %s;
                    """,
                    (plan_id, guest_session_id),
                )
                r = cur.fetchone()
                if not r:
                    return None

                plan_record = r
                cur.execute(
                    """
                    SELECT id, day_index, slot_type, recipe_id, recipe_title, cooking_status, status_updated_at
                    FROM meal_planner.meal_plan_slots
                    WHERE plan_id = %s
                    ORDER BY day_index ASC, slot_type ASC, id ASC;
                    """,
                    (plan_id,),
                )
                slots = [
                    MealPlanSlotDetail(
                        id=s[0],
                        day_index=s[1],
                        slot_type=s[2],
                        recipe_id=s[3],
                        recipe_title=s[4],
                        cooking_status=s[5],
                        status_updated_at=s[6],
                    )
                    for s in cur.fetchall()
                ]

                return MealPlanDetail(
                    id=str(plan_record[0]),
                    name=plan_record[1],
                    target_calories_kcal=plan_record[2],
                    days=plan_record[3],
                    slots=slots,
                    created_at=plan_record[4],
                    updated_at=plan_record[5],
                )

    def update_meal_plan(
        self,
        plan_id: str,
        guest_session_id: str,
        plan_data: SaveMealPlanRequest,
    ) -> Optional[MealPlanDetail]:
        """Replace schedule and parameters of an existing meal plan owned by guest."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE meal_planner.meal_plans
                    SET name = %s, target_calories_kcal = %s, days = %s, updated_at = NOW()
                    WHERE id = %s AND guest_session_id = %s
                    RETURNING id, name, target_calories_kcal, days, created_at, updated_at;
                    """,
                    (
                        plan_data.name.strip(),
                        plan_data.target_calories_kcal,
                        plan_data.days,
                        plan_id,
                        guest_session_id,
                    ),
                )
                r = cur.fetchone()
                if not r:
                    return None
                plan_record = r

                # Replace slots
                cur.execute("DELETE FROM meal_planner.meal_plan_slots WHERE plan_id = %s;", (plan_id,))

                # Invalidate existing shopping list to avoid stale grocery items
                cur.execute("DELETE FROM meal_planner.shopping_lists WHERE plan_id = %s;", (plan_id,))

                seen_slots: set[tuple[int, str, str]] = set()
                slots: List[MealPlanSlotDetail] = []
                for slot in plan_data.slots:
                    slot_key = (slot.day_index, slot.slot_type, slot.recipe_id)
                    if slot_key in seen_slots:
                        continue
                    seen_slots.add(slot_key)

                    cur.execute(
                        """
                        INSERT INTO meal_planner.meal_plan_slots
                            (plan_id, day_index, slot_type, recipe_id, recipe_title, cooking_status)
                        VALUES (%s, %s, %s, %s, %s, 'pending')
                        RETURNING id, day_index, slot_type, recipe_id, recipe_title, cooking_status, status_updated_at;
                        """,
                        (
                            plan_id,
                            slot.day_index,
                            slot.slot_type,
                            slot.recipe_id,
                            slot.recipe_title.strip(),
                        ),
                    )
                    s = cur.fetchone()
                    slots.append(
                        MealPlanSlotDetail(
                            id=s[0],
                            day_index=s[1],
                            slot_type=s[2],
                            recipe_id=s[3],
                            recipe_title=s[4],
                            cooking_status=s[5],
                            status_updated_at=s[6],
                        )
                    )

                conn.commit()
                return MealPlanDetail(
                    id=str(plan_record[0]),
                    name=plan_record[1],
                    target_calories_kcal=plan_record[2],
                    days=plan_record[3],
                    slots=slots,
                    created_at=plan_record[4],
                    updated_at=plan_record[5],
                )

    def delete_meal_plan(self, plan_id: str, guest_session_id: str) -> bool:
        """Delete a meal plan (cascades to slots and shopping list)."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM meal_planner.meal_plans
                    WHERE id = %s AND guest_session_id = %s
                    RETURNING id;
                    """,
                    (plan_id, guest_session_id),
                )
                deleted = cur.fetchone() is not None
                conn.commit()
                return deleted

    def update_slot_cooking_progress(
        self,
        plan_id: str,
        guest_session_id: str,
        updates: List[SlotCookingProgressUpdate],
    ) -> Optional[int]:
        """Update cooking execution status for specific slots belonging to this plan."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # Validate plan exists and belongs to guest
                cur.execute(
                    """
                    SELECT id FROM meal_planner.meal_plans
                    WHERE id = %s AND guest_session_id = %s;
                    """,
                    (plan_id, guest_session_id),
                )
                if not cur.fetchone():
                    return None

                updated_count = 0
                for u in updates:
                    cur.execute(
                        """
                        UPDATE meal_planner.meal_plan_slots
                        SET cooking_status = %s, status_updated_at = NOW()
                        WHERE id = %s AND plan_id = %s
                        RETURNING id;
                        """,
                        (u.cooking_status, u.slot_id, plan_id),
                    )
                    if cur.fetchone():
                        updated_count += 1
                    else:
                        # Slot does not belong to this plan
                        conn.rollback()
                        return None

                conn.commit()
                return updated_count

    # =========================================================================
    # SHOPPING LISTS
    # =========================================================================

    def get_or_create_shopping_list(
        self,
        plan_id: str,
        guest_session_id: str,
        items_to_create: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[ShoppingListResponse]:
        """Retrieve existing shopping list or generate one from provided aggregated ingredients."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Verify plan exists and is owned by guest
                cur.execute(
                    """
                    SELECT id FROM meal_planner.meal_plans
                    WHERE id = %s AND guest_session_id = %s;
                    """,
                    (plan_id, guest_session_id),
                )
                if not cur.fetchone():
                    return None

                # 2. Check for existing shopping list
                cur.execute(
                    """
                    SELECT id FROM meal_planner.shopping_lists
                    WHERE plan_id = %s;
                    """,
                    (plan_id,),
                )
                row = cur.fetchone()
                if row:
                    list_id = str(row[0])
                else:
                    if items_to_create is None:
                        return None

                    # Create new shopping list record
                    cur.execute(
                        """
                        INSERT INTO meal_planner.shopping_lists (plan_id)
                        VALUES (%s)
                        RETURNING id;
                        """,
                        (plan_id,),
                    )
                    list_id = str(cur.fetchone()[0])

                    # Insert items if provided
                    if items_to_create:
                        for it in items_to_create:
                            cur.execute(
                                """
                                INSERT INTO meal_planner.shopping_list_items
                                    (shopping_list_id, ingredient_name, quantity_display, category, checked)
                                VALUES (%s, %s, %s, %s, FALSE);
                                """,
                                (
                                    list_id,
                                    it["ingredient_name"],
                                    it.get("quantity_display"),
                                    it.get("category"),
                                ),
                            )
                    conn.commit()

                # 3. Load all items for this shopping list
                cur.execute(
                    """
                    SELECT id, ingredient_name, quantity_display, category, checked
                    FROM meal_planner.shopping_list_items
                    WHERE shopping_list_id = %s
                    ORDER BY id ASC;
                    """,
                    (list_id,),
                )
                rows = cur.fetchall()

                # Group items by category
                categories_dict: Dict[str, List[ShoppingListItem]] = {}
                total_items = len(rows)

                for r in rows:
                    cat = r[3] or "Other"
                    item = ShoppingListItem(
                        id=r[0],
                        ingredient_name=r[1],
                        quantity_display=r[2],
                        category=r[3],
                        checked=r[4],
                    )
                    if cat not in categories_dict:
                        categories_dict[cat] = []
                    categories_dict[cat].append(item)

                category_groups = [
                    ShoppingListCategoryGroup(category=k, items=v)
                    for k, v in categories_dict.items()
                ]

                return ShoppingListResponse(
                    id=list_id,
                    plan_id=plan_id,
                    categories=category_groups,
                    total_items=total_items,
                )

    def update_shopping_list_item(
        self,
        plan_id: str,
        item_id: int,
        guest_session_id: str,
        checked: bool,
    ) -> Optional[ShoppingListItem]:
        """Toggle or set the checked procurement state of a shopping list item."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE meal_planner.shopping_list_items sli
                    SET checked = %s
                    FROM meal_planner.shopping_lists sl
                    JOIN meal_planner.meal_plans mp ON mp.id = sl.plan_id
                    WHERE sli.id = %s
                      AND sli.shopping_list_id = sl.id
                      AND mp.id = %s
                      AND mp.guest_session_id = %s
                    RETURNING sli.id, sli.ingredient_name, sli.quantity_display, sli.category, sli.checked;
                    """,
                    (checked, item_id, plan_id, guest_session_id),
                )
                r = cur.fetchone()
                if not r:
                    return None
                conn.commit()

                return ShoppingListItem(
                    id=r[0],
                    ingredient_name=r[1],
                    quantity_display=r[2],
                    category=r[3],
                    checked=r[4],
                )
