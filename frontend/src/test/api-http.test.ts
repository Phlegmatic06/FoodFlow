import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { generateRequestId, httpClient, request } from '../api/http';
import { ApiError } from '../api/types/common';

describe('HTTP Client & Standardized Error Handling', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('generates non-empty unique request IDs', () => {
    const id1 = generateRequestId();
    const id2 = generateRequestId();
    expect(id1).toBeTruthy();
    expect(id2).toBeTruthy();
    expect(id1).not.toBe(id2);
  });

  it('attaches X-Request-ID and Accept headers to every request', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'healthy' }),
    });
    global.fetch = mockFetch;

    const res = await httpClient.get<{ status: string }>('http://localhost:8001/api/v1/health');
    expect(res).toEqual({ status: 'healthy' });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers['Accept']).toBe('application/json');
    expect(init.headers['X-Request-ID']).toBeTruthy();
  });

  it('properly serializes query parameters into the URL', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [] }),
    });
    global.fetch = mockFetch;

    await httpClient.get('http://localhost:8002/api/v1/recipes', {
      params: { query: 'chicken', limit: 10, offset: 0 },
    });

    const [calledUrl] = mockFetch.mock.calls[0];
    const parsed = new URL(calledUrl);
    expect(parsed.searchParams.get('query')).toBe('chicken');
    expect(parsed.searchParams.get('limit')).toBe('10');
    expect(parsed.searchParams.get('offset')).toBe('0');
  });

  it('handles HTTP 204 No Content without attempting JSON parsing', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(), // Should not be called
    });
    global.fetch = mockFetch;

    const res = await httpClient.del('http://localhost:8003/api/v1/plans/123');
    expect(res).toBeNull();
  });

  it('parses standardized OpenAPI error responses into ApiError instances', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Height must be between 100 and 250 cm',
          details: [{ field: 'height_cm', issue: 'Out of range' }],
          request_id: 'req-custom-999',
        },
      }),
    });
    global.fetch = mockFetch;

    await expect(httpClient.post('http://localhost:8001/api/v1/profile/biometrics', {}))
      .rejects.toThrow(ApiError);

    try {
      await httpClient.post('http://localhost:8001/api/v1/profile/biometrics', {});
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.statusCode).toBe(400);
      expect(apiErr.code).toBe('VALIDATION_ERROR');
      expect(apiErr.message).toBe('Height must be between 100 and 250 cm');
      expect(apiErr.requestId).toBe('req-custom-999');
      expect(apiErr.details).toEqual([{ field: 'height_cm', issue: 'Out of range' }]);
    }
  });

  it('handles non-JSON error bodies gracefully with HTTP status fallback', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => {
        throw new Error('Not JSON');
      },
    });
    global.fetch = mockFetch;

    try {
      await httpClient.get('http://localhost:8001/api/v1/health');
      expect.fail('Should have thrown ApiError');
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.statusCode).toBe(502);
      expect(apiErr.code).toBe('HTTP_502');
      expect(apiErr.message).toContain('Bad Gateway');
    }
  });

  it('throws TIMEOUT_ERROR when request exceeds timeoutMs', async () => {
    const mockFetch = vi.fn().mockImplementation((_url, init) => {
      return new Promise((_, reject) => {
        init.signal.addEventListener('abort', () => {
          const abortErr = new DOMException('The operation was aborted.', 'AbortError');
          reject(abortErr);
        });
      });
    });
    global.fetch = mockFetch;

    try {
      await request('http://localhost:8001/api/v1/health', { timeoutMs: 30 });
      expect.fail('Should have timed out');
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.statusCode).toBe(408);
      expect(apiErr.code).toBe('TIMEOUT_ERROR');
      expect(apiErr.message).toContain('timed out after 30ms');
    }
  });

  it('throws NETWORK_ERROR on unexpected network drop', async () => {
    const mockFetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));
    global.fetch = mockFetch;

    try {
      await httpClient.get('http://localhost:8001/api/v1/health');
      expect.fail('Should have failed');
    } catch (err) {
      const apiErr = err as ApiError;
      expect(apiErr.statusCode).toBe(0);
      expect(apiErr.code).toBe('NETWORK_ERROR');
      expect(apiErr.message).toContain('Failed to fetch');
    }
  });
});

