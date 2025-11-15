"""
Kullanıcıların hangi yüz bölgelerine daha çok odaklandığını analiz eder.
Her kullanıcı için bölgeleri sıralı olarak gösterir.
"""

import pandas as pd
import os
from pathlib import Path

GAZE_ON_FACE_FILE = "results/gaze_on_face_regions.csv"
OUTPUT_FILE = "results/focus_regions_analysis.csv"
SUMMARY_FILE = "results/focus_regions_summary.txt"

# Yüz bölgeleri (önem sırasına göre)
FACE_REGIONS = [
    "left_eye", "right_eye", "nose", "mouth",
    "left_cheek", "right_cheek", "forehead", "chin"
]

def clean_region_name(region):
    """Bölge ismini temizler (near_ prefix'ini kaldırır)"""
    if region and region.startswith("near_"):
        return region.replace("near_", "")
    return region if region else "unknown"

def calculate_focus_metrics(df, participant_id=None, video_id=None):
    """Bakış metriklerini hesaplar"""
    # Filtreleme
    filtered_df = df.copy()
    if participant_id:
        filtered_df = filtered_df[filtered_df['participant_id'] == participant_id]
    if video_id:
        filtered_df = filtered_df[filtered_df['video_id'] == video_id]
    
    if len(filtered_df) == 0:
        return None
    
    # Bölge isimlerini temizle
    filtered_df['clean_region'] = filtered_df['gaze_region'].apply(clean_region_name)
    
    # Her bölge için metrikler
    region_stats = {}
    
    for region in FACE_REGIONS + ["unknown"]:
        region_data = filtered_df[filtered_df['clean_region'] == region]
        
        if len(region_data) == 0:
            continue
        
        # Bakış sayısı
        gaze_count = len(region_data)
        
        # Toplam bakış süresi (ardışık gaze noktaları arasındaki zaman farklarını topla)
        # Önce video_time'a göre sırala
        region_data_sorted = region_data.sort_values('video_time')
        
        # Ardışık noktalar arası zaman farklarını hesapla
        time_diffs = region_data_sorted['video_time'].diff().dropna()
        # Ortalama örnekleme hızı (30Hz = 0.033s)
        avg_sample_rate = 0.033
        # Her gaze noktası için ortalama süre
        total_duration = gaze_count * avg_sample_rate
        
        # Bölge içinde olan gaze noktaları (distance_to_region == 0)
        inside_count = len(region_data[region_data['distance_to_region'] == 0])
        
        # Ortalama mesafe (bölge merkezine)
        avg_distance = region_data['distance_to_region'].mean() if 'distance_to_region' in region_data.columns else 0
        
        # Yüzde oranı
        percentage = (gaze_count / len(filtered_df)) * 100
        
        region_stats[region] = {
            'gaze_count': gaze_count,
            'total_duration': round(total_duration, 2),
            'percentage': round(percentage, 2),
            'inside_count': inside_count,
            'avg_distance': round(avg_distance, 2) if pd.notna(avg_distance) else 0
        }
    
    return region_stats

