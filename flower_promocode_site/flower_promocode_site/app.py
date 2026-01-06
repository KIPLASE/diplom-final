from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uuid
from datetime import datetime, timedelta
import random
from typing import Optional, List

app = FastAPI(title="🌸 Цветочные Промокоды", description="Самые выгодные скидки на цветы!")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Создаем папки
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Цветочная палитра
FLOWER_COLORS = {
    "rose": "#FF69B4", "lilac": "#C8A2C8", "tulip": "#FF6347",
    "sunflower": "#FFD700", "lavender": "#E6E6FA", "leaf": "#32CD32",
    "violet": "#8A2BE2", "peach": "#FFDAB9", "orchid": "#DA70D6",
    "hydrangea": "#7B68EE", "daisy": "#FFFACD", "iris": "#5D478B"
}

# Типы цветов с иконками
FLOWER_TYPES = {
    "Розы": "🌹", "Тюльпаны": "🌷", "Лилии": "⚜️",
    "Хризантемы": "🌼", "Пионы": "🌸", "Орхидеи": "💮",
    "Герберы": "🌻", "Альстромерии": "🏵️", "Подсолнухи": "🌻",
    "Гортензии": "🔮", "Ирисы": "🔷", "Разные": "💐"
}

# Хранилище данных
users_db = {}
promocodes_db = []
next_promo_id = 1
popularity_stats = {}  # Статистика популярности промокодов


# Вспомогательные функции
def get_current_user(request: Request):
    return request.cookies.get("username")


def is_owner(promocode, username):
    return promocode.get("owner") == username


def get_random_flower_emoji():
    emojis = ["🌸", "🌺", "🌷", "🌹", "💐", "🥀", "🌻", "🌼", "💮", "🏵️"]
    return random.choice(emojis)


def get_random_color():
    colors = list(FLOWER_COLORS.values())
    return random.choice(colors)


def get_flower_quote():
    quotes = [
        "Цветы – это остатки рая на земле",
        "Где цветы, там и весна",
        "Жизнь начинается с любви, а любовь – с цветов",
        "Цветы улыбаются каждому, кто на них смотрит",
        "В каждом цветке – маленькое солнце",
        "Цветы – это слова, которые может прочитать даже слепой"
    ]
    return random.choice(quotes)


def extract_discount_value(discount_str: str) -> int:
    """Извлекает числовое значение скидки из строки"""
    import re
    # Ищем числа в строке
    numbers = re.findall(r'\d+', discount_str)
    if numbers:
        return int(numbers[0])
    return 0


def update_popularity(promo_id: int, action: str):
    """Обновляет статистику популярности промокода"""
    if promo_id not in popularity_stats:
        popularity_stats[promo_id] = {"views": 0, "copies": 0, "clicks": 0}

    if action == "view":
        popularity_stats[promo_id]["views"] += 1
    elif action == "copy":
        popularity_stats[promo_id]["copies"] += 1
    elif action == "click":
        popularity_stats[promo_id]["clicks"] += 1


def get_popular_promocodes(limit: int = 5):
    """Возвращает самые популярные промокоды"""
    sorted_promos = sorted(
        [(promo, popularity_stats.get(promo["id"], {"copies": 0, "views": 0}))
         for promo in promocodes_db],
        key=lambda x: (x[1]["copies"] * 3 + x[1]["views"] * 2 + x[1].get("clicks", 0)),
        reverse=True
    )
    return [promo for promo, _ in sorted_promos[:limit]]


