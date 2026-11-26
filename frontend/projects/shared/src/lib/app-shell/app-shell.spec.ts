import { BreakpointObserver } from '@angular/cdk/layout';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AppShell } from './app-shell';

// Stubs BreakpointObserver instead of polyfilling window.matchMedia (jsdom has no
// implementation of it) -- `observe()` just needs to emit synchronously, matching the real
// service's contract that app-shell.ts's `toSignal(..., { requireSync: true })` relies on.
function configureAppShell(isHandset: boolean): Promise<ComponentFixture<AppShell>> {
  return TestBed.configureTestingModule({
    imports: [AppShell],
    providers: [
      {
        provide: BreakpointObserver,
        useValue: { observe: () => of({ matches: isHandset, breakpoints: {} }) },
      },
    ],
  })
    .compileComponents()
    .then(() => {
      const fixture = TestBed.createComponent(AppShell);
      fixture.componentRef.setInput('appName', 'customer-web');
      return fixture;
    });
}

describe('AppShell', () => {
  describe('on a wide viewport', () => {
    let fixture: ComponentFixture<AppShell>;

    beforeEach(async () => {
      fixture = await configureAppShell(false);
      await fixture.whenStable();
    });

    it('should create', () => {
      expect(fixture.componentInstance).toBeTruthy();
    });

    it('renders the app name in the toolbar', () => {
      const toolbar: HTMLElement | null = fixture.nativeElement.querySelector('.app-shell__toolbar');
      expect(toolbar?.textContent).toContain('customer-web');
    });

    it('does not render the nav toggle button', () => {
      const toggle = fixture.nativeElement.querySelector('.app-shell__nav-toggle');
      expect(toggle).toBeNull();
    });
  });

  describe('on a narrow (handset) viewport', () => {
    let fixture: ComponentFixture<AppShell>;

    beforeEach(async () => {
      fixture = await configureAppShell(true);
      await fixture.whenStable();
    });

    it('renders the nav toggle button', () => {
      const toggle: HTMLElement | null = fixture.nativeElement.querySelector(
        '.app-shell__nav-toggle',
      );
      expect(toggle).not.toBeNull();
      expect(toggle?.getAttribute('aria-label')).toBe('Toggle navigation menu');
    });
  });
});
