import os
import datetime
from functools import wraps
from flask import Flask, request, jsonify
import jwt
import boto3
from botocore.exceptions import ClientError
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv()

# Import DB, Models, and Custom Logger
from db import db, User, DeploymentHistory
from logger import setup_logger

app = Flask(__name__)

# Initialize the custom logger
auth_logger = setup_logger()

# ==========================================
# Configuration Variables (Loaded from .env)
# ==========================================
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

db.init_app(app)

# Initialize AWS Clients
s3_client = boto3.client('s3', region_name=AWS_REGION)
sns_client = boto3.client('sns', region_name=AWS_REGION)
cloudwatch_client = boto3.client('cloudwatch', region_name=AWS_REGION)

# ==========================================
# Helper Functions
# ==========================================
def send_sns_alert(subject, message, severity="INFO"):
    """
    Sends an email alert via AWS SNS.
    Severity can be: INFO, WARNING, or CRITICAL.
    """
    try:
        prefix = "APP ALERT" if severity != "CRITICAL" else "CRITICAL SYSTEM ALERT"
        body = f"Severity: {severity}\nTime (UTC): {datetime.datetime.now(datetime.timezone.utc)}\n\nDetails:\n{message}"
        
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"{prefix}: {subject}",
            Message=body
        )
    except Exception as e:
        auth_logger.error(f"Action: SEND_SNS_ALERT | Status: FAILED | Error: {e}")


# ==========================================
# Startup Health Checks
# ==========================================
@app.route('/health', methods=['GET'])
def health_check():
    return {"status": "ok"}, 200

try:
    sns_client.get_topic_attributes(TopicArn=SNS_TOPIC_ARN)
    auth_logger.info(f"System Startup | Status: SUCCESS | Connected to AWS SNS. Topic Verified: {SNS_TOPIC_ARN}")
except Exception as e:
    auth_logger.warning(f"System Startup | Status: WARNING | Could not verify SNS Topic. Alerts will NOT be sent! Error: {e}")

with app.app_context():
    try:
        db.create_all()
        auth_logger.info("System Startup | Status: SUCCESS | Connected to RDS and verified database tables.")
    except OperationalError as e:
        error_msg = f"Could not connect to RDS. Details: {e}"
        auth_logger.critical(f"System Startup | Status: CRITICAL | {error_msg}")
        send_sns_alert("RDS Connection Failure", error_msg, "CRITICAL")


# --- Authentication Middleware ---
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
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found!'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid or expired!'}), 401
            
        return f(current_user, *args, **kwargs)
    return decorated


