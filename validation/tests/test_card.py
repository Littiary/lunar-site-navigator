"""The validation card is rebuilt from the stored data and must agree with the committed file."""

import json
import re

from validation.card import build

# Checks that fail as registered. A failed check stays on the card as failed; this list
# only makes sure that no further check fails unnoticed and that none of these turns
# into a pass without the card being rebuilt and the cause being looked at.
KNOWN_FAILED = ["image_strip_agreement"]


def test_card_rebuilds_and_agrees_with_the_committed_file():
    card = build.build()
    assert len(card["checks"]) == 32
    assert card["summary"]["failed_ids"] == KNOWN_FAILED
    assert card["summary"]["passed"] == len(card["checks"]) - len(KNOWN_FAILED)
    stored = json.loads((build.HERE / "validation_card.json").read_text(encoding="utf-8"))
    assert stored["summary"] == card["summary"]
    assert [c["id"] for c in stored["checks"]] == [c["id"] for c in card["checks"]]
    for old, new in zip(stored["checks"], card["checks"]):
        assert old["threshold"] == new["threshold"], old["id"]
        assert old["status"] == new["status"] == ("FAIL" if old["id"] in KNOWN_FAILED else "PASS"), old["id"]
        # The committed number is the measured one, not a typed one.
        assert abs(old["measured"]["value"] - new["measured"]["value"]) <= 1e-6 * max(1.0, abs(new["measured"]["value"])), old["id"]
        assert old["limit"] == new["limit"], old["id"]
    assert all(item["state"] for item in card["not_validated"])


def test_every_check_states_its_main_limit_in_one_sentence():
    stored = json.loads((build.HERE / "validation_card.json").read_text(encoding="utf-8"))
    for check in stored["checks"]:
        limit = check["limit"]
        assert limit and limit.endswith("."), check["id"]
        assert not re.search(r"[.!?]\s+[A-Z]", limit), check["id"]


def test_a_failed_check_is_shown_as_failed():
    stored = json.loads((build.HERE / "validation_card.json").read_text(encoding="utf-8"))
    text = (build.HERE / "validation_card.md").read_text(encoding="utf-8")
    strip = next(check for check in stored["checks"] if check["id"] == "image_strip_agreement")
    assert strip["threshold"] == {"value": 0.90, "unit": "share of points", "comparison": ">="}
    assert strip["status"] == ("PASS" if strip["measured"]["value"] >= 0.90 else "FAIL")
    assert text.count("**FAIL**") == stored["summary"]["failed"] == len(KNOWN_FAILED)
    assert f"{stored['summary']['passed']} of {len(stored['checks'])} checks pass; 1 fails" in text
