"""Allow ``python -m e2e`` / ``python -m e2e.cli``."""

from e2e.cli import main

raise SystemExit(main())
