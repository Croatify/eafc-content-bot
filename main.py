import os
import sys
import re
import asyncio
import discord
from discord.ext import commands, tasks

def yesno(v): return "✅" if v else "❌"

# Read raw env (do NOT cast yet)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
ROLE_MENTION = os.getenv("ROLE_MENTION")
GUILD_ID_RAW = os.getenv("GUILD_ID")

# Trim whitespace just in case
if CHANNEL_ID_RAW: CHANNEL_ID_RAW = CHANNEL_ID_RAW.strip()
if GUILD_ID_RAW:   GUILD_ID_RAW   = GUILD_ID_RAW.strip()
if ROLE_MENTION:   ROLE_MENTION   = ROLE_MENTION.strip()
if DISCORD_TOKEN:  DISCORD_TOKEN  = DISCORD_TOKEN.strip()

print("==== ENV CHECK ====")
print(f"DISCORD_TOKEN present: {yesno(bool(DISCORD_TOKEN))}")
print(f"CHANNEL_ID present:   {yesno(bool(CHANNEL_ID_RAW))}  value={CHANNEL_ID_RAW!r}")
print(f"ROLE_MENTION present: {yesno(bool(ROLE_MENTION))}    value={ROLE_MENTION!r}")
print(f"GUILD_ID present:     {yesno(bool(GUILD_ID_RAW))}    value={GUILD_ID_RAW!r}")
print("====================")

missing = []
if not DISCORD_TOKEN: missing.append("DISCORD_TOKEN")
if not CHANNEL_ID_RAW: missing.append("CHANNEL_ID")
if not ROLE_MENTION: missing.append("ROLE_MENTION")
if not GUILD_ID_RAW: missing.append("GUILD_ID")

if missing:
    print(f"❌ Missing environment variables: {', '.join(missing)}")
    print("➡️  Add them in Railway → Service → Variables, then Redeploy.")
    sys.exit(1)

# Safe cast after validation
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    print("❌ CHANNEL_ID and GUILD_ID must be numbers only (no quotes/spaces).")
    print(f"CHANNEL_ID_RAW={CHANNEL_ID_RAW!r}  GUILD_ID_RAW={GUILD_ID_RAW!r}")
    sys.exit(1)

# ===== Bot setup =====
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_seen_tweet_id = None

def extract_6pm_content(text: str) -> str | None:
    m = re.match(r"^🚨\s*6pm\s*Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

@tasks.loop(minutes=2)
async def check_for_tweets():
    global last_seen_tweet_id
    await bot.wait_until_ready()

    try:
        import snscrape.modules.twitter as sntwitter
    except Exception as e:
        print(f"❌ snscrape not available: {e}")
        return

    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"❌ Could not resolve CHANNEL_ID={CHANNEL_ID}. Is the bot in that server?")
            return

        scraper = sntwitter.TwitterUserScraper("FUTBIN")
        count = 0
        async for tweet in scraper.get_items():
            if count >= 10:
                break
            count += 1

            content = tweet.content or ""
            if content.startswith("🚨 6pm Content:"):
                if last_seen_tweet_id != tweet.id:
                    last_seen_tweet_id = tweet.id
                    cleaned = extract_6pm_content(content) or content
                    msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
                    await channel.send(msg[:2000])
                    print("✅ Posted new 6pm content.")
                else:
                    print("ℹ️ 6pm content already posted.")
                break
        else:
            print("🔍 No matching 6pm Content tweet found.")

    except Exception as e:
        print(f"Error checking tweets: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def setup_hook():
    # Instant slash commands if GUILD_ID is set
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Synced {len(synced)} slash command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    check_for_tweets.start()

@bot.command(name="ping")
async def ping_prefix(ctx: commands.Context):
    await ctx.send("🏓 Pong! Bot is online (prefix).")

@bot.tree.command(name="ping", description="Check if the bot is alive (slash)")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send("🏓 Pong! Bot is online (slash).")

async def main():
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())


















    
















