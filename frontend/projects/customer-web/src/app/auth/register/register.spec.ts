import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { Register } from './register';

describe('Register', () => {
  let component: Register;
  let fixture: ComponentFixture<Register>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Register],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(Register);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('shows the explanatory not-yet-available notice', () => {
    const notice: HTMLElement | null =
      fixture.nativeElement.querySelector('.register-form__notice');
    expect(notice?.textContent).toContain('Registration is not yet available');
  });

  it('keeps the submit control disabled even when every field is filled in validly', () => {
    component.form.setValue({
      email: 'a@example.com',
      password: 'secret',
      confirmPassword: 'secret',
    });
    fixture.detectChanges();

    const submit: HTMLButtonElement | null =
      fixture.nativeElement.querySelector('button[type="submit"]');
    expect(submit?.disabled).toBe(true);
  });
});
