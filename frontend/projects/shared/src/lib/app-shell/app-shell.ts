import { BreakpointObserver } from '@angular/cdk/layout';
import { Component, inject, input } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatButtonModule } from '@angular/material/button';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { map } from 'rxjs/operators';

// Mobile-first cutoff matching Angular Material's own "handset" boundary (599.98px, paired
// with app-shell.css's 600px min-width breakpoint). Deliberately a plain media-query string
// rather than CDK's `Breakpoints.Handset` constant: that constant combines orientation and
// device-resolution queries which don't reliably re-match a headless Playwright viewport
// resize (confirmed by testing both against a 375px/1280px resize), while a single
// `max-width` query does.
const HANDSET_QUERY = '(max-width: 599.98px)';

@Component({
  imports: [MatToolbarModule, MatSidenavModule, MatButtonModule],
  selector: 'lib-app-shell',
  styleUrl: './app-shell.css',
  templateUrl: './app-shell.html',
})
export class AppShell {
  appName = input.required<string>();

  private readonly breakpointObserver = inject(BreakpointObserver);

  // `requireSync: true` is safe here: BreakpointObserver.observe() always emits the current
  // match state synchronously on subscribe (confirmed via Angular Material's own current
  // responsive-sidenav example), so there is no "undefined" frame before the first real value.
  readonly isHandset = toSignal(
    this.breakpointObserver.observe(HANDSET_QUERY).pipe(map((state) => state.matches)),
    { requireSync: true },
  );
}
