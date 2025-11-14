# Автоматизация входа на Tilda.ru с обходом капчи

Этот проект автоматизирует процесс входа на платформу Tilda.ru с использованием Playwright и обходом Google reCAPTCHA, Yandex SmartCaptcha через сервис RuCaptcha.

## Возможности

- Автоматический вход на tilda.ru/login
- Поддержка различных типов капчи:
  - Google reCAPTCHA v2
  - Google reCAPTCHA v3
  - hCaptcha
  - Yandex SmartCaptcha
- Автоматическое определение типа капчи с приоритетом
- Решение капчи через RuCaptcha API
- Переход на страницу лидов после входа
- Экспорт cookies в формате Burp Suite (Python dict)
- Сохранение скриншотов результата
- Проверка баланса RuCaptcha
- Режимы отладки (headless/headed)
- Множественная проверка успешности входа

## Требования

- Python 3.8+
- Аккаунт на [RuCaptcha](https://rucaptcha.com/) с положительным балансом

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd automate_flower
```

### 2. Создание виртуального окружения

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Установка браузеров Playwright

```bash
playwright install chromium
```

### 5. Настройка переменных окружения

Скопируйте файл `.env.example` в `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл и укажите свои данные:

```env
# Tilda credentials
TILDA_EMAIL=your_email@example.com
TILDA_PASSWORD=your_password

# RuCaptcha API key (get it from https://rucaptcha.com/)
RUCAPTCHA_API_KEY=your_rucaptcha_api_key
```

### Как получить API ключ RuCaptcha:

1. Зарегистрируйтесь на https://rucaptcha.com/
2. Пополните баланс (минимум ~10 рублей)
3. Скопируйте API ключ из личного кабинета
4. Вставьте его в `.env` файл

## Использование

### Запуск с видимым браузером (для отладки)

```bash
python tilda_login.py
```

### Запуск в фоновом режиме

Отредактируйте `tilda_login.py` и измените параметр:

```python
success = login_to_tilda(headless=True, slow_mo=0)
```

Затем запустите:

```bash
python tilda_login.py
```

## Структура проекта

```
automate_flower/
├── captcha_solver.py    # Модуль для работы с RuCaptcha API
├── tilda_login.py       # Основной скрипт автоматизации
├── requirements.txt     # Зависимости проекта
├── .env.example         # Шаблон переменных окружения
├── .env                 # Ваши настройки (не коммитится)
├── .gitignore          # Игнорируемые файлы
└── README.md           # Документация
```

## Логика работы

1. **Инициализация**: Загрузка переменных окружения и создание экземпляра решателя капчи
2. **Проверка баланса**: Проверка баланса RuCaptcha перед началом работы
3. **Запуск браузера**: Открытие Chromium через Playwright
4. **Переход на страницу входа**: Навигация на https://tilda.ru/login/
5. **Определение капчи**: Автоматическое определение типа капчи (Yandex → hCaptcha → reCAPTCHA v2 → v3)
6. **Решение капчи**: Отправка капчи в RuCaptcha и получение токена (если капча обнаружена)
7. **Внедрение токена**: Подстановка токена в форму и вызов callback-функций
8. **Заполнение формы**: Ввод email и пароля
9. **Отправка формы**: Клик по кнопке входа
10. **Проверка успеха**: Множественная проверка (URL, форма входа, элементы кабинета, ошибки)
11. **Переход на страницу лидов**: Автоматический переход на страницу leads с projectid=2050405
12. **Экспорт cookies**: Извлечение и форматирование cookies в формате Burp Suite
13. **Сохранение результата**: Создание скриншота страницы лидов

## Примеры использования

### Базовое использование

```python
from tilda_login import login_to_tilda

# Запуск с видимым браузером
success = login_to_tilda(headless=False, slow_mo=100)

if success:
    print("Вход выполнен успешно!")
else:
    print("Ошибка при входе")
```

### Использование модуля решения капчи отдельно

```python
from captcha_solver import RuCaptchaSolver

solver = RuCaptchaSolver("your_api_key")

# Проверка баланса
balance = solver.get_balance()

# Решение reCAPTCHA v2
token = solver.solve_recaptcha_v2(
    site_key="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
    page_url="https://example.com"
)

# Решение Yandex Captcha
token = solver.solve_yandex_captcha(
    site_key="ysc1_...",
    page_url="https://example.com"
)
```

### Пример вывода cookies

После успешного входа скрипт выводит cookies в формате Burp Suite:

```
============================================================
Cookies в формате Burp Suite:
============================================================
burp0_cookies = {"registered": "yes", "deviceid": "xcj8EP", "__ddg1_": "z9dVPCVAXugpHR", "PHPSESSID": "kmen31b5k7gjafs3b3gm", "userid": "1017", "hash": "9cb8b968a3b71b41a3", "lang": "RU"}
============================================================
```

Эти cookies можно скопировать и использовать в:
- **Burp Suite** для тестирования безопасности
- **Postman** для API запросов
- **Python requests** для автоматизации
- Любых других HTTP-клиентах

## Отладка

### Включение режима медленного выполнения

Для лучшего наблюдения за процессом увеличьте параметр `slow_mo`:

```python
success = login_to_tilda(headless=False, slow_mo=500)
```

### Анализ скриншотов

После выполнения скрипта создаются скриншоты:
- `tilda_before_submit.png` - страница входа перед отправкой формы
- `tilda_logged_in.png` - страница лидов после успешного входа
- `tilda_error.png` - ошибка при входе
- `tilda_exception.png` - критическая ошибка

### Проверка логов

Скрипт выводит подробную информацию о каждом шаге:
- Определение типа капчи
- Статус решения капчи
- Результаты действий

## Возможные проблемы

### 1. Ошибка "Неверный API ключ"

**Решение**: Проверьте правильность API ключа в `.env` файле

### 2. Ошибка "Недостаточно средств"

**Решение**: Пополните баланс на RuCaptcha.com

### 3. Таймаут при решении капчи

**Решение**:
- Проверьте баланс RuCaptcha
- Убедитесь в наличии интернет-соединения
- Попробуйте увеличить таймаут в `captcha_solver.py`

### 4. Капча не определяется

**Решение**:
- Проверьте, действительно ли на странице есть капча
- Возможно, Tilda использует другой тип капчи - добавьте поддержку в `detect_captcha_type()`

### 5. "Неверный email или пароль"

**Решение**: Проверьте правильность учетных данных в `.env` файле

## Стоимость

Примерная стоимость решения капчи на RuCaptcha:
- reCAPTCHA v2: ~0.25-0.5 руб
- reCAPTCHA v3: ~0.5-1 руб
- Yandex Captcha: ~0.5-1 руб
- hCaptcha: ~0.25-0.5 руб

## Безопасность

⚠️ **Важно**:
- Файл `.env` содержит конфиденциальные данные
- Никогда не коммитьте `.env` в репозиторий
- Используйте разные пароли для разных сервисов
- Храните API ключи в безопасности

## Лицензия

MIT

## Поддержка

При возникновении проблем:
1. Проверьте логи выполнения
2. Изучите созданные скриншоты
3. Убедитесь в правильности настроек `.env`
4. Проверьте баланс RuCaptcha

## API RuCaptcha документация

Официальная документация: https://rucaptcha.com/api-rucaptcha

## Playwright документация

Официальная документация: https://playwright.dev/python/
