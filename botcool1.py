import os
import vk_api
import json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import pandas as pd
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from dotenv import load_dotenv
import requests
from API_ke import API



# ================= НАСТРОЙКИ =================
TOKEN = API
GROUP_ID = "11111111"  
ADMIN_IDS = [1111111]
EXCEL_FILENAME = "rating.xlsx"
# =============================================

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)




def create_keyboard():
    """Создание inline-кнопок, которые крепятся к сообщению"""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button('❓ Инструкция', color=VkKeyboardColor.PRIMARY)
    # Возвращаем строку JSON, так как ВК требует именно её в актуальных версиях API
    return keyboard.get_keyboard()

def send_msg(user_id, text, use_keyboard=False):
    """Абсолютно надежная функция отправки сообщений с кнопками через peer_id"""
    try:
        params = {
            # Для ботов сообществ надежнее использовать peer_id вместо user_id
            'peer_id': user_id, 
            'message': text,
            'random_id': get_random_id()
        }
        
        if use_keyboard:
            params['keyboard'] = create_keyboard()
        else:
            # Если кнопки не нужны, принудительно очищаем клавиатуру (ВК это любит)
            params['keyboard'] = json.dumps({"buttons": [], "one_time": True})
            
        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

def send_msg(user_id, text):
    """Функция отправки текстового сообщения"""
    try:
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=get_random_id()
        )
    except Exception as e:
        print(f"Ошибка отправки сообщения пользователю {user_id}: {e}")

def get_applicant_rating(applicant_id):
    """Поиск места абитуриента в Excel-файле с защитой от ошибок"""
    if not os.path.exists(EXCEL_FILENAME):
        return "Ошибка: База данных абитуриентов временно недоступна. Попробуйте позже."
    
    try:
        # Читаем Excel
        df = pd.read_excel(EXCEL_FILENAME)
        
        # Шаг 1: Чистим названия колонок от пробелов и переводим в нижний регистр
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # Проверяем, есть ли нужные колонки (теперь ищем строго 'номер' и 'место')
        if 'номер' not in df.columns or 'место' not in df.columns:
            print(f"Ошибка: В Excel найдены только колонки: {list(df.columns)}")
            return "⚠️ Ошибка на сервере: Неверный формат таблицы. Убедитесь, что есть колонки 'Номер' и 'Место'."
        
        # Шаг 2: Приводим колонку с номерами к строкам и чистим пробелы
        df['номер'] = df['номер'].astype(str).str.strip()
        
        # Ищем совпадение
        search_val = str(applicant_id).strip()
        result = df[df['номер'] == search_val]
        
        if not result.empty:
            # Берем значение из колонки "место"
            position = result['место'].values[0]
            
            # Проверка на пустую ячейку (NaN)
            if pd.isna(position):
                return "Ваш номер найден, но место в рейтинге еще не определено."
                
            # Превращаем в красивую строку (без .0 если это было число)
            if isinstance(position, float) and position.is_integer():
                position = int(position)
                
            return f"Ваше текущее место в рейтинге: {position}"
        else:
            return "Абитуриент с таким номером не найден в списках. Проверьте правильность ввода."
            
    except Exception as e:
        print(f"Критическая ошибка при чтении Excel: {e}")
        return "Произошла техническая ошибка при обработке файла. Администраторы уже уведомлены."

def handle_admin_file(user_id, message_obj):
    """Функция обновления Excel-файла администратором"""
    attachments = message_obj.get('attachments', [])
    if not attachments:
        return False
        
    doc = attachments[0]
    if doc['type'] == 'doc' and doc['doc']['ext'] == 'xlsx':
        file_url = doc['doc']['url']
        try:
            # Скачиваем файл и перезаписываем старый
            response = requests.get(file_url)
            with open(EXCEL_FILENAME, 'wb') as f:
                f.write(response.content)
            
            # Быстрая проверка, что файл валидный
            pd.read_excel(EXCEL_FILENAME)
            
            send_msg(user_id, "✅ База данных успешно обновлена!")
            return True
        except Exception as e:
            send_msg(user_id, f"❌ Ошибка при обновлении файла: {e}")
            return True
            
    return False

print("Бот успешно запущен и слушает сервер...")

# Главный цикл LongPoll
for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        message = event.obj.message
        user_id = message['from_id']
        text = message['text'].strip()
        
        # 1. Проверка на администратора и обновление файла
        if user_id in ADMIN_IDS:
            if handle_admin_file(user_id, message):
                continue  # Если файл обработан, переходим к следующему событию
                
        # Приветственное сообщение
        if text.lower() in ['привет', 'начать', 'start', '/start']:
            send_msg(user_id, "Приветствуем! Введите ваш номер абитуриента (например, номер заявления или СНИЛС), чтобы узнать место в рейтинге.")
            continue
            
        # 2. Логика для обычного пользователя (поиск рейтинга)
        if text:
            # Передаем текст (номер) в функцию поиска
            response_text = get_applicant_rating(text)
            send_msg(user_id, response_text)

