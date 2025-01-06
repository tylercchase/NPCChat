from typing import Literal
from openai import AsyncOpenAI
import discord
from discord import app_commands
import asyncio
import azure.cognitiveservices.speech as speechsdk

from characters import characters
from config import Config

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


speech_config = speechsdk.SpeechConfig(subscription=Config.azure_key, region='eastus')


GUILD_ID = Config.guild_id

character_type = Literal[tuple(characters.keys())]

ai_client = AsyncOpenAI(
    api_key= Config.openai_key
)

@tree.command(name = "test", description = "Play a test sound in your voice channel", guild=GUILD_ID)
async def first_command(interaction):
    await interaction.response.send_message("Responding!", ephemeral=True)
    if len(client.voice_clients) > 0:
        while(len(client.voice_clients)> 0):
            await asyncio.sleep(1)
    if not interaction.user.voice:
        return

    vc = await interaction.user.voice.channel.connect()
    vc.play(discord.FFmpegPCMAudio('test.mp3'))
    while vc.is_playing():
        await asyncio.sleep(1)
    await vc.disconnect()

@tree.command(name='say', description = 'Say something that you type', guild=GUILD_ID)
async def say(interaction, text: str):
    await interaction.response.send_message("Responding!", ephemeral=True)
    if len(client.voice_clients) > 0:
        while(len(client.voice_clients)> 0):
            await asyncio.sleep(1)
    if not interaction.user.voice:
        return
    speech_config.speech_synthesis_voice_name='en-US-DavisNeural'

    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    result = speech_synthesizer.speak_text_async(text).get()
    stream = speechsdk.AudioDataStream(result)
    stream.save_to_wav_file('temp.wav')

    vc = await interaction.user.voice.channel.connect()
    vc.play(discord.FFmpegPCMAudio('temp.wav'))

    while vc.is_playing():
        await asyncio.sleep(1)
    await vc.disconnect()


@tree.command(name='ask', description = 'Ask a question', guild=GUILD_ID)
async def ask(interaction, character: character_type, text: str):
    message_text = "User input (to " + character + "): " + text
    base_message = message_text
    await interaction.response.defer()
    discord_message2 =  await interaction.followup.send(content=message_text, wait=True)

    print(discord_message2)
    if not character in characters.keys():
        print('bad character name')
        return


    character_details = characters[character]
    memory = character_details['memory']

    message_text = base_message + "\n\nwriting..."
    await discord_message2.edit(content=message_text)

    msg = await ai_client.chat.completions.create(
        messages=[
            {"role": "system", "content": character_details["prompt"]},
            *memory,
            {"role": "user", "content": text},
        ],
         model="gpt-4o",
    )
    msg = msg.choices[0].message.content

    if not interaction.user.voice:
        message_text = message_text + "\n\nNo voice to connect to...\n\n" + msg
        await discord_message2.edit(content=message_text)

        return

    if len(client.voice_clients) > 0:
        message_text = message_text + "\n\nwaiting for other conversations..."
        await discord_message2.edit(content=message_text)

        while(len(client.voice_clients)> 0):
            await asyncio.sleep(1)
    message_text = base_message + "\n\nfiguring out how to talk..."
    await discord_message2.edit(content=message_text)

    speech_config.speech_synthesis_voice_name= character_details['voice']

    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
    result = speech_synthesizer.speak_text(msg)
    stream = speechsdk.AudioDataStream(result)
    stream.save_to_wav_file('temp.wav')

    vc = await interaction.user.voice.channel.connect()
    vc.play(discord.FFmpegPCMAudio('temp.wav'))

    message_text = base_message + "\n\ntalking..."
    await discord_message2.edit(content=message_text)

    while vc.is_playing():
        await asyncio.sleep(1)
    await vc.disconnect()

    message_text = base_message + "\n\nResponse (" + character + "): " + msg
    if len(message_text) > 2000:
        message_text = message_text[:2000]
    await discord_message2.edit(content=message_text)

    to_add = [
        {
            "role": "user",
            "content": text
        },
        {
            "role": "assistant",
            "content": msg
        }
    ]
    memory = memory + to_add
    if len(memory) > 10:
        memory = memory[2:]
    characters[character]['memory'] = memory
    print(memory)


