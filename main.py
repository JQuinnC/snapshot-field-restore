import json
import requests
from flask import Flask, request
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/", methods=["POST"])
def restore_custom_fields():
    """Restores custom field options in GoHighLevel."""
    try:
        request_json = request.get_json()
        logging.info(f"Received request")

        required_keys = ('version', 'locationId', 'access_token', 'restore_fields')
        if not request_json or not all(key in request_json for key in required_keys):
            return ("Invalid request: Missing required parameters", 400)

        # Extract basic parameters
        location_id = request_json['locationId']
        access_token = request_json['access_token']
        version = request_json['version']

        # Parse the restore_fields string (it's a JSON string within JSON)
        try:
            restore_data = json.loads(request_json['restore_fields'])
            fields_to_restore = restore_data.get('Restore', [])
            logging.info(f"Found {len(fields_to_restore)} fields to restore")
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing restore_fields: {e}")
            return ("Invalid restore_fields format", 400)

        # Setup API headers
        api_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Version': version
        }

        results = []
        for field in fields_to_restore:
            field_id = field.get('id')
            field_name = field.get('name')
            options = field.get('picklistOptions', [])

            if not all([field_id, field_name, options]):
                logging.warning(f"Skipping field due to missing data: {field}")
                continue

            # Construct the API URL for this field
            api_url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields/{field_id}"

            # Prepare the payload
            payload = {
                "name": field_name,
                "options": options
            }

            try:
                logging.info(f"Updating field {field_name} with ID {field_id}")
                response = requests.put(api_url, headers=api_headers, json=payload)
                response.raise_for_status()
                
                results.append({
                    "id": field_id,
                    "name": field_name,
                    "status": "success",
                    "statusCode": response.status_code
                })
                logging.info(f"Successfully updated field {field_name}")

            except requests.exceptions.RequestException as e:
                error_message = str(e)
                try:
                    error_detail = e.response.json() if e.response else "No detail available"
                except:
                    error_detail = "Could not parse error response"

                results.append({
                    "id": field_id,
                    "name": field_name,
                    "status": "error",
                    "error": error_message,
                    "errorDetail": error_detail
                })
                logging.error(f"Error updating field {field_name}: {error_message}")

        response_data = {
            "results": results,
            "total_processed": len(results),
            "successful": len([r for r in results if r.get("status") == "success"]),
            "failed": len([r for r in results if r.get("status") == "error"])
        }

        response_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }

        logging.info(f"Completed processing with results: {json.dumps(response_data, indent=2)}")
        return (json.dumps(response_data), 200, response_headers)

    except Exception as e:
        logging.exception("An unexpected error occurred")
        return (f"An unexpected error occurred: {e}", 500)
