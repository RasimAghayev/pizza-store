import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
// calls AuthService.isAuthenticated() -- see shared/src/lib/auth/auth.service.ts
import { AuthService } from 'shared';

// Fails closed by construction: AuthService.isAuthenticated() starts false and only ever
// becomes true after a real login/refresh success, so any ambiguous/unknown state (not yet
// logged in, a lost in-memory signal after a page reload) resolves to the `/login` redirect
// rather than route access.
export const authGuard: CanActivateFn = () => {
  if (inject(AuthService).isAuthenticated()) {
    return true;
  }
  return inject(Router).createUrlTree(['/login']);
};
