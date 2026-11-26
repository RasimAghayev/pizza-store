import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService, LOGIN_URL, LOGOUT_URL, REFRESH_URL } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('posts login credentials with the browser client-type header and credentials', () => {
    service.login({ email: 'a@example.com', password: 'secret' }).subscribe();

    const request = httpMock.expectOne(LOGIN_URL);
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('X-Client-Type')).toBe('browser');
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.body).toEqual({ email: 'a@example.com', password: 'secret' });

    request.flush({ message: 'Login successful.' });
  });

  it('posts refresh with the browser client-type header and credentials', () => {
    service.refresh().subscribe();

    const request = httpMock.expectOne(REFRESH_URL);
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('X-Client-Type')).toBe('browser');
    expect(request.request.withCredentials).toBe(true);

    request.flush({ message: 'Token refreshed.' });
  });

  it('posts logout with the browser client-type header and credentials', () => {
    service.logout().subscribe();

    const request = httpMock.expectOne(LOGOUT_URL);
    expect(request.request.method).toBe('POST');
    expect(request.request.headers.get('X-Client-Type')).toBe('browser');
    expect(request.request.withCredentials).toBe(true);

    request.flush({ message: 'Logged out.' });
  });

  it('shares one in-flight refresh call across concurrent callers', () => {
    const results: AuthMessageResult[] = [];
    service.refreshOnce().subscribe((value) => results.push(value));
    service.refreshOnce().subscribe((value) => results.push(value));

    httpMock.expectOne(REFRESH_URL).flush({ message: 'Token refreshed.' });

    expect(results).toEqual([{ message: 'Token refreshed.' }, { message: 'Token refreshed.' }]);
  });

  it('starts a fresh refresh call once the previous one has completed', () => {
    service.refreshOnce().subscribe();
    httpMock.expectOne(REFRESH_URL).flush({ message: 'Token refreshed.' });

    service.refreshOnce().subscribe();
    httpMock.expectOne(REFRESH_URL).flush({ message: 'Token refreshed.' });
  });

  it('starts out unauthenticated, becomes authenticated on login success', () => {
    expect(service.isAuthenticated()).toBe(false);

    service.login({ email: 'a@example.com', password: 'secret' }).subscribe();
    httpMock.expectOne(LOGIN_URL).flush({ message: 'Login successful.' });

    expect(service.isAuthenticated()).toBe(true);
  });

  it('stays unauthenticated when login fails', () => {
    let error: unknown;
    service.login({ email: 'a@example.com', password: 'wrong' }).subscribe({
      error: (err: unknown) => (error = err),
    });
    httpMock.expectOne(LOGIN_URL).flush({ error: { message: 'Invalid email or password.' } }, {
      status: 401,
      statusText: 'Unauthorized',
    });

    expect(error).toBeTruthy();
    expect(service.isAuthenticated()).toBe(false);
  });

  it('becomes unauthenticated once logout completes', () => {
    service.login({ email: 'a@example.com', password: 'secret' }).subscribe();
    httpMock.expectOne(LOGIN_URL).flush({ message: 'Login successful.' });
    expect(service.isAuthenticated()).toBe(true);

    service.logout().subscribe();
    httpMock.expectOne(LOGOUT_URL).flush({ message: 'Logged out.' });

    expect(service.isAuthenticated()).toBe(false);
  });

  it('becomes unauthenticated when a refresh fails', () => {
    service.login({ email: 'a@example.com', password: 'secret' }).subscribe();
    httpMock.expectOne(LOGIN_URL).flush({ message: 'Login successful.' });
    expect(service.isAuthenticated()).toBe(true);

    let error: unknown;
    service.refresh().subscribe({ error: (err: unknown) => (error = err) });
    httpMock.expectOne(REFRESH_URL).flush({ error: { message: 'Invalid or expired refresh token.' } }, {
      status: 401,
      statusText: 'Unauthorized',
    });

    expect(error).toBeTruthy();
    expect(service.isAuthenticated()).toBe(false);
  });
});

interface AuthMessageResult {
  message: string;
}
