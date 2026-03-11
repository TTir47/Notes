import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
import sys
import re

# Настройки
API_TOKEN = '8682994538:AAGub_2h31QKycp-P2iDdC0mqiRAoFZO7ZM'

# Инициализация бота и диспетчера для aiogram 3.x
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Классы состояний для разных типов заметок
class PeopleNote(StatesGroup):
    waiting_for_name = State()  # ФИО
    waiting_for_address = State()  # Адрес
    waiting_for_description = State()  # Описание
    waiting_for_alarm_choice = State()  # Выбор: установить будильник или нет
    waiting_for_alarm_time = State()  # Время для будильника


class CarNote(StatesGroup):
    waiting_for_car_number = State()
    waiting_for_car_model = State()
    waiting_for_description = State()
    waiting_for_alarm_choice = State()
    waiting_for_alarm_time = State()


class ReminderNote(StatesGroup):
    waiting_for_address = State()
    waiting_for_time = State()
    waiting_for_description = State()
    waiting_for_alarm_choice = State()
    waiting_for_alarm_time = State()


class AlarmNote(StatesGroup):
    waiting_for_title = State()
    waiting_for_time = State()
    waiting_for_description = State()


# Классы для редактирования заметок
class EditNote(StatesGroup):
    waiting_for_note_id = State()
    waiting_for_field_choice = State()
    waiting_for_new_value = State()


# Классы для удаления заметок
class DeleteNote(StatesGroup):
    waiting_for_note_id = State()
    waiting_for_confirmation = State()


