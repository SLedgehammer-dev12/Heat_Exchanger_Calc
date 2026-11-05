# Ponytail: Lazy Senior Dev Mode Rehberi (OpenCode & Antigravity)

Bu rehber, [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) reposundaki **ajanların (agents)** ve **becerilerin (skills)** bu projeye (`Heat_Exchanger_Calc`) nasıl entegre edildiğini; hem **OpenCode** hem de **Google Antigravity** ile en yüksek verimle nasıl kullanılacağını açıklar.

---

## 1. Ponytail Felsefesi

> *"En iyi kod, hiç yazılmamış koddur. Bir kıdemli geliştirici gibi düşün: en az yeni kodla tüm sorunu çöz, gereksiz soyutlamaları ve spekülatif geleceğe yatırım sanılan fazlalıkları (YAGNI) çöpe at."*

- **Gereksiz kod yazmama (YAGNI)**: İstenmeyen özellikleri, yapılandırma parametrelerini ve esneklik katmanlarını atla.
- **Önce Standart Kütüphane / Projedeki Kod**: Yeni bağımlılık ekleme, projenin mevcut fonksiyonlarını ve standart kütüphanesini kullan.
- **Kısa ve net iletişim**: Yanıtın sonuna her zaman neyin atlandığı / kontrol edilmediği ve olası riskler 1-2 satırda eklenir.
- **Yüksek test güvencesi**: Gereksiz kod yazılmaz ama kritik iş mantığı (dallanma, döngü, matematik modelleri, güvenlik) mutlaka doğrulanır.
- **Borç takibi**: Bilinçli kısayollar `shortcut: <sınır>, <ne zaman güncellenmeli>` formatında etiketlenir.

---

## 2. Sunulan Ajanlar (Personalar / Subagents)

Projede hem OpenCode hem de Antigravity tarafından doğrudan tanınan 3 uzman ajan tanımlanmıştır:

| Ajan (Persona) | Görev ve Odak Alanı | Çalışma Modu / Yetki |
| :--- | :--- | :--- |
| **`ponytail`** | **Lazy Senior Developer**: Problemleri en küçük çalışan farkla çözer, YAGNI uygular, stdlib önceler, atlanan noktaları ve riskleri açıklar. | Birincil (Primary) & Eş Programcı |
| **`ponytail-reviewer`** | **Senior Code Reviewer**: Değişiklikleri gecenin bir yarısı sistem çöktüğünde uyanacak kıdemli mühendis titizliğiyle inceler (Doğruluk $\rightarrow$ Güvenlik $\rightarrow$ Yük/Concurrency $\rightarrow$ Testler $\rightarrow$ Hız $\rightarrow$ Sadelik). | Salt Okunur Alt Ajan (Subagent) |
| **`ponytail-auditor`** | **Senior Repository Auditor**: Tüm mimariyi, ölü kodları, gereksiz bağımlılıkları, ölçekleme darboğazlarını ve gereksiz soyutlamaları denetler. | Salt Okunur Alt Ajan (Subagent) |

---

## 3. Sunulan Beceriler (Skills) ve Eğik Çizgi Komutları

| Beceri / Komut | Tetikleyici | Ne Yapar? |
| :--- | :--- | :--- |
| **`ponytail`** | `/ponytail [lite\|full\|ultra\|off]` | Ponytail yoğunluk seviyesini değiştirir. Oturum boyunca kalıcıdır. |
| **`ponytail-review`** | `/ponytail-review [hedef]` | Mevcut git farkını, belirtilen dalı veya PR'ı 4 parçalı somut maddelerle inceler. Kod değiştirmez. |
| **`ponytail-audit`** | `/ponytail-audit [kapsam]` | Tüm depoyu veya modülü tarar; en fazla 20 somut maddeyle şişkinlik ve risk raporu üretir. |
| **`ponytail-debt`** | `/ponytail-debt` | Kod tabanındaki `shortcut:` etiketlerini tarayarak teknik borç defteri çıkarır. |
| **`ponytail-gain`** | `/ponytail-gain` | Ponytail benchmark tasarruf metriklerini (daha az kod, daha az maliyet, daha yüksek test oranı) gösterir. |
| **`ponytail-help`** | `/ponytail-help` | Hızlı referans ve komut kartını gösterir. |

