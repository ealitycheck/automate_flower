"""
Модуль для решения капчи через RuCaptcha API
Поддерживает: reCAPTCHA v2, reCAPTCHA v3, hCaptcha, Yandex Captcha
"""

import time
import requests
from typing import Optional


class RuCaptchaSolver:
    """Класс для работы с RuCaptcha API"""

    def __init__(self, api_key: str):
        """
        Инициализация решателя капчи

        Args:
            api_key: API ключ от RuCaptcha
        """
        self.api_key = api_key
        self.base_url = "https://rucaptcha.com"

    def solve_recaptcha_v2(self, site_key: str, page_url: str, timeout: int = 120) -> Optional[str]:
        """
        Решение reCAPTCHA v2

        Args:
            site_key: Ключ сайта (data-sitekey)
            page_url: URL страницы с капчей
            timeout: Максимальное время ожидания решения в секундах

        Returns:
            Токен решения капчи или None в случае ошибки
        """
        # Отправка капчи на решение
        response = requests.post(f"{self.base_url}/in.php", data={
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1
        })

        result = response.json()
        if result.get("status") != 1:
            print(f"Ошибка отправки капчи: {result.get('request')}")
            return None

        captcha_id = result.get("request")
        print(f"Капча отправлена на решение. ID: {captcha_id}")

        # Ожидание решения
        return self._wait_for_result(captcha_id, timeout)

    def solve_recaptcha_v3(self, site_key: str, page_url: str, action: str = "verify",
                           min_score: float = 0.3, timeout: int = 120) -> Optional[str]:
        """
        Решение reCAPTCHA v3

        Args:
            site_key: Ключ сайта
            page_url: URL страницы с капчей
            action: Действие (обычно 'verify' или 'submit')
            min_score: Минимальный требуемый score (0.1 - 0.9)
            timeout: Максимальное время ожидания решения в секундах

        Returns:
            Токен решения капчи или None в случае ошибки
        """
        response = requests.post(f"{self.base_url}/in.php", data={
            "key": self.api_key,
            "method": "userrecaptcha",
            "version": "v3",
            "googlekey": site_key,
            "pageurl": page_url,
            "action": action,
            "min_score": min_score,
            "json": 1
        })

        result = response.json()
        if result.get("status") != 1:
            print(f"Ошибка отправки капчи: {result.get('request')}")
            return None

        captcha_id = result.get("request")
        print(f"ReCAPTCHA v3 отправлена на решение. ID: {captcha_id}")

        return self._wait_for_result(captcha_id, timeout)

    def solve_hcaptcha(self, site_key: str, page_url: str, timeout: int = 120) -> Optional[str]:
        """
        Решение hCaptcha

        Args:
            site_key: Ключ сайта
            page_url: URL страницы с капчей
            timeout: Максимальное время ожидания решения в секундах

        Returns:
            Токен решения капчи или None в случае ошибки
        """
        response = requests.post(f"{self.base_url}/in.php", data={
            "key": self.api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1
        })

        result = response.json()
        if result.get("status") != 1:
            print(f"Ошибка отправки капчи: {result.get('request')}")
            return None

        captcha_id = result.get("request")
        print(f"hCaptcha отправлена на решение. ID: {captcha_id}")

        return self._wait_for_result(captcha_id, timeout)

    def solve_yandex_captcha(self, site_key: str, page_url: str, timeout: int = 120) -> Optional[str]:
        """
        Решение Yandex SmartCaptcha

        Args:
            site_key: Ключ сайта
            page_url: URL страницы с капчей
            timeout: Максимальное время ожидания решения в секундах

        Returns:
            Токен решения капчи или None в случае ошибки
        """
        response = requests.post(f"{self.base_url}/in.php", data={
            "key": self.api_key,
            "method": "yandex",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1
        })

        result = response.json()
        if result.get("status") != 1:
            print(f"Ошибка отправки капчи: {result.get('request')}")
            return None

        captcha_id = result.get("request")
        print(f"Yandex Captcha отправлена на решение. ID: {captcha_id}")

        return self._wait_for_result(captcha_id, timeout)

    def _wait_for_result(self, captcha_id: str, timeout: int) -> Optional[str]:
        """
        Ожидание результата решения капчи

        Args:
            captcha_id: ID капчи
            timeout: Максимальное время ожидания в секундах

        Returns:
            Токен решения капчи или None в случае ошибки
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(5)  # Проверка каждые 5 секунд

            response = requests.get(f"{self.base_url}/res.php", params={
                "key": self.api_key,
                "action": "get",
                "id": captcha_id,
                "json": 1
            })

            result = response.json()

            if result.get("status") == 1:
                token = result.get("request")
                print(f"Капча решена успешно!")
                return token
            elif result.get("request") == "CAPCHA_NOT_READY":
                print("Капча еще решается...")
                continue
            else:
                print(f"Ошибка получения результата: {result.get('request')}")
                return None

        print("Превышено время ожидания решения капчи")
        return None

    def get_balance(self) -> Optional[float]:
        """
        Получение баланса аккаунта RuCaptcha

        Returns:
            Баланс в рублях или None в случае ошибки
        """
        response = requests.get(f"{self.base_url}/res.php", params={
            "key": self.api_key,
            "action": "getbalance",
            "json": 1
        })

        result = response.json()
        if result.get("status") == 1:
            balance = float(result.get("request", 0))
            print(f"Баланс RuCaptcha: {balance} руб.")
            return balance
        else:
            print(f"Ошибка получения баланса: {result.get('request')}")
            return None
