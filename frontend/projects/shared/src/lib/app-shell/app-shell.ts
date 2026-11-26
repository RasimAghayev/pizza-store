import { Component, input } from '@angular/core';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';

@Component({
  imports: [MatToolbarModule, MatSidenavModule],
  selector: 'lib-app-shell',
  styleUrl: './app-shell.css',
  templateUrl: './app-shell.html',
})
export class AppShell {
  appName = input.required<string>();
}
