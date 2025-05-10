# Main script for bulletin generation

import requests  # For HTTP requests to PocketBase
import toml      # For reading config.toml
import jinja2    # For HTML templating
from weasyprint import HTML, CSS # For PDF generation
import os
import datetime # For handling dates
import argparse
import re # Added for HTML stripping
import html # For unescaping HTML entities like &nbsp;

# --- Configuration ---
CONFIG_PATH = "config.toml" # NOW LOCAL TO SCRIPT DIRECTORY
TEMP_IMAGE_DIR = "temp_images"
OUTPUT_DIR = "output" # For local PDF saving
TEMPLATES_DIR = "templates" # Directory for Jinja2 templates, relative to main.py

def strip_html_tags(text):
    """Removes HTML tags from a string and handles common entities like &nbsp;."""
    if not text:
        return ""
    # 1. Remove HTML tags
    text_no_tags = re.sub(r'<[^>]+>', '', text)
    # 2. Unescape HTML entities (e.g., &nbsp; -> \xa0, &amp; -> &)
    text_unescaped = html.unescape(text_no_tags)
    # 3. Replace non-breaking space character (\xa0) with a regular space
    text_final = text_unescaped.replace('\xa0', ' ')
    return text_final

def load_config():
    """Loads configuration from config.toml."""
    try:
        # Construct the absolute path to config.toml relative to main.py
        # os.path.abspath ensures the path is correct regardless of where the script is run from,
        # as long as config.toml maintains its relative position to the script.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file_path = os.path.join(script_dir, CONFIG_PATH)
        
        with open(config_file_path, 'r') as f:
            config_data = toml.load(f)
        print(f"Successfully loaded configuration from {config_file_path}")
        return config_data
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at {config_file_path}")
        return None
    except toml.TomlDecodeError as e:
        print(f"ERROR: Could not decode TOML from {config_file_path}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading config: {e}")
        return None

def get_pocketbase_client(config):
    """
    Extracts PocketBase connection details from the loaded configuration.
    Returns a dictionary with 'base_url', 'admin_email', 'admin_password',
    or None if essential keys are missing.
    """
    if not config:
        print("ERROR: Configuration data is not available for PocketBase client setup.")
        return None

    required_keys = [
        "pocketbase_url", 
        "pocketbase_admin_email", 
        "pocketbase_admin_password", 
        "bulletin_collection_name",
        "events_collection_name"
    ]
    pb_details = {}

    for key in required_keys:
        if key not in config:
            print(f"ERROR: Missing '{key}' in configuration for PocketBase client.")
            return None
        pb_details[key] = config[key]
    
    # Ensure the URL does not end with a slash to simplify joining later
    if pb_details["pocketbase_url"].endswith('/'):
        pb_details["pocketbase_url"] = pb_details["pocketbase_url"].rstrip('/')

    print(f"PocketBase client configured for URL: {pb_details['pocketbase_url']}")
    return pb_details

def fetch_bulletin_data(pb_config, bulletin_date_str):
    """
    Fetches the bulletin record for the given date string (e.g., "YYYY-MM-DD").
    Assumes public read access for the bulletin collection.
    Returns the bulletin record item if found, otherwise None.
    """
    if not pb_config:
        print("ERROR: PocketBase configuration is not available for fetching bulletin data.")
        return None

    base_url = pb_config['pocketbase_url']
    collection_name = pb_config['bulletin_collection_name']
    
    api_url = f"{base_url}/api/collections/{collection_name}/records"

    # Parse the input date string to create a date range for the filter
    try:
        target_date = datetime.datetime.strptime(bulletin_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"ERROR: Invalid bulletin_date_str format: '{bulletin_date_str}'. Please use YYYY-MM-DD.")
        return None

    start_datetime_str = target_date.strftime("%Y-%m-%d 00:00:00")
    # Next day for the upper bound (exclusive)
    next_day_date = target_date + datetime.timedelta(days=1)
    end_datetime_str = next_day_date.strftime("%Y-%m-%d 00:00:00") # Exclusive end

    params = {
        'filter': f"(date >= '{start_datetime_str}' && date < '{end_datetime_str}')"
        # Add 'is_active=true' if you have such a field: f"(date>='{start_datetime_str}' && date<'{end_datetime_str}' && is_active=true)"
    }

    try:
        print(f"Fetching bulletin data from: {api_url} with params: {params}")
        response = requests.get(api_url, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        data = response.json()
        records = data.get('items', [])

        if len(records) == 1:
            print(f"Successfully fetched bulletin record for date: {bulletin_date_str}")
            return records[0] # Return the single record found
        elif len(records) == 0:
            print(f"No bulletin record found for date: {bulletin_date_str}")
            return None
        else:
            print(f"WARNING: Multiple bulletin records ({len(records)}) found for date: {bulletin_date_str}. Returning the first one.")
            return records[0] # Or handle as an error, depending on expected data integrity

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed while fetching bulletin data: {e}")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while fetching bulletin data: {e}")
        return None

