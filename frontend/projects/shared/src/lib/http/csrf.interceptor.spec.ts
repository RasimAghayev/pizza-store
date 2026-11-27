import { DOCUMENT } from '@angular/common';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { LOGIN_URL, LOGOUT_URL, REFRESH_URL } from '../auth/auth.service';
import { csrfInterceptor } from './csrf.interceptor';

function configure(cookie: string) {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([csrfInterceptor])),
      provideHttpClientTesting(),
      { provide: DOCUMENT, useValue: { cookie } },
    ],
  });
}

describe('csrfInterceptor', () => {
  let httpMock: HttpTestingController;

  afterEach(() => httpMock.verify());

  it('attaches X-CSRFToken from the csrftoken cookie on refresh', () => {
    configure('other=1; csrftoken=the-token; another=2');
    const http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);

    http.post(REFRESH_URL, {}).subscribe();

    const request = httpMock.expectOne(REFRESH_URL);
    expect(request.request.headers.get('X-CSRFToken')).toBe('the-token');
    request.flush({});
  });

  it('attaches X-CSRFToken on logout', () => {
    configure('csrftoken=the-token');
    const http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);

    http.post(LOGOUT_URL, {}).subscribe();

    const request = httpMock.expectOne(LOGOUT_URL);
    expect(request.request.headers.get('X-CSRFToken')).toBe('the-token');
    request.flush({});
  });

  it('does not attach X-CSRFToken on login, even when the cookie is present', () => {
    configure('csrftoken=the-token');
    const http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);

    http.post(LOGIN_URL, {}).subscribe();

    const request = httpMock.expectOne(LOGIN_URL);
    expect(request.request.headers.has('X-CSRFToken')).toBe(false);
    request.flush({});
  });

  it('leaves the request untouched when no csrftoken cookie exists', () => {
    configure('other=1');
    const http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);

    http.post(REFRESH_URL, {}).subscribe();

    const request = httpMock.expectOne(REFRESH_URL);
    expect(request.request.headers.has('X-CSRFToken')).toBe(false);
    request.flush({});
  });
});
