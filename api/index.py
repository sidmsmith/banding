# api/index.py
from flask import Flask, request, jsonify, send_from_directory
import json, os
from datetime import datetime, timedelta
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

# Critical: Fail fast if secrets missing
if not PASSWORD or not CLIENT_SECRET:
    raise Exception("Missing MANHATTAN_PASSWORD or MANHATTAN_SECRET environment variables")

# === HELPERS ===
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
    payload = {
        "Query": f"OrderId in ('{order_ids_str}')",
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
    
    # Group oLPNs by OrderId
    olpns_by_order = {}
    for olpn in olpns:
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
    
    return jsonify({
        "success": True,
        "olpns": olpns
    })

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