def download_cover_image(pb_config, collection_id, record_id, image_field_name, bulletin_record, save_dir):
    """
    Downloads a file (e.g., cover image) from a PocketBase record.
    Assumes the field 'image_field_name' in 'bulletin_record' contains the filename.
    Returns the full path to the downloaded image, or None on error.
    """
    if not pb_config:
        print("ERROR: PocketBase configuration is not available for downloading image.")
        return None
    if not bulletin_record:
        print("ERROR: Bulletin record data is not available for downloading image.")
        return None

    base_url = pb_config['pocketbase_url']
    image_filename = bulletin_record.get(image_field_name)

    if not image_filename:
        print(f"ERROR: Image filename not found in bulletin record under field '{image_field_name}'.")
        return None

    # Ensure the save directory exists
    os.makedirs(save_dir, exist_ok=True)

    # Construct the file download URL
    # Format: /api/files/COLLECTION_ID_OR_NAME/RECORD_ID/FILENAME
    file_url = f"{base_url}/api/files/{collection_id}/{record_id}/{image_filename}"
    local_image_path = os.path.join(save_dir, image_filename)

    try:
        print(f"Downloading cover image from: {file_url}")
        response = requests.get(file_url, stream=True) # stream=True for potentially larger files
        response.raise_for_status()

        with open(local_image_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Successfully downloaded cover image to: {local_image_path}")
        return local_image_path

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed while downloading image '{image_filename}': {e}")
        if os.path.exists(local_image_path):
            os.remove(local_image_path) # Clean up partial download
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while downloading image '{image_filename}': {e}")
        if os.path.exists(local_image_path):
            os.remove(local_image_path) # Clean up partial download
        return None

def fetch_events_data(pb_config, bulletin_date_obj):
    """
    Fetches all events and filters them based on end_time >= bulletin_date_obj.
    Assumes public read access for the events collection.
    'bulletin_date_obj' is a datetime.date object.
    Returns a list of event items, or an empty list on error/no events.
    """
    if not pb_config:
        print("ERROR: PocketBase configuration is not available for fetching events.")
        return []

    base_url = pb_config['pocketbase_url']
    collection_name = pb_config.get('events_collection_name') # Get from config

    if not collection_name:
        print("ERROR: 'events_collection_name' not found in PocketBase configuration.")
        return []

    api_url = f"{base_url}/api/collections/{collection_name}/records"

    # Format the bulletin_date_obj to "YYYY-MM-DD 00:00:00" for the filter
    filter_start_date_str = bulletin_date_obj.strftime("%Y-%m-%d 00:00:00")

    params = {
        # Filter for events where end_time is greater than or equal to the start of the bulletin day.
        # Assumes 'end_time' is a datetime field in PocketBase.
        'filter': f"(end_time >= '{filter_start_date_str}')",
        'sort': '+start_time' # Optional: sort events by their start time
    }

    try:
        print(f"Fetching events data from: {api_url} with params: {params}")
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        events = data.get('items', [])
        
        print(f"Successfully fetched {len(events)} events.")
        # Format start_time and strip HTML from relevant fields
        for event in events:
            if 'title' in event and event['title']:
                event['title'] = strip_html_tags(event['title'])
            if 'description' in event and event['description']:
                event['description'] = strip_html_tags(event['description'])
            
            if 'start_time' in event and event['start_time']:
                try:
                    # Assuming start_time is like "2024-03-15 10:00:00.000Z"
                    dt_obj = datetime.datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                    event['start_time_formatted'] = dt_obj.strftime("%A, %B %d, %Y at %I:%M %p") # Readable format
                except ValueError:
                    event['start_time_formatted'] = event['start_time'] # Fallback to raw string
            else:
                event['start_time_formatted'] = "Date/Time TBD"

        return events

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Request failed while fetching events data: {e}")
        return []
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while fetching events data: {e}")
        return []

def parse_sabbath_school(ss_text):
    """
    Parses the plain text (after stripping HTML) from the sabbath_school field.
    Expected format is "Label:" on one line, value on the next.
    Returns a list of dictionaries (e.g., [{'label': 'Song Service', 'details': 'Lisa Wroniak', 'time': '9:30 AM'}, ...])
    """
    sabbath_school_event_times = ["9:15 AM", "9:30 AM", "10:30 AM", "10:35 AM", "10:45 AM"]
    clean_ss_text = strip_html_tags(ss_text) # Strip HTML first
    if not clean_ss_text or not clean_ss_text.strip():
        return []

    parsed_items = []
    lines = clean_ss_text.splitlines()
    i = 0
    while i < len(lines):
        current_line = lines[i].strip() # Ensure line is stripped for checks
        if not current_line: # Skip empty lines that might result from splitlines or data
            i += 1
            continue

        if current_line.endswith(':'):
            label = current_line[:-1].strip() # Remove colon and strip
            details = ""
            # Check if there is a next line, it's not empty, and it's not another label
            if i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].strip().endswith(':'):
                details = lines[i+1].strip() # Assign stripped details line
                i += 1 # Crucial: Move past the details line as it has been consumed
            
            item_time = ""
            if len(parsed_items) < len(sabbath_school_event_times):
                item_time = sabbath_school_event_times[len(parsed_items)]
            else:
                item_time = "Time TBD" # Fallback if more items than times

            parsed_items.append({'label': label, 'details': details, 'time': item_time})
        # If the line doesn't end with ':', it might be a details line already consumed by a previous label,
        # or it's a line that doesn't fit the "Label:" pattern (e.g., an orphaned detail or remark).
        # In such cases, we just move to the next line.
        i += 1
        
    return parsed_items

