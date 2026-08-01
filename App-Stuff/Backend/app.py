import os
import time
import subprocess
import html
import re
import json
import requests
import boto3
import datetime
from functools import wraps
from flask import Flask, request, jsonify
from pydantic import ValidationError
import jwt
from dotenv import load_dotenv

# Import existing logic from your modules
from Src.logger import setup_loggers
from Src.defs import load_os_data, generate_reservation_model, save_configuration

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# --- FIX 1: Explicitly load SECRET_KEY into app.config ---
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

f_logger, c_logger = setup_loggers()

# Fetch configuration from environment variables
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
# Auth service base URL (provided via the AUTH_URL env var in the deployment).
AUTH_SERVICE_URL = os.getenv('AUTH_URL')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=AWS_REGION)


# --- Authentication Middleware (Stateless) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'error': 'Token is missing!'}), 401
        
        try:
            # Decode using the SECRET_KEY loaded from .env
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_id = data['user_id']
        except Exception as e:
            f_logger.error(f"JWT Verification failed: {e}")
            return jsonify({'error': 'Token is invalid or expired!'}), 401
            
        return f(current_user_id, *args, **kwargs)
    return decorated


# --- S3 Upload Helper ---
def upload_to_s3(file_content, file_name, user_id):
    """Uploads generated file content directly to the S3 bucket."""
    s3_key = f"users/{user_id}/{file_name}"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content.encode('utf-8')
        )
        f_logger.info(f"Successfully uploaded {file_name} to S3 at {s3_key}")
        return s3_key
    except Exception as e:
        f_logger.error(f"S3 Upload Error for {file_name}: {e}")
        return None


# --- Metadata Sync: notify the Auth service directly over HTTP ---
def save_metadata_to_auth(metadata_payload):
    """
    Sends provisioning metadata to the Auth service via a direct HTTP call so it
    can be persisted to the database. Replaces the previous SQS-based async flow.
    """
    if not AUTH_SERVICE_URL:
        f_logger.warning("AUTH_URL is not set. Cannot sync metadata to the Auth service.")
        return

    try:
        response = requests.post(
            f"{AUTH_SERVICE_URL}/api/internal/save_metadata",
            json=metadata_payload,
            headers={"X-Internal-Secret": app.config['SECRET_KEY']},
            timeout=10
        )
        if response.status_code == 200:
            f_logger.info(f"Action: SAVE_METADATA_HTTP | Status: SUCCESS | File: {metadata_payload.get('file_name')}")
        else:
            f_logger.error(f"Action: SAVE_METADATA_HTTP | Status: FAILED | Code: {response.status_code} | Body: {response.text}")
    except Exception as e:
        f_logger.error(f"Action: SAVE_METADATA_HTTP | Status: FAILED | Error: {e}")


# --- Provisioning Logic ---
def is_malicious_payload(input_string):
    malicious_pattern = re.compile(r'(<|>|<script>|javascript:|onload=|eval\()', re.IGNORECASE)
    return bool(malicious_pattern.search(str(input_string)))

def sanitize_and_validate_payload(data):
    errors = []
    clean_data = {}

    allowed_keys = {'count', 'baseName', 'osKey', 'typeChoice', 'installScript', 'infraType'}
    incoming_keys = set(data.keys())
    extra_keys = incoming_keys - allowed_keys
    
    if extra_keys:
        f_logger.critical(f"SECURITY ALERT: Unexpected fields in payload: {', '.join(extra_keys)}. Raw payload: {data}")
        errors.append("Security Error: Payload contains unauthorized or unrecognized fields.")
        return None, errors 

    raw_count = data.get('count')
    if raw_count is None:
        errors.append("Validation Error: 'count' is missing.")
    else:
        try:
            count = int(raw_count)
            if 1 <= count <= 10:
                clean_data['count'] = count
            else:
                errors.append("Validation Error: 'count' must be between 1 and 10.")
        except (ValueError, TypeError):
            errors.append("Validation Error: 'count' must be a valid number.")

    allowed_os = ['ubuntu', 'centos']
    raw_os = data.get('osKey')
    if raw_os is None:
        errors.append("Validation Error: 'osKey' is missing.")
    else:
        raw_os_str = str(raw_os).strip()
        if is_malicious_payload(raw_os_str):
            errors.append("Security Error: Invalid characters in OS selection.")
        elif raw_os_str in allowed_os:
            clean_data['osKey'] = raw_os_str
        else:
            errors.append(f"Validation Error: 'osKey' must be strictly one of {allowed_os}.")

    allowed_types = ['1', '2']
    raw_type = data.get('typeChoice')
    if raw_type is None:
        errors.append("Validation Error: 'typeChoice' is missing.")
    else:
        raw_type_str = str(raw_type).strip()
        if is_malicious_payload(raw_type_str):
            errors.append("Security Error: Invalid characters in Type selection.")
        elif raw_type_str in allowed_types:
            clean_data['typeChoice'] = raw_type_str
        else:
            errors.append(f"Validation Error: 'typeChoice' must be strictly one of {allowed_types}.")

    allowed_scripts = ['none', 'nginx']
    raw_script = data.get('installScript')
    if raw_script is None:
        clean_data['installScript'] = 'none' 
    else:
        raw_script_str = str(raw_script).strip()
        if not raw_script_str:
            clean_data['installScript'] = 'none'
        elif is_malicious_payload(raw_script_str):
            errors.append("Security Error: Invalid characters in Script selection.")
        elif raw_script_str in allowed_scripts:
            clean_data['installScript'] = raw_script_str
        else:
            errors.append(f"Validation Error: 'installScript' must be strictly one of {allowed_scripts}.")

    raw_base_name = data.get('baseName')
    if raw_base_name is None:
        errors.append("Validation Error: 'baseName' is missing.")
    else:
        raw_base_name_str = str(raw_base_name).strip()
        if is_malicious_payload(raw_base_name_str):
            errors.append("Security Error: Invalid characters in Base Name.")
        elif not raw_base_name_str:
            errors.append("Validation Error: Base Name is required.")
        else:
            clean_data['baseName'] = html.escape(raw_base_name_str)

    allowed_infra = ['json', 'terraform']
    raw_infra = data.get('infraType')
    
    if raw_infra is None:
        clean_data['infraType'] = 'json'
    else:
        raw_infra_str = str(raw_infra).strip()
        if is_malicious_payload(raw_infra_str):
            errors.append("Security Error: Invalid characters in Infrastructure Type.")
        elif raw_infra_str in allowed_infra:
            clean_data['infraType'] = raw_infra_str
        else:
            errors.append(f"Validation Error: 'infraType' must be strictly one of {allowed_infra}.")

    return clean_data, errors

