import discord
from discord.ext import commands
from discord import app_commands
import random
import os
from flask import Flask
from threading import Thread

TOKEN = os.getenv('TOKEN')

if TOKEN is None:
    raise ValueError("DISCORD_BOT_TOKENが設定されていません。")

# インテントの定義
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True 

# ボットの初期化
bot = commands.Bot(command_prefix='!', intents=intents)

# ロールの定義
ROLES = ["TOP", "JG", "MID", "ADC", "SUP"]

def get_league_members(guild):
    """Leagueチャンネルに接続しているメンバーを取得"""
    league_channel = discord.utils.get(guild.voice_channels, name="League")
    if league_channel:
        return league_channel.members
    return []

def search_members(members, query):
    """メンバー名を部分一致で検索"""
    if not query:
        return members
    return [member for member in members if query.lower() in member.display_name.lower()]

@bot.tree.command(name="select", description="指定された人数を選択します")
@app_commands.describe(
    exclude_num="除外する人数（数字、必須項目）",
    member_name="メンバー名（部分一致、省略可）"
)
async def select(interaction: discord.Interaction, exclude_num: int, member_name: str = None):
    await interaction.response.defer()

    all_members = get_league_members(interaction.guild)
    selected_members = search_members(all_members, member_name)

    if exclude_num >= len(selected_members):
        await interaction.followup.send("❌ **エラー**: 除外する人数がメンバー数以上です。")
        return

    final_members = random.sample(selected_members, len(selected_members) - exclude_num)
    member_names = '\n'.join([f"- {member.display_name}" for member in final_members])

    embed = discord.Embed(
        title="🎯 選ばれたメンバー",
        description=member_names,
        color=discord.Color.green()
    )
    embed.set_footer(text=f"除外人数: {exclude_num} | 検索クエリ: {member_name or 'なし'}")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="role", description="LoLのロール割り当て")
@app_commands.describe(
    member_name="メンバー名（部分一致、カンマ区切り）",
    role="ロール（部分一致、カンマ区切り）"
)
async def assign_role(interaction: discord.Interaction, member_name: str = None, role: str = None):
    await interaction.response.defer()

    all_members = get_league_members(interaction.guild)
    selected_members = search_members(all_members, member_name)

    num_members = len(selected_members)

    if num_members == 0:
        await interaction.followup.send("❌ **エラー**: Leagueチャンネルに接続しているメンバーがいません。")
        return

    roles_assigned = {}

    if not role:
        # ロールが指定されていない場合
        if num_members <= 3:
            available_roles = ["TOP", "JG", "MID"]
            if num_members > len(available_roles):
                await interaction.followup.send("❌ **エラー**: メンバー数がロールの数を超えています。重複なしで割り当てることができません。")
                return
            random.shuffle(available_roles)
            for member, assigned_role in zip(selected_members, available_roles):
                roles_assigned[member.display_name] = assigned_role
        elif num_members == 4:
            adc_sup = random.choice(["ADC", "SUP"])
            available_roles = ["TOP", "JG", "MID"]
            random.shuffle(available_roles)
            roles_assigned[selected_members[0].display_name] = adc_sup
            for member, assigned_role in zip(selected_members[1:], available_roles):
                roles_assigned[member.display_name] = assigned_role
        elif num_members == 5:
            shuffled_roles = ROLES.copy()
            random.shuffle(shuffled_roles)
            for member, assigned_role in zip(selected_members, shuffled_roles):
                roles_assigned[member.display_name] = assigned_role
        else:
            await interaction.followup.send("❌ **エラー**: 対応していないメンバー数です。")
            return
    else:
        # ロールが指定されている場合
        input_roles = [r.strip().upper() for r in role.split(',')]
        unique_roles = list(dict.fromkeys(input_roles))

        if len(unique_roles) < num_members:
            await interaction.followup.send("❌ **エラー**: 指定されたロールの数がメンバー数に足りません。")
            return

        random.shuffle(unique_roles)
        for member, assigned_role in zip(selected_members, unique_roles):
            roles_assigned[member.display_name] = assigned_role

    # 結果をフォーマットして送信
    role_messages = '\n'.join([f"- **{name}**: {role}" for name, role in roles_assigned.items()])
    embed = discord.Embed(
        title="📜 ロール割り当て結果",
        description=role_messages,
        color=discord.Color.blue()
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="team", description="Leagueチャンネルのメンバーをランダムに2チームに分けます。")
async def team(interaction: discord.Interaction):
    await interaction.response.defer()

    members = get_league_members(interaction.guild)

    if len(members) < 2:
        await interaction.followup.send("❌ **エラー**: チームに分けるには、2人以上のメンバーが必要です。")
        return

    random.shuffle(members)
    midpoint = len(members) // 2
    team1 = members[:midpoint]
    team2 = members[midpoint:]

    team1_names = "\n".join([f"- {m.display_name}" for m in team1])
    team2_names = "\n".join([f"- {m.display_name}" for m in team2])

    embed = discord.Embed(
        title="⚔️ チーム分け結果",
        color=discord.Color.purple()
    )
    embed.add_field(name="**チーム1**", value=team1_names, inline=False)
    embed.add_field(name="**チーム2**", value=team2_names, inline=False)

    await interaction.followup.send(embed=embed)

@bot.event
async def on_ready():
    print(f'✅ ログインしました: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"✅ 同期したコマンド数: {len(synced)}")
    except Exception as e:
        print(f"❌ コマンドの同期中にエラーが発生しました: {e}")


app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run).start()

bot.run(TOKEN)
