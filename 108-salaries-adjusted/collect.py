"""Pull BEA Regional Price Parities by metro area (MARPP) for the cost-of-living adjustment.

The API key lives in BEA_API_KEY, never in this repo.

BEA returns "This UserId is not active" intermittently for a freshly activated
key — activation propagates across their servers unevenly — so every call
retries rather than trusting one answer.
"""
import json, os, pathlib, sys, time
import urllib.parse, urllib.request

HERE = pathlib.Path(__file__).parent
BASE = "https://apps.bea.gov/api/data/"
KEY = os.environ.get("BEA_API_KEY")
if not KEY:
    sys.exit("Set BEA_API_KEY. The key is not stored in this repo.")

TRANSIENT = ("not active", "temporarily unavailable", "try again")


def api(**params):
    params.update(UserID=KEY, ResultFormat="json")
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(12):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                res = json.loads(r.read())["BEAAPI"]["Results"]
        except Exception as e:
            res = {"Error": {"APIErrorDescription": str(e)}}
        err = res.get("Error")
        if not err:
            return res
        msg = str(err if isinstance(err, str) else err.get("APIErrorDescription", err))
        if not any(t in msg.lower() for t in TRANSIENT):
            sys.exit(f"BEA error: {msg}")
        print(f"  transient ({msg[:40]}…) retry {attempt+1}", file=sys.stderr)
        time.sleep(10)
    sys.exit("BEA kept returning a transient error after 12 attempts.")


def main():
    lines = api(method="GetParameterValuesFiltered", datasetname="Regional",
                TargetParameter="LineCode", TableName="MARPP")["ParamValue"]
    print("MARPP line codes:")
    for l in lines:
        print("  ", l)

    years = api(method="GetParameterValuesFiltered", datasetname="Regional",
                TargetParameter="Year", TableName="MARPP", LineCode=1)["ParamValue"]
    latest = max(y["Key"] if "Key" in y else y["Year"] for y in years)
    print("latest MARPP year:", latest)

    out = {"year": latest, "line_codes": lines, "rpp": {}}
    # Labels must match the LineCode descriptions printed above exactly — 3 is
    # Rents and 4 is Utilities, not a single "housing" bucket.
    for code, label in ((1, "all_items"), (2, "goods"), (3, "rents"),
                        (4, "utilities"), (5, "other_services")):
        d = api(method="GetData", datasetname="Regional", TableName="MARPP",
                LineCode=code, GeoFips="MSA", Year=latest)["Data"]
        out["rpp"][label] = {r["GeoFips"]: {"name": r["GeoName"], "value": r["DataValue"]}
                             for r in d}
        print(f"  {label}: {len(d)} metros")

    out["source"] = ("BEA Regional Price Parities by MSA (table MARPP), "
                     f"year {latest}, via BEA Data API — https://apps.bea.gov/api/")
    (HERE / "rpp.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    print("wrote rpp.json")


if __name__ == "__main__":
    main()
