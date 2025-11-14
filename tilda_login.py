"""
Автоматизация входа на Tilda.ru с обходом капчи через RuCaptcha
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout, Request
from captcha_solver import RuCaptchaSolver


# Загрузка переменных окружения
load_dotenv()

TILDA_EMAIL = os.getenv("TILDA_EMAIL")
TILDA_PASSWORD = os.getenv("TILDA_PASSWORD")
RUCAPTCHA_API_KEY = os.getenv("RUCAPTCHA_API_KEY")

# Путь к файлу сессии
SESSION_FILE = "tilda_session.json"


def detect_captcha_type(page: Page, wait_for_load: bool = True) -> dict:
    """
    Определение типа капчи на странице

    Args:
        page: Страница Playwright
        wait_for_load: Ожидать загрузки капчи

    Returns:
        Словарь с информацией о капче: {type: str, site_key: str}
    """
    print("Определение типа капчи...")

    if wait_for_load:
        print("Ожидание загрузки капчи...")
        # Ждем появления iframe капчи (до 10 секунд)
        try:
            page.wait_for_selector('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], iframe[src*="captcha-api.yandex"], iframe[src*="smartcaptcha"]', timeout=10000)
            page.wait_for_timeout(2000)  # Дополнительная пауза для полной загрузки
        except PlaywrightTimeout:
            print("Капча не загрузилась за отведенное время, продолжаем поиск...")

    # ВАЖНО: Проверяем Yandex ПЕРВЫМ, так как он тоже может использовать data-sitekey
    # Проверка Yandex SmartCaptcha
    print("Проверка Yandex SmartCaptcha...")
    try:
        yandex_info = page.evaluate("""() => {
            // Способ 1: проверка iframe с yandex
            const yandexIframe = document.querySelector('iframe[src*="smartcaptcha"], iframe[src*="captcha-api.yandex"]');
            if (yandexIframe) {
                // Ищем родительский элемент с ключом
                let parent = yandexIframe.parentElement;
                while (parent) {
                    const key = parent.getAttribute('data-sitekey') ||
                               parent.getAttribute('data-smartcaptcha-sitekey');
                    if (key) return key;
                    parent = parent.parentElement;
                }
            }

            // Способ 2: прямой поиск элемента с data-smartcaptcha-sitekey
            const elem = document.querySelector('[data-smartcaptcha-sitekey]');
            if (elem) return elem.getAttribute('data-smartcaptcha-sitekey');

            // Способ 3: поиск в скриптах
            const scripts = Array.from(document.querySelectorAll('script'));
            for (const script of scripts) {
                const text = script.textContent || script.innerHTML;
                if (text.includes('smartcaptcha') || text.includes('yandex')) {
                    const match = text.match(/sitekey['":\s]+['"]([^'"]+)['"]/i);
                    if (match) return match[1];
                }
            }

            return null;
        }""")
        if yandex_info:
            print(f"Обнаружена Yandex SmartCaptcha, site-key: {yandex_info}")
            return {"type": "yandex", "site_key": yandex_info}
    except Exception as e:
        print(f"Ошибка при определении Yandex SmartCaptcha: {e}")

    # Проверка hCaptcha
    print("Проверка hCaptcha...")
    hcaptcha_iframe = page.locator('iframe[src*="hcaptcha.com"]').first
    if hcaptcha_iframe.count() > 0:
        try:
            site_key = page.evaluate("""() => {
                const iframe = document.querySelector('iframe[src*="hcaptcha.com"]');
                if (iframe) {
                    // Ищем родительский элемент с data-sitekey
                    let parent = iframe.parentElement;
                    while (parent) {
                        const key = parent.getAttribute('data-sitekey');
                        if (key) return key;
                        parent = parent.parentElement;
                    }
                }
                return null;
            }""")
            if site_key:
                print(f"Обнаружена hCaptcha, site-key: {site_key}")
                return {"type": "hcaptcha", "site_key": site_key}
        except Exception as e:
            print(f"Ошибка при определении hCaptcha: {e}")

    # Проверка reCAPTCHA v2 - расширенный поиск
    print("Проверка reCAPTCHA v2...")
    try:
        # Несколько способов найти site-key
        site_key = page.evaluate("""() => {
            // Способ 1: стандартный элемент .g-recaptcha
            let elem = document.querySelector('.g-recaptcha');
            if (elem && elem.getAttribute('data-sitekey')) {
                return elem.getAttribute('data-sitekey');
            }

            // Способ 2: проверка iframe с google.com/recaptcha
            const recaptchaIframe = document.querySelector('iframe[src*="google.com/recaptcha"]');
            if (recaptchaIframe) {
                // Ищем родительский элемент с data-sitekey
                let parent = recaptchaIframe.parentElement;
                while (parent) {
                    const key = parent.getAttribute('data-sitekey');
                    if (key) return key;
                    parent = parent.parentElement;
                }

                // Пытаемся извлечь из src iframe
                const src = recaptchaIframe.getAttribute('src');
                const match = src.match(/[&?]k=([^&]+)/);
                if (match) return match[1];
            }

            // Способ 3: поиск в скриптах с упоминанием grecaptcha
            const scripts = Array.from(document.querySelectorAll('script'));
            for (const script of scripts) {
                const text = script.textContent || script.innerHTML;
                if (text.includes('grecaptcha') || text.includes('google.com/recaptcha')) {
                    const match = text.match(/['"&?]sitekey['"]?\s*[:=]\s*['"]([^'"]+)['"]/i);
                    if (match) return match[1];
                }
            }

            return null;
        }""")

        if site_key:
            print(f"Обнаружена reCAPTCHA v2, site-key: {site_key}")
            return {"type": "recaptcha_v2", "site_key": site_key}
    except Exception as e:
        print(f"Ошибка при определении reCAPTCHA v2: {e}")

    # Проверка reCAPTCHA v3
    print("Проверка reCAPTCHA v3...")
    recaptcha_v3_key = page.evaluate("""() => {
        const scripts = Array.from(document.querySelectorAll('script'));
        for (const script of scripts) {
            const text = script.textContent || script.innerHTML;
            const match = text.match(/grecaptcha\.execute\(['"]([^'"]+)['"]/);
            if (match) return match[1];
        }
        return null;
    }""")
    if recaptcha_v3_key:
        print(f"Обнаружена reCAPTCHA v3, site-key: {recaptcha_v3_key}")
        return {"type": "recaptcha_v3", "site_key": recaptcha_v3_key}

    print("Капча не обнаружена на странице")
    return {"type": None, "site_key": None}


def solve_and_inject_captcha(page: Page, captcha_solver: RuCaptchaSolver) -> bool:
    """
    Решение капчи и внедрение токена на страницу

    Args:
        page: Страница Playwright
        captcha_solver: Экземпляр решателя капчи

    Returns:
        True если капча решена успешно, False в противном случае
    """
    captcha_info = detect_captcha_type(page)

    if not captcha_info["type"]:
        print("Капча не требуется или не обнаружена")
        return True

    page_url = page.url
    site_key = captcha_info["site_key"]
    captcha_type = captcha_info["type"]

    print(f"Решение капчи типа: {captcha_type}")

    # Решение в зависимости от типа
    token = None
    if captcha_type == "recaptcha_v2":
        token = captcha_solver.solve_recaptcha_v2(site_key, page_url)
    elif captcha_type == "recaptcha_v3":
        token = captcha_solver.solve_recaptcha_v3(site_key, page_url)
    elif captcha_type == "hcaptcha":
        token = captcha_solver.solve_hcaptcha(site_key, page_url)
    elif captcha_type == "yandex":
        token = captcha_solver.solve_yandex_captcha(site_key, page_url)

    if not token:
        print("Не удалось решить капчу")
        return False

    # Внедрение токена
    print("Внедрение токена капчи...")
    try:
        if captcha_type == "recaptcha_v2":
            # Для reCAPTCHA v2 нужно установить токен в textarea и вызвать callback
            result = page.evaluate(f"""
                (function() {{
                    try {{
                        // Находим textarea для ответа
                        let textarea = document.getElementById('g-recaptcha-response');
                        if (!textarea) {{
                            textarea = document.querySelector('[name="g-recaptcha-response"]');
                        }}

                        if (textarea) {{
                            // Делаем textarea видимым временно
                            textarea.style.display = 'block';
                            textarea.innerHTML = '{token}';
                            textarea.value = '{token}';

                            // Вызываем callback если есть
                            const recaptchaElement = document.querySelector('.g-recaptcha');
                            if (recaptchaElement) {{
                                const callback = recaptchaElement.getAttribute('data-callback');
                                if (callback && typeof window[callback] === 'function') {{
                                    window[callback]('{token}');
                                }}
                            }}

                            // Проверяем наличие глобального callback
                            if (typeof window.onRecaptchaSuccess === 'function') {{
                                window.onRecaptchaSuccess('{token}');
                            }}

                            return 'success';
                        }}
                        return 'textarea not found';
                    }} catch(e) {{
                        return 'error: ' + e.message;
                    }}
                }})()
            """)
            print(f"Результат внедрения reCAPTCHA v2: {result}")

        elif captcha_type == "recaptcha_v3":
            page.evaluate(f"""
                document.querySelector('[name="g-recaptcha-response"]').value = '{token}';
            """)
        elif captcha_type == "hcaptcha":
            page.evaluate(f"""
                document.querySelector('[name="h-captcha-response"]').value = '{token}';
            """)
        elif captcha_type == "yandex":
            page.evaluate(f"""
                const input = document.querySelector('[name="smart-token"]');
                if (input) input.value = '{token}';
            """)

        print("Токен успешно внедрен")
        page.wait_for_timeout(1000)  # Пауза после внедрения
        return True

    except Exception as e:
        print(f"Ошибка при внедрении токена: {e}")
        return False


def save_session(context, filename: str = SESSION_FILE):
    """
    Сохранение сессии браузера в файл

    Args:
        context: Контекст браузера Playwright
        filename: Имя файла для сохранения
    """
    try:
        context.storage_state(path=filename)
        print(f"✓ Сессия сохранена в {filename}")
    except Exception as e:
        print(f"Ошибка сохранения сессии: {e}")


def load_session(filename: str = SESSION_FILE) -> dict:
    """
    Загрузка сохраненной сессии из файла

    Args:
        filename: Имя файла с сессией

    Returns:
        Словарь с данными сессии или None если файл не найден
    """
    if not Path(filename).exists():
        print(f"Файл сессии {filename} не найден")
        return None

    try:
        with open(filename, 'r') as f:
            session_data = json.load(f)
        print(f"✓ Сессия загружена из {filename}")
        return session_data
    except Exception as e:
        print(f"Ошибка загрузки сессии: {e}")
        return None


def setup_request_interceptor(page: Page):
    """
    Настройка перехватчика запросов для логирования API запросов к лидам

    Args:
        page: Страница Playwright
    """
    intercepted_requests = []

    def handle_request(request: Request):
        # Фильтруем запросы к API лидов
        if "projects/submit/leads" in request.url:
            try:
                post_data = request.post_data

                # Проверяем, содержит ли POST данные "comm": "getleads" или comm=getleads
                if post_data and ("comm=getleads" in post_data or '"comm": "getleads"' in post_data or '"comm":"getleads"' in post_data):
                    print("\n" + "="*70)
                    print("🎯 ПЕРЕХВАЧЕН ЦЕЛЕВОЙ ЗАПРОС getleads!")
                    print("="*70)

                    # Получаем заголовки
                    headers = dict(request.headers)

                    # Извлекаем cookies из заголовка
                    cookie_header = headers.get("cookie", "")
                    cookies_dict = {}
                    if cookie_header:
                        for cookie_pair in cookie_header.split("; "):
                            if "=" in cookie_pair:
                                key, value = cookie_pair.split("=", 1)
                                cookies_dict[key] = value

                    # Удаляем cookie из headers (будет отдельно)
                    headers_without_cookie = {k: v for k, v in headers.items() if k.lower() != "cookie"}

                    print("\n📍 URL запроса:")
                    print("-"*70)
                    print(f'burp0_url = "{request.url}"')

                    print("\n🍪 Cookies:")
                    print("-"*70)
                    formatted_cookies = "{" + ", ".join([f'"{k}": "{v}"' for k, v in cookies_dict.items()]) + "}"
                    print(f"burp0_cookies = {formatted_cookies}")

                    print("\n📋 Headers:")
                    print("-"*70)
                    formatted_headers = "{" + ", ".join([f'"{k}": "{v}"' for k, v in headers_without_cookie.items()]) + "}"
                    print(f"burp0_headers = {formatted_headers}")

                    print("\n📦 POST Data:")
                    print("-"*70)
                    print(post_data)

                    print("\n" + "="*70)
                    print("✅ Данные готовы для повторного использования!")
                    print("="*70 + "\n")

                    # Сохраняем для дальнейшего использования
                    intercepted_requests.append({
                        "url": request.url,
                        "method": request.method,
                        "headers": headers_without_cookie,
                        "cookies": cookies_dict,
                        "post_data": post_data
                    })
            except Exception as e:
                print(f"Ошибка при обработке запроса: {e}")

    page.on("request", handle_request)
    return intercepted_requests


def format_cookies_for_burp(cookies: list) -> str:
    """
    Форматирование cookies в формат Burp Suite (Python dict)

    Args:
        cookies: Список cookies от Playwright

    Returns:
        Строка с форматированными cookies в виде Python словаря
    """
    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}

    # Форматируем в виде Python словаря с кавычками
    formatted_items = [f'"{key}": "{value}"' for key, value in cookie_dict.items()]
    formatted_dict = "{" + ", ".join(formatted_items) + "}"

    return f"burp0_cookies = {formatted_dict}"


def login_to_tilda(headless: bool = False, slow_mo: int = 0) -> bool:
    """
    Основная функция входа на Tilda

    Args:
        headless: Запуск браузера в фоновом режиме
        slow_mo: Задержка между действиями в миллисекундах (для отладки)

    Returns:
        True если вход выполнен успешно, False в противном случае
    """
    # Проверка наличия необходимых переменных
    if not all([TILDA_EMAIL, TILDA_PASSWORD, RUCAPTCHA_API_KEY]):
        print("Ошибка: Не все переменные окружения заданы!")
        print("Создайте .env файл на основе .env.example")
        return False

    # Инициализация решателя капчи
    captcha_solver = RuCaptchaSolver(RUCAPTCHA_API_KEY)

    # Проверка баланса
    balance = captcha_solver.get_balance()
    if balance is not None and balance < 1:
        print("Предупреждение: Низкий баланс RuCaptcha!")

    with sync_playwright() as p:
        # Запуск браузера
        print("Запуск браузера...")
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)

        # Попытка загрузить сохраненную сессию
        session_data = load_session()

        # Создание контекста с сессией или без
        if session_data:
            print("Попытка использовать сохраненную сессию...")
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                storage_state=session_data
            )
        else:
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

        page = context.new_page()

        # Настройка перехватчика запросов
        intercepted_requests = setup_request_interceptor(page)

        try:
            # Проверка валидности сохраненной сессии
            if session_data:
                print("Проверка валидности сессии...")
                try:
                    leads_url = "https://tilda.ru/projects/leads/?projectid=2050405"
                    page.goto(leads_url, wait_until="networkidle", timeout=15000)
                    page.wait_for_timeout(2000)

                    # Проверяем, не попали ли мы на страницу логина
                    current_url = page.url
                    if "/login" in current_url.lower():
                        print("⚠ Сессия устарела, требуется повторный вход")
                        session_data = None  # Сбрасываем сессию
                    else:
                        print("✓ Сессия валидна! Пропускаем авторизацию")

                        # Ждем загрузку API запроса
                        page.wait_for_timeout(3000)

                        # Вывод cookies
                        cookies = context.cookies()
                        print(f"\nПолучено {len(cookies)} cookies")
                        burp_cookies = format_cookies_for_burp(cookies)
                        print("\n" + "="*60)
                        print("Cookies в формате Burp Suite:")
                        print("="*60)
                        print(burp_cookies)
                        print("="*60)

                        # Скриншот
                        page.screenshot(path="tilda_logged_in.png")
                        print("\nСкриншот сохранен: tilda_logged_in.png")

                        return True
                except Exception as e:
                    print(f"Ошибка проверки сессии: {e}")
                    session_data = None

            # Если сессии нет или она невалидна - выполняем обычный вход
            # Переход на страницу входа
            print("Переход на страницу входа Tilda...")
            page.goto("https://tilda.ru/login/", wait_until="networkidle")
            print("Страница загружена, ожидание загрузки всех элементов...")
            page.wait_for_timeout(3000)

            # Проверка и решение капчи ПЕРЕД заполнением формы (опционально)
            print("\n--- Этап 1: Определение и решение капчи ---")
            captcha_result = solve_and_inject_captcha(page, captcha_solver)
            if not captcha_result:
                print("Предупреждение: Капча не была решена (возможно, её нет на странице)")
                # Не возвращаем False - продолжаем, так как капча может быть необязательной

            print("\n--- Этап 2: Заполнение формы входа ---")
            # Ввод email
            print("Ввод email...")
            email_input = page.locator('input[name="email"], input[type="email"]').first
            email_input.fill(TILDA_EMAIL)
            page.wait_for_timeout(500)

            # Ввод пароля
            print("Ввод пароля...")
            password_input = page.locator('input[name="password"], input[type="password"]').first
            password_input.fill(TILDA_PASSWORD)
            page.wait_for_timeout(1000)

            # Скриншот перед отправкой
            page.screenshot(path="tilda_before_submit.png")
            print("Скриншот сохранен: tilda_before_submit.png")

            # Нажатие кнопки входа
            print("\n--- Этап 3: Отправка формы ---")
            print("Нажатие кнопки входа...")
            login_button = page.locator('button[type="submit"], input[type="submit"]').first
            login_button.click()

            # Ожидание успешного входа
            print("Ожидание перенаправления...")
            page.wait_for_timeout(3000)  # Даем время на обработку

            # Проверяем успешность входа несколькими способами
            current_url = page.url
            print(f"Текущий URL: {current_url}")

            # Способ 1: Проверка URL (исключаем страницу логина)
            is_login_page = "/login" in current_url.lower()

            # Способ 2: Проверка отсутствия формы входа
            login_form_exists = page.locator('form:has(input[type="password"])').count() > 0

            # Способ 3: Проверка наличия элементов личного кабинета
            dashboard_elements = page.locator('[class*="dashboard"], [class*="projects"], [class*="header-user"], .tn-top-panel').count()

            # Способ 4: Проверка на наличие ошибок входа
            error_text = page.locator('.error, .alert-danger, [class*="error-message"]').first
            has_login_error = error_text.count() > 0

            print(f"Анализ состояния:")
            print(f"  - Страница логина: {is_login_page}")
            print(f"  - Форма входа существует: {login_form_exists}")
            print(f"  - Элементы личного кабинета найдены: {dashboard_elements}")
            print(f"  - Ошибки входа: {has_login_error}")

            # Определяем успешность входа
            if not is_login_page and not login_form_exists and dashboard_elements > 0:
                print("\n✓ Успешный вход в аккаунт Tilda!")

                # Переход на страницу лидов
                print("\n--- Этап 4: Переход на страницу лидов ---")
                leads_url = "https://tilda.ru/projects/leads/?projectid=2050405"
                print(f"Переход на {leads_url}...")
                page.goto(leads_url, wait_until="networkidle")
                page.wait_for_timeout(3000)  # Ждем API запросы
                print("Страница лидов загружена")

                # Сохранение сессии для последующего использования
                print("\n--- Сохранение сессии ---")
                save_session(context)

                # Сохранение скриншота
                page.screenshot(path="tilda_logged_in.png")
                print("Скриншот сохранен: tilda_logged_in.png")

                # Получение и вывод cookies для Burp Suite
                cookies = context.cookies()
                print(f"\nПолучено {len(cookies)} cookies")

                # Форматирование cookies для Burp Suite
                burp_cookies = format_cookies_for_burp(cookies)
                print("\n" + "="*60)
                print("Cookies в формате Burp Suite:")
                print("="*60)
                print(burp_cookies)
                print("="*60)

                # Небольшая пауза для просмотра результата
                page.wait_for_timeout(2000)

                return True

            elif not is_login_page and not login_form_exists:
                # Вход выполнен, но элементы кабинета не найдены
                print("\n✓ Вход выполнен (форма логина исчезла, но элементы кабинета не определены)")
                print("Это может быть нормально, если структура страницы отличается")

                # Переход на страницу лидов
                print("\n--- Этап 4: Переход на страницу лидов ---")
                leads_url = "https://tilda.ru/projects/leads/?projectid=2050405"
                print(f"Переход на {leads_url}...")
                page.goto(leads_url, wait_until="networkidle")
                page.wait_for_timeout(3000)  # Ждем API запросы
                print("Страница лидов загружена")

                # Сохранение сессии для последующего использования
                print("\n--- Сохранение сессии ---")
                save_session(context)

                # Сохранение скриншота
                page.screenshot(path="tilda_logged_in.png")
                print("Скриншот сохранен: tilda_logged_in.png")

                # Получение и вывод cookies для Burp Suite
                cookies = context.cookies()
                print(f"\nПолучено {len(cookies)} cookies")

                # Форматирование cookies для Burp Suite
                burp_cookies = format_cookies_for_burp(cookies)
                print("\n" + "="*60)
                print("Cookies в формате Burp Suite:")
                print("="*60)
                print(burp_cookies)
                print("="*60)

                return True

            else:
                print("\n✗ Ошибка: Вход не выполнен")
                print("Возможные причины:")
                print("  - Неверный email или пароль")
                print("  - Капча не была решена правильно")
                print("  - Проблемы с сетью")

                # Проверка на сообщения об ошибках
                if has_login_error:
                    error_messages = page.locator('.error, .alert-danger, [class*="error"]').all_text_contents()
                    print(f"Сообщения об ошибках: {[msg for msg in error_messages if msg.strip()][:5]}")  # Показываем только первые 5

                page.screenshot(path="tilda_error.png")
                print("Скриншот ошибки сохранен: tilda_error.png")

                return False

        except Exception as e:
            print(f"Произошла ошибка: {e}")
            page.screenshot(path="tilda_exception.png")
            print("Скриншот ошибки сохранен: tilda_exception.png")
            return False

        finally:
            browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Автоматизация входа на Tilda.ru с обходом капчи")
    print("=" * 60)
    print()

    # Запуск с видимым браузером для отладки
    # Для фонового режима установите headless=True
    success = login_to_tilda(headless=False, slow_mo=100)

    if success:
        print("\n✓ Скрипт завершен успешно!")
        exit(0)
    else:
        print("\n✗ Скрипт завершен с ошибкой")
        exit(1)
