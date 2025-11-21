from psychopy import visual, event, core, gui, monitors
import os
import json
import csv
import time
from collections import OrderedDict
from eye_tracker import EyeTracker

# === Global Ayarlar === #
VIDEO_DIR = "videos"
RESULTS_FILE = "results/answers.csv"
GAZE_DATA_FILE = "results/gaze_data.csv"
QUESTIONS_FILE = "questions.json"
SURVEY_FILE = "results/survey_answers.csv"
DEMOGRAPHIC_FILE = "results/demographic_data.csv"

# Video boyutları: 720p (1280x720) 30fps
# Uygulama fullscreen olacak, video kalitesi korunacak
# Ekran boyutları window oluşturulduğunda alınacak
SCREEN_WIDTH = None  # Fullscreen'de otomatik alınacak
SCREEN_HEIGHT = None  # Fullscreen'de otomatik alınacak

# Monitor tanımlaması
def setup_monitor():
    """Monitor spesifikasyonunu oluşturur"""
    monitor = monitors.Monitor('default')
    # Fullscreen için monitor boyutlarını otomatik al
    monitor.setWidth(30)
    monitor.setDistance(57)
    return monitor

# Window'u başlangıçta None olarak tanımla (login'den sonra oluşturulacak)
win = None

# Eye tracker global değişkeni
eye_tracker = None

def save_demographic_data(participant_id, demographic_data):
    """Demografik verileri CSV dosyasına kaydeder"""
    os.makedirs(os.path.dirname(DEMOGRAPHIC_FILE), exist_ok=True)
    file_exists = os.path.isfile(DEMOGRAPHIC_FILE)
    
    with open(DEMOGRAPHIC_FILE, 'a', newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "participant_id", "cinsiyet", "yas", "egitim_durumu", "meslek",
                "nöromodülasyon_aldı_mı", "nöromodülasyon_kaç_kez", "nöromodülasyon_ne_zaman",
                "görme_bozukluğu_var_mı", "görme_bozukluğu_detay", "onam_durumu"
            ])
        writer.writerow([
            participant_id,
            demographic_data.get("cinsiyet", ""),
            demographic_data.get("yas", ""),
            demographic_data.get("egitim_durumu", ""),
            demographic_data.get("meslek", ""),
            demographic_data.get("nöromodülasyon_aldı_mı", ""),
            demographic_data.get("nöromodülasyon_kaç_kez", ""),
            demographic_data.get("nöromodülasyon_ne_zaman", ""),
            demographic_data.get("görme_bozukluğu_var_mı", ""),
            demographic_data.get("görme_bozukluğu_detay", ""),
            demographic_data.get("onam_durumu", "")
        ])

def run_demographic_form():
    """Demografik bilgi formunu tek bir pop-up dialog olarak çalıştırır ve participant_id (rumuz) döndürür"""
    demographic_data = {}
    
    # PsychoPy'nin DlgFromDict alfabetik sıralama yapıyor, bu yüzden manuel Dlg kullanıyoruz
    # Word dosyasındaki sıra: Rumuz, Cinsiyet, Yaş, Eğitim, Meslek, Nöromodülasyon soruları, Görme bozukluğu soruları
    dlg = gui.Dlg(title="Demografik Bilgi Formu", screen=0)
    
    # Sırayı korumak için fieldOrder kullanıyoruz
    # Rumuz en üstte
    dlg.addField('Rumuz:', '')
    dlg.addField('Cinsiyetiniz:', choices=['Kadın', 'Erkek'])
    dlg.addField('Yaşınız:', '')
    dlg.addField('Eğitim Durumunuz (En son tamamladığınız):', choices=['Lise', 'Ön Lisans', 'Lisans', 'Yüksek Lisans', 'Doktora'])
    dlg.addField('Mesleğiniz:', '')
    dlg.addField('Daha önce kozmetik amaçlı nöromodülasyon (Botoks vb.) tedavisi aldınız mı?', choices=['Evet', 'Hayır'])
    dlg.addField('Eğer evet ise, toplam kaç kez bu tedaviyi aldınız?', '')
    dlg.addField('Nöromodülasyon tedavisini en son ne zaman aldınız?', choices=['', '0–3 ay önce', '3–6 ay önce', '6 ay–1 yıl önce', '1 yıldan uzun süre önce'])
    dlg.addField('Duygusal yüz ifadelerini görsel olarak algılamanızı etkileyebilecek herhangi bir görme bozukluğunuz veya nörolojik hastalığınız var mı?', choices=['Evet', 'Hayır'])
    dlg.addField('Lütfen belirtiniz (Eğer görme bozukluğu veya nörolojik hastalık varsa):', '')
    
    # Zorunlu alan kontrolü ile döngü
    while True:
        dlg.show()
        
        if not dlg.OK:
            safe_exit()
        
        # Verileri al (dlg.data listesi olarak döner, sırayla)
        results = dlg.data
        
        # Zorunlu alan kontrolü
        errors = []
        
        # Rumuz (zorunlu)
        if not results[0] or not results[0].strip():
            errors.append("Rumuz alanı zorunludur.")
        
        # Cinsiyet (zorunlu)
        if not results[1]:
            errors.append("Cinsiyet seçimi zorunludur.")
        
        # Yaş (zorunlu)
        if not results[2] or not results[2].strip():
            errors.append("Yaş alanı zorunludur.")
        
        # Eğitim durumu (zorunlu)
        if not results[3]:
            errors.append("Eğitim durumu seçimi zorunludur.")
        
        # Meslek (zorunlu)
        if not results[4] or not results[4].strip():
            errors.append("Meslek alanı zorunludur.")
        
        # Nöromodülasyon (zorunlu)
        if not results[5]:
            errors.append("Nöromodülasyon sorusu zorunludur.")
        
        # Nöromodülasyon koşullu alanlar (sadece "Evet" ise zorunlu)
        if results[5] == "Evet":
            if not results[6] or not results[6].strip():
                errors.append("Nöromodülasyon kaç kez alındığı zorunludur (Evet seçildiğinde).")
            if not results[7] or results[7] == "":
                errors.append("Nöromodülasyon ne zaman alındığı zorunludur (Evet seçildiğinde).")
        
        # Görme bozukluğu (zorunlu)
        if not results[8]:
            errors.append("Görme bozukluğu sorusu zorunludur.")
        
        # Görme bozukluğu koşullu alan (sadece "Evet" ise zorunlu)
        if results[8] == "Evet":
            if not results[9] or not results[9].strip():
                errors.append("Görme bozukluğu detayı zorunludur (Evet seçildiğinde).")
        
        # Hata yoksa döngüden çık
        if not errors:
            break
        
        # Hata varsa mesaj göster ve tekrar formu aç
        error_msg = "Lütfen aşağıdaki alanları doldurun:\n\n" + "\n".join(errors)
        error_dlg = gui.Dlg(title="Eksik Bilgi", screen=0)
        error_dlg.addText(error_msg)
        error_dlg.show()
        
        # Formu tekrar oluştur (değerleri koru)
        dlg = gui.Dlg(title="Demografik Bilgi Formu", screen=0)
        dlg.addField('Rumuz:', results[0] if results[0] else '')
        dlg.addField('Cinsiyetiniz:', choices=['Kadın', 'Erkek'])
        dlg.addField('Yaşınız:', results[2] if results[2] else '')
        dlg.addField('Eğitim Durumunuz (En son tamamladığınız):', choices=['Lise', 'Ön Lisans', 'Lisans', 'Yüksek Lisans', 'Doktora'])
        dlg.addField('Mesleğiniz:', results[4] if results[4] else '')
        dlg.addField('Daha önce kozmetik amaçlı nöromodülasyon (Botoks vb.) tedavisi aldınız mı?', choices=['Evet', 'Hayır'])
        dlg.addField('Eğer evet ise, toplam kaç kez bu tedaviyi aldınız?', results[6] if results[6] else '')
        dlg.addField('Nöromodülasyon tedavisini en son ne zaman aldınız?', choices=['', '0–3 ay önce', '3–6 ay önce', '6 ay–1 yıl önce', '1 yıldan uzun süre önce'])
        dlg.addField('Duygusal yüz ifadelerini görsel olarak algılamanızı etkileyebilecek herhangi bir görme bozukluğunuz veya nörolojik hastalığınız var mı?', choices=['Evet', 'Hayır'])
        dlg.addField('Lütfen belirtiniz (Eğer görme bozukluğu veya nörolojik hastalık varsa):', results[9] if results[9] else '')
    
    # Verileri kaydet
    demographic_data["rumuz"] = results[0]
    demographic_data["cinsiyet"] = results[1]
    demographic_data["yas"] = results[2]
    demographic_data["egitim_durumu"] = results[3]
    demographic_data["meslek"] = results[4]
    demographic_data["nöromodülasyon_aldı_mı"] = results[5]
    
    # Nöromodülasyon koşullu sorular
    if demographic_data["nöromodülasyon_aldı_mı"] == "Evet":
        demographic_data["nöromodülasyon_kaç_kez"] = results[6] if results[6] else ""
        nöromodülasyon_zaman = results[7] if results[7] else ""
        demographic_data["nöromodülasyon_ne_zaman"] = nöromodülasyon_zaman if nöromodülasyon_zaman else ""
    else:
        demographic_data["nöromodülasyon_kaç_kez"] = ""
        demographic_data["nöromodülasyon_ne_zaman"] = ""
    
    # Görme bozukluğu koşullu sorular
    demographic_data["görme_bozukluğu_var_mı"] = results[8]
    if demographic_data["görme_bozukluğu_var_mı"] == "Evet":
        demographic_data["görme_bozukluğu_detay"] = results[9] if results[9] else ""
    else:
        demographic_data["görme_bozukluğu_detay"] = ""
    
    # Participant ID: Rumuz
    participant_id = demographic_data["rumuz"]
    
    # Verileri kaydet (onam durumu henüz yok, sonra eklenecek)
    # save_demographic_data(participant_id, demographic_data)  # Onam sonrası kaydedilecek
    
    return participant_id, demographic_data

