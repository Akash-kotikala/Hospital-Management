import os
import sys
import subprocess

def main():
    print("==================================================")
    print("Starting Healthcare Platform in Local Mode")
    print("==================================================")
    
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    os.chdir(backend_dir)
    sys.path.insert(0, backend_dir)

    # 1. Run Alembic migrations
    print("\n[1/3] Running database migrations...")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    # 2. Seed database
    print("\n[2/3] Seeding demo hospitals, doctors, and patient accounts...")
    subprocess.run([sys.executable, "-m", "app.db.seed"], check=True)

    # 3. Start Uvicorn
    print("\n[3/3] Starting FastAPI server on http://localhost:8000 ...")
    print("Open http://localhost:8000/ in your browser for the full dashboard UI!")
    print("Open http://localhost:8000/docs for Swagger OpenAPI documentation.\n")
    
    import uvicorn
    # Use 127.0.0.1 locally so terminal links are directly clickable in Windows browsers
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()
