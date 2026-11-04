"""FoodFlow Stratified Recipe Sampling Package

Provides unified, deterministic, stratified reservoir sampling engines for
development datasets (Food.com and RecipeNLG).

Key Exports:
  - FoodComSampler: Stratified sampler for Food.com recipes + interaction filter.
  - RecipeNLGSampler: Stratified sampler for RecipeNLG corpus.
  - SamplingReport: Structured audit and provenance report generator.
  - allocate_proportional_quotas: Proportional allocation with minimum representation.
  - ReservoirSampler: Memory-bounded single-stream reservoir sampler (Algorithm R).
  - StratifiedReservoirSampler: Multi-stratum reservoir coordinator.
  - StratifiedRecipeSampler: Unified interface for backwards compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ingestion.sampling.base import (
    ReservoirSampler,
    StratifiedReservoirSampler,
    allocate_proportional_quotas,
    derive_stratum_seed,
)
from ingestion.sampling.foodcom_sampler import FoodComSampler
from ingestion.sampling.recipenlg_sampler import RecipeNLGSampler
from ingestion.sampling.reports import SamplingReport


class StratifiedRecipeSampler:
    """Unified coordinator for development dataset sampling."""

    def __init__(self, target_sample_size: int = 25000, random_seed: int = 42):
        self.target_sample_size = target_sample_size
        self.random_seed = random_seed

    def sample_foodcom(
        self,
        source_path: Path,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> SamplingReport:
        """Execute stratified sampling for Food.com."""
        sampler = FoodComSampler(
            source_path=source_path,
            output_dir=output_dir,
            limit=self.target_sample_size,
            seed=self.random_seed,
        )
        return sampler.run(dry_run=dry_run)

    def sample_recipenlg(
        self,
        source_path: Path,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> SamplingReport:
        """Execute stratified sampling for RecipeNLG."""
        sampler = RecipeNLGSampler(
            source_path=source_path,
            output_dir=output_dir,
            limit=self.target_sample_size,
            seed=self.random_seed,
        )
        return sampler.run(dry_run=dry_run)


__all__ = [
    "FoodComSampler",
    "RecipeNLGSampler",
    "SamplingReport",
    "allocate_proportional_quotas",
    "derive_stratum_seed",
    "ReservoirSampler",
    "StratifiedReservoirSampler",
    "StratifiedRecipeSampler",
]