---

## 4. OpenCode ile Verimli Kullanım

OpenCode, projedeki `.opencode/` ve `opencode.json` konfigürasyonunu doğrudan tanır.

### A. Ajan Olarak Çalıştırma

1. **Varsayılan Birincil Ajan:**
   ```bash
   opencode --agent ponytail
   ```
   Tüm oturumu Ponytail zihniyetiyle (minimum kod, YAGNI, net risk bildirimi) başlatır.

2. **Alt Ajan (Subagent) Olarak Çağırma:**
   OpenCode içinde `@` ile uzman ajanları çağırabilirsiniz:
   - `@ponytail-reviewer staged değişiklikleri ve hesaplama mantığını incele`
   - `@ponytail-auditor heat_exchanger.py ve orc modüllerindeki ölü kodları ve şişkinlikleri denetle`

### B. Eğik Çizgi Komutları (Slash Commands)

OpenCode komut satırında doğrudan çalıştırılabilir:
- `/ponytail full` (veya `lite`, `ultra`, `off`)
- `/ponytail-review` (veya `/ponytail-review main...HEAD`)
- `/ponytail-audit`
- `/ponytail-debt`

### C. Yapılandırma (`opencode.json`)
OpenCode çalışma zamanı eklentisi (`.opencode/plugins/ponytail.mjs`), her dönüşte sistem istemine (system prompt) aktif seviyenin kurallarını otomatik olarak enjekte eder.

---

## 5. Google Antigravity ile Verimli Kullanım

Antigravity, proje hiyerarşisindeki kuralları, becerileri ve ajanları otomatik olarak keşfeder ve bağlar.

### A. Always-On Kurallar (Her Zaman Aktif)
- [`AGENTS.md`](AGENTS.md): Antigravity her oturumda bu dosyayı proje kuralları olarak doğrudan sistem istemine alır.
- [`.agents/rules/ponytail.md`](.agents/rules/ponytail.md): Proje kuralı olarak devrededir.

### B. Antigravity Ajanları
`.agents/agents/` dizinindeki ajan tanımları sayesinde Antigravity, subagent motoruyla bu personaları başlatabilir:
- Sohbet içerisinde:
  - *"Bu değişikliği ponytail-reviewer personamıza incelet"*
  - *"ponytail-auditor ajanını çalıştırarak fluids_db ve mechanical modüllerini denetle"*
  - *"Ponytail modunda, en az yeni kodla bu özelliği ekle"*

### C. Antigravity Becerileri (Skills)
`.agents/skills/` ve `skills/` dizinlerindeki 6 beceri Antigravity tarafından taranır:
- [`.agents/skills/ponytail/SKILL.md`](.agents/skills/ponytail/SKILL.md)
- [`.agents/skills/ponytail-review/SKILL.md`](.agents/skills/ponytail-review/SKILL.md)
- [`.agents/skills/ponytail-audit/SKILL.md`](.agents/skills/ponytail-audit/SKILL.md)
- [`.agents/skills/ponytail-debt/SKILL.md`](.agents/skills/ponytail-debt/SKILL.md)
- [`.agents/skills/ponytail-gain/SKILL.md`](.agents/skills/ponytail-gain/SKILL.md)
- [`.agents/skills/ponytail-help/SKILL.md`](.agents/skills/ponytail-help/SKILL.md)

---

## 6. Proje Dizin Mimarisi

