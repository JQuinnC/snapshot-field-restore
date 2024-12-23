import json
import requests
from flask import Flask, request
import logging
import re

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/", methods=["POST"])
def filter_custom_fields():
    """Filters custom fields from GoHighLevel API based on prefix and field names."""
    try:
        # Log the raw request data
        raw_data = request.get_data()
        logging.info(f"Raw request data: {raw_data.decode('utf-8')}")
        
        try:
            # Parse the outer JSON structure
            request_data = request.get_json()
            logging.info(f"Outer JSON structure: {json.dumps(request_data, indent=2)}")
            
            # Extract and parse the inner JSON string
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

        # Extract restore_fields if it exists and parse it
        if 'restore_fields' in request_json:
            try:
                restore_fields = json.loads(request_json['restore_fields'].replace('\\"', '"'))
                logging.info(f"Parsed restore_fields: {json.dumps(restore_fields, indent=2)}")
                return (json.dumps(restore_fields), 200)
            except Exception as e:
                logging.error(f"Error parsing restore_fields: {e}")
                return ("Error parsing restore_fields", 400)

        required_keys = ('prefix', 'field_names', 'locationId', 'access_token', 'version')
        missing_keys = [key for key in required_keys if key not in request_json]
        if missing_keys:
            logging.error(f"Missing required keys: {missing_keys}")
            return (f"Invalid request: Missing required parameters: {', '.join(missing_keys)}", 400)

        prefix = request_json['prefix']
        field_names = [name.lower().replace('\u00a0', ' ').strip() for name in request_json['field_names']]
        location_id = request_json['locationId']
        access_token = request_json['access_token']
        version = request_json['version']

        logging.info(f"Processing request for prefix: {prefix}")
        logging.info(f"Looking for field names (normalized): {field_names}")

        api_url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields"
        api_headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Version': version
        }

        response = requests.get(api_url, headers=api_headers)
        response.raise_for_status()

        data = response.json()
        custom_fields = data.get('customFields', [])
        logging.info(f"Retrieved {len(custom_fields)} custom fields from API")

        filtered_fields = []

        for field in custom_fields:
            field_name = field.get('name', '')
            if not field_name:
                continue

            logging.info(f"\nChecking field: {field_name}")

            if not (field_name.startswith(f"{prefix} - ") or 
                   any(field_name.startswith(f"{prefix}-A{i} - ") for i in range(10))):
                logging.info(f"Skipping {field_name} - prefix doesn't match")
                continue

            try:
                base_field_name = field_name.split(" - ", 1)[1]
                base_field_name = base_field_name.replace('\u00a0', ' ').strip()
                logging.info(f"Base field name (normalized): {base_field_name}")
                
                if base_field_name.lower() in field_names:
                    logging.info(f"Found matching field name: {base_field_name}")
                    
                    if 'picklistOptions' in field and isinstance(field['picklistOptions'], list):
                        filtered_fields.append({
                            "id": field.get('id', ''),
                            "name": field_name,
                            "picklistOptions": field['picklistOptions']
                        })
                        logging.info(f"Added to results with options: {field['picklistOptions']}")
                    else:
                        logging.info(f"Field {field_name} has no valid picklistOptions")
                else:
                    logging.info(f"Base field name {base_field_name.lower()} not in target list {field_names}")
            except Exception as e:
                logging.error(f"Error processing field {field_name}: {e}")
                logging.exception("Full exception details:")

        response_data = {"Restore": filtered_fields}

        response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        logging.info(f"Final filtered fields count: {len(filtered_fields)}")
        logging.info(f"Final filtered fields: {json.dumps(filtered_fields, indent=2)}")
        
        return (json.dumps(response_data), 200, response_headers)

    except requests.exceptions.RequestException as e:
        logging.error(f"API request error: {e}")
        return (f"Error fetching custom fields: {e}", 500)

    except Exception as e:
        logging.exception("An unexpected error occurred")
        return (f"An unexpected error occurred: {e}", 500)
