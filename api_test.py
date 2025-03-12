import requests

response = requests.post(
    "http://localhost:8000/userQuery",
    json={"userInput": "Recommend some staking protocols for me, at least 5% APR."},
)

if response.status_code == 200:
    try:
        print(response.json())
    except requests.exceptions.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        print(f"Raw response: {response.text}")
else:
    print(f"Error: {response.status_code}")
    print(f"Response: {response.text}")
