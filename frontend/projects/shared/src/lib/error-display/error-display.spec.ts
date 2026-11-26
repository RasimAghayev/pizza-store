import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ErrorDisplay } from './error-display';

describe('ErrorDisplay', () => {
  let component: ErrorDisplay;
  let fixture: ComponentFixture<ErrorDisplay>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ErrorDisplay],
    }).compileComponents();

    fixture = TestBed.createComponent(ErrorDisplay);
    fixture.componentRef.setInput('message', 'Request failed');
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders the provided error message', () => {
    const message: HTMLElement | null =
      fixture.nativeElement.querySelector('.error-display__message');
    expect(message?.textContent).toContain('Request failed');
  });

  it('emits dismissed when the dismiss button is clicked', () => {
    fixture.componentRef.setInput('dismissible', true);
    fixture.detectChanges();

    let dismissed = false;
    component.dismissed.subscribe(() => (dismissed = true));

    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    button.click();

    expect(dismissed).toBe(true);
  });
});
