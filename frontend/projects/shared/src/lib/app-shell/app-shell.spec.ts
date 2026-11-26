import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppShell } from './app-shell';

describe('AppShell', () => {
  let component: AppShell;
  let fixture: ComponentFixture<AppShell>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppShell],
    }).compileComponents();

    fixture = TestBed.createComponent(AppShell);
    fixture.componentRef.setInput('appName', 'customer-web');
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders the app name in the toolbar', () => {
    const toolbar: HTMLElement | null = fixture.nativeElement.querySelector('.app-shell__toolbar');
    expect(toolbar?.textContent).toContain('customer-web');
  });
});
