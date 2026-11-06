/**
 * useRecipeSearch Hook
 * Manages search query, facets, sorting, pagination, AbortController lifecycle,
 * and bi-directional URL query string synchronization.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { recipeClient } from '../api/recipeClient';
import {
  PaginationInfo,
  RecipeSearchParams,
  RecipeSortOption,
  RecipeSourceDataset,
  RecipeSummary,
} from '../api/types/recipe';
import { ApiError } from '../api/types/common';

export interface ActiveFilters {
  cuisine?: string;
  diet?: string;
  tag?: string;
  max_time?: number;
  source_dataset?: RecipeSourceDataset;
}

export function useRecipeSearch(initialLimit: number = 24) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Parse initial state from URL query parameters
  const qParam = searchParams.get('q') || '';
  const cuisineParam = searchParams.get('cuisine') || undefined;
  const dietParam = searchParams.get('diet') || undefined;
  const tagParam = searchParams.get('tag') || undefined;
  const maxTimeParam = searchParams.get('max_time')
    ? parseInt(searchParams.get('max_time')!, 10)
    : undefined;
  const sourceDatasetParam = (searchParams.get('source_dataset') as RecipeSourceDataset) || undefined;
  const sortParam = (searchParams.get('sort') as RecipeSortOption) || 'relevance';
  const pageParam = searchParams.get('page') ? Math.max(1, parseInt(searchParams.get('page')!, 10)) : 1;

  // Local state
  const [queryInput, setQueryInput] = useState<string>(qParam);
  const [recipes, setRecipes] = useState<RecipeSummary[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: pageParam,
    limit: initialLimit,
    total_items: 0,
    total_pages: 0,
  });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<ApiError | null>(null);

  // Active filters object
  const activeFilters: ActiveFilters = {
    cuisine: cuisineParam,
    diet: dietParam,
    tag: tagParam,
    max_time: maxTimeParam,
    source_dataset: sourceDatasetParam,
  };

  // Keep references for request cancellation and race condition avoidance
  const abortControllerRef = useRef<AbortController | null>(null);
  const requestSeqRef = useRef<number>(0);

  // Sync state to URL
  const updateUrlParams = useCallback(
    (newParams: Record<string, string | number | undefined | null>, resetPage = false) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        Object.entries(newParams).forEach(([key, val]) => {
          if (val === undefined || val === null || val === '') {
            next.delete(key);
          } else {
            next.set(key, String(val));
          }
        });
        if (resetPage) {
          next.set('page', '1');
        }
        return next;
      });
    },
    [setSearchParams]
  );

  // Perform search query against Recipe & Ingredient Service
  const fetchRecipes = useCallback(async () => {
    // Cancel in-flight request if present
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentSeq = ++requestSeqRef.current;

    setLoading(true);
    setError(null);

    const searchArgs: RecipeSearchParams = {
      q: qParam || undefined,
      cuisine: cuisineParam,
      diet: dietParam,
      tag: tagParam,
      max_time: maxTimeParam,
      source_dataset: sourceDatasetParam,
      sort: sortParam,
      page: pageParam,
      limit: initialLimit,
    };

    try {
      const response = await recipeClient.searchRecipes(searchArgs, {
        signal: controller.signal,
      });

      // Avoid setting state if a newer request was dispatched
      if (currentSeq === requestSeqRef.current) {
        setRecipes(response.data);
        setPagination(response.pagination);
        setLoading(false);
      }
    } catch (err) {
      if (currentSeq === requestSeqRef.current) {
        if (err instanceof ApiError) {
          if (err.code !== 'CLIENT_ABORT') {
            setError(err);
            setLoading(false);
          }
        } else {
          setError(
            new ApiError(
              err instanceof Error ? err.message : 'Failed to search recipes',
              0,
              'SEARCH_ERROR'
            )
          );
          setLoading(false);
        }
      }
    }
  }, [
    qParam,
    cuisineParam,
    dietParam,
    tagParam,
    maxTimeParam,
    sourceDatasetParam,
    sortParam,
    pageParam,
    initialLimit,
  ]);

  // Execute search whenever URL params change
  useEffect(() => {
    fetchRecipes();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchRecipes]);

  // Keep local query input in sync when URL changes (e.g. back/forward navigation)
  useEffect(() => {
    setQueryInput(qParam);
  }, [qParam]);

  // Actions
  const handleSearchSubmit = useCallback(
    (customQuery?: string) => {
      const targetQuery = customQuery !== undefined ? customQuery : queryInput;
      updateUrlParams({ q: targetQuery.trim() }, true);
    },
    [queryInput, updateUrlParams]
  );

  const handleClearSearch = useCallback(() => {
    setQueryInput('');
    updateUrlParams({ q: undefined }, true);
  }, [updateUrlParams]);

  const handleSetFilter = useCallback(
    <K extends keyof ActiveFilters>(key: K, value: ActiveFilters[K] | undefined) => {
      updateUrlParams({ [key]: value }, true);
    },
    [updateUrlParams]
  );

  const handleRemoveFilter = useCallback(
    (key: keyof ActiveFilters) => {
      updateUrlParams({ [key]: undefined }, true);
    },
    [updateUrlParams]
  );

  const handleClearAllFilters = useCallback(() => {
    updateUrlParams(
      {
        cuisine: undefined,
        diet: undefined,
        tag: undefined,
        max_time: undefined,
        source_dataset: undefined,
      },
      true
    );
  }, [updateUrlParams]);

  const handleSetSort = useCallback(
    (sort: RecipeSortOption) => {
      updateUrlParams({ sort }, true);
    },
    [updateUrlParams]
  );

  const handleSetPage = useCallback(
    (newPage: number) => {
      updateUrlParams({ page: newPage }, false);
    },
    [updateUrlParams]
  );

  return {
    recipes,
    pagination,
    loading,
    error,
    queryInput,
    setQueryInput,
    activeQuery: qParam,
    activeFilters,
    activeSort: sortParam,
    currentPage: pageParam,
    submitSearch: handleSearchSubmit,
    clearSearch: handleClearSearch,
    setFilter: handleSetFilter,
    removeFilter: handleRemoveFilter,
    clearAllFilters: handleClearAllFilters,
    setSort: handleSetSort,
    setPage: handleSetPage,
    retry: fetchRecipes,
  };
}

