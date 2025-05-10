# Church Bulletin Auto-Generator

This project automates the generation of a bi-fold (4-panel) church bulletin using Python, HTML, and CSS, with data sourced from a PocketBase backend. The output is a professional-looking PDF intended to be runnable via a cron job.

## Features

*   Automated data fetching from PocketBase for bulletin content and events.
*   Dynamic HTML generation using Jinja2 templates.
*   PDF rendering via WeasyPrint.
*   Customizable bi-fold layout with front cover, inside spread, and back cover.
*   Scriptable for cron job automation.

## Prerequisites

*   Python 3.x
*   Access to a PocketBase instance with the required collections (`bulletins`, `events`).
*   Dependencies listed in `requirements.txt`.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:RTSDA/Bulletin-auto-generator.git
    cd Bulletin-auto-generator
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure `config.toml`:**
    *   Create `config.toml` by copying `config.toml.example` if it exists, or by creating it manually based on the required fields (PocketBase URL, admin credentials, collection names).
    *   **Important:** `config.toml` contains sensitive credentials and is excluded by `.gitignore`. Ensure this file is secured and **never committed** to the repository.

## Usage

To generate a bulletin for the upcoming Saturday (or today if it's Saturday):
```bash
python main.py
```

To generate a bulletin for a specific date:
```bash
python main.py --date YYYY-MM-DD
```
The generated PDF will be saved in the `output/` directory.

## Cron Job Automation

Use the `setup_cron.sh` script to help generate the cron job line for your server. Follow the instructions provided by the script.
```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## Project Structure

    ./
    ├── main.py                 # Main Python script
    ├── config.toml             # Configuration (ignored by Git)
    ├── requirements.txt        # Python dependencies
    ├── templates/              # HTML/CSS templates
    │   ├── bulletin_template.html
    │   └── style.css
    ├── output/                 # Generated PDFs (ignored by Git)
    ├── temp_images/            # Temporary cover images (ignored by Git)
    ├── setup_cron.sh           # Cron setup helper script
    ├── .gitignore              # Specifies intentionally untracked files
    ├── README.md               # This file
    └── LICENSE                 # MIT License file 