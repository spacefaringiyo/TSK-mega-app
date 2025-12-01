import urllib.request
from pathlib import Path

# The official TradingView Lightweight Charts library
URL = "https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"

# Path: Kovaaks_V2/modules/charts/lightweight-charts.js
DEST = Path(__file__).parent / "modules" / "charts" / "lightweight-charts.js"

print(f"Downloading library to: {DEST}...")

try:
    with urllib.request.urlopen(URL) as response:
        data = response.read()
        with open(DEST, 'wb') as f:
            f.write(data)
    print("Success! File saved.")
except Exception as e:
    print(f"Error: {e}")