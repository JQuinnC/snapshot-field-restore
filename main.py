import json
import requests
from flask import Flask, request
import logging
import time
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def unescape_json_string(s):
    """Recursively unescape a JSON string that has been escaped multiple times."""
    prev = None
    current = s
    while prev != current:
        prev = current
        try:
            current = json.loads(current)
            if isinstance(current, str):
                continue
            else:
                return current
        except:
            return prev
    return current

def update_custom_field(location_id, field_id, field_name, options, access_token, version):
    """Update a custom field with new options, handling rate limits."""
    api_url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields/{field_id}"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'Version': version
    }
    payload = {
        "name": field_name,
        "options": options
    }

    while True:
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            
            # Check rate limit
            remaining = int(response.headers.get('x-ratelimit-remaining', '1000'))
            logging.info(f"Rate limit remaining: {remaining}")
            
            if remaining <= 50:
                logging.info("Rate limit low, waiting 10 seconds")
                time.sleep(10)
            
            if response.status_code == 429:  # Rate limit exceeded
                logging.warning("Rate limit exceeded, waiting 10 seconds")
                time.sleep(10)
                continue
                
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error updating custom field {field_id}: {e}")
            if response.status_code == 429:  # Rate limit exceeded
                time.sleep(10)
                continue
            return False

@app.route("/", methods=["POST"])
def filter_custom_fields():
    """Filters custom fields from GoHighLevel API based on prefix and field names."""
    try:
        raw_data = request.get_data()
        logging.info(f"Raw request data: {raw_data.decode('utf-8')}")
        
        try:
            request_data = request.get_json()
            logging.info(f"Outer JSON structure: {json.dumps(request_data, indent=2)}")
            
            if isinstance(request_data, list) and len(request_data) > 0:
                inner_json_str = request_data[0].get('json', '{}')
                request_json = json.loads(inner_json_str)
                logging.info(f"Inner JSON structure: {json.dumps(request_json, indent=2)}")
            else:
                request_json = request_data
            
        except Exception as e:
            logging.error(f"Error parsing JSON: {e}")
            return ("Invalid request: JSON parsing error", 400)

        if not request_json:
            logging.error("Request body is empty")
            return ("Invalid request: Empty body", 400)

        # Handle restore_fields case
        if 'restore_fields' in request_json:
            try:
                restore_fields = unescape_json_string(request_json['restore_fields'])
                logging.info(f"Parsed restore_fields: {json.dumps(restore_fields, indent=2)}")
                
                # Extract necessary information for updates
                location_id = request_json.get('locationId')
                access_token = request_json.get('access_token')
                version = request_json.get('version')
                
                if not all([location_id, access_token, version]):
                    return ("Missing required parameters for update", 400)
                
                # Process each field in restore_fields
                update_results = []
                for field in restore_fields.get('Restore', []):
                    field_id = field.get('id')
                    field_name = field.get('name')
                    options = field.get('picklistOptions', [])
                    
                    logging.info(f"Updating field {field_name} with options {options}")
                    
                    success = update_custom_field(
                        location_id=location_id,
                        field_id=field_id,
                        field_name=field_name,
                        options=options,
                        access_token=access_token,
                        version=version
                    )
                    
                    update_results.append({
                        "field_name": field_name,
                        "success": success
                    })
                
                return (json.dumps({"updates": update_results}), 200)
                
            except Exception as e:
                logging.error(f"Error processing restore_fields: {e}")
                logging.exception("Full exception details:")
                return ("Error processing restore_fields", 400)

        # ... rest of your existing code for the initial field gathering ...
        
        response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        
        return (json.dumps(response_data), 200, response_headers)

    except Exception as e:
        logging.exception("An unexpected error occurred")
        return (f"An unexpected error occurred: {e}", 500)