# Gaze verilerini toplu kaydetmek için buffer
gaze_buffer = []
GAZE_BUFFER_SIZE = 50  # 50 veri toplandığında dosyaya yaz

def save_gaze_data(participant_id, video_id, x, y, timestamp, video_time, flush=False):
    """Gaze verilerini buffer'a ekler, buffer dolduğunda veya flush=True olduğunda CSV'ye kaydeder"""
    global gaze_buffer
    
    # Eğer flush isteniyorsa sadece buffer'ı kaydet, yeni veri ekleme
    if flush:
        if len(gaze_buffer) > 0:
            os.makedirs(os.path.dirname(GAZE_DATA_FILE), exist_ok=True)
            file_exists = os.path.isfile(GAZE_DATA_FILE)
            
            with open(GAZE_DATA_FILE, 'a', newline='', encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["participant_id", "video_id", "gaze_x", "gaze_y", "timestamp", "video_time"])
                writer.writerows(gaze_buffer)
            
            gaze_buffer = []  # Buffer'ı temizle
        return
    
    # Normal durumda veriyi buffer'a ekle (sadece geçerli veriler)
    # 0,0 değerleri de geçerli olabilir (ekranın sol üst köşesi), bu yüzden hepsini kaydet
    gaze_buffer.append([
        participant_id,
        video_id,
        round(x, 2),
        round(y, 2),
        round(timestamp, 3),
        round(video_time, 3)
    ])
    
    # Buffer dolduğunda dosyaya yaz (videolar oynatılırken otomatik yazılır)
    if len(gaze_buffer) >= GAZE_BUFFER_SIZE:
        os.makedirs(os.path.dirname(GAZE_DATA_FILE), exist_ok=True)
        file_exists = os.path.isfile(GAZE_DATA_FILE)
        
        with open(GAZE_DATA_FILE, 'a', newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["participant_id", "video_id", "gaze_x", "gaze_y", "timestamp", "video_time"])
            writer.writerows(gaze_buffer)
        
        gaze_buffer = []  # Buffer'ı temizle

def flush_gaze_buffer():
    """Buffer'daki kalan gaze verilerini CSV'ye yazar (video bitince kullanılır)"""
    global gaze_buffer
    if len(gaze_buffer) > 0:
        os.makedirs(os.path.dirname(GAZE_DATA_FILE), exist_ok=True)
        file_exists = os.path.isfile(GAZE_DATA_FILE)
        
        with open(GAZE_DATA_FILE, 'a', newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["participant_id", "video_id", "gaze_x", "gaze_y", "timestamp", "video_time"])
            writer.writerows(gaze_buffer)
        
        gaze_buffer = []  # Buffer'ı temizle

