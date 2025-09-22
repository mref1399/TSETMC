import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BRSAPI_KEY')

url = f"https://BrsApi.ir/Api/Tsetmc/AllSymbols.php?key={api_key}"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Accept": "application/json, text/plain, */*"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Found {len(data)} symbols")
    print("First 3 symbols:")
    for symbol in data[:3]:
        print(f"  - {symbol}")
else:
    print(f"❌ Error: {response.status_code}")
    print(f"Response: {response.text}")
