import sys
import time
import asyncio
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt5.QtGui import QFont, QPalette, QColor, QLinearGradient, QBrush
from PyQt5.QtCore import Qt
from playwright.async_api import async_playwright
from qasync import QEventLoop

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("網站載入摘要小工具")

        # ➤ 建議視窗大小（你要求的大小）
        self.resize(600, 400)

        # ===== 背景漸層 =====
        palette = QPalette()
        gradient = QLinearGradient(0,0,0,1)
        gradient.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
        gradient.setColorAt(0, QColor(140, 190, 255))
        gradient.setColorAt(1, QColor(160, 177, 255))
        palette.setBrush(QPalette.Window, QBrush(gradient))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        # 整體字體
        self.setFont(QFont("Microsoft JhengHei", 13))

        # ===== 輸入框 =====
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("請貼上網址...")
        self.url_input.setFont(QFont("Microsoft JhengHei", 14))
        self.url_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border: 2px solid rgba(255,255,255,0.7);
                border-radius: 18px;
                background-color: rgba(255,255,255,0.2);
                color: white;
            }
        """)

        # ===== 膠囊按鈕（小型版） =====
        self.button = QPushButton("開始分析")
        self.button.setFont(QFont("Microsoft JhengHei", 16, QFont.Bold))
        self.button.setFixedWidth(180)     # ← 按鈕不再佔滿整行！

        self.button.setStyleSheet("""
            QPushButton {
                padding: 6px 18px;
                border-radius: 18px;
                border: 2px solid rgba(255,255,255,0.85);
                background-color: rgba(255,255,255,0.15);
                color: white;
                font-size: 20px;
            }
            QPushButton:hover {
                border: 2px solid rgba(255,255,255,1.0);
                background-color: rgba(255,255,255,0.22);
            }
            QPushButton:pressed {
                border: 2px solid #FFD56A;
                background-color: rgba(255,255,255,0.30);
                color: #FFE8A3;
            }
            QPushButton:disabled {
                border: 2px solid rgba(255,255,255,0.4);
                color: rgba(255,255,255,0.4);
                background-color: rgba(255,255,255,0.08);
            }
        """)

        self.button.clicked.connect(self.run_analysis)

        # ===== 結果輸出 =====
        self.output = QLabel("尚未分析")
        self.output.setWordWrap(True)
        self.output.setFont(QFont("Microsoft JhengHei", 15))
        self.output.setStyleSheet("color: white;")

        # ===== Layout =====
        layout = QVBoxLayout()
        layout.addWidget(self.url_input)
        layout.addWidget(self.button, alignment=Qt.AlignHCenter)  # ← 按鈕居中
        layout.addWidget(self.output)
        layout.setSpacing(25)
        layout.setContentsMargins(40,40,40,40)
        self.setLayout(layout)

    # ===== 開始分析 =====
    def run_analysis(self):
        url = self.url_input.text().strip()
        if url:
            asyncio.create_task(self.analyze(url))

    # ===== 主分析流程 =====
    async def analyze(self, url):
        self.output.setText("讀取中，請稍候...")

        async with async_playwright() as p:

            browser = await p.chromium.launch(
                args=[
                    "--disable-cache",
                    "--disk-cache-size=0",
                    "--media-cache-size=0",
                    "--disable-application-cache",
                    "--disable-default-apps",
                    "--disable-background-networking",
                ]
            )

            context = await browser.new_context()

            await context.route("**/*", lambda route: route.continue_(headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }))

            page = await context.new_page()

            # 清除 storage
            await page.add_init_script("""
                localStorage.clear();
                sessionStorage.clear();
            """)

            try:
                await page.evaluate("""
                    caches.keys().then(keys => keys.forEach(k => caches.delete(k)));
                """)
            except:
                pass

            # ===== request 偵測 =====
            start_time = time.time()
            last_request_finish_time = start_time
            requests = []

            async def on_finish(request):
                nonlocal last_request_finish_time
                last_request_finish_time = time.time()
                requests.append(request)

            page.on("requestfinished", on_finish)

            # ===== 開始載入 =====
            await page.goto(url)

            # ===== Idle 偵測（模擬 Chrome Idle 行為）=====
            idle_buffer = 1.5

            while True:
                now = time.time()
                if now - last_request_finish_time >= idle_buffer:
                    break
                await asyncio.sleep(0.05)

            # ===== Navigation Timing（Chrome 同步）=====
            nav = await page.evaluate("performance.getEntriesByType('navigation')[0]")

            dcl = nav["domContentLoadedEventEnd"]
            load = nav["loadEventEnd"]

            # ===== 資源大小 =====
            resources = await page.evaluate("performance.getEntriesByType('resource')")
            total_transfer = sum(r.get("transferSize", 0) for r in resources)
            total_resource = sum(r.get("decodedBodySize", 0) for r in resources)

            # ===== 完成時間 =====
            finish_sec = last_request_finish_time - start_time

            await browser.close()

            # ===== 最終輸出 =====
            summary = (
                f"要求數量：{len(requests)}\n"
                f"已轉移：{round(total_transfer/1024/1024,2)} MB\n"
                f"資源大小：{round(total_resource/1024/1024,2)} MB\n"
                f"DOMContentLoaded：{int(dcl)} 毫秒\n"
                f"載入：{int(load)} 毫秒\n"
                f"完成：{round(finish_sec,2)} 秒"
            )

            self.output.setText(summary)


# ===== 主程式 =====
app = QApplication(sys.argv)
loop = QEventLoop(app)
asyncio.set_event_loop(loop)

with loop:
    w = Window()
    w.show()
    loop.run_forever()
