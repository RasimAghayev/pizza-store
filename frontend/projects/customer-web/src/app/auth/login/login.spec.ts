import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { Observable, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import { ApiError, AuthService } from 'shared';
import { Login } from './login';

describe('Login', () => {
  let component: Login;
  let fixture: ComponentFixture<Login>;
  let authService: { login: ReturnType<typeof vi.fn> };
  let router: Router;

  beforeEach(async () => {
    authService = { login: vi.fn() };

    await TestBed.configureTestingModule({
      imports: [Login],
      providers: [provideRouter([]), { provide: AuthService, useValue: authService }],
    }).compileComponents();

    fixture = TestBed.createComponent(Login);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('does not submit while the form is invalid', () => {
    authService.login.mockReturnValue(new Subject());

    component.submit();

    expect(authService.login).not.toHaveBeenCalled();
  });

  it('logs in and navigates to the dashboard on success', () => {
    const response$ = new Subject<{ message: string }>();
    authService.login.mockReturnValue(response$ as unknown as Observable<{ message: string }>);
    component.form.setValue({ email: 'a@example.com', password: 'secret' });

    component.submit();
    response$.next({ message: 'Login successful.' });
    response$.complete();

    expect(authService.login).toHaveBeenCalledWith({ email: 'a@example.com', password: 'secret' });
    expect(router.navigateByUrl).toHaveBeenCalledWith('/dashboard');
    expect(component.errorMessage()).toBeNull();
  });

  it('surfaces the backend error message and does not navigate on failure', () => {
    const apiError: ApiError = {
      code: 'authentication_failed',
      message: 'Invalid email or password.',
      details: {},
      status: 401,
    };
    authService.login.mockReturnValue(throwError(() => apiError));
    component.form.setValue({ email: 'a@example.com', password: 'wrong' });

    component.submit();

    expect(component.errorMessage()).toBe('Invalid email or password.');
    expect(router.navigateByUrl).not.toHaveBeenCalled();
  });
});
