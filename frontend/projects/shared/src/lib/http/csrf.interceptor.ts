import { HttpInterceptorFn } from '@angular/common/http';
import { LOGOUT_URL, REFRESH_URL } from '../auth/auth.service';
import { readCookie } from './read-cookie';

const CSRF_COOKIE_NAME = 'csrftoken';
const CSRF_HEADER_NAME = 'X-CSRFToken';

// Matches backend/apps/identity/api/views.py / shared/api/csrf.py::enforce_csrf's CSRF
// scoping: enforced on refresh/logout, exempt on login (docs/api/conventions.md's "CSRF
// scoping" section) -- no session/cookie exists yet at login for an attacker to forge.
const CSRF_PROTECTED_URLS = [REFRESH_URL, LOGOUT_URL];

export const csrfInterceptor: HttpInterceptorFn = (req, next) => {
  if (!CSRF_PROTECTED_URLS.includes(req.url)) {
    return next(req);
  }

  const token = readCookie(CSRF_COOKIE_NAME);
  if (!token) {
    return next(req);
  }

  return next(req.clone({ setHeaders: { [CSRF_HEADER_NAME]: token } }));
};
