"""Streamlit entry point for the Phase 0 prototype."""

from phase0_analyzer.config import get_settings
from phase0_analyzer.database import initialize_database
from phase0_analyzer.ui.home import render_home


def main() -> None:
    """Initialize local resources and render the startup screen."""
    settings = get_settings()
    initialize_database(settings)
    render_home(settings)


if __name__ == "__main__":
    main()
