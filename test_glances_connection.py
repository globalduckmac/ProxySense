#!/usr/bin/env python3
"""
Тест подключения к Glances API для диагностики проблем.
"""
import asyncio
import httpx
import time
import sys
from typing import Optional

async def test_glances_url(url: str, timeout: int = 30) -> dict:
    """Тестирует подключение к Glances API."""
    results = {
        'url': url,
        'timeout': timeout,
        'success': False,
        'status_code': None,
        'response_time': 0,
        'data_size': 0,
        'error': None
    }
    
    start_time = time.time()
    
    try:
        timeout_config = httpx.Timeout(
            connect=10.0,
            read=timeout,
            write=10.0,
            pool=10.0
        )
        
        async with httpx.AsyncClient(
            timeout=timeout_config,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={"User-Agent": "Reverse-Proxy-Monitor-Test/1.0"}
        ) as client:
            
            print(f"🔍 Тестирование подключения к {url}...")
            
            response = await client.get(url)
            
            end_time = time.time()
            results['response_time'] = round(end_time - start_time, 2)
            results['status_code'] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                results['data_size'] = len(str(data))
                results['success'] = True
                
                print(f"✅ Подключение успешно!")
                print(f"   Статус: {response.status_code}")
                print(f"   Время ответа: {results['response_time']}s")
                print(f"   Размер данных: {results['data_size']} символов")
                
                # Проверяем ключевые поля в ответе
                key_fields = ['cpu', 'mem', 'load', 'uptime']
                found_fields = [field for field in key_fields if field in data]
                print(f"   Найденные поля: {', '.join(found_fields)}")
                
            else:
                results['error'] = f"HTTP {response.status_code}"
                print(f"❌ Ошибка HTTP: {response.status_code}")
                print(f"   Ответ: {response.text[:200]}")
    
    except httpx.TimeoutException as e:
        end_time = time.time()
        results['response_time'] = round(end_time - start_time, 2)
        results['error'] = f"Timeout: {str(e)}"
        print(f"⏰ Таймаут ({results['response_time']}s): {e}")
        
    except httpx.ConnectError as e:
        end_time = time.time()
        results['response_time'] = round(end_time - start_time, 2)
        results['error'] = f"Connection Error: {str(e)}"
        print(f"🔌 Ошибка подключения: {e}")
        
    except Exception as e:
        end_time = time.time()
        results['response_time'] = round(end_time - start_time, 2)
        results['error'] = f"Unexpected: {str(e)}"
        print(f"❌ Неожиданная ошибка: {e}")
    
    return results

async def test_multiple_timeouts(url: str):
    """Тестирует разные таймауты."""
    timeouts = [5, 10, 15, 30, 60]
    
    print(f"\n🧪 Тестирование различных таймаутов для {url}\n")
    
    results = []
    for timeout in timeouts:
        print(f"--- Тест с таймаутом {timeout}s ---")
        result = await test_glances_url(url, timeout)
        results.append(result)
        print()
        
        # Если удачно с текущим таймаутом, останавливаемся
        if result['success']:
            print(f"🎯 Оптимальный таймаут найден: {timeout}s")
            break
    
    return results

def print_summary(results: list):
    """Выводит сводку результатов."""
    print("\n" + "="*60)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("="*60)
    
    for result in results:
        status = "✅ Успех" if result['success'] else "❌ Ошибка"
        print(f"Таймаут: {result['timeout']}s | {status} | Время: {result['response_time']}s")
        if result['error']:
            print(f"   Ошибка: {result['error']}")
    
    # Рекомендации
    successful_results = [r for r in results if r['success']]
    if successful_results:
        min_timeout = min(r['timeout'] for r in successful_results)
        avg_time = sum(r['response_time'] for r in successful_results) / len(successful_results)
        
        print(f"\n🎯 РЕКОМЕНДАЦИИ:")
        print(f"   Минимальный рабочий таймаут: {min_timeout}s")
        print(f"   Среднее время ответа: {round(avg_time, 2)}s")
        print(f"   Рекомендуемый таймаут: {max(min_timeout + 5, 30)}s")
    else:
        print(f"\n⚠️  НИ ОДИН ТЕСТ НЕ ПРОШЕЛ УСПЕШНО")
        print(f"   Проверьте доступность Glances API")
        print(f"   Убедитесь что URL корректен")

async def main():
    if len(sys.argv) < 2:
        print("Использование: python3 test_glances_connection.py <glances_url>")
        print("Пример: python3 test_glances_connection.py http://109.120.150.248:61208/api/4/all")
        sys.exit(1)
    
    url = sys.argv[1]
    
    print("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ К GLANCES API")
    print("="*60)
    print(f"URL: {url}")
    print(f"Время запуска: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Сначала быстрый тест
    print(f"\n🚀 Быстрый тест с таймаутом 10s:")
    quick_result = await test_glances_url(url, 10)
    
    if quick_result['success']:
        print(f"\n🎉 Быстрый тест прошел успешно! API работает.")
    else:
        print(f"\n🔄 Быстрый тест не прошел. Запускаем детальное тестирование...")
        results = await test_multiple_timeouts(url)
        print_summary(results)

if __name__ == "__main__":
    asyncio.run(main())