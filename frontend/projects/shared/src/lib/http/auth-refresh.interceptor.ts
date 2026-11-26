import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService, LOGIN_URL, LOGOUT_URL, REFRESH_URL } from '../auth/auth.service';

// Excludes the auth endpoints themselves -- a 401 from login/refresh/logout is a real
// credential/session failure, not a case to retry (this is also what stops refreshOnce()
// retrying itself and looping forever).
const AUTH_ENDPOINTS = [LOGIN_URL, REFRESH_URL, LOGOUT_URL];

// Must run closer to the backend than http/error.interceptor.ts in the app's
// withInterceptors([...]) list (registration order = request order; responses/errors flow
// back in reverse) so it sees the raw HttpErrorResponse before error.interceptor.ts maps it
// to an ApiError -- see customer-web's app.config.ts.
export const authRefreshInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);

  return next(req).pipe(
    catchError((error: unknown) => {
      const isUnauthorized = error instanceof HttpErrorResponse && error.status === 401;
      if (!isUnauthorized || AUTH_ENDPOINTS.includes(req.url)) {
        return throwError(() => error);
      }

      // One refresh, one retry -- no further catchError wraps the retried next(req), so a
      // second failure propagates straight to the caller instead of looping.
      return authService.refreshOnce().pipe(switchMap(() => next(req)));
    }),
  );
};
