#  LearnWords — 6 Sefer Kelime Ezberleme Sistemi(Okul projesi)

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
# 1. Gerekli paketleri kurmak için;
pip install -r requirements.txt
```

### API Key'ler (zorunlu)

Uygulama çalışmak için iki API key'e ihtiyaç duyar. Proje klasöründe `.env` adında bir dosya oluşturup aşağıdaki bilgileri gir:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
HF_TOKEN=hf_...
```

| Key | Ne için | Nereden alınır |
|-----|---------|----------------|
| `ANTHROPIC_API_KEY` | Word Chain'de Türkçe hikaye üretimi (Claude Haiku) | [console.anthropic.com](https://console.anthropic.com) |
| `HF_TOKEN` | Word Chain'de AI görsel üretimi (FLUX.1-schnell) | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |

> `.env` dosyası `.gitignore`'a eklenmiştir, GitHub'a yüklenmez.

```bash
# 2. Uygulamayı başlatmak için;
python app.py
```

**macOS'ta:** `projeyibaslat.command` dosyasına çift tıklayarak da başlatabilirsin.

Tarayıcıda aç: **http://localhost:5001** veya **http://127.0.0.1:5001/**

## 6 Sefer Algoritması

Bir kelimeyi kalıcı öğrenmek için 6 farklı zaman diliminde doğru cevaplanması gerekir:

```
İlk Doğru → 1 Gün → 1 Hafta → 1 Ay → 3 Ay → 6 Ay → 1 Yıl →  Öğrenildi
```

Herhangi bir aşamada yanlış cevap verilirse süreç **sıfırdan** başlar.

## Veritabanı Şeması

```
Users            : UserID, UserName, Password, Email, words_per_day
Words            : WordID, EngWordName, TurWordName, Picture, Audio
WordSamples      : WordSamplesID, WordID, Sample
UserWordProgress : UserID, WordID, Stage(0-6), next_review, is_learned
QuizAnswers      : UserID, WordID, is_correct, quiz_date, stage_before
```

## Teknolojiler

- **Backend:**    Python / Flask
- **Veritabanı:** SQLite (SQLAlchemy ORM)
- **Frontend:**   Bootstrap 5, Vanilla JS
- **Şifreleme:**  Werkzeug (bcrypt hash)