def _process_dw_item(label_str, detail_lines):
    """Helper to process a single divine worship item."""
    item = {
        'label': label_str,
        'type': 'Default', # Will be overridden
        'title': None,
        'speaker': None,
        'details': "\n".join(detail_lines).strip() # Default behavior for details
    }

    normalized_label = label_str.lower()
    print(f"DEBUG DW LABEL: '{label_str}', NORMALIZED: '{normalized_label}'")

    if "sermon" in normalized_label:
        item['type'] = "Sermon"
        if len(detail_lines) >= 1:
            item['title'] = detail_lines[0].strip()
        if len(detail_lines) >= 2:
            item['speaker'] = detail_lines[1].strip()
        # Consolidate remaining details or clear if captured by title/speaker
        item['details'] = "\n".join(detail_lines[2:]).strip() if len(detail_lines) > 2 else None

    elif "scripture reading" in normalized_label:
        item['type'] = "Scripture Reading"
        if len(detail_lines) >= 1:
            item['title'] = detail_lines[0].strip()  # Scripture reference
        if len(detail_lines) >= 2:
            item['speaker'] = detail_lines[1].strip()  # Reader
        item['details'] = "\n".join(detail_lines[2:]).strip() if len(detail_lines) > 2 else None

    elif "hymn" in normalized_label or "song" in normalized_label:
        item['type'] = "Hymn"
        item['title'] = " ".join(line.strip() for line in detail_lines)
        item['details'] = None

    elif "call to worship" in normalized_label:
        item['type'] = "Call to Worship"
        item['title'] = " ".join(line.strip() for line in detail_lines)
        item['details'] = None

    elif "prayer" in normalized_label:  # Catches "Prayer & Praises"
        item['type'] = "Prayer"
        if len(detail_lines) == 1:
            item['speaker'] = detail_lines[0].strip()
            item['details'] = None
        # else, default details behavior if more lines

    elif "offering" in normalized_label:
        item['type'] = "Offering"
        if len(detail_lines) >= 1:
            item['title'] = detail_lines[0].strip()  # What the offering is for
        if len(detail_lines) >= 2:
            item['speaker'] = detail_lines[1].strip() # Person involved
        item['details'] = "\n".join(detail_lines[2:]).strip() if len(detail_lines) > 2 else None

    elif "children's story" in normalized_label or "childrens story" in normalized_label:
        item['type'] = "Childrens Story"
        if len(detail_lines) == 1:
            item['speaker'] = detail_lines[0].strip()
            item['details'] = None

    elif "special music" in normalized_label:
        item['type'] = "Special Music"
        if len(detail_lines) == 1 and detail_lines[0].strip().lower() == 'tba':
            item['title'] = 'TBA'
            item['speaker'] = None
        elif len(detail_lines) == 1:
            item['speaker'] = detail_lines[0].strip()
        item['details'] = None # Usually speaker/TBA is enough
    
    elif "announcements" in normalized_label: # From DW example
        item['type'] = "Announcement DW"
        if len(detail_lines) == 1:
            item['speaker'] = detail_lines[0].strip()
            item['details'] = None

    # If type is still Default or details are just joined lines
    if item['type'] == 'Default':
        item['details'] = "\n".join(line.strip() for line in detail_lines).strip()
        item['title'] = None 
        item['speaker'] = None

    if not item['details']: # Ensure empty string becomes None
        item['details'] = None
    
    return item