def analyze_all_participants():
    """Tüm katılımcılar için analiz yapar"""
    print("Gaze verileri yükleniyor...")
    
    if not os.path.exists(GAZE_ON_FACE_FILE):
        print(f"Hata: {GAZE_ON_FACE_FILE} bulunamadı!")
        return
    
    df = pd.read_csv(GAZE_ON_FACE_FILE)
    print(f"✓ {len(df)} gaze kaydı yüklendi\n")
    
    # Tüm katılımcılar
    participants = df['participant_id'].unique()
    
    all_results = []
    summary_lines = []
    
    summary_lines.append("=" * 80)
    summary_lines.append("YÜZ BÖLGELERİNE ODAKLANMA ANALİZİ")
    summary_lines.append("=" * 80)
    summary_lines.append("")
    
    for participant_id in sorted(participants):
        print(f"Analiz ediliyor: {participant_id}")
        
        # Katılımcı için metrikler
        region_stats = calculate_focus_metrics(df, participant_id=participant_id)
        
        if not region_stats:
            continue
        
        # Bölgeleri yüzde oranına göre sırala (yüksekten düşüğe)
        sorted_regions = sorted(
            region_stats.items(),
            key=lambda x: x[1]['percentage'],
            reverse=True
        )
        
        # Sonuçları kaydet
        summary_lines.append(f"\n{'=' * 80}")
        summary_lines.append(f"KATILIMCI: {participant_id}")
        summary_lines.append(f"{'=' * 80}")
        summary_lines.append(f"{'Bölge':<20} {'Bakış Sayısı':<15} {'Süre (s)':<12} {'Yüzde (%)':<12} {'İçinde':<10} {'Ort. Mesafe':<12}")
        summary_lines.append("-" * 80)
        
        for region, stats in sorted_regions:
            # Türkçe bölge isimleri
            region_names = {
                'left_eye': 'Sol Göz',
                'right_eye': 'Sağ Göz',
                'nose': 'Burun',
                'mouth': 'Ağız',
                'left_cheek': 'Sol Yanak',
                'right_cheek': 'Sağ Yanak',
                'forehead': 'Alın',
                'chin': 'Çene',
                'unknown': 'Bilinmeyen'
            }
            region_tr = region_names.get(region, region)
            
            summary_lines.append(
                f"{region_tr:<20} {stats['gaze_count']:<15} {stats['total_duration']:<12.2f} "
                f"{stats['percentage']:<12.2f} {stats['inside_count']:<10} {stats['avg_distance']:<12.2f}"
            )
            
            # CSV için veri
            all_results.append({
                'participant_id': participant_id,
                'region': region,
                'region_tr': region_tr,
                'gaze_count': stats['gaze_count'],
                'total_duration': stats['total_duration'],
                'percentage': stats['percentage'],
                'inside_count': stats['inside_count'],
                'avg_distance': stats['avg_distance'],
                'rank': len([r for r, s in sorted_regions if s['percentage'] > stats['percentage']]) + 1
            })
        
        # Toplam istatistikler
        total_gaze = sum(s['gaze_count'] for _, s in sorted_regions)
        total_duration = sum(s['total_duration'] for _, s in sorted_regions)
        
        summary_lines.append("-" * 80)
        summary_lines.append(f"{'TOPLAM':<20} {total_gaze:<15} {total_duration:<12.2f}")
        summary_lines.append("")
        
        # En çok odaklanılan 3 bölge
        top_3 = sorted_regions[:3]
        summary_lines.append("🏆 En Çok Odaklanılan 3 Bölge:")
        for i, (region, stats) in enumerate(top_3, 1):
            region_names = {
                'left_eye': 'Sol Göz',
                'right_eye': 'Sağ Göz',
                'nose': 'Burun',
                'mouth': 'Ağız',
                'left_cheek': 'Sol Yanak',
                'right_cheek': 'Sağ Yanak',
                'forehead': 'Alın',
                'chin': 'Çene',
                'unknown': 'Bilinmeyen'
            }
            region_tr = region_names.get(region, region)
            summary_lines.append(f"  {i}. {region_tr}: %{stats['percentage']:.2f} ({stats['gaze_count']} bakış, {stats['total_duration']:.2f}s)")
        summary_lines.append("")
    
    # CSV'ye kaydet
    if all_results:
        results_df = pd.DataFrame(all_results)
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        results_df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8')
        print(f"\n✓ Detaylı sonuçlar kaydedildi: {OUTPUT_FILE}")
    
    # Özet dosyasına kaydet
    summary_text = "\n".join(summary_lines)
    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"✓ Özet rapor kaydedildi: {SUMMARY_FILE}")
    
    # Konsola yazdır
    print("\n" + summary_text)
    
    return results_df if all_results else None

