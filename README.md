# tanishimu-credit-simulator

A graduation requirement and GPA checker for Osaka University economics students.

This project includes:

- A desktop app for local use
- A web app for paste-based KOAN import
- KOAN transcript parsing into the internal JSON format
- Graduation requirement checks and GPA calculation

## Privacy

This repository does not include personal transcript data.

- `current_student_data.json` is intentionally ignored
- source PDFs under `学生便覧/` are intentionally ignored

Users should paste their own KOAN transcript or prepare their own JSON data locally.

## Run the desktop app

```powershell
py -3.12 main.py
```

## Run the web app

Install dependencies:

```powershell
py -3.12 -m pip install -r requirements-web.txt
```

Run locally:

```powershell
py -3.12 web_app.py --host 127.0.0.1 --port 7860
```

Open a temporary public tunnel:

```powershell
launch_public_tunnel.bat
```

## Main files

- `main.py`: desktop UI
- `web_app.py`: web UI
- `simulator.py`: parsing, credit aggregation, GPA logic
- `requirements.py`: degree rules and validation

## Notes

GitHub can host the source code, but the Python web app itself still needs a Python runtime to run.