def play_video_with_controls(video_path, video_index=None, participant_id=None, video_id=None):
    """
    Videoyu fullscreen'de kaliteyi koruyarak oynatır.
    Video aspect ratio'su korunur, ekrana sığdırılır (letterbox/pillarbox).
    """
    global SCREEN_WIDTH, SCREEN_HEIGHT
    
    # Ekran boyutlarını al (fullscreen window'dan)
    screen_width = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
    screen_height = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
    
    # Video aspect ratio'sunu koruyarak ekrana sığdır
    # Video genellikle 1280x720 (16:9) olduğu için bunu varsayıyoruz
    # Gerçek video boyutunu almak için video dosyasını açıp kontrol edebiliriz
    # Ancak performans için varsayılan 16:9 kullanıyoruz
    video_aspect = 16.0 / 9.0  # 1280x720 için aspect ratio
    screen_aspect = screen_width / screen_height
    
    # Aspect ratio'yu koruyarak video boyutunu hesapla
    if screen_aspect > video_aspect:
        # Ekran daha geniş (widescreen), yüksekliği kullan (letterbox)
        video_height = screen_height
        video_width = video_height * video_aspect
    else:
        # Ekran daha yüksek veya eşit, genişliği kullan (pillarbox)
        video_width = screen_width
        video_height = video_width / video_aspect
    
    # Video boyutunu hesapla (kaliteyi korumak için tam piksel değerleri)
    video_size = (int(video_width), int(video_height))
    
    # Video yükleme optimizasyonu: noAudio=True (ses kapalı), loop=False
    # size parametresi ile aspect ratio korunur ve kalite bozulmaz
    video = visual.MovieStim(
        win, 
        filename=video_path, 
        size=video_size,  # Aspect ratio korunarak ekrana sığdırılmış boyut
        flipVert=False,
        noAudio=True,  # Ses kapalı (performans için ve kullanıcı isteği)
        loop=False,  # Tekrar oynatma
        # Performans optimizasyonları
        autoStart=False,  # Otomatik başlatma kapalı (manuel kontrol)
        volume=0.0  # Ses seviyesi 0 (ekstra güvence)
    )
    
    # Ön-video ekranı - TextStim'leri önceden oluştur (her frame'de yeniden oluşturma)
    # Ekran boyutlarını güvenli şekilde al
    screen_w = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
    screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
    
    instruction_text = f"{video_index or ''} Videoyu oynatmak için aşağıdaki 'Oynat' butonuna tıklayın"
    instruction = visual.TextStim(
        win, 
        text=instruction_text.strip(), 
        pos=(0, screen_h * 0.15), 
        height=screen_h * 0.04, 
        color='white', 
        wrapWidth=screen_w * 0.8
    )
    play_rect = visual.Rect(
        win, 
        width=screen_w * 0.15, 
        height=screen_h * 0.07, 
        fillColor='white', 
        pos=(0, 0)
    )
    play_label = visual.TextStim(
        win, 
        text="Oynat", 
        pos=(0, 0), 
        height=screen_h * 0.035, 
        color='black'
    )
    mouse = event.Mouse(win=win, visible=True)
    
    # Event polling optimizasyonu - clock kullan
    wait_clock = core.Clock()
    wait_clock.reset()

    # Kullanıcı tıklayana kadar bekle - optimizasyon: event polling'i azalt
    while True:
        instruction.draw()
        play_rect.draw()
        play_label.draw()
        win.flip()
        
        # Mouse kontrolü - sadece gerektiğinde kontrol et
        if mouse.getPressed()[0]:
            if play_rect.contains(mouse):
                break
        
        # Klavye kontrolü - non-blocking
        keys = event.getKeys(keyList=['escape'], timeStamped=False)
        if 'escape' in keys:
            video.stop()
            safe_exit()
            return
        
        # CPU kullanımını azaltmak için kısa bekleme
        core.wait(0.01, hogCPUperiod=0.0)

    video.play()
    # Mouse'u gizle (video oynatılırken)
    win.setMouseVisible(False)
    
    # Zamana dayalı oynatma kontrolü - optimizasyon: sadece video duration kontrolü
    clock = core.Clock()
    clock.reset()
    
    # Gaze verisi kaydetme optimizasyonu - zaman bazlı örnekleme
    last_gaze_time = 0
    gaze_sample_rate = 1.0 / 30.0  # 30Hz (her 33ms'de bir)
    # Floating point precision için küçük bir tolerans ekle
    min_sample_interval = gaze_sample_rate - 0.001  # 1ms tolerans
    
    # Video oynatma loop'u - optimize edilmiş
    # Video oynatma için PsychoPy'nin kendi timing'ini kullan
    while clock.getTime() < video.duration:
        # Video frame'ini çiz ve göster
        video.draw()
        win.flip()
        
        # ESC tuşu kontrolü - sadece ara sıra kontrol et (performans için)
        current_time = clock.getTime()
        if int(current_time * 5) % 5 == 0:  # Her 0.2 saniyede bir kontrol et
            keys = event.getKeys(keyList=['escape'], timeStamped=False)
            if 'escape' in keys:
                video.stop()
                win.setMouseVisible(True)  # Mouse'u tekrar göster
                safe_exit()
                return
        
        # Eye tracking verilerini kaydet (optimize edilmiş - zaman bazlı)
        # Gaze verileri video ekran koordinatlarına göre normalize edilir
        # Daha sıkı zamanlama kontrolü: >= yerine > kullan ve tolerans ekle
        time_since_last_gaze = current_time - last_gaze_time
        if time_since_last_gaze >= min_sample_interval:
            # last_gaze_time'i güncelle (örnekleme yapılsa da yapılmasa da)
            last_gaze_time = current_time
            
            if eye_tracker and eye_tracker.is_tracking():
                gaze_data = None
                
                # Önce get_latest_gaze() ile listener thread'den veri al (daha hızlı)
                gaze_data = eye_tracker.get_latest_gaze()
                
                # Eğer veri yoksa (None), get_gaze_data() ile manuel istek yap (fallback)
                # Not: 0,0 geçerli bir değer olabilir (ekranın sol üst köşesi), bu yüzden sadece None kontrolü yap
                if not gaze_data:
                    try:
                        # Manuel istek yap - bazen listener thread gecikebilir
                        gaze_data = eye_tracker.get_gaze_data()
                    except:
                        gaze_data = None
                
                # Veri varsa işle ve kaydet
                if gaze_data and participant_id and video_id:
                    x, y, timestamp = gaze_data
                    
                    # Geçersiz değerleri filtrele (çok büyük veya NaN değerler)
                    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                        x, y = 0, 0
                    if abs(x) > 100000 or abs(y) > 100000 or (x != x) or (y != y):  # NaN kontrolü
                        x, y = 0, 0

                    # TheEyeTribe 'avg' koordinatları normalize (0-1 arası) olabiliyor.
                    # Eğer gelen değerler bu aralıktaysa ekran pikseline ölçekle.
                    # Ekran boyutlarını güvenli şekilde al
                    screen_w = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
                    screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
                    
                    if -0.5 <= x <= 1.5 and -0.5 <= y <= 1.5:
                        x *= screen_w
                        y *= screen_h

                    # Ekran sınırlarını aşmasını engelle
                    x_clamped = max(0, min(screen_w, x))
                    y_clamped = max(0, min(screen_h, y))
                    video_time = current_time
                    
                    # Tüm gaze verilerini kaydet (0,0 dahil - ekranın sol üst köşesi geçerli bir değer)
                    # Buffer otomatik olarak 50 veri toplandığında CSV'ye yazacak
                    save_gaze_data(participant_id, video_id, x_clamped, y_clamped, timestamp, video_time, flush=False)
    
    # Video bittiğinde kalan gaze verilerini kaydet (buffer'da kalan veriler)
    # Not: Bu sadece buffer'daki kalan verileri yazar, yeni veri eklemez
    flush_gaze_buffer()
    
    video.stop()
    # Mouse'u tekrar göster (video bittiğinde)
    win.setMouseVisible(True)
    # Video objesini temizle (memory optimizasyonu)
    del video
            
def load_questions(video_id):
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # JSON is a dict with key "1" mapping to a list of questions; use that list
    questions = data.get("1", [])
    return questions[:2]  # always return first two questions

