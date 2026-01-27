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
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        if r.ok:
            response_data = r.json()
            # Extract orders from response
            orders = response_data.get("data", [])
            if isinstance(orders, list):
                return orders
            return []
        return []
    except Exception as e:
        print(f"[SEARCH_ORDERS] Error: {str(e)}")
        return []

def search_olpns(order_ids, headers, org):
    """Search for oLPNs for given order IDs"""
    if not order_ids:
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
    
    # Format order IDs for query (comma-separated, single-quoted)
    order_ids_str = "', '".join(order_ids)
    payload = {
        "Query": f"OrderId in '{order_ids_str}'",
        "Size": 1000,
        "Page": 0
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=60, verify=False)
        if r.ok:
            response_data = r.json()
            # Extract oLPNs from response
            olpns = response_data.get("data", [])
            if isinstance(olpns, list):
                return olpns
            return []
        return []
    except Exception as e:
        print(f"[SEARCH_OLPNS] Error: {str(e)}")
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
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 1: Search for orders with Status=7200
    orders = search_orders(headers, org)
    
    if not orders:
        return jsonify({
            "success": True,
            "results": []
        })
    
    # Extract OrderIds
    order_ids = [order.get("OrderId") for order in orders if order.get("OrderId")]
    
    if not order_ids:
        return jsonify({
            "success": True,
            "results": []
        })
    
    # Step 2: Search for oLPNs for these orders
    olpns = search_olpns(order_ids, headers, org)
    
    # Step 3: Process and aggregate data
    # Group oLPNs by OrderId
    olpns_by_order = {}
    for olpn in olpns:
        order_id = olpn.get("OrderId")
        if order_id:
            if order_id not in olpns_by_order:
                olpns_by_order[order_id] = []
            olpns_by_order[order_id].append(olpn)
    
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
            olpn_id = olpn.get("oLPNId") or olpn.get("OlpnId")
            if olpn_id:
                unique_olpns.add(olpn_id)
        
        # Get Location from first oLPN where CurrentLocationId is not null
        location = None
        for olpn in order_olpns:
            location = olpn.get("CurrentLocationId") or olpn.get("currentLocationId")
            if location:
                break
        
        # Get SVIA (ShipViaId) from order or first oLPN
        svia = order.get("ShipViaId") or order.get("shipViaId")
        if not svia and order_olpns:
            svia = order_olpns[0].get("ShipViaId") or order_olpns[0].get("shipViaId")
        
        # Generate random divert date/time
        divert_datetime = generate_random_divert_time()
        
        results.append({
            "OrderId": order_id,
            "Location": location or "",
            "OlpnCount": len(unique_olpns),
            "SVIA": svia or "",
            "DivertDateTime": divert_datetime
        })
    
    return jsonify({
        "success": True,
        "results": results
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
