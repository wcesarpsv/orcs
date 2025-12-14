import json
import os
import sys

REGISTRY_PATH = "config/image_registry.json"
PROJECT_ROOT = "."


REQUIRED_FIELDS = {"image_id", "path", "procedure", "tags"}
GENERIC_TAGS = {"error", "issue", "problem", "unknown"}


def error(msg):
    print(f"❌ ERROR: {msg}")
    return False


def warning(msg):
    print(f"⚠️ WARNING: {msg}")
    return True


def ok(msg):
    print(f"✅ OK: {msg}")
    return True


def validate():
    if not os.path.exists(REGISTRY_PATH):
        return error(f"{REGISTRY_PATH} not found")

    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "images" not in data or not isinstance(data["images"], list):
        return error("'images' must be a list")

    image_ids = set()
    all_ok = True

    for i, img in enumerate(data["images"], start=1):
        prefix = f"[Image #{i}]"

        # Required fields
        missing = REQUIRED_FIELDS - img.keys()
        if missing:
            all_ok &= error(f"{prefix} Missing fields: {missing}")
            continue

        # image_id uniqueness
        if img["image_id"] in image_ids:
            all_ok &= error(f"{prefix} Duplicate image_id: {img['image_id']}")
        image_ids.add(img["image_id"])

        # Path exists
        img_path = os.path.join(PROJECT_ROOT, img["path"])
        if not os.path.exists(img_path):
            all_ok &= error(f"{prefix} Image file not found: {img['path']}")
        else:
            ok(f"{prefix} Image file exists")

        # Procedure exists
        proc_path = os.path.join(PROJECT_ROOT, "documents", img["procedure"])
        if not os.path.exists(proc_path):
            all_ok &= error(f"{prefix} Procedure file not found: {img['procedure']}")
        else:
            ok(f"{prefix} Procedure file exists")

        # Tags validation
        if not isinstance(img["tags"], list) or not img["tags"]:
            all_ok &= error(f"{prefix} Tags must be a non-empty list")
        else:
            for tag in img["tags"]:
                if " " in tag:
                    all_ok &= error(f"{prefix} Tag contains space: '{tag}'")
                if tag.lower() in GENERIC_TAGS:
                    warning(f"{prefix} Generic tag used: '{tag}'")

    return all_ok


if __name__ == "__main__":
    print("🔍 Validating image_registry.json...\n")
    success = validate()

    if success:
        print("\n🎉 Validation PASSED")
        sys.exit(0)
    else:
        print("\n🚫 Validation FAILED")
        sys.exit(1)
