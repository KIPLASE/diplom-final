from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uuid
from datetime import datetime
import random

app = FastAPI(title="🌸 Цветочные Промокоды", description="Самые выгодные скидки на цветы!")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Создаем папки
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Цветочная палитра для дизайна
FLOWER_COLORS = {
    "rose": "#FF69B4",  # Ярко-розовый
    "lilac": "#C8A2C8",  # Сиреневый
    "tulip": "#FF6347",  # Оранжево-красный
    "sunflower": "#FFD700",  # Золотой
    "lavender": "#E6E6FA",  # Лавандовый
    "leaf": "#32CD32",  # Зеленый
    "violet": "#8A2BE2",  # Фиолетовый
    "peach": "#FFDAB9"  # Персиковый
}

# Хранилище данных
users_db = {}
promocodes_db = []
next_promo_id = 1


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


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/")
async def home(request: Request):
    username = get_current_user(request)

    # Статистика для главной страницы
    stats = {
        "total_promos": len(promocodes_db),
        "active_users": len(users_db),
        "flower_quotes": get_flower_quote(),
        "random_emoji": get_random_flower_emoji()
    }

    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": username,
        "promocodes": promocodes_db,
        "is_owner": lambda promo: is_owner(promo, username),
        "stats": stats,
        "colors": FLOWER_COLORS,
        "random_color": get_random_color()
    })


# ========== РЕГИСТРАЦИЯ ==========
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


# ========== ВХОД ==========
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


# ========== ДОБАВЛЕНИЕ ПРОМОКОДА ==========
@app.get("/add_promo")
async def add_promo_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse("add_promo.html", {
        "request": request,
        "username": username,
        "colors": FLOWER_COLORS,
        "flower_types": ["Розы", "Тюльпаны", "Лилии", "Хризантемы", "Пионы", "Орхидеи", "Герберы", "Альстромерии"]
    })


@app.post("/add_promo")
async def add_promocode(request: Request,
                        code: str = Form(...),
                        shop: str = Form(...),
                        discount: str = Form(...),
                        description: str = Form(None),
                        flower_type: str = Form("Разные")):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    global next_promo_id

    # Создаем промокод
    promocode = {
        "id": next_promo_id,
        "code": code,
        "shop": shop,
        "discount": discount,
        "description": description or "",
        "flower_type": flower_type,
        "owner": username,
        "owner_color": get_random_color(),
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "expires_at": (datetime.now().replace(day=28)).strftime("%d.%m.%Y"),
        "is_active": True,
        "views": 0,
        "copies": 0,
        "emoji": get_random_flower_emoji()
    }

    promocodes_db.append(promocode)
    next_promo_id += 1

    return RedirectResponse("/", status_code=303)


# ========== РЕДАКТИРОВАНИЕ ==========
@app.get("/edit_promo/{promo_id}")
async def edit_promo_page(request: Request, promo_id: int):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для редактирования этого промокода",
            "colors": FLOWER_COLORS
        })

    return templates.TemplateResponse("edit_promo.html", {
        "request": request,
        "username": username,
        "promocode": promocode,
        "colors": FLOWER_COLORS
    })


@app.post("/edit_promo/{promo_id}")
async def edit_promocode(request: Request, promo_id: int,
                         code: str = Form(...),
                         shop: str = Form(...),
                         discount: str = Form(...),
                         description: str = Form(None)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для редактирования этого промокода",
            "colors": FLOWER_COLORS
        })

    promocode["code"] = code
    promocode["shop"] = shop
    promocode["discount"] = discount
    promocode["description"] = description or ""

    return RedirectResponse("/", status_code=303)


# ========== УДАЛЕНИЕ ==========
@app.get("/delete_promo/{promo_id}")
async def delete_promocode(request: Request, promo_id: int):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для удаления этого промокода",
            "colors": FLOWER_COLORS
        })

    promocodes_db[:] = [p for p in promocodes_db if p["id"] != promo_id]

    return RedirectResponse("/", status_code=303)


# ========== МОИ ПРОМОКОДЫ ==========
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
        "total_copies": sum(p.get("copies", 0) for p in user_promocodes),
        "total_views": sum(p.get("views", 0) for p in user_promocodes)
    }

    return templates.TemplateResponse("my_promocodes.html", {
        "request": request,
        "username": username,
        "promocodes": user_promocodes,
        "stats": user_stats,
        "colors": FLOWER_COLORS,
        "random_color": get_random_color()
    })


# ========== О САЙТЕ ==========
@app.get("/about")
async def about_page(request: Request):
    return templates.TemplateResponse("about.html", {
        "request": request,
        "username": get_current_user(request),
        "colors": FLOWER_COLORS,
        "flower_quote": get_flower_quote()
    })


# ========== ВЫХОД ==========
@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(key="username")
    return response


# ========== ЗАПУСК СЕРВЕРА ==========
if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("🌸  ЦВЕТОЧНЫЕ ПРОМОКОДЫ - СЕРВЕР ЗАПУЩЕН  🌸")
    print("=" * 50)
    print("🌐 Адрес: http://localhost:8000")
    print("🎨 Дизайн: Цветочная тема с градиентами")
    print("📊 Функции: Регистрация, промокоды, статистика")
    print("=" * 50)

    # Добавляем тестовые промокоды
    if not promocodes_db:
        test_promocodes = [
            {
                "id": 1,
                "code": "SPRING30",
                "shop": "Цветочный рай",
                "discount": "30% на весенние букеты",
                "description": "Скидка на все весенние композиции до конца месяца",
                "flower_type": "Тюльпаны",
                "owner": "admin",
                "owner_color": FLOWER_COLORS["rose"],
                "created_at": "01.03.2024 10:00",
                "expires_at": "31.03.2024",
                "is_active": True,
                "views": 142,
                "copies": 89,
                "emoji": "🌷"
            },
            {
                "id": 2,
                "code": "LOVE2024",
                "shop": "Romantic Flowers",
                "discount": "500 руб. на букет роз",
                "description": "Специальное предложение для влюбленных",
                "flower_type": "Розы",
                "owner": "user1",
                "owner_color": FLOWER_COLORS["lilac"],
                "created_at": "14.02.2024 18:30",
                "expires_at": "14.03.2024",
                "is_active": True,
                "views": 256,
                "copies": 134,
                "emoji": "🌹"
            },
            {
                "id": 3,
                "code": "SUNNY50",
                "shop": "Sunflower Delivery",
                "discount": "50% на подсолнухи",
                "description": "Яркие подсолнухи по специальной цене",
                "flower_type": "Подсолнухи",
                "owner": "user2",
                "owner_color": FLOWER_COLORS["sunflower"],
                "created_at": "10.03.2024 09:15",
                "expires_at": "10.04.2024",
                "is_active": True,
                "views": 98,
                "copies": 45,
                "emoji": "🌻"
            }
        ]

        promocodes_db.extend(test_promocodes)
        next_promo_id = 4

        # Тестовые пользователи
        users_db["admin"] = "admin123"
        users_db["user1"] = "password1"
        users_db["user2"] = "password2"

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)