def get_recommendations(username: str, limit: int = 3):
    """Рекомендации на основе истории пользователя"""
    user_promos = [p for p in promocodes_db if p["owner"] == username]
    if not user_promos:
        return get_popular_promocodes(limit)

    # Находим предпочитаемые типы цветов пользователя
    user_flower_types = {}
    for promo in user_promos:
        flower_type = promo.get("flower_type", "Разные")
        user_flower_types[flower_type] = user_flower_types.get(flower_type, 0) + 1

    # Рекомендуем промокоды с похожими типами цветов
    preferred_types = [t for t, _ in sorted(user_flower_types.items(), key=lambda x: x[1], reverse=True)[:2]]

    recommendations = []
    for promo in promocodes_db:
        if promo["owner"] != username and promo.get("flower_type") in preferred_types:
            recommendations.append(promo)

    if len(recommendations) < limit:
        # Добавляем популярные промокоды, если рекомендаций мало
        popular = get_popular_promocodes(limit - len(recommendations))
        recommendations.extend([p for p in popular if p not in recommendations])

    return recommendations[:limit]


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/")
async def home(request: Request):
    username = get_current_user(request)

    # Статистика
    stats = {
        "total_promos": len(promocodes_db),
        "active_users": len(users_db),
        "flower_quotes": get_flower_quote(),
        "random_emoji": get_random_flower_emoji(),
        "popular_promos": get_popular_promocodes(3)
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": username,
        "promocodes": promocodes_db,
        "is_owner": lambda promo: is_owner(promo, username),
        "stats": stats,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES,
        "random_color": get_random_color()
    })


# ========== ПОИСК И ФИЛЬТРАЦИЯ ==========
@app.get("/search")
async def search_promocodes(
        request: Request,
        query: Optional[str] = Query(None),
        flower_type: Optional[str] = Query(None),
        min_discount: Optional[int] = Query(None),
        max_discount: Optional[int] = Query(None),
        sort_by: str = Query("newest"),
        shop: Optional[str] = Query(None)
):
    username = get_current_user(request)

    # Фильтрация промокодов
    filtered = promocodes_db.copy()

    # Поиск по тексту
    if query:
        query_lower = query.lower()
        filtered = [
            p for p in filtered
            if (query_lower in p["code"].lower() or
                query_lower in p["shop"].lower() or
                query_lower in p.get("description", "").lower())
        ]

    # Фильтр по типу цветов
    if flower_type and flower_type != "all":
        filtered = [p for p in filtered if p.get("flower_type") == flower_type]

    # Фильтр по магазину
    if shop:
        shop_lower = shop.lower()
        filtered = [p for p in filtered if shop_lower in p["shop"].lower()]

    # Фильтр по скидке
    if min_discount is not None:
        filtered = [p for p in filtered if extract_discount_value(p["discount"]) >= min_discount]

    if max_discount is not None:
        filtered = [p for p in filtered if extract_discount_value(p["discount"]) <= max_discount]

    # Сортировка
    if sort_by == "newest":
        filtered.sort(key=lambda x: datetime.strptime(x["created_at"], "%d.%m.%Y %H:%M"), reverse=True)
    elif sort_by == "oldest":
        filtered.sort(key=lambda x: datetime.strptime(x["created_at"], "%d.%m.%Y %H:%M"))
    elif sort_by == "discount_high":
        filtered.sort(key=lambda x: extract_discount_value(x["discount"]), reverse=True)
    elif sort_by == "discount_low":
        filtered.sort(key=lambda x: extract_discount_value(x["discount"]))
    elif sort_by == "popular":
        filtered.sort(
            key=lambda x: popularity_stats.get(x["id"], {"copies": 0})["copies"],
            reverse=True
        )

    return templates.TemplateResponse("search.html", {
        "request": request,
        "username": username,
        "promocodes": filtered,
        "query": query,
        "flower_type": flower_type,
        "min_discount": min_discount,
        "max_discount": max_discount,
        "sort_by": sort_by,
        "shop": shop,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES,
        "is_owner": lambda promo: is_owner(promo, username)
    })


# ========== РЕЙТИНГ ПОПУЛЯРНОСТИ ==========
@app.get("/rating")
async def rating_page(request: Request):
    username = get_current_user(request)

    # Получаем промокоды с их популярностью
    promos_with_popularity = []
    for promo in promocodes_db:
        stats = popularity_stats.get(promo["id"], {"views": 0, "copies": 0, "clicks": 0})
        score = stats["copies"] * 3 + stats["views"] * 2 + stats["clicks"]
        promos_with_popularity.append({
            **promo,
            "popularity_score": score,
            "stats": stats
        })

    # Сортируем по популярности
    promos_with_popularity.sort(key=lambda x: x["popularity_score"], reverse=True)

    return templates.TemplateResponse("rating.html", {
        "request": request,
        "username": username,
        "promocodes": promos_with_popularity,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES,
        "is_owner": lambda promo: is_owner(promo, username)
    })


