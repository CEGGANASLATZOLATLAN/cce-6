#  LearnWords — 6 Sefer Kelime Ezberleme Sistemi

Scrum metodolojisiyle geliştirilen, aralıklı tekrar (spaced repetition) yöntemiyle
kalıcı kelime öğrenmeyi sağlayan web uygulaması.

## Özellikler

| Story | Açıklama | Puan |
|-------|----------|------|
| Story 1 | Kullanıcı Kayıt / Giriş / Şifremi Unuttum | 5 |
| Story 2 | Kelime Ekleme (resim + örnek cümleler) | 5 |
| Story 3 | 6 Sefer Sınav Modülü (spaced repetition) | 10 |
| Story 4 | Günlük kelime sayısı ayarı | 5 |
| Story 5 | Analiz Raporu (yazdırılabilir) | 5 |
| Story 6 | Wordle Bulmacası | 15 |
| Story 7 | Word Chain (hikaye oluşturucu) | 5 |

## Kurulum

```bash
# 1. Gerekli paketleri kur
pip install flask flask-sqlalchemy werkzeug

# 2. Uygulamayı başlat
python app.py
```

Tarayıcıda aç: **http://localhost:5001**

## 6 Sefer Algoritması

Bir kelimeyi kalıcı öğrenmek için 6 farklı zaman diliminde doğru cevaplanması gerekir:

```
İlk Doğru → 1 Gün → 1 Hafta → 1 Ay → 3 Ay → 6 Ay → 1 Yıl → ✅ Öğrenildi
```

Herhangi bir aşamada yanlış cevap verilirse süreç **sıfırdan** başlar.

## Veritabanı Şeması

```
Users         : UserID, UserName, Password, Email, words_per_day
Words         : WordID, EngWordName, TurWordName, Picture, Audio
WordSamples   : WordSamplesID, WordID, Sample
UserWordProgress : UserID, WordID, Stage(0-6), next_review, is_learned
QuizAnswers   : UserID, WordID, is_correct, quiz_date, stage_before
```

## Teknolojiler

- **Backend:** Python / Flask
- **Veritabanı:** SQLite (SQLAlchemy ORM)
- **Frontend:** Bootstrap 5, Vanilla JS
- **Şifreleme:** Werkzeug (bcrypt hash)
