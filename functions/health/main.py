import os
import json
import functions_framework

@functions_framework.http
def health_check(request):
    """HTTP Cloud Function for Health Check."""
    # Set CORS headers for the preflight request
    if request.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
        return ('', 204, headers)

    # Set CORS headers for the main request
    headers = {
        'Access-Control-Allow-Origin': '*'
    }

    response_payload = {
        "status": "healthy",
        "service": "ElectIQ-CloudFunction",
        "version": "1.0",
        "region": os.environ.get("FUNCTION_REGION", "unknown")
    }

    return (json.dumps(response_payload), 200, headers)