```text
Heat_Exchanger_Calc/
├── AGENTS.md                          # Antigravity & OpenCode için daima aktif temel kurallar
├── opencode.json                      # OpenCode eklenti ve ajan tanımları
├── PONYTAIL_GUIDE.md                  # Bu rehber
├── commands/                          # Antigravity & CLI komut şablonları (*.toml)
│   ├── ponytail.toml
│   ├── ponytail-audit.toml
│   ├── ponytail-debt.toml
│   ├── ponytail-gain.toml
│   ├── ponytail-help.toml
│   └── ponytail-review.toml
├── .agents/
│   ├── agents/                        # Antigravity uzman ajanları
│   │   ├── ponytail.md                # Lazy senior dev ajan tanımı
│   │   ├── ponytail-reviewer.md       # Kod inceleme uzman ajanı
│   │   └── ponytail-auditor.md        # Mimari denetim uzman ajanı
│   ├── rules/
│   │   └── ponytail.md                # Antigravity çalışma alanı kuralları
│   └── skills/                        # Antigravity çalışma alanı becerileri
│       ├── ponytail/SKILL.md
│       ├── ponytail-review/SKILL.md
│       ├── ponytail-audit/SKILL.md
│       ├── ponytail-debt/SKILL.md
│       ├── ponytail-gain/SKILL.md
│       ├── ponytail-help/SKILL.md
│       ├── repository-indexer/SKILL.md
│       └── teardown/SKILL.md
├── .opencode/
│   ├── agents/                        # OpenCode uzman ajanları
│   │   ├── ponytail.md
│   │   ├── ponytail-reviewer.md
│   │   └── ponytail-auditor.md
│   ├── command/                       # OpenCode eğik çizgi komutları
│   │   ├── ponytail.md
│   │   ├── ponytail-review.md
│   │   ├── ponytail-audit.md
│   │   ├── ponytail-debt.md
│   │   ├── ponytail-gain.md
│   │   ├── ponytail-help.md
│   │   └── teardown.md
│   └── plugins/                       # OpenCode eklenti çalışma zamanı (v1 & v2 uyumlu)
│       ├── index.js
│       ├── ponytail.mjs
│       └── ponytail-frontmatter.cjs
├── hooks/                             # Eklenti ortak çalışma zamanı ve subagent kancaları
│   ├── band/                          # Tasarruf panosu arayüzü
│   ├── ponytail-instructions.js       # Dinamik kural derleyici
│   ├── ponytail-config.js             # Seviye ve konfigürasyon yöneticisi
│   ├── ponytail-mode-tracker.js       # Mod değiştirici ve takipçi
│   ├── ponytail-subagent.js           # Subagent bağlam enjektörü
│   ├── ponytail-runtime.js            # Platformlar arası çalışma zamanı
│   └── ponytail-map.js                # Hızlı kod tabanı haritalayıcı
└── skills/                            # Genel / harici uyumlu beceri kök dizini
    ├── ponytail/SKILL.md
    ├── ponytail-review/SKILL.md
    ├── ponytail-audit/SKILL.md
    ├── ponytail-debt/SKILL.md
    ├── ponytail-gain/SKILL.md
    └── ponytail-help/SKILL.md
```

---

## 7. Proje İçi En İyi Pratikler

1. **Önce Mevcut Koda Bak**:
   Yeni bir hesaplama veya yardımcı fonksiyon yazmadan önce [`helpers.py`](helpers.py), [`engineering_utils.py`](engineering_utils.py), [`fluids_db.py`](fluids_db.py) veya [`config.py`](config.py) içindeki fonksiyonları inceleyin ve yeniden kullanın.
2. **Kısa Diff = Güvenli Kod**:
   En iyi kod, yazılmayan koddur. Az satırlı değişiklikler daha kolay gözden geçirilir ve hata payını azaltır.
3. **Kritik Mantık İçin Test Yaz**:
   Hesaplama formülleri, yeni termodinamik döngüler veya sınır durumlar için [`test_changes.py`](test_changes.py) veya ilgili test dosyasına odaklı bir test ekleyin.
4. **Bilinçli Kısayol Bırak**:
   Gerektiğinde bilinen bir kısıtlama içeren kısayol kullanıyorsanız şu formatta not bırakın:
   ```python
   # shortcut: <limit>, <ne zaman güncellenmeli>
   ```