def ask_question(q_data, video_id, index, participant_id):
    global SCREEN_WIDTH, SCREEN_HEIGHT
    question = q_data["question"]
    options = q_data["options"]

    # Soru ve seçenekleri ekran boyutuna göre ayarla
    # Ekran boyutlarını güvenli şekilde al
    screen_w = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
    screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
    
    question_height = screen_h * 0.25
    button_height = screen_h * 0.08
    option_spacing = screen_h * 0.10  # Butonlar arası sabit boşluk
    num_options = len(options)
    
    # Soru ile butonlar arasında boşluk bırak
    question_bottom = question_height - screen_h * 0.08  # Soru metninin alt kenarı
    # İlk butonun pozisyonunu hesapla (sorunun altından başla, daha yukarı)
    start_y = question_bottom - screen_h * 0.05  # Sorunun altından 5% boşluk (daha az boşluk = daha yukarı)
    
    question_text = visual.TextStim(
        win, 
        text=question, 
        pos=(0, question_height), 
        height=screen_h * 0.04, 
        wrapWidth=screen_w * 0.8,
        color='white'
    )
    
    # Butonlar ve metinler için listeler
    option_buttons = []
    option_texts = []
    option_keys = []
    mouse = event.Mouse(win=win, visible=True)
    
    for i, opt in enumerate(options):
        # Buton pozisyonunu hesapla (yukarıdan aşağıya, ekranın ortasından başla)
        y_pos = start_y - i * option_spacing
        key_label = chr(65 + i)  # A, B, C, D, E, F...
        
        # Buton boyutları - metni kapsayacak şekilde
        button_width = screen_w * 0.6
        
        # Buton oluştur (beyaz arka plan, siyah kenarlık)
        # Butonun merkez noktası y_pos'ta olacak
        button = visual.Rect(
            win,
            width=button_width,
            height=button_height,
            pos=(0, y_pos),  # Butonun merkez noktası
            fillColor='white',
            lineColor='black',
            lineWidth=2
        )
        option_buttons.append(button)
        
        # Buton üzerindeki metin (siyah yazı) - harf etiketi olmadan
        # Metin butonun tam ortasında olmalı (buton ile aynı pozisyon)
        option_text = visual.TextStim(
            win, 
            text=opt,  # Sadece seçenek metni, harf etiketi yok
            pos=(0, y_pos),  # Buton ile tam aynı pozisyon (merkez noktası)
            height=screen_h * 0.03,
            color='black',
            wrapWidth=button_width * 0.85,  # Biraz daha dar wrapWidth
            alignText='center',  # Metni ortala
            anchorHoriz='center',  # Yatay ortalama
            anchorVert='center'  # Dikey ortalama
        )
        option_texts.append(option_text)
        option_keys.append(key_label.lower())

    # İlk çizim için zamanlayıcı (PsychoPy'nin global clock'unu kullan)
    start_time = core.getTime()
    mouse.clickReset()  # Mouse tıklama geçmişini temizle
    last_click_state = False
    
    # Event polling optimizasyonu
    event_clock = core.Clock()
    event_clock.reset()
    last_event_check = 0
    
    while True:
        # Soru metnini çiz
        question_text.draw()
        
        # Butonları ve metinleri çiz
        for button, text in zip(option_buttons, option_texts):
            button.draw()
            text.draw()
        
        win.flip()
        
        current_time = event_clock.getTime()
        
        # Event kontrolü - sadece belirli aralıklarla (performans için)
        if current_time - last_event_check >= 0.01:  # Her 10ms'de bir kontrol et
            last_event_check = current_time
            
            # Mouse tıklamalarını kontrol et - sadece yeni tıklamalarda
            current_click_state = mouse.getPressed()[0]
            
            # Sadece tıklama başladığında (press down) kontrol et
            if current_click_state and not last_click_state:
                mouse_pos = mouse.getPos()
                for i, button in enumerate(option_buttons):
                    # Butonun sınırlarını hesapla
                    button_center = button.pos
                    button_width = button.width
                    button_height = button.height
                    
                    # Mouse pozisyonunun buton içinde olup olmadığını kontrol et
                    left_edge = button_center[0] - button_width / 2
                    right_edge = button_center[0] + button_width / 2
                    top_edge = button_center[1] + button_height / 2
                    bottom_edge = button_center[1] - button_height / 2
                    
                    if (left_edge <= mouse_pos[0] <= right_edge and
                        bottom_edge <= mouse_pos[1] <= top_edge):
                        # Buton tıklandı - tıklama bırakılana kadar bekle
                        while mouse.getPressed()[0]:
                            core.wait(0.01, hogCPUperiod=0.0)
                        
                        # Tıklama bırakıldı, seçimi kaydet
                        key = option_keys[i]
                        response_time = core.getTime() - start_time
                        save_result(video_id, index, q_data, key.upper(), response_time, participant_id)
                        return
            
            last_click_state = current_click_state
            
            # Tuş girişlerini kontrol et (non-blocking)
            keys = event.getKeys(keyList=option_keys + ['escape'], timeStamped=True)
            
            for key, timestamp in keys:
                if key == 'escape':
                    safe_exit()
                    return
                if key in option_keys:
                    answer_index = ord(key.upper()) - 65
                    if 0 <= answer_index < len(options):
                        # Gerçek response time'ı hesapla (aynı referans zamanından)
                        response_time = timestamp - start_time
                        save_result(video_id, index, q_data, key.upper(), response_time, participant_id)
                        return
        
        # Kısa bir gecikme (CPU kullanımını azaltmak için)
        core.wait(0.001, hogCPUperiod=0.0)

# Likert ölçeği seçenekleri (6 puanlık - Duygusal İfade Ölçeği)
LIKERT_SCALE = [
    "Asla",
    "Nadiren",
    "Bazen",
    "Sıklıkla",
    "Çoğu zaman",
    "Her zaman"
]

# Duygusal İfade Ölçeği soruları (17 soru)
SURVEY_QUESTIONS = [
    "Duygularımı başkalarına ifade etmem.",
    "Güçlü duygular yaşadığımda bile bunları dışarıya yansıtmam.",
    "Başkaları benim çok duygusal olduğumu düşünür.",
    "İnsanlar benim duygularımı \"okuyabilir\".",
    "Duygularımı kendime saklarım.",
    "Başkaları benim ne hissettiğimi kolayca gözlemleyemez.",
    "Duygularımı diğer insanlara gösteririm.",
    "İnsanlar beni duygusuz biri olarak görür.",
    "İnsanların benim ne hissettiğimi anlamasından hoşlanmam.",
    "Hissettiklerimi saklayamam.",
    "Duygularımı ifade eden biri değilim.",
    "Başkaları tarafından çoğu zaman kayıtsız olarak değerlendirilirim.",
    "Başkalarının önünde ağlayabilirim.",
    "Çok duygusal hissetsem bile başkalarının duygularımı görmesine izin vermem.",
    "Kendimi duygularını ifade eden biri olarak görürüm.",
    "Benim hissettiklerim, başkalarının benim ne hissettiğimi düşündüklerinden farklı.",
    "Duygularımı içimde tutarım."
]

def save_survey_answer(participant_id, question_index, question_text, answer_index, answer_text, response_time):
    """Anket cevaplarını CSV dosyasına kaydeder"""
    os.makedirs(os.path.dirname(SURVEY_FILE), exist_ok=True)
    file_exists = os.path.isfile(SURVEY_FILE)
    with open(SURVEY_FILE, 'a', newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["participant_id", "question_index", "question", "answer_index", "answer", "response_time"])
        writer.writerow([
            participant_id,
            question_index,
            question_text,
            answer_index + 1,  # 1-5 arası
            answer_text,
            round(response_time, 2)
        ])

