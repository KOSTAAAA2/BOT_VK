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
GROUP_ID = "239371469"  
ADMIN_IDS = [239371469]
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
    """Поиск всех специальностей и мест абитуриента в Excel"""
    if not os.path.exists(EXCEL_FILENAME):
        return "Ошибка: База данных абитуриентов временно недоступна."
    
    try:
        df = pd.read_excel(EXCEL_FILENAME)
        df.columns = df.columns.astype(str).str.strip().str.lower()
        
        # Проверяем наличие новой колонки 'специальность'
        if 'номер' not in df.columns or 'место' not in df.columns or 'специальность' not in df.columns:
            return "⚠️ Ошибка: В таблице должны быть колонки 'Номер', 'Специальность' и 'Место'."
        
        df['номер'] = df['номер'].astype(str).str.strip()
        search_val = str(applicant_id).strip()
        
        # Ищем ВСЕ строки с совпавшим номером
        results = df[df['номер'] == search_val]
        
        if not results.empty:
            response = "📊 Ваше текущее место в рейтингах:\n\n"
            
            # Перебираем все найденные строки
            for index, row in results.iterrows():
                spec = str(row['специальность']).strip()
                position = row['место']
                
                # Проверка на пустую ячейку
                if pd.isna(position): 
                    pos_str = "место еще не определено"
                elif isinstance(position, float) and position.is_integer(): 
                    pos_str = f"{int(position)} место"
                else:
                    pos_str = f"{position} место"
                    
                response += f"🔹 {spec}: {pos_str}\n"
                
            return response
        else:
            return "Абитуриент с таким номером не найден в списках. Проверьте правильность ввода."
            
    except Exception as e:
        return f"Ошибка при обработке данных: {e}"


def handle_admin_file(user_id, message_obj):
    """Проверка и скачивание нового Excel-файла от админа (с учетом новой колонки)"""
    attachments = message_obj.get('attachments', [])
    if not attachments:
        return False
        
    doc = attachments[0]
    if doc['type'] == 'doc' and doc['doc']['ext'] == 'xlsx':
        file_url = doc['doc']['url']
        try:
            response = requests.get(file_url)
            temp_filename = "temp_rating.xlsx"
            with open(temp_filename, 'wb') as f:
                f.write(response.content)
            
            # Проверяем структуру нового файла на наличие 3 нужных колонок
            df = pd.read_excel(temp_filename)
            df.columns = df.columns.astype(str).str.strip().str.lower()
            
            if 'номер' not in df.columns or 'место' not in df.columns or 'специальность' not in df.columns:
                send_msg(user_id, "❌ Ошибка: В присланном файле нет необходимых колонок ('Номер', 'Специальность', 'Место'). База НЕ обновлена.")
                os.remove(temp_filename)
                return True
                
            if os.path.exists(EXCEL_FILENAME):
                os.remove(EXCEL_FILENAME)
            os.rename(temp_filename, EXCEL_FILENAME)
            
            send_msg(user_id, "✅ База данных успешно обновлена и проверена!")
            return True
        except Exception as e:
            send_msg(user_id, f"❌ Не удалось обработать файл. Ошибка: {e}")
            return True
            
    return False
