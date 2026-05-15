# api/index.py
from flask import Flask, request, jsonify, send_from_directory
import json, os
from datetime import datetime, timedelta, timezone
import random
import requests
from requests.auth import HTTPBasicAuth
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# === SECURE CONFIG (from Vercel Environment Variables) ===
AUTH_HOST = "salep-auth.sce.manh.com"
API_HOST = "salep.sce.manh.com"
USERNAME_BASE = "sdtadmin@"
PASSWORD = os.getenv("MANHATTAN_PASSWORD")
CLIENT_ID = "omnicomponent.1.0.0"
CLIENT_SECRET = os.getenv("MANHATTAN_SECRET")

# === Usage ingest (dashboard → Neon) ===
USAGE_INGEST_URL = os.getenv("MANHATTAN_USAGE_INGEST_URL", "").strip()
USAGE_INGEST_SECRET = os.getenv("MANHATTAN_USAGE_INGEST_SECRET", "").strip()
APP_NAME = "banding"
APP_VERSION = "1.0.4"

# Critical: Fail fast if secrets missing
if not PASSWORD or not CLIENT_SECRET:
    raise Exception("Missing MANHATTAN_PASSWORD or MANHATTAN_SECRET environment variables")

# === HELPERS ===
def forward_usage_event(payload):
    """POST usage JSON to Manhattan app usage dashboard ingest (Neon)."""
    if not USAGE_INGEST_URL:
        print("[usage] MANHATTAN_USAGE_INGEST_URL not set; event not recorded")
        return
    headers = {"Content-Type": "application/json"}
    if USAGE_INGEST_SECRET:
        headers["Authorization"] = f"Bearer {USAGE_INGEST_SECRET}"
    try:
        requests.post(USAGE_INGEST_URL, json=payload, headers=headers, timeout=8)
    except Exception as e:
        print(f"[usage] Forward failed: {e}")

def get_manhattan_token(org):
    url = f"https://{AUTH_HOST}/oauth/token"
    username = f"{USERNAME_BASE}{org.lower()}"
    data = {
        "grant_type": "password",
        "username": username,
        "password": PASSWORD,
    }
    auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    try:
        r = requests.post(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=auth,
            timeout=30,
            verify=False,
        )
        r.raise_for_status()
        return r.json().get("access_token")
    except:
        return None