def ask_survey_question(question_text, question_index, participant_id):
    """Likert ölçekli anket sorusu sorar"""
    # İlerleme göstergesi
    progress_text = visual.TextStim(
        win,
        text=f"Soru {question_index} / {len(SURVEY_QUESTIONS)}",
        pos=(0, SCREEN_HEIGHT * 0.45),
        height=SCREEN_HEIGHT * 0.025,
        color='gray'
    )
    
    # Soru metni
    question_stim = visual.TextStim(
        win,
        text=question_text,
        pos=(0, SCREEN_HEIGHT * 0.3),
        height=SCREEN_HEIGHT * 0.035,
        wrapWidth=SCREEN_WIDTH * 0.8,
        color='white'
    )
    
    # Likert ölçeği butonları (6 seçenek)
    scale_buttons = []
    scale_texts = []
    num_options = len(LIKERT_SCALE)  # 6 seçenek
    button_width = SCREEN_WIDTH * 0.13  # Buton genişliği (metin için biraz genişletildi)
    button_height = SCREEN_HEIGHT * 0.12  # Buton yüksekliği (metin için biraz yükseltildi)
    spacing = SCREEN_WIDTH * 0.15  # Butonlar arası mesafe (6 buton için)
    
    # Butonları yatay olarak yerleştir
    start_x = -(num_options - 1) * spacing / 2
    
    for i, option_text in enumerate(LIKERT_SCALE):
        x_pos = start_x + i * spacing
        y_pos = -SCREEN_HEIGHT * 0.1
        
        # Buton oluştur
        button = visual.Rect(
            win,
            width=button_width,
            height=button_height,
            pos=(x_pos, y_pos),
            fillColor='white',
            lineColor='black',
            lineWidth=2
        )
        scale_buttons.append(button)
        
        # Buton üzerindeki metin (numara + tam metin)
        button_text = visual.TextStim(
            win,
            text=f"{i+1}\n{option_text}",
            pos=(x_pos, y_pos),
            height=SCREEN_HEIGHT * 0.022,
            color='black',
            wrapWidth=button_width * 0.9,
            alignText='center'
        )
        scale_texts.append(button_text)
    
    # Talimat metni
    instruction = visual.TextStim(
        win,
        text="Lütfen cevabınızı seçmek için butona tıklayın",
        pos=(0, -SCREEN_HEIGHT * 0.45),
        height=SCREEN_HEIGHT * 0.025,
        color='gray'
    )
    
    mouse = event.Mouse(win=win, visible=True)
    start_time = core.getTime()
    mouse.clickReset()
    last_click_state = False
    
    while True:
        # İlerleme göstergesi
        progress_text.draw()
        
        # Soru metnini çiz
        question_stim.draw()
        
        # Butonları ve metinleri çiz
        for button, text in zip(scale_buttons, scale_texts):
            button.draw()
            text.draw()
        
        # Talimat metni
        instruction.draw()
        
        win.flip()
        
        # Mouse tıklamalarını kontrol et
        current_click_state = mouse.getPressed()[0]
        
        if current_click_state and not last_click_state:
            mouse_pos = mouse.getPos()
            for i, button in enumerate(scale_buttons):
                button_center = button.pos
                btn_width = button.width
                btn_height = button.height
                
                left_edge = button_center[0] - btn_width / 2
                right_edge = button_center[0] + btn_width / 2
                top_edge = button_center[1] + btn_height / 2
                bottom_edge = button_center[1] - btn_height / 2
                
                if (left_edge <= mouse_pos[0] <= right_edge and
                    bottom_edge <= mouse_pos[1] <= top_edge):
                    # Tıklama bırakılana kadar bekle
                    while mouse.getPressed()[0]:
                        core.wait(0.01)
                    
                    # Cevabı kaydet
                    answer_text = LIKERT_SCALE[i]
                    response_time = core.getTime() - start_time
                    save_survey_answer(participant_id, question_index, question_text, i, answer_text, response_time)
                    return
        
        last_click_state = current_click_state
        
        # Klavye ile de seçim yapılabilir (1-6 tuşları)
        keys = event.getKeys(keyList=['1', '2', '3', '4', '5', '6', 'escape'], timeStamped=True)
        for key, timestamp in keys:
            if key == 'escape':
                safe_exit()
                return
            if key in ['1', '2', '3', '4', '5', '6']:
                answer_index = int(key) - 1
                if 0 <= answer_index < len(LIKERT_SCALE):
                    answer_text = LIKERT_SCALE[answer_index]
                    response_time = timestamp - start_time
                    save_survey_answer(participant_id, question_index, question_text, answer_index, answer_text, response_time)
                    return
        
        core.wait(0.01)

def run_survey(participant_id):
    """17 soruluk Duygusal İfade Ölçeği anketini çalıştırır"""
    # Anket başlangıç ekranı - Yönerge
    intro_text = visual.TextStim(
        win,
        text="DUYGUSAL İFADE ÖLÇEĞİ\n\nYÖNERGE: Aşağıdaki ifadeler sizinle ve duygularınızla ilgilidir. Lütfen aşağıdaki ölçekteki ifadelerden sizi en iyi tanımlayan bir sayı seçin.\n\nAsla (1) - Nadiren (2) - Bazen (3) - Sıklıkla (4) - Çoğu zaman (5) - Her zaman (6)\n\nAnket 17 sorudan oluşmaktadır.",
        pos=(0, SCREEN_HEIGHT * 0.15),
        height=SCREEN_HEIGHT * 0.028,
        wrapWidth=SCREEN_WIDTH * 0.85,
        color='white',
        alignText='left'
    )
    
    # "Başla" butonu
    button_width = SCREEN_WIDTH * 0.2
    button_height = SCREEN_HEIGHT * 0.1
    start_button = visual.Rect(
        win,
        width=button_width,
        height=button_height,
        pos=(0, -SCREEN_HEIGHT * 0.25),
        fillColor='green',
        lineColor='white',
        lineWidth=2
    )
    start_text = visual.TextStim(
        win,
        text="Başla",
        pos=(0, -SCREEN_HEIGHT * 0.25),
        height=SCREEN_HEIGHT * 0.04,
        color='white',
        anchorHoriz='center',
        anchorVert='center'
    )
    
    mouse = event.Mouse(win=win, visible=True)
    mouse.clickReset()
    
    while True:
        intro_text.draw()
        start_button.draw()
        start_text.draw()
        win.flip()
        
        # Mouse tıklamalarını kontrol et
        if mouse.getPressed()[0]:
            mouse_pos = mouse.getPos()
            if start_button.contains(mouse_pos):
                # Tıklama bırakılana kadar bekle
                while mouse.getPressed()[0]:
                    core.wait(0.01)
                break  # Anketi başlat
        
        # ESC tuşu kontrolü
        keys = event.getKeys(keyList=['escape'], timeStamped=False)
        if 'escape' in keys:
            safe_exit()
            return
        
        core.wait(0.01, hogCPUperiod=0.0)
    
    # Her soruyu sor
    for idx, question in enumerate(SURVEY_QUESTIONS, start=1):
        ask_survey_question(question, idx, participant_id)
    
    # Anket tamamlandı mesajı
    survey_complete = visual.TextStim(
        win,
        text="Anket tamamlandı. Teşekkür ederiz!",
        pos=(0, 0),
        height=SCREEN_HEIGHT * 0.04,
        color='white'
    )
    survey_complete.draw()
    win.flip()
    core.wait(2.0)  # 2 saniye göster

