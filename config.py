from firestore_client import get_db

DEFAULT_FAMILY_ID = "leo"


def load_family(family_id: str = DEFAULT_FAMILY_ID) -> dict:
    """Load family config from Firestore families/{family_id}."""
    doc = get_db().collection("families").document(family_id).get()
    if not doc.exists:
        raise ValueError(f"Family '{family_id}' not found in Firestore")
    data = doc.to_dict()
    data["family_id"] = doc.id
    return data
