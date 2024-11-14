import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# 環境変数からトークンを読み込む（セキュリティ向上）
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# インテントの定義
intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True  # 必要に応じてTrueに設定

# ボットの初期化
bot = commands.Bot(command_prefix='!', intents=intents)

# LoLのロール定義
LOL_ROLES = ["TOP", "JG", "MID", "ADC", "SUP"]

# サーバーごとの前回選ばれたメンバーのIDを保持する辞書
selected_members_last_round = {}

# サーバーごとの最後にselectコマンドが実行された時間を保持する辞書
last_select_time = {}

# モックメンバーを使用するヘルパー関数
def get_mock_members():
    members = []
    for i in range(5):
        mock_member = discord.Object(id=1234567890 + i)
        mock_member.display_name = f"テストメンバー{i + 1}"
        members.append(mock_member)
    return members

# コマンド1: ランダムに2チームに分ける
@bot.tree.command(name="team", description="Leagueチャンネルのメンバーをランダムに2チームに分けます。")
async def team(interaction: discord.Interaction):
    await interaction.response.defer()

    # ボイスチャンネルのメンバーを取得（テスト用にモックメンバーを使用）
    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else get_mock_members()

    # 「League」チャンネルでのみ実行可能に設定
    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if len(members) < 2:
        await interaction.followup.send("チームに分けるには、2人以上のメンバーが必要です。")
        return

    random.shuffle(members)
    midpoint = len(members) // 2
    team1 = members[:midpoint]
    team2 = members[midpoint:]

    team1_names = ", ".join([m.display_name for m in team1])
    team2_names = ", ".join([m.display_name for m in team2])

    embed = discord.Embed(title="チーム分け", color=discord.Color.blue())
    embed.add_field(name="チーム1", value=team1_names, inline=False)
    embed.add_field(name="チーム2", value=team2_names, inline=False)

    await interaction.followup.send(embed=embed)

# コマンド2: 指定人数のメンバーを選ぶ（前回選ばれたメンバーを除外）
@bot.tree.command(name="select", description="Leagueチャンネルから指定した人数のメンバーを選びます。")
@app_commands.describe(count="選ぶ人数")
async def select(interaction: discord.Interaction, count: int):
    global selected_members_last_round, last_select_time
    await interaction.response.defer()

    guild_id = interaction.guild.id  # サーバーごとに管理

    # ボイスチャンネルのメンバーを取得（テスト用にモックメンバーを使用）
    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else get_mock_members()

    # 「League」チャンネルでのみ実行可能に設定
    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if count > len(members):
        await interaction.followup.send(f"{count}人を選ぶことはできません。現在のメンバー数は {len(members)} 人です。")
        return

    # サーバーごとの選択状態を初期化
    if guild_id not in selected_members_last_round:
        selected_members_last_round[guild_id] = set()
        last_select_time[guild_id] = datetime.utcnow()

    # 前回選ばれたメンバーのIDを取得
    last_selected = selected_members_last_round[guild_id]

    # 前回選ばれたメンバーを除外してeligible_membersを定義
    eligible_members = [m for m in members if m.id not in last_selected]

    # デバッグ: eligible_membersとlast_selectedを確認
    eligible_names = ", ".join([m.display_name for m in eligible_members])
    last_round_names = ", ".join([m.display_name for m in members if m.id in last_selected])
    debug_message = f"デバッグ情報:\n前回選ばれたメンバー (last_selected): {last_round_names}\n選択可能なメンバー (eligible_members): {eligible_names}"
    await interaction.followup.send(debug_message)  # デバッグメッセージを送信

    # eligible_membersが空である場合、全員を対象にリセット
    if not eligible_members:
        eligible_members = members
        debug_message += "\neligible_members が空だったため、全メンバーを再度対象とします。"
        await interaction.followup.send("全メンバーを再度対象とします。")  # リセットの通知

    if len(eligible_members) >= count:
        # eligible_membersから指定人数をランダムに選択
        selected = random.sample(eligible_members, count)
    else:
        # eligible_members全員と、残りを全メンバーからランダムに選択
        remaining_count = count - len(eligible_members)
        remaining_members = [m for m in members if m.id in last_selected]
        selected = eligible_members + random.sample(remaining_members, remaining_count)

    # 選ばれたメンバーのIDを更新
    selected_members_last_round[guild_id] = set(m.id for m in selected)
    last_select_time[guild_id] = datetime.utcnow()  # 最後の選択時間を更新
    selected_names = ", ".join([m.display_name for m in selected])

    embed = discord.Embed(title="選ばれたメンバー", color=discord.Color.green())
    embed.add_field(name="メンバー", value=selected_names, inline=False)

    await interaction.followup.send(embed=embed)