def save_result(video_id, question_index, question_data, selected, response_time, participant_id):
    """Video sorularının cevaplarını kaydeder - soru numarası ve cevap numarası olarak"""
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    file_exists = os.path.isfile(RESULTS_FILE)
    
    # Harf cevabını numaraya çevir (A=1, B=2, C=3, D=4, E=5, F=6)
    selected_index = ord(selected.upper()) - 64 if selected and selected.upper() in ['A', 'B', 'C', 'D', 'E', 'F'] else ""
    
    with open(RESULTS_FILE, 'a', newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["participant_id", "video_id", "question_index", "selected_index", "response_time"])
        writer.writerow([
            participant_id,
            video_id,
            question_index,
            selected_index,
            round(response_time, 2)
        ])

def run_calibration(tracker, win):
    """
    TheEyeTribe kalibrasyonunu çalıştırır - Video ekran boyutuna göre optimize edilmiş yüksek doğruluklu kalibrasyon
    Returns: Kalibrasyon başarılı ise True
    """
    # Video ekran boyutları (kalibrasyon video ekranına göre yapılacak)
    screen_width = SCREEN_WIDTH  # 1280
    screen_height = SCREEN_HEIGHT  # 720
    
    # 13 nokta kalibrasyon pozisyonları (daha yüksek doğruluk için)
    # Video ekranının tamamını kapsayacak şekilde dağıtılmış
    calibration_points = [
        (screen_width * 0.05, screen_height * 0.05),   # Sol üst köşe
        (screen_width * 0.25, screen_height * 0.05),   # Üst sol
        (screen_width * 0.5, screen_height * 0.05),   # Üst orta
        (screen_width * 0.75, screen_height * 0.05),   # Üst sağ
        (screen_width * 0.95, screen_height * 0.05),   # Sağ üst köşe
        (screen_width * 0.05, screen_height * 0.5),   # Sol orta
        (screen_width * 0.25, screen_height * 0.5),   # Sol-orta
        (screen_width * 0.5, screen_height * 0.5),   # Merkez (en önemli)
        (screen_width * 0.75, screen_height * 0.5),   # Sağ-orta
        (screen_width * 0.95, screen_height * 0.5),   # Sağ orta
        (screen_width * 0.25, screen_height * 0.95),   # Alt sol
        (screen_width * 0.5, screen_height * 0.95),   # Alt orta
        (screen_width * 0.75, screen_height * 0.95),   # Alt sağ
    ]
    
    # Her denemeden önce kalibrasyon durumunu temizle
    try:
        tracker.calibration_prepare()
    except ConnectionError as e:
        print("Kalibrasyon durumu temizlenemedi: {}".format(e))
        return False
    except Exception as e:
        print("Kalibrasyon hazırlığı sırasında beklenmeyen hata: {}".format(e))
        return False
    
    # Kalibrasyonu başlat (13 nokta)
    if not tracker.calibration_start(point_count=13):
        print("Kalibrasyon başlatılamadı!")
        tracker.calibration_abort()
        tracker.calibration_clear()
        return False
    
    # Talimat ekranı
    instruction = visual.TextStim(
        win, 
        text="Yüksek doğruluklu kalibrasyon başlayacak.\nEkranda görünen noktalara dikkatle bakın ve sabit tutun.\n\nHer noktaya en az 2 saniye bakın.\n\nHazır olduğunuzda SPACE tuşuna basın.",
        pos=(0, 0), 
        height=SCREEN_HEIGHT * 0.03, 
        color='white', 
        wrapWidth=SCREEN_WIDTH * 0.8
    )
    
    instruction.draw()
    win.flip()
    event.waitKeys(keyList=['space', 'escape'])
    
    if 'escape' in event.getKeys():
        tracker.calibration_abort()
        return False
    
    # Her nokta için kalibrasyon
    point_circle = visual.Circle(win, radius=25, fillColor='red', lineColor='red', lineWidth=3)
    fixation_circle = visual.Circle(win, radius=8, fillColor='white', lineColor='white', lineWidth=2)
    
    for i, (x, y) in enumerate(calibration_points):
        # Noktayı ekranın merkezine göre ayarla (PsychoPy koordinat sistemi)
        screen_x = x - screen_width / 2
        screen_y = -(y - screen_height / 2)  # Y ekseni ters
        
        # Büyük kırmızı nokta göster (1.5 saniye)
        point_circle.pos = (screen_x, screen_y)
        for _ in range(45):  # ~1.5 saniye (45 frame @ 30fps)
            point_circle.draw()
            win.flip()
        
        # Kalibrasyon noktasını başlat (TheEyeTribe koordinat sistemi: sol üst köşe 0,0)
        if not tracker.calibration_pointstart(x, y):
            print(f"Kalibrasyon noktası başlatılamadı (index={i}). Kalibrasyon iptal ediliyor.")
            tracker.calibration_abort()
            tracker.calibration_clear()
            return False
        
        # Küçük beyaz nokta göster (sabit bakış için - 3 saniye, daha uzun süre daha iyi doğruluk)
        for _ in range(90):  # ~3 saniye (90 frame @ 30fps)
            fixation_circle.pos = (screen_x, screen_y)
            fixation_circle.draw()
            win.flip()
        
        # Kalibrasyon noktasını bitir
        if not tracker.calibration_pointend():
            print(f"Kalibrasyon noktası bitirilemedi (index={i}). Kalibrasyon iptal ediliyor.")
            tracker.calibration_abort()
            tracker.calibration_clear()
            return False
        
        # Noktalar arası bekleme
        core.wait(0.5)
    
    # Kalibrasyon sonucunu kontrol et - get request ile al
    # TheEyeTribe API: category="tracker", request="get", values=["calibresult"]
    avg_error = float('inf')
    success = False
    try:
        calib_result_response = tracker._send_request('tracker', 'get', ['calibresult'])
        if calib_result_response.get('statuscode') == 200:
            values = calib_result_response.get('values', {})
            calibresult = values.get('calibresult', {})
            
            if calibresult:
                # calibresult bir array olabilir veya object olabilir
                if isinstance(calibresult, list) and len(calibresult) > 0:
                    calibresult = calibresult[0]
                
                avg_error = calibresult.get('deg', float('inf'))
                # Yüksek doğruluk için 2.0 dereceden küçük hata yeterli
                success = avg_error < 2.0
    except Exception as e:
        print("Kalibrasyon sonucu alınamadı: {}".format(e))
        success = False
    
    if success:
        message = f"Kalibrasyon başarılı!\nOrtalama hata: {avg_error:.2f} derece\n\nSPACE tuşuna basın."
    else:
        message = f"Kalibrasyon doğruluğu yetersiz.\nOrtalama hata: {avg_error:.2f} derece (hedef: <2°)\n\nTekrar denemek için SPACE, devam etmek için ENTER tuşuna basın."
    
    result_text = visual.TextStim(win, text=message, pos=(0, 0), height=SCREEN_HEIGHT * 0.03, color='white', wrapWidth=SCREEN_WIDTH * 0.8)
    result_text.draw()
    win.flip()
    
    keys = event.waitKeys(keyList=['space', 'return', 'escape'])
    
    if 'escape' in keys:
        return False
    elif 'space' in keys and not success:
        # Tekrar dene
        tracker.calibration_clear()
        return run_calibration(tracker, win)
    else:
        return success

