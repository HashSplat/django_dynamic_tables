from django import template

register = template.Library()


def get_url_modifiers(context):
    # ===== Sorting and Filtering support =====
    if "base_url" not in context:
        try:
            base_url = "?" + context["request"].get_full_path().split("?", 1)[1]
        except IndexError:
            base_url = "?"
        context["base_url"] = base_url
    else:
        base_url = context["base_url"]
    # ===== END Sorting =====

    # ===== Modify Page URL =====
    if "base_page_url" not in context:
        try:
            page_name = context["view"].page_kwarg
        except:
            page_name = "page"
        try:
            if page_name+"=" in base_url:
                start, end = base_url.split(page_name+"=", 1)
                if "&" in end:
                    rm, end = end.split("&", 1)
                else:
                    end = ""
                    if start.endswith("&"):
                        start = start[:-1]
                base_page_url = start + end + "&"+page_name+"="  # should end with "&"
            else:
                base_page_url = base_url + "&"+page_name+"="
        except IndexError:
            base_page_url = "?"+page_name+"="
        context["base_page_url"] = base_page_url
    # ===== END Modify Page URL =====

    # ===== Modify order_by URL =====
    if "base_order_by_url" not in context:
        try:
            order_by_name = context["view"].order_by_name
        except:
            order_by_name = "order_by"

        try:
            if order_by_name+"=" in base_url:
                start, end = base_url.split(order_by_name+"=", 1)
                if "&" in end:
                    rm, end = end.split("&", 1)
                else:
                    end = ""
                    if start.endswith("&"):
                        start = start[:-1]
                base_order_by_url = start + end + "&"+order_by_name+"="  # should end with "&"
            else:
                base_order_by_url = base_url + "&"+order_by_name+"="
        except IndexError:
            base_order_by_url = "?"+order_by_name+"="
        context["base_order_by_url"] = base_order_by_url
    # ===== END Modify order_by URL =====

    return context