# ========== РЕКОМЕНДАЦИИ ==========
@app.get("/recommendations")
async def recommendations_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    recommendations = get_recommendations(username, 6)

    return templates.TemplateResponse("recommendations.html", {
        "request": request,
        "username": username,
        "recommendations": recommendations,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES
    })


# ========== ИНСТРУКЦИИ ПО ПРИМЕНЕНИЮ ==========
@app.get("/howto")
async def howto_page(request: Request):
    username = get_current_user(request)

    # Примеры инструкций для разных типов промокодов
    instructions = [
        {
            "title": "Промокоды на скидку в процентах",
            "icon": "fas fa-percentage",
            "steps": [
                "Выберите понравившийся промокод",
                "Скопируйте код (кнопка 'Копировать')",
                "Перейдите на сайт цветочного магазина",
                "Добавьте товары в корзину",
                "Введите промокод в специальное поле при оформлении заказа",
                "Нажмите 'Применить' и проверьте сумму заказа"
            ],
            "example": "Промокод 'SPRING30' даст скидку 30%"
        },
        {
            "title": "Промокоды с фиксированной суммой",
            "icon": "fas fa-ruble-sign",
            "steps": [
                "Найдите промокод с фиксированной скидкой",
                "Проверьте минимальную сумму заказа",
                "Скопируйте код",
                "На сайте магазина введите код на этапе оплаты",
                "Убедитесь, что сумма скидки применилась",
                "Завершите оформление заказа"
            ],
            "example": "Промокод 'FLOWER500' снизит стоимость заказа на 500 руб."
        },
        {
            "title": "Бесплатная доставка",
            "icon": "fas fa-truck",
            "steps": [
                "Ищите промокоды с пометкой 'бесплатная доставка'",
                "Обратите внимание на условия (часто требуется минимальная сумма)",
                "Скопируйте промокод",
                "При оформлении заказа введите код",
                "В стоимости заказа должна исчезнуть плата за доставку",
                "Если доставка не стала бесплатной, проверьте условия промокода"
            ],
            "example": "Промокод 'FREEDELIVERY' для бесплатной доставки"
        },
        {
            "title": "Подарочные сертификаты",
            "icon": "fas fa-gift",
            "steps": [
                "Найдите промокод-сертификат",
                "Проверьте номинал и срок действия",
                "Скопируйте код",
                "На сайте магазина введите код как промокод",
                "Сумма сертификата спишется с общей стоимости",
                "Оплатите остаток суммы (если требуется)"
            ],
            "example": "Промокод 'GIFT1000' эквивалентен подарочному сертификату на 1000 руб."
        }
    ]

    # Советы по экономии
    money_saving_tips = [
        "🎯 Подписывайтесь на рассылки цветочных магазинов - там часто публикуют эксклюзивные промокоды",
        "📅 Ищите промокоды перед праздниками (8 марта, День матери, День влюбленных) - скидки обычно больше",
        "🛒 Делайте заказы заранее - многие магазины дают скидки за предзаказ",
        "👥 Объединяйте заказы с друзьями - часто действуют скидки на крупные суммы",
        "⭐ Сохраняйте понравившиеся промокоды - они могут пригодиться в будущем",
        "🔔 Включайте уведомления на нашем сайте - мы сообщим о новых промокодах",
        "💬 Делитесь своими промокодами - чем больше пользователей, тем больше скидок для всех"
    ]

    return templates.TemplateResponse("howto.html", {
        "request": request,
        "username": username,
        "instructions": instructions,
        "money_saving_tips": money_saving_tips,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES
    })


