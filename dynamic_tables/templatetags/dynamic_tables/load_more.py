from django.utils.safestring import mark_safe

from .base import register


__all__ = ["render_load_more"]


@register.inclusion_tag("dynamic_tables/load_more.html", takes_context=True)
def render_load_more(context):
    """Render a load more data button with javascript functionality.

    Must implement function load_more_data(json) javascript function before this tag is called.

    Uses pagination in order to work.
    """
    try:
        context["page_sorting"] = context["request"].GET.get("sort")
    except KeyError:
        pass

    return context


@register.inclusion_tag("dynamic_tables/load_more_btn.html", takes_context=True)
def render_load_more_btn(context):
    """Render a load more data button (only render the button)."""
    return context