# ==========================================
# Internal Microservice Routes
# ==========================================
# Backend calls this endpoint directly (synchronous HTTP) to persist
# provisioning metadata to the database.
@app.route('/api/internal/save_metadata', methods=['POST'])
def save_metadata():
    data = request.get_json()
    secret = request.headers.get('X-Internal-Secret')
    
    if secret != app.config['SECRET_KEY']:
        auth_logger.warning("Action: INTERNAL_SYNC | Status: FAILED | Reason: Unauthorized microservice access attempt.")
        return jsonify({'error': 'Unauthorized'}), 401

    user_id = data.get('user_id')
    file_name = data.get('file_name')
    file_type = data.get('file_type')
    s3_key = data.get('s3_key')

    if not all([user_id, file_name, file_type, s3_key]):
        return jsonify({'error': 'Missing required metadata fields'}), 400

    try:
        new_deployment = DeploymentHistory(
            user_id=user_id,
            file_name=file_name,
            file_type=file_type,
            s3_key=s3_key
        )
        db.session.add(new_deployment)
        db.session.commit()
        
        auth_logger.info(f"Action: SAVE_METADATA_HTTP | Status: SUCCESS | User ID: {user_id} | File: {file_name}")
        return jsonify({'message': 'Metadata saved successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"User ID: {user_id} | Error: {e}"
        auth_logger.critical(f"Action: SAVE_METADATA_HTTP | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Save Error (Metadata)", error_msg, "CRITICAL")
        return jsonify({'error': 'Database error'}), 500


# ==========================================
# Public API Routes
# ==========================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    
    required_fields = ['username', 'password', 're_password', 'email', 'fullName']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400
            
    if data['password'] != data['re_password']:
        return jsonify({'error': 'Passwords do not match'}), 400
        
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400

    try:
        new_user = User(username=data['username'], email=data['email'], full_name=data['fullName'])
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()
        
        auth_logger.info(f"Action: REGISTER | Status: SUCCESS | User: {new_user.username}")
        
        # SNS Trigger (Email Alert)
        send_sns_alert("New User Registration", f"Username: {new_user.username}\nEmail: {new_user.email}\nFull Name: {new_user.full_name}", "INFO")
        
        return jsonify({'message': 'User registered successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Attempted Username: {data.get('username')} | Error: {e}"
        auth_logger.critical(f"Action: REGISTER | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Error (Registration)", error_msg, "CRITICAL")
        return jsonify({'error': 'Database error during registration'}), 500


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    
    if not data or not username or not data.get('password'):
        return jsonify({'error': 'Missing credentials'}), 400
        
    try:
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(data['password']):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            
            auth_logger.info(f"Action: LOGIN | Status: SUCCESS | User: {user.username}")
            return jsonify({
                'message': 'Login successful',
                'token': token,
                'user': {'username': user.username, 'fullName': user.full_name, 'email': user.email}
            }), 200
            
        auth_logger.warning(f"Action: LOGIN | Status: WARNING | Attempted Username: {username} | Reason: Invalid password or user not found.")
        send_sns_alert("Failed Login Attempt", f"Someone attempted to log in with the username: '{username}' but provided invalid credentials.", "WARNING")
        return jsonify({'error': 'Invalid username or password'}), 401
        
    except Exception as e:
        error_msg = f"Attempted Username: {username} | Error: {e}"
        auth_logger.critical(f"Action: LOGIN | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Error (Login)", error_msg, "CRITICAL")
        return jsonify({'error': 'Database integration error during login'}), 500


@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_user):
    auth_logger.info(f"Action: LOGOUT | Status: SUCCESS | User: {current_user.username}")
    return jsonify({'message': 'Logout logged successfully'}), 200


@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    try:
        deployments = DeploymentHistory.query.filter_by(user_id=current_user.id).all()
        valid_deployments = []
        db_changed = False

        for d in deployments:
            try:
                s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=d.s3_key)
                valid_deployments.append(d)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404' or error_code == '403':
                    auth_logger.info(f"Auto-Sync: File {d.file_name} not found in S3. Removing from DB.")
                    db.session.delete(d)
                    db_changed = True
                else:
                    auth_logger.warning(f"S3 Head Object Error for {d.s3_key}: {e}")
                    valid_deployments.append(d)

        if db_changed:
            db.session.commit()

        valid_deployments.sort(key=lambda x: x.created_at, reverse=True)

        return jsonify({
            'username': current_user.username,
            'fullName': current_user.full_name,
            'email': current_user.email,
            'files': [d.to_dict() for d in valid_deployments]
        }), 200

    except Exception as e:
        db.session.rollback()
        error_msg = f"User: {current_user.username} | Error: {e}"
        auth_logger.critical(f"Action: FETCH_PROFILE | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Error (Profile Fetch)", error_msg, "CRITICAL")
        return jsonify({'error': 'Failed to fetch profile details'}), 500


@app.route('/api/user/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    data = request.get_json()
    old_password = data.get('oldPassword')
    new_password = data.get('newPassword')
    
    if not old_password or not new_password:
        return jsonify({'error': 'Missing required fields'}), 400
        
    if not current_user.check_password(old_password):
        auth_logger.warning(f"Action: CHANGE_PASSWORD | Status: WARNING | User: {current_user.username} | Reason: Incorrect current password.")
        return jsonify({'error': 'Incorrect current password'}), 400
        
    try:
        current_user.set_password(new_password)
        db.session.commit()
        auth_logger.info(f"Action: CHANGE_PASSWORD | Status: SUCCESS | User: {current_user.username}")
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        error_msg = f"User: {current_user.username} | Error: {e}"
        auth_logger.critical(f"Action: CHANGE_PASSWORD | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Error (Password Change)", error_msg, "CRITICAL")
        return jsonify({'error': 'Database error during password change'}), 500


@app.route('/api/user/file/<int:file_id>', methods=['GET'])
@token_required
def get_user_file(current_user, file_id):
    action = request.args.get('action', 'view').upper()
    
    try:
        deployment = DeploymentHistory.query.filter_by(id=file_id, user_id=current_user.id).first()
        if not deployment:
            auth_logger.warning(f"Action: FILE_{action} | Status: WARNING | User: {current_user.username} | Reason: File ID {file_id} not found or unauthorized.")
            return jsonify({'error': 'File not found or unauthorized access'}), 404
    except Exception as e:
        error_msg = f"User: {current_user.username} | Error: {e}"
        auth_logger.critical(f"Action: FILE_{action}_METADATA | Status: CRITICAL | {error_msg}")
        send_sns_alert("Database Error (File Metadata)", error_msg, "CRITICAL")
        return jsonify({'error': 'Database error while verifying file'}), 500

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=deployment.s3_key)
        file_content = response['Body'].read().decode('utf-8')
        
        auth_logger.info(f"Action: FILE_{action} | Status: SUCCESS | User: {current_user.username} | File Name: {deployment.file_name}")
        
        send_sns_alert(
            f"File Accessed ({action})", 
            f"User '{current_user.username}' successfully {action.lower()}ed the file '{deployment.file_name}'.\nS3 Path: {deployment.s3_key}", 
            "INFO"
        )
        
        return jsonify({
            'fileName': deployment.file_name,
            'fileType': deployment.file_type,
            'content': file_content
        }), 200
        
    except Exception as e:
        error_msg = f"User: {current_user.username} | S3 Key: {deployment.s3_key} | Error: {e}"
        auth_logger.critical(f"Action: FILE_{action}_S3_FETCH | Status: CRITICAL | {error_msg}")
        send_sns_alert("S3 Fetch Error", error_msg, "CRITICAL")
        return jsonify({'error': 'File could not be retrieved from storage'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)