# ========== ДОБАВЛЕНИЕ ПРОМОКОДА (обновлено для трекинга) ==========
@app.post("/add_promo")
async def add_promocode(request: Request,
                        code: str = Form(...),
                        shop: str = Form(...),
                        discount: str = Form(...),
                        description: str = Form(None),
                        flower_type: str = Form("Разные"),
                        usage_instructions: str = Form("")):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    global next_promo_id

    # Определяем тип скидки
    discount_type = "percentage" if "%" in discount else "fixed" if any(
        word in discount.lower() for word in ["руб", "р.", "рублей"]) else "other"

    # Создаем промокод
    promocode = {
        "id": next_promo_id,
        "code": code,
        "shop": shop,
        "discount": discount,
        "description": description or "",
        "usage_instructions": usage_instructions or "Скопируйте код и введите при оформлении заказа на сайте магазина",
        "flower_type": flower_type,
        "discount_type": discount_type,
        "discount_value": extract_discount_value(discount),
        "owner": username,
        "owner_color": get_random_color(),
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "expires_at": (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"),
        "is_active": True,
        "views": 0,
        "copies": 0,
        "clicks": 0,
        "emoji": FLOWER_TYPES.get(flower_type, "💐")
    }

    promocodes_db.append(promocode)
    popularity_stats[next_promo_id] = {"views": 0, "copies": 0, "clicks": 0}
    next_promo_id += 1

    return RedirectResponse("/", status_code=303)


# ========== API ДЛЯ ТРЕКИНГА ==========
@app.get("/track/{promo_id}/{action}")
async def track_action(promo_id: int, action: str):
    """Трекинг действий пользователей для статистики"""
    if promo_id in popularity_stats and action in ["view", "copy", "click"]:
        popularity_stats[promo_id][action] += 1
    return {"status": "tracked", "action": action}


# ========== ОСТАЛЬНЫЕ МАРШРУТЫ (как в предыдущей версии) ==========
@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "colors": FLOWER_COLORS
    })


@app.post("/register")
async def register_user(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users_db:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Это имя пользователя уже занято",
            "colors": FLOWER_COLORS
        })

    if len(username) < 3:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Имя пользователя должно быть не менее 3 символов",
            "colors": FLOWER_COLORS
        })

    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пароль должен быть не менее 6 символов",
            "colors": FLOWER_COLORS
        })

    users_db[username] = password

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="username", value=username)
    return response


@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "colors": FLOWER_COLORS
    })


@app.post("/login")
async def login_user(request: Request, username: str = Form(...), password: str = Form(...)):
    if username not in users_db or users_db[username] != password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль",
            "colors": FLOWER_COLORS
        })

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="username", value=username)
    return response


@app.get("/add_promo")
async def add_promo_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse("add_promo.html", {
        "request": request,
        "username": username,
        "colors": FLOWER_COLORS,
        "flower_types": FLOWER_TYPES
    })


@app.get("/my_promocodes")
async def my_promocodes_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    user_promocodes = [p for p in promocodes_db if p["owner"] == username]

    # Статистика пользователя
    user_stats = {
        "total": len(user_promocodes),
        "active": len([p for p in user_promocodes if p["is_active"]]),
        "total_copies": sum(popularity_stats.get(p["id"], {}).get("copies", 0) for p in user_promocodes),
        "total_views": sum(popularity_stats.get(p["id"], {}).get("views", 0) for p in user_promocodes),
        "total_clicks": sum(popularity_stats.get(p["id"], {}).get("clicks", 0) for p in user_promocodes)
    }

    return templates.TemplateResponse("my_promocodes.html", {
        "request": request,
        "username": username,
        "promocodes": user_promocodes,
        "stats": user_stats,
        "colors": FLOWER_COLORS,
        "random_color": get_random_color(),
        "flower_types": FLOWER_TYPES
    })


@app.get("/about")
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {
        "request": request,
        "username": get_current_user(request),
        "colors": FLOWER_COLORS,
        "flower_quote": get_flower_quote()
    })


@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(key="username")
    return response


