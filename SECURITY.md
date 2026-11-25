# Security Policy

## Dəstəklənən versiyalar

Layihə hazırda Phase 0-dadır (repository foundation); hələ release olunmuş versiya yoxdur.
İlk stabil versiya elan olunana qədər `main` branch dəstəklənən tək xətdir.

## Zəiflik bildirişi

Təhlükəsizlik zəifliyi aşkar etsəniz, **ictimai Issue açmayın**.

- GitHub Private Vulnerability Reporting aktiv olduqda ("Security" tabından "Report a
  vulnerability"), ondan istifadə edin.
- Alternativ olaraq: rasimaqayev@gmail.com ünvanına yazın.

Bildirişdə təsvir, təkrarlama addımları və təsir dairəsi olsun. Mümkün qədər tez (məqsəd:
7 iş günü ərzində ilkin cavab) geri dönüş ediləcək.

## Əhatə dairəsi

- Autentifikasiya/avtorizasiya, data sızması, injection, SSRF, secret ifşası: kritik.
- Dependency zəiflikləri Dependabot/Renovate vasitəsilə izlənilir.
- Secret-lər heç vaxt repository-yə commit edilməməlidir (push protection aktivdir).
