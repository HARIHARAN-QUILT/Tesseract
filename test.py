import base64
import requests

url="http://127.0.0.1:5000/api/document-analyze"

headers={
 "Content-Type":"application/json",
 "x-api-key":"sk_track2_987654321"
}

with open("sample.jpeg","rb") as f:
    b64=base64.b64encode(f.read()).decode()

payload={
 "fileName":"sample.jpeg",
 "fileType":"jpeg",
 "fileBase64":b64
}
r=requests.post(url,headers=headers,json=payload)
print(payload)
print("-------------------------------------------------------------------------------------------------------------------")

print(r.json())