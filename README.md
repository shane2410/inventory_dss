# Inventory DSS

Minimal instructions to set up and run the Django inventory project locally.

Prerequisites

- Python 3.10+ installed
- Git (optional)

Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # or use activate.bat on cmd.exe
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks script execution, use cmd to activate and install:

```cmd
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

Run the development server

```powershell
cd inventory_dss-main
python manage.py migrate
python manage.py runserver
```

Notes

- The project uses SQLite by default. To use MySQL, set the environment variable `USE_MYSQL=1` and configure `MYSQL_*` variables in your environment.
- If you prefer to use the system Python where Django may already be installed, skip creating a virtual environment but be cautious about global package conflicts.
