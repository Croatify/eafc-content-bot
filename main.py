import os
import re
import asyncio
import discord
from discord.ext import commands, tasks

# ====== ENV ======
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ROLE_MENTION = os.getenv("ROLE_MENTION")  # e.g. "<@&1397029826568781997>"
GUILD_ID = os.getenv("GUILD_ID")          # optional: your server ID as string for instant slash sync

# ====== INTENTS / BOT ======
intents = discord.Intents.default()
intents.message_content = True  # needed for prefix commands like !ping
import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import os
import re
import asyncio
import time

# ================================
# Load environment variables
# ================================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ROLE_MENTION = os.getenv("ROLE_MENTION")
GUILD_ID = os.getenv("GUILD_ID")

# Check for missing variables
missing_vars = []
if not DISCORD_TOKEN:
    missing_vars.append("DISCORD_TOKEN")
if not CHANNEL_ID:
    missing_vars.append("CHANNEL_ID")
if not ROLE_MENTION:
    missing_vars.append("ROLE_MENTION")
if not GUILD_ID:
    missing_vars.append("GUILD_ID")

if missing_vars:
    raise ValueError(f"❌ Missing environment variables: {', '.join(missing_vars)}")

# Convert numeric IDs
CHANNEL_ID = int(CHANNEL_ID)
GUILD_ID = int(GUILD_ID)

# ================================
# Discord bot setup
# ================================
intents = discord.Intents.default()
intents.message_content = True  # Needed for commands

bot = commands.Bot(command_prefix="/", intents=intents)

# ================================
# FUTBIN scrape settings
# ================================
URL = "https://x.com/FUTBIN/with_replies"
last_seen_tweet = None

def extract_6pm_content(text):
    """Extracts everything after '🚨 6pm Content:' from a tweet."""
    match = re.match(r"🚨 6pm Content:(.*)", text, re.DOTALL)
    return match.group(1).strip() if match else None

async def check_for_new_content():
    """Checks FUTBIN's tweets every 2 minutes for new 6pm Content."""
    global last_seen_tweet
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    while True:
        try:
            import snscrape.modules.twitter as sntwitter
            tweets = list(sntwitter.TwitterUserScraper("FUTBIN").get_items())

            for tweet in tweets:
                if tweet.content.startswith("🚨 6pm Content:"):
                    if tweet.id != last_seen_tweet:
                        last_seen_tweet = tweet.id
                        content = extract_6pm_content(tweet.content)
                        message = f"{ROLE_MENTION}\n**6pm Content:**\n\n{content}"
                        await channel.send(message[:2000])
                    break

        except Exception as e:
            print(f"⚠ Error checking tweets: {e}")

        await asyncio.sleep(120)  # Check every 2 minutes

# ================================
# Bot events & commands
# ================================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    bot.loop.create_task(check_for_new_content())

@bot.command(name="ping")
async def ping(ctx):
    """Test command to see if bot is responding."""
    await ctx.send("🏓 Bot is online!")

# ================================
# Run bot
# ================================
async def start_bot():
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(start_bot())
        except Exception as e:
            print(f"⚠ Bot loop error: {e}")
        print("🔄 Restarting bot in 5 seconds...")
        time.sleep(5)



















    
















