#!/usr/bin/env python3
"""
MMSI encoder / decoder  (ITU-R M.585)  — AI-assisted (Claude)
=============================================================
Maritime Mobile Service Identity: a 9-digit identity used by DSC/AIS/GMDSS to
address a station. This parses and validates an MMSI, classifies its category,
and resolves the Maritime Identification Digits (MID) to a country. Also builds
(encodes) an MMSI of a given category for a MID.

Category rules (ITU-R M.585):
  MIDxxxxxx        ship station (MID = first 3 digits)
  0MIDxxxxx        group of ships
  00MIDxxxx        coast station
  111MIDxxx        SAR aircraft
  99MIDxxxx        aids to navigation (AtoN)
  98MIDxxxx        craft associated with a parent ship
  8xxxxxxxx        handheld VHF / DSC (no national MID)
"""
# Representative MID -> country table (ITU). Subset of the full list; extend freely.
MID = {
 "201":"Albania","202":"Andorra","203":"Austria","204":"Azores","205":"Belgium","206":"Belarus",
 "207":"Bulgaria","208":"Vatican","209":"Cyprus","210":"Cyprus","211":"Germany","212":"Cyprus",
 "219":"Denmark","220":"Denmark","224":"Spain","225":"Spain","226":"France","227":"France","228":"France",
 "230":"Finland","232":"United Kingdom","233":"United Kingdom","234":"United Kingdom","235":"United Kingdom",
 "236":"Gibraltar","237":"Greece","238":"Croatia","239":"Greece","240":"Greece","244":"Netherlands",
 "245":"Netherlands","246":"Netherlands","247":"Italy","248":"Malta","249":"Malta","250":"Ireland",
 "255":"Madeira","256":"Malta","257":"Norway","258":"Norway","259":"Norway","261":"Poland","263":"Portugal",
 "265":"Sweden","266":"Sweden","269":"Switzerland","271":"Turkey","273":"Russia","303":"Alaska (USA)",
 "338":"USA","366":"USA","367":"USA","368":"USA","369":"USA","316":"Canada","309":"Bahamas","311":"Bahamas",
 "314":"Barbados","339":"Jamaica","343":"St Lucia","345":"Mexico","347":"St Vincent","348":"British Virgin Is",
 "351":"Panama","352":"Panama","354":"Panama","370":"Panama","371":"Panama","372":"Panama","373":"Panama",
 "374":"Panama","375":"St Kitts & Nevis","377":"St Kitts & Nevis","378":"British Virgin Is","379":"US Virgin Is",
 "431":"Japan","432":"Japan","440":"South Korea","441":"South Korea","445":"North Korea","457":"Mongolia",
 "477":"Hong Kong","503":"Australia","512":"New Zealand","525":"Indonesia","533":"Malaysia","563":"Singapore",
 "564":"Singapore","565":"Singapore","566":"Singapore","574":"Vietnam","701":"Argentina","710":"Brazil",
 "720":"Bolivia","725":"Chile","730":"Colombia","735":"Ecuador","740":"Falkland Is","750":"India",
 "755":"Paraguay","760":"Peru","770":"Uruguay","775":"Venezuela",
}

def _mid_country(mid):
    return MID.get(mid, "MID "+mid+" (not in table)")

def decode(mmsi):
    s = str(mmsi).strip()
    if not s.isdigit() or len(s) != 9:
        return {"valid": False, "error": "MMSI must be exactly 9 digits"}
    out = {"valid": True, "mmsi": s}
    if s.startswith("111"):
        out.update(category="SAR aircraft", mid=s[3:6], country=_mid_country(s[3:6]))
    elif s.startswith("00"):
        out.update(category="Coast station", mid=s[2:5], country=_mid_country(s[2:5]))
    elif s.startswith("0"):
        out.update(category="Group of ships", mid=s[1:4], country=_mid_country(s[1:4]))
    elif s.startswith("99"):
        out.update(category="Aid to navigation (AtoN)", mid=s[2:5], country=_mid_country(s[2:5]))
    elif s.startswith("98"):
        out.update(category="Craft w/ parent ship", mid=s[2:5], country=_mid_country(s[2:5]))
    elif s.startswith("8"):
        out.update(category="Handheld VHF/DSC", mid="-", country="(no national MID)")
    else:
        out.update(category="Ship station", mid=s[0:3], country=_mid_country(s[0:3]))
    return out

def encode(category, mid, serial):
    """Build an MMSI for a category. serial is the national part (digits)."""
    mid = str(mid); serial = str(serial)
    cat = category.lower()
    if cat.startswith("ship"):   body = (mid + serial.ljust(6, "0"))[:9]
    elif cat.startswith("group"):body = ("0" + mid + serial.ljust(5, "0"))[:9]
    elif cat.startswith("coast"):body = ("00" + mid + serial.ljust(4, "0"))[:9]
    elif "sar" in cat:           body = ("111" + mid + serial.ljust(3, "0"))[:9]
    elif "aton" in cat or "navigation" in cat: body = ("99" + mid + serial.ljust(4, "0"))[:9]
    else: raise ValueError("unknown category")
    return body.ljust(9, "0")[:9]

if __name__ == "__main__":
    for m in ["314123456", "003140000", "111314123", "812345678", "538001234", "99314abc1"]:
        print(m, "->", decode(m))
    print("encode ship 314 ser 1234 ->", encode("ship", "314", "1234"))
    print("encode coast 232 ser 7 ->", encode("coast", "232", "7"))
