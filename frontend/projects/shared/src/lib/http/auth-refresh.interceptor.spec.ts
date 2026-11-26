import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { vi } from 'vitest';
import { AuthService, LOGIN_URL } from '../auth/auth.service';
import { authRefreshInterceptor } from './auth-refresh.interceptor';

describe('authRefreshInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let authService: { refreshOnce: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    authService = { refreshOnce: vi.fn() };

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authRefreshInterceptor])),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: authService },
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('refreshes once and retries the original request after a 401', () => {
    authService.refreshOnce.mockReturnValue(of({ message: 'Token refreshed.' }));

    let result: { data: string } | undefined;
    http.get<{ data: string }>('/api/v1/orders/').subscribe((value) => (result = value));

    httpMock
      .expectOne('/api/v1/orders/')
      .flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
    expect(authService.refreshOnce).toHaveBeenCalledTimes(1);

    httpMock.expectOne('/api/v1/orders/').flush({ data: 'ok' });
    expect(result).toEqual({ data: 'ok' });
  });

  it('propagates the failure when the refresh call itself fails, without retrying again', () => {
    authService.refreshOnce.mockReturnValue(throwError(() => new Error('refresh failed')));

    let error: unknown;
    http.get('/api/v1/orders/').subscribe({ error: (err: unknown) => (error = err) });

    httpMock
      .expectOne('/api/v1/orders/')
      .flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

    expect(authService.refreshOnce).toHaveBeenCalledTimes(1);
    expect((error as Error).message).toBe('refresh failed');
    httpMock.verify();
  });

  it('propagates a second 401 on the retried request without refreshing again', () => {
    authService.refreshOnce.mockReturnValue(of({ message: 'Token refreshed.' }));

    let error: unknown;
    http.get('/api/v1/orders/').subscribe({ error: (err: unknown) => (error = err) });

    httpMock
      .expectOne('/api/v1/orders/')
      .flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
    httpMock
      .expectOne('/api/v1/orders/')
      .flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

    expect(authService.refreshOnce).toHaveBeenCalledTimes(1);
    expect((error as { status: number }).status).toBe(401);
  });

  it('does not attempt a refresh for a non-401 error', () => {
    let error: unknown;
    http.get('/api/v1/orders/').subscribe({ error: (err: unknown) => (error = err) });

    httpMock
      .expectOne('/api/v1/orders/')
      .flush('Server error', { status: 500, statusText: 'Internal Server Error' });

    expect(authService.refreshOnce).not.toHaveBeenCalled();
    expect((error as { status: number }).status).toBe(500);
  });

  it('does not attempt a refresh when login itself returns a 401', () => {
    let error: unknown;
    http.post(LOGIN_URL, {}).subscribe({ error: (err: unknown) => (error = err) });

    httpMock
      .expectOne(LOGIN_URL)
      .flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

    expect(authService.refreshOnce).not.toHaveBeenCalled();
    expect((error as { status: number }).status).toBe(401);
  });
});
