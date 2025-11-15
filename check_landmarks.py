"""
Face landmarks verilerinin mantıklı ve düzgün olup olmadığını kontrol eder.
"""

import pandas as pd
import os
from pathlib import Path

LANDMARKS_DIR = "results/face_landmarks"
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720

def check_landmarks_file(file_path):
    """Bir landmark dosyasını kontrol eder"""
    print(f"\n{'='*60}")
    print(f"Kontrol ediliyor: {os.path.basename(file_path)}")
    print(f"{'='*60}")
    
    df = pd.read_csv(file_path)
    
    # Temel bilgiler
    print(f"\n📊 Temel Bilgiler:")
    print(f"  Toplam kare sayısı: {len(df)}")
    print(f"  Video boyutu: {df['video_width'].iloc[0]}x{df['video_height'].iloc[0]}")
    print(f"  İlk frame zamanı: {df['frame_time'].iloc[0]:.3f}s")
    print(f"  Son frame zamanı: {df['frame_time'].iloc[-1]:.3f}s")
    
    # Eksik veri kontrolü
    print(f"\n🔍 Eksik Veri Kontrolü:")
    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(f"  ⚠️  Eksik veri bulundu:")
        for col, count in missing[missing > 0].items():
            print(f"    - {col}: {count} eksik ({count/len(df)*100:.1f}%)")
    else:
        print(f"  ✓ Hiç eksik veri yok")
    
    # Koordinat sınırları kontrolü
    print(f"\n📐 Koordinat Sınırları Kontrolü:")
    errors = []
    
    regions = ['left_eye', 'right_eye', 'nose', 'mouth', 'left_cheek', 'right_cheek', 'forehead', 'chin']
    
    for region in regions:
        min_x_col = f"{region}_min_x"
        max_x_col = f"{region}_max_x"
        min_y_col = f"{region}_min_y"
        max_y_col = f"{region}_max_y"
        
        if min_x_col in df.columns:
            # Negatif koordinat kontrolü
            neg_x = (df[min_x_col] < 0).sum()
            neg_y = (df[min_y_col] < 0).sum()
            
            # Video boyutunu aşan koordinat kontrolü
            over_x = (df[max_x_col] > VIDEO_WIDTH).sum()
            over_y = (df[max_y_col] > VIDEO_HEIGHT).sum()
            
            # Min > Max kontrolü
            invalid_x = (df[min_x_col] > df[max_x_col]).sum()
            invalid_y = (df[min_y_col] > df[max_y_col]).sum()
            
            if neg_x > 0 or neg_y > 0 or over_x > 0 or over_y > 0 or invalid_x > 0 or invalid_y > 0:
                errors.append({
                    'region': region,
                    'neg_x': neg_x,
                    'neg_y': neg_y,
                    'over_x': over_x,
                    'over_y': over_y,
                    'invalid_x': invalid_x,
                    'invalid_y': invalid_y
                })
    
    if errors:
        print(f"  ⚠️  Hatalı koordinatlar bulundu:")
        for err in errors:
            print(f"    - {err['region']}:")
            if err['neg_x'] > 0:
                print(f"      Negatif X: {err['neg_x']}")
            if err['neg_y'] > 0:
                print(f"      Negatif Y: {err['neg_y']}")
            if err['over_x'] > 0:
                print(f"      X > {VIDEO_WIDTH}: {err['over_x']}")
            if err['over_y'] > 0:
                print(f"      Y > {VIDEO_HEIGHT}: {err['over_y']}")
            if err['invalid_x'] > 0:
                print(f"      Min_X > Max_X: {err['invalid_x']}")
            if err['invalid_y'] > 0:
                print(f"      Min_Y > Max_Y: {err['invalid_y']}")
    else:
        print(f"  ✓ Tüm koordinatlar geçerli")
    
    # Yüz bölgeleri pozisyon kontrolü (mantıklı sıralama)
    print(f"\n👤 Yüz Bölgeleri Pozisyon Kontrolü:")
    
    # Ortalama pozisyonlar
    avg_positions = {}
    for region in regions:
        center_x_col = f"{region}_center_x"
        center_y_col = f"{region}_center_y"
        if center_x_col in df.columns:
            avg_x = df[center_x_col].mean()
            avg_y = df[center_y_col].mean()
            avg_positions[region] = (avg_x, avg_y)
    
    # Y pozisyonlarına göre sıralama (üstten alta)
    sorted_by_y = sorted(avg_positions.items(), key=lambda x: x[1][1])
    
    print(f"  Y pozisyonuna göre sıralama (üstten alta):")
    for i, (region, (x, y)) in enumerate(sorted_by_y, 1):
        print(f"    {i}. {region}: Y={y:.1f}, X={x:.1f}")
    
    # Mantıklı sıralama kontrolü
    expected_order = ['forehead', 'left_eye', 'right_eye', 'nose', 'mouth', 'chin']
    actual_order = [r[0] for r in sorted_by_y]
    
    # Forehead en üstte olmalı
    if actual_order[0] == 'forehead':
        print(f"  ✓ Alın en üstte")
    else:
        print(f"  ⚠️  Alın en üstte değil (ilk: {actual_order[0]})")
    
    # Chin en altta olmalı
    if actual_order[-1] == 'chin':
        print(f"  ✓ Çene en altta")
    else:
        print(f"  ⚠️  Çene en altta değil (son: {actual_order[-1]})")
    
    # Gözler burunun üstünde olmalı
    eye_y = min(avg_positions.get('left_eye', (0, 999))[1], avg_positions.get('right_eye', (0, 999))[1])
    nose_y = avg_positions.get('nose', (0, 0))[1]
    if eye_y < nose_y:
        print(f"  ✓ Gözler burunun üstünde (göz: {eye_y:.1f}, burun: {nose_y:.1f})")
    else:
        print(f"  ⚠️  Gözler burunun altında (göz: {eye_y:.1f}, burun: {nose_y:.1f})")
    
    # Ağız burunun altında olmalı
    mouth_y = avg_positions.get('mouth', (0, 0))[1]
    if mouth_y > nose_y:
        print(f"  ✓ Ağız burunun altında (ağız: {mouth_y:.1f}, burun: {nose_y:.1f})")
    else:
        print(f"  ⚠️  Ağız burunun üstünde (ağız: {mouth_y:.1f}, burun: {nose_y:.1f})")
    
    # Sol göz sol tarafta, sağ göz sağ tarafta olmalı
    left_eye_x = avg_positions.get('left_eye', (0, 0))[0]
    right_eye_x = avg_positions.get('right_eye', (0, 0))[0]
    if left_eye_x < right_eye_x:
        print(f"  ✓ Sol göz solda, sağ göz sağda (sol: {left_eye_x:.1f}, sağ: {right_eye_x:.1f})")
    else:
        print(f"  ⚠️  Göz pozisyonları ters (sol: {left_eye_x:.1f}, sağ: {right_eye_x:.1f})")
    
    # Frame sürekliliği kontrolü
    print(f"\n⏱️  Frame Sürekliliği:")
    frame_diffs = df['frame_number'].diff().dropna()
    if (frame_diffs == 1).all():
        print(f"  ✓ Frame numaraları sürekli (1'den {len(df)}'e kadar)")
    else:
        missing_frames = frame_diffs[frame_diffs != 1]
        print(f"  ⚠️  Eksik frame'ler var: {len(missing_frames)} adet")
        print(f"    Örnek: {missing_frames.head(5).tolist()}")
    
    # Zaman sürekliliği kontrolü
    time_diffs = df['frame_time'].diff().dropna()
    avg_time_diff = time_diffs.mean()
    expected_fps = 1.0 / avg_time_diff if avg_time_diff > 0 else 0
    
    print(f"  Ortalama frame aralığı: {avg_time_diff:.3f}s")
    print(f"  Tahmini FPS: {expected_fps:.1f}")
    
    if 29 <= expected_fps <= 31:
        print(f"  ✓ FPS değeri normal (30fps bekleniyor)")
    else:
        print(f"  ⚠️  FPS değeri beklenenden farklı (30fps bekleniyor, {expected_fps:.1f}fps bulundu)")
    
    # Boyut kontrolü (yüz bölgeleri mantıklı boyutlarda mı?)
    print(f"\n📏 Yüz Bölgeleri Boyut Kontrolü:")
    for region in ['left_eye', 'right_eye', 'nose', 'mouth']:
        width_col = f"{region}_width"
        height_col = f"{region}_height"
        if width_col in df.columns:
            avg_width = df[width_col].mean()
            avg_height = df[height_col].mean()
            print(f"  {region}:")
            print(f"    Ortalama genişlik: {avg_width:.1f}px")
            print(f"    Ortalama yükseklik: {avg_height:.1f}px")
            
            # Gözler için mantıklı boyut kontrolü
            if region in ['left_eye', 'right_eye']:
                if 30 <= avg_width <= 150 and 10 <= avg_height <= 50:
                    print(f"    ✓ Göz boyutu mantıklı")
                else:
                    print(f"    ⚠️  Göz boyutu beklenenden farklı")
    
    return len(errors) == 0

def main():
    """Tüm landmark dosyalarını kontrol eder"""
    landmarks_dir = Path(LANDMARKS_DIR)
    
    if not landmarks_dir.exists():
        print(f"Hata: {LANDMARKS_DIR} dizini bulunamadı!")
        return
    
    landmark_files = sorted(landmarks_dir.glob("*_landmarks.csv"))
    
    if not landmark_files:
        print(f"Hiç landmark dosyası bulunamadı!")
        return
    
    print(f"Toplam {len(landmark_files)} landmark dosyası bulundu.\n")
    
    all_valid = True
    for file_path in landmark_files:
        valid = check_landmarks_file(file_path)
        if not valid:
            all_valid = False
    
    print(f"\n{'='*60}")
    if all_valid:
        print("✓ Tüm dosyalar geçerli görünüyor!")
    else:
        print("⚠️  Bazı dosyalarda sorunlar bulundu!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