# ========== ЗАПУСК СЕРВЕРА ==========
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🌸  ЦВЕТОЧНЫЕ ПРОМОКОДЫ 2.0 - СЕРВЕР ЗАПУЩЕН  🌸")
    print("=" * 60)
    print("🌐 Основной адрес: http://localhost:8000")
    print("🔍 Поиск и фильтры: http://localhost:8000/search")
    print("🏆 Рейтинг: http://localhost:8000/rating")
    print("💡 Рекомендации: http://localhost:8000/recommendations")
    print("📚 Инструкции: http://localhost:8000/howto")
    print("=" * 60)

    # Добавляем тестовые промокоды
    if not promocodes_db:
        test_promocodes = [
            {
                "id": 1,
                "code": "SPRING30",
                "shop": "Цветочный рай",
                "discount": "30% на весенние букеты",
                "description": "Скидка на все весенние композиции до конца месяца",
                "usage_instructions": "Введите код на этапе оплаты заказа",
                "flower_type": "Тюльпаны",
                "discount_type": "percentage",
                "discount_value": 30,
                "owner": "admin",
                "owner_color": FLOWER_COLORS["rose"],
                "created_at": "01.03.2024 10:00",
                "expires_at": "31.03.2024",
                "is_active": True,
                "views": 142,
                "copies": 89,
                "clicks": 45,
                "emoji": "🌷"
            },
            {
                "id": 2,
                "code": "LOVE2024",
                "shop": "Romantic Flowers",
                "discount": "500 руб. на букет роз",
                "description": "Специальное предложение для влюбленных",
                "usage_instructions": "Минимальная сумма заказа 2000 руб. Ввести при оформлении",
                "flower_type": "Розы",
                "discount_type": "fixed",
                "discount_value": 500,
                "owner": "user1",
                "owner_color": FLOWER_COLORS["lilac"],
                "created_at": "14.02.2024 18:30",
                "expires_at": "14.03.2024",
                "is_active": True,
                "views": 256,
                "copies": 134,
                "clicks": 78,
                "emoji": "🌹"
            },
            {
                "id": 3,
                "code": "SUNNY50",
                "shop": "Sunflower Delivery",
                "discount": "50% на подсолнухи",
                "description": "Яркие подсолнухи по специальной цене",
                "usage_instructions": "Действует только на подсолнухи. Ввести код в корзине",
                "flower_type": "Подсолнухи",
                "discount_type": "percentage",
                "discount_value": 50,
                "owner": "user2",
                "owner_color": FLOWER_COLORS["sunflower"],
                "created_at": "10.03.2024 09:15",
                "expires_at": "10.04.2024",
                "is_active": True,
                "views": 98,
                "copies": 45,
                "clicks": 32,
                "emoji": "🌻"
            },
            {
                "id": 4,
                "code": "ORCHID25",
                "shop": "Экзотик Флауэрс",
                "discount": "25% на орхидеи",
                "description": "Экзотические орхидеи со скидкой",
                "usage_instructions": "Активируется автоматически при добавлении орхидей в корзину",
                "flower_type": "Орхидеи",
                "discount_type": "percentage",
                "discount_value": 25,
                "owner": "admin",
                "owner_color": FLOWER_COLORS["violet"],
                "created_at": "05.03.2024 14:20",
                "expires_at": "05.04.2024",
                "is_active": True,
                "views": 76,
                "copies": 32,
                "clicks": 21,
                "emoji": "💮"
            },
            {
                "id": 5,
                "code": "FREESHIP",
                "shop": "Flower Express",
                "discount": "Бесплатная доставка",
                "description": "Бесплатная доставка по городу",
                "usage_instructions": "Минимальный заказ 1500 руб. Введите код на этапе выбора доставки",
                "flower_type": "Разные",
                "discount_type": "other",
                "discount_value": 0,
                "owner": "user1",
                "owner_color": FLOWER_COLORS["lavender"],
                "created_at": "20.03.2024 11:45",
                "expires_at": "20.04.2024",
                "is_active": True,
                "views": 120,
                "copies": 67,
                "clicks": 43,
                "emoji": "🚚"
            },
            {
                "id": 6,
                "code": "GIFT1000",
                "shop": "Подарочные цветы",
                "discount": "1000 руб. на первый заказ",
                "description": "Подарочный сертификат для новых клиентов",
                "usage_instructions": "Только для новых пользователей магазина. Ввести при регистрации",
                "flower_type": "Разные",
                "discount_type": "fixed",
                "discount_value": 1000,
                "owner": "admin",
                "owner_color": FLOWER_COLORS["peach"],
                "created_at": "15.03.2024 16:30",
                "expires_at": "15.06.2024",
                "is_active": True,
                "views": 89,
                "copies": 52,
                "clicks": 29,
                "emoji": "🎁"
            }
        ]

        promocodes_db.extend(test_promocodes)
        next_promo_id = 7

        # Инициализируем статистику
        for promo in test_promocodes:
            popularity_stats[promo["id"]] = {
                "views": promo["views"],
                "copies": promo["copies"],
                "clicks": promo["clicks"]
            }

        # Тестовые пользователи
        users_db["admin"] = "admin123"
        users_db["user1"] = "password1"
        users_db["user2"] = "password2"

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)