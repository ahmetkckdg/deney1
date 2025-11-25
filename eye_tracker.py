"""
TheEyeTribe Eye Tracker Implementation
TheEyeTribe, TCP socket üzerinden JSON protokolü kullanarak çalışır.
Kullanım için TheEyeTribe sunucusunun çalışıyor olması gerekir.
"""

import socket
import json
import time as time_module
import threading
from typing import Optional, Tuple
from queue import Queue

class EyeTracker:
    """
    TheEyeTribe göz takip cihazı için Python sınıfı.
    
    Kullanım:
        tracker = EyeTracker()
        tracker.connect()
        tracker.start_tracking()
        gaze_data = tracker.get_gaze_data()  # (x, y, timestamp)
        tracker.stop_tracking()
        tracker.disconnect()
    """
    
    def __init__(self, host='localhost', port=6555):
        """
        Args:
            host: TheEyeTribe sunucusunun IP adresi (genellikle localhost)
            port: TheEyeTribe sunucusunun port numarası (varsayılan: 6555)
        """
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.tracking = False
        self.latest_gaze = None
        self.lock = threading.Lock()
        self.request_id = 0
        # C# örneğine benzer şekilde: ayrı thread için
        self.listener_thread = None
        self.listener_running = False
        self.response_queue = Queue()  # Gelen mesajlar için queue (thread-safe)
        self.pending_requests = {}  # Bekleyen request'ler: {(category, request): (event, response_dict)}
        self.pending_lock = threading.Lock()  # pending_requests için lock
        self.buffer = b''  # Listener thread için buffer
        
    def _get_request_id(self):
        """Her istek için benzersiz ID oluşturur"""
        self.request_id += 1
        return self.request_id
    
    def _log(self, message: str):
        """Log mesajı yazdırır (zaman damgası ile)"""
        try:
            timestamp = time_module.strftime("%H:%M:%S.%f")[:-3]  # milisaniye hassasiyeti
        except Exception:
            timestamp = time_module.strftime("%H:%M:%S")
        
        # Güvenli yazdırma - message içindeki özel karakterleri escape et
        try:
            # Önce % karakterlerini escape et
            safe_message = str(message).replace('%', '%%')
            print("[%s] [EyeTracker] %s" % (timestamp, safe_message))
        except Exception as e:
            # Eğer hata olursa, en basit şekilde yazdır
            try:
                print("[{}] [EyeTracker] {}".format(timestamp, str(message)))
            except Exception:
                # Son çare: direkt print
                print("[EyeTracker]", message)
    
    def _listener_loop(self):
        """
        C# örneğindeki ListenerLoop gibi: ayrı thread'de sürekli socket'ten okuyup mesajları parse eder
        Gelen mesajları queue'ya koyar ve bekleyen request'lere yanıt verir
        """
        self._log("Listener loop başlatıldı")
        buffer = b''
        recv_count = 0
        message_count = 0
        decoder = json.JSONDecoder()

        def handle_message(message_bytes: bytes):
            nonlocal message_count
            if not message_bytes:
                return

            trimmed = message_bytes.strip()
            if not trimmed:
                return

            message_count += 1
            if message_count <= 5 or message_count % 50 == 0:
                self._log("Listener: Mesaj işleniyor ({} mesaj, {} byte)".format(
                    message_count, len(message_bytes)))

            try:
                message_str = message_bytes.decode('utf-8')
                message_json = json.loads(message_str)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                preview = message_bytes[:120]
                self._log("Listener: Mesaj parse edilemedi: {} - Mesaj: {}".format(e, preview))
                return

            msg_category = message_json.get('category', '')
            msg_request = message_json.get('request', None)

            if message_count <= 10:
                self._log("Listener: Mesaj parse edildi: category={}, request={}".format(
                    msg_category, msg_request if msg_request is not None else "(yok)"))

            # Mesajı queue'ya koy
            self.response_queue.put(message_json)

            # Frame data ise latest_gaze'i güncelle
            if msg_category == 'tracker' and msg_request is None:
                values = message_json.get('values', {})
                frame = values.get('frame', {})
                if frame:
                    avg = frame.get('avg', {})
                    if avg:  # avg boş olabilir, kontrol et
                        x = avg.get('x', 0)
                        y = avg.get('y', 0)
                        time_ms = frame.get('time', int(time_module.time() * 1000))
                        timestamp = time_ms / 1000.0
                        
                        # Geçersiz değerleri filtrele
                        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
                            x, y = 0, 0
                        if abs(x) > 100000 or abs(y) > 100000 or (x != x) or (y != y):  # NaN kontrolü
                            x, y = 0, 0

                        with self.lock:
                            self.latest_gaze = (x, y, timestamp)
                        
                        # İlk birkaç frame'i logla (debug için)
                        if message_count <= 5:
                            self._log("Listener: Frame verisi alındı: x={:.2f}, y={:.2f}, time={:.3f}".format(
                                x, y, timestamp))

            # Bekleyen request'lere yanıt ver
            self._check_pending_requests(message_json)
        
        while self.listener_running and self.connected and self.socket:
            try:
                # Socket'ten oku (C# örneğindeki reader.ReadLine() gibi)
                # Python'da readline() yok, bu yüzden recv() kullanıyoruz
                self.socket.settimeout(1.0)  # 1 saniye timeout (non-blocking için)
                chunk = self.socket.recv(8192)
                
                if not chunk:
                    self._log("Listener: Boş chunk alındı (bağlantı kesildi)")
                    break
                
                recv_count += 1
                if recv_count <= 5 or recv_count % 50 == 0:
                    self._log("Listener: Veri alındı ({} byte, {} çağrı)".format(len(chunk), recv_count))
                
                buffer += chunk
                
                # Buffer çok büyürse uyarı ver
                if len(buffer) > 100000:
                    self._log("Listener: UYARI: Buffer çok büyük ({} byte)".format(len(buffer)))
                    # Son 10KB'ı tut
                    trim_delimiter = None
                    if b'\r\n' in buffer:
                        trim_delimiter = b'\r\n'
                    elif b'\n' in buffer:
                        trim_delimiter = b'\n'
                    if trim_delimiter:
                        last_newline = buffer.rfind(trim_delimiter)
                        if last_newline > 0:
                            buffer = buffer[last_newline + len(trim_delimiter):]
                
                processed_message = False

                # Buffer'daki tüm tam mesajları işle (satır sonu ile biten)
                while True:
                    delimiter = None
                    if b'\r\n' in buffer:
                        delimiter = b'\r\n'
                    elif b'\n' in buffer:
                        delimiter = b'\n'
                    else:
                        break

                    message_end = buffer.find(delimiter)
                    message_bytes = buffer[:message_end]
                    buffer = buffer[message_end + len(delimiter):]
                    handle_message(message_bytes)
                    processed_message = True

                # Eğer satır sonu bulunamadıysa, JSONDecoder ile tam nesne arayın
                if not processed_message and buffer:
                    try:
                        buffer_str = buffer.decode('utf-8')
                    except UnicodeDecodeError as e:
                        self._log("Listener: Buffer decode edilemedi ({}). Buffer temizleniyor.".format(e))
                        buffer = b''
                        continue

                    idx = 0
                    str_len = len(buffer_str)
                    while idx < str_len:
                        try:
                            _, parsed_len = decoder.raw_decode(buffer_str[idx:])
                        except json.JSONDecodeError:
                            break

                        message_text = buffer_str[idx: idx + parsed_len]
                        handle_message(message_text.encode('utf-8'))
                        idx += parsed_len

                        while idx < str_len and buffer_str[idx] in '\r\n \t':
                            idx += 1

                        processed_message = True

                    if idx > 0:
                        buffer = buffer_str[idx:].encode('utf-8')
                
            except socket.timeout:
                # Timeout normal (non-blocking için)
                if recv_count == 0:
                    self._log("Listener: İlk timeout (henüz veri yok)")
                continue
            except (socket.error, OSError, ConnectionResetError) as e:
                self._log("Listener: Socket hatası: {}".format(e))
                break
            except Exception as e:
                self._log("Listener: Beklenmeyen hata: {}: {}".format(type(e).__name__, e))
                import traceback
                self._log("Listener: Traceback: {}".format(traceback.format_exc()))
                break
        
        self._log("Listener loop sonlandı (toplam {} mesaj, {} recv çağrısı)".format(message_count, recv_count))
    
    def _check_pending_requests(self, message_json: dict):
        """Gelen mesajın bekleyen bir request'e yanıt olup olmadığını kontrol eder"""
        msg_category = message_json.get('category', '')
        msg_request = message_json.get('request', None)
        
        with self.pending_lock:
            pending_count = len(self.pending_requests)
            if pending_count > 0:
                self._log("Listener: Bekleyen request kontrol ediliyor: {} request, gelen: category={}, request={}".format(
                    pending_count, msg_category, msg_request if msg_request is not None else "(yok)"))
            
            # Tüm bekleyen request'leri kontrol et
            keys_to_remove = []
            for (cat, req), (event, response_dict) in self.pending_requests.items():
                if cat == msg_category:
                    if req is None:
                        # Heartbeat gibi request olmayan istekler
                        if msg_request is None:
                            # Yanıt bulundu!
                            self._log("Listener: Yanıt eşleşti! category={}, request=(yok)".format(cat))
                            response_dict['response'] = message_json
                            event.set()
                            keys_to_remove.append((cat, req))
                    elif req == msg_request:
                        # Request eşleşiyor - yanıt bulundu!
                        self._log("Listener: Yanıt eşleşti! category={}, request={}".format(cat, req))
                        response_dict['response'] = message_json
                        event.set()
                        keys_to_remove.append((cat, req))
                    else:
                        # Category eşleşiyor ama request eşleşmiyor
                        if pending_count > 0:
                            self._log("Listener: Category eşleşiyor ama request farklı: beklenen={}, gelen={}".format(
                                req, msg_request))
            
            # Eşleşen request'leri temizle
            for key in keys_to_remove:
                del self.pending_requests[key]
                self._log("Listener: Pending request temizlendi: {}".format(key))
    
    def _send_request(self, category: str, request_type: str = None, values=None, timeout: float = 5.0) -> dict:
        """
        TheEyeTribe sunucusuna JSON isteği gönderir ve yanıtı alır.
        
        TheEyeTribe API formatı (JSON-RPC değil, özel format):
        {
            "category": "tracker",
            "request": "get",
            "values": [...] veya {...}
        }
        
        Args:
            category: İstek kategorisi ('tracker', 'calibration', 'heartbeat')
            request_type: İstek tipi ('get', 'set', 'start', 'pointstart', 'pointend', vb.)
            values: İstek değerleri (list, dict veya None)
            timeout: İstek için timeout süresi (saniye)
            
        Returns:
            Sunucudan gelen JSON yanıtı
        """
        values_str = repr(values) if values else "None"
        self._log("İstek hazırlanıyor: category={}, request={}, values={}, timeout={}s".format(
            category, request_type, values_str, timeout))
        
        if not self.connected or not self.socket:
            self._log("HATA: Bağlantı kontrolü başarısız - connected={}, socket={}".format(
                self.connected, self.socket is not None))
            raise ConnectionError("TheEyeTribe sunucusuna bağlı değil!")
        
        self._log("Bağlantı durumu: OK")
        
        # Socket timeout'unu ayarlama - listener thread kullanıyoruz, timeout listener thread'de ayarlı
        # _send_request'te socket timeout'u değiştirmemeliyiz çünkü listener thread'i etkiler
        # Listener thread zaten 1.0s timeout kullanıyor
        
        # TheEyeTribe API formatı (JSON-RPC değil!)
        request = {
            "category": category
        }
        
        # request_type'ı ekle (None ise ekleme - API guide'a göre heartbeat'te request field'ı yok)
        # API guide: {"category": "heartbeat"} - request field'ı yok
        if request_type is not None:
            request["request"] = request_type
        
        # values varsa ekle (list veya dict olabilir)
        if values is not None:
            request["values"] = values
        
        # İstek detaylarını logla
        request_type_str = request_type if request_type else "(yok)"
        self._log("JSON isteği oluşturuldu: category={}, request={}".format(category, request_type_str))
        try:
            request_preview = json.dumps(request, indent=2, ensure_ascii=False)
            # İlk 300 karakteri göster
            if len(request_preview) > 300:
                request_preview = request_preview[:300] + "..."
            # \n karakterlerini | ile değiştir (log için güvenli)
            request_preview_safe = request_preview.replace('\n', ' | ')
            self._log("İstek içeriği: {}".format(request_preview_safe))
        except Exception as e:
            self._log("UYARI: İstek preview oluşturulamadı: {}".format(e))
        
        try:
            # JSON isteğini gönder - TheEyeTribe API formatı:
            # - Compact JSON (indent yok)
            # - ensure_ascii=False (Unicode karakterleri koru)
            # - \r\n ile bitir (TheEyeTribe protokolü gereksinimi)
            message = json.dumps(request, ensure_ascii=False, separators=(',', ':')) + '\r\n'
            message_bytes = message.encode('utf-8')
            
            # Log için güvenli gösterim
            message_display = message.strip().replace('\n', '\\n').replace('\r', '\\r')
            if len(message_display) > 200:
                message_display = message_display[:200] + "..."
            self._log("İstek gönderiliyor ({} byte): {}".format(len(message_bytes), message_display))
            
            # C# örneğine benzer: listener thread'den yanıt bekle
            request_type_str = request_type if request_type is not None else "(yok)"
            self._log("Yanıt bekleniyor... (category={}, request={})".format(category, request_type_str))
            
            # Event ve response dict oluştur
            response_event = threading.Event()
            response_dict = {'response': None}
            
            # Pending request'e ekle - SENDALL'DAN ÖNCE! (race condition önleme)
            # Eğer sunucu çok hızlı yanıt verirse, listener thread yanıtı görmeden önce
            # request'in pending listesine eklenmesi gerekir
            request_key = (category, request_type)
            with self.pending_lock:
                self.pending_requests[request_key] = (response_event, response_dict)
            self._log("Pending request eklendi: {}".format(request_key))
            
            try:
                # İsteği gönder - sendall tüm byte'ları gönderir
                self.socket.sendall(message_bytes)
                self._log("İstek başarıyla gönderildi ({} byte)".format(len(message_bytes)))
            except Exception as send_error:
                # Gönderme başarısız oldu - pending request'i temizle
                with self.pending_lock:
                    if request_key in self.pending_requests:
                        del self.pending_requests[request_key]
                self._log("HATA: İstek gönderilemedi: {}".format(send_error))
                raise ConnectionError("İstek gönderilemedi: {}".format(send_error))
            
            # Yanıtı bekle (listener thread'den gelecek)
            start_time = time_module.time()
            wait_count = 0
            while True:
                # Timeout kontrolü
                elapsed = time_module.time() - start_time
                if elapsed > timeout:
                    # Timeout oldu - pending request'i temizle
                    with self.pending_lock:
                        pending_info = "{} pending request".format(len(self.pending_requests))
                        if request_key in self.pending_requests:
                            del self.pending_requests[request_key]
                    self._log("TIMEOUT: {:.2f}s geçti, limit: {}s, {} bekleme döngüsü, {}".format(
                        elapsed, timeout, wait_count, pending_info))
                    raise ConnectionError("Sunucu yanıt vermiyor (timeout: {}s)".format(timeout))
                
                wait_count += 1
                if wait_count % 10 == 0:
                    with self.pending_lock:
                        pending_count = len(self.pending_requests)
                    self._log("Yanıt bekleniyor... ({} döngü, {:.2f}s geçti, {} pending request)".format(
                        wait_count, elapsed, pending_count))
                
                # Event'in set edilip edilmediğini kontrol et (non-blocking)
                if response_event.wait(timeout=0.1):  # 100ms timeout
                    # Yanıt geldi!
                    response = response_dict['response']
                    if response:
                        # Pending request'i temizle
                        with self.pending_lock:
                            if request_key in self.pending_requests:
                                del self.pending_requests[request_key]
                        
                        statuscode = response.get('statuscode', 'yok')
                        has_values = 'var' if 'values' in response else 'yok'
                        self._log("Yanıt alındı: category={}, request={}, statuscode={}, values={} ({} döngü, {:.2f}s)".format(
                            category, request_type_str, statuscode, has_values, wait_count, elapsed))
                        return response
                    else:
                        # Event set edildi ama response yok - hata
                        self._log("UYARI: Event set edildi ama response yok")
                        continue
                
                # Event henüz set edilmedi, devam et
            
        except socket.timeout as e:
            self._log("HATA: İstek timeout oldu: {}".format(e))
            raise ConnectionError("İstek timeout oldu ({}s)".format(timeout))
        except json.JSONDecodeError as e:
            self._log("HATA: JSON parse hatası: {}".format(e))
            if 'response_str' in locals():
                response_display = response_str.replace('\n', '\\n').replace('\r', '\\r')
                if len(response_display) > 200:
                    response_display = response_display[:200] + "..."
                self._log("Hatalı yanıt: {}".format(response_display))
            raise ConnectionError("Sunucudan geçersiz JSON yanıtı: {}".format(e))
        except Exception as e:
            # Hata durumunda pending request'i temizle
            with self.pending_lock:
                if 'request_key' in locals() and request_key in self.pending_requests:
                    del self.pending_requests[request_key]
            self._log("HATA: Beklenmeyen hata: {}: {}".format(type(e).__name__, e))
            raise ConnectionError("İstek gönderilirken hata: {}".format(e))
    
    def connect(self, test_connection: bool = True) -> bool:
        """
        TheEyeTribe sunucusuna bağlanır.
        
        Args:
            test_connection: Bağlantıyı test etmek için istek gönder (varsayılan: True)
        
        Returns:
            Bağlantı başarılı ise True
        """
        self._log("=" * 60)
        self._log("BAĞLANTI BAŞLATILIYOR")
        self._log("Hedef: {}:{}".format(self.host, self.port))
        self._log("Test modu: {}".format(test_connection))
        self._log("=" * 60)
        
        # Önceki bağlantıyı temizle
        if self.socket:
            self._log("Önceki socket bağlantısı temizleniyor...")
            try:
                self.socket.close()
                self._log("Önceki socket kapatıldı")
            except Exception as e:
                self._log("UYARI: Önceki socket kapatılamadı: {}".format(e))
            self.socket = None
        self.connected = False
        
        try:
            # Socket oluştur
            self._log("Adım 1: Socket oluşturuluyor...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._log("Socket oluşturuldu: OK")
            
            # Windows için socket ayarları
            self._log("Adım 2: Socket ayarları yapılıyor...")
            try:
                # SO_REUSEADDR - Windows'ta bazen gerekli
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._log("SO_REUSEADDR ayarlandı: OK")
            except Exception as e:
                self._log("UYARI: SO_REUSEADDR ayarlanamadı: {}".format(e))
            
            try:
                # TCP_NODELAY - Nagle algoritmasını devre dışı bırak (daha hızlı yanıt)
                self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._log("TCP_NODELAY ayarlandı: OK")
            except Exception as e:
                self._log("UYARI: TCP_NODELAY ayarlanamadı: {}".format(e))
            
            # Timeout ayarla (bağlantı ve tüm işlemler için)
            connection_timeout = 5.0
            self._log("Adım 3: Socket timeout ayarlanıyor: {}s".format(connection_timeout))
            self.socket.settimeout(connection_timeout)
            self._log("Timeout ayarlandı: OK")
            
            # Bağlantıyı dene
            self._log("Adım 4: Bağlantı deneniyor ({}:{})...".format(self.host, self.port))
            connect_start = time_module.time()
            
            try:
                # Normal connect kullan (timeout zaten ayarlı)
                self.socket.connect((self.host, self.port))
                connect_elapsed = time_module.time() - connect_start
                self._log("Bağlantı başarılı! (Süre: {:.3f}s)".format(connect_elapsed))
                
                # Socket'in gerçekten bağlı olduğunu kontrol et
                try:
                    # getpeername() bağlantı varsa çalışır
                    peer = self.socket.getpeername()
                    self._log("Socket bağlantısı doğrulandı: {}:{}".format(peer[0], peer[1]))
                except Exception as e:
                    self._log("UYARI: getpeername() başarısız: {}".format(e))
                    # Yine de devam et, bağlantı olabilir
                
            except socket.timeout:
                connect_elapsed = time_module.time() - connect_start
                self._log("HATA: Bağlantı timeout ({:.3f}s geçti, limit: {}s)".format(
                    connect_elapsed, connection_timeout))
                self._log("Sunucu yanıt vermiyor. Kontrol edin:")
                self._log("  1. TheEyeTribe sunucusu çalışıyor mu?")
                self._log("  2. Port {} açık mı?".format(self.port))
                self._log("  3. Firewall engelliyor mu?")
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = None
                return False
            except ConnectionRefusedError as e:
                connect_elapsed = time_module.time() - connect_start
                self._log("HATA: Bağlantı reddedildi ({:.3f}s): {}".format(connect_elapsed, e))
                self._log("Sunucu bağlantıyı reddetti. Muhtemelen:")
                self._log("  - Sunucu çalışmıyor")
                self._log("  - Port {} yanlış".format(self.port))
                self._log("  - Sunucu 'local only' modunda ve başka bir IP'den bağlanıyorsunuz")
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = None
                return False
            except (socket.error, OSError, ConnectionResetError) as e:
                connect_elapsed = time_module.time() - connect_start
                self._log("HATA: Bağlantı hatası ({:.3f}s): {}: {}".format(
                    connect_elapsed, type(e).__name__, e))
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                self.socket = None
                return False
            
            # Bağlantı başarılı
            self.connected = True
            self._log("Adım 5: Bağlantı durumu güncellendi: connected=True")
            
            # C# örneğine benzer: ayrı thread'de sürekli okuma başlat
            self._log("Listener thread başlatılıyor...")
            self.listener_running = True
            self.buffer = b''  # Buffer'ı temizle
            # Socket timeout'unu listener thread için ayarla (1.0s)
            try:
                self.socket.settimeout(1.0)
                self._log("Socket timeout listener thread için ayarlandı: 1.0s")
            except Exception as e:
                self._log("UYARI: Socket timeout ayarlanamadı: {}".format(e))
            
            self.listener_thread = threading.Thread(target=self._listener_loop, daemon=True)
            self.listener_thread.start()
            self._log("Listener thread başlatıldı")
            
            # Thread'in başlamasını bekle (kısa bir süre)
            time_module.sleep(0.1)
            if self.listener_thread.is_alive():
                self._log("Listener thread çalışıyor")
            else:
                self._log("UYARI: Listener thread başlamadı!")
            
            # Bağlantıyı test et (opsiyonel - eğer test_connection=False ise atla)
            if test_connection:
                self._log("Adım 6: Bağlantı testi başlatılıyor...")
                test_success = False
                
                # Önce basit bir test - sadece socket'in çalışıp çalışmadığını kontrol et
                try:
                    # Socket'in durumunu kontrol et
                    self._log("Socket durumu kontrol ediliyor...")
                    peer = self.socket.getpeername()
                    self._log("Socket bağlı: {}:{}".format(peer[0], peer[1]))
                    
                    # Şimdi basit bir istek gönder - TheEyeTribe API formatına göre
                    self._log("Basit test isteği gönderiliyor...")
                    # TheEyeTribe API formatı: category="tracker", request="get", values=["version"]
                    response = self._send_request('tracker', 'get', ['version'], timeout=5.0)
                    
                    # TheEyeTribe yanıt formatı kontrolü
                    if 'statuscode' in response and response.get('statuscode') == 200:
                        values = response.get('values', {})
                        if 'version' in values:
                            version = values.get('version', 'bilinmiyor')
                            self._log("BAĞLANTI BAŞARILI! Versiyon: {}".format(version))
                            test_success = True
                        else:
                            self._log("UYARI: Yanıtta 'version' yok, ancak statuscode=200")
                            self._log("Yanıt values: {}".format(values))
                            test_success = False
                    elif 'statuscode' in response:
                        statuscode = response.get('statuscode')
                        statusmessage = response.get('values', {}).get('statusmessage', 'bilinmiyor')
                        self._log("UYARI: Sunucu hata döndürdü: statuscode={}, message={}".format(
                            statuscode, statusmessage))
                        self._log("Ancak bağlantı kuruldu, devam ediliyor...")
                        test_success = False
                    else:
                        # Geçersiz yanıt ama bağlantı var - devam et
                        self._log("UYARI: Beklenmeyen yanıt formatı: {}".format(response))
                        self._log("Ancak bağlantı kuruldu, devam ediliyor...")
                        test_success = False
                        
                except ConnectionError as e:
                    # Test başarısız ama socket bağlı - bağlantıyı kabul et
                    self._log("UYARI: Bağlantı testi başarısız (ConnectionError): {}".format(e))
                    self._log("Ancak socket bağlantısı kuruldu, devam ediliyor...")
                    test_success = False
                except socket.timeout as e:
                    # Timeout - ama socket bağlı
                    self._log("UYARI: Bağlantı testi timeout oldu: {}".format(e))
                    self._log("Sunucu yanıt vermiyor ama socket bağlı, devam ediliyor...")
                    test_success = False
                except Exception as e:
                    # Beklenmeyen hata - bağlantıyı kabul et ama uyar
                    self._log("UYARI: Test sırasında beklenmeyen hata - {}: {}".format(type(e).__name__, e))
                    import traceback
                    self._log("Detay: {}".format(str(e)))
                    self._log("Ancak socket bağlantısı kuruldu, devam ediliyor...")
                    test_success = False
                
                # Test sonucu ne olursa olsun, socket bağlantısı kurulduysa devam et
                if test_success:
                    self._log("=" * 60)
                    self._log("BAĞLANTI VE TEST BAŞARILI!")
                else:
                    self._log("=" * 60)
                    self._log("UYARI: Test başarısız ama socket bağlantısı aktif")
                    self._log("Bağlantı kabul ediliyor, devam ediliyor...")
                self._log("=" * 60)
                return True
            else:
                # Test atlandı - sadece socket bağlantısı yeterli
                self._log("Adım 6: Test atlandı - socket bağlantısı yeterli")
                self._log("BAĞLANTI KURULDU (test atlandı)")
                self._log("=" * 60)
                return True
                
        except socket.timeout as e:
            self._log("HATA: Socket timeout - {}".format(e))
            self._log("Sunucuya bağlanırken timeout oldu. Sunucunun çalıştığından emin olun.")
            self._log("=" * 60)
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                    self._log("Socket kapatıldı")
                except Exception as close_err:
                    self._log("UYARI: Socket kapatılırken hata: {}".format(close_err))
                self.socket = None
            return False
        except (socket.error, OSError, ConnectionRefusedError, ConnectionResetError) as e:
            self._log("HATA: Socket/Network hatası - {}: {}".format(type(e).__name__, e))
            self._log("Sunucuya bağlanılamadı. Kontrol edin:")
            self._log("  1. TheEyeTribe sunucusu çalışıyor mu?")
            self._log("  2. Port {} açık mı?".format(self.port))
            self._log("  3. Firewall engelliyor mu?")
            self._log("=" * 60)
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                    self._log("Socket kapatıldı")
                except Exception as close_err:
                    self._log("UYARI: Socket kapatılırken hata: {}".format(close_err))
                self.socket = None
            return False
        except Exception as e:
            self._log("HATA: Beklenmeyen hata - {}: {}".format(type(e).__name__, e))
            import traceback
            self._log("Detaylı hata bilgisi:")
            tb_str = traceback.format_exc()
            # Traceback'i satır satır logla
            for line in tb_str.split('\n'):
                if line.strip():
                    self._log("  {}".format(line))
            self._log("Lütfen TheEyeTribe sunucusunun çalıştığından emin olun.")
            self._log("=" * 60)
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                    self._log("Socket kapatıldı")
                except Exception as close_err:
                    self._log("UYARI: Socket kapatılırken hata: {}".format(close_err))
                self.socket = None
            return False
    
    def disconnect(self):
        """TheEyeTribe sunucusuyla bağlantıyı keser"""
        self._log("Bağlantı kesiliyor...")
        if self.tracking:
            self._log("Takip durduruluyor...")
            self.stop_tracking()
        
        # Listener thread'i durdur
        if self.listener_running:
            self._log("Listener thread durduruluyor...")
            self.listener_running = False
            if self.listener_thread and self.listener_thread.is_alive():
                # Thread'in bitmesini bekle (max 2 saniye)
                self.listener_thread.join(timeout=2.0)
                if self.listener_thread.is_alive():
                    self._log("UYARI: Listener thread zamanında bitmedi")
                else:
                    self._log("Listener thread durduruldu")
        
        if self.socket:
            try:
                self.socket.close()
                self._log("Socket kapatıldı")
            except Exception as e:
                self._log("UYARI: Socket kapatılırken hata: {}".format(e))
        self.connected = False
        self.socket = None
        self.buffer = b''  # Buffer'ı temizle
        self._log("Bağlantı kesildi")
    
    def start_tracking(self):
        """Göz takibini başlatır"""
        self._log("Göz takibi başlatılıyor...")
        if not self.connected:
            self._log("HATA: Bağlantı yok!")
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        try:
            # Push modunu etkinleştir (sürekli veri almak için)
            # TheEyeTribe API formatı: category="tracker", request="set", values={"push": true, "version": 1}
            self._log("Push modu etkinleştiriliyor...")
            response = self._send_request('tracker', 'set', {
                'push': True,
                'version': 1
            })
            
            if 'statuscode' in response and response.get('statuscode') == 200:
                self.tracking = True
                self._log("Göz takibi başlatıldı: OK")
                # Push mode aktif, listener thread frame verilerini almaya başlayacak
                # Kısa bir bekleme ekle ki listener thread frame almaya başlasın
                time_module.sleep(0.2)  # 200ms bekle
                self._log("Push mode aktif, frame verileri bekleniyor...")
            else:
                statuscode = response.get('statuscode', 'bilinmiyor')
                statusmessage = response.get('values', {}).get('statusmessage', 'bilinmiyor')
                self._log("HATA: Takip başlatılamadı - statuscode: {}, message: {}".format(
                    statuscode, statusmessage))
                raise Exception("Takip başlatılamadı")
                
        except Exception as e:
            self._log("HATA: Takip başlatma hatası: {}: {}".format(type(e).__name__, e))
            raise
    
    def stop_tracking(self):
        """Göz takibini durdurur"""
        if not self.tracking:
            self._log("Takip zaten durdurulmuş")
            return
        
        self._log("Göz takibi durduruluyor...")
        try:
            # TheEyeTribe API formatı: category="tracker", request="set", values={"push": false}
            response = self._send_request('tracker', 'set', {
                'push': False
            })
            self.tracking = False
            self._log("Göz takibi durduruldu: OK")
        except Exception as e:
            self._log("HATA: Takip durdurma hatası: {}: {}".format(type(e).__name__, e))
    
    def get_gaze_data(self) -> Optional[Tuple[float, float, float]]:
        """
        En son göz takip verisini alır.
        
        Returns:
            (x, y, timestamp) tuple veya None
            x, y: Ekran koordinatları (piksel)
            timestamp: Zaman damgası (saniye)
        """
        if not self.connected or not self.tracking:
            return None
        
        try:
            # Frame verisini al - TheEyeTribe API formatı: category="tracker", request="get", values=["frame"]
            response = self._send_request('tracker', 'get', ['frame'], timeout=1.0)
            
            # TheEyeTribe yanıt formatı: {"category": "tracker", "request": "get", "statuscode": 200, "values": {"frame": {...}}}
            if 'statuscode' in response and response.get('statuscode') == 200:
                values = response.get('values', {})
                frame = values.get('frame', {})
                if frame:
                    # Gaze verilerini çıkar
                    avg = frame.get('avg', {})
                    x = avg.get('x', 0)
                    y = avg.get('y', 0)
                    # time milliseconds cinsinden, saniyeye çevir
                    time_ms = frame.get('time', int(time_module.time() * 1000))
                    timestamp = time_ms / 1000.0
                    
                    with self.lock:
                        self.latest_gaze = (x, y, timestamp)
                    
                    return (x, y, timestamp)
                else:
                    # Frame boş - sessizce None döndür (çok sık çağrılıyor)
                    return None
            else:
                # Statuscode 200 değil veya yanıt formatı beklenmeyen - sessizce None döndür
                return None
            
        except Exception as e:
            # Sadece hata durumunda log (çok sık çağrılıyor olabilir)
            self._log("UYARI: Gaze verisi alma hatası: {}: {}".format(type(e).__name__, e))
            return None
    
    def get_latest_gaze(self, consume: bool = False) -> Optional[Tuple[float, float, float]]:
        """
        Thread-safe olarak en son gaze verisini döndürür.
        Listener thread'den gelen push mode verilerini kullanır.
        
        Args:
            consume: True ise, data döndürüldükten sonra None yapılır (aynı data tekrar kullanılmaz)
        """
        if not self.connected or not self.tracking:
            return None
        
        with self.lock:
            data = self.latest_gaze
            if consume and data is not None:
                self.latest_gaze = None  # Aynı data tekrar kullanılmasın
            return data
    
    def calibration_prepare(self):
        """Yeni bir kalibrasyona başlamadan önce sunucuyu temiz duruma getirir."""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")

        self._log("Calibration durumu temizleniyor (abort + clear)...")
        for request_type in ('abort', 'clear'):
            try:
                response = self._send_request('calibration', request_type, None, timeout=3.0)
            except ConnectionError as e:
                self._log("UYARI: Calibration {} isteği başarısız: {}".format(request_type, e))
                continue

            statuscode = response.get('statuscode', 'yok')
            statusmessage = response.get('values', {}).get('statusmessage', '')

            if statuscode == 200:
                self._log("Calibration {} tamamlandı.".format(request_type))
            elif isinstance(statuscode, int) and 800 <= statuscode <= 804:
                self._log("Calibration {} gerekli değil (statuscode={}, message={}).".format(
                    request_type, statuscode, statusmessage))
            else:
                self._log("UYARI: Calibration {} beklenmeyen yanıt: statuscode={}, message={}".format(
                    request_type, statuscode, statusmessage))

        # Sunucuya durum güncellemesi için kısa süre tanı
        time_module.sleep(0.1)

    def calibration_start(self, point_count: int = 9):
        """Kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="start", values={"pointcount": integer}
        # Calibration sırasında push mode aktif olabilir, bu yüzden daha uzun timeout kullan
        self._log("Calibration başlatılıyor: point_count={}".format(point_count))
        response = self._send_request('calibration', 'start', {'pointcount': point_count}, timeout=10.0)
        statuscode = response.get('statuscode', 'yok')
        statusmessage = response.get('values', {}).get('statusmessage', '')

        if isinstance(statuscode, int) and statuscode in (800, 801, 802):
            self._log("Calibration start yanıtı statuscode={} ({}). Durum sıfırlanıyor ve tekrar deneniyor...".format(
                statuscode, statusmessage))
            self.calibration_prepare()
            response = self._send_request('calibration', 'start', {'pointcount': point_count}, timeout=10.0)
            statuscode = response.get('statuscode', 'yok')
            statusmessage = response.get('values', {}).get('statusmessage', '')

        self._log("Calibration start yanıtı: statuscode={}, statusmessage={}".format(statuscode, statusmessage))
        return statuscode == 200
    
    def calibration_pointstart(self, x: float, y: float):
        """Belirli bir nokta için kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="pointstart", values={"x": integer, "y": integer}
        # x ve y integer olmalı (pixel koordinatları)
        response = self._send_request('calibration', 'pointstart', {'x': int(x), 'y': int(y)})
        statuscode = response.get('statuscode', 'yok')
        if statuscode != 200:
            statusmessage = response.get('values', {}).get('statusmessage', '')
            self._log("UYARI: calibration_pointstart başarısız (x={}, y={}): statuscode={}, message={}".format(
                int(x), int(y), statuscode, statusmessage))
        return statuscode == 200
    
    def calibration_pointend(self, x: float = None, y: float = None):
        """Belirli bir nokta için kalibrasyonu bitirir"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="pointend" (values yok)
        response = self._send_request('calibration', 'pointend', None)
        statuscode = response.get('statuscode', 'yok')
        if statuscode != 200:
            statusmessage = response.get('values', {}).get('statusmessage', '')
            self._log("UYARI: calibration_pointend başarısız: statuscode={}, message={}".format(
                statuscode, statusmessage))
        return statuscode == 200
    
    def calibration_abort(self):
        """Kalibrasyonu iptal eder"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="abort" (values yok)
        response = self._send_request('calibration', 'abort', None)
        statuscode = response.get('statuscode', 'yok')
        if statuscode != 200:
            statusmessage = response.get('values', {}).get('statusmessage', '')
            self._log("UYARI: calibration_abort yanıtı: statuscode={}, message={}".format(
                statuscode, statusmessage))
        return statuscode == 200
    
    def calibration_result(self) -> dict:
        """Kalibrasyon sonucunu döndürür"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # Not: TheEyeTribe API'sinde ayrı bir "result" request'i yok
        # Calibration result genellikle son pointend yanıtında gelir
        # Bu metod sadece son pointend yanıtını saklamak için kullanılabilir
        # Şimdilik boş dict döndürüyoruz, çünkü result pointend'den geliyor
        return {}
    
    def calibration_clear(self):
        """Kalibrasyon verilerini temizler"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="clear" (values yok)
        response = self._send_request('calibration', 'clear', None)
        statuscode = response.get('statuscode', 'yok')
        if statuscode != 200:
            statusmessage = response.get('values', {}).get('statusmessage', '')
            self._log("UYARI: calibration_clear yanıtı: statuscode={}, message={}".format(
                statuscode, statusmessage))
        return statuscode == 200
    
    def send_heartbeat(self):
        """Sunucuya heartbeat gönderir (bağlantıyı canlı tutmak için)"""
        if not self.connected:
            return False
        
        try:
            # TheEyeTribe API formatı: category="heartbeat", request=null (C# örneğine göre)
            # C# örneği: {"category":"heartbeat","request":null}
            response = self._send_request('heartbeat', None, None, timeout=1.0)
            return response.get('statuscode') == 200
        except Exception as e:
            self._log("UYARI: Heartbeat gönderilemedi: {}".format(e))
            return False
    
    def is_connected(self) -> bool:
        """Bağlantı durumunu kontrol eder"""
        return self.connected
    
    def is_tracking(self) -> bool:
        """Takip durumunu kontrol eder"""
        return self.tracking
    
    def release(self):
        """Kaynakları serbest bırakır (eski API uyumluluğu için)"""
        self.disconnect()