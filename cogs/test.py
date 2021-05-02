import requests

url = "https://discord.com/api/guilds/764920308846035014/members?limit=1000"
headers = {"Authorization": "Bot Nzk1NjY0ODYxMzMzNTUzMjIz.X_MqpQ.uHQdgjW4AyCV9DWtnvCbywYen2g"}

req = requests.get(url, headers=headers)

print(req.text)
