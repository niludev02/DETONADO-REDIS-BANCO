import markdown as markdown_lib
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def markdown_safe(value):
    html = markdown_lib.markdown(value or "", extensions=["extra", "nl2br"])
    return mark_safe(nh3.clean(html))