# Клавиатура главного меню
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📝 Добавить заметку"))
    builder.add(KeyboardButton(text="📋 Мои заметки"))
    builder.add(KeyboardButton(text="⏰ Мои будильники"))
    builder.add(KeyboardButton(text="✏️ Редактировать заметку"))
    builder.add(KeyboardButton(text="🗑 Удалить заметку"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура выбора типа заметки
def get_note_type_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="👤 Люди"))
    builder.add(KeyboardButton(text="🚗 Машины"))
    builder.add(KeyboardButton(text="⏰ Напоминания"))
    builder.add(KeyboardButton(text="🔔 Будильник"))
    builder.add(KeyboardButton(text="🔙 Назад"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура для пропуска поля
def get_skip_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="⏭ Пропустить"))
    builder.add(KeyboardButton(text="🔙 Отмена"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура для выбора установки будильника
def get_alarm_choice_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="✅ Да, установить будильник"))
    builder.add(KeyboardButton(text="❌ Нет, только заметка"))
    builder.add(KeyboardButton(text="🔙 Отмена"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


# Клавиатура для выбора поля для редактирования (для заметок о людях)
def get_people_edit_fields_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👤 ФИО", callback_data="edit_field_name"))
    builder.add(InlineKeyboardButton(text="📍 Адрес", callback_data="edit_field_address"))
    builder.add(InlineKeyboardButton(text="📝 Описание", callback_data="edit_field_description"))
    builder.add(InlineKeyboardButton(text="⏰ Время будильника", callback_data="edit_field_alarm_time"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel"))
    builder.adjust(1)
    return builder.as_markup()


# Клавиатура для выбора поля для редактирования (для заметок о машинах)
def get_car_edit_fields_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔢 Номер", callback_data="edit_field_car_number"))
    builder.add(InlineKeyboardButton(text="🏭 Марка", callback_data="edit_field_car_model"))
    builder.add(InlineKeyboardButton(text="📝 Описание", callback_data="edit_field_description"))
    builder.add(InlineKeyboardButton(text="⏰ Время будильника", callback_data="edit_field_alarm_time"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel"))
    builder.adjust(1)
    return builder.as_markup()


# Клавиатура для выбора поля для редактирования (для напоминаний)
def get_reminder_edit_fields_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📍 Адрес", callback_data="edit_field_address"))
    builder.add(InlineKeyboardButton(text="📝 Описание", callback_data="edit_field_description"))
    builder.add(InlineKeyboardButton(text="⏰ Время будильника", callback_data="edit_field_alarm_time"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel"))
    builder.adjust(1)
    return builder.as_markup()


# Клавиатура подтверждения удаления
def get_delete_confirmation_keyboard(note_id):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{note_id}"))
    builder.add(InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_delete"))
    builder.adjust(1)
    return builder.as_markup()


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    # Таблица для обычных заметок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_type TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица для будильников (напоминаний по времени)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            note_id INTEGER,
            title TEXT,
            alarm_time TIMESTAMP NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES notes (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


# Функция для сохранения заметки в БД
def save_note_to_db(user_id, note_type, content):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO notes (user_id, note_type, content)
        VALUES (?, ?, ?)
    ''', (user_id, note_type, content))

    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


# Функция для сохранения будильника
def save_alarm_to_db(user_id, note_id, title, alarm_time, description):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO alarms (user_id, note_id, title, alarm_time, description)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, note_id, title, alarm_time, description))

    alarm_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alarm_id


# Функция для получения активных будильников пользователя
def get_user_alarms(user_id):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, title, alarm_time, description FROM alarms
        WHERE user_id = ? AND is_active = 1
        ORDER BY alarm_time ASC
    ''', (user_id,))

    alarms = cursor.fetchall()
    conn.close()
    return alarms


# Функция для деактивации будильника
def deactivate_alarm(alarm_id):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE alarms SET is_active = 0 WHERE id = ?
    ''', (alarm_id,))

    conn.commit()
    conn.close()


# Функция для получения всех активных будильников
def get_all_active_alarms():
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, user_id, title, alarm_time, description FROM alarms
        WHERE is_active = 1
    ''')

    alarms = cursor.fetchall()
    conn.close()
    return alarms


# Функция для получения заметок пользователя из БД
def get_user_notes(user_id):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, note_type, content, created_at FROM notes
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))

    notes = cursor.fetchall()
    conn.close()
    return notes


# Функция для получения конкретной заметки по ID
def get_note_by_id(note_id, user_id):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, note_type, content, created_at FROM notes
        WHERE id = ? AND user_id = ?
    ''', (note_id, user_id))

    note = cursor.fetchone()
    conn.close()
    return note


# Функция для обновления заметки
def update_note_in_db(note_id, user_id, new_content):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE notes SET content = ? WHERE id = ? AND user_id = ?
    ''', (new_content, note_id, user_id))

    conn.commit()
    conn.close()


# Функция для удаления заметки
def delete_note_from_db(note_id, user_id):
    conn = sqlite3.connect('notes.db')
    cursor = conn.cursor()

    # Сначала удаляем связанные будильники (каскадное удаление должно работать,
    # но на всякий случай делаем явное удаление)
    cursor.execute('''
        DELETE FROM alarms WHERE note_id = ?
    ''', (note_id,))

    # Затем удаляем заметку
    cursor.execute('''
        DELETE FROM notes WHERE id = ? AND user_id = ?
    ''', (note_id, user_id))

    conn.commit()
    conn.close()


# Функция для парсинга заметки на поля
def parse_note_content(note_type, content):
    lines = content.split('\n')
    fields = {}

    if note_type == 'people':
        for line in lines:
            if line.startswith('👤 ФИО:'):
                fields['name'] = line.replace('👤 ФИО:', '').strip()
            elif line.startswith('📍 Адрес:'):
                fields['address'] = line.replace('📍 Адрес:', '').strip()
            elif line.startswith('📝 Описание:'):
                fields['description'] = line.replace('📝 Описание:', '').strip()
            elif line.startswith('⏰ Будильник:'):
                fields['alarm_time'] = line.replace('⏰ Будильник:', '').strip()
    elif note_type == 'car':
        for line in lines:
            if line.startswith('🔢 Номер:'):
                fields['car_number'] = line.replace('🔢 Номер:', '').strip()
            elif line.startswith('🏭 Марка:'):
                fields['car_model'] = line.replace('🏭 Марка:', '').strip()
            elif line.startswith('📝 Описание:'):
                fields['description'] = line.replace('📝 Описание:', '').strip()
            elif line.startswith('⏰ Будильник:'):
                fields['alarm_time'] = line.replace('⏰ Будильник:', '').strip()
    elif note_type == 'reminder':
        for line in lines:
            if line.startswith('📍 Адрес:'):
                fields['address'] = line.replace('📍 Адрес:', '').strip()
            elif line.startswith('📝 Описание:'):
                fields['description'] = line.replace('📝 Описание:', '').strip()
            elif line.startswith('⏰ Будильник:'):
                fields['alarm_time'] = line.replace('⏰ Будильник:', '').strip()

    return fields


# Функция для создания нового содержимого заметки после редактирования
def create_updated_content(note_type, fields):
    if note_type == 'people':
        return (f"Заметка о человеке:\n"
                f"👤 ФИО: {fields.get('name', 'Не указано')}\n"
                f"📍 Адрес: {fields.get('address', 'Не указан')}\n"
                f"📝 Описание: {fields.get('description', 'Нет описания')}\n"
                f"⏰ Будильник: {fields.get('alarm_time', 'Не указано')}")
    elif note_type == 'car':
        return (f"Заметка о машине:\n"
                f"🔢 Номер: {fields.get('car_number', 'Не указан')}\n"
                f"🏭 Марка: {fields.get('car_model', 'Не указана')}\n"
                f"📝 Описание: {fields.get('description', 'Нет описания')}\n"
                f"⏰ Будильник: {fields.get('alarm_time', 'Не указано')}")
    elif note_type == 'reminder':
        return (f"Напоминание:\n"
                f"📍 Адрес: {fields.get('address', 'Не указан')}\n"
                f"📝 Описание: {fields.get('description', 'Нет описания')}\n"
                f"⏰ Будильник: {fields.get('alarm_time', 'Не указано')}")


# Функция для проверки и отправки напоминаний
async def check_alarms():
    while True:
        try:
            alarms = get_all_active_alarms()
            current_time = datetime.now()

            for alarm_id, user_id, title, alarm_time_str, description in alarms:
                try:
                    alarm_time = datetime.strptime(alarm_time_str, '%Y-%m-%d %H:%M:%S')

                    # Если время наступило или прошло не более 1 минуты назад
                    if alarm_time <= current_time and (current_time - alarm_time).seconds < 60:
                        # Отправляем напоминание
                        message = f"🔔 <b>НАПОМИНАНИЕ!</b>\n\n"
                        if title:
                            message += f"📌 {title}\n"
                        if description:
                            message += f"📝 {description}\n"
                        message += f"⏰ Время: {alarm_time.strftime('%d.%m.%Y %H:%M')}"

                        try:
                            await bot.send_message(user_id, message, parse_mode=ParseMode.HTML)
                            # Деактивируем будильник
                            deactivate_alarm(alarm_id)
                        except Exception as e:
                            logging.error(f"Ошибка отправки будильника {alarm_id}: {e}")

                except Exception as e:
                    logging.error(f"Ошибка обработки будильника {alarm_id}: {e}")

            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)

        except Exception as e:
            logging.error(f"Ошибка в check_alarms: {e}")
            await asyncio.sleep(60)


@dp.message(Command('start'))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для создания заметок и напоминаний. Выберите действие:",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda message: message.text == "📝 Добавить заметку")
async def add_note(message: Message):
    await message.answer(
        "Выберите тип заметки:",
        reply_markup=get_note_type_keyboard()
    )


@dp.message(lambda message: message.text == "📋 Мои заметки")
async def show_notes(message: Message):
    user_id = message.from_user.id
    user_notes = get_user_notes(user_id)

    if not user_notes:
        await message.answer("У вас пока нет заметок.")
    else:
        response = "📋 <b>Ваши заметки:</b>\n\n"
        for i, (note_id, note_type, content, created_at) in enumerate(user_notes, 1):
            try:
                created_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                time_str = created_time.strftime('%d.%m.%Y %H:%M')
            except:
                time_str = created_at

            type_emoji = {
                'people': '👤',
                'car': '🚗',
                'reminder': '⏰'
            }.get(note_type, '📝')

            response += f"{i}. ID: {note_id} {type_emoji}\n{content}\n   📅 {time_str}\n\n"

        if len(response) > 4096:
            for x in range(0, len(response), 4096):
                await message.answer(response[x:x + 4096], parse_mode=ParseMode.HTML)
        else:
            await message.answer(response, parse_mode=ParseMode.HTML)


@dp.message(lambda message: message.text == "⏰ Мои будильники")
async def show_alarms(message: Message):
    user_id = message.from_user.id
    alarms = get_user_alarms(user_id)

    if not alarms:
        await message.answer("У вас пока нет активных будильников.")
    else:
        response = "🔔 <b>Ваши будильники:</b>\n\n"
        for i, (alarm_id, title, alarm_time_str, description) in enumerate(alarms, 1):
            try:
                alarm_time = datetime.strptime(alarm_time_str, '%Y-%m-%d %H:%M:%S')
                time_str = alarm_time.strftime('%d.%m.%Y %H:%M')
            except:
                time_str = alarm_time_str

            response += f"{i}. ID: {alarm_id}\n"
            if title:
                response += f"   📌 {title}\n"
            else:
                response += f"   📌 Без названия\n"
            response += f"   ⏰ {time_str}\n"
            if description:
                response += f"   📝 {description}\n"
            response += "\n"

        await message.answer(response, parse_mode=ParseMode.HTML)


# Обработчик для редактирования заметок
@dp.message(lambda message: message.text == "✏️ Редактировать заметку")
async def edit_note_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_notes = get_user_notes(user_id)

    if not user_notes:
        await message.answer("У вас пока нет заметок для редактирования.")
        return

    response = "Введите <b>ID заметки</b>, которую хотите отредактировать:\n\n"
    response += "Ваши заметки:\n"
    for note_id, note_type, content, created_at in user_notes[:5]:  # Показываем только первые 5
        type_emoji = {'people': '👤', 'car': '🚗', 'reminder': '⏰'}.get(note_type, '📝')
        short_content = content[:50] + "..." if len(content) > 50 else content
        response += f"ID: {note_id} {type_emoji} - {short_content}\n"

    if len(user_notes) > 5:
        response += f"\n... и еще {len(user_notes) - 5} заметок. Все ID можно посмотреть в разделе 'Мои заметки'"

    await message.answer(response, parse_mode=ParseMode.HTML)
    await state.set_state(EditNote.waiting_for_note_id)


@dp.message(EditNote.waiting_for_note_id)
async def edit_note_get_id(message: Message, state: FSMContext):
    try:
        note_id = int(message.text)
        user_id = message.from_user.id

        note = get_note_by_id(note_id, user_id)
        if not note:
            await message.answer("❌ Заметка с таким ID не найдена. Попробуйте еще раз или нажмите /cancel")
            return

        await state.update_data(note_id=note_id, note_type=note[1], content=note[2])

        # Показываем заметку и предлагаем выбрать поле для редактирования
        await message.answer(
            f"📝 <b>Текущая заметка:</b>\n\n{note[2]}\n\n"
            f"Выберите поле для редактирования:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_edit_fields_keyboard(note[1])
        )
        await state.set_state(EditNote.waiting_for_field_choice)

    except ValueError:
        await message.answer("❌ Пожалуйста, введите числовой ID заметки")


def get_edit_fields_keyboard(note_type):
    if note_type == 'people':
        return get_people_edit_fields_keyboard()
    elif note_type == 'car':
        return get_car_edit_fields_keyboard()
    else:
        return get_reminder_edit_fields_keyboard()


@dp.callback_query(lambda c: c.data.startswith('edit_field_'))
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace('edit_field_', '')

    if field == 'cancel':
        await callback.message.edit_text("❌ Редактирование отменено.")
        await state.clear()
        await callback.answer()
        return

    data = await state.get_data()
    note_type = data.get('note_type')
    content = data.get('content')

    # Парсим текущее содержимое
    fields = parse_note_content(note_type, content)

    field_names = {
        'name': '👤 ФИО',
        'address': '📍 Адрес',
        'description': '📝 Описание',
        'car_number': '🔢 Номер машины',
        'car_model': '🏭 Марка машины',
        'alarm_time': '⏰ Время будильника'
    }

    field_name = field_names.get(field, field)
    current_value = fields.get(field, 'Не указано')

    await state.update_data(edit_field=field)

    await callback.message.edit_text(
        f"Редактирование поля: <b>{field_name}</b>\n"
        f"Текущее значение: {current_value}\n\n"
        f"Введите новое значение (или отправьте 'пропустить' чтобы оставить как есть):",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(EditNote.waiting_for_new_value)
    await callback.answer()


@dp.message(EditNote.waiting_for_new_value)
async def edit_note_new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    note_id = data['note_id']
    note_type = data['note_type']
    content = data['content']
    edit_field = data['edit_field']
    user_id = message.from_user.id

    # Парсим текущее содержимое
    fields = parse_note_content(note_type, content)

    # Обновляем поле
    new_value = message.text
    if new_value.lower() == 'пропустить':
        new_value = fields.get(edit_field, 'Не указано')

    fields[edit_field] = new_value

    # Создаем новое содержимое
    new_content = create_updated_content(note_type, fields)

    # Обновляем в базе
    update_note_in_db(note_id, user_id, new_content)

    await message.answer(
        f"✅ Заметка успешно обновлена!\n\n"
        f"Новое содержимое:\n{new_content}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


# Обработчик для удаления заметок
@dp.message(lambda message: message.text == "🗑 Удалить заметку")
async def delete_note_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_notes = get_user_notes(user_id)

    if not user_notes:
        await message.answer("У вас пока нет заметок для удаления.")
        return

    response = "Введите <b>ID заметки</b>, которую хотите удалить:\n\n"
    response += "Ваши заметки:\n"
    for note_id, note_type, content, created_at in user_notes[:5]:
        type_emoji = {'people': '👤', 'car': '🚗', 'reminder': '⏰'}.get(note_type, '📝')
        short_content = content[:50] + "..." if len(content) > 50 else content
        response += f"ID: {note_id} {type_emoji} - {short_content}\n"

    if len(user_notes) > 5:
        response += f"\n... и еще {len(user_notes) - 5} заметок."

    await message.answer(response, parse_mode=ParseMode.HTML)
    await state.set_state(DeleteNote.waiting_for_note_id)


@dp.message(DeleteNote.waiting_for_note_id)
async def delete_note_get_id(message: Message, state: FSMContext):
    try:
        note_id = int(message.text)
        user_id = message.from_user.id

        note = get_note_by_id(note_id, user_id)
        if not note:
            await message.answer("❌ Заметка с таким ID не найдена. Попробуйте еще раз или нажмите /cancel")
            return

        await state.update_data(note_id=note_id)

        # Показываем заметку и запрашиваем подтверждение
        await message.answer(
            f"🗑 <b>Вы действительно хотите удалить эту заметку?</b>\n\n"
            f"{note[2]}\n\n"
            f"Это действие нельзя отменить!",
            parse_mode=ParseMode.HTML,
            reply_markup=get_delete_confirmation_keyboard(note_id)
        )
        await state.set_state(DeleteNote.waiting_for_confirmation)

    except ValueError:
        await message.answer("❌ Пожалуйста, введите числовой ID заметки")


@dp.callback_query(lambda c: c.data.startswith('confirm_delete_'))
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    note_id = int(callback.data.replace('confirm_delete_', ''))
    user_id = callback.from_user.id

    delete_note_from_db(note_id, user_id)

    await callback.message.edit_text("✅ Заметка успешно удалена!")
    await state.clear()
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'cancel_delete')
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Удаление отменено.")
    await state.clear()
    await callback.answer()


@dp.message(lambda message: message.text == "🔙 Назад")
async def back_to_main(message: Message):
    await message.answer(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda message: message.text == "🔙 Отмена")
async def cancel_current(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Действие отменено.",
        reply_markup=get_main_keyboard()
    )


# Общая функция для обработки выбора будильника
async def process_alarm_choice(message: Message, state: FSMContext, note_type):
    if message.text == "✅ Да, установить будильник":
        await message.answer(
            "Введите время для будильника (в формате ДД.ММ.ГГГГ ЧЧ:ММ, например 25.12.2023 15:30):",
            reply_markup=None
        )
        await state.set_state(PeopleNote.waiting_for_alarm_time)
    elif message.text == "❌ Нет, только заметка":
        user_data = await state.get_data()
        user_id = message.from_user.id

        # Формируем заметку в зависимости от типа
        if note_type == 'people':
            note = (f"Заметка о человеке:\n"
                    f"👤 ФИО: {user_data.get('name', 'Не указано')}\n"
                    f"📍 Адрес: {user_data.get('address', 'Не указан')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}")
        elif note_type == 'car':
            note = (f"Заметка о машине:\n"
                    f"🔢 Номер: {user_data.get('car_number', 'Не указан')}\n"
                    f"🏭 Марка: {user_data.get('car_model', 'Не указана')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}")
        else:  # reminder
            note = (f"Напоминание:\n"
                    f"📍 Адрес: {user_data.get('address', 'Не указан')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}")

        # Сохраняем заметку
        note_id = save_note_to_db(user_id, note_type, note)

        await message.answer("✅ Заметка сохранена!", reply_markup=get_main_keyboard())
        await state.clear()
    else:
        await message.answer("Пожалуйста, выберите вариант из меню:")


# Обработчики для заметок о людях
@dp.message(lambda message: message.text == "👤 Люди")
async def people_note_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите имя, фамилию и отчество (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(PeopleNote.waiting_for_name)


@dp.message(PeopleNote.waiting_for_name)
async def people_name(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(name="Не указано")
    else:
        await state.update_data(name=message.text)

    await message.answer(
        "Введите адрес (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(PeopleNote.waiting_for_address)


@dp.message(PeopleNote.waiting_for_address)
async def people_address(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(address="Не указан")
    else:
        await state.update_data(address=message.text)

    await message.answer(
        "Введите описание (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(PeopleNote.waiting_for_description)


@dp.message(PeopleNote.waiting_for_description)
async def people_description(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(description="Нет описания")
    else:
        await state.update_data(description=message.text)

    await message.answer(
        "Хотите установить будильник для этой заметки?",
        reply_markup=get_alarm_choice_keyboard()
    )
    await state.set_state(PeopleNote.waiting_for_alarm_choice)


@dp.message(PeopleNote.waiting_for_alarm_choice)
async def people_alarm_choice(message: Message, state: FSMContext):
    await process_alarm_choice(message, state, 'people')


# Обработчики для заметок о машинах
@dp.message(lambda message: message.text == "🚗 Машины")
async def car_note_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите номер машины (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(CarNote.waiting_for_car_number)


@dp.message(CarNote.waiting_for_car_number)
async def car_number(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(car_number="Не указан")
    else:
        await state.update_data(car_number=message.text)

    await message.answer(
        "Введите марку машины (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(CarNote.waiting_for_car_model)


@dp.message(CarNote.waiting_for_car_model)
async def car_model(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(car_model="Не указана")
    else:
        await state.update_data(car_model=message.text)

    await message.answer(
        "Введите описание (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(CarNote.waiting_for_description)


@dp.message(CarNote.waiting_for_description)
async def car_description(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(description="Нет описания")
    else:
        await state.update_data(description=message.text)

    await message.answer(
        "Хотите установить будильник для этой заметки?",
        reply_markup=get_alarm_choice_keyboard()
    )
    await state.set_state(CarNote.waiting_for_alarm_choice)


@dp.message(CarNote.waiting_for_alarm_choice)
async def car_alarm_choice(message: Message, state: FSMContext):
    await process_alarm_choice(message, state, 'car')


# Обработчики для напоминаний
@dp.message(lambda message: message.text == "⏰ Напоминания")
async def reminder_note_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите адрес (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(ReminderNote.waiting_for_address)


@dp.message(ReminderNote.waiting_for_address)
async def reminder_address(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(address="Не указан")
    else:
        await state.update_data(address=message.text)

    await message.answer(
        "Введите описание (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(ReminderNote.waiting_for_description)


@dp.message(ReminderNote.waiting_for_description)
async def reminder_description(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(description="Нет описания")
    else:
        await state.update_data(description=message.text)

    await message.answer(
        "Хотите установить будильник для этого напоминания?",
        reply_markup=get_alarm_choice_keyboard()
    )
    await state.set_state(ReminderNote.waiting_for_alarm_choice)


@dp.message(ReminderNote.waiting_for_alarm_choice)
async def reminder_alarm_choice(message: Message, state: FSMContext):
    await process_alarm_choice(message, state, 'reminder')


# Обработчик для времени будильника (общий для всех типов заметок)
@dp.message(PeopleNote.waiting_for_alarm_time)
@dp.message(CarNote.waiting_for_alarm_time)
@dp.message(ReminderNote.waiting_for_alarm_time)
async def process_alarm_time(message: Message, state: FSMContext):
    try:
        # Парсим время
        alarm_time = datetime.strptime(message.text, '%d.%m.%Y %H:%M')

        # Проверяем, что время в будущем
        if alarm_time <= datetime.now():
            await message.answer("❌ Время должно быть в будущем! Попробуйте еще раз:")
            return

        # Получаем данные из состояния
        user_data = await state.get_data()
        user_id = message.from_user.id

        # Определяем тип заметки из текущего состояния
        current_state = await state.get_state()
        if 'PeopleNote' in current_state:
            note_type = 'people'
            note = (f"Заметка о человеке:\n"
                    f"👤 ФИО: {user_data.get('name', 'Не указано')}\n"
                    f"📍 Адрес: {user_data.get('address', 'Не указан')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}\n"
                    f"⏰ Будильник: {alarm_time.strftime('%d.%m.%Y %H:%M')}")
        elif 'CarNote' in current_state:
            note_type = 'car'
            note = (f"Заметка о машине:\n"
                    f"🔢 Номер: {user_data.get('car_number', 'Не указан')}\n"
                    f"🏭 Марка: {user_data.get('car_model', 'Не указана')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}\n"
                    f"⏰ Будильник: {alarm_time.strftime('%d.%m.%Y %H:%M')}")
        else:  # reminder
            note_type = 'reminder'
            note = (f"Напоминание:\n"
                    f"📍 Адрес: {user_data.get('address', 'Не указан')}\n"
                    f"📝 Описание: {user_data.get('description', 'Нет описания')}\n"
                    f"⏰ Будильник: {alarm_time.strftime('%d.%m.%Y %H:%M')}")

        # Сохраняем заметку
        note_id = save_note_to_db(user_id, note_type, note)

        # Сохраняем будильник
        alarm_title = f"Напоминание из заметки: {note_type}"
        if note_type == 'people' and user_data.get('name') != 'Не указано':
            alarm_title = f"Встреча с {user_data['name']}"
        elif note_type == 'car' and user_data.get('car_number') != 'Не указан':
            alarm_title = f"Машина {user_data['car_number']}"

        alarm_id = save_alarm_to_db(
            user_id,
            note_id,
            alarm_title,
            alarm_time.strftime('%Y-%m-%d %H:%M:%S'),
            user_data.get('description', 'Нет описания')
        )

        await message.answer(
            f"✅ Заметка и будильник успешно сохранены!\n"
            f"⏰ Будильник установлен на {alarm_time.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Неверный формат времени! Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2023 15:30"
        )


# Обработчики для отдельного будильника
@dp.message(lambda message: message.text == "🔔 Будильник")
async def alarm_note_start(message: Message, state: FSMContext):
    await message.answer(
        "Введите название будильника (или нажмите 'Пропустить'):",
        reply_markup=get_skip_keyboard()
    )
    await state.set_state(AlarmNote.waiting_for_title)


@dp.message(AlarmNote.waiting_for_title)
async def alarm_title(message: Message, state: FSMContext):
    if message.text == "⏭ Пропустить":
        await state.update_data(title="Без названия")
    else:
        await state.update_data(title=message.text)

    await message.answer(
        "Введите время срабатывания (в формате ДД.ММ.ГГГГ ЧЧ:ММ, например 25.12.2023 15:30):\n"
        "Это поле обязательно для заполнения!",
        reply_markup=None
    )
    await state.set_state(AlarmNote.waiting_for_time)


@dp.message(AlarmNote.waiting_for_time)
async def alarm_time(message: Message, state: FSMContext):
    try:
        alarm_time = datetime.strptime(message.text, '%d.%m.%Y %H:%M')

        if alarm_time <= datetime.now():
            await message.answer("❌ Время должно быть в будущем! Попробуйте еще раз:")
            return

        await state.update_data(alarm_time=alarm_time.strftime('%Y-%m-%d %H:%M:%S'))

        await message.answer(
            "Введите описание (или нажмите 'Пропустить'):",
            reply_markup=get_skip_keyboard()
        )
        await state.set_state(AlarmNote.waiting_for_description)

    except ValueError:
        await message.answer(
            "❌ Неверный формат времени! Используйте формат ДД.ММ.ГГГГ ЧЧ:ММ\n"
            "Например: 25.12.2023 15:30"
        )


@dp.message(AlarmNote.waiting_for_description)
async def alarm_description(message: Message, state: FSMContext):
    user_data = await state.get_data()
    user_id = message.from_user.id

    if message.text == "⏭ Пропустить":
        description = ""
    else:
        description = message.text

    alarm_id = save_alarm_to_db(
        user_id,
        None,  # note_id = None для отдельного будильника
        user_data.get('title', 'Без названия'),
        user_data['alarm_time'],
        description
    )

    alarm_time = datetime.strptime(user_data['alarm_time'], '%Y-%m-%d %H:%M:%S')
    time_str = alarm_time.strftime('%d.%m.%Y %H:%M')

    await message.answer(
        f"✅ Будильник успешно установлен!\n"
        f"⏰ Время: {time_str}\n"
        f"ID: {alarm_id}",
        reply_markup=get_main_keyboard()
    )
    await state.clear()


# Обработчик для отмены состояний
@dp.message(Command('cancel'))
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_keyboard())


# Обработчик для всех остальных сообщений
@dp.message()
async def handle_unknown(message: Message):
    await message.answer(
        "Я не понимаю эту команду. Используйте кнопки меню.",
        reply_markup=get_main_keyboard()
    )


async def main():
    # Инициализируем базу данных
    init_db()

    # Запускаем фоновую задачу для проверки будильников
    asyncio.create_task(check_alarms())

    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())