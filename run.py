import uvicorn, os
from pathlib import Path
from dotenv import load_dotenv

# Her yerden çalıştırılsa da proje kökü doğru olsun
os.chdir(Path(__file__).parent)
load_dotenv()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
