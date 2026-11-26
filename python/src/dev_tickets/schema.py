"""The package's own GraphQL schema, served at `devtickets/graphql/`.

Its own endpoint rather than types merged into the host's schema: the package then
knows nothing about the host's GraphQL, and works in a host that has none.
"""

from __future__ import annotations

import strawberry

from .mutations import Mutation
from .queries import Query

schema = strawberry.Schema(query=Query, mutation=Mutation)
