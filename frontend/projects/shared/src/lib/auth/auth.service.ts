import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, catchError, finalize, shareReplay, tap, throwError } from 'rxjs';

// calls POST /api/v1/auth/{login,refresh,logout} -- see
// backend/apps/identity/api/views.py (Issue #129) / backend/apps/identity/api/urls.py
export const AUTH_API_BASE = '/api/v1/auth';
export const LOGIN_URL = `${AUTH_API_BASE}/login/`;
export const REFRESH_URL = `${AUTH_API_BASE}/refresh/`;
export const LOGOUT_URL = `${AUTH_API_BASE}/logout/`;

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthMessage {
  message: string;
}

// Only `browser` mode is implemented here -- `native` (bearer-token-in-body) mode has no
// Angular client and is out of this app's scope (docs/api/conventions.md's X-Client-Type
// table).
const BROWSER_CLIENT_HEADERS = { 'X-Client-Type': 'browser' } as const;

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private refreshInFlight$: Observable<AuthMessage> | null = null;

  // In-memory only -- no "whoami" endpoint exists yet to restore this across a page reload
  // (documented known gap in frontend/README.md). customer-web's auth.guard.ts reads this to
  // decide route access and must fail closed, so losing the signal on reload correctly
  // redirects to /login rather than trusting a possibly-still-valid httpOnly cookie.
  private readonly authenticated = signal(false);
  readonly isAuthenticated = this.authenticated.asReadonly();

  login(credentials: LoginCredentials): Observable<AuthMessage> {
    return this.http
      .post<AuthMessage>(LOGIN_URL, credentials, {
        headers: BROWSER_CLIENT_HEADERS,
        withCredentials: true,
      })
      .pipe(tap(() => this.authenticated.set(true)));
  }

  refresh(): Observable<AuthMessage> {
    return this.http
      .post<AuthMessage>(
        REFRESH_URL,
        {},
        {
          headers: BROWSER_CLIENT_HEADERS,
          withCredentials: true,
        },
      )
      .pipe(
        tap(() => this.authenticated.set(true)),
        catchError((error: unknown) => {
          this.authenticated.set(false);
          return throwError(() => error);
        }),
      );
  }

  logout(): Observable<AuthMessage> {
    return this.http
      .post<AuthMessage>(
        LOGOUT_URL,
        {},
        {
          headers: BROWSER_CLIENT_HEADERS,
          withCredentials: true,
        },
      )
      .pipe(finalize(() => this.authenticated.set(false)));
  }

  // called by http/auth-refresh.interceptor.ts -- shares one in-flight refresh call across
  // every request that 401s while a refresh is already pending, instead of firing one
  // refresh per concurrent failed request.
  refreshOnce(): Observable<AuthMessage> {
    if (!this.refreshInFlight$) {
      this.refreshInFlight$ = this.refresh().pipe(
        shareReplay({ bufferSize: 1, refCount: true }),
        finalize(() => {
          this.refreshInFlight$ = null;
        }),
      );
    }
    return this.refreshInFlight$;
  }
}
