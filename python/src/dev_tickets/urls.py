"""Mount with `path("", include("dev_tickets.urls"))`.

`devtickets-files/` is its own prefix, apart from the GraphQL endpoint, so a reverse
proxy that sends only some paths to Django can route uploads by prefix.

`devtickets/api/v1/` is the hub's API for other installs (`hub.py`); it answers 404
unless `MODE = "hub"`.
"""

from django.urls import path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from . import endpoints, hub, settings_views, views

urlpatterns = [
    path("devtickets/graphql/", endpoints.graphql, name="dev_tickets_graphql"),
    path(
        "devtickets/csrf/",
        require_GET(ensure_csrf_cookie(views.csrf)),
        name="dev_tickets_csrf",
    ),
    path("devtickets-files/attachment/<int:attachment_id>/", endpoints.attachment_file),
    path("devtickets-files/<str:ref>/", endpoints.upload),
    # The Settings dialog's Connection section: always this install, never forwarded.
    path("devtickets/settings/", settings_views.settings_state),
    path("devtickets/settings/connection/", settings_views.save_connection),
    path("devtickets/settings/connection/test/", settings_views.test_connection),
    path("devtickets/settings/clients/", settings_views.add_client),
    path("devtickets/settings/clients/<str:pk>/", settings_views.update_client),
    path("devtickets/settings/clients/<str:pk>/rotate/", settings_views.rotate_client),
    path("devtickets/api/v1/graphql/", hub.graphql, name="dev_tickets_hub_graphql"),
    path("devtickets/api/v1/files/attachment/<int:attachment_id>/", hub.attachment_file),
    path("devtickets/api/v1/files/<str:ref>/", hub.upload),
]
