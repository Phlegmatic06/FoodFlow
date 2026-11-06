import '@testing-library/jest-dom';

/**
 * Node 24 + jsdom AbortSignal compatibility shim for React Router / @remix-run/router.
 *
 * In Node 24, undici's RequestInit strictly validates that `init.signal` is an instance
 * of Node's internal AbortSignal. When running under jsdom, jsdom replaces globalThis.AbortController
 * with its own implementation, causing React Router's internal `new Request(url, { signal })`
 * calls to fail the brand check.
 *
 * This shim allows jsdom's AbortSignal to be passed to Request without throwing a TypeError.
 */
if (typeof globalThis.Request !== 'undefined') {
  const OriginalRequest = globalThis.Request;

  (globalThis as unknown as { Request: unknown }).Request = class PatchedRequest extends OriginalRequest {
    private _signal?: AbortSignal;

    constructor(input: RequestInfo | URL, init?: RequestInit) {
      if (init && init.signal) {
        const { signal, ...rest } = init;
        super(input as RequestInfo, rest);
        this._signal = signal as AbortSignal;
      } else {
        super(input as RequestInfo, init);
      }
    }

    get signal(): AbortSignal {
      return this._signal || super.signal;
    }
  };
}