def search_orders(headers, org):
    """Search for orders with Status=7200"""
    url = f"https://{API_HOST}/dcorder/api/dcorder/order/search"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    
    payload = {
        "Query": "MinimumStatus= '7200' and MaximumStatus = '7200'",
        "Size": 1000,
        "Page": 0
    }
    
    print(f"[SEARCH_ORDERS] URL: {url}")
    print(f"[SEARCH_ORDERS] Payload: {json.dumps(payload, indent=2)}")
    print(f"[SEARCH_ORDERS] Organization: {org.upper()}")
    print(f"[SEARCH_ORDERS] FacilityId: {facility_id}")
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        print(f"[SEARCH_ORDERS] Status Code: {r.status_code}")
        
        if r.ok:
            response_data = r.json()
            print(f"[SEARCH_ORDERS] Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            # Extract orders from response
            orders = response_data.get("data", [])
            if isinstance(orders, list):
                print(f"[SEARCH_ORDERS] Found {len(orders)} orders")
                if len(orders) > 0:
                    print(f"[SEARCH_ORDERS] First order keys: {list(orders[0].keys()) if isinstance(orders[0], dict) else 'Not a dict'}")
                return orders
            print(f"[SEARCH_ORDERS] Orders is not a list: {type(orders)}")
            return []
        else:
            print(f"[SEARCH_ORDERS] Error response: {r.text[:500]}")
        return []
    except Exception as e:
        print(f"[SEARCH_ORDERS] Error: {str(e)}")
        import traceback
        print(f"[SEARCH_ORDERS] Traceback: {traceback.format_exc()}")
        return []

def olpn_status_under_9000(olpn):
    """Return True if oLPN Status is missing or < 9000 (include in count/display)."""
    status = olpn.get("Status") if olpn.get("Status") is not None else olpn.get("status")
    if status is None:
        return True
    try:
        return int(status) < 9000
    except (TypeError, ValueError):
        return True

def search_olpns(order_ids, headers, org):
    """Search for oLPNs for given order IDs"""
    if not order_ids:
        print(f"[SEARCH_OLPNS] No order IDs provided")
        return []
    
    url = f"https://{API_HOST}/pickpack/api/pickpack/olpn/search"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    
    # Format order IDs for query (comma-separated, single-quoted, in parentheses)
    order_ids_str = "', '".join(order_ids)
    # Template tells the API which fields to return (include Pk for olpn/save updates)
    payload = {
        "Query": f"OrderId in ('{order_ids_str}')",
        "Template": {
            "OrderId": None,
            "OlpnId": None,
            "Pk": None,
            "PK": None,
            "Status": None,
            "CurrentLocationId": None,
            "Weight": None,
            "EstimatedWeight": None,
            "TotalQty": None,
            "TotalLpnQty": None,
            "OlpnDetail": None,
            "Extended": {
                "CombinedOlpns": None
            }
        },
        "Size": 1000,
        "Page": 0
    }
    
    print(f"[SEARCH_OLPNS] URL: {url}")
    print(f"[SEARCH_OLPNS] Payload: {json.dumps(payload, indent=2)}")
    print(f"[SEARCH_OLPNS] Organization: {org.upper()}")
    print(f"[SEARCH_OLPNS] FacilityId: {facility_id}")
    print(f"[SEARCH_OLPNS] Searching for {len(order_ids)} order IDs")
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        print(f"[SEARCH_OLPNS] Status Code: {r.status_code}")
        
        if r.ok:
            response_data = r.json()
            print(f"[SEARCH_OLPNS] Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
            # Extract oLPNs from response
            olpns = response_data.get("data", [])
            if isinstance(olpns, list):
                print(f"[SEARCH_OLPNS] Found {len(olpns)} oLPNs")
                if len(olpns) > 0:
                    print(f"[SEARCH_OLPNS] First oLPN keys: {list(olpns[0].keys()) if isinstance(olpns[0], dict) else 'Not a dict'}")
                return olpns
            print(f"[SEARCH_OLPNS] oLPNs is not a list: {type(olpns)}")
            return []
        else:
            print(f"[SEARCH_OLPNS] Error response: {r.text[:500]}")
        return []
    except Exception as e:
        print(f"[SEARCH_OLPNS] Error: {str(e)}")
        import traceback
        print(f"[SEARCH_OLPNS] Traceback: {traceback.format_exc()}")
        return []

def search_locations(headers, org, location_ids):
    """
    Call /dcinventory/api/dcinventory/location/search to get DisplayLocation for each LocationId.
    location_ids: list of LocationId strings. Returns dict LocationId -> DisplayLocation (or LocationId if not found).
    """
    if not location_ids:
        return {}
    url = f"https://{API_HOST}/dcinventory/api/dcinventory/location/search"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    # Query: LocationId in ('Loc1','Loc2','Loc3')
    escaped = [str(lid).replace("'", "''") for lid in location_ids if lid]
    if not escaped:
        return {}
    in_clause = "', '".join(escaped)
    payload = {
        "Query": f"LocationId in ('{in_clause}')",
        "Size": 1000,
        "Template": {
            "LocationId": None,
            "DisplayLocation": None
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        if not r.ok:
            print(f"[SEARCH_LOCATIONS] Error: {r.status_code} {r.text[:300]}")
            return {}
        data = r.json()
        locs = data.get("data") or data.get("Data") or []
        if not isinstance(locs, list):
            return {}
        display_map = {}
        for item in locs:
            if not isinstance(item, dict):
                continue
            loc_id = item.get("LocationId") or item.get("locationId") or item.get("LocationID")
            display = item.get("DisplayLocation") or item.get("displayLocation")
            if loc_id is not None and str(loc_id).strip():
                display_map[str(loc_id).strip()] = (display if display is not None and str(display).strip() else str(loc_id).strip())
        print(f"[SEARCH_LOCATIONS] Resolved {len(display_map)} display locations")
        return display_map
    except Exception as e:
        print(f"[SEARCH_LOCATIONS] Exception: {e}")
        import traceback
        traceback.print_exc()
        return {}

def generate_random_divert_time():
    """Generate a random time within the last couple of hours"""
    now = datetime.now()
    # Random time between 2 hours ago and now
    hours_ago = random.uniform(0, 2)
    minutes_ago = random.uniform(0, 60)
    seconds_ago = random.uniform(0, 60)
    
    divert_time = now - timedelta(hours=hours_ago, minutes=minutes_ago, seconds=seconds_ago)
    return divert_time.strftime("%Y-%m-%d %H:%M:%S")

# === API ROUTES ===
@app.route('/api/auth', methods=['POST'])
def auth():
    org = request.json.get('org', '').strip()
    if not org:
        return jsonify({"success": False, "error": "ORG required"})
    token = get_manhattan_token(org)
    if token:
        return jsonify({"success": True, "token": token})
    return jsonify({"success": False, "error": "Auth failed"})

@app.route('/api/searchOrders', methods=['POST'])
def search_orders_endpoint():
    """Search for orders with Status=7200 and their associated oLPNs"""
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    
    if not org or not token:
        return jsonify({"success": False, "error": "ORG and token required"})
    
    print(f"\n=== [SEARCH_ORDERS_ENDPOINT] Starting search for ORG: {org.upper()} ===")
    
    headers = {"Authorization": f"Bearer {token}"}
    api_calls_log = []  # Track API calls for frontend logging
    
    # Step 1: Search for orders with Status=7200
    print(f"[SEARCH_ORDERS_ENDPOINT] Step 1: Searching for orders with Status=7200...")
    
    # Log order search API call details
    order_search_url = f"https://{API_HOST}/dcorder/api/dcorder/order/search"
    order_search_payload = {
        "Query": "MinimumStatus= '7200' and MaximumStatus = '7200'",
        "Size": 1000,
        "Page": 0
    }
    api_calls_log.append({
        "type": "order_search",
        "url": order_search_url,
        "payload": order_search_payload,
        "description": "Searching for orders with Status=7200"
    })
    
    orders = search_orders(headers, org)
    
    if not orders:
        print(f"[SEARCH_ORDERS_ENDPOINT] No orders found")
        return jsonify({
            "success": True,
            "results": [],
            "api_calls": api_calls_log
        })
    
    print(f"[SEARCH_ORDERS_ENDPOINT] Found {len(orders)} orders")
    
    # Extract OrderIds
    order_ids = [order.get("OrderId") for order in orders if order.get("OrderId")]
    print(f"[SEARCH_ORDERS_ENDPOINT] Extracted {len(order_ids)} order IDs: {order_ids[:5]}{'...' if len(order_ids) > 5 else ''}")
    
    if not order_ids:
        print(f"[SEARCH_ORDERS_ENDPOINT] No valid OrderIds found in orders")
        return jsonify({
            "success": True,
            "results": [],
            "api_calls": api_calls_log
        })
    
    # Step 2: Search for oLPNs for these orders
    print(f"[SEARCH_ORDERS_ENDPOINT] Step 2: Searching for oLPNs for {len(order_ids)} orders...")
    
    # Log oLPN search API call details
    olpn_search_url = f"https://{API_HOST}/pickpack/api/pickpack/olpn/search"
    order_ids_str = "', '".join(order_ids)
    olpn_search_payload = {
        "Query": f"OrderId in ('{order_ids_str}')",
        "Size": 1000,
        "Page": 0
    }
    api_calls_log.append({
        "type": "olpn_search",
        "url": olpn_search_url,
        "payload": olpn_search_payload,
        "description": f"Searching for oLPNs for {len(order_ids)} orders"
    })
    
    olpns = search_olpns(order_ids, headers, org)
    print(f"[SEARCH_ORDERS_ENDPOINT] Found {len(olpns)} oLPNs")
    
    # Step 3: Process and aggregate data
    print(f"[SEARCH_ORDERS_ENDPOINT] Step 3: Processing and aggregating data...")
    
    # Group oLPNs by OrderId (only include Status < 9000 for count/display)
    olpns_by_order = {}
    for olpn in olpns:
        if not olpn_status_under_9000(olpn):
            continue
        order_id = olpn.get("OrderId")
        if order_id:
            if order_id not in olpns_by_order:
                olpns_by_order[order_id] = []
            olpns_by_order[order_id].append(olpn)
    
    print(f"[SEARCH_ORDERS_ENDPOINT] Grouped oLPNs into {len(olpns_by_order)} orders")
    
    # Build results
    results = []
    for order in orders:
        order_id = order.get("OrderId")
        if not order_id:
            continue
        
        # Get oLPNs for this order
        order_olpns = olpns_by_order.get(order_id, [])
        
        # Get unique oLPN count
        unique_olpns = set()
        for olpn in order_olpns:
            olpn_id = olpn.get("oLPNId") or olpn.get("OlpnId") or olpn.get("olpnId")
            if olpn_id:
                unique_olpns.add(olpn_id)
        
        # Get Location from first oLPN where CurrentLocationId is not null
        location = None
        for olpn in order_olpns:
            location = olpn.get("CurrentLocationId") or olpn.get("currentLocationId") or olpn.get("CurrentLocation")
            if location:
                break
        
        # Get SVIA (ShipViaId) from order or first oLPN
        svia = order.get("ShipViaId") or order.get("shipViaId") or order.get("ShipVia")
        if not svia and order_olpns:
            svia = order_olpns[0].get("ShipViaId") or order_olpns[0].get("shipViaId") or order_olpns[0].get("ShipVia")
        
        # DivertDateTime will be generated in frontend using user's timezone
        # Placeholder value (will be replaced in frontend)
        divert_datetime = ""
        
        result_item = {
            "OrderId": order_id,
            "Location": location or "",
            "OlpnCount": len(unique_olpns),
            "SVIA": svia or "",
            "DivertDateTime": divert_datetime
        }
        print(f"[RESULT] Order: {order_id}, Location: {location}, OlpnCount: {len(unique_olpns)}, SVIA: {svia}, DivertDateTime: (will be set in frontend)")
        results.append(result_item)
    
    # Resolve DisplayLocation for order list (single location search call for all unique location IDs)
    location_ids = list({r.get("Location") for r in results if r.get("Location")})
    display_map = search_locations(headers, org, location_ids) if location_ids else {}
    for r in results:
        loc_id = r.get("Location")
        if loc_id:
            r["Location"] = display_map.get(loc_id, loc_id)
    
    print(f"[SEARCH_ORDERS_ENDPOINT] Returning {len(results)} results")
    
    # Add response info to API calls log
    for api_call in api_calls_log:
        if api_call["type"] == "order_search":
            api_call["response"] = {"orders_found": len(orders)}
        elif api_call["type"] == "olpn_search":
            api_call["response"] = {"olpns_found": len(olpns)}
    
    return jsonify({
        "success": True,
        "results": results,
        "api_calls": api_calls_log
    })

@app.route('/api/getOlpns', methods=['POST'])
def get_olpns_endpoint():
    """Fetch oLPNs for a single order (for Order Detail screen)"""
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    order_id = request.json.get('orderId', '').strip()
    
    if not org or not token or not order_id:
        return jsonify({"success": False, "error": "ORG, token, and orderId required"})
    
    headers = {"Authorization": f"Bearer {token}"}
    olpns = search_olpns([order_id], headers, org)
    # Only return oLPNs with Status < 9000 for Order Detail display
    olpns_filtered = [o for o in olpns if olpn_status_under_9000(o)]
    
    # Resolve DisplayLocation for Order Detail (single location search call)
    location_ids = []
    for o in olpns_filtered:
        loc = o.get("CurrentLocationId") or o.get("currentLocationId") or o.get("CurrentLocation")
        if loc and str(loc).strip():
            location_ids.append(str(loc).strip())
    location_ids = list(dict.fromkeys(location_ids))  # unique, preserve order
    display_map = search_locations(headers, org, location_ids) if location_ids else {}
    for o in olpns_filtered:
        loc = o.get("CurrentLocationId") or o.get("currentLocationId") or o.get("CurrentLocation")
        if loc:
            o["DisplayLocation"] = display_map.get(str(loc).strip(), loc)
    
    return jsonify({
        "success": True,
        "olpns": olpns_filtered
    })

@app.route('/api/getOlpnPk', methods=['POST'])
def get_olpn_pk():
    """Fetch PK for a single oLPN by order and OlpnId (no list refresh). Used to clear To LPN CombinedOlpns after Remove."""
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    order_id = request.json.get('orderId', '').strip()
    olpn_id = request.json.get('olpnId', '').strip()
    if not org or not token or not order_id or not olpn_id:
        return jsonify({"success": False, "error": "ORG, token, orderId, and olpnId required"})
    headers = {"Authorization": f"Bearer {token}"}
    olpns = search_olpns([order_id], headers, org)
    olpn_id_lower = olpn_id.lower()
    for o in olpns:
        oid = (o.get("OlpnId") or o.get("olpnId") or o.get("oLPNId") or "").__str__().strip().lower()
        if oid == olpn_id_lower:
            pk = o.get("PK") or o.get("Pk") or o.get("pk") or o.get("OlpnPk") or o.get("olpnPk")
            if pk is not None:
                return jsonify({"success": True, "pk": str(pk)})
            break
    return jsonify({"success": False, "error": "oLPN not found or missing PK"})

def split_combine_olpn(headers, org, from_olpn_id, to_olpn_id):
    """
    Call Manhattan Split Combine API to combine FromOlpnId into ToOlpnId (bundle).
    Must be called BEFORE updating Extended.CombinedOlpns; if this fails we do not update CombinedOlpns.
    After a successful combine, the FromOlpnId oLPN will have changed (status, items, qty), so
    CombinedOlpns payload must be built from pre-combine data (see frontend comments).
    """
    url = f"https://{API_HOST}/pickpack/api/pickpack/postpack/splitcombineolpn/olpn/splitCombine"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    payload = {
        "TransactionType": "SplitCombineOlpn",
        "FromOlpnId": from_olpn_id,
        "ToOlpnId": to_olpn_id,
        "SplitCombineOlpnCritieriaId": "Combine oLPN Criteria",
        "TransactionId": "Combine Olpn"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        print(f"[SPLIT_COMBINE_OLPN] Status: {r.status_code}, FromOlpnId={from_olpn_id}, ToOlpnId={to_olpn_id}")
        if not r.ok:
            print(f"[SPLIT_COMBINE_OLPN] Error: {r.text[:500]}")
            return False, r.text
        data = r.json() if r.text else {}
        if data.get("success") is False:
            return False, json.dumps(data)
        return True, None
    except Exception as e:
        print(f"[SPLIT_COMBINE_OLPN] Exception: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def split_olpn(headers, org, from_olpn_id, to_olpn_id, item_id, quantity):
    """
    Call Manhattan Split Combine API to split one item from bundle (FromOlpnId) to oLPN (ToOlpnId).
    Same URL as combine; payload uses Split oLPN Criteria, Split Olpn transaction, and ItemId/Quantity.
    ItemId and Quantity must come from CombinedOlpns Details (not the live ToOlpnId record).
    API allows only one item per request; call once per item for Remove.
    """
    url = f"https://{API_HOST}/pickpack/api/pickpack/postpack/splitcombineolpn/olpn/splitCombine"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    payload = {
        "TransactionType": "SplitCombineOlpn",
        "FromOlpnId": from_olpn_id,
        "ToOlpnId": to_olpn_id,
        "SplitCombineOlpnCritieriaId": "Split oLPN Criteria",
        "TransactionId": "Split Olpn",
        "ItemId": item_id,
        "Quantity": int(quantity) if quantity is not None else 0
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        print(f"[SPLIT_OLPN] Status: {r.status_code}, From={from_olpn_id}, To={to_olpn_id}, ItemId={item_id}, Qty={quantity}")
        if not r.ok:
            print(f"[SPLIT_OLPN] Error: {r.text[:500]}")
            return False, r.text
        data = r.json() if r.text else {}
        if data.get("success") is False:
            return False, json.dumps(data)
        return True, None
    except Exception as e:
        print(f"[SPLIT_OLPN] Exception: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)


def olpn_save(headers, org, payload):
    """Update oLPN via /pickpack/api/pickpack/olpn/save (e.g. Extended.CombinedOlpns)."""
    url = f"https://{API_HOST}/pickpack/api/pickpack/olpn/save"
    facility_id = f"{org.upper()}-DM1"
    headers = headers.copy()
    headers.update({
        "Content-Type": "application/json",
        "FacilityId": facility_id,
        "selectedOrganization": org.upper(),
        "selectedLocation": facility_id
    })
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        print(f"[OLPN_SAVE] Status: {r.status_code}, Payload: {json.dumps(payload, indent=2)}")
        if not r.ok:
            print(f"[OLPN_SAVE] Error: {r.text[:500]}")
            return None, r.text
        data = r.json()
        return data, None
    except Exception as e:
        print(f"[OLPN_SAVE] Exception: {e}")
        import traceback
        traceback.print_exc()
        return None, str(e)

@app.route('/api/splitCombineOlpn', methods=['POST'])
def api_split_combine_olpn():
    """
    Combine oLPN (FromOlpnId) into bundle (ToOlpnId) via Manhattan Split Combine API.
    Call this BEFORE updateOlpnExtended when adding an oLPN to a bundle.
    If this fails, do NOT update CombinedOlpns.
    """
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    from_olpn_id = request.json.get('fromOlpnId', '').strip()
    to_olpn_id = request.json.get('toOlpnId', '').strip()
    if not org or not token or not from_olpn_id or not to_olpn_id:
        return jsonify({"success": False, "error": "ORG, token, fromOlpnId, and toOlpnId required"})
    headers = {"Authorization": f"Bearer {token}"}
    ok, err = split_combine_olpn(headers, org, from_olpn_id, to_olpn_id)
    if not ok:
        return jsonify({"success": False, "error": err or "Split combine failed"})
    return jsonify({"success": True})


@app.route('/api/splitOlpn', methods=['POST'])
def api_split_olpn():
    """
    Split one item from bundle (fromOlpnId) to oLPN (toOlpnId). ItemId and Quantity from CombinedOlpns Details.
    Call once per item for Remove; update CombinedOlpns after each successful call.
    """
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    from_olpn_id = request.json.get('fromOlpnId', '').strip()
    to_olpn_id = request.json.get('toOlpnId', '').strip()
    item_id = request.json.get('itemId', '')
    quantity = request.json.get('quantity')
    if not org or not token or not from_olpn_id or not to_olpn_id:
        return jsonify({"success": False, "error": "ORG, token, fromOlpnId, and toOlpnId required"})
    if item_id is None or item_id == '':
        return jsonify({"success": False, "error": "itemId required"})
    headers = {"Authorization": f"Bearer {token}"}
    ok, err = split_olpn(headers, org, from_olpn_id, to_olpn_id, item_id, quantity)
    if not ok:
        return jsonify({"success": False, "error": err or "Split failed"})
    return jsonify({"success": True})


@app.route('/api/updateOlpnExtended', methods=['POST'])
def update_olpn_extended():
    """Update oLPN extended field (e.g. CombinedOlpns) via pickpack olpn/save."""
    org = request.json.get('org', '').strip()
    token = request.json.get('token', '').strip()
    olpn_id = request.json.get('olpnId', '').strip()
    pk_raw = request.json.get('pk') or request.json.get('PK')
    pk = str(pk_raw).strip() if pk_raw is not None else ''
    combined_olpns = request.json.get('combinedOlpns', '')
    
    if not org or not token or not olpn_id or not pk:
        return jsonify({"success": False, "error": "ORG, token, olpnId, and pk required"})
    
    # Payload: OlpnId, PK (API returns PK at top level), Extended.CombinedOlpns
    payload = {
        "OlpnId": olpn_id,
        "PK": pk,
        "Extended": {
            "CombinedOlpns": combined_olpns if combined_olpns is not None else ""
        }
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    data, err = olpn_save(headers, org, payload)
    
    if err:
        return jsonify({"success": False, "error": err})
    if data and data.get("success") is False:
        return jsonify({"success": False, "error": json.dumps(data)})
    return jsonify({"success": True, "data": data})


@app.route("/api/usage-track", methods=["POST"])
def usage_track():
    """Receive events from frontend and forward to usage ingest (Neon)."""
    data = request.json or {}
    event_name = data.get("event_name")
    metadata = data.get("metadata", {})
    payload = {
        **metadata,
        "event_name": event_name,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    forward_usage_event(payload)
    return jsonify({"success": True})


# === FALLBACK: Serve index.html for SPA (Critical for Vercel) ===
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if path.startswith('api/'):
        return "API route not found", 404
    # Don't serve index.html for JavaScript files that don't exist - return 404 instead
    if path.endswith('.js'):
        return jsonify({'error': 'File not found'}), 404
    try:
        return send_from_directory('..', 'index.html')
    except:
        return "File not found", 404

# === DEV SERVER ===
if __name__ == '__main__':
    app.run(port=5000, debug=True)
