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

    logging.info(f"Making PUT request to {api_url}")
    logging.info(f"Headers: {headers}")
    logging.info(f"Payload: {payload}")

    while True:
        try:
            response = requests.put(api_url, headers=headers, json=payload)
            
            # Log response details
            logging.info(f"Response status: {response.status_code}")
            logging.info(f"Response headers: {dict(response.headers)}")
            logging.info(f"Response body: {response.text}")
            
            remaining = int(response.headers.get('x-ratelimit-remaining', '1000'))
            logging.info(f"Rate limit remaining: {remaining}")
            
            if remaining <= 50:
                logging.info("Rate limit low, waiting 10 seconds")
                time.sleep(10)
            
            if response.status_code == 429:
                logging.warning("Rate limit exceeded, waiting 10 seconds")
                time.sleep(10)
                continue
                
            response.raise_for_status()
            # Return both success status and response details
            return {
                "success": True,
                "status_code": response.status_code,
                "response_body": response.text,
                "api_url": api_url,
                "sent_payload": payload
            }
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Error updating custom field {field_id}: {e}")
            if hasattr(response, 'status_code') and response.status_code == 429:
                time.sleep(10)
                continue
            return {
                "success": False,
                "error": str(e),
                "status_code": getattr(response, 'status_code', None),
                "response_body": getattr(response, 'text', None),
                "api_url": api_url,
                "sent_payload": payload
            }

@app.route("/", methods=["POST"])
def filter_custom_fields():
    """Process and update custom fields."""
    try:
        # Log the raw request data
        raw_data = request.get_data()
        logging.info(f"Raw request data: {raw_data.decode('utf-8')}")
        
        try:
            # Parse the outer JSON structure (array)
            request_data = request.get_json()
            if isinstance(request_data, list):
                request_json = request_data[0]  # Get the first object from the array
            else:
                request_json = request_data
                
            logging.info(f"Processed request JSON: {json.dumps(request_json, indent=2)}")
            
        except Exception as e:
            logging.error(f"Error parsing JSON: {e}")
            return ("Invalid request: JSON parsing error", 400)

        if not request_json:
            logging.error("Request body is empty")
            return ("Invalid request: Empty body", 400)

        # Extract required fields
        location_id = request_json.get('locationId')
        access_token = request_json.get('access_token')
        version = request_json.get('version')
        restore_fields_str = request_json.get('restore_fields')

        if not all([location_id, access_token, version, restore_fields_str]):
            missing = [k for k, v in {
                'locationId': location_id,
                'access_token': access_token,
                'version': version,
                'restore_fields': restore_fields_str
            }.items() if not v]
            return (f"Missing required parameters: {', '.join(missing)}", 400)

        try:
            # Parse restore_fields
            restore_fields = unescape_json_string(restore_fields_str)
            logging.info(f"Parsed restore_fields: {json.dumps(restore_fields, indent=2)}")
            
            # Process each field in restore_fields
            update_results = []
            for field in restore_fields.get('fields', []):
                field_id = field.get('fieldId')
                field_name = field.get('fieldName')
                options = field.get('options', [])
                
                logging.info(f"Processing field update:")
                logging.info(f"Field ID: {field_id}")
                logging.info(f"Field Name: {field_name}")
                logging.info(f"Options: {options}")
                
                result = update_custom_field(
                    location_id=location_id,
                    field_id=field_id,
                    field_name=field_name,
                    options=options,
                    access_token=access_token,
                    version=version
                )
                
                update_results.append({
                    "field_name": field_name,
                    "field_id": field_id,
                    "result": result
                })
            
            response_data = {"updates": update_results}
            
            response_headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }
            
            return (json.dumps(response_data), 200, response_headers)
            
        except Exception as e:
            logging.error(f"Error processing restore_fields: {e}")
            logging.exception("Full exception details:")
            return ("Error processing restore_fields", 400)

    except Exception as e:
        logging.exception("An unexpected error occurred")
        return (f"An unexpected error occurred: {e}", 500)
