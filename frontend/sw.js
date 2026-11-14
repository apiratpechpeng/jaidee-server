// Service worker แบบง่ายที่สุด — มีไว้เพื่อให้เบราว์เซอร์อนุญาตให้ "ติดตั้งเป็นแอป" ได้
// (เงื่อนไขหนึ่งของ PWA คือต้องมี service worker ที่ควบคุม fetch)
//
// กลยุทธ์: cache เฉพาะไฟล์หน้าตาเว็บ (HTML/CSS/JS/ไอคอน) แบบ "เช็คเน็ตก่อนเสมอ ถ้าออนไลน์
// ต้องได้ไฟล์ล่าสุดจริงๆ ค่อย fallback ไปใช้ cache ตอนออฟไลน์เท่านั้น" (network-first)
// เดิมทีใช้กลยุทธ์ "cache ก่อนแล้วค่อยอัปเดตเบื้องหลัง" ซึ่งทำให้เห็นโค้ดหน้าเว็บฉบับเก่าค้างอยู่
// เสมอ (ช้ากว่าไฟล์จริงอยู่ 1 รอบรีเฟรช) เวลาที่ยังแก้ไขไฟล์ frontend บ่อยๆ แบบตอนพัฒนาอยู่
// จึงเปลี่ยนมาเป็น network-first แทน เพื่อให้แก้โค้ดแล้วเห็นผลทันทีตั้งแต่รีเฟรชครั้งแรก
//
// ส่วน /api/... (ข้อมูลผู้ใช้ แชท แบบประเมิน) ปล่อยผ่านไปหาเซิร์ฟเวอร์ตรงๆ เสมอ ไม่ cache เด็ดขาด
// เพื่อไม่ให้แอปแสดงข้อมูลเก่าค้าง (โดยเฉพาะช่วงวิกฤตที่ต้องได้คำตอบสดใหม่เสมอ)

const CACHE_NAME = "jaidee-shell-v2"; // เปลี่ยนเลขเวอร์ชันทุกครั้งที่แก้กลยุทธ์ cache เพื่อล้างของเก่าทิ้ง
const SHELL_FILES = [
  "/",
  "/index.html",
  "/style.css",
  "/app.js",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // ไม่ยุ่งกับ API เลย — ปล่อยให้วิ่งไปเซิร์ฟเวอร์ตรงๆ ทุกครั้ง
  if (url.pathname.startsWith("/api/")) return;
  if (event.request.method !== "GET") return;

  // network-first: ลองโหลดจากเน็ตก่อนเสมอ ได้ไฟล์ล่าสุดจริงๆ มาแสดง แล้วค่อยอัปเดต cache
  // ไว้เผื่อออฟไลน์ (ถ้าเน็ตหลุด/ใช้งานออฟไลน์ค่อยดึงจาก cache ที่เก็บไว้ล่าสุดมาแทน)
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
