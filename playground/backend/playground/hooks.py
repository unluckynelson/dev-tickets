"""Example hooks: what a host app tells Dev Tickets about itself."""


def context_label(request) -> str:
    # A real app would return the tenant or workspace the user is working in.
    return "Playground"


def avatar(user) -> str | None:
    # A real app would return the user's profile picture URL.
    return None
