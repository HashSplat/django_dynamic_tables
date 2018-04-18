from django.utils.safestring import mark_safe

from .base import register, get_url_modifiers


__all__ = ["render_load_more", 'render_load_more_btn', 'render_parse_tag']


@register.inclusion_tag("dynamic_tables/load_more.html", takes_context=True)
def render_load_more(context):
    """Render a load more data button with javascript functionality.

    Must implement function load_more_data(json) javascript function before this tag is called.

    Uses pagination in order to work.
    """
    # Sorting and Filtering support
    context = get_url_modifiers(context)

    return context


@register.inclusion_tag("dynamic_tables/load_more_btn.html", takes_context=True)
def render_load_more_btn(context):
    """Render a load more data button (only render the button)."""
    return context


@register.inclusion_tag("dynamic_tables/parse_tag.html")
def render_parse_tag():
    """Render a load more data button (only render the button)."""
    return {}  # No context, only javascript
