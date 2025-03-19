import telegram
import asyncio

# Reemplaza 'TU_TOKEN_DEL_BOT' con el token de tu bot
TOKEN = '7635657147:AAE711ZReGbNmxTkYLp7tYvZd_ZThf9v_u8'

# Inicializar el bot de Telegram
bot = telegram.Bot(token=TOKEN)

# Enviar un mensaje al bot para obtener el ID del chat
async def obtener_id_chat():
    updates = await bot.get_updates()
    for update in updates:
        chat_id = update.message.chat_id
        print(f"ID del chat: {chat_id}")
        return chat_id

if __name__ == '__main__':
    asyncio.run(obtener_id_chat())