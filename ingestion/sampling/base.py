"""NutriPod Unified Sampling Engine - Base Primitives & Reservoir Samplers

Provides deterministic reservoir sampling, proportional stratum quota allocation
(Hamilton-Hare largest remainder method with minimum representation), and
streaming data structures for memory-bounded dataset subsampling.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, List, Optional, Sequence, Tuple, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class StratumMetadata:
    """Descriptor for a single sampling stratum."""
    stratum_id: str
    population_count: int
    target_quota: int
    selected_count: int = 0

    @property
    def population_share(self) -> float:
        return 0.0

    @property
    def sample_share(self) -> float:
        return 0.0


def derive_stratum_seed(base_seed: int, stratum_id: str) -> int:
    """Derive a stable, platform- and process-independent 31-bit seed for a stratum.
    
    Uses SHA-256 on the UTF-8 encoded stratum identifier to avoid Python's
    process-randomized hash() implementation (SipHash / PYTHONHASHSEED).
    
    Algorithm:
      1. Canonical UTF-8 encode stratum_id.
      2. Compute sha256 digest.
      3. Convert first 8 bytes of digest to big-endian unsigned integer.
      4. Combine with base_seed using deterministic multiplier 1,000,003.
      5. Mask with 0x7FFFFFFF to yield a non-negative 31-bit integer.
    """
    digest = hashlib.sha256(stratum_id.encode("utf-8")).digest()
    stratum_hash_int = int.from_bytes(digest[:8], "big")
    return (base_seed * 1000003 + stratum_hash_int) & 0x7FFFFFFF


def allocate_proportional_quotas(
    stratum_counts: Dict[str, int],
    target_total: int,
    min_stratum_quota: int = 1,
) -> Dict[str, int]:
    """Calculate integer sample quotas per stratum using proportional allocation.
    
    Uses the Hamilton-Hare (Largest Remainder) method with guaranteed minimum
    representation for small strata where records are available.
    
    Guarantees:
      1. If total population <= target_total, return all available counts (100% census).
      2. If target_total <= 0, return 0 for all strata.
      3. Sum of allocated quotas strictly equals min(target_total, total_population).
      4. No stratum is allocated more than its available population N_s.
      5. All non-empty strata receive minimum representation (min_stratum_quota)
         where mathematically possible (i.e. when target_total >= active strata count).
      6. If target_total < active strata count, assigns 1 to the largest strata by
         population (tied deterministically by stratum_id).
      7. Quota allocation is completely independent of dictionary iteration order.
    """
    if target_total <= 0 or not stratum_counts:
        return {s: 0 for s in sorted(stratum_counts.keys())}

    # Sort keys deterministically to guarantee dictionary order independence
    sorted_strata_keys = sorted(stratum_counts.keys())
    total_pop = sum(max(0, stratum_counts[s]) for s in sorted_strata_keys)
    if total_pop <= target_total:
        return {s: max(0, stratum_counts[s]) for s in sorted_strata_keys}

    active_strata = [s for s in sorted_strata_keys if stratum_counts[s] > 0]
    if not active_strata:
        return {s: 0 for s in sorted_strata_keys}

    quotas: Dict[str, int] = {s: 0 for s in sorted_strata_keys}

    # Case A: target_total is smaller than active strata count
    if target_total < len(active_strata):
        # Give 1 to the largest strata by population (break ties alphabetically by stratum_id)
        sorted_by_pop = sorted(active_strata, key=lambda s: (-stratum_counts[s], s))
        for s in sorted_by_pop[:target_total]:
            quotas[s] = 1
        return quotas

    # Case B: Standard proportional calculation with largest remainder
    remainders: List[Tuple[float, int, str]] = []
    base_allocated = 0

    for s in active_strata:
        n_s = stratum_counts[s]
        exact_share = (target_total * n_s) / total_pop
        floor_val = math.floor(exact_share)
        
        # Apply minimum quota representation
        allocated = max(min_stratum_quota, floor_val)
        allocated = min(allocated, n_s)  # cannot exceed stratum population

        quotas[s] = allocated
        base_allocated += allocated
        
        # Store remainder for secondary distribution: (fractional_part, population, stratum_id)
        fractional = exact_share - math.floor(exact_share)
        remainders.append((fractional, n_s, s))

    # Adjust if over-allocated due to minimum quotas
    if base_allocated > target_total:
        surplus = base_allocated - target_total
        # Deduct from strata with largest quotas where quota > min_stratum_quota
        # Tie break deterministically by stratum ID
        reducible = sorted(
            [s for s in active_strata if quotas[s] > 1],
            key=lambda s: (-quotas[s], s),
        )
        for s in reducible:
            if surplus <= 0:
                break
            reduction = min(surplus, quotas[s] - 1)
            quotas[s] -= reduction
            surplus -= reduction
        
        # If still in surplus (extreme edge case), reduce further
        if surplus > 0:
            for s in sorted(active_strata, key=lambda s: (-quotas[s], s)):
                if surplus <= 0:
                    break
                if quotas[s] > 0:
                    quotas[s] -= 1
                    surplus -= 1

    # Distribute remaining slots if under-allocated
    elif base_allocated < target_total:
        deficit = target_total - base_allocated
        # Sort by remainder descending, then population descending, then stratum_id ascending
        remainders.sort(key=lambda item: (-item[0], -item[1], item[2]))

        for _, _, s in remainders:
            if deficit <= 0:
                break
            if quotas[s] < stratum_counts[s]:
                quotas[s] += 1
                deficit -= 1

        # If still deficit because some strata hit their cap, distribute to any stratum with capacity
        if deficit > 0:
            for s in sorted(active_strata, key=lambda s: (-stratum_counts[s], s)):
                if deficit <= 0:
                    break
                available_capacity = stratum_counts[s] - quotas[s]
                if available_capacity > 0:
                    add_amt = min(deficit, available_capacity)
                    quotas[s] += add_amt
                    deficit -= add_amt

    return quotas


class ReservoirSampler(Generic[T]):
    """Memory-bounded, deterministic single-stream reservoir sampler (Algorithm R).
    
    Guarantees that each element seen in the stream has an exact uniform probability
    of (capacity / total_seen) of being retained in the reservoir.
    """

    def __init__(self, capacity: int, seed: int = 42, name: str = "default"):
        if capacity < 0:
            raise ValueError(f"Reservoir capacity cannot be negative, got {capacity}")
        self.capacity = capacity
        self.seed = seed
        self.name = name
        self.rng = random.Random(seed)
        self.reservoir: List[T] = []
        self.total_seen = 0

    def feed(self, item: T) -> bool:
        """Feed an item into the reservoir.
        
        Returns True if the item was added or replaced into the reservoir.
        """
        self.total_seen += 1
        if self.capacity <= 0:
            return False

        if len(self.reservoir) < self.capacity:
            self.reservoir.append(item)
            return True

        # Algorithm R replacement
        j = self.rng.randint(0, self.total_seen - 1)
        if j < self.capacity:
            self.reservoir[j] = item
            return True

        return False

    def get_sample(self) -> List[T]:
        """Return the current reservoir sample."""
        return list(self.reservoir)

    def __len__(self) -> int:
        return len(self.reservoir)


class StratifiedReservoirSampler(Generic[T]):
    """Orchestrates independent reservoir samplers across multiple discrete strata.
    
    Derives deterministic, independent PRNG seeds for each stratum using SHA-256
    digest integers to prevent inter-process and inter-platform hash randomization biases.
    """

    def __init__(
        self,
        stratum_quotas: Dict[str, int],
        base_seed: int = 42,
    ):
        self.base_seed = base_seed
        self.stratum_quotas = dict(stratum_quotas)
        self.samplers: Dict[str, ReservoirSampler[T]] = {}

        for stratum_id in sorted(self.stratum_quotas.keys()):
            quota = self.stratum_quotas[stratum_id]
            # Stable SHA-256 derived seed independent of process or PYTHONHASHSEED
            stratum_seed = derive_stratum_seed(base_seed, stratum_id)
            self.samplers[stratum_id] = ReservoirSampler(
                capacity=quota,
                seed=stratum_seed,
                name=stratum_id,
            )

    def feed(self, stratum_id: str, item: T) -> bool:
        """Feed an item into its designated stratum reservoir."""
        if stratum_id not in self.samplers:
            # If an unexpected stratum appears in pass 2, ignore or initialize with 0
            return False
        return self.samplers[stratum_id].feed(item)

    def get_samples_by_stratum(self) -> Dict[str, List[T]]:
        """Return selected items grouped by stratum ID."""
        return {s_id: sampler.get_sample() for s_id, sampler in self.samplers.items()}

    def get_all_samples(self) -> List[T]:
        """Return all selected items aggregated across all strata."""
        result: List[T] = []
        for s_id in sorted(self.samplers.keys()):
            result.extend(self.samplers[s_id].get_sample())
        return result

    @property
    def total_selected(self) -> int:
        """Total items currently retained across all reservoirs."""
        return sum(len(s) for s in self.samplers.values())

    @property
    def total_seen(self) -> int:
        """Total items fed across all reservoirs."""
        return sum(s.total_seen for s in self.samplers.values())
