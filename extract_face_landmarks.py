"""
Video karelerindeki yüz landmark'larını tespit edip kaydeder.
Her kare için yüz bölgelerinin (gözler, burun, ağız, vb.) piksel koordinatlarını çıkarır.
"""

import math
import os
import csv
from pathlib import Path

# Mediapipe GPU kullanımı macOS sandbox'larında sorun çıkarabildiği için devre dışı bırak
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

import imageio.v2 as imageio
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision as mp_vision

# Video dizini
VIDEO_DIR = "videos"
OUTPUT_DIR = "results/face_landmarks"
FPS = 30  # Video FPS (30fps)
LANDMARKER_MODEL_PATH = Path("models/face_landmarker.task")


# Yüz bölgeleri bounding box'larını biraz genişletmek için padding oranı
REGION_PADDING_RATIO = 0.12  # Her bir kenara %12 padding ekle
MIN_REGION_PADDING = 6       # Piksel cinsinden minimum padding

# Yüz bölgeleri tanımlamaları (MediaPipe Face Mesh landmark indeksleri - 468 landmark)
# MediaPipe Face Mesh: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
FACE_REGIONS = {
    # Sol göz (left eye) - göz çevresi landmark'ları
    "left_eye": [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
    # Sağ göz (right eye) - göz çevresi landmark'ları
    "right_eye": [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398],
    # Burun (nose) - burun ve çevresi
    "nose": [1, 2, 5, 4, 6, 19, 20, 94, 125, 141, 235, 236, 3, 51, 48, 115, 131, 134, 102, 49, 220, 305, 281, 363, 360],
    # Ağız (mouth) - ağız ve dudaklar
    "mouth": [61, 146, 91, 181, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318],
    # Sol yanak (left cheek)
    "left_cheek": [116, 117, 118, 119, 120, 121, 126, 142, 36, 205, 206, 207, 213, 192, 147],
    # Sağ yanak (right cheek)
    "right_cheek": [345, 346, 347, 348, 349, 350, 451, 452, 453, 464, 435, 416, 434, 432],
    # Alın (forehead)
    "forehead": [10, 151, 9, 107, 55, 65, 52, 53, 46, 124, 35, 31, 228, 229, 230, 231, 232, 233, 244, 245],
    # Çene (chin)
    "chin": [18, 200, 199, 175, 169, 170, 140, 136, 150, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323],
    # Sol kulak (katılımcının solu - ekranın sağ tarafı)
    "left_ear": [234, 93, 132, 58, 172, 136, 150, 176, 377, 379, 397, 400, 356],
    # Sağ kulak (katılımcının sağı - ekranın sol tarafı)
    "right_ear": [454, 323, 361, 288, 397, 365, 379, 378, 400, 352, 330, 332, 284, 251, 389],
    # Tüm yüz ovali - genel referans için
    "face_outline": [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400,
                     377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
}

def _get_landmark_list(landmarks):
    """FaceMesh veya FaceLandmarker çıktısını tek tip listeye dönüştürür."""
    if landmarks is None:
        return []
    if hasattr(landmarks, "landmark"):
        return landmarks.landmark
    return landmarks

def _apply_padding(min_val, max_val, length, max_limit):
    """Belirli bir eksende padding uygular ve sınırlar dahilinde kalır"""
    padding = max(MIN_REGION_PADDING, int(length * REGION_PADDING_RATIO))
    padded_min = max(0, min_val - padding)
    padded_max = min(max_limit, max_val + padding)
    return padded_min, padded_max

def get_region_bounds(landmarks, region_indices, img_width, img_height):
    """Belirli bir yüz bölgesinin bounding box'ını hesaplar"""
    if not region_indices:
        return None
    
    landmark_list = _get_landmark_list(landmarks)
    if not landmark_list:
        return None
    
    x_coords = []
    y_coords = []
    
    for idx in region_indices:
        if idx < len(landmark_list):
            landmark = landmark_list[idx]
            x = int(landmark.x * img_width)
            y = int(landmark.y * img_height)
            x_coords.append(x)
            y_coords.append(y)
    
    if not x_coords or not y_coords:
        return None
    
    min_x = min(x_coords)
    max_x = max(x_coords)
    min_y = min(y_coords)
    max_y = max(y_coords)
    width = max_x - min_x
    height = max_y - min_y

    # Padding uygula ve sınırları koru
    padded_min_x, padded_max_x = _apply_padding(min_x, max_x, width, img_width - 1)
    padded_min_y, padded_max_y = _apply_padding(min_y, max_y, height, img_height - 1)

    padded_width = padded_max_x - padded_min_x
    padded_height = padded_max_y - padded_min_y

    return {
        "min_x": padded_min_x,
        "max_x": padded_max_x,
        "min_y": padded_min_y,
        "max_y": padded_max_y,
        "center_x": (padded_min_x + padded_max_x) / 2,
        "center_y": (padded_min_y + padded_max_y) / 2,
        "width": padded_width,
        "height": padded_height
    }

def get_region_center(landmarks, region_indices, img_width, img_height):
    """Belirli bir yüz bölgesinin merkez noktasını hesaplar"""
    if not region_indices:
        return None
    
    landmark_list = _get_landmark_list(landmarks)
    if not landmark_list:
        return None
    
    x_sum = 0
    y_sum = 0
    count = 0
    
    for idx in region_indices:
        if idx < len(landmark_list):
            landmark = landmark_list[idx]
            x_sum += landmark.x * img_width
            y_sum += landmark.y * img_height
            count += 1
    
    if count == 0:
        return None
    
    return {
        "center_x": x_sum / count,
        "center_y": y_sum / count
    }

def process_video(video_path, output_file, landmarker):
    """Videoyu kare kare işleyip yüz landmark'larını çıkarır"""
    video_name = os.path.basename(video_path)
    video_id = os.path.splitext(video_name)[0]
    
    print(f"İşleniyor: {video_name}")
    
    try:
        reader = imageio.get_reader(video_path, "ffmpeg")
    except Exception as exc:
        print(f"Hata: {video_path} açılamadı! ({exc})")
        return
    
    with reader:
        try:
            meta = reader.get_meta_data()
        except Exception:
            meta = {}
        
        fps = meta.get("fps") or FPS
        fps = fps if fps and fps > 0 else FPS
        
        size = meta.get("size")
        if size and isinstance(size, (tuple, list)) and len(size) == 2:
            width, height = int(size[0]), int(size[1])
        else:
            width = height = None
        
        total_frames = None
        possible_frames = meta.get("nframes")
        if isinstance(possible_frames, (int, float)) and not math.isinf(possible_frames):
            total_frames = int(possible_frames)
        
        total_frames_display = total_frames if total_frames is not None else "?"
        width_display = width if width is not None else "?"
        height_display = height if height is not None else "?"
        print(f"  FPS: {fps}, Toplam kare: {total_frames_display}, Boyut: {width_display}x{height_display}")
        
        frame_data = []
        frame_number = 0
        
        for frame_number, frame in enumerate(reader, start=1):
            if frame is None:
                continue
            
            if frame.ndim == 2:
                # Gri tonlamalı kareleri RGB'ye genişlet
                frame = np.stack([frame] * 3, axis=-1)
            
            frame_height, frame_width = frame.shape[:2]
            if width is None or height is None:
                width, height = frame_width, frame_height
            
            frame_time = frame_number / fps  # Saniye cinsinden zaman
            
            rgb_frame = np.ascontiguousarray(frame)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            # Yüz landmark'larını tespit et
            results = landmarker.detect(mp_image)
            face_landmarks = results.face_landmarks[0] if results.face_landmarks else None
            
            frame_info = {
                "video_id": video_id,
                "frame_number": frame_number,
                "frame_time": round(frame_time, 3),
                "video_width": width,
                "video_height": height
            }
            
            if face_landmarks:
                # Her yüz bölgesi için koordinatları hesapla
                for region_name, region_indices in FACE_REGIONS.items():
                    bounds = get_region_bounds(face_landmarks, region_indices, width, height)
                    if bounds:
                        frame_info[f"{region_name}_min_x"] = int(bounds["min_x"])
                        frame_info[f"{region_name}_max_x"] = int(bounds["max_x"])
                        frame_info[f"{region_name}_min_y"] = int(bounds["min_y"])
                        frame_info[f"{region_name}_max_y"] = int(bounds["max_y"])
                        frame_info[f"{region_name}_center_x"] = round(bounds["center_x"], 2)
                        frame_info[f"{region_name}_center_y"] = round(bounds["center_y"], 2)
                        frame_info[f"{region_name}_width"] = int(bounds["width"])
                        frame_info[f"{region_name}_height"] = int(bounds["height"])
                    else:
                        frame_info[f"{region_name}_min_x"] = None
                        frame_info[f"{region_name}_max_x"] = None
                        frame_info[f"{region_name}_min_y"] = None
                        frame_info[f"{region_name}_max_y"] = None
                        frame_info[f"{region_name}_center_x"] = None
                        frame_info[f"{region_name}_center_y"] = None
                        frame_info[f"{region_name}_width"] = None
                        frame_info[f"{region_name}_height"] = None
            else:
                # Yüz bulunamadı
                for region_name in FACE_REGIONS.keys():
                    frame_info[f"{region_name}_min_x"] = None
                    frame_info[f"{region_name}_max_x"] = None
                    frame_info[f"{region_name}_min_y"] = None
                    frame_info[f"{region_name}_max_y"] = None
                    frame_info[f"{region_name}_center_x"] = None
                    frame_info[f"{region_name}_center_y"] = None
                    frame_info[f"{region_name}_width"] = None
                    frame_info[f"{region_name}_height"] = None
            
            frame_data.append(frame_info)
            
            # İlerleme göster
            if frame_number % 30 == 0:
                if total_frames is not None:
                    print(f"  İşlenen kare: {frame_number}/{total_frames}")
                else:
                    print(f"  İşlenen kare: {frame_number}")
    
    # CSV'ye kaydet
    if frame_data:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # CSV başlıkları
        fieldnames = ["video_id", "frame_number", "frame_time", "video_width", "video_height"]
        for region_name in FACE_REGIONS.keys():
            fieldnames.extend([
                f"{region_name}_min_x", f"{region_name}_max_x",
                f"{region_name}_min_y", f"{region_name}_max_y",
                f"{region_name}_center_x", f"{region_name}_center_y",
                f"{region_name}_width", f"{region_name}_height"
            ])
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(frame_data)
        
        print(f"  ✓ Kaydedildi: {output_file} ({len(frame_data)} kare)")
    else:
        print(f"  ⚠ Hiç veri bulunamadı!")

def main():
    """Tüm videoları işle"""
    video_dir = Path(VIDEO_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Tüm video dosyalarını bul
    video_files = sorted(video_dir.glob("*.mp4"))
    
    if not video_files:
        print(f"Videolar bulunamadı: {VIDEO_DIR}")
        return
    
    if not LANDMARKER_MODEL_PATH.exists():
        print(f"Model dosyası bulunamadı: {LANDMARKER_MODEL_PATH}. Lütfen modeli indirip tekrar deneyin.")
        return
    
    base_options = mp_tasks.BaseOptions(
        model_asset_path=str(LANDMARKER_MODEL_PATH),
        delegate=mp_tasks.BaseOptions.Delegate.CPU
    )
    landmarker_options = mp_vision.FaceLandmarkerOptions(
        base_options=base_options,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_facial_transformation_matrixes=False
    )
    
    print(f"Toplam {len(video_files)} video bulundu.\n")
    
    with mp_vision.FaceLandmarker.create_from_options(landmarker_options) as landmarker:
        for video_path in video_files:
            video_id = video_path.stem
            output_file = output_dir / f"{video_id}_landmarks.csv"
            
            # Eğer dosya zaten varsa atla (yeniden işlemek için silin)
            if output_file.exists():
                print(f"Atlanıyor (zaten var): {video_id}")
                continue
            
            process_video(str(video_path), str(output_file), landmarker)
            print()
    
    print("Tüm videolar işlendi!")

if __name__ == "__main__":
    main()

