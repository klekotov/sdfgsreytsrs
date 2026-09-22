from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import asyncio
import logging
from typing import Dict, Optional

from config import TELEGRAM_TOKEN, SITES_CONFIG, CHECK_INTERVAL
from database import Database
from parser import SiteParser
from payments import InfernoCookiesPayment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AddProduct(StatesGroup):
    selecting_site = State()
    selecting_product = State()
    custom_product_name = State()
    target_price = State()
    confirm = State()

active_watchers: Dict[int, asyncio.Task] = {}

class AutoBuyBot:
    def __init__(self):
        self.bot = Bot(token=TELEGRAM_TOKEN)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.db = Database()
        self.parsers: Dict[str, SiteParser] = {}
        self.register_handlers()

    async def init(self):
        await self.db.init_db()
        for site_key, config in SITES_CONFIG.items():
            parser = SiteParser(config)
            await parser.init()
            self.parsers[site_key] = parser

    async def close(self):
        for parser in self.parsers.values():
            await parser.close()
        await self.bot.session.close()

    def register_handlers(self):
        self.dp.message.register(self.start_cmd, Command("start"))
        self.dp.message.register(self.add_product_cmd, Command("add"))
        self.dp.message.register(self.my_products_cmd, Command("list"))
        self.dp.message.register(self.history_cmd, Command("history"))
        self.dp.message.register(self.help_cmd, Command("help"))

        self.dp.message.register(self.add_product_cmd, F.text == "➕ Добавить товар")
        self.dp.message.register(self.my_products_cmd, F.text == "📋 Мои товары")
        self.dp.message.register(self.history_cmd,     F.text == "📊 История")
        self.dp.message.register(self.help_cmd,        F.text == "❓ Справка")

        self.dp.message.register(self.enter_custom_product, AddProduct.custom_product_name)
        self.dp.message.register(self.set_target_price,     AddProduct.target_price)

        self.dp.callback_query.register(
            self.select_site,
            F.data.startswith("site_"),
            StateFilter(AddProduct.selecting_site)
        )
        self.dp.callback_query.register(
            self.select_product,
            F.data.startswith("prod_"),
            StateFilter(AddProduct.selecting_product)
        )
        self.dp.callback_query.register(
            self.confirm_product,
            F.data.startswith("confirm_"),
            StateFilter(AddProduct.confirm)
        )

    async def start_cmd(self, message: types.Message):
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        await self.db.add_user(user_id, username)  # ← await

        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="➕ Добавить товар")],
            [KeyboardButton(text="📋 Мои товары"), KeyboardButton(text="📊 История")],
            [KeyboardButton(text="❓ Справка")]
        ], resize_keyboard=True)

        await message.answer(
            "🤖 <b>Auto Buy Bot</b>\n\n"
            "Привет! Я помогу тебе автоматически отслеживать и покупать товары.\n\n"
            "Выбери действие:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    async def add_product_cmd(self, message: types.Message, state: FSMContext):
        sites_list = list(SITES_CONFIG.items())

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=config['name'], callback_data=f"site_{key}")]
            for key, config in sites_list
        ])

        await message.answer("Выбери сайт для отслеживания:", reply_markup=kb)
        await state.set_state(AddProduct.selecting_site)

    async def select_site(self, callback: types.CallbackQuery, state: FSMContext):
        site_key = callback.data.replace("site_", "")

        if site_key not in SITES_CONFIG:
            await callback.answer("❌ Неизвестный сайт")
            return

        await state.update_data(site_key=site_key)

        parser = self.parsers.get(site_key)
        if not parser:
            await callback.message.edit_text("❌ Парсер не инициализирован.")
            return

        products = await parser.get_all_products()

        if not products:
            await callback.message.edit_text("❌ Не удалось загрузить товары. Попробуй позже.")
            await callback.answer()
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=p['name'][:45], callback_data=f"prod_{i}")]
            for i, p in enumerate(products[:10])
        ] + [
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="prod_custom")]
        ])

        await callback.message.edit_text(
            f"<b>{SITES_CONFIG[site_key]['name']}</b>\n\n"
            "Выбери товар или введи название вручную:",
            reply_markup=kb,
            parse_mode="HTML"
        )

        await state.update_data(products=products)
        await state.set_state(AddProduct.selecting_product)
        await callback.answer()

    async def select_product(self, callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        products = data.get('products', [])

        if callback.data == "prod_custom":
            await callback.message.edit_text("Введи название товара вручную:")
            await state.set_state(AddProduct.custom_product_name)
            await callback.answer()
            return

        try:
            product_idx = int(callback.data.replace("prod_", ""))
            selected_product = products[product_idx]

            await state.update_data(selected_product=selected_product)
            await callback.message.edit_text(
                f"<b>{selected_product['name']}</b>\n"
                f"Цена: ${selected_product.get('price', 0)}\n"
                f"В наличии: {'✅ Да' if selected_product['in_stock'] else '❌ Нет'}\n"
                f"Доступно: {selected_product.get('available_count', 0)} шт.\n\n"
                "Укажи максимальную цену для автопокупки (или 0 для любой):",
                parse_mode="HTML"
            )
            await state.set_state(AddProduct.target_price)
            await callback.answer()
        except (ValueError, IndexError):
            await callback.answer("❌ Ошибка выбора")

    async def enter_custom_product(self, message: types.Message, state: FSMContext):
        product_name = message.text.strip()

        if len(product_name) < 2:
            await message.answer("❌ Название слишком короткое")
            return

        await state.update_data(custom_product_name=product_name)
        await message.answer("Укажи максимальную цену для автопокупки (или 0 для любой):")
        await state.set_state(AddProduct.target_price)

    async def set_target_price(self, message: types.Message, state: FSMContext):
        try:
            price = float(message.text.replace(',', '.'))
            if price < 0:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введи корректную цену (например: 9.99 или 0)")
            return

        await state.update_data(target_price=price)
        data = await state.get_data()

        selected_product = data.get('selected_product')
        product_name = selected_product['name'] if selected_product else data.get('custom_product_name', 'Неизвестно')
        site_key = data.get('site_key', '')
        site_name = SITES_CONFIG.get(site_key, {}).get('name', site_key)
        price_text = f"${price}" if price > 0 else "Любая"

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="confirm_no")
        ]])

        await message.answer(
            f"<b>Подтверди добавление:</b>\n\n"
            f"Товар: {product_name}\n"
            f"Сайт: {site_name}\n"
            f"Макс. цена: {price_text}",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await state.set_state(AddProduct.confirm)

    async def confirm_product(self, callback: types.CallbackQuery, state: FSMContext):
        if callback.data == "confirm_no":
            await callback.message.edit_text("❌ Отменено.")
            await state.clear()
            await callback.answer()
            return

        data = await state.get_data()
        user_id = callback.from_user.id
        site_key = data['site_key']
        selected_product = data.get('selected_product')
        product_name = selected_product['name'] if selected_product else data.get('custom_product_name')
        product_sku = selected_product.get('id') if selected_product else None
        target_price = data.get('target_price', 0)

        db_id = await self.db.add_watched_product(  # ← await
            user_id, site_key, product_name, product_sku,
            target_price if target_price > 0 else None
        )

        await callback.message.edit_text(
            f"✅ <b>Товар добавлен!</b>\n\n"
            f"ID: {db_id}\n"
            f"Начинаю отслеживание...",
            parse_mode="HTML"
        )

        await state.clear()
        await callback.answer()

        if user_id not in active_watchers:
            task = asyncio.create_task(self.watch_user_products(user_id))
            active_watchers[user_id] = task

    async def my_products_cmd(self, message: types.Message):
        user_id = message.from_user.id
        products = await self.db.get_watched_products(user_id)  # ← await

        if not products:
            await message.answer("📭 Ты пока ничего не отслеживаешь")
            return

        text = "<b>📋 Мои товары:</b>\n\n"
        for product in products:
            site_name = SITES_CONFIG.get(product['site_key'], {}).get('name', 'Unknown')
            text += (
                f"<b>#{product['id']}</b> - {product['product_name']}\n"
                f"  Сайт: {site_name}\n"
                f"  Статус: {product['status']}\n\n"
            )

        await message.answer(text, parse_mode="HTML")

    async def history_cmd(self, message: types.Message):
        user_id = message.from_user.id
        purchases = await self.db.get_purchase_history(user_id)  # ← await

        if not purchases:
            await message.answer("📭 История покупок пуста")
            return

        text = "<b>📊 История покупок:</b>\n\n"
        for purchase in purchases:
            status_emoji = "✅" if purchase['status'] == 'success' else "❌"
            text += (
                f"{status_emoji} {purchase['product_name']}\n"
                f"  Цена: ${purchase['price']}\n"
                f"  Заказ: {purchase['order_id']}\n"
                f"  Дата: {purchase['purchased_at']}\n\n"
            )

        await message.answer(text, parse_mode="HTML")

    async def help_cmd(self, message: types.Message):
        await message.answer(
            "<b>❓ Справка</b>\n\n"
            "/add — Добавить новый товар\n"
            "/list — Мои товары\n"
            "/history — История покупок\n"
            "/help — Эта справка\n\n"
            "<b>Как это работает:</b>\n"
            "1️⃣ Выбери сайт и товар\n"
            "2️⃣ Укажи максимальную цену (опционально)\n"
            "3️⃣ Я буду проверять наличие каждую минуту\n"
            "4️⃣ Когда товар появится — автоматически куплю\n"
            "5️⃣ Пришлю ссылку для скачивания\n\n"
            "<i>Покупка полностью автоматическая, никаких подтверждений</i>",
            parse_mode="HTML"
        )

    async def watch_user_products(self, user_id: int):
        logger.info(f"Started watching products for user {user_id}")

        try:
            while True:
                products = await self.db.get_watched_products(user_id, "active")  # ← await

                for product in products:
                    site_key = product['site_key']
                    product_name = product['product_name']
                    product_sku = product['product_sku']

                    parser = self.parsers.get(site_key)
                    if not parser:
                        continue

                    check = await parser.check_stock(product_name)

                    if check['found']:
                        await self.db.update_product_cache(  # ← await
                            site_key,
                            product_name,
                            product_sku or '',
                            check['product'].get('price', 0),
                            check['in_stock'],
                            check.get('available_count', 0)
                        )

                        if check['in_stock']:
                            price = check['product'].get('price', 0)
                            target = product.get('target_price')

                            if target and price > target:
                                continue

                            await self.bot.send_message(
                                user_id,
                                f"🔔 <b>ТОВАР В НАЛИЧИИ!</b>\n\n"
                                f"'{product_name}'\n"
                                f"Доступно: {check.get('available_count', 0)} шт.\n"
                                f"Цена: ${price}\n\n"
                                f"⏳ Начинаю автоматическую покупку...",
                                parse_mode="HTML"
                            )

                            payment = InfernoCookiesPayment()
                            purchase_result = await payment.execute_purchase(product_sku)

                            await self.db.add_purchase(  # ← await
                                user_id, site_key, product_name, price,
                                'success' if purchase_result['success'] else 'failed',
                                purchase_result.get('order_id')
                            )

                            if purchase_result['success']:
                                download_url = purchase_result.get('bundle_download_url', '')
                                msg = (
                                    f"✅ <b>ПОКУПКА УСПЕШНА!</b>\n\n"
                                    f"Товар: {product_name}\n"
                                    f"Номер заказа: {purchase_result['order_id']}\n\n"
                                )
                                if download_url:
                                    full_url = f"https://inferno-cookies.com{download_url}"
                                    msg += f"<a href='{full_url}'>📥 Скачать</a>"
                                await self.bot.send_message(user_id, msg, parse_mode="HTML")
                            else:
                                await self.bot.send_message(
                                    user_id,
                                    f"❌ <b>Ошибка при покупке</b>\n\n"
                                    f"Товар: {product_name}\n"
                                    f"Ошибка: {purchase_result.get('error', 'Неизвестная ошибка')}",
                                    parse_mode="HTML"
                                )

                            await self.db.remove_watched_product(product['id'])  # ← await

                await asyncio.sleep(CHECK_INTERVAL)

        except asyncio.CancelledError:
            logger.info(f"Stopped watching products for user {user_id}")
        except Exception as e:
            logger.error(f"Watch error for user {user_id}: {e}")
        finally:
            active_watchers.pop(user_id, None)

    async def run(self):
        await self.init()
        logger.info("Bot started (polling mode)")
        try:
            await self.dp.start_polling(self.bot)
        finally:
            await self.close()

async def main():
    bot = AutoBuyBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
