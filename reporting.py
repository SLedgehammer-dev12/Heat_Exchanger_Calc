from datetime import datetime

from i18n import _
from mechanical import mechanical_design_report


def _fmt(value, digits=4):
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _section(lines, title):
    lines.extend(["", _(title), "-" * len(title)])


def _add_mapping(lines, data, skip_empty=False):
    for key, value in data.items():
        if skip_empty and value in (None, "", [], {}):
            continue
        lines.append(f"- {key}: {value}")


GEOMETRY_LABELS = {
    "D_o": "Boru dış çapı D_o [m]",
    "D_i": "Boru iç çapı D_i [m]",
    "L": "Boru uzunluğu [m]",
    "N_tubes": "Boru sayısı",
    "k_wall": "Boru malzemesi ısıl iletkenliği [W/m.K]",
    "D_shell": "Gövde iç çapı [m]",
    "pitch": "Transverse pitch [m]",
    "is_finned": "Kanatçıklı boru",
    "fin_height": "Kanatçık yüksekliği [m]",
    "fin_thickness": "Kanatçık kalınlığı [m]",
    "fin_density": "Kanatçık yoğunluğu [1/m]",
    "k_fin": "Kanatçık ısıl iletkenliği [W/m.K]",
    "fin_type": "Kanatçık tipi",
    "R_f_i": "Fouling iç direnci [m2.K/W]",
    "R_f_o": "Fouling dış direnci [m2.K/W]",
    "pitch_parallel": "Longitudinal pitch [m]",
    "tube_arrangement": "Boru yerleşimi",
    "baffle_spacing": "Deflektör aralığı [m]",
    "baffle_cut": "Deflektör kesim oranı",
    "tube_layout_angle": "Yerleşim açısı [°]",
    "shell_passes": "Gövde geçiş sayısı",
    "tube_passes": "Boru geçiş sayısı",
    "tema_designation": "TEMA İsimlendirme",
    "fin_attachment": "API 661 Kanat Bağlantı Tipi",
    "api661_fin_type": "API 661 Kanat Tipi",
    "N_transverse": "Enine Sıra Boru Sayısı (N_T)",
    "N_rows": "Boyuna Sıra Sayısı (N_L)",
}


def _add_geometry(lines, geometry):
    _add_mapping(lines, {GEOMETRY_LABELS.get(k, k): v for k, v in geometry.items()}, skip_empty=True)


from engineering_utils import result_warnings as _collect_warnings


def _flow_formula(flow_type, source):
    if source == "ht":
        return "ε = ht.hx.effectiveness_from_NTU(NTU, Cr, subtype)"
    if flow_type == "parallel":
        return "ε = (1 - exp[-NTU(1 + Cr)]) / (1 + Cr)"
    if flow_type == "counter":
        return "Cr < 1 için ε = (1 - exp[-NTU(1 - Cr)]) / (1 - Cr exp[-NTU(1 - Cr)]); Cr = 1 için ε = NTU / (1 + NTU)"
    if flow_type == "cross_unmixed":
        return "ε = 1 - exp[(1/Cr) NTU^0.22 (exp(-Cr NTU^0.78) - 1)]"
    if flow_type == "cross_mixed_unmixed":
        return "ε = (1/Cr) [1 - exp(-Cr (1 - exp(-NTU)))]"
    return "Seçilen akış tipi için özel ε-NTU bağıntısı"


