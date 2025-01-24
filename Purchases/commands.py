import json
import os
import discord
from discord.ext import commands
import requests


import requests

def send_webhook(webhook_url, item_name, user_id, amount, bot_token):
    user_info = get_user_info(user_id, bot_token)
    if user_info is None:
        print("Failed to fetch user details. Sending with user ID instead.")
        user_name = user_id
    else:
        user_name = f"{user_info['username']}#{user_info['discriminator']}"

    data = {
        "username": "Store Bot",
        "embeds": [
            {
                "title": "New Purchase",
                "description": f"**Item:** {item_name}\n**User:** {user_name}\n**Amount:** ${amount:.2f}",
                "color": 3447003
            }
        ]
    }

    # Send the webhook
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        print("Webhook sent successfully!")
    else:
        print(f"Failed to send webhook: {response.status_code}, {response.text}")

def get_user_info(user_id, bot_token):
    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    url = f"https://discord.com/api/v10/users/{user_id}"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch user info: {response.status_code}, {response.text}")
        return None

async def on_purchase(user_id, sku_id, bot):
	user = await bot.fetch_user(user_id)
	if user:
		try:
			await user.send(f"Thank you for supporting Spectra!")
			try:
				send_webhook(os.environ["WEBHOOK_URL"], "Spectra", user_id, 1.0, bot.user.bot_token)
			except:
				pass
		except discord.Forbidden:
			pass

class Purchases(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener()
	async def on_socket_raw_receive(self, payload):
		if isinstance(payload, bytes):
			payload = payload.decode('utf-8')
		event_data = json.loads(payload)
		
		if event_data.get("t") == "ENTITLEMENT_CREATE":
			entitlement = event_data.get("d", {})
			user_id = entitlement.get("user_id")
			sku_id = entitlement.get("sku_id")
			
			await on_purchase(user_id, sku_id, self.bot)

async def setup(bot):
	await bot.add_cog(Purchases(bot))