import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter } from '@angular/router';
// calls into shared/src/lib/http/*.interceptor.ts -- see each file for what it does
import { authRefreshInterceptor, csrfInterceptor, errorInterceptor } from 'shared';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideAnimationsAsync(),
    // Registration order = request order; responses/errors flow back in reverse, so
    // authRefreshInterceptor (closest to the backend here) sees a 401 before
    // errorInterceptor maps it to an ApiError -- see auth-refresh.interceptor.ts.
    provideHttpClient(
      withInterceptors([csrfInterceptor, errorInterceptor, authRefreshInterceptor]),
    ),
  ],
};
