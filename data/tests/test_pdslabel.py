from lsn_data.pdslabel import parse_label_text

SAMPLE = '''PDS_VERSION_ID            = "PDS3"
PRODUCT_VERSION_ID        = "V2.0"
MISSION_PHASE_NAME        = {"COMMISSIONING","NOMINAL MISSION","SCIENCE
                              MISSION"}
DESCRIPTION               = "line one
   line two."
OBJECT = IMAGE
  LINES = 30400
  SCALING_FACTOR = 0.5
  OFFSET = 1737400.
  UNIT = METER
END_OBJECT = IMAGE
/* comment = ignored */
MAP_RESOLUTION = 1516.17 <pix/deg>
A_AXIS_RADIUS = 1737.4 <km>
CENTER_LATITUDE = -90 <deg>
FIRST_STANDARD_PARALLEL = 'N/A'
END
'''


def test_parse():
    d = parse_label_text(SAMPLE)
    assert d["PRODUCT_VERSION_ID"] == "V2.0"
    assert d["MISSION_PHASE_NAME"] == ["COMMISSIONING", "NOMINAL MISSION", "SCIENCE MISSION"]
    assert d["DESCRIPTION"] == "line one line two."
    assert d["LINES"] == 30400 and d["SCALING_FACTOR"] == 0.5 and d["OFFSET"] == 1737400.0
    assert d["UNIT"] == "METER"
    assert d["MAP_RESOLUTION"] == 1516.17 and d["A_AXIS_RADIUS"] == 1737.4 and d["CENTER_LATITUDE"] == -90
    assert d["FIRST_STANDARD_PARALLEL"] == "N/A"
    assert "comment" not in d
