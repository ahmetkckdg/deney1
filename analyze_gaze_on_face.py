"""
Eye tracking verilerini yüz landmark'larıyla eşleştirir.
Her gaze noktasının hangi yüz bölgesine denk geldiğini belirler.
"""

import pandas as pd
import os
import csv
from pathlib import Path

# Dosya yolları
GAZE_DATA_FILE = "results/gaze_data.csv"
LANDMARKS_DIR = "results/face_landmarks"
OUTPUT_FILE = "results/gaze_on_face_regions.csv"

# Yüz bölgeleri (landmark dosyalarındaki sütun isimleriyle eşleşmeli)
FACE_REGIONS = [
    "left_eye", "right_eye", "nose", "mouth",
    "left_cheek", "right_cheek", "forehead", "chin"
]

def is_point_in_region(gaze_x, gaze_y, region_data):
    """Gaze noktasının belirli bir yüz bölgesi içinde olup olmadığını kontrol eder"""
    if pd.isna(region_data.get("min_x")) or pd.isna(region_data.get("max_x")):
        return False
    
    min_x = region_data["min_x"]
    max_x = region_data["max_x"]
    min_y = region_data["min_y"]
    max_y = region_data["max_y"]
    
    return (min_x <= gaze_x <= max_x) and (min_y <= gaze_y <= max_y)

def find_closest_region(gaze_x, gaze_y, frame_data):
    """Gaze noktasına en yakın yüz bölgesini bulur (eğer hiçbir bölge içinde değilse)"""
    min_distance = float('inf')
    closest_region = None
    
    for region in FACE_REGIONS:
        center_x = frame_data.get(f"{region}_center_x")
        center_y = frame_data.get(f"{region}_center_y")
        
        if pd.isna(center_x) or pd.isna(center_y):
            continue
        
        # Öklid mesafesi
        distance = ((gaze_x - center_x) ** 2 + (gaze_y - center_y) ** 2) ** 0.5
        
        if distance < min_distance:
            min_distance = distance
            closest_region = region
    
    return closest_region, min_distance

def analyze_gaze_data():
    """Gaze verilerini yüz landmark'larıyla eşleştirir"""
    
    # Gaze verilerini yükle
    if not os.path.exists(GAZE_DATA_FILE):
        print(f"Hata: {GAZE_DATA_FILE} bulunamadı!")
        return
    
    gaze_df = pd.read_csv(GAZE_DATA_FILE)
    print(f"Gaze verileri yüklendi: {len(gaze_df)} kayıt")
    
    # Landmark dosyalarını yükle
    landmarks_dir = Path(LANDMARKS_DIR)
    if not landmarks_dir.exists():
        print(f"Hata: {LANDMARKS_DIR} dizini bulunamadı!")
        print("Önce extract_face_landmarks.py script'ini çalıştırın.")
        return
    
    # Sonuçları saklamak için liste
    results = []
    
    # Her video için işle
    for video_id in gaze_df['video_id'].unique():
        video_gaze = gaze_df[gaze_df['video_id'] == video_id]
        
        # Landmark dosyasını yükle
        landmark_file = landmarks_dir / f"{video_id}_landmarks.csv"
        if not landmark_file.exists():
            print(f"Uyarı: {landmark_file} bulunamadı, atlanıyor...")
            continue
        
        landmarks_df = pd.read_csv(landmark_file)
        print(f"  İşleniyor: {video_id} ({len(video_gaze)} gaze, {len(landmarks_df)} kare)")
        
        # Her gaze noktası için
        for idx, gaze_row in video_gaze.iterrows():
            gaze_x = gaze_row['gaze_x']
            gaze_y = gaze_row['gaze_y']
            video_time = gaze_row['video_time']
            
            # Video zamanına göre frame numarasını bul
            # FPS'yi landmark dosyasından al (varsayılan 30fps)
            fps = 30.0
            if 'frame_time' in landmarks_df.columns and len(landmarks_df) > 0:
                # FPS'yi hesapla (ilk iki frame arasındaki zaman farkından)
                if len(landmarks_df) > 1:
                    time_diff = landmarks_df.iloc[1]['frame_time'] - landmarks_df.iloc[0]['frame_time']
                    if time_diff > 0:
                        fps = 1.0 / time_diff
            
            # Video zamanına en yakın frame'i bul
            frame_number = int(video_time * fps)
            frame_data = landmarks_df[landmarks_df['frame_number'] == frame_number]
            
            if frame_data.empty:
                # En yakın frame'i bul
                frame_data = landmarks_df.iloc[(landmarks_df['frame_time'] - video_time).abs().argsort()[:1]]
            
            if frame_data.empty:
                # Frame bulunamadı
                results.append({
                    'participant_id': gaze_row['participant_id'],
                    'video_id': video_id,
                    'gaze_x': gaze_x,
                    'gaze_y': gaze_y,
                    'video_time': video_time,
                    'frame_number': None,
                    'gaze_region': 'unknown',
                    'region_center_x': None,
                    'region_center_y': None,
                    'distance_to_region': None
                })
                continue
            
            frame_data = frame_data.iloc[0]
            
            # Hangi yüz bölgesinde olduğunu bul
            gaze_region = None
            region_center_x = None
            region_center_y = None
            distance_to_region = None
            
            # Önce bölge içinde mi kontrol et
            for region in FACE_REGIONS:
                if is_point_in_region(gaze_x, gaze_y, frame_data):
                    gaze_region = region
                    region_center_x = frame_data.get(f"{region}_center_x")
                    region_center_y = frame_data.get(f"{region}_center_y")
                    distance_to_region = 0  # Bölge içinde
                    break
            
            # Eğer hiçbir bölge içinde değilse, en yakın bölgeyi bul
            if gaze_region is None:
                closest_region, min_distance = find_closest_region(gaze_x, gaze_y, frame_data)
                if closest_region:
                    gaze_region = f"near_{closest_region}"
                    region_center_x = frame_data.get(f"{closest_region}_center_x")
                    region_center_y = frame_data.get(f"{closest_region}_center_y")
                    distance_to_region = min_distance
            
            results.append({
                'participant_id': gaze_row['participant_id'],
                'video_id': video_id,
                'gaze_x': gaze_x,
                'gaze_y': gaze_y,
                'video_time': video_time,
                'frame_number': frame_data.get('frame_number'),
                'gaze_region': gaze_region if gaze_region else 'unknown',
                'region_center_x': region_center_x,
                'region_center_y': region_center_y,
                'distance_to_region': distance_to_region
            })
    
    # Sonuçları CSV'ye kaydet
    if results:
        results_df = pd.DataFrame(results)
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        results_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        print(f"\n✓ Sonuçlar kaydedildi: {OUTPUT_FILE}")
        print(f"  Toplam kayıt: {len(results_df)}")
        print(f"\nYüz bölgesi dağılımı:")
        print(results_df['gaze_region'].value_counts())
    else:
        print("Hiç sonuç bulunamadı!")

if __name__ == "__main__":
    analyze_gaze_data()

