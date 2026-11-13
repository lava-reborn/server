"""Optional, versioned engines. Install only inside the range implementation."""


def install():
    from training import formulas
    if not formulas.available():
        from training.engines import simulator_v1
        formulas.register(simulator_v1)
        # Read-only catalogue queries may precede explicit startup. Rebuild
        # their source list before freezing private item IDs and display data.
        from training import catalog
        catalog.item_catalogue.cache_clear()