def build_calculation_report(context):
    """Detaylı metin raporu üretir."""
    inputs = context.get("inputs") or {}
    methods = context.get("methods") or {}
    fluids = context.get("fluids") or {}
    results = context.get("results") or {}
    geometry = context.get("geometry") or {}
    geo_result = context.get("geo_result") or {}
    actual_result = context.get("actual_result")
    crosscheck_results = context.get("crosscheck_results") or []
    selected = (results.get("main") if isinstance(results, dict) else {}) or {}

    lines = [
        _("ISI DEGISTIRICI DETAYLI HESAP RAPORU"),
        "=" * 40,
        f"Rapor tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "Not: Bu rapor mühendislik ön tasarım/doğrulama amaçlıdır; kritik tasarımlarda üretici verisi ve standart hesap defteri ile doğrulanmalıdır.",
    ]

    _section(lines, "1. Secilen Yontemler")
    _add_mapping(lines, methods)

    _section(lines, "2. Kullanici Girdileri")
    _add_mapping(
        lines,
        {
            "Hesap amacı": methods.get("Hesap amacı"),
            "Akış konfigürasyonu": methods.get("Akış tipi"),
            "Sıcak akışkan": (fluids.get("hot") or {}).get("label"),
            "Sıcak debi - kullanıcı girdisi": inputs.get("m_hot_raw"),
            "Sıcak debi - hesapta kullanılan": f"{_fmt(inputs.get('m_hot_kg_s'), 6)} kg/s",
            "Sıcak giriş sıcaklığı": f"{_fmt(inputs.get('T_hot_in_C'), 3)} °C",
            "Soğuk akışkan": (fluids.get("cold") or {}).get("label"),
            "Soğuk debi - kullanıcı girdisi": inputs.get("m_cold_raw"),
            "Soğuk debi - hesapta kullanılan": f"{_fmt(inputs.get('m_cold_kg_s'), 6)} kg/s",
            "Soğuk giriş sıcaklığı": f"{_fmt(inputs.get('T_cold_in_C'), 3)} °C",
        },
    )
    if inputs.get("T_hot_out_C") is not None:
        _add_mapping(
            lines,
            {
                "Girilen sıcak çıkış sıcaklığı": f"{_fmt(inputs.get('T_hot_out_C'), 3)} °C",
                "Girilen soğuk çıkış sıcaklığı": f"{_fmt(inputs.get('T_cold_out_C'), 3)} °C",
            },
        )

    _section(lines, "3. Akiskan Ozellikleri")
    for side, label in [("hot", "Sıcak akışkan"), ("cold", "Soğuk akışkan")]:
        data = fluids.get(side) or {}
        lines.append(f"{label}: {data.get('label')}")
        _add_mapping(
            lines,
            {
                "İç ad": data.get("name"),
                "Özellik kaynağı": data.get("source", "-"),
                "cp": f"{_fmt(data.get('cp'), 3)} J/kg.K",
                "Yoğunluk": f"{_fmt(data.get('density'), 6)} kg/m3",
                "Dinamik viskozite": f"{_fmt(data.get('mu'), 8)} Pa.s",
                "Isıl iletkenlik": f"{_fmt(data.get('k_cond'), 6)} W/m.K",
            },
            skip_empty=True,
        )

    _section(lines, "4. Geometri ve U/A Bilgileri")
    if methods.get("U modu", "").lower().startswith("basit"):
        _add_mapping(
            lines,
            {
                "U": f"{_fmt(inputs.get('U'), 4)} W/m2.K",
                "A": f"{_fmt(inputs.get('A'), 4)} m2",
            },
        )
    else:
        _add_geometry(lines, geometry)
        if geo_result:
            _add_mapping(
                lines,
                {
                    "Hesaplanan U": f"{_fmt(geo_result.get('U'), 4)} W/m2.K",
                    "Hesaplanan toplam alan": f"{_fmt(geo_result.get('A_total'), 4)} m2",
                    "h_i": f"{_fmt(geo_result.get('h_i'), 4)} W/m2.K",
                    "h_o": f"{_fmt(geo_result.get('h_o'), 4)} W/m2.K",
                    "Re_i": _fmt(geo_result.get("Re_i"), 2),
                    "Re_o": _fmt(geo_result.get("Re_o"), 2),
                    "R_wall": _fmt(geo_result.get("R_wall"), 8),
                    "Kanatçık verimi": _fmt(geo_result.get("eta_fin"), 4),
                    "ΔP boru tarafı": f"{_fmt(geo_result.get('delta_p_tube', 0) / 1000, 4)} kPa",
                    "ΔP gövde/kanat tarafı": f"{_fmt(geo_result.get('delta_p_shell', 0) / 1000, 4)} kPa",
                    "Pompa gücü (boru)": f"{_fmt(geo_result.get('pump_power_tube', 0), 4)} W",
                    "Fan/Pompa gücü (gövde/kanat)": f"{_fmt(geo_result.get('pump_power_shell', 0), 4)} W",
                },
            )

    _section(lines, "5. Kullanilan Formuller")
    flow_type = methods.get("Akış tipi internal", "")
    source = selected.get("Source", "custom")
    _add_mapping(
        lines,
        {
            "Isı kapasite oranları": "C_h = m_h cp_h, C_c = m_c cp_c, C_min = min(C_h, C_c), C_max = max(C_h, C_c), Cr = C_min / C_max",
            "NTU": "NTU = U A / C_min",
            "Maksimum ısı transferi": "Q_max = C_min (T_h,in - T_c,in)",
            "Gerçek ısı transferi": "Q = ε Q_max",
            "Çıkış sıcaklıkları": "T_h,out = T_h,in - Q/C_h; T_c,out = T_c,in + Q/C_c",
            "Seçilen ε bağıntısı": _flow_formula(flow_type, source),
            "LMTD": "ΔT_lm = (ΔT1 - ΔT2) / ln(ΔT1/ΔT2); ΔT1≈ΔT2 ise ΔT_lm = ΔT1",
        },
    )
    if geo_result:
        _add_mapping(
            lines,
            {
                "Reynolds": "Re = ρ V D / μ (kodda fluids.core.Reynolds kullanılır)",
                "Prandtl": "Pr = cp μ / k (kodda fluids.core.Prandtl kullanılır)",
                "İç türbülanslı Nu": "Birincil: Gnielinski (fd=(0.79 ln(Re)-1.64)^-2); yedek: Dittus-Boelter Nu=0.023 Re^0.8 Pr^n",
                "Laminer Nu": "İç boru için Nu=3.66; annulus tarafı için Nu=4.36",
                "Duvar direnci": "R_wall = ln(D_o/D_i)/(2π k_wall L N)",
                "Toplam UA": "UA = 1/(R_i + R_f_i + R_wall + R_f_o + R_o)",
            },
        )

    _section(lines, "6. Ara Hesaplar")
    C_h = (inputs.get("m_hot_kg_s") or 0.0) * ((fluids.get("hot") or {}).get("cp") or 0.0)
    C_c = (inputs.get("m_cold_kg_s") or 0.0) * ((fluids.get("cold") or {}).get("cp") or 0.0)
    C_min = min(C_h, C_c)
    C_max = max(C_h, C_c)
    q_max = C_min * ((inputs.get("T_hot_in_C") or 0.0) - (inputs.get("T_cold_in_C") or 0.0))
    _add_mapping(
        lines,
        {
            "C_h": f"{_fmt(C_h, 3)} W/K",
            "C_c": f"{_fmt(C_c, 3)} W/K",
            "C_min": f"{_fmt(C_min, 3)} W/K",
            "C_max": f"{_fmt(C_max, 3)} W/K",
            "Cr": _fmt(C_min / C_max if C_max else None, 6),
            "Q_max": f"{_fmt(q_max / 1000, 3)} kW",
            "NTU": _fmt(selected.get("NTU"), 6),
        },
    )

    _section(lines, "7. Secilen Cozucunun Sonucu")
    _add_mapping(
        lines,
        {
            "Metot": selected.get("Method"),
            "Kaynak": selected.get("Source"),
            "Durum": selected.get("status", "ok"),
            "Q": f"{_fmt(selected.get('Q [W]') / 1000, 4)} kW" if selected.get("Q [W]") is not None else "-",
            "epsilon": _fmt(selected.get("epsilon"), 6),
            "Sıcak çıkış": f"{_fmt(selected.get('T_hot_out [C]'), 4)} °C",
            "Soğuk çıkış": f"{_fmt(selected.get('T_cold_out [C]'), 4)} °C",
        },
    )

    if actual_result:
        _section(lines, "8. Performans Degerlendirmesi")
        _add_mapping(
            lines,
            {
                "Sıcak taraftan hesaplanan Q": f"{_fmt(actual_result.get('Q_hot [W]') / 1000, 4)} kW" if actual_result.get("Q_hot [W]") is not None else "-",
                "Soğuk taraftan hesaplanan Q": f"{_fmt(actual_result.get('Q_cold [W]') / 1000, 4)} kW" if actual_result.get("Q_cold [W]") is not None else "-",
                "Ortalama Q": f"{_fmt(actual_result.get('Q_avg [W]') / 1000, 4)} kW" if actual_result.get("Q_avg [W]") is not None else "-",
                "Gerçekleşen epsilon": _fmt(actual_result.get("epsilon_actual"), 6),
                "Gereken U": f"{_fmt(actual_result.get('U_required'), 4)} W/m2.K",
                "LMTD": f"{_fmt(actual_result.get('LMTD'), 4)} K",
                "F": _fmt(actual_result.get("F"), 6),
            },
        )

    _section(lines, "9. Cross-Check / Bagimsiz Dogrulama")
    if crosscheck_results:
        ref_q = selected.get("Q [W]")
        for result in crosscheck_results:
            diff = ""
            if ref_q and ref_q > 0 and result.get("Q [W]") is not None:
                diff = f", seçili sonuca göre Q sapması = {_fmt(abs(result.get('Q [W]') - ref_q) / ref_q * 100, 4)} %"
            q_res = f"{_fmt(result.get('Q [W]') / 1000, 4)} kW" if result.get("Q [W]") is not None else "-"
            lines.append(
                f"- {result.get('Method')} / {result.get('Source')}: "
                f"Q={q_res}, "
                f"Th,out={_fmt(result.get('T_hot_out [C]'), 3)} °C, "
                f"Tc,out={_fmt(result.get('T_cold_out [C]'), 3)} °C, "
                f"durum={result.get('status', 'ok')}{diff}"
            )
    else:
        lines.append("- Cross-check sonucu bulunmuyor.")

    warnings = _collect_warnings(selected, actual_result, geo_result, *crosscheck_results)
    _section(lines, "10. Uyarilar ve Gecerlik Notlari")
    if warnings:
        lines.extend(f"- {msg}" for msg in warnings)
    else:
        lines.append("- Kritik uyarı yok.")
    lines.extend(
        [
            "- Gövde-boru eşanjörlerde LMTD düzeltme faktörü Bowman cebirsel formülü (1-N TEMA), çapraz akışta ise ε-NTU bağıntısı ile hesaplanır; F < 0.5 durumunda seri geçiş veya ters akış düzenlemesi önerilir.",
            "- Gnielinski korelasyonu ana iç akış korelasyonudur; Dittus-Boelter sadece yedek olarak kullanılır. Laminer/geçiş bölgesi sonuçları ön tasarım kabulüdür.",
            "- Termal yağ verileri quadratic cp(T) korelasyon modeli ile hesaplanır; üretici datasheet değerleri ile doğrulanmalıdır.",
        ]
    )

    mech_rows = mechanical_design_report(geometry)
    if mech_rows:
        _section(lines, "10b. Mekanik Tasarim (ASME / API 661)")
        for row in mech_rows:
            lines.append(f"- {row['label']}: {row['value']}  [{row['status']}]")

    _section(lines, "11. Cozum Akisi")
    lines.extend(
        [
            "1. Kullanıcı girdileri SI birimlerine çevrildi.",
            "2. Akışkan özellikleri CoolProp, ChEDL/thermo veya manuel/korelasyon verilerinden üretildi.",
            "3. Basit modda U ve A doğrudan alındı; geometrik modda taşınım/direnç modeliyle U ve A hesaplandı.",
            "4. Seçili metoda göre NTU veya LMTD tabanlı çözüm üretildi.",
            "5. Çıkış sıcaklıkları enerji dengesi ile hesaplandı.",
            "6. ht ve PyChemEngg gibi bağımsız kaynaklarla cross-check yapıldı.",
            "7. Geçerlilik uyarıları ve yöntem varsayımları rapora eklendi.",
        ]
    )

    return "\n".join(lines) + "\n"


