"""calls shared/events/relay.py::relay_pending -- this file only exists because Django's
management-command discovery requires `<app>/management/commands/<name>.py`; the actual
poller logic lives in relay.py, not here."""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from shared.events.publisher import connection_parameters
from shared.events.relay import relay_pending


class Command(BaseCommand):
    help = "Relays pending Transactional Outbox rows of --model to --exchange (ADR 0005)."

    def add_arguments(self, parser):
        parser.add_argument("--model", required=True, help="Dotted app_label.ModelName")
        parser.add_argument("--exchange", required=True, help="Target topic exchange")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--host", default=None, help="Override RABBITMQ_HOST (testing only)")
        parser.add_argument(
            "--port", type=int, default=None, help="Override RABBITMQ_PORT (testing only)"
        )

    def handle(self, *args, **options):
        try:
            app_label, model_name = options["model"].split(".", 1)
            model = apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as exc:
            raise CommandError(f"Unknown model {options['model']!r}") from exc

        parameters = connection_parameters(host=options["host"], port=options["port"])
        result = relay_pending(
            model,
            exchange=options["exchange"],
            connection_parameters=parameters,
            limit=options["limit"],
        )
        self.stdout.write(f"Relayed: {result.published} published, {result.failed} failed.")
