"""
Автоматизация входа на Tilda.ru с обходом капчи через RuCaptcha
"""

import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout
from captcha_solver import RuCaptchaSolver


# Загрузка переменных окружения
load_dotenv()

TILDA_EMAIL = os.getenv("TILDA_EMAIL")
TILDA_PASSWORD = os.getenv("TILDA_PASSWORD")
RUCAPTCHA_API_KEY = os.getenv("RUCAPTCHA_API_KEY")


def detect_captcha_type(page: Page) -> dict:
    """
    Определение типа капчи на странице

    Args:
        page: Страница Playwright

    Returns:
        Словарь с информацией о капче: {type: str, site_key: str}
    """
    print("Определение типа капчи...")

    # Проверка reCAPTCHA v2
    recaptcha_v2 = page.locator('iframe[src*="google.com/recaptcha"]').first
    if recaptcha_v2.count() > 0:
        try:
            # Получение site-key из родительского элемента
            site_key = page.evaluate("""() => {
                const elem = document.querySelector('.g-recaptcha');
                return elem ? elem.getAttribute('data-sitekey') : null;
            }""")
            if site_key:
                print(f"Обнаружена reCAPTCHA v2, site-key: {site_key}")
                return {"type": "recaptcha_v2", "site_key": site_key}
        except Exception as e:
            print(f"Ошибка при определении reCAPTCHA v2: {e}")

    # Проверка reCAPTCHA v3
    recaptcha_v3_key = page.evaluate("""() => {
        const scripts = Array.from(document.querySelectorAll('script'));
        for (const script of scripts) {
            const match = script.textContent?.match(/grecaptcha\\.execute\\(['"]([^'"]+)['"]/);
            if (match) return match[1];
        }
        return null;
    }""")
    if recaptcha_v3_key:
        print(f"Обнаружена reCAPTCHA v3, site-key: {recaptcha_v3_key}")
        return {"type": "recaptcha_v3", "site_key": recaptcha_v3_key}

    # Проверка hCaptcha
    hcaptcha = page.locator('iframe[src*="hcaptcha.com"]').first
    if hcaptcha.count() > 0:
        try:
            site_key = page.evaluate("""() => {
                const elem = document.querySelector('[data-sitekey]');
                return elem ? elem.getAttribute('data-sitekey') : null;
            }""")
            if site_key:
                print(f"Обнаружена hCaptcha, site-key: {site_key}")
                return {"type": "hcaptcha", "site_key": site_key}
        except Exception as e:
            print(f"Ошибка при определении hCaptcha: {e}")

    # Проверка Yandex SmartCaptcha
    yandex_captcha = page.evaluate("""() => {
        const elem = document.querySelector('[data-smartcaptcha-sitekey]');
        return elem ? elem.getAttribute('data-smartcaptcha-sitekey') : null;
    }""")
    if yandex_captcha:
        print(f"Обнаружена Yandex SmartCaptcha, site-key: {yandex_captcha}")
        return {"type": "yandex", "site_key": yandex_captcha}

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
            page.evaluate(f"""
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
            """)
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
        return True

    except Exception as e:
        print(f"Ошибка при внедрении токена: {e}")
        return False


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
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            # Переход на страницу входа
            print("Переход на страницу входа Tilda...")
            page.goto("https://tilda.ru/login/", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Ввод email
            print("Ввод email...")
            email_input = page.locator('input[name="email"], input[type="email"]').first
            email_input.fill(TILDA_EMAIL)
            page.wait_for_timeout(500)

            # Ввод пароля
            print("Ввод пароля...")
            password_input = page.locator('input[name="password"], input[type="password"]').first
            password_input.fill(TILDA_PASSWORD)
            page.wait_for_timeout(500)

            # Решение капчи если присутствует
            if not solve_and_inject_captcha(page, captcha_solver):
                print("Не удалось решить капчу")
                return False

            # Нажатие кнопки входа
            print("Нажатие кнопки входа...")
            login_button = page.locator('button[type="submit"], input[type="submit"]').first
            login_button.click()

            # Ожидание успешного входа
            print("Ожидание перенаправления...")
            try:
                # Ждем изменения URL или появления элементов личного кабинета
                page.wait_for_url("**/projects/**", timeout=15000)
                print("✓ Успешный вход в аккаунт Tilda!")

                # Сохранение скриншота
                page.screenshot(path="tilda_logged_in.png")
                print("Скриншот сохранен: tilda_logged_in.png")

                # Сохранение cookies для последующего использования
                cookies = context.cookies()
                print(f"Получено {len(cookies)} cookies")

                # Небольшая пауза для просмотра результата
                page.wait_for_timeout(3000)

                return True

            except PlaywrightTimeout:
                print("Ошибка: Таймаут при ожидании входа")
                print("Возможные причины:")
                print("  - Неверный email или пароль")
                print("  - Капча не была решена правильно")
                print("  - Проблемы с сетью")

                # Проверка на сообщения об ошибках
                error_messages = page.locator('.error, .alert-danger, [class*="error"]').all_text_contents()
                if error_messages:
                    print(f"Сообщения об ошибках: {error_messages}")

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
