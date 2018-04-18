from django.core.paginator import Paginator, InvalidPage
from django.http import Http404

from .base import register, get_url_modifiers
from dynamic_tables.views import PaginatorMixin


__all__ = ["paginate_query", "render_pagination"]


@register.simple_tag(takes_context=True)
def paginate_query(context, queryset, context_object_name, paginate_by, page_kwarg="page",
                   allow_empty=True, paginate_orphans=0, ordering=None, paginator_class=Paginator):
    paginator = paginator_class(queryset, paginate_by, orphans=paginate_orphans, allow_empty_first_page=allow_empty)
    page = context["request"].GET.get(page_kwarg) or 1
    try:
        page_number = int(page)
    except ValueError:
        if page == "last":
            page_number = paginator.num_pages
        else:
            raise Http404("Page is not 'last', nor can it be converted to an int.")
    try:
        page = paginator.page(page_number)
        context["paginator"] = paginator
        context["page_obj"] = page
        context["is_paginated"] = page.has_other_pages()
        context[context_object_name] = page.object_list

    except InvalidPage as e:
        raise Http404(('Invalid page (%(page_number)s): %(message)s') % {
            'page_number': page_number,
            'message': str(e)
        })


def get_pagination_class(idx, page_num):
    if idx == page_num:
        return "waves_effect active"
    return "waves_effect"


@register.inclusion_tag("dynamic_tables/pagination.html", takes_context=True)
def render_pagination(context):
    """Render a pagination."""
    # Sorting and Filtering support
    context = get_url_modifiers(context)
    base_page_url = context["base_page_url"]

    try:
        page_obj = context["page_obj"]
    except KeyError:
        return context

    num_pages = page_obj.paginator.num_pages
    page_num = page_obj.number

    if num_pages <= 10:
        page_obj_pages = [{"number": i+1, "icon": "", "url": base_page_url+str(i+1),
                           "class": get_pagination_class(i+1, page_num)}
                          for i in range(num_pages)]
    else:
        first_page = {"number": 1, "icon": "skip_previous", "url": base_page_url+"1", "class": "waves-effect",
                      "tooltip": "First Page"}
        prev_page = {"number": page_num-1, "icon": "chevron_left", "url": base_page_url+str(page_num-1),
                     "class": "waves-effect", "tooltip": "Previous Page"}

        next_page = {"number": page_num+1, "icon": "chevron_right", "url": base_page_url+str(page_num+1),
                     "class": "waves-effect", "tooltip": "Next Page"}
        last_page = {"number": num_pages, "icon": "skip_next", "url": base_page_url+str(num_pages),
                     "class": "waves-effect", "tooltip": "Last Page (" + str(num_pages) + ")"}

        # Get page_numbers
        spread = 5
        start = page_num - int(spread/2)
        end = page_num + int(spread/2)
        if len(range(start, end)) < spread:
            end += 1

        if start < 1:
            diff = 1 - start
            start += diff
            end += diff
        elif end > num_pages:
            diff = (end - 1) - num_pages
            start -= diff
            end -= diff

        # List pages
        page_obj_pages = [first_page, prev_page]
        page_obj_pages += [{"number": i, "icon": "", "url": base_page_url+str(i), "class": get_pagination_class(i, page_num)}
                            for i in range(start, end)]
        page_obj_pages.extend([next_page, last_page])

        if page_num == 1:
            # Fix First chevrons
            first_page["class"] = "disabled"
            first_page["url"] = ""
            prev_page["class"] = "disabled"
            prev_page["url"] = ""
            prev_page["number"] = 1

        elif page_num == num_pages:
            # Fix First chevrons
            next_page["class"] = "disabled"
            next_page["url"] = ""
            next_page["number"] = page_num
            last_page["class"] = "disabled"
            last_page["url"] = ""

        # Add text indicators that show there are more pages than shown.
        if start == 1:
            page_obj_pages.insert(-2, {"number": "\u2022", "class": "disabled", "tooltip": "More Pages Exist"})

        elif end == num_pages:
            page_obj_pages.insert(2, {"number": "\u2022", "class": "disabled", "tooltip": "More Pages Exist"})

        else:
            page_obj_pages.insert(2, {"number": "\u2022", "class": "disabled", "tooltip": "More Pages Exist"})
            page_obj_pages.insert(-2, {"number": "\u2022", "class": "disabled", "tooltip": "More Pages Exist"})

    context["page_obj_pages"] = page_obj_pages

    return context
