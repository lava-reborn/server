"""Wire type namespaces shared by persistent items and runtime-only templates.

Existing persistent 60000..60009 types stay unchanged. Reserved bands cannot
be allocated to persistent content, even when optional runtime modes are off.
"""
PRIVATE_BANDS = ((54000, 59999), (61000, 61999))


def private(type_id):
    return type(type_id) is int and any(first <= type_id <= last for first, last in PRIVATE_BANDS)