def show_consent_form():
    """Bilgilendirilmiş gönüllü onam formunu gösterir ve kullanıcının onayını alır"""
    consent_text = """BİLGİLENDİRİLMİŞ GÖNÜLLÜ ONAM FORMU

Bu araştırma Zeynep Koç tarafından Doç. Dr. Neşe Alkan gözetmenliğinde yürütülmektedir. Bu çalışmanın amacı nöromodülasyon tedavisi yaptırmış bireylerin yüz ifadelerini tanıma stratejilerini incelemektir. Bu çalışma kapsamında sizden bazı görsel uyarıcılara karşılık olarak tepki vermeniz beklenmektedir. Çalışma yaklaşık olarak 15-20 dakika sürecektir. Katılım bireysel olarak gerçekleştirilecek ve kimliğiniz gizli tutulacaktır. Bu çalışmaya katılım herhangi bir fiziksel ya da psikolojik zarar riski içermemektedir. Ancak rahatsızlık hissederseniz çalışmayı dilediğiniz zaman sonlandırabilirsiniz. Katılım tamamen gönüllülük esasına dayalıdır. Katılmama veya herhangi bir aşamada çalışmadan çekilme hakkına sahipsiniz. Bu durumda hiçbir yaptırım uygulanmayacaktır. Toplanan veriler yalnızca bilimsel amaçla kullanılacak, kimlik bilgilerinizle ilişkilendirilmeyecek ve gizlilik ilkesi çerçevesinde saklanacaktır. Çalışma hakkında herhangi bir sorunuz olması durumunda araştırmacıya koczeynnep@gmail.com adresinden ulaşabilirsiniz."""
    
    # Onam metnini göster
    consent_stim = visual.TextStim(
        win,
        text=consent_text,
        pos=(0, SCREEN_HEIGHT * 0.15),
        height=SCREEN_HEIGHT * 0.025,
        color='white',
        wrapWidth=SCREEN_WIDTH * 0.85,
        alignText='left'
    )
    
    # Butonlar
    button_width = SCREEN_WIDTH * 0.25
    button_height = SCREEN_HEIGHT * 0.08
    button_spacing = SCREEN_WIDTH * 0.15
    
    # "Onaylıyorum" butonu (sağda)
    approve_button = visual.Rect(
        win,
        width=button_width,
        height=button_height,
        pos=(button_spacing, -SCREEN_HEIGHT * 0.35),
        fillColor='green',
        lineColor='white',
        lineWidth=2
    )
    approve_text = visual.TextStim(
        win,
        text="Onaylıyorum",
        pos=(button_spacing, -SCREEN_HEIGHT * 0.35),
        height=SCREEN_HEIGHT * 0.035,
        color='white',
        anchorHoriz='center',
        anchorVert='center'
    )
    
    # "Onaylamıyorum" butonu (solda)
    reject_button = visual.Rect(
        win,
        width=button_width,
        height=button_height,
        pos=(-button_spacing, -SCREEN_HEIGHT * 0.35),
        fillColor='red',
        lineColor='white',
        lineWidth=2
    )
    reject_text = visual.TextStim(
        win,
        text="Onaylamıyorum",
        pos=(-button_spacing, -SCREEN_HEIGHT * 0.35),
        height=SCREEN_HEIGHT * 0.035,
        color='white',
        anchorHoriz='center',
        anchorVert='center'
    )
    
    mouse = event.Mouse(win=win, visible=True)
    mouse.clickReset()
    
    while True:
        # Onam metnini çiz
        consent_stim.draw()
        
        # Butonları çiz
        approve_button.draw()
        approve_text.draw()
        reject_button.draw()
        reject_text.draw()
        
        win.flip()
        
        # Mouse tıklamalarını kontrol et
        if mouse.getPressed()[0]:
            mouse_pos = mouse.getPos()
            
            # "Onaylıyorum" butonu kontrolü
            if approve_button.contains(mouse_pos):
                # Tıklama bırakılana kadar bekle
                while mouse.getPressed()[0]:
                    core.wait(0.01)
                return True  # Onaylandı
            
            # "Onaylamıyorum" butonu kontrolü
            if reject_button.contains(mouse_pos):
                # Tıklama bırakılana kadar bekle
                while mouse.getPressed()[0]:
                    core.wait(0.01)
                return False  # Onaylanmadı
        
        # ESC tuşu kontrolü
        keys = event.getKeys(keyList=['escape'], timeStamped=False)
        if 'escape' in keys:
            safe_exit()
            return False
        
        core.wait(0.01, hogCPUperiod=0.0)

def safe_exit():
    """Güvenli çıkış - tüm kaynakları temizler"""
    global eye_tracker, win
    
    try:
        # Önce kalan gaze verilerini kaydet (veri kaybını önlemek için)
        flush_gaze_buffer()
        
        # Eye tracker temizliği
        if eye_tracker:
            try:
                eye_tracker.stop_tracking()
            except:
                pass
            try:
                eye_tracker.disconnect()
            except:
                pass
            eye_tracker = None
        
        # Window temizliği - güvenli kapatma
        if win is not None:
            try:
                # Window'un backend'inin var olup olmadığını kontrol et
                if hasattr(win, 'backend') and win.backend is not None:
                    # Window'u kapat
                    win.close()
                # Backend yoksa veya zaten kapatılmışsa sessizce geç
            except (AttributeError, RuntimeError, Exception):
                # Herhangi bir hata durumunda sessizce geç
                # Window zaten kapatılmış veya backend yok olabilir
                pass
            finally:
                # Window referansını temizle (garbage collector'ın tekrar kapatmaya çalışmasını önle)
                # Global değişkeni değiştirmek için global anahtar kelimesi zaten yukarıda var
                win = None
    except Exception as e:
        print(f"Çıkış sırasında hata: {e}")
    finally:
        try:
            core.quit()
        except:
            pass

