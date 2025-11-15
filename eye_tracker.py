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
    
    def _send_request(self, method: str, params: dict = None) -> dict:
        """
        TheEyeTribe sunucusuna JSON isteği gönderir ve yanıtı alır.
        
        Args:
            method: API metod adı (örn: 'get', 'set', 'calibration.start')
            params: İsteğe eklenecek parametreler
            
        Returns:
            Sunucudan gelen JSON yanıtı
        """
        if not self.connected:
            raise ConnectionError("TheEyeTribe sunucusuna bağlı değil!")
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_request_id(),
            "method": method
        }
        
        if params:
            request["params"] = params
        
        try:
            # JSON isteğini gönder
            message = json.dumps(request) + '\r\n'
            self.socket.sendall(message.encode('utf-8'))
            
            # Yanıtı al
            response_data = b''
            while b'\r\n' not in response_data:
                chunk = self.socket.recv(4096)
                if not chunk:
                    raise ConnectionError("Sunucu bağlantısı kesildi")
                response_data += chunk
            
            # JSON yanıtını parse et
            response_str = response_data.split(b'\r\n')[0].decode('utf-8')
            response = json.loads(response_str)
            
            return response
            
        except Exception as e:
            raise ConnectionError(f"İstek gönderilirken hata: {e}")
    
    def connect(self) -> bool:
        """
        TheEyeTribe sunucusuna bağlanır.
        
        Returns:
            Bağlantı başarılı ise True
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5.0)
            self.socket.connect((self.host, self.port))
            self.connected = True
            
            # Bağlantıyı test et
            response = self._send_request('get', {'category': 'tracker', 'request': 'version'})
            if 'result' in response:
                print(f"TheEyeTribe bağlantısı başarılı! Versiyon: {response.get('result', {}).get('version', 'bilinmiyor')}")
                return True
            else:
                self.connected = False
                return False
                
        except Exception as e:
            print(f"TheEyeTribe bağlantı hatası: {e}")
            print("Lütfen TheEyeTribe sunucusunun çalıştığından emin olun.")
            self.connected = False
            return False
    
    def disconnect(self):
        """TheEyeTribe sunucusuyla bağlantıyı keser"""
        if self.tracking:
            self.stop_tracking()
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        self.connected = False
        self.socket = None
    
    def start_tracking(self):
        """Göz takibini başlatır"""
        if not self.connected:
            raise ConnectionError("Önce bağlantı kurulmalı!")
        
        try:
            # Push modunu etkinleştir (sürekli veri almak için)
            response = self._send_request('set', {
                'category': 'tracker',
                'request': 'push',
                'values': [True]
            })
            
            if 'result' in response and response['result'].get('statuscode') == 200:
                self.tracking = True
                print("Göz takibi başlatıldı")
            else:
                raise Exception("Takip başlatılamadı")
                
        except Exception as e:
            print(f"Takip başlatma hatası: {e}")
            raise
    
    def stop_tracking(self):
        """Göz takibini durdurur"""
        if not self.tracking:
            return
        
        try:
            response = self._send_request('set', {
                'category': 'tracker',
                'request': 'push',
                'values': [False]
            })
            self.tracking = False
            print("Göz takibi durduruldu")
        except Exception as e:
            print(f"Takip durdurma hatası: {e}")
    
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
            # Frame verisini al
            response = self._send_request('get', {
                'category': 'tracker',
                'request': 'frame'
            })
            
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
            
            return None
            
        except Exception as e:
            print(f"Gaze verisi alma hatası: {e}")
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