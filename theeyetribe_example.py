"""
TheEyeTribe Kullanım Örneği
Bu dosya, TheEyeTribe göz takip cihazının nasıl kullanılacağını gösterir.
"""

from eye_tracker import EyeTracker
import time

def main():
    # Eye tracker oluştur
    tracker = EyeTracker()
    
    # TheEyeTribe sunucusuna bağlan
    print("TheEyeTribe sunucusuna bağlanılıyor...")
    if not tracker.connect():
        print("Bağlantı başarısız! Lütfen TheEyeTribe sunucusunun çalıştığından emin olun.")
        return
    
    try:
        # Göz takibini başlat
        tracker.start_tracking()
        
        print("Göz takibi başlatıldı. 10 saniye boyunca veri toplanacak...")
        print("ESC tuşuna basarak çıkabilirsiniz.\n")
        
        # 10 saniye boyunca gaze verilerini topla
        start_time = time.time()
        sample_count = 0
        
        while time.time() - start_time < 10:
            gaze_data = tracker.get_gaze_data()
            
            if gaze_data:
                x, y, timestamp = gaze_data
                sample_count += 1
                print(f"Örnek {sample_count}: X={x:.1f}, Y={y:.1f}, Zaman={timestamp:.3f}")
            else:
                print("Gaze verisi alınamadı...")
            
            time.sleep(0.1)  # 100ms aralıklarla örnekle
        
        print(f"\nToplam {sample_count} örnek toplandı.")
        
        # Göz takibini durdur
        tracker.stop_tracking()
        
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.")
    except Exception as e:
        print(f"Hata oluştu: {e}")
    finally:
        # Bağlantıyı kapat
        tracker.disconnect()
        print("Bağlantı kapatıldı.")

if __name__ == "__main__":
    main()