def analyze_by_video(participant_id=None):
    """Video bazında analiz - tüm katılımcılar için"""
    print("\n" + "=" * 80)
    print("VİDEO BAZINDA ANALİZ (TÜM KATILIMCILAR)")
    print("=" * 80)
    
    if not os.path.exists(GAZE_ON_FACE_FILE):
        print(f"Hata: {GAZE_ON_FACE_FILE} bulunamadı!")
        return
    
    df = pd.read_csv(GAZE_ON_FACE_FILE)
    
    videos = df['video_id'].unique()
    
    video_results = []
    video_detailed_results = []
    
    for video_id in sorted(videos):
        video_data = df[df['video_id'] == video_id]
        region_stats = calculate_focus_metrics(df, video_id=video_id)
        
        if not region_stats:
            continue
        
        # En çok bakılan bölge
        sorted_regions = sorted(
            region_stats.items(),
            key=lambda x: x[1]['percentage'],
            reverse=True
        )
        top_region = sorted_regions[0]
        
        video_results.append({
            'video_id': video_id,
            'top_region': clean_region_name(top_region[0]),
            'top_region_percentage': top_region[1]['percentage'],
            'total_gaze': sum(s['gaze_count'] for s in region_stats.values())
        })
        
        # Detaylı sonuçlar (tüm bölgeler)
        for region, stats in sorted_regions:
            video_detailed_results.append({
                'video_id': video_id,
                'region': clean_region_name(region),
                'gaze_count': stats['gaze_count'],
                'total_duration': stats['total_duration'],
                'percentage': stats['percentage'],
                'rank': len([r for r, s in sorted_regions if s['percentage'] > stats['percentage']]) + 1
            })
    
    # Video bazında sonuçları göster
    print(f"\n{'Video ID':<20} {'En Çok Bakılan Bölge':<25} {'Yüzde (%)':<12} {'Toplam Bakış':<15}")
    print("-" * 80)
    for result in sorted(video_results, key=lambda x: x['top_region_percentage'], reverse=True):
        region_names = {
            'left_eye': 'Sol Göz',
            'right_eye': 'Sağ Göz',
            'nose': 'Burun',
            'mouth': 'Ağız',
            'left_cheek': 'Sol Yanak',
            'right_cheek': 'Sağ Yanak',
            'forehead': 'Alın',
            'chin': 'Çene',
            'unknown': 'Bilinmeyen'
        }
        region_tr = region_names.get(result['top_region'], result['top_region'])
        print(f"{result['video_id']:<20} {region_tr:<25} {result['top_region_percentage']:<12.2f} {result['total_gaze']:<15}")
    
    # Detaylı CSV'ye kaydet
    if video_detailed_results:
        video_df = pd.DataFrame(video_detailed_results)
        video_output_file = "results/video_focus_regions_analysis.csv"
        os.makedirs(os.path.dirname(video_output_file), exist_ok=True)
        video_df.to_csv(video_output_file, index=False, encoding='utf-8')
        print(f"\n✓ Video bazında detaylı sonuçlar kaydedildi: {video_output_file}")
    
    return video_results, video_detailed_results

