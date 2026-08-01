import os
import json
import logging
import subprocess
from datetime import datetime


from Src.path import OS_DATA_PATH, CONFIG_FILE_PATH
from Src.models import TagModel, InstanceModel, ReservationModel, RootModel

def load_os_data(f_logger: logging.Logger, c_logger: logging.Logger) -> dict:
    try:
        with open(OS_DATA_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        f_logger.error(f" Error: The source file {OS_DATA_PATH} was not found.")
        c_logger.error("Error: Source file missing. Check logs.")
        return None
    except json.JSONDecodeError:
        f_logger.error(f" Error: The file {OS_DATA_PATH} contains invalid JSON.")
        c_logger.error("Error: Source file is corrupt. Check logs.")
        return None

def get_user_inputs(f_logger: logging.Logger, c_logger: logging.Logger):
    count = 0
    while True:
        val = input("Enter count (1-10): ")
        if val.isdigit():
            int_val = int(val)
            if 1 <= int_val <= 10:
                count = int_val
                break
        f_logger.error(f" Error: Invalid count input: '{val}'. User prompted to try again.")
        c_logger.error("Error: Please enter a number between 1 and 10.")

    base_name = ""
    while True:
        val = input("Enter machine base name: ")
        if len(val.strip()) > 0:
            base_name = val
            break
        f_logger.error(" Error: Invalid name input: Empty string provided. User prompted to try again.")
        c_logger.error("Error: Name cannot be empty.")

    os_key = ""
    while True:
        val = input("Enter OS (ubuntu/centos): ").lower()
        if val in ["ubuntu", "centos"]:
            os_key = val
            break
        f_logger.error(f" Error: Invalid OS input: '{val}'. User prompted to try again.")
        c_logger.error("Error: Must be 'ubuntu' or 'centos'.")

    type_choice = ""
    c_logger.info("1. t2micro (2 VCPU RAM: 1GB)\n2. t2nano (1 VCPU RAM: 0.5GB)")
    while True:
        val = input("Select type (1 or 2): ")
        if val in ["1", "2"]:
            type_choice = val
            break
        f_logger.error(f" Error: Invalid type input: '{val}'. User prompted to try again.")
        c_logger.error("Error: Must be 1 or 2. \n1. t2micro (2 VCPU RAM: 1GB)\n2. t2nano (1 VCPU RAM: 0.5GB)")

    return count, base_name, os_key, type_choice

def generate_reservation_model(count: int, base_name: str, os_key: str, type_choice: str, os_data: dict) -> RootModel:
    ami = os_data.get(os_key, "ami-unknown")
    i_type = "t2.micro" if type_choice == "1" else "t2.nano"
    launch_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    instances_list = []

    for i in range(1, count + 1):
        name_val = f"{base_name}-{i}"
        
        instance = InstanceModel(
            ImageId=ami,
            InstanceType=i_type,
            LaunchTime=launch_time,
            Tags=[
                TagModel(Key="Name", Value=name_val)
            ]
        )
        instances_list.append(instance)

    reservation = ReservationModel(Instances=instances_list)
    return RootModel(Reservations=[reservation])

def save_configuration(data_model: RootModel, f_logger: logging.Logger, c_logger: logging.Logger, count: int):
    config_dir = os.path.dirname(CONFIG_FILE_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)

    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            f.write(data_model.model_dump_json(indent=4))

        f_logger.info(f"Successfully created configuration for {count} instances in {CONFIG_FILE_PATH}")
        c_logger.info(f"Success! Configuration saved to {CONFIG_FILE_PATH}.")
        
    except Exception as e:
        f_logger.error(f"Unexpected System Error during file save: {e}")
        c_logger.error("An unexpected error occurred while saving.")

def run_bash_installation(os_key: str, f_logger: logging.Logger, c_logger: logging.Logger) -> bool:
    script_path = os.path.join("./Scripts/", f"{os_key}_install.sh")
    
    if not os.path.exists(script_path):
        f_logger.error(f"Installation script not found: {script_path}")
        c_logger.error(f"Error: Installation script not found: {script_path}")
        return False

    f_logger.info(f"--- Starting deployment script: {script_path} ---")
    c_logger.info(f"\nStarting {os_key} deployment (Nginx)... please wait, until you see the completion message.")

    try:
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        f_logger.info(f"Deployment script executed successfully.\nOutput:\n{result.stdout.strip()}")
        c_logger.info("Deployment completed successfully!, You can check log in ./Logs/app.log.")
        return True

    except subprocess.CalledProcessError as e:
        f_logger.error(f" Error: Deployment failed! Bash script exited with code: {e.returncode}")
        
        error_output = e.stderr.strip() if e.stderr else ""
        standard_output = e.stdout.strip() if e.stdout else ""
        
        full_error_log = f"Bash Output Before Crash:\n{standard_output}\n\nBash Error Message:\n{error_output}"
        
        f_logger.error(full_error_log)
        c_logger.error("\n[ERROR] Deployment failed during execution!")
        c_logger.error(f"Reason:\n{error_output if error_output else standard_output}")
        c_logger.error("Please check the log file for full details.")
        return False

    except Exception as e:
        f_logger.critical(f"Critical System Error running bash script: {e}")
        c_logger.error(f"\n[CRITICAL ERROR] Failed to start deployment process: {e}")
        return False