def parse_divine_worship(dw_text):
    """
    Parses the Divine Worship text (after stripping HTML) into a structured list of items.
    Handles labels and multi-line details, identifying specific types like Sermon, Hymn, etc.
    """
    clean_dw_text = strip_html_tags(dw_text) # Strip HTML first
    if not clean_dw_text or not clean_dw_text.strip():
        return []

    items = []
    current_lines = clean_dw_text.splitlines() # Use cleaned text
    
    current_label = None
    detail_lines = []

    i = 0
    while i < len(current_lines):
        current_line = current_lines[i].strip() # Ensure the line is stripped before checking
        if not current_line: # Skip empty lines
            i += 1
            continue

        if current_line.endswith(':'):
            if current_label: # If there was a previous label, process it
                item_dict = _process_dw_item(current_label, detail_lines)
                items.append(item_dict)
            current_label = current_line[:-1].strip() # Assign new label (already stripped, but strip colon part)
            detail_lines = [] # Reset for new label
        else:
            detail_lines.append(current_lines[i]) # Append the original (unstripped) line for details
        i += 1

    if current_label: # Process the last accumulated item
        item_dict = _process_dw_item(current_label, detail_lines)
        items.append(item_dict)

    return items

def render_html_template(template_file_name, context_data):
    """
    Renders the Jinja2 HTML template with the given context.
    'template_file_name' is the name of the template file in the TEMPLATES_DIR.
    Returns the rendered HTML as a string, or None on error.
    """
    try:
        # Get the directory containing the current script (main.py)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Combine with the TEMPLATES_DIR to get the absolute path to the templates folder
        templates_abs_path = os.path.join(script_dir, TEMPLATES_DIR)
        
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(templates_abs_path),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
        template = env.get_template(template_file_name)
        rendered_html = template.render(context_data)
        print(f"Successfully rendered HTML template: {template_file_name}")
        return rendered_html
    except jinja2.exceptions.TemplateNotFound:
        print(f"ERROR: Jinja2 template not found: {template_file_name} in {templates_abs_path}")
        return None
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during HTML template rendering: {e}")
        return None

