"""Optional, versioned engines. Install only inside the range implementation."""


def install():
    from training import formulas
    if not formulas.available():
        from training.engines import simulator_v1
        formulas.register(simulator_v1)
