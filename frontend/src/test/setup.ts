import "@testing-library/jest-dom/vitest";

// React Router builds a Node `Request` with jsdom's `AbortSignal`, which Node rejects ("Expected signal to be an
// instance of AbortSignal"). Tests never abort navigations, so the signal is dropped here, in test setup only.
const NodeRequest = globalThis.Request;
globalThis.Request = class extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const { signal: _signal, ...rest } = init ?? {};
    super(input, rest);
  }
} as typeof Request;
