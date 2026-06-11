import os
import json
import sys
import traceback
import requests
import pandas as pd
import vk_api
from API_ke import API
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

# ================= НАСТРОЙКИ =================
TOKEN = API  # Сюда вставь свой токен из Ключей Доступа
GROUP_ID = "239371469"         # Твой ID группы из скриншота
ADMIN_IDS = [12345678]         # Твой цифровой VK ID
EXCEL_FILENAME = "rating.xlsx" 
# =============================================

def create_keyboard():
    """Создание inline-клавиатуры, прикрепленной к сообщению"""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button('❓ Инструкция', color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def send_msg(user_id, text, use_keyboard=False):
    """Отправка сообщений через peer_id"""
    try:
        params = {
            'peer_id': user_id, 
            'message': text,
            'random_id': get_random_id()
        }
        if use_keyboard:
            params['keyboard'] = create_keyboard()
        else:
            params['keyboard'] = json.dumps({"buttons": [], "inline": True})
        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}", flush=True)

def get_applicant_rating(applicant_id):
    """Поиск мест абитуриента по 3 специальностям"""
    if not os.path.exists(EXCEL_FILENAME):
        return "Ошибка: База данных абитуриентов временно недоступна."
    try:
        df = pd.read_excel(EXCEL_FILENAME)
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        if 'номер' not in df.columns or 'место' not in df.columns or 'специальность' not in df.columns:
            return "⚠️ Ошибка: В таблице на сервере отсутствуют колонки 'Номер', 'Специальность' или 'Место'."
            
        df['номер'] = df['номер'].astype(str).str.strip()
        search_val = str(applicant_id).strip()
        results = df[df['номер'] == search_val]
        
        if not results.empty:
            response = "📊 Ваше текущее место в рейтингах:\n\n"
            for index, row in results.iterrows():
                spec = str(row['специальность']).strip()
                position = row['место']
                
                if pd.isna(position): 
                    pos_str = "не определено"
                elif isinstance(position, float) and position.is_integer(): 
                    pos_str = f"{int(position)} место"
                else: 
                    pos_str = f"{position} место"
                    
                response += f"🔹 {spec}: {pos_str}\n"
            return response
        return "Абитуриент с таким номером не найден в списках. Проверьте правильность ввода."
    except Exception as e:
        return f"Ошибка чтения базы данных Excel: {e}"

def handle_admin_file(user_id, message_obj):
    """Прием нового Excel-файла от администратора"""
    attachments = message_obj.get('attachments', [])
    if not attachments: 
        return False
    doc = attachments[0]
    if doc['type'] == 'doc' and doc['doc']['ext'] == 'xlsx':
        try:
            response = requests.get(doc['doc']['url'])
            temp = "temp_rating.xlsx"
            with open(temp, 'wb') as f: 
                f.write(response.content)
            
            df = pd.read_excel(temp)
            df.columns = df.columns.astype(str).str.strip().str.lower()
            
            if 'номер' not in df.columns or 'место' not in df.columns or 'специальность' not in df.columns:
                send_msg(user_id, "❌ Ошибка: В файле должны быть колонки 'Номер', 'Специальность', 'Место'. База НЕ обновлена.")
                os.remove(temp)
                return True
                
            if os.path.exists(EXCEL_FILENAME): 
                os.remove(EXCEL_FILENAME)
            os.rename(temp, EXCEL_FILENAME)
            send_msg(user_id, "✅ База данных успешно обновлена и проверена!")
            return True
        except Exception as e:
            send_msg(user_id, f"❌ Ошибка при обработке файла: {e}")
            return True
    return False

# Запуск основного процесса с ловушкой для вылетов
try:
    print("=== ЗАПУСК БОТА ===", flush=True)
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("✅ Бот успешно подключился к LongPoll и готов к работе!", flush=True)

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            message = event.obj.message
            user_id = message['from_id']
            text = message['text'].strip()
            
            # 1. Проверка на админский файл
            if user_id in ADMIN_IDS and handle_admin_file(user_id, message):
                continue
                
            # 2. Команды приветствия
            if text.lower() in ['привет', 'начать', 'start', '/start', '❓ инструкция']:
                send_msg(
                    user_id, 
                    "Приветствуем! Введите ваш уникальный номер абитуриента, чтобы узнать место в рейтинге по направлениям.", 
                    use_keyboard=True
                )
                continue
                
            # 3. Поиск номера в базе
            if text:
                res = get_applicant_rating(text)
                send_msg(user_id, res, use_keyboard=True)

except Exception as crash_error:
    print("\n🛑 БОТ ВЫЛЕТЕЛ С КРИТИЧЕСКОЙ ОШИБКОЙ! 🛑", flush=True)
    print("="*50, flush=True)
    traceback.print_exc(file=sys.stdout)
    print("="*50, flush=True)

finally:
    print("\nРабота скрипта завершена.", flush=True)
    input("Нажмите ENTER, чтобы закрыть окно терминала...")