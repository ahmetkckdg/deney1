#!/usr/bin/env python3
"""
TheEyeTribe sunucu durumu kontrol scripti
Sunucunun çalışıp çalışmadığını ve loglarını kontrol eder
"""

import socket
import sys
import os

def check_port(host='localhost', port=6555):
    """Port'un açık olup olmadığını kontrol eder"""
    print("=" * 60)
    print("SUNUCU DURUMU KONTROLÜ")
    print("=" * 60)
    print(f"Hedef: {host}:{port}")
    print()
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✓ Port {} AÇIK - Sunucu çalışıyor!".format(port))
            return True
        else:
            print("✗ Port {} KAPALI - Sunucu çalışmıyor!".format(port))
            print(f"  Hata kodu: {result}")
            return False
    except Exception as e:
        print(f"✗ Port kontrolü başarısız: {e}")
        return False

def check_server_process():
    """Windows'ta TheEyeTribe sunucu process'ini kontrol eder"""
    print()
    print("=" * 60)
    print("SUNUCU PROCESS KONTROLÜ")
    print("=" * 60)
    
    try:
        import subprocess
        
        # Windows'ta tasklist komutu ile kontrol et
        if sys.platform == 'win32':
            print("Windows process kontrolü yapılıyor...")
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq TheEyeTribe.exe'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'TheEyeTribe.exe' in result.stdout:
                print("✓ TheEyeTribe.exe process bulundu!")
                print("\nProcess bilgileri:")
                print(result.stdout)
                return True
            else:
                print("✗ TheEyeTribe.exe process bulunamadı!")
                print("\nAlternatif process isimleri kontrol ediliyor...")
                
                # Alternatif isimler
                alt_names = ['EyeTribe', 'eyetribe', 'TET', 'tet']
                for name in alt_names:
                    result2 = subprocess.run(
                        ['tasklist', '/FI', f'IMAGENAME eq {name}.exe'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if name in result2.stdout:
                        print(f"✓ {name}.exe process bulundu!")
                        return True
                
                return False
        else:
            # Linux/Mac için
            print("Unix sistem - process kontrolü...")
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'eyetribe' in result.stdout.lower() or 'theeyetribe' in result.stdout.lower():
                print("✓ TheEyeTribe process bulundu!")
                return True
            else:
                print("✗ TheEyeTribe process bulunamadı!")
                return False
                
    except Exception as e:
        print(f"✗ Process kontrolü başarısız: {e}")
        return False

def show_log_locations():
    """Log dosyası konumlarını gösterir"""
    print()
    print("=" * 60)
    print("LOG DOSYASI KONUMLARI")
    print("=" * 60)
    
    log_locations = []
    
    if sys.platform == 'win32':
        # Windows log konumları
        user_profile = os.environ.get('USERPROFILE', '')
        appdata = os.environ.get('APPDATA', '')
        localappdata = os.environ.get('LOCALAPPDATA', '')
        
        possible_locations = [
            os.path.join(user_profile, 'TheEyeTribe', 'logs'),
            os.path.join(appdata, 'TheEyeTribe', 'logs'),
            os.path.join(localappdata, 'TheEyeTribe', 'logs'),
            os.path.join('C:', 'Program Files', 'TheEyeTribe', 'logs'),
            os.path.join('C:', 'Program Files (x86)', 'TheEyeTribe', 'logs'),
            os.path.join(user_profile, 'Documents', 'TheEyeTribe', 'logs'),
        ]
        
        print("Windows log konumları:")
        for loc in possible_locations:
            if os.path.exists(loc):
                print(f"  ✓ {loc}")
                log_locations.append(loc)
            else:
                print(f"  ✗ {loc} (bulunamadı)")
    else:
        # Unix log konumları
        home = os.environ.get('HOME', '')
        possible_locations = [
            os.path.join(home, '.eyetribe', 'logs'),
            os.path.join(home, '.local', 'share', 'TheEyeTribe', 'logs'),
            '/var/log/TheEyeTribe',
            '/var/log/eyetribe',
        ]
        
        print("Unix log konumları:")
        for loc in possible_locations:
            if os.path.exists(loc):
                print(f"  ✓ {loc}")
                log_locations.append(loc)
            else:
                print(f"  ✗ {loc} (bulunamadı)")
    
    return log_locations

def check_console_output():
    """Console çıktısını kontrol et"""
    print()
    print("=" * 60)
    print("SUNUCU LOGLARINI KONTROL ETME YÖNTEMLERİ")
    print("=" * 60)
    print()
    print("1. SUNUCU GUI UYGULAMASI:")
    print("   - TheEyeTribe sunucusu GUI uygulamasını açın")
    print("   - Alt kısımdaki log penceresini kontrol edin")
    print("   - Veya 'View' > 'Logs' menüsüne bakın")
    print()
    print("2. COMMAND LINE'DAN ÇALIŞTIRMA:")
    print("   - TheEyeTribe sunucusunu command line'dan çalıştırın:")
    print("     TheEyeTribe.exe")
    print("   - Console'da log mesajlarını görebilirsiniz")
    print()
    print("3. LOG DOSYALARI:")
    print("   - Yukarıda gösterilen log dosyası konumlarını kontrol edin")
    print("   - En son değiştirilen log dosyasını açın")
    print()
    print("4. WINDOWS EVENT VIEWER:")
    print("   - Windows Event Viewer'ı açın (eventvwr.exe)")
    print("   - Windows Logs > Application bölümüne bakın")
    print("   - 'TheEyeTribe' veya 'EyeTribe' ile filtreleyin")
    print()

if __name__ == "__main__":
    print("\nTheEyeTribe Sunucu Durumu Kontrol Aracı\n")
    
    # Port kontrolü
    port_ok = check_port()
    
    # Process kontrolü
    process_ok = check_server_process()
    
    # Log konumları
    log_locations = show_log_locations()
    
    # Log kontrol yöntemleri
    check_console_output()
    
    # Özet
    print()
    print("=" * 60)
    print("ÖZET")
    print("=" * 60)
    if port_ok:
        print("✓ Port açık - Sunucu çalışıyor gibi görünüyor")
    else:
        print("✗ Port kapalı - Sunucu çalışmıyor olabilir")
    
    if process_ok:
        print("✓ Process bulundu - Sunucu çalışıyor")
    else:
        print("✗ Process bulunamadı - Sunucu çalışmıyor olabilir")
        print()
        print("ÇÖZÜM ÖNERİLERİ:")
        print("  1. TheEyeTribe sunucusunu başlatın")
        print("  2. Sunucunun çalıştığından emin olun")
        print("  3. Firewall ayarlarını kontrol edin")
        print("  4. Port 6555'in açık olduğundan emin olun")
    
    if log_locations:
        print(f"\n✓ {len(log_locations)} log konumu bulundu")
        print("  Log dosyalarını bu konumlardan kontrol edebilirsiniz")
    else:
        print("\n✗ Log dosyası konumu bulunamadı")
        print("  Sunucu GUI uygulamasındaki log penceresini kontrol edin")
    
    print("=" * 60)

