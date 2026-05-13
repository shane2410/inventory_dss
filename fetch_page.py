import urllib.request
url='http://127.0.0.1:8000/forecast-monthly/'
print('Fetching',url)
resp=urllib.request.urlopen(url)
html=resp.read().decode('utf-8')
print(html[:4000])
