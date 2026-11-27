import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { toApiError } from './api-error';

// Maps the backend's error envelope (docs/api/conventions.md) into a typed ApiError so
// callers/components (e.g. shared's ErrorDisplay -- error-display/error-display.ts) get a
// consistent shape regardless of which endpoint failed or how.
export const errorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(catchError((error: unknown) => throwError(() => toApiError(error))));
