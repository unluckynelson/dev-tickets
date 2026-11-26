"""Mount with `path("", include("dev_tickets.urls"))`.

`devtickets-files/` is its own prefix, apart from the GraphQL endpoint, so a reverse
proxy that sends only some paths to Django can route uploads by prefix.
"""

from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from strawberry.django.views import GraphQLView

from . import views
from .schema import schema

urlpatterns = [
    path("devtickets/graphql/", GraphQLView.as_view(schema=schema), name="dev_tickets_graphql"),
    path(
        "devtickets/csrf/",
        require_GET(ensure_csrf_cookie(views.csrf)),
        name="dev_tickets_csrf",
    ),
    path("devtickets-files/attachment/<int:attachment_id>/", views.attachment_file),
    path("devtickets-files/<str:ref>/", views.upload),
]
