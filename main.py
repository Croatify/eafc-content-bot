import os
import sys
import re
import asyncio
import time
import requests
import discord
from discord.ext import commands, tasks

def yesno(v): return "✅" if v else "❌"

# ---------- ENV ----------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
ROLE_MENTION = os.getenv("ROLE_MENTION")
GUILD_ID_RAW = os.getenv("GUILD_ID")

# Optional: overrideable Nitter instance for fallback
NITTER_URL = os.getenv("NITTER_URL", "https://nitter.net").rstrip("/")

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

# ---------- BOT ----------
intents = discord.Intents.default()
intents.message_content = True  # for prefix command
bot = commands.Bot(command_prefix="!", intents=intents)

last_seen_tweet_id = None

def extract_6pm_content(text: str) -> str | None:
    m = re.match(r"^🚨\s*6pm\s*Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None

def fetch_via_nitter() -> tuple[str | None, str | None]:
    """
    Fallback: fetch FUTBIN RSS via Nitter and return (tweet_id, full_text) for the latest
    '🚨 6pm Content:' post if present.
    """
    try:
        rss_url = f"{NITTER_URL}/FUTBIN/rss"
        resp = requests.get(rss_url, timeout=15)
        if resp.status_code != 200:
            print(f"⚠ Nitter RSS status {resp.status_code}")
            return None, None

        # Very light parse (avoid extra deps). Look for <item> blocks.
        text = resp.text
        items = text.split("<item>")
        for raw in items[1:10]:  # check first ~9 items
            # extract title/description/link/guid quickly
            def tag(name):
                start = raw.find(f"<{name}>")
                end   = raw.find(f"</{name}>")
                if start == -1 or end == -1: return ""
                return raw[start+len(name)+2:end].strip()

            title = tag("title")
            desc  = tag("description")
            link  = tag("link")  # often something like nitter.net/FUTBIN/status/123...
            guid  = tag("guid")

            body = title or desc or ""
            if body.startswith("🚨 6pm Content:"):
                # crude ID: take the last number in link/guid
                m = re.search(r"/status/(\d+)", link or guid or "")
                tweet_id = m.group(1) if m else (guid or link or "")
                return tweet_id, body
        return None, None
    except Exception as e:
        print(f"⚠ Nitter fallback failed: {e}")
        return None, None

@tasks.loop(minutes=2)
async def check_for_tweets():
    """Try snscrape first; if that import fails, use Nitter RSS fallback."""
    global last_seen_tweet_id
    await bot.wait_until_ready()

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"❌ Could not resolve CHANNEL_ID={CHANNEL_ID}. Is the bot in that server and can it view the channel?")
        return

    # Try snscrape
    used_fallback = False
    try:
        import snscrape.modules.twitter as sntwitter  # type: ignore
        scraper = sntwitter.TwitterUserScraper("FUTBIN")
        count = 0
        async for tweet in scraper.get_items():
            if count >= 10:
                break
            count += 1

            text = tweet.content or ""
            if text.startswith("🚨 6pm Content:"):
                tw_id = str(tweet.id)
                if last_seen_tweet_id != tw_id:
                    last_seen_tweet_id = tw_id
                    cleaned = extract_6pm_content(text) or text
                    msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
                    await channel.send(msg[:2000])
                    print("✅ Posted new 6pm content (snscrape).")
                else:
                    print("ℹ️ 6pm content already posted (snscrape).")
                return
        else:
            print("🔍 No matching 6pm Content tweet found (snscrape).")
            return
    except Exception as e:
        print(f"❌ snscrape import/usage failed: {e}")
        used_fallback = True

    if used_fallback:
        tw_id, body = fetch_via_nitter()
        if body and body.startswith("🚨 6pm Content:"):
            if last_seen_tweet_id != tw_id:
                last_seen_tweet_id = tw_id
                cleaned = extract_6pm_content(body) or body
                msg = f"{ROLE_MENTION}\n**6pm Content:**\n\n{cleaned}"
                await channel.send(msg[:2000])
                print("✅ Posted new 6pm content (Nitter fallback).")
            else:
                print("ℹ️ 6pm content already posted (Nitter fallback).")
        else:
            print("🔍 No matching 6pm Content tweet found (fallback).")

# ----- events & commands -----
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

# Register the slash command at module load (guild-scoped) so sync will see it
@bot.tree.command(name="ping", description="Check if the bot is alive (slash)", guild=GUILD)
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send("🏓 Pong! Bot is online (slash).")

@bot.event
async def setup_hook():
    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Synced {len(synced)} slash command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

    # Prefix command too
    @bot.command(name="ping", help="Check if the bot is alive (prefix: !ping)")
    async def ping_prefix(ctx: commands.Context):
        await ctx.send("🏓 Pong! Bot is online (prefix).")

    check_for_tweets.start()

async def main():
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())














    
















