import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { Router } from '@angular/router';
// calls AuthService.logout() -- see shared/src/lib/auth/auth.service.ts
import { AuthService } from 'shared';

@Component({
  imports: [MatButtonModule],
  selector: 'app-dashboard-placeholder',
  styleUrl: './dashboard-placeholder.css',
  templateUrl: './dashboard-placeholder.html',
})
export class DashboardPlaceholder {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  logout(): void {
    // Navigates to /login on both outcomes: AuthService.logout() already clears the local
    // auth signal via its own `finalize` regardless of whether the backend call itself
    // succeeds, so there is no "stay logged in" outcome to preserve on a network failure.
    this.authService.logout().subscribe({
      next: () => this.router.navigateByUrl('/login'),
      error: () => this.router.navigateByUrl('/login'),
    });
  }
}
