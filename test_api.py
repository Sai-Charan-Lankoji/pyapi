import requests

# Since resume.pdf is in the same folder, we can just use the filename
pdf_path = "resume2.pdf"  

url = 'http://localhost:5000/'

with open(pdf_path, 'rb') as pdf_file:
    files = {'file': pdf_file}
    response = requests.post(url, files=files)

print(response.json())