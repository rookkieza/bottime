import discord
import json
import os
from datetime import datetime, timezone

# ========== CONFIG ==========
TOKEN = "MTUxMTk5OTkyOTg0Mzg0NzE3OA.GmBuxm.UQFLpnAcO0AXMr6IfmTonJ1jYf-cjAW8_XVLT4"  # ใส่ Token บอทของคุณ
DATA_FILE = "voice_data.json"
# ============================

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

client = discord.Client(intents=intents)

# { "user_id": { "total_seconds": int, "joined_at": iso_str or null, "username": str } }
voice_data: dict = {}

# track คนที่กำลังอยู่ใน voice channel อยู่ตอนนี้
active_sessions: dict = {}  # { user_id: datetime }


# ---------- Helpers ----------

def load_data():
    global voice_data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            voice_data = json.load(f)
    else:
        voice_data = {}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(voice_data, f, ensure_ascii=False, indent=2)


def ensure_user(user: discord.Member):
    uid = str(user.id)
    if uid not in voice_data:
        voice_data[uid] = {
            "username": str(user),
            "total_seconds": 0,
        }
    else:
        # อัปเดตชื่อล่าสุด
        voice_data[uid]["username"] = str(user)


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h} ชม. {m} นาที {s} วินาที"
    elif m > 0:
        return f"{m} นาที {s} วินาที"
    else:
        return f"{s} วินาที"


def get_current_total(uid: str) -> int:
    """รวมเวลาสะสม + เวลา session ปัจจุบัน (ถ้ายังอยู่ใน voice)"""
    base = voice_data.get(uid, {}).get("total_seconds", 0)
    if uid in active_sessions:
        elapsed = (datetime.now(timezone.utc) - active_sessions[uid]).total_seconds()
        base += int(elapsed)
    return base


# ---------- Events ----------

@client.event
async def on_ready():
    load_data()

    # กู้คืน session ของคนที่อยู่ใน voice ตอนบอทเปิด
    now = datetime.now(timezone.utc)
    for guild in client.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot:
                    ensure_user(member)
                    active_sessions[str(member.id)] = now

    print(f"✅ บอทออนไลน์แล้ว: {client.user}")
    print(f"📂 โหลดข้อมูลจาก {DATA_FILE} สำเร็จ ({len(voice_data)} คน)")


@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return

    uid = str(member.id)
    now = datetime.now(timezone.utc)

    joined = before.channel is None and after.channel is not None
    left = before.channel is not None and after.channel is None

    if joined:
        ensure_user(member)
        active_sessions[uid] = now
        print(f"🎙️  {member} เข้า {after.channel.name}")

    elif left:
        ensure_user(member)
        if uid in active_sessions:
            elapsed = int((now - active_sessions.pop(uid)).total_seconds())
            voice_data[uid]["total_seconds"] += elapsed
            save_data()
            print(f"🔇 {member} ออก — session {format_duration(elapsed)}")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    content = message.content.strip()

    # ---------- !voice ----------
    if content.lower() == "!voice":
        uid = str(message.author.id)
        ensure_user(message.author)
        total = get_current_total(uid)

        status = "🎙️ กำลังอยู่ใน Voice" if uid in active_sessions else "🔇 ออกจาก Voice แล้ว"
        embed = discord.Embed(
            title="⏱️ เวลา Voice ของคุณ",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 ผู้ใช้", value=str(message.author), inline=False)
        embed.add_field(name="⏳ เวลาสะสม", value=format_duration(total), inline=False)
        embed.add_field(name="สถานะ", value=status, inline=False)
        await message.channel.send(embed=embed)

    # ---------- !voicetop ----------
    elif content.lower() == "!voicetop":
        if not voice_data:
            await message.channel.send("❌ ยังไม่มีข้อมูลเลย")
            return

        # รวม session ปัจจุบันด้วย
        ranking = []
        for uid, data in voice_data.items():
            total = get_current_total(uid)
            ranking.append((uid, data.get("username", uid), total))

        ranking.sort(key=lambda x: x[2], reverse=True)
        top = ranking[:10]

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, username, seconds) in enumerate(top):
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{medal} **{username}** — {format_duration(seconds)}")

        embed = discord.Embed(
            title="🏆 อันดับ Voice สะสม (Top 10)",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text="อัปเดตแบบ Real-time")
        await message.channel.send(embed=embed)


client.run(TOKEN)
