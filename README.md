## Özellikler

Kullanıcı kayıt, giriş ve şifremi unuttum ekranları mevcuttur. Kelime ekleme sırasında resim ve örnek cümleler de eklenebilir. 6 sefer sınav modülü ile spaced repetition algoritması uygulanmaktadır. Günlük kelime sayısı ayarlanabilir. Analiz raporu ekranı yazdırılabilir. Wordle bulmacası ve Word Chain (AI destekli hikaye oluşturucu) özellikleri de bulunmaktadır.

## Kurulum

Önce gerekli paketleri kur:

```
pip install -r requirements.txt
```

## API Key'ler (zorunlu)

Uygulama çalışmak için iki API key'e ihtiyaç duyar. Proje klasöründe .env adında bir dosya oluşturup aşağıdaki bilgileri gir:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
HF_TOKEN=hf_...
```

ANTHROPIC_API_KEY, Word Chain özelliğinde Türkçe hikaye üretimi için kullanılır. console.anthropic.com adresinden alınabilir.

HF_TOKEN, Word Chain özelliğinde AI görsel üretimi için kullanılır. huggingface.co/settings/tokens adresinden alınabilir.

.env dosyası .gitignore'a eklenmiştir, GitHub'a yüklenmez.

Anthropic API Key ücretlidir.
Hugging Face API Key "1$" kredi vermektedir.

Uygulamayı başlatmak için:

```
python app.py
```

macOS'ta projeyibaslat.command dosyasına çift tıklayarak da başlatabilirsin.

Tarayıcıda aç: http://localhost:5001

## 6 Sefer Algoritması

Bir kelimeyi kalıcı öğrenmek için 6 farklı zaman diliminde doğru cevaplanması gerekir. Sırasıyla ilk doğru cevabın ardından 1 gün, 1 hafta, 1 ay, 3 ay, 6 ay ve 1 yıl sonra tekrar sorulur. Herhangi bir aşamada yanlış cevap verilirse süreç sıfırdan başlar.

## Veritabanı Şeması

Users tablosu kullanıcı bilgilerini tutar. Words tablosu kelime çiftlerini, görselleri ve sesleri saklar. WordSamples tablosu her kelimeye ait örnek cümleleri içerir. UserWordProgress tablosu her kullanıcının her kelime için bulunduğu aşamayı ve sonraki tekrar tarihini takip eder. QuizAnswers tablosu ise sınav geçmişini kaydeder.

## Teknolojiler

Backend Python ve Flask ile yazılmıştır. Veritabanı olarak SQLite kullanılmakta, SQLAlchemy ORM ile yönetilmektedir. Frontend Bootstrap 5 ve Vanilla JS ile geliştirilmiştir. Şifreleme için Werkzeug bcrypt hash kullanılmaktadır. AI özellikleri için Anthropic Claude ve HuggingFace FLUX entegre edilmiştir.