def main():
    global eye_tracker, win
    
    try:
        # Demografik bilgi formunu çalıştır (window açılmadan önce - pop-up dialog)
        participant_id, demographic_data = run_demographic_form()
        
        # Monitor setup
        monitor = setup_monitor()
        
        # Fullscreen window oluştur (video kalitesi korunacak)
        win = visual.Window(
            fullscr=True,  # Fullscreen aktif
            size=None,  # Fullscreen'de otomatik alınır
            units='pix', 
            color=(0, 0, 0), 
            screen=0,
            monitor=monitor,
            waitBlanking=True,
            allowGUI=False,  # Fullscreen'de GUI kapalı
            useFBO=True,
            multiSample=False,
            allowStencil=False,
            winType='pyglet',
            checkTiming=False,
            autoLog=False
        )
        
        # Ekran boyutlarını global değişkenlere kaydet
        global SCREEN_WIDTH, SCREEN_HEIGHT
        SCREEN_WIDTH = win.size[0]
        SCREEN_HEIGHT = win.size[1]
        print(f"Ekran boyutu: {SCREEN_WIDTH}x{SCREEN_HEIGHT}")
        
        win.setMouseVisible(True)
        win.setRecordFrameIntervals(False)
        
        # Onam formunu göster
        consent_approved = show_consent_form()
        
        # Onam durumunu demographic data'ya ekle
        demographic_data["onam_durumu"] = "Onaylandı" if consent_approved else "Onaylanmadı"
        
        # Demografik verileri onam durumu ile birlikte kaydet
        save_demographic_data(participant_id, demographic_data)
        
        if not consent_approved:
            # Onaylanmadıysa uygulamayı kapat
            safe_exit()
            return
        
        # Eye tracker bağlantısı
        eye_tracker = EyeTracker()
        
        # Bağlantı ekranı - animasyonlu (UI donmasını önlemek için)
        # Ekran boyutlarını güvenli şekilde al
        screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
        connecting_text = visual.TextStim(
            win, 
            text="TheEyeTribe sunucusuna bağlanılıyor...", 
            pos=(0, 0), 
            height=screen_h * 0.04, 
            color='white'
        )
        connecting_text.draw()
        win.flip()
        
        # Bağlantıyı dene (timeout korumalı - artık donmayacak)
        # İlk denemede test ile, eğer başarısız olursa test olmadan dene
        print("Bağlantı deneniyor (test modu: True)...")
        connection_success = eye_tracker.connect(test_connection=True)
        
        # Eğer bağlantı başarısız olursa, test olmadan tekrar dene
        if not connection_success:
            print("\nİlk deneme başarısız, test olmadan tekrar deneniyor...")
            connection_success = eye_tracker.connect(test_connection=False)
        
        if not connection_success:
            # Ekran boyutlarını güvenli şekilde al
            screen_w = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
            screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
            error_text = visual.TextStim(
                win,
                text="TheEyeTribe sunucusuna bağlanılamadı!\nLütfen sunucunun çalıştığından emin olun.\n\nESC tuşuna basarak çıkın.",
                pos=(0, 0),
                height=screen_h * 0.03,
                color='red',
                wrapWidth=screen_w * 0.8
            )
            error_text.draw()
            win.flip()
            event.waitKeys(keyList=['escape'])
            safe_exit()
            return
        
        # Kalibrasyon
        calibration_success = run_calibration(eye_tracker, win)
        
        if not calibration_success:
            # Ekran boyutlarını güvenli şekilde al
            screen_w = SCREEN_WIDTH if SCREEN_WIDTH else win.size[0]
            screen_h = SCREEN_HEIGHT if SCREEN_HEIGHT else win.size[1]
            error_text = visual.TextStim(
                win,
                text="Kalibrasyon başarısız oldu.\nDeney devam edemez.\n\nESC tuşuna basarak çıkın.",
                pos=(0, 0),
                height=screen_h * 0.03,
                color='red',
                wrapWidth=screen_w * 0.8
            )
            error_text.draw()
            win.flip()
            event.waitKeys(keyList=['escape'])
            safe_exit()
            return
        
        # Göz takibini başlat
        try:
            eye_tracker.start_tracking()
            
            # Gaze verisi gelip gelmediğini test et
            print("Gaze verisi test ediliyor...")
            test_success = False
            for i in range(10):  # 10 deneme yap
                core.wait(0.1)  # Her denemede 100ms bekle
                gaze_test = eye_tracker.get_latest_gaze()
                if gaze_test:
                    x, y, timestamp = gaze_test
                    # Eğer x ve y 0 değilse veya geçerli bir değerse, veri geliyor demektir
                    if (x != 0 or y != 0) or (abs(x) < 10000 and abs(y) < 10000):  # Geçerli aralıkta
                        print(f"✓ Gaze verisi alındı: x={x:.2f}, y={y:.2f}")
                        test_success = True
                        break
                # Alternatif: get_gaze_data() ile manuel istek yap
                if not test_success:
                    try:
                        gaze_test = eye_tracker.get_gaze_data()
                        if gaze_test:
                            x, y, timestamp = gaze_test
                            if (x != 0 or y != 0) or (abs(x) < 10000 and abs(y) < 10000):
                                print(f"✓ Gaze verisi alındı (manuel): x={x:.2f}, y={y:.2f}")
                                test_success = True
                                break
                    except:
                        pass
            
            if not test_success:
                print("⚠️  UYARI: Gaze verisi alınamadı! Eye tracker çalışıyor olabilir ama veri gelmiyor.")
                print("   Kalibrasyonu kontrol edin veya eye tracker cihazını kontrol edin.")
                # Yine de devam et, belki video oynatılırken veri gelir
        except Exception as e:
            print(f"Göz takibi başlatılamadı: {e}")
        
        # Deney başlat
        # Videoları 4 kişiye göre gruplandır (her kişiden 6 video)
        # Kişi 1: kisi1video1-kisi1video6, Kişi 2: kisi2video1-kisi2video6, Kişi 3: kisi3video1-kisi3video6, Kişi 4: kisi4video1-kisi4video6
        NUM_PERSONS = 4
        VIDEOS_PER_PERSON = 6
        
        # Videoları kişilere göre grupla
        person_videos = {}
        for person in range(1, NUM_PERSONS + 1):
            person_videos[person] = []
            for video_num in range(1, VIDEOS_PER_PERSON + 1):
                video_file = f"kisi{person}video{video_num}.mp4"
                video_path = os.path.join(VIDEO_DIR, video_file)
                if os.path.exists(video_path):
                    person_videos[person].append(video_file)
        
        # Her turda farklı kişiden video göster (sıra sabit)
        # Tur 1: Kişi1-video1, Kişi2-video1, Kişi3-video1, Kişi4-video1
        # Tur 2: Kişi1-video2, Kişi2-video2, Kişi3-video2, Kişi4-video2
        # ... şeklinde devam eder
        video_sequence = []
        for video_index in range(VIDEOS_PER_PERSON):  # 0-5 arası (6 video)
            for person in range(1, NUM_PERSONS + 1):  # 1-4 arası (4 kişi)
                if video_index < len(person_videos[person]):
                    video_sequence.append(person_videos[person][video_index])
        
        # Video sırasını göster
        for idx, video_file in enumerate(video_sequence, start=1):
            video_id = os.path.splitext(video_file)[0]
            video_path = os.path.join(VIDEO_DIR, video_file)

            play_video_with_controls(video_path, idx, participant_id, video_id)

            questions = load_questions(video_id)
            for idx_q, q in enumerate(questions):
                ask_question(q, video_id, idx_q, participant_id)

        # Anketi çalıştır
        run_survey(participant_id)

        # Deney bitmeden önce kalan gaze verilerini kaydet
        flush_gaze_buffer()
        print("Deney tamamlandı - kalan gaze verileri kaydedildi")

        # Deney tamamlandı
        completion_text = visual.TextStim(
            win, 
            text="Deney tamamlandı. Teşekkür ederiz!", 
            height=SCREEN_HEIGHT * 0.04,
            color='white'
        )
        completion_text.draw()
        win.flip()
        core.wait(3.0)  # 3 saniye göster, sonra otomatik çıkış
        
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu (Ctrl+C)")
    except Exception as e:
        print(f"Deney sırasında hata oluştu: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Güvenli çıkış
        safe_exit()

if __name__ == "__main__":
    main()