def generate_pdf_from_html(html_string, output_pdf_path):
    """
    Converts HTML content to PDF using WeasyPrint.
    html_string: The HTML content as a string.
    output_pdf_path: The full path where the PDF will be saved.
    The CSS is expected to be linked correctly in the HTML and resolvable
    relative to the base_url (templates directory).
    Returns True on success, False on error.
    """
    if not html_string:
        print("ERROR: No HTML content provided for PDF generation.")
        return False

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # base_url for resolving relative paths in HTML (like style.css link, or images if they were relative)
        # Our cover image path is absolute, so this mainly helps find style.css.
        base_url_for_html = os.path.join(script_dir, TEMPLATES_DIR)
        
        # Explicitly load the CSS to ensure it's found and applied.
        css_file_path = os.path.join(base_url_for_html, "style.css")
        if not os.path.exists(css_file_path):
            print(f"ERROR: CSS file not found at {css_file_path}")
            return False
        
        css_stylesheet = CSS(css_file_path)

        # Ensure output directory exists for the PDF
        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

        html_doc = HTML(string=html_string, base_url=base_url_for_html)
        html_doc.write_pdf(output_pdf_path, stylesheets=[css_stylesheet])
        
        print(f"Successfully generated PDF: {output_pdf_path}")
        return True
    except FileNotFoundError as e: # For CSS file usually
        print(f"ERROR: File not found during PDF generation: {e}")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during PDF generation: {e}")
        return False

def upload_pdf_to_pocketbase(pb_config, bulletin_collection_id, bulletin_record_id, pdf_path, bulletin_record_data):
    """
    Uploads the generated PDF to the 'pdf' field of the specified bulletin record.
    Requires admin authentication.
    Returns True on success, False on error.
    """
    if not pb_config:
        print("ERROR: PocketBase configuration is not available for PDF upload.")
        return False

    base_url = pb_config['pocketbase_url']
    admin_email = pb_config['pocketbase_admin_email']
    admin_password = pb_config['pocketbase_admin_password']
    auth_token = None

    # 1. Authenticate as Admin to get a token
    # The collection for admins is typically named '_superusers'
    admin_collection_name = "_superusers" 
    auth_url = f"{base_url}/api/collections/{admin_collection_name}/auth-with-password"
    auth_payload = {
        'identity': admin_email,
        'password': admin_password
    }
    try:
        print(f"Authenticating admin user: {admin_email}")
        auth_response = requests.post(auth_url, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        auth_token = auth_data.get('token')
        if not auth_token:
            print("ERROR: Admin authentication successful but no token received.")
            return False
        print("Admin authentication successful.")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Admin authentication failed: {e} - Response: {e.response.text if e.response else 'No response'}")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during admin authentication: {e}")
        return False

    # Common URL for updates
    update_url = f"{base_url}/api/collections/{bulletin_collection_id}/records/{bulletin_record_id}"
    headers = {
        # Use token directly, as this worked
        'Authorization': auth_token 
    }

    # 2. Upload the PDF file (original logic)
    pdf_filename = os.path.basename(pdf_path)
    try:
        with open(pdf_path, 'rb') as f:
            files = {
                'pdf': (pdf_filename, f, 'application/pdf')
            }
            print(f"Uploading PDF '{pdf_filename}' to record '{bulletin_record_id}' at {update_url}")
            upload_response = requests.patch(update_url, headers=headers, files=files)
            upload_response.raise_for_status()
            print(f"Successfully uploaded PDF to PocketBase record ID: {bulletin_record_id}")
            return True
            
    except FileNotFoundError:
        print(f"ERROR: PDF file not found at {pdf_path} for upload.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"ERROR: PDF upload failed: {e} - Response: {e.response.text if e.response else 'No response'}")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during PDF upload: {e}")
        return False

