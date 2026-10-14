"""All bot texts, in one place. Handlers never contain text of their own.

Each key has three versions in this order: Uzbek (the default), Russian, English.
Use t(lang, key, **fields) to get one; {placeholders} are filled from `fields`.
"""

LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"

_TEXTS = {
    # --- language and menu ---
    "lang_prompt": ("Tilni tanlang / Выберите язык / Choose a language",) * 3,
    "menu_title": (
        "Bosh menyu. Nima qilamiz?",
        "Главное меню. Что делаем?",
        "Main menu. What would you like to do?",
    ),
    "btn_lost": ("😢 Men nimadir yo'qotdim", "😢 Я потерял(а) вещь", "😢 I lost something"),
    "btn_found": ("🙌 Men nimadir topdim", "🙌 Я нашёл(а) вещь", "🙌 I found something"),
    "btn_recent": ("🔎 So'nggi topilmalar", "🔎 Недавние находки", "🔎 Recent found items"),
    "btn_mine": ("📋 Mening arizalarim", "📋 Мои заявки", "📋 My reports"),
    "not_understood": (
        "Menyuni ochish uchun /start ni bosing.",
        "Чтобы открыть меню, нажмите /start.",
        "Press /start to open the menu.",
    ),
    "blocked": (
        "Kechirasiz, bu xizmat siz uchun mavjud emas.",
        "Извините, этот сервис вам недоступен.",
        "Sorry, this service is not available to you.",
    ),
    # --- wizard questions ---
    "ask_category": (
        "Buyum turini tanlang:",
        "Выберите категорию вещи:",
        "Choose the item category:",
    ),
    "ask_title": (
        "Buyum nomini yozing (masalan: qora Xiaomi powerbank):",
        "Напишите название вещи (например: чёрный повербанк Xiaomi):",
        "Write a short title (for example: black Xiaomi power bank):",
    ),
    "ask_description": (
        "Tavsifini yozing (brendi, belgilari, ichidagi narsalar):",
        "Опишите вещь (бренд, приметы, содержимое):",
        "Describe the item (brand, marks, contents):",
    ),
    "ask_color": ("Rangini tanlang:", "Выберите цвет:", "Choose the color:"),
    "ask_building": ("Qaysi binoda?", "В каком здании?", "Which building?"),
    "ask_area": ("Aniq joyni tanlang:", "Выберите место:", "Choose the exact place:"),
    "btn_unknown_loc": ("Bilmayman", "Не знаю", "I don't know"),
    "ask_date": ("Qachon?", "Когда?", "When?"),
    "btn_today": ("Bugun", "Сегодня", "Today"),
    "btn_yesterday": ("Kecha", "Вчера", "Yesterday"),
    "btn_pick_date": ("Sanani kiritish", "Ввести дату", "Pick a date"),
    "ask_date_text": (
        "Sanani KK.OO.YYYY ko'rinishida yozing (masalan 25.10.2026):",
        "Введите дату в формате ДД.ММ.ГГГГ (например 25.10.2026):",
        "Type the date as DD.MM.YYYY (for example 25.10.2026):",
    ),
    "ask_photo": (
        "Buyum rasmini yuboring yoki o'tkazib yuboring:",
        "Отправьте фото вещи или пропустите:",
        "Send a photo of the item, or skip:",
    ),
    "btn_skip": ("O'tkazib yuborish", "Пропустить", "Skip"),
    "ask_where": ("Buyum hozir qayerda?", "Где вещь сейчас?", "Where is the item now?"),
    "btn_office": ("🏢 Ofisga topshirdim", "🏢 Сдал(а) в офис", "🏢 I handed it to the office"),
    "btn_kept": ("🤲 O'zimda turibdi", "🤲 Вещь у меня", "🤲 I still have it"),
    "ask_consent": (
        "Egasi siz bilan bog'lana olishi uchun Telegram profilingizni ko'rsatamizmi?",
        "Разрешаете показать ваш Telegram владельцу, чтобы он мог с вами связаться?",
        "May we show your Telegram to the owner so they can contact you?",
    ),
    "btn_yes": ("Ha", "Да", "Yes"),
    "btn_no": ("Yo'q", "Нет", "No"),
    # --- validation errors ---
    "err_title": (
        "Nom 3 dan 100 gacha belgidan iborat bo'lsin.",
        "Название должно быть от 3 до 100 символов.",
        "The title must be 3 to 100 characters.",
    ),
    "err_description": (
        "Tavsif 3 dan 500 gacha belgidan iborat bo'lsin.",
        "Описание должно быть от 3 до 500 символов.",
        "The description must be 3 to 500 characters.",
    ),
    "err_date": (
        "Sana noto'g'ri yoki kelajakda. KK.OO.YYYY ko'rinishida yozing.",
        "Дата неверна или в будущем. Формат ДД.ММ.ГГГГ.",
        "That date is invalid or in the future. Use DD.MM.YYYY.",
    ),
    "err_photo": (
        "Iltimos, rasm yuboring yoki «O'tkazib yuborish» tugmasini bosing.",
        "Отправьте фото или нажмите «Пропустить».",
        "Please send a photo or press Skip.",
    ),
    # --- summary and results ---
    "kind_lost": ("Yo'qolgan", "Потеряно", "Lost"),
    "kind_found": ("Topilgan", "Найдено", "Found"),
    "summary": (
        "📋 Tekshiring ({kind}):\n\n📂 {category}\n📝 {title}\n💬 {description}\n"
        "🎨 {color}\n📍 {location}\n📅 {date}\n📷 {photo}",
        "📋 Проверьте ({kind}):\n\n📂 {category}\n📝 {title}\n💬 {description}\n"
        "🎨 {color}\n📍 {location}\n📅 {date}\n📷 {photo}",
        "📋 Please check ({kind}):\n\n📂 {category}\n📝 {title}\n💬 {description}\n"
        "🎨 {color}\n📍 {location}\n📅 {date}\n📷 {photo}",
    ),
    "summary_where": ("\n🏢 {where}", "\n🏢 {where}", "\n🏢 {where}"),
    "btn_submit": ("✅ Yuborish", "✅ Отправить", "✅ Submit"),
    "btn_edit": ("✏️ O'zgartirish", "✏️ Изменить", "✏️ Edit"),
    "btn_cancel": ("❌ Bekor qilish", "❌ Отмена", "❌ Cancel"),
    "restart": (
        "Keling, boshidan boshlaymiz.",
        "Давайте начнём сначала.",
        "Let's go through the steps again.",
    ),
    "cancelled": ("Bekor qilindi.", "Отменено.", "Cancelled."),
    "saved_lost": (
        "✅ Ariza qabul qilindi. Mos topilma bo'lsa, sizga xabar beramiz.",
        "✅ Заявка принята. Если найдётся похожая вещь, мы сообщим вам.",
        "✅ Your report is saved. We will message you if a similar item is found.",
    ),
    "saved_found": (
        "✅ Rahmat! Ariza qabul qilindi. Ofis xodimlari uni ko'rib chiqadi.",
        "✅ Спасибо! Заявка принята. Сотрудники офиса её рассмотрят.",
        "✅ Thank you! Your report is saved. The office will review it.",
    ),
    # --- recent found items ---
    "recent_prompt": (
        "Qaysi toifadagi topilmalarni ko'rsatay?",
        "Находки какой категории показать?",
        "Which category of found items should I show?",
    ),
    "all_categories": ("Barchasi", "Все", "All"),
    "recent_empty": (
        "So'nggi 30 kunda topilmalar yo'q.",
        "За последние 30 дней находок нет.",
        "No found items in the last 30 days.",
    ),
    "card": (
        "{emoji} {category}\n📝 {title}\n📍 {location}\n📅 {date}",
        "{emoji} {category}\n📝 {title}\n📍 {location}\n📅 {date}",
        "{emoji} {category}\n📝 {title}\n📍 {location}\n📅 {date}",
    ),
    "card_contact": (
        "\n👤 Topuvchi: {contact}",
        "\n👤 Нашедший: {contact}",
        "\n👤 Finder: {contact}",
    ),
    "btn_this_is_mine": ("🙋 Bu meniki", "🙋 Это моё", "🙋 This is mine"),
    "btn_more": ("Yana ▶", "Ещё ▶", "More ▶"),
    "need_lost_report": (
        "Avval shu toifadagi yo'qolgan buyum haqida ariza qoldiring.",
        "Сначала оставьте заявку о потере вещи этой категории.",
        "Please file a lost report in this category first.",
    ),
    "claim_sent": (
        "Rahmat! Ofis xodimlari so'rovingizni ko'rib chiqadi.",
        "Спасибо! Сотрудники офиса рассмотрят ваш запрос.",
        "Thanks! The office will review your claim.",
    ),
    # --- my reports ---
    "mine_title": ("Mening arizalarim:", "Мои заявки:", "My reports:"),
    "mine_empty": (
        "Sizda hali arizalar yo'q.",
        "У вас пока нет заявок.",
        "You have no reports yet.",
    ),
    "mine_line": ("{kind}: {title} — {status}",) * 3,
    "btn_cancel_report": ("❌ Bekor qilish: {title}", "❌ Отменить: {title}", "❌ Cancel: {title}"),
    "btn_reopen": ("🔄 Qayta ochish: {title}", "🔄 Открыть снова: {title}", "🔄 Reopen: {title}"),
    "report_cancelled": ("Ariza bekor qilindi.", "Заявка отменена.", "Report cancelled."),
    "report_reopened": ("Ariza qayta ochildi.", "Заявка открыта снова.", "Report reopened."),
    "status_open": ("ochiq", "открыта", "open"),
    "status_matched": ("mos topildi", "найдено совпадение", "matched"),
    "status_returned": ("qaytarildi", "возвращена", "returned"),
    "status_expired": ("muddati tugagan", "срок истёк", "expired"),
    "status_cancelled": ("bekor qilingan", "отменена", "cancelled"),
    "status_registered": ("ro'yxatga olingan", "принята офисом", "registered"),
    # --- notifications sent to users ---
    "n_item_registered": (
        "✅ «{title}» topilmasi ofisda ro'yxatga olindi (javon {shelf}). Rahmat!",
        "✅ Находка «{title}» принята в офисе (полка {shelf}). Спасибо!",
        "✅ Your found item «{title}» was registered at the office (shelf {shelf}). Thank you!",
    ),
    "n_match_found": (
        "Yo'qolgan «{title}» buyumingizga o'xshash narsa ofisga topshirildi. "
        "Shaxsni tasdiqlovchi hujjat bilan {room}-xonaga keling.",
        "Вещь, похожая на вашу пропажу «{title}», сдана в офис. "
        "Приходите в комнату {room} с документом.",
        "An item similar to your lost «{title}» was handed to the office. "
        "Come to room {room} with your ID.",
    ),
    "n_report_status": (
        "«{title}» arizangiz holati: {status}.",
        "Статус вашей заявки «{title}»: {status}.",
        "Your report «{title}» is now: {status}.",
    ),
    "n_expired": (
        "«{title}» arizangizning muddati tugadi (90 kun). Uni qayta ochishingiz mumkin.",
        "Срок заявки «{title}» истёк (90 дней). Вы можете открыть её снова.",
        "Your report «{title}» expired (90 days). You can reopen it.",
    ),
    "btn_match_yes": ("✅ Ha, bu meniki", "✅ Да, это моё", "✅ Yes, that's mine"),
    "btn_match_no": ("❌ Yo'q", "❌ Нет", "❌ No"),
    "match_yes_ack": (
        "Rahmat! Ofis xodimlari tasdiqlaydi. Hujjatingizni olib keling.",
        "Спасибо! Сотрудники офиса подтвердят. Возьмите с собой документ.",
        "Thanks! The office will confirm it. Bring your ID.",
    ),
    "match_no_ack": (
        "Tushunarli, bu taklifni yopdik.",
        "Понятно, это предложение закрыто.",
        "Understood, we closed this suggestion.",
    ),
    # --- daily digest (sent to the office group) ---
    "digest_title": ("📋 Kunlik hisobot", "📋 Ежедневный отчёт", "📋 Daily digest"),
    "digest_expiring": (
        "⏳ 7 kun ichida saqlash muddati tugaydi:",
        "⏳ Срок хранения истекает в ближайшие 7 дней:",
        "⏳ Retention ends within 7 days:",
    ),
    "digest_disposal": (
        "🗑 Utilizatsiyaga tayyor (muddati o'tgan):",
        "🗑 Готово к утилизации (срок истёк):",
        "🗑 Ready for disposal (retention is over):",
    ),
    "digest_none": ("—", "—", "—"),
    "digest_counts": (
        "Ochiq arizalar: {lost}. Ko'rib chiqilmagan takliflar: {pending}.",
        "Открытых заявок: {lost}. Предложений на проверке: {pending}.",
        "Open lost reports: {lost}. Suggestions to review: {pending}.",
    ),
}

STRINGS = {key: dict(zip(LANGUAGES, values, strict=True)) for key, values in _TEXTS.items()}


def t(lang, key, **fields):
    """The text for `key` in `lang` (falls back to Uzbek), with {placeholders} filled in."""
    texts = STRINGS[key]
    return texts.get(lang, texts[DEFAULT_LANGUAGE]).format(**fields)
