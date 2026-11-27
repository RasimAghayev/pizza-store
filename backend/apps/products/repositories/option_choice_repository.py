from apps.products.models import OptionChoice


class OptionChoiceRepository:
    def create(self, *, option_group_id: int, name: str, price_delta) -> OptionChoice:
        return OptionChoice.objects.create(
            option_group_id=option_group_id, name=name, price_delta=price_delta
        )

    def get_by_id(self, option_choice_id: int) -> OptionChoice | None:
        return OptionChoice.objects.filter(pk=option_choice_id).first()

    def all_for_option_group(self, option_group_id: int):
        return list(OptionChoice.objects.filter(option_group_id=option_group_id))

    def filter_by_ids(self, option_choice_ids) -> list[OptionChoice]:
        return list(OptionChoice.objects.filter(pk__in=option_choice_ids))

    def delete(self, option_choice: OptionChoice) -> None:
        option_choice.delete()
