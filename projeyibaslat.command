#!/bin/bash

# Proje klasörüne geç
cd "$(dirname "$0")"

echo "================================================"
echo "   CCE - Kelime Ezberleme Uygulaması"
echo "================================================"
echo ""

# Eski sunucu varsa kapat
OLD_PID=$(lsof -ti :5001)
if [ -n "$OLD_PID" ]; then
  echo "⚡ Eski sunucu kapatılıyor..."
  kill -9 $OLD_PID 2>/dev/null
  sleep 1
fi

echo "🚀 Sunucu başlatılıyor..."
python3 app.py &
SERVER_PID=$!

# Sunucunun açılmasını bekle
sleep 2

echo ""
echo "✅ Sunucu açıldı → http://localhost:5001"
echo ""

# Tarayıcıyı otomatik aç
open http://localhost:5001

echo "🔴 Kapatmak için bu pencereyi kapatın veya Ctrl+C yapın."
echo "================================================"

# Sunucu kapanana kadar bekle
wait $SERVER_PID
