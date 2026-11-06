/**
 * Core HTTP Client for FoodFlow Frontend
 * - Generates X-Request-ID for distributed tracing.
 * - Parses standardized API error payloads into typed ApiError objects.
 * - Handles HTTP 204 No Content safely.
 * - Supports request cancellation and configurable timeouts.
 * - Disallows dangerous blind retries on non-idempotent mutations.
 */

import { ApiError, ApiErrorResponse } from './types/common';
import { API_CONFIG } from './config';

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined | null>;
  customHeaders?: Record<string, string>;
}

export function generateRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'req_' + Date.now().toString(36) + '_' + Math.random().toString(36).substring(2, 9);
}

export async function request<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const {
    timeoutMs = API_CONFIG.defaultTimeoutMs,
    params,
    customHeaders = {},
    headers: initHeaders,
    signal: userSignal,
    ...fetchInit
  } = options;

  // Build URL with query parameters
  const targetUrl = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        targetUrl.searchParams.append(key, String(value));
      }
    });
  }

  // Setup AbortController for timeout + user signal propagation
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  if (userSignal) {
    userSignal.addEventListener('abort', () => controller.abort());
  }

  // Build headers with X-Request-ID
  const requestId = generateRequestId();
  const mergedHeaders: Record<string, string> = {
    'Accept': 'application/json',
    'X-Request-ID': requestId,
    ...customHeaders,
  };

  if (fetchInit.body && !(fetchInit.body instanceof FormData)) {
    mergedHeaders['Content-Type'] = 'application/json';
  }

  if (initHeaders) {
    if (initHeaders instanceof Headers) {
      initHeaders.forEach((val, key) => {
        mergedHeaders[key] = val;
      });
    } else if (Array.isArray(initHeaders)) {
      initHeaders.forEach(([key, val]) => {
        mergedHeaders[key] = val;
      });
    } else {
      Object.assign(mergedHeaders, initHeaders);
    }
  }

  try {
    const response = await fetch(targetUrl.toString(), {
      ...fetchInit,
      headers: mergedHeaders,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    // Handle HTTP 204 No Content
    if (response.status === 204) {
      return null as unknown as T;
    }

    // Handle error responses
    if (!response.ok) {
      let errorBody: ApiErrorResponse | null = null;
      try {
        errorBody = await response.json();
      } catch {
        // Response was not JSON
      }

      if (errorBody && errorBody.error) {
        throw new ApiError(
          errorBody.error.message || `Request failed with status ${response.status}`,
          response.status,
          errorBody.error.code || `HTTP_${response.status}`,
          errorBody.error.details,
          errorBody.error.request_id || requestId
        );
      }

      throw new ApiError(
        `HTTP Error ${response.status}: ${response.statusText}`,
        response.status,
        `HTTP_${response.status}`,
        null,
        requestId
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiError) {
      throw error;
    }

    if (timedOut) {
      throw new ApiError(
        `Request to ${targetUrl.pathname} timed out after ${timeoutMs}ms`,
        408,
        'TIMEOUT_ERROR',
        null,
        requestId
      );
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request aborted by client', 499, 'CLIENT_ABORT', null, requestId);
    }

    const message = error instanceof Error ? error.message : 'Unknown network failure';
    throw new ApiError(`Network connection failure: ${message}`, 0, 'NETWORK_ERROR', null, requestId);
  }
}

export const httpClient = {
  get: <T>(url: string, options?: RequestOptions) => request<T>(url, { ...options, method: 'GET' }),
  post: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(url: string, body?: unknown, options?: RequestOptions) =>
    request<T>(url, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    }),
  del: <T>(url: string, options?: RequestOptions) => request<T>(url, { ...options, method: 'DELETE' }),
};