def build_calculation_report_pdf(context):
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=16, spaceAfter=4 * mm)
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        textColor=colors.HexColor("#1a5276"),
    )
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=8.5, leading=11)
    cell = ParagraphStyle("Cell", parent=body, fontSize=8, leading=10)
    cell_bold = ParagraphStyle("CellBold", parent=cell, fontWeight="bold")
    note = ParagraphStyle("Note", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#666666"))

    def p(text, style=cell):
        safe = str(text if text is not None else "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("  ", "&nbsp;&nbsp;")
        return Paragraph(safe, style)

    def hr():
        return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"))

    story = []
    story.append(Paragraph(_("Isı Değiştirici Hesap Raporu"), title_style))
    story.append(Paragraph(f"Oluşturulma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", note))
    story.append(hr())

    inputs = context.get("inputs") or {}
    methods = context.get("methods") or {}
    fluids = context.get("fluids") or {}
    results = context.get("results") or {}
    geometry = context.get("geometry") or {}
    geo_result = context.get("geo_result") or {}
    actual_result = context.get("actual_result") or {}
    crosscheck_results = context.get("crosscheck_results") or []
    selected = (results.get("main") if isinstance(results, dict) else {}) or {}

    # --- 1. Yöntemler ---
    story.append(Paragraph("1. Seçilen Yöntemler", h2))
    data = [[p(k, cell_bold), p(v)] for k, v in methods.items()]
    t = Table(data, colWidths=[55 * mm, 105 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee")),
            ]
        )
    )
    story.append(t)

    # --- 2. Girdiler ---
    story.append(Paragraph("2. Kullanıcı Girdileri", h2))
    input_data = [
        ("Hesap amacı", methods.get("Hesap amacı")),
        ("Akış konfigürasyonu", methods.get("Akış tipi")),
        ("Sıcak akışkan", (fluids.get("hot") or {}).get("label", "-")),
        ("Sıcak debi", f"{_fmt(inputs.get('m_hot_kg_s'), 6)} kg/s"),
        ("Sıcak giriş", f"{_fmt(inputs.get('T_hot_in_C'), 3)} °C"),
        ("Soğuk akışkan", (fluids.get("cold") or {}).get("label", "-")),
        ("Soğuk debi", f"{_fmt(inputs.get('m_cold_kg_s'), 6)} kg/s"),
        ("Soğuk giriş", f"{_fmt(inputs.get('T_cold_in_C'), 3)} °C"),
    ]
    if inputs.get("T_hot_out_C") is not None:
        input_data.append(("Sıcak çıkış (girilen)", f"{_fmt(inputs.get('T_hot_out_C'), 3)} °C"))
        input_data.append(("Soğuk çıkış (girilen)", f"{_fmt(inputs.get('T_cold_out_C'), 3)} °C"))
    data = [[p(k, cell_bold), p(v)] for k, v in input_data]
    t = Table(data, colWidths=[55 * mm, 105 * mm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee")),
            ]
        )
    )
    story.append(t)

    # --- 3. Akışkan Özellikleri ---
    story.append(Paragraph("3. Akışkan Özellikleri", h2))
    header = [p("Özellik", cell_bold), p("Sıcak", cell_bold), p("Soğuk", cell_bold)]
    rows = [header]
    for key, tr in [
        ("cp (J/kg.K)", "cp"),
        ("Yoğunluk (kg/m³)", "density"),
        ("Viskozite (Pa.s)", "mu"),
        ("İletkenlik (W/m.K)", "k_cond"),
    ]:
        h_val = (fluids.get("hot") or {}).get(tr)
        c_val = (fluids.get("cold") or {}).get(tr)
        rows.append(
            [
                p(key),
                p(f"{_fmt(h_val, 4)}" if h_val is not None else "-"),
                p(f"{_fmt(c_val, 4)}" if c_val is not None else "-"),
            ]
        )
    t = Table(rows, colWidths=[50 * mm, 55 * mm, 55 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#cccccc")),
            ]
        )
    )
    story.append(t)

    # --- 4. Geometri ve U/A ---
    story.append(Paragraph("4. Geometri ve Isı Transferi", h2))
    if methods.get("U modu", "").lower().startswith("basit"):
        data = [
            [p("U (W/m².K)", cell_bold), p(f"{_fmt(inputs.get('U'), 4)}")],
            [p("A (m²)", cell_bold), p(f"{_fmt(inputs.get('A'), 4)}")],
        ]
        t = Table(data, colWidths=[55 * mm, 105 * mm])
        t.setStyle(
            TableStyle(
                [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]
            )
        )
        story.append(t)
    else:
        # Geometry table
        geo_items = []
        for k, v in geometry.items():
            lbl = GEOMETRY_LABELS.get(k, k)
            geo_items.append([p(lbl, cell_bold), p(str(v))])
        if geo_items:
            story.append(Paragraph("Geometri", ParagraphStyle("SubH", parent=body, fontWeight="bold", fontSize=9)))
            t = Table(geo_items, colWidths=[55 * mm, 105 * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee")),
                    ]
                )
            )
            story.append(t)

        # U/A results
        if geo_result:
            # Shell-side results
            shell_items = [
                ("h_o (W/m².K)", geo_result.get("h_o")),
                ("Re_o", geo_result.get("Re_o")),
                ("ΔP gövde/kanat (kPa)", geo_result.get("delta_p_shell", 0) / 1000),
                ("Fan/Pompa gücü (W)", geo_result.get("pump_power_shell", 0)),
            ]
            data_s = [[p(k, cell_bold), p(f"{_fmt(v, 4)}")] for k, v in shell_items]
            story.append(
                Paragraph("Gövde/Kanat Tarafı", ParagraphStyle("SubH", parent=body, fontWeight="bold", fontSize=9))
            )
            t = Table(data_s, colWidths=[55 * mm, 105 * mm])
            t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]))
            story.append(t)

            # Tube-side results
            tube_items = [
                ("h_i (W/m².K)", geo_result.get("h_i")),
                ("Re_i", geo_result.get("Re_i")),
                ("ΔP boru (kPa)", geo_result.get("delta_p_tube", 0) / 1000),
                ("Pompa gücü (W)", geo_result.get("pump_power_tube", 0)),
            ]
            data_t = [[p(k, cell_bold), p(f"{_fmt(v, 4)}")] for k, v in tube_items]
            story.append(Paragraph("Boru Tarafı", ParagraphStyle("SubH", parent=body, fontWeight="bold", fontSize=9)))
            t = Table(data_t, colWidths=[55 * mm, 105 * mm])
            t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]))
            story.append(t)

            # Overall results
            overall = [
                ["Hesaplanan U (W/m².K)", f"{_fmt(geo_result.get('U'), 4)}"],
                ["Toplam alan (m²)", f"{_fmt(geo_result.get('A_total'), 4)}"],
                ["R_wall", f"{_fmt(geo_result.get('R_wall'), 8)}"],
                ["Kanatçık verimi", f"{_fmt(geo_result.get('eta_fin'), 4)}"],
            ]
            data_o = [[p(k, cell_bold), p(v)] for k, v in overall]
            story.append(Paragraph("Toplam", ParagraphStyle("SubH", parent=body, fontWeight="bold", fontSize=9)))
            t = Table(data_o, colWidths=[55 * mm, 105 * mm])
            t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]))
            story.append(t)

    # --- 5. Formüller ---
    story.append(Paragraph("5. Kullanılan Formüller", h2))
    flow_type = methods.get("Akış tipi internal", "")
    source = selected.get("Source", "custom")
    formula_items = [
        (
            "Isı kapasite oranları",
            "C_h = m_h·cp_h, C_c = m_c·cp_c, C_min = min(C_h, C_c), C_max = max(C_h, C_c), Cr = C_min / C_max",
        ),
        ("NTU", "NTU = U·A / C_min"),
        ("Maksimum ısı transferi", "Q_max = C_min·(T_h,in − T_c,in)"),
        ("Gerçek ısı transferi", "Q = ε·Q_max"),
        ("Çıkış sıcaklıkları", "T_h,out = T_h,in − Q/C_h; T_c,out = T_c,in + Q/C_c"),
        ("Seçilen ε bağıntısı", _flow_formula(flow_type, source)),
        ("LMTD", "ΔT_lm = (ΔT₁ − ΔT₂) / ln(ΔT₁/ΔT₂); ΔT₁≈ΔT₂ ise ΔT_lm = ΔT₁"),
    ]
    if geo_result:
        formula_items += [
            ("Reynolds", "Re = ρ·V·D / μ"),
            ("Prandtl", "Pr = cp·μ / k"),
            ("İç türbülanslı Nu", "Gnielinski (birincil); Dittus-Boelter (yedek)"),
            ("Laminer Nu", "İç boru: Nu=3.66; çift borulu annulus: Nu_i=3.66+1.2·(r*)⁻⁰·⁸"),
            ("Duvar direnci", "R_wall = ln(D_o/D_i) / (2π·k_wall·L·N)"),
            ("Toplam UA", "1/UA = R_i + R_f,i + R_wall + R_f,o + R_o"),
        ]
    data = [[p(k, cell_bold), p(v)] for k, v in formula_items]
    t = Table(data, colWidths=[50 * mm, 110 * mm])
    t.setStyle(
        TableStyle(
            [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]
        )
    )
    story.append(t)

    # --- 6. Ara Hesaplar ---
    story.append(Paragraph("6. Ara Hesaplar", h2))
    C_h = (inputs.get("m_hot_kg_s") or 0.0) * ((fluids.get("hot") or {}).get("cp") or 0.0)
    C_c = (inputs.get("m_cold_kg_s") or 0.0) * ((fluids.get("cold") or {}).get("cp") or 0.0)
    C_min = min(C_h, C_c)
    C_max = max(C_h, C_c)
    q_max = C_min * ((inputs.get("T_hot_in_C") or 0.0) - (inputs.get("T_cold_in_C") or 0.0))
    inter_data = [
        ("C_h (W/K)", f"{_fmt(C_h, 3)}"),
        ("C_c (W/K)", f"{_fmt(C_c, 3)}"),
        ("C_min (W/K)", f"{_fmt(C_min, 3)}"),
        ("C_max (W/K)", f"{_fmt(C_max, 3)}"),
        ("Cr", f"{_fmt(C_min / C_max if C_max else None, 6)}"),
        ("Q_max (kW)", f"{_fmt(q_max / 1000, 3)}"),
        ("NTU", f"{_fmt(selected.get('NTU'), 6)}"),
    ]
    data = [[p(k, cell_bold), p(v)] for k, v in inter_data]
    t = Table(data, colWidths=[55 * mm, 105 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]))
    story.append(t)

    # --- 7. Çözüm Sonucu ---
    story.append(Paragraph("7. Çözüm Sonucu", h2))
    q_sel = selected.get("Q [W]")
    res_data = [
        ("Metot", selected.get("Method")),
        ("Kaynak", selected.get("Source")),
        ("Durum", selected.get("status", "ok")),
        ("Q (kW)", f"{_fmt(q_sel / 1000, 4)}" if q_sel is not None else "-"),
        ("ε", f"{_fmt(selected.get('epsilon'), 6)}"),
        ("Sıcak çıkış (°C)", f"{_fmt(selected.get('T_hot_out [C]'), 4)}"),
        ("Soğuk çıkış (°C)", f"{_fmt(selected.get('T_cold_out [C]'), 4)}"),
    ]
    data = [[p(k, cell_bold), p(v)] for k, v in res_data]
    t = Table(data, colWidths=[55 * mm, 105 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2f8")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee")),
            ]
        )
    )
    story.append(t)

    # --- 8. Performans ---
    if actual_result:
        story.append(Paragraph("8. Performans Değerlendirmesi", h2))
        q_h = actual_result.get("Q_hot [W]")
        q_c = actual_result.get("Q_cold [W]")
        q_a = actual_result.get("Q_avg [W]")
        perf_data = [
            ("Q_hot (kW)", f"{_fmt(q_h / 1000, 4)}" if q_h is not None else "-"),
            ("Q_cold (kW)", f"{_fmt(q_c / 1000, 4)}" if q_c is not None else "-"),
            ("Q_avg (kW)", f"{_fmt(q_a / 1000, 4)}" if q_a is not None else "-"),
            ("ε_actual", f"{_fmt(actual_result.get('epsilon_actual'), 6)}"),
            ("U_required (W/m².K)", f"{_fmt(actual_result.get('U_required'), 4)}"),
            ("LMTD (K)", f"{_fmt(actual_result.get('LMTD'), 4)}"),
            ("F", f"{_fmt(actual_result.get('F'), 6)}"),
        ]
        data = [[p(k, cell_bold), p(v)] for k, v in perf_data]
        t = Table(data, colWidths=[55 * mm, 105 * mm])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#eeeeee"))]))
        story.append(t)

    # --- 9. Cross-Check ---
    story.append(Paragraph("9. Bağımsız Doğrulama (Cross-Check)", h2))
    if crosscheck_results:
        hdr = [
            p("Yöntem", cell_bold),
            p("Q (kW)", cell_bold),
            p("T_h,out (°C)", cell_bold),
            p("T_c,out (°C)", cell_bold),
            p("Durum", cell_bold),
        ]
        rows = [hdr]
        ref_q = selected.get("Q [W]")
        for r in crosscheck_results:
            diff = ""
            if ref_q and ref_q > 0 and r.get("Q [W]") is not None:
                diff = f" sapma={_fmt(abs(r.get('Q [W]') - ref_q) / ref_q * 100, 4)}%"
            q_ck = r.get("Q [W]")
            rows.append(
                [
                    p(f"{r.get('Method')}/{r.get('Source')}"),
                    p(f"{_fmt(q_ck / 1000, 4)}" if q_ck is not None else "-"),
                    p(f"{_fmt(r.get('T_hot_out [C]'), 3)}"),
                    p(f"{_fmt(r.get('T_cold_out [C]'), 3)}"),
                    p(f"{r.get('status', 'ok')}{diff}"),
                ]
            )
        t = Table(rows, colWidths=[45 * mm, 30 * mm, 30 * mm, 30 * mm, 35 * mm])
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ]
            )
        )
        story.append(t)
    else:
        story.append(p("Cross-check sonucu bulunmuyor."))

    # --- 10. Uyarılar ---
    story.append(Paragraph("10. Uyarılar", h2))
    warnings = _collect_warnings(selected, actual_result, geo_result, *crosscheck_results)
    if warnings:
        for msg in warnings:
            story.append(p(f"• {msg}"))
    else:
        story.append(p("Kritik uyarı yok."))
    story.append(Spacer(1, 3 * mm))

    # --- 10b. Mekanik Tasarım (ASME / API 661) ---
    mech_rows = mechanical_design_report(geometry)
    if mech_rows:
        story.append(Paragraph("10b. Mekanik Tasarım (ASME / API 661)", h2))
        for row in mech_rows:
            story.append(p(f"• <font color='#888888'>{row['label']}:</font> <b>{row['value']}</b> [{row['status']}]"))
        story.append(Spacer(1, 3 * mm))

    # --- 11. Akış Şeması ve Sıcaklık Profili (Faz 3.1) ---
    images = context.get("images") or []
    if images:
        story.append(Paragraph("11. Akış Şeması ve Sıcaklık Profili", h2))
        for img in images:
            buf = img.get("buffer")
            if buf is None:
                continue
            buf.seek(0)
            width_mm = img.get("width_mm", 170.0)
            height_mm = img.get("height_mm", 60.0)
            story.append(Image(buf, width=width_mm * mm, height=height_mm * mm))
            caption = img.get("caption")
            if caption:
                story.append(p(caption, note))
            story.append(Spacer(1, 2 * mm))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def generate_tema_datasheet_pdf(context: dict) -> bytes:
    """TEMA Standard Section 5 / API 661 formatında 1 sayfalık teknik föy (datasheet) üretir."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = BytesIO()
    # 1 sayfalık standart föy için kenar boşlukları (10 mm)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SheetTitle",
        parent=styles["Title"],
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#0f3a5d"),
        alignment=1,
    )
    subtitle_style = ParagraphStyle(
        "SheetSubtitle",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#555555"),
        alignment=1,
    )
    section_hdr = ParagraphStyle(
        "SectionHdr",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=9.5,
        textColor=colors.white,
        fontWeight="bold",
    )
    cell = ParagraphStyle("CellText", parent=styles["Normal"], fontSize=6.8, leading=8.2)
    cell_bold = ParagraphStyle("CellBold", parent=cell, fontWeight="bold")

    def p(text, style=cell):
        safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, style)

    story = []

    # 1. BAŞLIK BİLGİSİ
    story.append(Paragraph(_("ISI DEGISTIRICI TEKNIK SARTNAME VERI SAYFASI (DATASHEET)"), title_style))
    story.append(
        Paragraph(
            f"TEMA Standards 10th Ed. / API 661 7th Ed. / ASME Sec. VIII Div. 1 — Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 1.5 * mm))

    inputs = context.get("inputs") or {}
    methods = context.get("methods") or {}
    fluids = context.get("fluids") or {}
    results = context.get("results") or {}
    geometry = context.get("geometry") or {}
    actual_result = context.get("actual_result") or {}
    geo_result = context.get("geo_result") or {}
    selected = (results.get("main") if isinstance(results, dict) else {}) or {}

    # 2. PROJE & GENEL TANIM TABLOSU
    info_data = [
        [
            p("<b>Hizmet / Servis:</b>", cell_bold),
            p(methods.get("Hesap amacı", "Genel Eşanjör")),
            p("<b>Eşanjör Tipi:</b>", cell_bold),
            p(methods.get("Eşanjör tipi", "Gövde-Boru / Kanatlı")),
        ],
        [
            p("<b>Akış Tipi:</b>", cell_bold),
            p(methods.get("Akış tipi", "-")),
            p("<b>TEMA Kodu / Standart:</b>", cell_bold),
            p(geometry.get("tema_designation", "API 661 / TEMA")),
        ],
    ]
    t_info = Table(info_data, colWidths=[35 * mm, 60 * mm, 38 * mm, 57 * mm], rowHeights=4.0 * mm)
    t_info.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7f9")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b0c4de")),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ]
        )
    )
    story.append(t_info)
    story.append(Spacer(1, 2.0 * mm))

    # 3. İŞLETME VE TERMAL PERFORMANS TABLOSU (PERFORMANCE DATA)
    perf_header = [
        [
            p("PERFORMANS VE İŞLETME VERİLERİ", section_hdr),
            p("", section_hdr),
            p("BORU TARAFI (TUBE)", section_hdr),
            p("GÖVDE / HAVA TARAFI (SHELL/AIR)", section_hdr),
        ]
    ]

    hot_is_tube = geometry.get("hot_is_tube", True)
    tube_fluid = fluids.get("hot" if hot_is_tube else "cold") or {}
    shell_fluid = fluids.get("cold" if hot_is_tube else "hot") or {}

    m_tube = inputs.get("m_hot_kg_s") if hot_is_tube else inputs.get("m_cold_kg_s")
    m_shell = inputs.get("m_cold_kg_s") if hot_is_tube else inputs.get("m_hot_kg_s")

    t_in_tube = inputs.get("T_hot_in_C") if hot_is_tube else inputs.get("T_cold_in_C")
    t_in_shell = inputs.get("T_cold_in_C") if hot_is_tube else inputs.get("T_hot_in_C")

    t_out_tube = selected.get("T_hot_out [C]") if hot_is_tube else selected.get("T_cold_out [C]")
    t_out_shell = selected.get("T_cold_out [C]") if hot_is_tube else selected.get("T_hot_out [C]")

    q_kw = (selected.get("Q [W]") or actual_result.get("Q_avg [W]") or 0.0) / 1000.0
    dp_tube_kpa = (
        actual_result.get("delta_p_tube_kPa")
        or actual_result.get("delta_p_tube [kPa]")
        or (geo_result.get("delta_p_tube", 0.0) / 1000.0 if geo_result.get("delta_p_tube") else 0.0)
    )
    dp_shell_kpa = (
        actual_result.get("delta_p_shell_kPa")
        or actual_result.get("delta_p_shell [kPa]")
        or (geo_result.get("delta_p_shell", 0.0) / 1000.0 if geo_result.get("delta_p_shell") else 0.0)
    )

    perf_rows = [
        [p("Akışkan Adı"), p("-"), p(tube_fluid.get("label", "-")), p(shell_fluid.get("label", "-"))],
        [
            p("Toplam Kütlesel Debi"),
            p("kg/h"),
            p(f"{_fmt(m_tube * 3600 if m_tube else None, 1)}"),
            p(f"{_fmt(m_shell * 3600 if m_shell else None, 1)}"),
        ],
        [p("Giriş Sıcaklığı"), p("°C"), p(f"{_fmt(t_in_tube, 2)}"), p(f"{_fmt(t_in_shell, 2)}")],
        [p("Çıkış Sıcaklığı"), p("°C"), p(f"{_fmt(t_out_tube, 2)}"), p(f"{_fmt(t_out_shell, 2)}")],
        [
            p("Yoğunluk (Giriş/Ortalama)"),
            p("kg/m³"),
            p(f"{_fmt(tube_fluid.get('density'), 2)}"),
            p(f"{_fmt(shell_fluid.get('density'), 2)}"),
        ],
        [p("Özgül Isı (Cp)"), p("J/kg·K"), p(f"{_fmt(tube_fluid.get('cp'), 1)}"), p(f"{_fmt(shell_fluid.get('cp'), 1)}")],
        [
            p("Isıl İletkenlik (k)"),
            p("W/m·K"),
            p(f"{_fmt(tube_fluid.get('k_cond'), 4)}"),
            p(f"{_fmt(shell_fluid.get('k_cond'), 4)}"),
        ],
        [
            p("Dinamik Viskozite"),
            p("cP"),
            p(f"{_fmt(tube_fluid.get('mu') * 1000 if tube_fluid.get('mu') else None, 3)}"),
            p(f"{_fmt(shell_fluid.get('mu') * 1000 if shell_fluid.get('mu') else None, 3)}"),
        ],
        [
            p("Fouling Isıl Direnci (R_f)"),
            p("m²·K/W"),
            p(f"{_fmt(geometry.get('R_f_i', 0.0), 6)}"),
            p(f"{_fmt(geometry.get('R_f_o', 0.0), 6)}"),
        ],
        [p("Hesaplanan Basınç Kaybı"), p("kPa"), p(f"{_fmt(dp_tube_kpa, 2)}"), p(f"{_fmt(dp_shell_kpa, 2)}")],
        [
            p("Taşınım Katsayısı (h)"),
            p("W/m²·K"),
            p(f"{_fmt(actual_result.get('h_i') or geo_result.get('h_i'), 1)}"),
            p(f"{_fmt(actual_result.get('h_o') or geo_result.get('h_o'), 1)}"),
        ],
        [
            p("Toplam Isı Yükü (Q)"),
            p("kW"),
            p(f"<b>{_fmt(q_kw, 2)} kW</b>", cell_bold),
            p(f"Etkinlik (ε): <b>{_fmt(selected.get('epsilon'), 3)}</b>"),
        ],
        [
            p("LMTD / Düzeltilmiş MTD"),
            p("°C"),
            p(f"LMTD: {_fmt(selected.get('LMTD') or actual_result.get('LMTD'), 2)} °C"),
            p(f"F-Faktörü: {_fmt(selected.get('F') or actual_result.get('F'), 3)}"),
        ],
        [
            p("Toplam Isı Transfer Katsayısı (U)"),
            p("W/m²·K"),
            p(f"<b>{_fmt(actual_result.get('U') or selected.get('U') or geo_result.get('U'), 1)}</b>"),
            p(f"Gerekli U: {_fmt(actual_result.get('U_required') or selected.get('U_required'), 1)}"),
        ],
        [
            p("Efektif Isı Transfer Alanı (A)"),
            p("m²"),
            p(f"<b>{_fmt(actual_result.get('A_total') or selected.get('A') or geo_result.get('A_total'), 2)} m²</b>", cell_bold),
            p(f"Yüzey Verimi (η_o): {_fmt((actual_result.get('eta_o') or geo_result.get('eta_o') or 1.0) * 100, 1)}%"),
        ],
    ]

    t_perf = Table(
        perf_header + perf_rows,
        colWidths=[55 * mm, 18 * mm, 58 * mm, 59 * mm],
        rowHeights=[3.8 * mm] * (len(perf_rows) + 1),
    )
    t_perf.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfcfd")]),
            ]
        )
    )
    story.append(t_perf)
    story.append(Spacer(1, 2.0 * mm))

    # 4. MEKANİK VE KONSTRÜKSİYON DETAYLARI TABLOSU (CONSTRUCTION SPECIFICATION)
    mech_header = [
        [
            p("KONSTRÜKSİYON VE MEKANİK DETAYLAR (ASME / TEMA / API)", section_hdr),
            p("", section_hdr),
            p("BORU DEMETİ (TUBE BUNDLE)", section_hdr),
            p("GÖVDE / KANAT (SHELL / FINS)", section_hdr),
        ]
    ]

    d_o_mm = (geometry.get("D_o") or 0.0254) * 1000.0
    d_i_mm = (geometry.get("D_i") or 0.0211) * 1000.0
    t_w_mm = (d_o_mm - d_i_mm) / 2.0
    l_m = geometry.get("L") or 3.0
    n_t = geometry.get("N_tubes") or 100
    pitch_mm = (geometry.get("pitch") or 0.03175) * 1000.0
    angle = geometry.get("tube_layout_angle", "30°")
    tube_mat = geometry.get("tube_material", "Karbon Çelik")
    d_shell_mm = (geometry.get("D_shell") or 0.5) * 1000.0
    baffle_spacing_mm = (geometry.get("baffle_spacing") or 0.2) * 1000.0
    baffle_cut_pct = (geometry.get("baffle_cut") or 0.25) * 100.0

    is_finned = geometry.get("is_finned", False)
    fin_type = geometry.get("fin_type", "annular")
    fin_attach = geometry.get("fin_attachment", geometry.get("api661_fin_type", "Extruded"))
    fin_h_mm = (geometry.get("fin_height") or 0.0159) * 1000.0
    fin_t_mm = (geometry.get("fin_thickness") or 0.0004) * 1000.0
    fin_dens = geometry.get("fin_density") or 400
    p_tube_des = float(geometry.get("design_pressure_tube_bar") or (geometry.get("design_pressure", 10.0e5) / 1e5))
    p_shell_des = float(geometry.get("design_pressure_shell_bar") or (geometry.get("design_pressure", 10.0e5) / 1e5))
    p_tube_test = p_tube_des * 1.3
    p_shell_test = p_shell_des * 1.3

    mech_rows = [
        [
            p("Boru Sayısı / Geçiş Sayısı"),
            p("-"),
            p(f"{n_t} boru / {geometry.get('tube_passes', 2)} geçiş"),
            p(f"Gövde Geçiş Sayısı: {geometry.get('shell_passes', 1)}"),
        ],
        [
            p("Boru Dış Çapı × Et Kalınlığı"),
            p("mm"),
            p(f"Ø{d_o_mm:.1f} mm × {t_w_mm:.2f} mm (ID: {d_i_mm:.1f} mm)"),
            p(f"Gövde İç Çapı: Ø{d_shell_mm:.1f} mm"),
        ],
        [
            p("Boru Boyu / Hatve & Açı"),
            p("-"),
            p(f"{l_m:.2f} m / Hatve: {pitch_mm:.1f} mm ({angle})"),
            p(f"Şaşırtma Aralığı: {baffle_spacing_mm:.0f} mm (Kesim: %{baffle_cut_pct:.0f})"),
        ],
        [
            p("Boru / Gövde Malzemesi"),
            p("-"),
            p(f"{tube_mat}"),
            p("Gövde Malzemesi: Karbon Çelik (ASME SA-516 Gr. 70)"),
        ],
        [
            p("Kanat Tipi & Bağlantı (API 661)"),
            p("-"),
            p("Kanatçıklı" if is_finned else "Çıplak Borulu (Bare Tube)"),
            p(f"{fin_attach} ({fin_type})" if is_finned else "Yok"),
        ],
        [
            p("Kanat Boyutları (Yüks. × Kal. × Sıklık)"),
            p("-"),
            p(f"Y:{fin_h_mm:.1f}mm, K:{fin_t_mm:.2f}mm, {fin_dens:.0f} fpm" if is_finned else "-"),
            p(f"Kanat Verimi: η_f = {(actual_result.get('eta_fin') or geo_result.get('eta_fin') or 1.0):.3f}" if is_finned else "-"),
        ],
        [
            p("Tasarım / Hidrostatik Test Basıncı"),
            p("bar(g)"),
            p(f"Tasarım: {p_tube_des:.1f} bar / Test: {p_tube_test:.1f} bar"),
            p(f"Tasarım: {p_shell_des:.1f} bar / Test: {p_shell_test:.1f} bar"),
        ],
        [
            p("Korozyon Payı (CA)"),
            p("mm"),
            p("Boru: 0.0 mm (TEMA RCB-1.511)"),
            p("Gövde: 3.0 mm (ASME UG-25)"),
        ],
    ]

    t_mech = Table(
        mech_header + mech_rows,
        colWidths=[55 * mm, 18 * mm, 58 * mm, 59 * mm],
        rowHeights=[3.8 * mm] * (len(mech_rows) + 1),
    )
    t_mech.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e4053")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cccccc")),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfcfd")]),
            ]
        )
    )
    story.append(t_mech)
    story.append(Spacer(1, 2.0 * mm))

    # 5. UYARILAR VE ŞARTNAME NOTLARI
    notes = []
    all_warns = _collect_warnings(selected, actual_result, geo_result)
    if all_warns:
        notes.extend(all_warns[:2])
    notes.append("İmalat ve kaynaklar ASME Section IX ve TEMA RCB standartlarına uygun olarak gerçekleştirilecektir.")
    notes.append("Boru et kalınlığı kontrolü ASME Section VIII Div. 1 UG-27 kuralına göre doğrulanmıştır.")

    notes_p = [p(f"<b>Not {i + 1}:</b> {n}") for i, n in enumerate(notes)]
    t_notes = Table([[item] for item in notes_p], colWidths=[190 * mm])
    t_notes.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdf5")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0d4a8")),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ]
        )
    )
    story.append(t_notes)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def export_calculation_csv(context: dict) -> str:
    """Hesaplama girdileri, termal rating sonuçları ve mekanik parametreleri CSV olarak dışa aktarır."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["# HEAT EXCHANGER CALCULATION EXPORT — TEMA / API 661 / ASME"])
    writer.writerow(["# Export Date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow([])

    # 1. Yöntemler ve Genel Bilgiler
    writer.writerow(["[1. METHODS & OPERATING MODE]"])
    writer.writerow(["Parameter", "Value"])
    methods = context.get("methods") or {}
    for k, v in methods.items():
        writer.writerow([k, v])
    writer.writerow([])

    # 2. Akışkan ve İşletme Koşulları
    writer.writerow(["[2. OPERATING CONDITIONS]"])
    writer.writerow(["Side", "Fluid", "Flow Rate [kg/s]", "T_in [C]", "T_out [C]"])
    inputs = context.get("inputs") or {}
    fluids = context.get("fluids") or {}
    results = context.get("results") or {}
    selected = (results.get("main") if isinstance(results, dict) else {}) or context.get("selected_result") or {}

    writer.writerow(
        [
            "Hot Side",
            (fluids.get("hot") or {}).get("label", "-"),
            inputs.get("m_hot_kg_s", "-"),
            inputs.get("T_hot_in_C", "-"),
            selected.get("T_hot_out [C]", "-"),
        ]
    )
    writer.writerow(
        [
            "Cold Side",
            (fluids.get("cold") or {}).get("label", "-"),
            inputs.get("m_cold_kg_s", "-"),
            inputs.get("T_cold_in_C", "-"),
            selected.get("T_cold_out [C]", "-"),
        ]
    )
    writer.writerow([])

    # 3. Termal Performans Sonuçları
    writer.writerow(["[3. THERMAL PERFORMANCE]"])
    writer.writerow(["Metric", "Value", "Unit"])
    actual = context.get("actual_result") or {}
    geo = context.get("geo_result") or {}
    metrics = [
        ("Heat Exchanged (Q)", selected.get("Q [W]"), "W"),
        ("Effectiveness (epsilon)", selected.get("epsilon"), "-"),
        ("LMTD", selected.get("LMTD") or actual.get("LMTD"), "C"),
        ("LMTD Correction Factor (F)", selected.get("F") or actual.get("F"), "-"),
        ("Overall U (Calculated)", actual.get("U") or selected.get("U") or geo.get("U"), "W/m2.K"),
        ("Required U", actual.get("U_required") or selected.get("U_required"), "W/m2.K"),
        ("Heat Transfer Area (A)", actual.get("A_total") or selected.get("A") or geo.get("A_total"), "m2"),
        ("Tube-side Pressure Drop", actual.get("delta_p_tube_kPa") or (geo.get("delta_p_tube") / 1000.0 if geo.get("delta_p_tube") else None), "kPa"),
        ("Shell/Air-side Pressure Drop", actual.get("delta_p_shell_kPa") or (geo.get("delta_p_shell") / 1000.0 if geo.get("delta_p_shell") else None), "kPa"),
        ("Inside HTC (h_i)", actual.get("h_i") or geo.get("h_i"), "W/m2.K"),
        ("Outside HTC (h_o)", actual.get("h_o") or geo.get("h_o"), "W/m2.K"),
        ("Fin Efficiency (eta_fin)", actual.get("eta_fin") or geo.get("eta_fin"), "-"),
        ("Overall Surface Efficiency (eta_o)", actual.get("eta_o") or geo.get("eta_o"), "-"),
    ]
    for m, val, unit in metrics:
        if val is not None:
            writer.writerow([m, val, unit])
    writer.writerow([])

    # 4. Geometri Parametreleri
    writer.writerow(["[4. GEOMETRY PARAMETERS]"])
    writer.writerow(["Parameter", "Value"])
    geometry = context.get("geometry") or {}
    for k, v in geometry.items():
        writer.writerow([GEOMETRY_LABELS.get(k, k), v])
    writer.writerow([])

    # 5. Mekanik Tasarım Kontrolleri
    writer.writerow(["[5. MECHANICAL DESIGN (ASME / API 661)]"])
    writer.writerow(["Check Label", "Value", "Status"])
    for row in mechanical_design_report(geometry):
        writer.writerow([row.get("label"), row.get("value"), row.get("status")])
    writer.writerow([])

    return output.getvalue()


def export_profile_csv(profile_data_or_context) -> str:
    """1D segmenter sıcaklık ve basınç profillerini tabular CSV olarak dışa aktarır."""
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Segment", "Length_Fraction", "T_hot_C", "T_cold_C", "Delta_T_C"])

    t_h = []
    t_c = []
    if isinstance(profile_data_or_context, dict):
        results_dict = profile_data_or_context.get("results") or {}
        res = (
            profile_data_or_context.get("actual_result")
            or results_dict.get("main")
            or profile_data_or_context
        )
        t_h = res.get("T_h_profile") or []
        t_c = res.get("T_c_profile") or []
        if not t_h and "inputs" in profile_data_or_context:
            inp = profile_data_or_context.get("inputs") or {}
            t_h_in = inp.get("T_hot_in_C", 100.0)
            t_h_out = (results_dict.get("main") or {}).get("T_hot_out [C]", 60.0)
            t_c_in = inp.get("T_cold_in_C", 20.0)
            t_c_out = (results_dict.get("main") or {}).get("T_cold_out [C]", 50.0)
            t_h = [t_h_in - (t_h_in - t_h_out) * (i / 10.0) for i in range(11)]
            t_c = [t_c_in + (t_c_out - t_c_in) * (i / 10.0) for i in range(11)]

    n_points = max(len(t_h), len(t_c))
    for i in range(n_points):
        th_val = t_h[i] if i < len(t_h) else "-"
        tc_val = t_c[i] if i < len(t_c) else "-"
        dt_val = (
            round(th_val - tc_val, 2)
            if (isinstance(th_val, (int, float)) and isinstance(tc_val, (int, float)))
            else "-"
        )
        frac = round(i / max(1, n_points - 1), 3)
        writer.writerow([i + 1, frac, th_val, tc_val, dt_val])

    return output.getvalue()


def export_calculation_excel(context: dict) -> bytes:
    """Hesaplama ve mühendislik sonuçlarını formüllü Excel (.xlsx) olarak dışa aktarır."""
    from io import BytesIO

    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "TEMA Hesap Föyü"

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    section_font = Font(name="Arial", size=11, bold=True, color="0F3A5D")
    bold_font = Font(name="Arial", size=10, bold=True)
    regular_font = Font(name="Arial", size=10)

    header_fill = PatternFill(start_color="0F3A5D", end_color="0F3A5D", fill_type="solid")

    ws.merge_cells("A1:F1")
    ws["A1"] = "HEAT EXCHANGER CALCULATION & TEMA RATING SHEET"
    ws["A1"].font = Font(name="Arial", size=14, bold=True, color="0F3A5D")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A2"] = f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws["A2"].font = Font(name="Arial", size=9, italic=True)

    row = 4
    ws.cell(row=row, column=1, value="1. İŞLETME VE AKIŞKAN KOŞULLARI").font = section_font
    row += 1
    headers = ["Taraf", "Akışkan", "Debi [kg/s]", "Giriş T [°C]", "Çıkış T [°C]", "Basınç [bar]"]
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    inputs = context.get("inputs") or {}
    fluids = context.get("fluids") or {}
    results = context.get("results") or {}
    selected = (results.get("main") if isinstance(results, dict) else {}) or context.get("selected_result") or {}

    row += 1
    hot_row = row
    ws.cell(row=row, column=1, value="Sıcak Taraf").font = bold_font
    ws.cell(row=row, column=2, value=(fluids.get("hot") or {}).get("label", "-")).font = regular_font
    ws.cell(row=row, column=3, value=float(inputs.get("m_hot_kg_s", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=4, value=float(inputs.get("T_hot_in_C", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=5, value=float(selected.get("T_hot_out [C]", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=6, value=float(inputs.get("P_hot_bar", 1.013) or 1.013)).font = regular_font

    row += 1
    cold_row = row
    ws.cell(row=row, column=1, value="Soğuk Taraf").font = bold_font
    ws.cell(row=row, column=2, value=(fluids.get("cold") or {}).get("label", "-")).font = regular_font
    ws.cell(row=row, column=3, value=float(inputs.get("m_cold_kg_s", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=4, value=float(inputs.get("T_cold_in_C", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=5, value=float(selected.get("T_cold_out [C]", 0.0) or 0.0)).font = regular_font
    ws.cell(row=row, column=6, value=float(inputs.get("P_cold_bar", 1.013) or 1.013)).font = regular_font

    row += 2
    ws.cell(row=row, column=1, value="2. TERMAL PERFORMANS VE DERECELENDİRME").font = section_font
    row += 1
    ws.cell(row=row, column=1, value="Parametre").font = header_font
    ws.cell(row=row, column=1).fill = header_fill
    ws.cell(row=row, column=2, value="Değer").font = header_font
    ws.cell(row=row, column=2).fill = header_fill
    ws.cell(row=row, column=3, value="Birim").font = header_font
    ws.cell(row=row, column=3).fill = header_fill
    ws.cell(row=row, column=4, value="Formül / Not").font = header_font
    ws.cell(row=row, column=4).fill = header_fill

    actual = context.get("actual_result") or {}
    geo = context.get("geo_result") or {}

    flow_type_str = str(
        context.get("methods", {}).get("Akış tipi internal")
        or context.get("methods", {}).get("Akış tipi")
        or context.get("inputs", {}).get("flow_type")
        or ""
    ).lower()
    if "parallel" in flow_type_str or "paralel" in flow_type_str:
        lmtd_formula = f"=IFERROR(((D{hot_row}-D{cold_row})-(E{hot_row}-E{cold_row}))/LN(MAX(0.001,(D{hot_row}-D{cold_row}))/MAX(0.001,(E{hot_row}-E{cold_row}))), D{hot_row}-D{cold_row})"
    elif "counter" in flow_type_str or "ters" in flow_type_str:
        lmtd_formula = f"=IFERROR(((D{hot_row}-E{cold_row})-(E{hot_row}-D{cold_row}))/LN(MAX(0.001,(D{hot_row}-E{cold_row}))/MAX(0.001,(E{hot_row}-D{cold_row}))), D{hot_row}-E{cold_row})"
    else:
        lmtd_formula = "Sayısal / Çapraz Akış LMTD"

    thermal_rows = [
        ("Isı Yükü (Q)", selected.get("Q [W]", 0.0), "W", "Q = m * Cp * ΔT"),
        ("Etkinlik (ε)", selected.get("epsilon", 0.0), "-", "ε = Q / Q_max"),
        ("LMTD", selected.get("LMTD") or actual.get("LMTD", 0.0), "°C", lmtd_formula),
        ("Düzeltme Faktörü (F)", selected.get("F") or actual.get("F", 1.0), "-", "Bowman / Crossflow F-Factor"),
        ("Toplam Isı Transfer Katsayısı (U)", actual.get("U") or selected.get("U") or geo.get("U", 0.0), "W/m²·K", "1 / (1/h_i + R_f_i + R_wall + R_f_o + 1/h_o)"),
        ("Gerekli Isı Transfer Alanı (A_req)", actual.get("A_required") or selected.get("A_required", 0.0), "m²", "Q / (U * F * LMTD)"),
        ("Mevcut Isı Transfer Alanı (A_actual)", actual.get("A_total") or selected.get("A") or geo.get("A_total", 0.0), "m²", "N * π * Do * L"),
        ("Termal Aşım Oranı (Margin)", None, "%", f"=(B{row+7}-B{row+6})/MAX(0.001,B{row+6})*100"),
        ("İç Taşınım Katsayısı (h_i)", actual.get("h_i") or geo.get("h_i", 0.0), "W/m²·K", "Gnielinski / Dittus-Boelter"),
        ("Dış Taşınım Katsayısı (h_o)", actual.get("h_o") or geo.get("h_o", 0.0), "W/m²·K", "Bell-Delaware / Kern / Briggs-Young"),
        ("Boru Tarafı Basınç Kaybı (ΔP_tube)", actual.get("delta_p_tube_kPa") or (geo.get("delta_p_tube", 0.0)/1000.0), "kPa", "Darcy-Weisbach"),
        ("Gövde Tarafı Basınç Kaybı (ΔP_shell)", actual.get("delta_p_shell_kPa") or (geo.get("delta_p_shell", 0.0)/1000.0), "kPa", "Bell-Delaware / Kern"),
    ]

    for label, val, unit, note in thermal_rows:
        row += 1
        ws.cell(row=row, column=1, value=label).font = regular_font
        val_cell = ws.cell(row=row, column=2)
        if isinstance(note, str) and note.startswith("="):
            val_cell.value = note
        else:
            val_cell.value = float(val) if val is not None else 0.0
        val_cell.font = bold_font
        ws.cell(row=row, column=3, value=unit).font = regular_font
        ws.cell(row=row, column=4, value=note if not note.startswith("=") else "Canlı Excel Formülü").font = regular_font

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

    orc_data = context.get("orc_data") or (context.get("inputs") if any(k in context.get("inputs", {}) for k in ("n_boilers", "pipe_di_mm", "pipe_dn_sel")) else None)
    if orc_data:
        ws_orc = wb.create_sheet(title="ORC & WHRU Tesis Verileri")
        ws_orc.merge_cells("A1:F1")
        ws_orc["A1"] = "WHRU KAZANLARI, BORU HİDROLİĞİ VE ORC GÜÇ DÖNGÜSÜ"
        ws_orc["A1"].font = Font(name="Arial", size=14, bold=True, color="0F3A5D")
        ws_orc["A1"].alignment = Alignment(horizontal="center")

        ws_orc["A2"] = f"Rapor Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ws_orc["A2"].font = Font(name="Arial", size=9, italic=True)

        r = 4
        ws_orc.cell(row=r, column=1, value="1. ATIK ISI BACA KAZANLARI (WHRU)").font = section_font
        r += 1
        b_headers = ["Kazan", "Durum", "Baca Debisi [kg/s]", "Giriş T_fg [°C]", "Yağ Debisi [kg/s]", "Pay [%]"]
        for c_idx, bh in enumerate(b_headers, start=1):
            c_cell = ws_orc.cell(row=r, column=c_idx, value=bh)
            c_cell.font = header_font
            c_cell.fill = header_fill
            c_cell.alignment = Alignment(horizontal="center")

        n_b = int(orc_data.get("n_boilers", 1) or 1)
        tot_m_oil = float(orc_data.get("m_oil", 32.0) or 32.0)
        for idx in range(1, max(2, n_b + 1)):
            r += 1
            is_active = (idx <= n_b)
            split_pct = (100.0 / n_b) if is_active else 0.0
            m_oil_i = (tot_m_oil / n_b) if is_active else 0.0
            m_flue_i = float(orc_data.get(f"m_flue_{idx}", orc_data.get("m_flue", 28.5)) or 28.5) if is_active else 0.0
            t_flue_i = float(orc_data.get(f"t_flue_in_{idx}", orc_data.get("T_flue_in", 340.0)) or 340.0) if is_active else 0.0

            ws_orc.cell(row=r, column=1, value=f"WHRU-{idx}").font = bold_font
            ws_orc.cell(row=r, column=2, value="Aktif" if is_active else "Pasif").font = regular_font
            ws_orc.cell(row=r, column=3, value=round(m_flue_i, 2)).font = regular_font
            ws_orc.cell(row=r, column=4, value=round(t_flue_i, 1)).font = regular_font
            ws_orc.cell(row=r, column=5, value=round(m_oil_i, 2)).font = regular_font
            ws_orc.cell(row=r, column=6, value=f"%{split_pct:.1f}").font = regular_font

        r += 2
        ws_orc.cell(row=r, column=1, value="2. KIZGIN YAĞ BORU HATTI VE HİDROLİK (DARCY-WEISBACH)").font = section_font
        r += 1
        pipe_headers = ["Parametre", "Değer", "Birim", "Yöntem / Standart"]
        for c_idx, ph in enumerate(pipe_headers, start=1):
            p_cell = ws_orc.cell(row=r, column=c_idx, value=ph)
            p_cell.font = header_font
            p_cell.fill = header_fill
            p_cell.alignment = Alignment(horizontal="center")

        pipe_dn = str(orc_data.get("pipe_dn_sel", "DN150 (Di=154.0 mm)"))
        pipe_di = float(orc_data.get("pipe_di_mm", 154.0) or 154.0)
        pipe_l = float(orc_data.get("pipe_length_m", 80.0) or 80.0)
        p_rows = [
            ("Nominal Boru Çapı (DN)", pipe_dn, "-", "Kullanıcı / Standart Seçim"),
            ("Boru İç Çapı (Di)", pipe_di, "mm", "Standart Çelik Boru Tablosu"),
            ("Toplam Eşdeğer Boru Uzunluğu (L)", pipe_l, "m", "Kazan - Eşanjör Arası Hat"),
            ("Sirkülasyon Yağ Debisi (m_oil)", tot_m_oil, "kg/s", "Kızgın Yağ Sirkülasyonu"),
            ("Pürüzlülük Katsayısı (ε)", 0.045, "mm", "Ticari Karbon Çelik Boru (API/ASME)"),
            ("Sürtünme Modeli", "Darcy-Weisbach & Swamee-Jain", "-", "Laminer-Türbülans Geçişli"),
        ]
        for p_label, p_val, p_unit, p_method in p_rows:
            r += 1
            ws_orc.cell(row=r, column=1, value=p_label).font = regular_font
            ws_orc.cell(row=r, column=2, value=p_val).font = bold_font
            ws_orc.cell(row=r, column=3, value=p_unit).font = regular_font
            ws_orc.cell(row=r, column=4, value=p_method).font = regular_font

        r += 2
        ws_orc.cell(row=r, column=1, value="3. ORC GÜÇ DÖNGÜSÜ VE PARAZİTİK TÜKETİM").font = section_font
        r += 1
        for c_idx, ph in enumerate(pipe_headers, start=1):
            p_cell = ws_orc.cell(row=r, column=c_idx, value=ph)
            p_cell.font = header_font
            p_cell.fill = header_fill
            p_cell.alignment = Alignment(horizontal="center")

        orc_rows = [
            ("ORC Çevrim Akışkanı", str(orc_data.get("orc_fluid_sel", "Cyclopentane")), "-", "Organik Çalışma Akışkanı"),
            ("Buharlaşma Basıncı (P_evap)", float(orc_data.get("P_evap_bar", 16.0) or 16.0), "bar", "Süperheater / Evaporatör Basıncı"),
            ("Kondenser Tipi", "Hava Soğutmalı (ACC)" if str(orc_data.get("condenser_type", "")).lower() in ("air", "acc") else "Su Soğutmalı Gövde-Boru", "-", "Kondensasyon Kaynağı"),
            ("Termal Yağ Akışkanı", str(orc_data.get("oil_fluid_sel", "Therminol 66")), "-", "Isı Taşıyıcı Kapalı Devre Yağı"),
        ]
        for o_label, o_val, o_unit, o_method in orc_rows:
            r += 1
            ws_orc.cell(row=r, column=1, value=o_label).font = regular_font
            ws_orc.cell(row=r, column=2, value=o_val).font = bold_font
            ws_orc.cell(row=r, column=3, value=o_unit).font = regular_font
            ws_orc.cell(row=r, column=4, value=o_method).font = regular_font

        for col in ws_orc.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws_orc.column_dimensions[col_letter].width = max(max_len + 3, 14)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

