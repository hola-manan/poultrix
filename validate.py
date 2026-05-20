#!/usr/bin/env python
"""
Quick validation script - runs diagnostics and basic tests
Usage: python validate.py
"""
import sys
import subprocess
from pathlib import Path

# src/ layout: add src/ to path so `import jeevn.*` works without pip install -e .
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_python_version():
    """Check Python version"""
    print_section("1. Python Version")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("⚠️  WARNING: Python 3.11+ recommended")
        return False
    print("✅ OK")
    return True

def check_required_packages():
    """Check if required packages are installed"""
    print_section("2. Required Packages")
    
    required = [
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'pydantic',
        'pytest',
        'requests',
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - NOT INSTALLED")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    return True

def check_optional_packages():
    """Check optional packages"""
    print_section("3. Optional Packages")
    
    optional = [
        ('rasterio', 'GDAL/rasterio - for full preprocessing'),
        ('gdal', 'GDAL - for remote sensing data'),
        ('sentinelsat', 'SentinelSat - for Sentinel-2 data access'),
        ('streamlit', 'Streamlit - for UI'),
        ('prometheus_client', 'Prometheus - for metrics'),
        ('mlflow', 'MLflow - for experiment tracking'),
    ]
    
    for pkg, desc in optional:
        try:
            __import__(pkg)
            print(f"✅ {desc}")
        except ImportError:
            print(f"⚠️  {desc} - optional")
    return True

def check_imports():
    """Check if main modules can be imported"""
    print_section("4. Module Imports")
    
    modules = [
        'jeevn.api.app',
        'jeevn.infrastructure.db.connection',
        'jeevn.infrastructure.db.models',
        'jeevn.ingestion.sentinel',
        'jeevn.ingestion.runner',
        'jeevn.remote_sensing.pipeline',
    ]
    
    for mod in modules:
        try:
            __import__(mod)
            print(f"✅ {mod}")
        except ImportError as e:
            print(f"❌ {mod} - {e}")
            return False
    
    return True

def check_file_structure():
    """Check if required files exist"""
    print_section("5. File Structure")
    
    required_files = [
        'src/jeevn/api/app.py',
        'src/jeevn/infrastructure/db/connection.py',
        'src/jeevn/infrastructure/db/models.py',
        'src/jeevn/ingestion/sentinel.py',
        'src/jeevn/remote_sensing/pipeline.py',
        'requirements.txt',
        '.env.example',
        'tests/api/test_api.py',
        'tests/infrastructure/db/test_models.py',
    ]
    
    missing = []
    for file in required_files:
        if Path(file).exists():
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - NOT FOUND")
            missing.append(file)
    
    return len(missing) == 0

def run_syntax_check():
    """Run Python syntax check on main files"""
    print_section("6. Python Syntax Check")
    
    files = [
        'src/jeevn/api/app.py',
        'src/jeevn/ingestion/sentinel.py',
        'src/jeevn/remote_sensing/pipeline.py',
        'src/jeevn/infrastructure/db/models.py',
    ]
    
    all_ok = True
    for file in files:
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'py_compile', file],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"✅ {file}")
            else:
                print(f"❌ {file}")
                print(f"   {result.stderr.decode()}")
                all_ok = False
        except Exception as e:
            print(f"❌ {file} - {e}")
            all_ok = False
    
    return all_ok

def check_database():
    """Check database initialization"""
    print_section("7. Database")
    
    try:
        from jeevn.infrastructure.db import connection as db
        db.init_db()
        print("✅ Database initialization successful")
        print(f"   Using: sqlite:///./data/dev.db")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False

def run_unit_tests():
    """Run pytest on new tests"""
    print_section("8. Unit Tests")
    
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest',
             'tests/infrastructure/db/test_models.py', 'tests/api/test_api.py',
             '-v', '--tb=short'],
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"⚠️  Could not run pytest: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  Jeevn MVP - System Validation")
    print("="*60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Required Packages", check_required_packages),
        ("Optional Packages", check_optional_packages),
        ("Module Imports", check_imports),
        ("File Structure", check_file_structure),
        ("Syntax Check", run_syntax_check),
        ("Database", check_database),
        ("Unit Tests", run_unit_tests),
    ]
    
    results = {}
    for name, check in checks:
        try:
            results[name] = check()
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            results[name] = False
    
    # Summary
    print_section("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if all(results.values()):
        print("\n✅ All checks passed! You're ready to go.")
        print("\nNext steps:")
        print("  1. Local: uvicorn jeevn.api.app:app --reload --app-dir src")
        print("  2. UI: streamlit run src/jeevn/ui/app.py")
        print("  3. Docker: docker compose -f infra/docker-compose.example.yml up -d")
        return 0
    else:
        print("\n❌ Some checks failed. See above for details.")
        print("\nFor help, see QUICKSTART.md")
        return 1

if __name__ == "__main__":
    sys.exit(main())
