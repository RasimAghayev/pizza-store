import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Loading } from './loading';

describe('Loading', () => {
  let component: Loading;
  let fixture: ComponentFixture<Loading>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Loading],
    }).compileComponents();

    fixture = TestBed.createComponent(Loading);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('renders the default loading message', () => {
    const message: HTMLElement | null = fixture.nativeElement.querySelector('.loading__message');
    expect(message?.textContent).toContain('Loading');
  });
});