def analyze_participant_by_video():
    """Her kullanıcı için video bazında detaylı analiz"""
    print("\n" + "=" * 80)
    print("KULLANICI BAZINDA VİDEO ANALİZİ")
    print("=" * 80)
    
    if not os.path.exists(GAZE_ON_FACE_FILE):
        print(f"Hata: {GAZE_ON_FACE_FILE} bulunamadı!")
        return
    
    df = pd.read_csv(GAZE_ON_FACE_FILE)
    participants = df['participant_id'].unique()
    
    participant_video_results = []
    summary_lines = []
    
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("KULLANICI BAZINDA VİDEO ANALİZİ")
    summary_lines.append("=" * 80)
    
    for participant_id in sorted(participants):
        print(f"\nAnaliz ediliyor: {participant_id}")
        summary_lines.append(f"\n{'=' * 80}")
        summary_lines.append(f"KATILIMCI: {participant_id}")
        summary_lines.append(f"{'=' * 80}")
        
        participant_data = df[df['participant_id'] == participant_id]
        videos = sorted(participant_data['video_id'].unique())
        
        for video_id in videos:
            video_data = participant_data[participant_data['video_id'] == video_id]
            region_stats = calculate_focus_metrics(video_data)
            
            if not region_stats:
                continue
            
            # Bölgeleri sırala
            sorted_regions = sorted(
                region_stats.items(),
                key=lambda x: x[1]['percentage'],
                reverse=True
            )
            
            top_region = sorted_regions[0]
            
            # Özet bilgi
            region_names = {
                'left_eye': 'Sol Göz',
                'right_eye': 'Sağ Göz',
                'nose': 'Burun',
                'mouth': 'Ağız',
                'left_cheek': 'Sol Yanak',
                'right_cheek': 'Sağ Yanak',
                'forehead': 'Alın',
                'chin': 'Çene',
                'unknown': 'Bilinmeyen'
            }
            top_region_tr = region_names.get(clean_region_name(top_region[0]), clean_region_name(top_region[0]))
            
            summary_lines.append(f"\n  📹 {video_id}")
            summary_lines.append(f"     En çok bakılan: {top_region_tr} (%{top_region[1]['percentage']:.2f}, {top_region[1]['gaze_count']} bakış)")
            summary_lines.append(f"     Toplam bakış: {sum(s['gaze_count'] for s in region_stats.values())}")
            summary_lines.append(f"     Bölge sıralaması:")
            
            # İlk 3 bölgeyi göster
            for i, (region, stats) in enumerate(sorted_regions[:3], 1):
                region_tr = region_names.get(clean_region_name(region), clean_region_name(region))
                summary_lines.append(f"       {i}. {region_tr}: %{stats['percentage']:.2f} ({stats['gaze_count']} bakış)")
            
            # CSV için detaylı veri
            for region, stats in sorted_regions:
                participant_video_results.append({
                    'participant_id': participant_id,
                    'video_id': video_id,
                    'region': clean_region_name(region),
                    'region_tr': region_names.get(clean_region_name(region), clean_region_name(region)),
                    'gaze_count': stats['gaze_count'],
                    'total_duration': stats['total_duration'],
                    'percentage': stats['percentage'],
                    'rank': len([r for r, s in sorted_regions if s['percentage'] > stats['percentage']]) + 1,
                    'is_top_region': 1 if region == top_region[0] else 0
                })
    
    # CSV'ye kaydet
    if participant_video_results:
        participant_video_df = pd.DataFrame(participant_video_results)
        participant_video_output = "results/participant_video_focus_analysis.csv"
        os.makedirs(os.path.dirname(participant_video_output), exist_ok=True)
        participant_video_df.to_csv(participant_video_output, index=False, encoding='utf-8')
        print(f"\n✓ Kullanıcı-video bazında detaylı sonuçlar kaydedildi: {participant_video_output}")
    
    # Özet dosyasına ekle
    summary_text = "\n".join(summary_lines)
    with open(SUMMARY_FILE, 'a', encoding='utf-8') as f:
        f.write(summary_text)
    
    # Konsola yazdır
    print(summary_text)
    
    return participant_video_df if participant_video_results else None

if __name__ == "__main__":
    # Tüm katılımcılar için analiz
    results_df = analyze_all_participants()
    
    # Video bazında analiz (tüm katılımcılar)
    video_results, video_detailed = analyze_by_video()
    
    # Kullanıcı bazında video analizi
    participant_video_df = analyze_participant_by_video()
    
    print("\n" + "=" * 80)
    print("Analiz tamamlandı!")
    print("=" * 80)
    print("\nOluşturulan dosyalar:")
    print(f"  - {OUTPUT_FILE} (Kullanıcı bazında genel analiz)")
    print(f"  - {SUMMARY_FILE} (Özet rapor)")
    print(f"  - results/video_focus_regions_analysis.csv (Video bazında analiz)")
    print(f"  - results/participant_video_focus_analysis.csv (Kullanıcı-video bazında detaylı analiz)")

