from typing import Any

from django import forms


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
            if self.instance.pk is not None:
                field.required = False
                field.widget.attrs["placeholder"] = self.filled_value_placeholder

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        for field_name in self.masked_fields:
            if self.instance.pk is not None and not cleaned_data.get(field_name):
                cleaned_data.pop(field_name, None)
        return cleaned_data

    def _get_validation_exclusions(self) -> set[str]:
        # django-stubs doesn't expose ModelForm._get_validation_exclusions
        exclude: set[str] = super()._get_validation_exclusions()  # type: ignore[misc]
        if self.instance.pk is not None:
            exclude.update(self.masked_fields)
        return exclude

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
