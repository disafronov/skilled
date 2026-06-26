from typing import Any

from django import forms
from django.db.models import Model

TIMESTAMP_FIELDS = ("updated_at", "created_at")


def model_field_names(
    model: type[Model],
    *,
    exclude: tuple[str, ...] = (),
    include_pk: bool = False,
) -> tuple[str, ...]:
    excluded_fields = set(exclude)
    return tuple(
        field.name
        for field in model._meta.fields
        if field.name not in excluded_fields and (include_pk or not field.primary_key)
    )


def model_admin_fields(
    model: type[Model],
    *,
    exclude: tuple[str, ...] = (),
    include_pk: bool = False,
) -> tuple[str, ...]:
    field_names = model_field_names(model, exclude=exclude, include_pk=include_pk)
    timestamp_fields = [name for name in TIMESTAMP_FIELDS if name in field_names]
    regular_fields = [name for name in field_names if name not in timestamp_fields]
    return (*regular_fields, *timestamp_fields)


def model_admin_list_display(
    model: type[Model],
    *,
    exclude: tuple[str, ...] = (),
    include_pk: bool = False,
    replacements: dict[str, str] | None = None,
) -> tuple[str, ...]:
    replacements = replacements or {}
    excluded_fields = (*exclude, "created_at")
    return tuple(
        replacements.get(field_name, field_name)
        for field_name in model_field_names(
            model,
            exclude=excluded_fields,
            include_pk=include_pk,
        )
    )


class AdminModelForm(forms.ModelForm):
    masked_fields: tuple[str, ...] = ()
    standard_width_style = "width: 32rem; max-width: 100%;"
    filled_value_placeholder = "Already set. Enter a new value to replace it."

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._set_standard_widths()
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

    def _set_standard_widths(self) -> None:
        excluded_widgets = (
            forms.CheckboxInput,
            forms.CheckboxSelectMultiple,
            forms.RadioSelect,
            forms.Textarea,
        )
        for field in self.fields.values():
            if isinstance(field.widget, excluded_widgets):
                continue
            style = field.widget.attrs.get("style", "")
            field.widget.attrs["style"] = f"{style} {self.standard_width_style}".strip()
