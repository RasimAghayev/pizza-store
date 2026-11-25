# ADR 0002: Polyglot Persistence — PostgreSQL, MongoDB, Redis

## Status

Accepted

## Kontekst

Platform üç növ məlumatla işləyir: (1) ciddi consistency tələb edən transaction məlumatları
(sifariş, ödəniş, balans), (2) strukturu dəyişkən, sorğu yükü az olan sənəd məlumatları
(audit, event history, tracking history), (3) qısa ömürlü, tez-tez oxunan "hot" məlumatlar
(cache, session, son GPS koordinatları).

Tək bir database (yalnız PostgreSQL) ilə hər üçünü eyni effektivliklə həll etmək mümkündür,
amma audit/tracking tarixçəsi kimi yüksək yazma tezliyinə malik, sxemsiz məlumatlar
PostgreSQL-i lazımsız yükləyəcək və hot-path oxumalar üçün əlavə latency yaradacaq.

## Qərar

Hər database yalnız öz məsuliyyət sahəsini daşıyır:

| Texnologiya | Rol | Nümunə məlumat |
|---|---|---|
| PostgreSQL | Source of truth, ACID | users, orders, order_items, payments, refunds, wallet/loyalty/inventory transaction-lar |
| MongoDB | Çevik sənəd məlumatı | audit records, order event history, delivery tracking history, analytics documents |
| Redis | Hot data (source of truth deyil) | cache, session, rate limiting, OTP, courier son koordinat, order status cache |

MongoDB heç vaxt PostgreSQL-in əvəzi kimi istifadə olunmur — pul və balans əməliyyatları
yalnız PostgreSQL-dədir. Redis-dəki məlumat itsə belə sistem funksional qalmalıdır (yalnız
performans təsirlənir, data itkisi olmur) — bu, Redis-in həmişə "cache/hot cache", heç vaxt
"yeganə mənbə" olmamasının təsdiqidir.

## Səbəb

- ACID tələb edən maliyyə və sifariş məlumatları üçün PostgreSQL-in transaction təminatı
  əvəzolunmazdır.
- Audit/tracking tarixçəsi həcmcə böyük, sxemi tez-tez dəyişə bilən, nadir hallarda mürəkkəb
  JOIN tələb edən məlumatdır — sənəd modeli (MongoDB) daha münasibdir və PostgreSQL-i
  lazımsız yazma yükündən qoruyur.
- Kuryerin son koordinatı, aktiv sifariş statusu kimi "yalnız ən son dəyər vacibdir"
  məlumatlar üçün Redis-in in-memory sürəti lazımdır; bu məlumatın tarixçəsi isə MongoDB-də
  saxlanılır.

## Nəticələr

- Cache invalidation və TTL siyasəti sənədləşdirilməlidir (bax `docs/database/`).
- Hansı məlumatın harada saxlandığı Database Responsibility Matrix ilə izlənilir.
- Servislər arası consistency event-driven mexanizmlə (RabbitMQ + Outbox, bax ADR 0001)
  qorunur — birbaşa cross-database transaction yoxdur.

## Alternativlər

- **Yalnız PostgreSQL (hamısı üçün):** rədd edildi — audit/tracking üçün lazımsız schema
  rigidiyi və yazma yükü.
- **Yalnız MongoDB (hamısı üçün):** rədd edildi — maliyyə əməliyyatları üçün ACID
  təminatının olmaması qəbuledilməzdir.
