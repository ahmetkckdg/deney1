#!/usr/bin/env python3
"""
TheEyeTribe istek formatını test eder
Farklı formatları deneyerek doğru formatı bulur
"""

import socket
import json
import time

def test_request_format(host='localhost', port=6555):
    """Farklı istek formatlarını test eder"""
    print("=" * 60)
    print("İSTEK FORMATI TESTİ")
    print("=" * 60)
    
    # Socket bağlantısı
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        print("✓ Socket bağlantısı başarılı\n")
    except Exception as e:
        print("✗ Socket bağlantısı başarısız: {}".format(e))
        return
    
    # Test 1: Mevcut format (nested params)
    print("Test 1: Nested params formatı")
    request1 = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "get",
        "params": {
            "category": "tracker",
            "request": "version"
        }
    }
    test_request(sock, request1, "Test 1")
    
    # Test 2: Flat params format
    print("\nTest 2: Flat params formatı")
    request2 = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "get",
        "params": {
            "category": "tracker",
            "request": "version"
        }
    }
    test_request(sock, request2, "Test 2")
    
    # Test 3: Array params format
    print("\nTest 3: Array params formatı")
    request3 = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "get",
        "params": ["tracker", "version"]
    }
    test_request(sock, request3, "Test 3")
    
    # Test 4: Direct method call
    print("\nTest 4: Direct method call")
    request4 = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tracker.get",
        "params": {
            "request": "version"
        }
    }
    test_request(sock, request4, "Test 4")
    
    # Test 5: Minimal format
    print("\nTest 5: Minimal format")
    request5 = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "get",
        "params": {
            "category": "tracker",
            "request": "version"
        }
    }
    test_request(sock, request5, "Test 5")
    
    sock.close()
    print("\n" + "=" * 60)

def test_request(sock, request, test_name):
    """Bir isteği test eder"""
    try:
        message = json.dumps(request) + '\r\n'
        print("  Gönderilen: {}".format(message.strip()))
        
        sock.sendall(message.encode('utf-8'))
        
        # Yanıt bekle
        sock.settimeout(3.0)
        response_data = b''
        start_time = time.time()
        
        while b'\r\n' not in response_data:
            chunk = sock.recv(4096)
            if not chunk:
                print("  ✗ Sunucu bağlantıyı kapattı")
                return
            response_data += chunk
            if time.time() - start_time > 3.0:
                print("  ✗ Timeout")
                return
        
        response_str = response_data.split(b'\r\n')[0].decode('utf-8')
        print("  Alınan: {}".format(response_str[:200]))
        
        try:
            response = json.loads(response_str)
            if 'result' in response:
                print("  ✓ BAŞARILI! result var")
                if 'version' in str(response.get('result', {})):
                    version = response.get('result', {}).get('version', 'bulunamadı')
                    print("  ✓ Versiyon: {}".format(version))
            elif 'error' in response:
                error = response.get('error', {})
                print("  ✗ HATA: {}".format(error))
            else:
                print("  ? Beklenmeyen yanıt formatı")
        except json.JSONDecodeError as e:
            print("  ✗ JSON parse hatası: {}".format(e))
            
    except Exception as e:
        print("  ✗ Hata: {}".format(e))

if __name__ == "__main__":
    test_request_format()

