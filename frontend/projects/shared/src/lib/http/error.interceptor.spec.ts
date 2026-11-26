import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ApiError } from './api-error';
import { errorInterceptor } from './error.interceptor';

describe('errorInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([errorInterceptor])),
        provideHttpClientTesting(),
      ],
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('maps the backend error envelope into an ApiError', () => {
    let caught: ApiError | undefined;
    http.get('/api/v1/ping/').subscribe({ error: (error: ApiError) => (caught = error) });

    httpMock
      .expectOne('/api/v1/ping/')
      .flush(
        { error: { code: 'not_found', message: 'Not found.', details: {} } },
        { status: 404, statusText: 'Not Found' },
      );

    expect(caught).toEqual({ code: 'not_found', message: 'Not found.', details: {}, status: 404 });
  });

  it('maps a response with no envelope to a generic unknown_error', () => {
    let caught: ApiError | undefined;
    http.get('/api/v1/ping/').subscribe({ error: (error: ApiError) => (caught = error) });

    httpMock.expectOne('/api/v1/ping/').flush('Internal Server Error', {
      status: 500,
      statusText: 'Internal Server Error',
    });

    expect(caught).toEqual({
      code: 'unknown_error',
      message: 'An unexpected error occurred.',
      details: {},
      status: 500,
    });
  });

  it('maps a status-0 network failure to network_error', () => {
    let caught: ApiError | undefined;
    http.get('/api/v1/ping/').subscribe({ error: (error: ApiError) => (caught = error) });

    httpMock.expectOne('/api/v1/ping/').error(new ProgressEvent('error'), { status: 0 });

    expect(caught).toEqual({
      code: 'network_error',
      message: 'Could not reach the server.',
      details: {},
      status: 0,
    });
  });

  it('passes successful responses through unchanged', () => {
    let result: { message: string } | undefined;
    http.get<{ message: string }>('/api/v1/ping/').subscribe((value) => (result = value));

    httpMock.expectOne('/api/v1/ping/').flush({ message: 'pong' });

    expect(result).toEqual({ message: 'pong' });
  });
});
