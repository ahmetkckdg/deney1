"""
Eye tracking verilerini yüz landmark'larıyla eşleştirir.
Her gaze noktasının hangi yüz bölgesine denk geldiğini belirler.
"""

import math
import pandas as pd
import os
import csv
from pathlib import Path

# Dosya yolları
GAZE_DATA_FILE = os.environ.get("GAZE_DATA_FILE", "gaze_data/gaze_data.csv")
LANDMARKS_DIR = "results/face_landmarks"
OUTPUT_FILE = "results/gaze_on_face_regions.csv"

# Yüz bölgeleri (landmark dosyalarındaki sütun isimleriyle eşleşmeli)
FACE_REGIONS = [
    "left_eye", "right_eye", "nose", "mouth",
    "left_cheek", "right_cheek", "forehead", "chin",
    "left_ear", "right_ear", "face_outline"
]
REGION_TOLERANCE_PX = 10.0

def is_point_in_region(gaze_x, gaze_y, frame_data, region_name, tolerance=0.0):
    """Gaze noktasının belirli bir yüz bölgesi içinde olup olmadığını kontrol eder"""
    bounds = get_region_bounds(frame_data, region_name)
    if not bounds:
        return False
    min_x, max_x, min_y, max_y = bounds
    
    min_x -= tolerance
    min_y -= tolerance
    max_x += tolerance
    max_y += tolerance
    
    return (min_x <= gaze_x <= max_x) and (min_y <= gaze_y <= max_y)

def get_region_bounds(frame_data, region_name):
    """frame_data içerisinden bölge bounding box değerlerini döndürür"""
    min_x = frame_data.get(f"{region_name}_min_x")
    max_x = frame_data.get(f"{region_name}_max_x")
    min_y = frame_data.get(f"{region_name}_min_y")
    max_y = frame_data.get(f"{region_name}_max_y")

    if any(pd.isna(val) for val in (min_x, max_x, min_y, max_y)):
        return None
    
    return min_x, max_x, min_y, max_y

def distance_to_region(gaze_x, gaze_y, frame_data, region_name):
    """Gaze noktasının bölge bounding box'ına olan mesafesini hesaplar"""
    bounds = get_region_bounds(frame_data, region_name)
    if not bounds:
        return None
    
    min_x, max_x, min_y, max_y = bounds
    
    if min_x <= gaze_x <= max_x:
        dx = 0.0
    else:
        dx = min(abs(gaze_x - min_x), abs(gaze_x - max_x))
    
    if min_y <= gaze_y <= max_y:
        dy = 0.0
    else:
        dy = min(abs(gaze_y - min_y), abs(gaze_y - max_y))
    
    return math.hypot(dx, dy)

def find_closest_region(gaze_x, gaze_y, frame_data):
    """Gaze noktasına en yakın yüz bölgesini bulur (eğer hiçbir bölge içinde değilse)"""
    min_distance = float('inf')
    closest_region = None
    
    for region in FACE_REGIONS:
        distance = distance_to_region(gaze_x, gaze_y, frame_data, region)
        if distance is None:
            continue
        
        if distance < min_distance:
            min_distance = distance
            closest_region = region
    
    if closest_region is None:
        return None, None
    
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
                if is_point_in_region(gaze_x, gaze_y, frame_data, region, tolerance=REGION_TOLERANCE_PX):
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

