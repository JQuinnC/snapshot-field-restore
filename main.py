import json
import requests
from flask import Flask, request
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def check_rate_limit(response_headers):
    """Check rate limit and determine if we need to pause."""
    try:
        remaining = int(response_headers.get('x-ratelimit-remaining', 0))
        logging.info(f"Rate limit remaining: {remaining}")
        
        if remaining < 50:
            logging.info("Rate limit below 50, pausing for 5 seconds")
            time.sleep(5)
            return True
        return False
    except (ValueError, TypeError) as e:
        logging.error(f"Error parsing rate limit header: {e}")
        return False

def handle_api_call(api_url, headers, payload, field_name, max_retries=3):
    """Make API call with rate limit handling and retries."""
    for attempt in range(max_retries):
        try:
            response = requests.put(api_url, headers=headers, json=payload)
            
            # Check rate limit headers
            check_rate_limit(response.headers)
            
            # If successful, return the response
            if response.status_code == 200:
                return response
            
            # Handle rate limit exceeded
            if response.status_code == 429:
                logging.warning("Rate limit exceeded, waiting 10 seconds")
                time.sleep(10)
                continue
                
            # If other error, raise it
            response.raise_for_status()
            
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:  # Last attempt
                raise
            
            if hasattr(e.response, 'status_code') and e.response.status_code == 429:
                logging.warning("Rate limit exceeded, waiting 10 seconds")
                time.sleep(10)
                continue
                
            logging.error(f"Error updating field {field_name}, attempt {attempt + 1}: {e}")
            time.sleep(2)  # Brief pause before retry
    
    raise Exception(f"Failed to update field after {max_retries} attempts")

@app.route("/", methods=["POST"])
def restore_custom_fields():
    """Restores custom field options in GoHighLevel."""
    try:
        request_json = request.get_json()
        logging.info("Received request")

        required_keys = ('version', 'locationId', 'access_token', 'restore_fields')
        if not request_json or not all(key in request_json for key in required_keys):
            return ("Invalid request: Missing required parameters", 400)

        # Extract basic parameters
        location_id = request_json['locationId']
        access_token = request_json['access_token']
        version = request_json['version']

        # Parse the restore_fields string
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

            api_url = f"https://services.leadconnectorhq.com/locations/{location_id}/customFields/{field_id}"
            payload = {
                "name": field_name,
                "options": options
            }

            try:
                logging.info(f"Updating field {field_name} with ID {field_id}")
                response = handle_api_call(api_url, api_headers, payload, field_name)
                
                results.append({
                    "id": field_id,
                    "name": field_name,
                    "status": "success",
                    "statusCode": response.status_code,
                    "rateLimit": response.headers.get('x-ratelimit-remaining', 'unknown')
                })
                logging.info(f"Successfully updated field {field_name}")

            except Exception as e:
                error_message = str(e)
                error_detail = "No detail available"
                
                if isinstance(e, requests.exceptions.RequestException) and e.response:
                    try:
                        error_detail = e.response.json()
                    except:
                        error_detail = e.response.text

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
