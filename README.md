## Ne yapıyor?

Kullanıcı kaydı ve girişi var. Kelime eklerken resim ve örnek cümleler de ekleyebiliyorsun. 6 aşamalı sınav sistemiyle kelimeleri kalıcı öğreniyorsun. Günlük kaç kelime çalışacağını kendin ayarlayabiliyorsun. Analiz ekranından gelişimini görebilir, yazdırabilirsin. Ayrıca eğlenmek için Wordle bulmacası ve AI destekli Word Chain (kelimelerden hikaye oluşturucu) de var.

## Kurulumu nasıl yaparsın?

Önce gerekli paketleri kur:

```
pip install -r requirements.txt
```

Sonra aşağıdaki adımı yapmadan uygulama çalışmaz, atlama.

## API Key'ler (zorunlu)

Word Chain özelliği için iki farklı API key lazım. Proje klasörüne .env adında bir dosya aç ve şunları yaz:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
HF_TOKEN=hf_...
```

ANTHROPIC_API_KEY olmadan hikaye oluşturmuyor. console.anthropic.com adresinden alabilirsin. Anthropic API Key ücretlidir.

HF_TOKEN olmadan görsel oluşturmuyor. huggingface.co/settings/tokens adresinden alabilirsin. Hugging Face API Key "1$" kredi vermektedir.

## Başlatmak için

```
python app.py
```

macOS kullanıyorsan projeyibaslat.command dosyasına çift tıklaman yeterli, otomatik açılıyor.

Sonra tarayıcıda şu adresi aç: http://localhost:5001

## 6 Sefer algoritması nasıl çalışıyor?

Bir kelimeyi gerçekten öğrenmiş sayılman için 6 farklı zamanda doğru cevaplaman gerekiyor. İlk doğru cevabın ardından sırasıyla 1 gün, 1 hafta, 1 ay, 3 ay, 6 ay ve 1 yıl sonra tekrar çıkıyor karşına. Herhangi bir aşamada yanlış cevap verirsen başa dönüyorsun.

## Kullanılan teknolojiler

Backend Python ve Flask ile yazıldı. Veritabanı için SQLite kullandım, SQLAlchemy ORM ile yönetiyorum. Frontend Bootstrap 5 ve Vanilla JS ile yapıldı. Şifreler Werkzeug ile hash'leniyor. AI özellikleri için Anthropic Claude (hikaye) ve HuggingFace FLUX (görsel) entegre ettim.
