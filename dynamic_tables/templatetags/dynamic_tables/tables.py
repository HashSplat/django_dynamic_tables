from .base import register, get_url_modifiers


@register.inclusion_tag("dynamic_tables/table.html", takes_context=True)
def render_table(context, table=None, use_pagination=True, use_load_more=False):
    if table:
        context["table"] = table

    if use_load_more:
        context["use_load_more"] = True
    elif use_pagination:
        context["use_pagination"] = True
    elif "is_paginated" in context:
        context["use_pagination"] = True

    # Sorting and Filtering support
    context = get_url_modifiers(context)

    return context


@register.simple_tag
def render_table_cell(table, row, col, row_idx=None):
    return table.render(row, col, row_idx=row_idx)
