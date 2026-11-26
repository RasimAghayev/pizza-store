import { DOCUMENT } from '@angular/common';
import { inject } from '@angular/core';

// Must be called synchronously from within an interceptor function body (not inside a
// pipe()/subscribe() callback) so Angular's inject() can resolve DOCUMENT from the active
// injection context -- see http/csrf.interceptor.ts.
export function readCookie(name: string): string | null {
  const cookies = inject(DOCUMENT).cookie;
  for (const entry of cookies.split('; ')) {
    if (entry.startsWith(`${name}=`)) {
      return decodeURIComponent(entry.slice(name.length + 1));
    }
  }
  return null;
}