def run_bash_installation(os_key: str) -> bool:
    script_path = os.path.join("./Scripts/", f"{os_key}_install.sh")
    if not os.path.exists(script_path):
        f_logger.error(f"Script not found: {script_path}")
        return False

    try:
        process = subprocess.Popen(
            ["bash", script_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1 
        )
        for line in process.stdout:
            clean_line = line.strip()
            if clean_line:
                f_logger.info(f"[Bash]: {clean_line}")
        process.wait()
        return process.returncode == 0
    except Exception as e:
        f_logger.critical(f"Critical System Error running bash script: {e}")
        return False
    
@app.route('/health', methods=['GET'])
def health_check():
    return {"status": "ok"}, 200

@app.route('/api/provision', methods=['POST'])
@token_required
def provision(current_user_id):
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    raw_data = request.get_json()
    clean_data, validation_errors = sanitize_and_validate_payload(raw_data)
    
    if validation_errors:
        return jsonify({"error": "Payload validation failed", "details": validation_errors}), 400

    count = clean_data.get('count')
    base_name = clean_data.get('baseName')
    os_key = clean_data.get('osKey')
    type_choice = clean_data.get('typeChoice')
    install_script = clean_data.get('installScript')
    infra_type = clean_data.get('infraType')

    os_data = load_os_data(f_logger, c_logger)
    if not os_data:
        return jsonify({"error": "Failed to load OS data"}), 500

    try:
        final_model = generate_reservation_model(count, base_name, os_key, type_choice, os_data)
    except ValidationError as e:
        return jsonify({"error": "Data validation failed at model generation"}), 400

    response_payload = None
    save_success = False

    if infra_type == 'terraform':
        from Src.tf_generator import generate_tf_file
        save_success, tf_content = generate_tf_file(final_model, f_logger, count, base_name, os_key)
        if save_success:
            response_payload = tf_content 
    else:
        try:
            save_configuration(final_model, f_logger, c_logger, count)
            save_success = True
            response_payload = final_model.model_dump() 
        except Exception as e:
            save_success = False

    if not save_success:
         return jsonify({"error": "Failed to generate infrastructure configuration file"}), 500

    f_logger.info(f"User ID {current_user_id} triggered provisioning for {count} instances of {base_name}.")

    # --- SAVE DIRECTLY TO S3 ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = 'tf' if infra_type == 'terraform' else 'json'
    file_name = f"{base_name}_{timestamp}.{extension}"
    
    content_to_save = response_payload if isinstance(response_payload, str) else json.dumps(response_payload, indent=2)
    
    s3_key = upload_to_s3(content_to_save, file_name, current_user_id)
    
    if not s3_key:
        return jsonify({"error": "Failed to store generated file in S3"}), 500

    # --- Notify the Auth service directly (synchronous HTTP) ---
    metadata_payload = {
        "user_id": current_user_id,
        "file_name": file_name,
        "file_type": infra_type,
        "s3_key": s3_key
    }

    save_metadata_to_auth(metadata_payload)
    f_logger.info(f"Metadata sync request sent to Auth service for file {file_name}")

    if install_script != 'none':
        deployment_success = run_bash_installation(os_key)
        if not deployment_success:
            return jsonify({"error": "Deployment failed. Check app.log"}), 500
    
    return jsonify({
        "message": "Success", 
        "config": response_payload 
    }), 200


@app.route('/api/log_error', methods=['POST'])
def log_frontend_error():
    error_data = request.get_json()
    f_logger.error(f"[Frontend Validation Error]: {error_data}")
    return jsonify({"status": "logged"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)