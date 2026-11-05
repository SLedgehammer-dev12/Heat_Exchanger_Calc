# Teardown: 3D Makine & Mekanizma Simülatörü Rehberi (Antigravity & OpenCode)

Bu belge, **Teardown** (`https://github.com/elvarofficial/teardown`) becerisinin bu projeye nasıl entegre edildiğini ve hem **Google Antigravity** hem de **OpenCode** ile nasıl kullanılacağını açıklar.

---

## 1. Teardown Nedir?

**Teardown**, karmaşık makinelerin ve fiziksel mekanizmaların (motorlar, iniş takımları, ısı değiştiriciler, pompalar, redüktörler vb.) nasıl çalıştığını gösteren **parçalarına ayrılabilir, interaktif 3D simülatörler** üreten gelişmiş bir ajandır.

### Temel Özellikleri:
- **Tek Sayfa Bağımsız HTML**: Three.js, CSS göstergeleri ve 3D geometrileri tek bir çevrimdışı `~800 KB - 1 MB` HTML dosyasına derler. Web sunucusu gerektirmez, doğrudan tarayıcıda açılır.
- **Tek Kaynaktan Beslenen Matematik**: Parçaları hareket ettiren kinematik formüller (`kin.js`) ile ekrandaki telemetri saatleri (basınç, sıcaklık, hız, açı) aynı fonksiyondan veri alır; hareketle veri asla çelişmez.
- **İnteraktif Kontroller & Kesitler (Cutaway)**:
  - Cam (glass), kesit (section) ve katı (solid) görünüm modları.
  - Her alt sistem için özel butonlar ve odaklanan kameralar.
  - Sayfa boş bırakıldığında imleçle sayfayı gezen **Otomatik Tur (Auto-Tour)** modu; kullanıcı fareye veya tuşlara dokunduğu an kontrolü ziyaretçiye devreder.
- **Kare Kare 60 FPS Video & Prosedürel Ses**:
  - Playwright ve Chromium ile kare kare kayıt (`capture.mjs`).
  - Python ile sentezlenen senkronize sesler (`sfx/score_kit.py`).

---

## 2. İlk Kurulum ve Gereksinimler

Teardown araç kitinin bağımlılıklarını yüklemek için terminalde bir kez çalıştırın:

```bash
cd skills/teardown && npm install && npx playwright install chromium
```

> **Gereksinimler:**
> - **Node.js**: v20 veya daha yenisi.
> - **Python 3**: Ses sentezi için (harici paket gerekmez, standart kütüphane yeterlidir).
> - **FFmpeg** *(Opsiyonel)*: Simülasyonu MP4 videosuna dönüştürmek için.

---

## 3. Hazır Gelen 3 Referans Simülatör

Teardown içinde incelenebilecek ve kopyalanabilecek 3 çalışan örnek bulunur:

| Simülatör | Mekanizma | Giriş Parametresi | Öne Çıkan Yetenek |
|---|---|---|---|
| `v8-*` | Çapraz kranklı V8 motoru | Krank açısı (0-720°) | Silindir patlama sırası (1-8-4-3-6-5-7-2), saydam gömlekler, basınç indikatör diyagramı. |
| `cessna-*` | Cessna 337 ana iniş takımı | Strok (0..1) | Pinyon-kremayer mekanizması, dönen uçak pisti, uçuş fazları. |
| `strandbeest-*` | Theo Jansen'in 20 bacaklı heykeli | Rüzgar hızı | 67 satırda kapalı döngü bacak çember kesişim çözücüsü, zemin temas grafiği. |

### Örnekleri Derlemek İçin:
```bash
# V8 motoru simülatörünü tek dosya HTML olarak derle:
node skills/teardown/sims/build.mjs v8-live
# Çıktı: teardown-out/dist/v8-live.html

# Tüm örnekleri derle:
node skills/teardown/sims/build.mjs
```

---

## 4. Antigravity ile Kullanım

Antigravity, `.agents/skills/teardown/SKILL.md` altındaki beceriyi otomatik olarak tanır.

Doğal dille sormanız yeterlidir:
- *"Teardown kullanarak borulu bir ısı değiştiricinin (shell-and-tube) 3D çalışan simülatörünü oluştur. Şaşırtma levhaları (baffles) ve borulardaki sıcaklık gradyanı interaktif olarak açılabilsin."*
- *"Bir santrifüj pompanın çark ve salyangoz gövdesini gösteren parçalarına ayrılabilir bir 3D simülatör yap."*
- *"Bize mekanik bir saatin maşa ve balans çarkını 3D simülatör olarak modelle."*

Antigravity otomatik olarak `skills/teardown/sims/kit/` altyapısını kullanarak mekanizmanın geometrisini, kinematiğini ve kontrol panelini yazar, ardından `node skills/teardown/sims/build.mjs` ile çalıştırılabilir `.html` dosyasını `teardown-out/dist/` klasörüne üretir.

---

## 5. OpenCode ile Kullanım

OpenCode üzerinde iki şekilde tetiklenebilir:

1. **Eğik Çizgi (Slash) Komutu:**
   ```text
   /teardown shell and tube heat exchanger
   /teardown 4 stroke single cylinder engine
   ```
2. **Sohbet İçinde:**
   OpenCode, `skills/teardown/SKILL.md` dosyasını otomatik olarak yetenek listesine ekler. Prompt içinde *"visual explainer", "3d simulator", "cutaway", "exploded view"* veya *"nasıl çalışır 3D göster"* gibi ifadeler geçtiğinde devreye girer.

---

## 6. Bir Makine Nasıl İnşa Edilir? (Mimari Yapı)

Her yeni simülatör 3 klasörden oluşur:
- `<isim>-shared/`: Makinenin Three.js geometrisi (`engine.js`), kinematik matematiği (`kin.js`), ışık/sahne (`stage.js`) ve telemetri paneli (`console.js`).
- `<isim>-live/`: Ziyaretçinin fare ve tuşlarla kullandığı gerçek zamanlı sayfa (`live.js`, `main.js`).
- `<isim>-film/`: Önceden kurgulanmış adımlarla kameranın gezdiği tur senaryosu (`film.js`, `timeline.json`).

Simülasyon motoru `runSim` ile ayağa kalkar:
```javascript
import {runSim} from '../kit/runtime.js';

runSim(DEFAULTS, async ({cfg, canvas}) => {
  // Sahne ve parçalar oluşturulur
  return {
    render(t) {
      // t zamanına göre sahne güncellenir
      return {};
    },
    resize() {}
  };
});
```

---

## 7. Dosya Konumları Özeti

- **Antigravity Beceri Yolu**: [`.agents/skills/teardown/SKILL.md`](.agents/skills/teardown/SKILL.md)
- **OpenCode Beceri Yolu**: [`skills/teardown/SKILL.md`](skills/teardown/SKILL.md)
- **OpenCode Komut Yolu**: [`.opencode/command/teardown.md`](.opencode/command/teardown.md)
- **Çalışma Kiti**: `skills/teardown/sims/kit/`
- **Hazır Örnekler**: `skills/teardown/sims/v8-*`, `cessna-*`, `strandbeest-*`
- **Derleme Çıktıları**: `./teardown-out/dist/`
