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
        timestamp = time.strftime("%H:%M:%S.%f")[:-3]  # milisaniye hassasiyeti
        # Güvenli yazdırma - message içindeki { } karakterleri sorun çıkarmasın diye
        # % formatını kullanarak güvenli yazdırma
        try:
            print("[%s] [EyeTracker] %s" % (timestamp, message))
        except Exception:
            # Eğer hata olursa, direkt yazdır
            print("[{}] [EyeTracker] {}".format(timestamp, str(message).replace('{', '{{').replace('}', '}}')))
    
    def _send_request(self, method: str, params: dict = None, timeout: float = 5.0) -> dict:
        """
        TheEyeTribe sunucusuna JSON isteği gönderir ve yanıtı alır.
        
        Args:
            method: API metod adı (örn: 'get', 'set', 'calibration.start')
            params: İsteğe eklenecek parametreler
            timeout: İstek için timeout süresi (saniye)
            
        Returns:
            Sunucudan gelen JSON yanıtı
        """
        params_str = repr(params) if params else "None"
        method_str = str(method)
        self._log("İstek hazırlanıyor: method={}, params={}, timeout={}s".format(
            repr(method_str), params_str, timeout))
        
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
            self._log(f"Socket timeout ayarlandı: {timeout}s (önceki: {old_timeout_str})")
        except Exception as e:
            self._log(f"UYARI: Socket timeout ayarlanamadı: {e}")
            pass
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": method
        }
        
        if params:
            request["params"] = params
        
        self._log(f"JSON isteği oluşturuldu: id={request['id']}")
        
        try:
            # JSON isteğini gönder
            message = json.dumps(request) + '\r\n'
            message_bytes = message.encode('utf-8')
            message_display = message.strip().replace('\n', '\\n').replace('\r', '\\r')
            if len(message_display) > 200:
                message_display = message_display[:200] + "..."
            self._log("İstek gönderiliyor ({} byte): {}".format(len(message_bytes), message_display))
            
            self.socket.sendall(message_bytes)
            self._log("İstek başarıyla gönderildi")
            
            # Yanıtı al - timeout ile korumalı
            response_data = b''
            start_time = time.time()
            recv_count = 0
            
            self._log("Yanıt bekleniyor...")
            
            while b'\r\n' not in response_data:
                # Timeout kontrolü
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self._log(f"TIMEOUT: {elapsed:.2f}s geçti, limit: {timeout}s")
                    raise ConnectionError(f"Sunucu yanıt vermiyor (timeout: {timeout}s)")
                
                try:
                    # Kalan timeout süresini hesapla
                    remaining_timeout = max(0.1, timeout - elapsed)
                    self.socket.settimeout(remaining_timeout)
                    
                    recv_count += 1
                    if recv_count == 1:
                        self._log(f"recv() çağrılıyor (kalan timeout: {remaining_timeout:.2f}s)...")
                    
                    chunk = self.socket.recv(4096)
                    
                    if chunk:
                        self._log(f"Veri alındı: {len(chunk)} byte (toplam: {len(response_data) + len(chunk)} byte)")
                    else:
                        self._log("HATA: Boş chunk alındı (bağlantı kesildi)")
                        raise ConnectionError("Sunucu bağlantısı kesildi")
                    
                    response_data += chunk
                    
                    if b'\r\n' in response_data:
                        self._log(f"Yanıt tamamlandı: {len(response_data)} byte, {recv_count} recv() çağrısı")
                        
                except socket.timeout:
                    # Timeout oldu - kontrol et
                    elapsed = time.time() - start_time
                    self._log(f"recv() timeout: {elapsed:.2f}s geçti (limit: {timeout}s)")
                    if elapsed >= timeout:
                        raise ConnectionError(f"Sunucu yanıt vermiyor (timeout: {timeout}s)")
                    # Kısa timeout olabilir, devam et
                    self._log("Kısa timeout, devam ediliyor...")
                    continue
                except (socket.error, OSError) as e:
                    self._log(f"HATA: Socket hatası: {e}")
                    raise ConnectionError(f"Socket hatası: {e}")
            
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
            has_result = 'var' if 'result' in response else 'yok'
            has_error = 'var' if 'error' in response else 'yok'
            self._log("JSON parse başarılı: id={}, result={}, error={}".format(
                response.get('id'), has_result, has_error))
            
            return response
            
        except socket.timeout as e:
            self._log(f"HATA: İstek timeout oldu: {e}")
            raise ConnectionError(f"İstek timeout oldu ({timeout}s)")
        except json.JSONDecodeError as e:
            self._log("HATA: JSON parse hatası: {}".format(e))
            if 'response_str' in locals():
                response_display = response_str.replace('\n', '\\n').replace('\r', '\\r')
                if len(response_display) > 200:
                    response_display = response_display[:200] + "..."
                self._log("Hatalı yanıt: {}".format(response_display))
            raise ConnectionError(f"Sunucudan geçersiz JSON yanıtı: {e}")
        except Exception as e:
            self._log(f"HATA: Beklenmeyen hata: {type(e).__name__}: {e}")
            raise ConnectionError(f"İstek gönderilirken hata: {e}")
        finally:
            # Timeout'u eski haline getir
            try:
                self.socket.settimeout(old_timeout)
                old_timeout_display = str(old_timeout) if old_timeout is not None else "None"
                self._log(f"Socket timeout eski haline getirildi: {old_timeout_display}")
            except Exception as e:
                self._log(f"UYARI: Timeout geri alınamadı: {e}")
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
                self._log(f"UYARI: Önceki socket kapatılamadı: {e}")
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
            
            # Önce connect_ex ile test et (non-blocking kontrol)
            try:
                result = self.socket.connect_ex((self.host, self.port))
                if result != 0:
                    connect_elapsed = time.time() - connect_start
                    self._log("HATA: connect_ex başarısız (hata kodu: {}, süre: {:.3f}s)".format(
                        result, connect_elapsed))
                    self.socket.close()
                    self.socket = None
                    return False
                
                # connect_ex başarılı, normal connect ile doğrula
                connect_elapsed = time.time() - connect_start
                self._log("connect_ex başarılı! (Süre: {:.3f}s)".format(connect_elapsed))
                
                # Socket'in gerçekten bağlı olduğunu kontrol et
                try:
                    # getpeername() bağlantı varsa çalışır
                    peer = self.socket.getpeername()
                    self._log("Socket bağlantısı doğrulandı: {}".format(peer))
                except Exception as e:
                    self._log("UYARI: getpeername() başarısız: {}".format(e))
                    # Yine de devam et, bağlantı olabilir
                
            except socket.timeout:
                connect_elapsed = time.time() - connect_start
                self._log("HATA: Bağlantı timeout ({:.3f}s geçti, limit: {}s)".format(
                    connect_elapsed, connection_timeout))
                self.socket.close()
                self.socket = None
                return False
            except (socket.error, OSError, ConnectionRefusedError, ConnectionResetError) as e:
                connect_elapsed = time.time() - connect_start
                self._log("HATA: Bağlantı hatası ({:.3f}s): {}: {}".format(
                    connect_elapsed, type(e).__name__, e))
                self.socket.close()
                self.socket = None
                return False
            
            # Bağlantı başarılı
            self.connected = True
            self._log("Adım 5: Bağlantı durumu güncellendi: connected=True")
            
            # Bağlantıyı test et (opsiyonel - eğer test_connection=False ise atla)
            if test_connection:
                self._log("Adım 6: Bağlantı testi başlatılıyor...")
                test_success = False
                try:
                    self._log("Version isteği gönderiliyor (timeout: 2.0s)...")
                    # Daha kısa timeout ile test et
                    response = self._send_request('get', {'category': 'tracker', 'request': 'version'}, timeout=2.0)
                    
                    if 'result' in response:
                        version = response.get('result', {}).get('version', 'bilinmiyor')
                        self._log("BAĞLANTI BAŞARILI! Versiyon: {}".format(version))
                        test_success = True
                    else:
                        # Geçersiz yanıt ama bağlantı var - devam et
                        self._log("UYARI: Geçersiz yanıt alındı (result yok), ancak bağlantı kuruldu")
                        test_success = False
                        
                except ConnectionError as e:
                    # Test başarısız ama socket bağlı - bağlantıyı kabul et
                    self._log("UYARI: Bağlantı testi başarısız (ConnectionError): {}".format(e))
                    self._log("Ancak socket bağlantısı kuruldu, devam ediliyor...")
                    test_success = False
                except socket.timeout as e:
                    # Timeout - ama socket bağlı
                    self._log("UYARI: Bağlantı testi timeout oldu: {}".format(e))
                    self._log("Ancak socket bağlantısı kuruldu, devam ediliyor...")
                    test_success = False
                except Exception as e:
                    # Beklenmeyen hata - bağlantıyı kabul et ama uyar
                    self._log("UYARI: Test sırasında beklenmeyen hata - {}: {}".format(type(e).__name__, e))
                    self._log("Ancak socket bağlantısı kuruldu, devam ediliyor...")
                    test_success = False
                
                # Test sonucu ne olursa olsun, socket bağlantısı kurulduysa devam et
                if test_success:
                    self._log("=" * 60)
                else:
                    self._log("UYARI: Test başarısız ama socket bağlantısı aktif, devam ediliyor...")
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
                self._log(f"UYARI: Socket kapatılırken hata: {e}")
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
            self._log("Push modu etkinleştiriliyor...")
            response = self._send_request('set', {
                'category': 'tracker',
                'request': 'push',
                'values': [True]
            })
            
            if 'result' in response and response['result'].get('statuscode') == 200:
                self.tracking = True
                self._log("Göz takibi başlatıldı: OK")
            else:
                statuscode = response.get('result', {}).get('statuscode', 'bilinmiyor')
                self._log(f"HATA: Takip başlatılamadı - statuscode: {statuscode}")
                raise Exception("Takip başlatılamadı")
                
        except Exception as e:
            self._log(f"HATA: Takip başlatma hatası: {type(e).__name__}: {e}")
            raise
    
    def stop_tracking(self):
        """Göz takibini durdurur"""
        if not self.tracking:
            self._log("Takip zaten durdurulmuş")
            return
        
        self._log("Göz takibi durduruluyor...")
        try:
            response = self._send_request('set', {
                'category': 'tracker',
                'request': 'push',
                'values': [False]
            })
            self.tracking = False
            self._log("Göz takibi durduruldu: OK")
        except Exception as e:
            self._log(f"HATA: Takip durdurma hatası: {type(e).__name__}: {e}")
    
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
            # Frame verisini al (log sadece hata durumunda)
            response = self._send_request('get', {
                'category': 'tracker',
                'request': 'frame'
            }, timeout=1.0)  # Gaze verisi için daha kısa timeout
            
            if 'result' in response:
                frame = response['result'].get('frame', {})
                if frame:
                    # Gaze verilerini çıkar
                    avg = frame.get('avg', {})
                    x = avg.get('x', 0)
                    y = avg.get('y', 0)
                    timestamp = frame.get('time', time.time())
                    
                    with self.lock:
                        self.latest_gaze = (x, y, timestamp)
                    
                    return (x, y, timestamp)
                else:
                    # Frame boş - sessizce None döndür (çok sık çağrılıyor)
                    return None
            else:
                # Result yok - sessizce None döndür
                return None
            
        except Exception as e:
            # Sadece hata durumunda log (çok sık çağrılıyor olabilir)
            self._log(f"UYARI: Gaze verisi alma hatası: {type(e).__name__}: {e}")
            return None
    
    def get_latest_gaze(self) -> Optional[Tuple[float, float, float]]:
        """Thread-safe olarak en son gaze verisini döndürür"""
        with self.lock:
            return self.latest_gaze
    
    def calibration_start(self, point_count: int = 9):
        """Kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.start', {'pointcount': point_count})
        return response.get('result', {}).get('statuscode') == 200
    
    def calibration_pointstart(self, x: float, y: float):
        """Belirli bir nokta için kalibrasyonu başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.pointstart', {'x': x, 'y': y})
        return response.get('result', {}).get('statuscode') == 200
    
    def calibration_pointend(self, x: float, y: float):
        """Belirli bir nokta için kalibrasyonu bitirir"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.pointend', {'x': x, 'y': y})
        return response.get('result', {}).get('statuscode') == 200
    
    def calibration_abort(self):
        """Kalibrasyonu iptal eder"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.abort')
        return response.get('result', {}).get('statuscode') == 200
    
    def calibration_result(self) -> dict:
        """Kalibrasyon sonucunu döndürür"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.result')
        if 'result' in response:
            return response['result']
        return {}
    
    def calibration_clear(self):
        """Kalibrasyon verilerini temizler"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        response = self._send_request('calibration.clear')
        return response.get('result', {}).get('statuscode') == 200
    
    def is_connected(self) -> bool:
        """Bağlantı durumunu kontrol eder"""
        return self.connected
    
    def is_tracking(self) -> bool:
        """Takip durumunu kontrol eder"""
        return self.tracking
    
    def release(self):
        """Kaynakları serbest bırakır (eski API uyumluluğu için)"""
        self.disconnect()