def cleanup_temp_files(image_path):
    """Removes temporary downloaded files (e.g., cover image)."""
    if not image_path or not os.path.exists(image_path):
        print(f"INFO: No temporary file to clean up at {image_path}, or file already removed.")
        return

    try:
        os.remove(image_path)
        print(f"Successfully removed temporary file: {image_path}")
    except OSError as e:
        print(f"ERROR: Could not remove temporary file {image_path}: {e}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during file cleanup for {image_path}: {e}")

def main_process(bulletin_date_str):
    """
    Main orchestration function.
    Takes a date string (e.g., "2024-03-15") to identify the bulletin.
    """
    print(f"--- Starting bulletin generation process for date: {bulletin_date_str} ---")

    # 1. Load config
    config = load_config()
    if not config:
        print("PROCESS HALTED: Configuration loading failed.")
        return

    # 2. Get PocketBase client details (not a client object, just config dict)
    pb_config = get_pocketbase_client(config)
    if not pb_config:
        print("PROCESS HALTED: PocketBase client configuration failed.")
        return

    # Create a datetime.date object from bulletin_date_str for functions that need it
    try:
        bulletin_date_obj = datetime.datetime.strptime(bulletin_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"PROCESS HALTED: Invalid bulletin_date_str format: '{bulletin_date_str}'. Please use YYYY-MM-DD.")
        return

    # 3. Fetch bulletin data
    print("Fetching bulletin main data...")
    bulletin_record = fetch_bulletin_data(pb_config, bulletin_date_str)
    if not bulletin_record:
        print(f"PROCESS HALTED: Could not fetch bulletin data for {bulletin_date_str}.")
        return
    
    print(f"DEBUG: Full bulletin record details: {bulletin_record}") # DEBUG PRINT
    
    bulletin_record_id = bulletin_record.get('id')
    bulletin_collection_id = bulletin_record.get('collectionId') # PB provides this
    if not bulletin_record_id or not bulletin_collection_id:
        print("PROCESS HALTED: Bulletin record ID or Collection ID missing from fetched data.")
        return

    # 4. Download cover image
    print("Downloading cover image...")
    # Assuming 'cover_image' is the field name in PB for the image filename
    # Ensure TEMP_IMAGE_DIR is an absolute path or resolvable from script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_image_save_dir = os.path.join(script_dir, TEMP_IMAGE_DIR)
    
    downloaded_cover_image_path = download_cover_image(
        pb_config, 
        bulletin_collection_id, 
        bulletin_record_id, 
        'cover_image', # Field name for the image in the bulletin record
        bulletin_record, 
        temp_image_save_dir
    )
    if not downloaded_cover_image_path:
        print("PROCESS CONTINUING WITHOUT COVER IMAGE: Cover image download failed.")
        # Allow process to continue, template can handle missing image

    # 5. Fetch and filter events (announcements)
    print("Fetching announcements (events data)...")
    announcements = fetch_events_data(pb_config, bulletin_date_obj)
    # fetch_events_data returns [] on error, so we can proceed

    # 6. Parse Sabbath School text
    print("Parsing Sabbath School text...")
    ss_text = bulletin_record.get('sabbath_school', '')
    sabbath_school_items = parse_sabbath_school(ss_text)

    # 7. Parse Divine Worship text
    print("Parsing Divine Worship text...")
    dw_text = bulletin_record.get('divine_worship', '')
    divine_worship_items = parse_divine_worship(dw_text)

    # 8. Prepare context for Jinja2 template
    print("Preparing template context...")
    bulletin_theme_title = strip_html_tags(bulletin_record.get('title', 'Welcome'))
    sunset_times = strip_html_tags(bulletin_record.get('sunset', 'Not available'))
    context_data = {
        'bulletin_date': bulletin_date_obj.strftime("%B %d, %Y"), # Formatted date
        'bulletin_theme_title': bulletin_theme_title,
        'church_name': config.get('church_name', 'Rockville Tolland SDA Church'), # Get from config or default
        'cover_image_path': downloaded_cover_image_path, # Will be None if download failed
        'sabbath_school_items': sabbath_school_items,
        'divine_worship_items': divine_worship_items,
        'announcements': announcements,
        'sunset_times': sunset_times,
        'contact_info': { # Could also be loaded from config if it varies
            'phone': config.get('contact_phone', '860-875-0450'),
            'website': config.get('contact_website', 'rockvilletollandsda.church'),
            'youtube': config.get('contact_youtube', 'YouTube.com/@RockvilleTollandSDAChurch'),
            'address': config.get('contact_address', '9 Hartford Tpke Tolland CT 06084')
        }
    }

    # 9. Render HTML
    print("Rendering HTML template...")
    html_output = render_html_template('bulletin_template.html', context_data)
    if not html_output:
        print("PROCESS HALTED: HTML rendering failed.")
        cleanup_temp_files(downloaded_cover_image_path)
        return

    # 10. Generate PDF
    print("Generating PDF...")
    # Ensure OUTPUT_DIR is an absolute path or resolvable
    output_dir_abs = os.path.join(script_dir, OUTPUT_DIR)
    os.makedirs(output_dir_abs, exist_ok=True)
    pdf_filename = f"bulletin_{bulletin_date_str}.pdf"
    output_pdf_path = os.path.join(output_dir_abs, pdf_filename)
    
    pdf_generation_success = generate_pdf_from_html(html_output, output_pdf_path)
    if not pdf_generation_success:
        print("PROCESS HALTED: PDF generation failed.")
        cleanup_temp_files(downloaded_cover_image_path)
        return

    # 11. Upload PDF to PocketBase
    print("Uploading PDF to PocketBase...")
    upload_success = upload_pdf_to_pocketbase(
        pb_config, 
        bulletin_collection_id, 
        bulletin_record_id, 
        output_pdf_path,
        bulletin_record # Pass the fetched bulletin_record here
    )
    if not upload_success:
        print("PROCESS WARNING: PDF upload to PocketBase failed. PDF is available locally.")
        # Don't halt, PDF is still generated locally.
    
    # 12. Cleanup temp image
    print("Cleaning up temporary files...")
    cleanup_temp_files(downloaded_cover_image_path)

    print(f"--- Bulletin generation process for date: {bulletin_date_str} COMPLETED ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a church bulletin PDF from PocketBase data.")
    parser.add_argument(
        "--date", 
        type=str, 
        help="Optional: Specific date for the bulletin in YYYY-MM-DD format. Defaults to the upcoming Saturday (or today if it is Saturday)."
    )
    
    args = parser.parse_args()
    target_bulletin_date_str = None

    if args.date:
        try:
            # Validate the provided date format
            datetime.datetime.strptime(args.date, "%Y-%m-%d")
            target_bulletin_date_str = args.date
            print(f"Using provided date: {target_bulletin_date_str}")
        except ValueError:
            print(f"ERROR: Provided date argument '{args.date}' must be in YYYY-MM-DD format.")
            parser.print_help()
            exit(1)
    else:
        today = datetime.date.today()
        # weekday(): Monday is 0 and Sunday is 6. Saturday is 5.
        if today.weekday() == 5: # It's Saturday
            target_bulletin_date = today
            print(f"Today is Saturday. Using current date: {target_bulletin_date.strftime('%Y-%m-%d')}")
        else: # It's not Saturday, find the upcoming Saturday
            days_until_saturday = (5 - today.weekday() + 7) % 7
            target_bulletin_date = today + datetime.timedelta(days=days_until_saturday)
            print(f"No date provided. Automatically determined upcoming Saturday: {target_bulletin_date.strftime('%Y-%m-%d')}")
        target_bulletin_date_str = target_bulletin_date.strftime("%Y-%m-%d")

    if target_bulletin_date_str:
        main_process(target_bulletin_date_str)
    else:
        # This case should not be reached if logic is correct, but as a safeguard:
        print("ERROR: Could not determine target bulletin date.")
        exit(1) 