# コマンド3: LoLのロールを割り当てる
# コマンド3: LoLのロールを割り当てる
@bot.tree.command(name="role", description="LeagueチャンネルのメンバーにLoLのロールを割り当てます。")
@app_commands.describe(roles="カンマ区切りのLoLロール（例：TOP,JG,MID,ADC,SUP）。指定がない場合はすべてのロールから割り当て")
async def role(interaction: discord.Interaction, roles: str = None):
    await interaction.response.defer()

    # ボイスチャンネルのメンバーを取得（テスト用にモックメンバーを使用）
    members = interaction.user.voice.channel.members if interaction.user.voice and interaction.user.voice.channel else get_mock_members()

    # 「League」チャンネルでのみ実行可能に設定
    if interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel.name != "League":
        await interaction.followup.send("このコマンドは「League」チャンネルでのみ使用できます。")
        return

    if len(members) > 5:
        await interaction.followup.send("このコマンドは5人以下のメンバーでのみ使用できます。現在のメンバー数は {} 人です。".format(len(members)))
        return

    # 役割が指定されていない場合、すべてのロールから割り当てる
    if not roles:
        roles_list = LOL_ROLES[:len(members)]
    else:
        roles_list = [role.strip().upper() for role in roles.split(",")]

    if len(roles_list) != len(members):
        await interaction.followup.send(f"提供されたロール数（{len(roles_list)}）がメンバー数（{len(members)}）と一致しません。")
        return

    # ロールのランダム化
    random.shuffle(roles_list)

    # ロールをメンバーに割り当て
    embed = discord.Embed(title="LoLロールの割り当て", color=discord.Color.purple())
    for member, role_name in zip(members, roles_list):
        if role_name not in LOL_ROLES:
            embed.add_field(name=member.display_name, value=f"無効なロール: {role_name}", inline=False)
            continue
        embed.add_field(name=member.display_name, value=role_name, inline=False)

    await interaction.followup.send(embed=embed)


# コマンド4: 選択履歴をリセットする（全ユーザー用）
@bot.tree.command(name="reset_selection", description="選択履歴をリセットします。")
async def reset_selection(interaction: discord.Interaction):
    global selected_members_last_round, last_select_time
    guild_id = interaction.guild.id

    # デバッグメッセージを送信
    await interaction.response.defer(ephemeral=True)
    print(f"{datetime.utcnow()} - reset_selection コマンドが {interaction.user} によって実行されました。")

    if guild_id in selected_members_last_round:
        selected_members_last_round[guild_id].clear()
    if guild_id in last_select_time:
        del last_select_time[guild_id]

    # ログに記録
    print(f"{datetime.utcnow()} - {interaction.user} が Guild ID {guild_id} の選択履歴をリセットしました。")

    await interaction.followup.send("選択履歴をリセットしました。", ephemeral=True)

# 背景タスク: 1.5時間の非操作後に選択履歴をリセット
@tasks.loop(minutes=5)  # 5分ごとに実行
async def auto_reset_selection():
    current_time = datetime.utcnow()
    reset_guilds = []

    for guild_id, last_time in list(last_select_time.items()):
        if current_time - last_time >= timedelta(hours=1, minutes=30):  # 1.5時間
            reset_guilds.append(guild_id)

    for guild_id in reset_guilds:
        selected_members_last_round[guild_id].clear()
        del last_select_time[guild_id]
        # ここで、必要に応じてログを出力
        print(f"{datetime.utcnow()} - Guild ID {guild_id} の選択履歴を自動リセットしました。")

# コマンドの同期および背景タスクの開始
@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)}個のコマンドを同期しました。')
    except Exception as e:
        print(f'コマンドの同期に失敗しました: {e}')
    auto_reset_selection.start()  # 自動リセットタスクを開始

# ボットの起動
bot.run(TOKEN)
