#!/usr/bin/env python3
"""
TheEyeTribe bağlantı test scripti
Sunucu durumunu ve bağlantıyı test eder
"""

import socket
import json
import time
import sys

def test_server_connection(host='localhost', port=6555):
    """Sunucuya basit TCP bağlantısı test eder"""
    print("=" * 60)
    print("SUNUCU BAĞLANTI TESTİ")
    print("=" * 60)
    print(f"Hedef: {host}:{port}")
    print()
    
    # Test 1: Port açık mı?
    print("Test 1: Port durumu kontrol ediliyor...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✓ Port {} açık ve erişilebilir".format(port))
        else:
            print("✗ Port {} kapalı veya erişilemez (hata kodu: {})".format(port, result))
            print("  → TheEyeTribe sunucusu çalışmıyor olabilir!")
            return False
    except Exception as e:
        print("✗ Port kontrolü başarısız: {}".format(e))
        return False
    
    print()
    
    # Test 2: Socket bağlantısı
    print("Test 2: Socket bağlantısı deneniyor...")
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        print("  Socket oluşturuldu")
        
        print("  Bağlantı deneniyor...")
        start_time = time.time()
        sock.connect((host, port))
        elapsed = time.time() - start_time
        print("✓ Socket bağlantısı başarılı! (Süre: {:.3f}s)".format(elapsed))
        
        # Test 3: Basit veri gönderme/alma
        print()
        print("Test 3: Veri gönderme/alma testi...")
        
        # TheEyeTribe JSON-RPC isteği
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "get",
            "params": {
                "category": "tracker",
                "request": "version"
            }
        }
        
        message = json.dumps(request) + '\r\n'
        print("  İstek gönderiliyor: {}".format(message.strip()))
        
        sock.sendall(message.encode('utf-8'))
        print("  İstek gönderildi")
        
        # Yanıt bekle
        print("  Yanıt bekleniyor...")
        sock.settimeout(3.0)
        response_data = b''
        start_time = time.time()
        
        while b'\r\n' not in response_data:
            chunk = sock.recv(4096)
            if not chunk:
                print("✗ Sunucu bağlantıyı kapattı")
                return False
            response_data += chunk
            elapsed = time.time() - start_time
            if elapsed > 3.0:
                print("✗ Yanıt timeout (3 saniye)")
                return False
        
        elapsed = time.time() - start_time
        response_str = response_data.split(b'\r\n')[0].decode('utf-8')
        print("✓ Yanıt alındı! (Süre: {:.3f}s)".format(elapsed))
        print("  Yanıt: {}".format(response_str[:200]))
        
        # JSON parse et
        try:
            response = json.loads(response_str)
            if 'result' in response:
                version = response.get('result', {}).get('version', 'bilinmiyor')
                print("✓ JSON parse başarılı!")
                print("  Versiyon: {}".format(version))
                return True
            else:
                print("✗ Yanıtta 'result' yok")
                print("  Yanıt: {}".format(response))
                return False
        except json.JSONDecodeError as e:
            print("✗ JSON parse hatası: {}".format(e))
            print("  Ham yanıt: {}".format(response_str))
            return False
        
    except socket.timeout:
        print("✗ Socket timeout - sunucu yanıt vermiyor")
        return False
    except ConnectionRefusedError:
        print("✗ Bağlantı reddedildi - sunucu çalışmıyor olabilir")
        return False
    except OSError as e:
        print("✗ OS hatası: {}".format(e))
        return False
    except Exception as e:
        print("✗ Beklenmeyen hata: {}: {}".format(type(e).__name__, e))
        import traceback
        traceback.print_exc()
        return False
    finally:
        if sock:
            try:
                sock.close()
                print("  Socket kapatıldı")
            except:
                pass

def test_with_eye_tracker():
    """EyeTracker sınıfı ile test"""
    print()
    print("=" * 60)
    print("EYETRACKER SINIFI İLE TEST")
    print("=" * 60)
    
    try:
        from eye_tracker import EyeTracker
        
        tracker = EyeTracker()
        print("EyeTracker oluşturuldu")
        print()
        
        print("Bağlantı deneniyor (test_connection=True)...")
        result = tracker.connect(test_connection=True)
        
        if result:
            print("✓ Bağlantı başarılı!")
            tracker.disconnect()
            return True
        else:
            print("✗ Bağlantı başarısız!")
            return False
            
    except Exception as e:
        print("✗ Hata: {}: {}".format(type(e).__name__, e))
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nTheEyeTribe Bağlantı Test Aracı\n")
    
    # Sunucu testi
    server_ok = test_server_connection()
    
    print()
    print("=" * 60)
    if server_ok:
        print("SONUÇ: Sunucu çalışıyor ve yanıt veriyor ✓")
    else:
        print("SONUÇ: Sunucu ile iletişim kurulamıyor ✗")
        print()
        print("KONTROL LİSTESİ:")
        print("  1. TheEyeTribe sunucusu çalışıyor mu?")
        print("  2. Port 6555 açık mı?")
        print("  3. Firewall engelliyor mu?")
        print("  4. Sunucu loglarını kontrol edin")
        sys.exit(1)
    
    print()
    
    # EyeTracker testi
    tracker_ok = test_with_eye_tracker()
    
    print()
    print("=" * 60)
    if tracker_ok:
        print("SONUÇ: EyeTracker sınıfı çalışıyor ✓")
    else:
        print("SONUÇ: EyeTracker sınıfı ile sorun var ✗")
        print("  → Kodda bir sorun olabilir")
    print("=" * 60)

