#!/bin/bash

echo "--- Church Bulletin Cron Job Setup ---"
echo "This script will help you generate the cron job line for automating the bulletin generation."
echo ""

# --- Configuration - Please edit these if defaults are not suitable ---
DEFAULT_PROJECT_DIR_PARENT="/srv/bulletin_auto/bulletin_processor" # Parent of bulletin_generator
DEFAULT_PYTHON_EXEC="venv/bin/python" # Relative to bulletin_generator
DEFAULT_CRON_SCHEDULE="0 17 * * 5" # Every Friday at 5:00 PM (0 minutes, 17th hour, any day_of_month, any month, 5th day_of_week (Sunday=0 or 7))
DEFAULT_LOG_FILE_NAME="cron_bulletin.log" # Will be placed in DEFAULT_PROJECT_DIR_PARENT
# --- End Configuration ---

# Get project directory
read -p "Enter the absolute path to the 'bulletin_processor' directory on the server (e.g., /srv/bulletin_auto/bulletin_processor) [${DEFAULT_PROJECT_DIR_PARENT}]: " PROJECT_DIR_PARENT
PROJECT_DIR_PARENT_EFFECTIVE="${PROJECT_DIR_PARENT:-$DEFAULT_PROJECT_DIR_PARENT}"
BULLETIN_GENERATOR_DIR="${PROJECT_DIR_PARENT_EFFECTIVE}/bulletin_generator"

# Get Python executable path
PYTHON_EXEC_FULL_PATH_DEFAULT="${BULLETIN_GENERATOR_DIR}/${DEFAULT_PYTHON_EXEC}"
read -p "Enter the absolute path to the Python executable in your venv (e.g., ${PYTHON_EXEC_FULL_PATH_DEFAULT}) [${PYTHON_EXEC_FULL_PATH_DEFAULT}]: " PYTHON_EXEC
PYTHON_EXEC_EFFECTIVE="${PYTHON_EXEC:-$PYTHON_EXEC_FULL_PATH_DEFAULT}"

# Get cron schedule
read -p "Enter the cron schedule (e.g., '0 17 * * 5' for Fri 5PM) [${DEFAULT_CRON_SCHEDULE}]: " CRON_SCHEDULE
CRON_SCHEDULE_EFFECTIVE="${CRON_SCHEDULE:-$DEFAULT_CRON_SCHEDULE}"

# Get log file path
LOG_FILE_FULL_PATH_DEFAULT="${PROJECT_DIR_PARENT_EFFECTIVE}/${DEFAULT_LOG_FILE_NAME}"
read -p "Enter the absolute path for the cron log file (e.g., ${LOG_FILE_FULL_PATH_DEFAULT}) [${LOG_FILE_FULL_PATH_DEFAULT}]: " LOG_FILE
LOG_FILE_EFFECTIVE="${LOG_FILE:-$LOG_FILE_FULL_PATH_DEFAULT}"

MAIN_PY_SCRIPT="${BULLETIN_GENERATOR_DIR}/main.py"

# Construct the cron command
CRON_COMMAND="${CRON_SCHEDULE_EFFECTIVE} cd ${BULLETIN_GENERATOR_DIR} && ${PYTHON_EXEC_EFFECTIVE} ${MAIN_PY_SCRIPT} >> ${LOG_FILE_EFFECTIVE} 2>&1"

echo ""
echo "--- Generated Cron Job Line ---"
echo "Please add the following line to your crontab. You can edit your crontab by running: crontab -e"
echo ""
echo "${CRON_COMMAND}"
echo ""
echo "--- Important Next Steps on the Server ---"
echo "1. Ensure this project is copied to: ${PROJECT_DIR_PARENT_EFFECTIVE}"
echo "2. Inside '${BULLETIN_GENERATOR_DIR}', ensure your Python virtual environment ('venv/') is set up and contains all dependencies (requests, toml, jinja2, WeasyPrint)."
echo "   You might need to run: cd ${BULLETIN_GENERATOR_DIR} && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt (if you have a requirements.txt)"
echo "3. Make sure the Python script '${MAIN_PY_SCRIPT}' is present."
echo "4. Ensure the Python executable path '${PYTHON_EXEC_EFFECTIVE}' is correct and executable."
echo "5. Ensure the directory for the log file exists or that cron can create it (e.g., create '${PROJECT_DIR_PARENT_EFFECTIVE}' if it doesn't exist)."
echo "6. Your 'config.toml' must be correctly placed and configured within '${BULLETIN_GENERATOR_DIR}'."
echo ""
echo "After adding the line to your crontab, the job will run according to the schedule: ${CRON_SCHEDULE_EFFECTIVE}."
echo "Monitor '${LOG_FILE_EFFECTIVE}' for output and errors." 