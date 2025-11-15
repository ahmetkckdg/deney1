"""
Örnek gaze verisi oluşturur - videolarla uyumlu
"""

import pandas as pd
import numpy as np
import csv
import os
from pathlib import Path

GAZE_DATA_FILE = "results/gaze_data.csv"
LANDMARKS_DIR = "results/face_landmarks"
SAMPLE_RATE = 30.0  # 30Hz (her 0.033 saniyede bir)

def get_video_info():
    """Landmark dosyalarından video bilgilerini çıkarır"""
    landmarks_dir = Path(LANDMARKS_DIR)
    video_info = {}
    
    for landmark_file in sorted(landmarks_dir.glob("*_landmarks.csv")):
        video_id = landmark_file.stem.replace("_landmarks", "")
        df = pd.read_csv(landmark_file)
        
        total_frames = len(df)
        duration = df['frame_time'].max()
        fps = 1.0 / df['frame_time'].diff().mean() if len(df) > 1 else 30.0
        
        video_info[video_id] = {
            'duration': duration,
            'total_frames': total_frames,
            'fps': fps
        }
    
    return video_info

def generate_realistic_gaze_points(video_id, duration, landmarks_df):
    """Gerçekçi gaze noktaları oluşturur (yüz bölgelerine yakın)"""
    gaze_points = []
    current_time = 0.0
    time_step = 1.0 / SAMPLE_RATE  # ~0.033 saniye
    
    # Yüz bölgeleri için hedef noktalar (merkez noktaları)
    regions = ['left_eye', 'right_eye', 'nose', 'mouth', 'forehead', 'chin']
    
    # Her 2 saniyede bir farklı bölgeye bakış simüle et
    region_sequence = []
    for i in range(int(duration / 2) + 1):
        # Rastgele bir bölge seç (bazı bölgeler daha sık)
        weights = [0.25, 0.25, 0.15, 0.15, 0.10, 0.10]  # Gözler daha sık
        region = np.random.choice(regions, p=weights)
        region_sequence.append((i * 2.0, region))
    
    region_idx = 0
    
    while current_time < duration:
        # Hangi bölgeye bakıldığını belirle
        if region_idx < len(region_sequence) - 1:
            if current_time >= region_sequence[region_idx + 1][0]:
                region_idx += 1
        
        target_region = region_sequence[region_idx][1]
        
        # Video zamanına göre frame bul
        frame_data = landmarks_df.iloc[(landmarks_df['frame_time'] - current_time).abs().argsort()[:1]]
        
        if len(frame_data) > 0:
            frame_data = frame_data.iloc[0]
            
            # Hedef bölgenin merkez noktasını al
            center_x = frame_data.get(f"{target_region}_center_x")
            center_y = frame_data.get(f"{target_region}_center_y")
            
            if pd.notna(center_x) and pd.notna(center_y):
                # Gerçekçi gaze noktası oluştur (merkez etrafında normal dağılım)
                # Gaze noktası bölgenin merkezine yakın ama tam üzerinde olmayabilir
                noise_x = np.random.normal(0, 20)  # 20 piksel standart sapma
                noise_y = np.random.normal(0, 15)  # 15 piksel standart sapma
                
                gaze_x = center_x + noise_x
                gaze_y = center_y + noise_y
                
                # Video sınırları içinde tut
                gaze_x = max(0, min(1280, gaze_x))
                gaze_y = max(0, min(720, gaze_y))
            else:
                # Bölge bulunamadıysa rastgele bir nokta (ekran merkezi etrafında)
                gaze_x = np.random.normal(640, 200)
                gaze_y = np.random.normal(360, 150)
                gaze_x = max(0, min(1280, gaze_x))
                gaze_y = max(0, min(720, gaze_y))
        else:
            # Frame bulunamadıysa rastgele nokta
            gaze_x = np.random.normal(640, 200)
            gaze_y = np.random.normal(360, 150)
            gaze_x = max(0, min(1280, gaze_x))
            gaze_y = max(0, min(720, gaze_y))
        
        # Timestamp (gerçek zaman)
        timestamp = current_time + np.random.uniform(0, 0.001)  # Küçük rastgelelik
        
        gaze_points.append({
            'gaze_x': round(gaze_x, 2),
            'gaze_y': round(gaze_y, 2),
            'video_time': round(current_time, 3),
            'timestamp': round(timestamp, 3)
        })
        
        current_time += time_step
    
    return gaze_points

def generate_sample_gaze_data():
    """Örnek gaze verisi oluşturur"""
    print("Video bilgileri alınıyor...")
    video_info = get_video_info()
    
    if not video_info:
        print("Hata: Landmark dosyaları bulunamadı!")
        return
    
    print(f"Toplam {len(video_info)} video bulundu.\n")
    
    # Örnek katılımcı ID'leri
    participant_ids = ["test_user_1", "test_user_2"]
    
    all_gaze_data = []
    
    for participant_id in participant_ids:
        print(f"Gaze verisi oluşturuluyor: {participant_id}")
        
        for video_id, info in video_info.items():
            print(f"  - {video_id} (süre: {info['duration']:.2f}s)")
            
            # Landmark dosyasını yükle
            landmark_file = Path(LANDMARKS_DIR) / f"{video_id}_landmarks.csv"
            if not landmark_file.exists():
                print(f"    ⚠️  Landmark dosyası bulunamadı, atlanıyor...")
                continue
            
            landmarks_df = pd.read_csv(landmark_file)
            
            # Gerçekçi gaze noktaları oluştur
            gaze_points = generate_realistic_gaze_points(
                video_id, 
                info['duration'], 
                landmarks_df
            )
            
            # Gaze verilerini ekle
            for point in gaze_points:
                all_gaze_data.append({
                    'participant_id': participant_id,
                    'video_id': video_id,
                    'gaze_x': point['gaze_x'],
                    'gaze_y': point['gaze_y'],
                    'timestamp': point['timestamp'],
                    'video_time': point['video_time']
                })
    
    # CSV'ye kaydet
    os.makedirs(os.path.dirname(GAZE_DATA_FILE), exist_ok=True)
    
    with open(GAZE_DATA_FILE, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['participant_id', 'video_id', 'gaze_x', 'gaze_y', 'timestamp', 'video_time']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_gaze_data)
    
    print(f"\n✓ Örnek gaze verisi oluşturuldu: {GAZE_DATA_FILE}")
    print(f"  Toplam kayıt: {len(all_gaze_data)}")
    print(f"  Katılımcı sayısı: {len(participant_ids)}")
    print(f"  Video sayısı: {len(video_info)}")
    
    # İstatistikler
    df = pd.read_csv(GAZE_DATA_FILE)
    print(f"\n📊 İstatistikler:")
    print(f"  Gaze X aralığı: {df['gaze_x'].min():.1f} - {df['gaze_x'].max():.1f}")
    print(f"  Gaze Y aralığı: {df['gaze_y'].min():.1f} - {df['gaze_y'].max():.1f}")
    print(f"  Video zamanı aralığı: {df['video_time'].min():.2f}s - {df['video_time'].max():.2f}s")
    print(f"\n  Katılımcı başına kayıt sayısı:")
    for pid in df['participant_id'].unique():
        count = len(df[df['participant_id'] == pid])
        print(f"    - {pid}: {count} kayıt")

if __name__ == "__main__":
    generate_sample_gaze_data()

