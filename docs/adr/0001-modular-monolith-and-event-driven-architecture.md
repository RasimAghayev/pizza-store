# ADR 0001: Modular Monolith + Event-Driven Architecture

## Status

Accepted

## Kontekst

Pizza Store Platform real restoran şəbəkəsinin bütün əməliyyatlarını (müştəri, sifariş,
ödəniş, kuryer, inventar, loyalty, idarəetmə) idarə edəcək. Layihə sıfırdan başlayır,
real yük və domain sərhədləri hələ təcrübə ilə sınanmayıb.

İki əsas variant nəzərdən keçirildi:

1. Başlanğıcdan Microservices arxitekturası.
2. Modular Monolith + Event-Driven Architecture (EDA), gələcəkdə seçilmiş modulların
   microservice-ə ayrılması imkanı ilə.

## Qərar

Modular Monolith + EDA seçilir.

- Django daxilində domain-lərə görə aydın ayrılmış app-lar (bounded context): identity,
  customers, restaurants, branches, menu, products, pricing, cart, orders, payments,
  kitchen, inventory, couriers, delivery, loyalty, notifications, reviews, analytics, audit.
- Modullar arasında birbaşa asılılıq minimuma endirilir; sinxron deyil, RabbitMQ üzərindən
  domain event-ləri ilə kommunikasiya üstünlük təşkil edir (OrderCreated, PaymentCompleted
  və s.).
- Clean Architecture, DDD, SOLID, Repository Pattern, Service Layer, Dependency Injection
  tətbiq olunur ki, modul sərhədləri kod səviyyəsində də qorunsun.

## Səbəb

- Tək deployment vahidi ilə ilk mərhələdə operativ mürəkkəbliyi (çoxsaylı servis, şəbəkə,
  distributed transaction) aşağı saxlayır.
- Bounded context-lər əvvəlcədən aydın ayrıldığına görə, real scaling ehtiyacı yarandıqda
  (məsələn, delivery tracking və ya notification yüksək yük alarsa) həmin modul ayrıca
  microservice-ə çıxarıla bilər — monolit bunu əngəlləmir, sadəcə indi məcbur etmir.
- RabbitMQ ilə EDA, monolit daxilində belə, modullar arasında sıx coupling yaranmasının
  qarşısını alır və gələcək ayrılmağı asanlaşdırır.

## Nəticələr

- Transactional Outbox Pattern məcburidir: PostgreSQL transaction uğurlu olub RabbitMQ
  əlçatmaz olduqda event itməməlidir.
- Idempotent consumer-lər məcburidir: eyni event təkrar gəlsə, ödəniş/sifariş əməliyyatı
  təkrar icra olunmamalıdır.
- Mikroservislərə keçid yalnız real domain və scaling ehtiyacı sübut olunduqda, ayrıca ADR
  ilə qiymətləndirilir — süni mikroservis yaradılmır.

## Alternativlər

- **Başlanğıcdan Microservices:** rədd edildi — ilk gündən distributed system
  mürəkkəbliyi (service discovery, distributed tracing, data consistency across
  services) biznes dəyəri yaratmadan əməliyyat xərci artırır.
- **Klassik monolit (EDA-sız, birbaşa funksiya çağırışları ilə):** rədd edildi — modullar
  arası sıx asılılıq yaradır, gələcək ayrılmağı çətinləşdirir, audit/retry/replay kimi
  tələbləri təbii dəstəkləmir.
