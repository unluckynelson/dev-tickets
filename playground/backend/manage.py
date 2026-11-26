#!/usr/bin/env python
"""The playground host: the smallest Django project that runs Dev Tickets."""

import os
import sys

if __name__ == "__main__":
    # Set, not setdefault: a shell that exports another project's settings module
    # must not hijack this one.
    os.environ["DJANGO_SETTINGS_MODULE"] = "playground.settings"
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