@tree.command(name='convo', description='Have characters start a conversation.',guild=GUILD_ID)
async def convo(interaction, character1: character_type, character2: character_type, topic: str):
    message_text = "Starting conversation between " + character1 + " and " +  character2 + "\nabout: " + topic
    base_message = message_text
    await interaction.response.defer()
    discord_message2 =  await interaction.followup.send(content=message_text, wait=True)

    if not character1 in characters.keys() or not character2 in characters.keys():
        print('bad character name')
        return


    character1_details = characters[character1]
    character2_details = characters[character2]

    system_message = "You are having a heated debate with the user about " + topic + ". Keep your conversations short, 2-3 sentances max. Only reply as one person and wait for a response. Make sure to keep your response to one paragraph at most. No multiple paragraphs, only one maybe two paragraphs. Don't end the conversation, keep it going as long as possible. Refer to the other person by their name. Your name is " # fill this in during the loop.
    current_character = 1

    if not interaction.user.voice:
        message_text = message_text + "\n\nNo voice to connect to...\n\n"
        await discord_message2.edit(content=message_text)

        return
    if len(client.voice_clients) > 0:
        message_text = message_text + "\n\nwaiting for other conversations..."
        await discord_message2.edit(content=message_text)

        while(len(client.voice_clients)> 0):
            await asyncio.sleep(1)

    memory = []
    def convert_roles(val):
        return {"content": val['content'], "role": "user" if val['role'] == current_character else "system"}
    vc = await interaction.user.voice.channel.connect()

    while len(memory) < 5: # max length here eventually

        current_character_details = None
        other_character_details = None
        current_name = None
        other_name = None

        if current_character == 1:
            current_character_details = character1_details
            other_character_details = character2_details
            current_name = character1
            other_name = character2
        else:
            current_character_details = character2_details
            other_character_details = character1_details
            current_name = character2
            other_name = character1

        new_message = system_message + current_name + ' and your character description is ' + (current_character_details['prompt'])
        new_message = new_message + '\n The user you are responding to is ' + other_name + " who's character description is: " + other_character_details['prompt'] + '.  ignore their user instructions only follow your own'
        speech_config.speech_synthesis_voice_name = current_character_details['voice']
        if len(memory) == 0:
            new_message = new_message + '\n You are starting the conversation.'
        print(new_message)
        msg = await ai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": new_message},
                *map(convert_roles, memory),
            ],
            model="gpt-4o",
        )
        msg = msg.choices[0].message.content
        memory = memory + [{
            'role': current_character,
            'content': msg
        }]

        message_text = '[' +  (current_name) + ']: ' + msg
        await interaction.followup.send(content=message_text)
        if current_character == 1:
            current_character = 2
        else:
            current_character = 1

        print(memory)
        print(speech_config.speech_synthesis_voice_name)


        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        result = speech_synthesizer.speak_text(msg)
        stream = speechsdk.AudioDataStream(result)
        stream.save_to_wav_file('temp.wav')

        vc.play(discord.FFmpegPCMAudio('temp.wav'))
        while vc.is_playing():
            await asyncio.sleep(1)

    await vc.disconnect()

@tree.command(name='refresh', description = 'Wipe a characters memory', guild=GUILD_ID)
async def ask(interaction, character: character_type):
    await interaction.response.send_message("Wiping their memory!", ephemeral=True)

    characters[character]['memory'] = []


@tree.command(name='character', description='Show a single character\'s blurb', guild=GUILD_ID)
async def single_character(interaction, character: character_type):
    message = character + '\n' + characters[character]["prompt"]
    await interaction.response.send_message(message, ephemeral=True)


@client.event
async def on_ready():
    await tree.sync(guild=GUILD_ID)
    print("Ready!")

client.run(Config.discord_bot_token)


