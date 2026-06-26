from typing import Any

from django import forms


class MaskedFieldsAdminForm(forms.ModelForm):
    masked_fields: tuple[str, ...] = ()
    filled_value_placeholder = "Already set. Enter a new value to replace it."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for field_name in self.masked_fields:
            field = self.fields[field_name]
            field.widget = forms.PasswordInput(
                attrs=field.widget.attrs,
                render_value=False,
            )
            if self._instance_has_value(field_name):
                field.required = False
                field.widget.attrs["placeholder"] = self.filled_value_placeholder

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        for field_name in self.masked_fields:
            if not cleaned_data.get(field_name) and self._instance_has_value(
                field_name
            ):
                cleaned_data[field_name] = getattr(self.instance, field_name)
        return cleaned_data

    def _instance_has_value(self, field_name: str) -> bool:
        return bool(self.instance and getattr(self.instance, field_name, None))
