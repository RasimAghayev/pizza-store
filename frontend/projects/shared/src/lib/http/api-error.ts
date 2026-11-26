import { HttpErrorResponse } from '@angular/common/http';

// Mirrors backend/shared/api/exception_handler.py's error envelope -- see
// docs/api/conventions.md's "Error envelope" section.
export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  status: number;
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

// called by http/error.interceptor.ts
export function toApiError(error: unknown): ApiError {
  if (!(error instanceof HttpErrorResponse)) {
    return {
      code: 'unknown_error',
      message: 'An unexpected error occurred.',
      details: {},
      status: 0,
    };
  }

  const envelope = error.error as ErrorEnvelope | null;
  if (envelope?.error) {
    return {
      code: envelope.error.code ?? 'unknown_error',
      message: envelope.error.message ?? 'An unexpected error occurred.',
      details: envelope.error.details ?? {},
      status: error.status,
    };
  }

  // status 0 means the request never reached a server (offline, DNS failure, CORS
  // rejection) -- there is no envelope to read because the backend never responded.
  return {
    code: error.status === 0 ? 'network_error' : 'unknown_error',
    message: error.status === 0 ? 'Could not reach the server.' : 'An unexpected error occurred.',
    details: {},
    status: error.status,
  };
}
