from django.conf import settings
from django.utils.html import format_html
from wagtail import hooks


@hooks.register("insert_global_admin_js")
def demo_site_admin_banner():
    # Staging only: the same red bar as the public site, so nobody edits the demo thinking it's live.
    if not settings.DEMO_SITE:
        return ""
    return format_html(
        "<script>document.addEventListener('DOMContentLoaded',function(){{"
        "var b=document.createElement('div');b.textContent='{}';"
        "b.style.cssText='position:fixed;left:0;right:0;bottom:0;z-index:10000;padding:8px 16px;"
        "text-align:center;font:700 14px/1.3 sans-serif;color:#fff;pointer-events:none;"
        "background:repeating-linear-gradient(-45deg,#B3261E 0 18px,#8E1B15 18px 36px)';"
        "document.body.appendChild(b);}});</script>",
        "DEMO SITE ADMIN — changes here do not affect the real fedcove.farm",
    )
