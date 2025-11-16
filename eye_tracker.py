"""
TheEyeTribe Eye Tracker Implementation
TheEyeTribe, TCP socket üzerinden JSON protokolü kullanarak çalışır.
Kullanım için TheEyeTribe sunucusunun çalışıyor olması gerekir.
"""

import socket
import json
import time
import threading
from typing import Optional, Tuple

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
        
    def _get_request_id(self):
        """Her istek için benzersiz ID oluşturur"""
        self.request_id += 1
        return self.request_id
    
    def _log(self, message: str):
        """Log mesajı yazdırır (zaman damgası ile)"""
        try:
            timestamp = time.strftime("%H:%M:%S.%f")[:-3]  # milisaniye hassasiyeti
        except Exception:
            timestamp = time.strftime("%H:%M:%S")
        
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
        
        # Socket timeout'unu ayarla (her istek için)
        old_timeout = self.socket.gettimeout()
        old_timeout_str = str(old_timeout) if old_timeout is not None else "None"
        try:
            self.socket.settimeout(timeout)
            self._log("Socket timeout ayarlandı: {}s (önceki: {})".format(timeout, old_timeout_str))
        except Exception as e:
            self._log("UYARI: Socket timeout ayarlanamadı: {}".format(e))
            pass
        
        # TheEyeTribe API formatı (JSON-RPC değil!)
        request = {
            "category": category
        }
        
        # request_type'ı ekle (None ise null olarak eklenir - heartbeat için gerekli)
        # C# örneği: {"category":"heartbeat","request":null}
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
            
            # İsteği gönder - sendall tüm byte'ları gönderir
            self.socket.sendall(message_bytes)
            self._log("İstek başarıyla gönderildi ({} byte)".format(len(message_bytes)))
            
            # Yanıtı al - timeout ile korumalı
            response_data = b''
            start_time = time.time()
            recv_count = 0
            
            self._log("Yanıt bekleniyor...")
            
            while b'\r\n' not in response_data:
                # Timeout kontrolü
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self._log("TIMEOUT: {:.2f}s geçti, limit: {}s".format(elapsed, timeout))
                    raise ConnectionError("Sunucu yanıt vermiyor (timeout: {}s)".format(timeout))
                
                try:
                    # Kalan timeout süresini hesapla
                    remaining_timeout = max(0.1, timeout - elapsed)
                    self.socket.settimeout(remaining_timeout)
                    
                    recv_count += 1
                    if recv_count == 1:
                        self._log("recv() çağrılıyor (kalan timeout: {:.2f}s)...".format(remaining_timeout))
                    
                    chunk = self.socket.recv(4096)
                    
                    if chunk:
                        total_bytes = len(response_data) + len(chunk)
                        self._log("Veri alındı: {} byte (toplam: {} byte)".format(len(chunk), total_bytes))
                    else:
                        self._log("HATA: Boş chunk alındı (bağlantı kesildi)")
                        raise ConnectionError("Sunucu bağlantısı kesildi")
                    
                    response_data += chunk
                    
                    if b'\r\n' in response_data:
                        self._log("Yanıt tamamlandı: {} byte, {} recv() çağrısı".format(len(response_data), recv_count))
                        
                except socket.timeout:
                    # Timeout oldu - kontrol et
                    elapsed = time.time() - start_time
                    self._log("recv() timeout: {:.2f}s geçti (limit: {}s)".format(elapsed, timeout))
                    if elapsed >= timeout:
                        raise ConnectionError("Sunucu yanıt vermiyor (timeout: {}s)".format(timeout))
                    # Kısa timeout olabilir, devam et
                    self._log("Kısa timeout, devam ediliyor...")
                    continue
                except (socket.error, OSError) as e:
                    self._log("HATA: Socket hatası: {}".format(e))
                    raise ConnectionError("Socket hatası: {}".format(e))
            
            # JSON yanıtını parse et
            if not response_data:
                self._log("HATA: Boş yanıt alındı")
                raise ConnectionError("Sunucudan boş yanıt alındı")
            
            self._log("Yanıt parse ediliyor: {} byte".format(len(response_data)))
            response_str = response_data.split(b'\r\n')[0].decode('utf-8')
            # Güvenli gösterim için özel karakterleri escape et
            response_display = response_str.replace('\n', '\\n').replace('\r', '\\r')
            if len(response_display) > 100:
                self._log("Yanıt string: {}...".format(response_display[:100]))
            else:
                self._log("Yanıt string: {}".format(response_display))
            
            response = json.loads(response_str)
            # TheEyeTribe yanıt formatı kontrolü
            has_statuscode = 'var' if 'statuscode' in response else 'yok'
            has_values = 'var' if 'values' in response else 'yok'
            statuscode = response.get('statuscode', 'yok')
            self._log("JSON parse başarılı: category={}, request={}, statuscode={}, values={}".format(
                response.get('category', 'yok'), response.get('request', 'yok'), statuscode, has_values))
            
            return response
            
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
            self._log("HATA: Beklenmeyen hata: {}: {}".format(type(e).__name__, e))
            raise ConnectionError("İstek gönderilirken hata: {}".format(e))
        finally:
            # Timeout'u eski haline getir
            try:
                self.socket.settimeout(old_timeout)
                old_timeout_display = str(old_timeout) if old_timeout is not None else "None"
                self._log("Socket timeout eski haline getirildi: {}".format(old_timeout_display))
            except Exception as e:
                self._log("UYARI: Timeout geri alınamadı: {}".format(e))
                pass
    
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
            connect_start = time.time()
            
            try:
                # Normal connect kullan (timeout zaten ayarlı)
                self.socket.connect((self.host, self.port))
                connect_elapsed = time.time() - connect_start
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
                connect_elapsed = time.time() - connect_start
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
                connect_elapsed = time.time() - connect_start
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
                connect_elapsed = time.time() - connect_start
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
        
        if self.socket:
            try:
                self.socket.close()
                self._log("Socket kapatıldı")
            except Exception as e:
                self._log("UYARI: Socket kapatılırken hata: {}".format(e))
        self.connected = False
        self.socket = None
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
                    time_ms = frame.get('time', int(time.time() * 1000))
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
    
    def get_latest_gaze(self) -> Optional[Tuple[float, float, float]]:
        """Thread-safe olarak en son gaze verisini döndürür"""
        with self.lock:
            return self.latest_gaze
    
    def calibration_start(self, point_count: int = 9):
        """Kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="start", values={"pointcount": integer}
        response = self._send_request('calibration', 'start', {'pointcount': point_count})
        return response.get('statuscode') == 200
    
    def calibration_pointstart(self, x: float, y: float):
        """Belirli bir nokta için kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="pointstart", values={"x": integer, "y": integer}
        # x ve y integer olmalı (pixel koordinatları)
        response = self._send_request('calibration', 'pointstart', {'x': int(x), 'y': int(y)})
        return response.get('statuscode') == 200
    
    def calibration_pointend(self, x: float = None, y: float = None):
        """Belirli bir nokta için kalibrasyonu bitirir"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="pointend" (values yok)
        response = self._send_request('calibration', 'pointend', None)
        return response.get('statuscode') == 200
    
    def calibration_abort(self):
        """Kalibrasyonu iptal eder"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        # TheEyeTribe API formatı: category="calibration", request="abort" (values yok)
        response = self._send_request('calibration', 'abort', None)
        return response.get('statuscode') == 200
    
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
        return response.get('statuscode') == 200
    
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