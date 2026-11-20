"""Preserve document order at individual entity write points."""


def order_document(document, template):
    """Preserve values and put affiliation campuses last, defaulting to []."""
    trailing = {"campuses"} if "campuses" in template else set()
    keys = ["_id", *(key for key in template if key not in trailing)]
    ordered = {key: document[key] for key in keys if key in document}
    ordered.update((key, value) for key, value in document.items()
                   if key not in ordered and key not in trailing)
    if trailing:
        ordered["campuses"] = document.get("campuses", [])
    return ordered


def insert_only_update(document):
    """Atomic ordered alternative to $setOnInsert (MongoDB >= 4.2).

    The upsert filter must not seed _id; existing documents always have _id.
    The complete literal retains BSON order and protects dollar-prefixed text.
    Matching documents are returned unchanged, including their field order.
    """
    return [{"$replaceRoot": {"newRoot": {"$cond": [
        {"$eq": [{"$type": "$_id"}, "missing"]},
        {"$literal": document},
        "$$ROOT",
    ]}}}]
