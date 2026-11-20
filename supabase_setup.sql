-- ใจดี v20: ตารางเก็บข้อมูลวิจัยบน Supabase
-- วิธีใช้: Supabase -> SQL Editor -> New query -> วางทั้งไฟล์นี้ -> Run (ทำครั้งเดียว)
-- ชื่อคอลัมน์ต้องตรงกับที่ backend/research_log.py ส่งไป ถ้าแก้ฝั่งใดฝั่งหนึ่ง ต้องแก้อีกฝั่งด้วย

create table if not exists research_chat (
  id bigint generated always as identity primary key,
  participant text not null,          -- รหัสสุ่มแทนผู้ใช้ (ย้อนกลับเป็นบัญชีจริงไม่ได้)
  conversation text not null,         -- รหัสสุ่มแทนบทสนทนา
  turn_no int,
  user_text text,                     -- ข้อความผู้ใช้ (ลบเบอร์/อีเมล/ชื่อ/โรงเรียนแล้ว)
  bot_text text,
  bot_bubbles int,
  intent text,
  topic text,
  secondary_topic text,
  topic_source text,
  topic_confidence real,
  dialogue_id text,
  sentiment text,
  crisis_level text,
  crisis_source text,
  reply_kind text,
  age_group text,
  age_band text,
  cards jsonb,
  model_name text,
  chatbot_build text,
  created_at timestamptz default now(),
  -- ช่องให้ผู้ตรวจ 2 คนกรอกภายหลัง (ไว้คำนวณ F1 และ Cohen's kappa)
  rater1_crisis text, rater2_crisis text, rater1_topic text, rater2_topic text, rater_note text
);

create table if not exists research_assessment (
  id bigint generated always as identity primary key,
  participant text not null,
  assessment_ref text,
  total_score int,
  severity_level text,
  q9_value int,
  answers jsonb,
  age_band text,
  created_at timestamptz default now()
);

create table if not exists research_rating (
  id bigint generated always as identity primary key,
  participant text not null,
  conversation text,
  bucket text,
  created_at timestamptz default now()
);

-- เปิด Row Level Security และไม่สร้าง policy ใดๆ = คนทั่วไปอ่าน/เขียนไม่ได้เลย
-- มีแค่เซิร์ฟเวอร์ (ใช้ service_role key) กับเจ้าของบัญชี Supabase ที่เข้าถึงได้
alter table research_chat enable row level security;
alter table research_assessment enable row level security;
alter table research_rating enable row level security;
