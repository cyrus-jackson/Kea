// watcher.ino — a battery camera that watches one thing and tells Kea.
//
// Board:  Seeed XIAO ESP32S3 Sense  (USB-C, LiPo charging, OV2640)
// Wake:   AM312 PIR on D1 (GPIO2), 3.3 V, ~12 uA idle
// Power:  1x 3.7 V LiPo on the XIAO's battery pads. The board charges it
//         whenever USB is plugged in, so the cell IS the UPS: plugged in
//         it runs and charges, unplugged it keeps going.
//
// THE WHOLE DESIGN IS "STAY ASLEEP"
//
// Deep sleep is ~14 uA. One wake-capture-upload is about 0.27 mAh, so on
// a 1000 mAh cell the arithmetic is:
//
//     ~10 triggers/day   ->  300+ days
//     every 10 minutes   ->   ~26 days
//     awake, streaming   ->    ~4 hours
//
// Sleep current is what decides this, not resolution or capture rate.
// Which is also why this is not an AI-Thinker ESP32-CAM: that board has
// no power gating and idles near 3 mA, so it loses on twice the battery.
//
// The node PUSHES. Kea never asks it for a frame, because answering
// would mean staying awake and listening. If Kea wants something it
// leaves a command in the POST response, which this picks up on its
// NEXT wake — that is what "on demand" honestly means for a device that
// is asleep almost all the time.
//
// Flash: Arduino IDE, board "XIAO_ESP32S3", PSRAM enabled.

#include "WiFi.h"
#include "HTTPClient.h"
#include "esp_camera.h"
#include "esp_sleep.h"
#include "driver/rtc_io.h"

// ── your setup ──────────────────────────────────────────────────────────
static const char* WIFI_SSID = "CHANGE-ME";
static const char* WIFI_PASS = "CHANGE-ME";
static const char* KEA_HOST  = "192.168.1.50";   // the Pi
static const int   KEA_PORT  = 842;
static const char* KEA_TOKEN = "CHANGE-ME";      // KEA_WATCHER_TOKEN
static const char* NODE_NAME = "door";

#define PIR_PIN  GPIO_NUM_2       // AM312 output
static const uint64_t HEARTBEAT_S = 6UL * 3600UL;   // prove we are alive
static const uint32_t WIFI_TIMEOUT_MS = 8000;       // then give up and sleep

// XIAO ESP32S3 Sense camera pins
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 10
#define SIOD_GPIO_NUM 40
#define SIOC_GPIO_NUM 39
#define Y9_GPIO_NUM 48
#define Y8_GPIO_NUM 11
#define Y7_GPIO_NUM 12
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 16
#define Y4_GPIO_NUM 18
#define Y3_GPIO_NUM 17
#define Y2_GPIO_NUM 15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM 47
#define PCLK_GPIO_NUM 13

RTC_DATA_ATTR uint32_t bootCount = 0;

static float batteryVolts() {
  // The XIAO divides VBAT by 2 onto A0. Rough, but enough to tell you a
  // cell is going flat before it dies in the middle of the night.
  return (analogReadMilliVolts(A0) * 2.0f) / 1000.0f;
}

static bool startCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM; c.pin_d4 = Y6_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM; c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM; c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000; c.pixel_format = PIXFORMAT_JPEG;
  // SVGA keeps a frame near 40 KB. Bigger costs radio time, and radio
  // time is the entire power budget.
  c.frame_size = FRAMESIZE_SVGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;
  return esp_camera_init(&c) == ESP_OK;
}

static void sleepNow() {
  // Power the sensor down BEFORE sleeping. Forgetting this is the usual
  // reason a "14 uA" node measures nearer a milliamp and the month of
  // battery life turns into a week.
  esp_camera_deinit();
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  rtc_gpio_pullup_dis(PIR_PIN);
  rtc_gpio_pulldown_en(PIR_PIN);
  esp_sleep_enable_ext0_wakeup(PIR_PIN, 1);          // PIR goes high
  esp_sleep_enable_timer_wakeup(HEARTBEAT_S * 1000000ULL);
  esp_deep_sleep_start();
}

void setup() {
  bootCount++;

  if (!startCamera()) { sleepNow(); }

  // Throw the first frame away: the sensor's auto-exposure has not
  // settled yet and frame one out of a cold start is usually a
  // washed-out or black rectangle.
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb) esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();
  if (!fb) { sleepNow(); }

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < WIFI_TIMEOUT_MS) {
    delay(100);
  }
  // No network is not an error worth staying awake for. Drop the frame
  // and sleep: the next trigger costs nothing, a stuck radio costs the
  // battery.
  if (WiFi.status() != WL_CONNECTED) { esp_camera_fb_return(fb); sleepNow(); }

  HTTPClient http;
  char url[96];
  snprintf(url, sizeof(url), "http://%s:%d/frame", KEA_HOST, KEA_PORT);
  http.begin(url);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Kea-Token", KEA_TOKEN);
  http.addHeader("X-Kea-Name", NODE_NAME);
  char batt[8];
  snprintf(batt, sizeof(batt), "%.2f", batteryVolts());
  http.addHeader("X-Kea-Battery", batt);

  int code = http.POST(fb->buf, fb->len);
  String reply = (code > 0) ? http.getString() : String("");
  http.end();
  esp_camera_fb_return(fb);

  // Kea can leave one instruction for us, collected here rather than by
  // us listening for it.
  if (reply.indexOf("\"command\":\"capture\"") >= 0) {
    delay(300);
    camera_fb_t* extra = esp_camera_fb_get();
    if (extra) {
      http.begin(url);
      http.addHeader("Content-Type", "image/jpeg");
      http.addHeader("X-Kea-Token", KEA_TOKEN);
      http.addHeader("X-Kea-Name", NODE_NAME);
      http.POST(extra->buf, extra->len);
      http.end();
      esp_camera_fb_return(extra);
    }
  }

  sleepNow();
}

void loop() { }     // never runs: setup() always ends in deep sleep
