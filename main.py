import os
import sys
import re
import asyncio
import discord
from discord.ext import commands, tasks

def yesno(v): return "✅" if v else "❌"

# --- ENV ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
ROLE_MENTION = os.getenv("ROLE_MENTION")
GUILD_ID_RAW = os.getenv("GUILD_ID")

# Trim
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
    sys.exit(1)

# Cast IDs
try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
    GUILD_ID = int(GUILD_ID_RAW)
except ValueError:
    print("❌ CHANNEL_ID and GUILD_ID must be numbers only.")
    sys.exit(1)

GUILD = discord.Object(id=GUILD_ID)

# --- BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_seen_tweet_id = None

def extract_6pm_content(text: str) -> str | None:
    m = re.match(r"^🚨\s*6pm\s*Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

@tasks.loop(minutes=2)
async def check_for_tweets():
    """Poll @FUTBIN every 2 min and post if new 6pm tweet found."""
    global last_seen_tweet_id
    await bot.wait_until_ready()

    try:
        import snscrape.modules.twitter as sntwitter
    except Exception as e:
        print(f"❌ snscrape import failed: {e}")
        print("➡️  Ensure requirements.txt pins a working snscrape version and redeploy.")
        return

    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"❌ Could not resolve CHANNEL_ID={CHANNEL_ID}. Is the bot in that server and can it view the channel?")
            return

        scraper = sntwitter.TwitterUserScraper("FUTBIN")
        count = 0
        async for tweet in scraper.get_items():
            if count >= 10:
                break
            count += 1

            text = tweet.content or ""
            if text.startswith("🚨 6pm Content:"):
                if last_seen_tweet_id != tweet.id:
                    last_seen_tweet_id = tweet.id
                    cleaned = extract_6pm_content(text) or text
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
    # Register guild-scoped commands so they appear instantly
    try:
        # define the slash command BEFORE syncing
        @bot.tree.command(name="ping", description="Check if the bot is alive (slash)", guild=GUILD)
        async def ping_slash(interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.followup.send("🏓 Pong! Bot is online (slash).")

        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Synced {len(synced)} slash command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    # Also provide a prefix command
    @bot.command(name="ping", help="Check if the bot is alive (prefix: !ping)")
    async def ping_prefix(ctx: commands.Context):
        await ctx.send("🏓 Pong! Bot is online (prefix).")

    check_for_tweets.start()

async def main():
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())














    
















