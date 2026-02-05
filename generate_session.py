#!/usr/bin/env python3
"""
One-time script to generate a new Telethon session string.
Run this interactively - it will ask for your phone number and verification code.
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = "25298694"
API_HASH = "1a23ce55412c2ac111b6cef8ec5ad4b2"

async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.start()
    
    session_string = client.session.save()
    print("\n" + "=" * 60)
    print("✅ New session string generated!")
    print("=" * 60)
    print(f"\n{session_string}\n")
    print("=" * 60)
    print("Copy the string above and update app.py")
    
    await client.disconnect()

asyncio.run(main())
