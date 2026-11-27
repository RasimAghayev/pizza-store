import { TestBed } from '@angular/core/testing';
import { CanActivateFn, Router, provideRouter } from '@angular/router';
import { AuthService } from 'shared';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  const executeGuard: CanActivateFn = (...guardParameters) =>
    TestBed.runInInjectionContext(() => authGuard(...guardParameters));

  it('allows access when AuthService reports an authenticated session', () => {
    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: { isAuthenticated: () => true } }],
    });

    const result = executeGuard({} as never, { url: '/dashboard' } as never);

    expect(result).toBe(true);
  });

  it('redirects to /login when AuthService reports no authenticated session', () => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: { isAuthenticated: () => false } },
      ],
    });

    const result = executeGuard({} as never, { url: '/dashboard' } as never);
    const router = TestBed.inject(Router);

    expect(router.serializeUrl(result as never)).toBe('/login');
  });
});
