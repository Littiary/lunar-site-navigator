"""The validation card is rebuilt from the stored data and must agree with the committed file."""

import json

from validation.card import build


def test_card_rebuilds_and_every_check_passes():
    card = build.build()
    assert card["summary"]["failed"] == 0 and card["summary"]["passed"] == len(card["checks"]) == 20
    stored = json.loads((build.HERE / "validation_card.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in stored["checks"]] == [c["id"] for c in card["checks"]]
    for old, new in zip(stored["checks"], card["checks"]):
        assert old["threshold"] == new["threshold"], old["id"]
        assert old["status"] == new["status"] == "PASS", old["id"]
        # The committed number is the measured one, not a typed one.
        assert abs(old["measured"]["value"] - new["measured"]["value"]) <= 1e-6 * max(1.0, abs(new["measured"]["value"])), old["id"]
    assert all(item["state"] for item in card["not_validated"])
