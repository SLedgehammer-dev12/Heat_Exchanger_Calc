from datetime import datetime


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
    lines.extend(["", title, "-" * len(title)])


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
}


def _add_geometry(lines, geometry):
    _add_mapping(lines, {GEOMETRY_LABELS.get(k, k): v for k, v in geometry.items()}, skip_empty=True)


def _collect_warnings(*results):
    warnings = []
    for result in results:
        if not result:
            continue
        for msg in result.get("warnings", []):
            if msg not in warnings:
                warnings.append(msg)
    return warnings


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
    inputs = context["inputs"]
    methods = context["methods"]
    fluids = context["fluids"]
    results = context["results"]
    geometry = context.get("geometry") or {}
    geo_result = context.get("geo_result")
    actual_result = context.get("actual_result")
    crosscheck_results = context.get("crosscheck_results") or []
    selected = results["main"]

    lines = [
        "ISI DEGISTIRICI DETAYLI HESAP RAPORU",
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
            "Sıcak akışkan": fluids["hot"].get("label"),
            "Sıcak debi - kullanıcı girdisi": inputs.get("m_hot_raw"),
            "Sıcak debi - hesapta kullanılan": f"{_fmt(inputs.get('m_hot_kg_s'), 6)} kg/s",
            "Sıcak giriş sıcaklığı": f"{_fmt(inputs.get('T_hot_in_C'), 3)} °C",
            "Soğuk akışkan": fluids["cold"].get("label"),
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
        data = fluids[side]
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
    C_h = (inputs.get("m_hot_kg_s") or 0.0) * (fluids.get("hot", {}).get("cp") or 0.0)
    C_c = (inputs.get("m_cold_kg_s") or 0.0) * (fluids.get("cold", {}).get("cp") or 0.0)
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
            "Q": f"{_fmt(selected.get('Q [W]') / 1000, 4)} kW",
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
                "Sıcak taraftan hesaplanan Q": f"{_fmt(actual_result.get('Q_hot [W]') / 1000, 4)} kW",
                "Soğuk taraftan hesaplanan Q": f"{_fmt(actual_result.get('Q_cold [W]') / 1000, 4)} kW",
                "Ortalama Q": f"{_fmt(actual_result.get('Q_avg [W]') / 1000, 4)} kW",
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
            if ref_q and ref_q > 0:
                diff = f", seçili sonuca göre Q sapması = {_fmt(abs(result.get('Q [W]') - ref_q) / ref_q * 100, 4)} %"
            lines.append(
                f"- {result.get('Method')} / {result.get('Source')}: "
                f"Q={_fmt(result.get('Q [W]') / 1000, 4)} kW, "
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
            "- Çapraz akış LMTD düzeltme faktörü Bowman cebirsel formülü (1-N shell-and-tube) ile hesaplanır; F < 0.5 durumunda seri shell veya counterflow önerilir.",
            "- Gnielinski korelasyonu ana iç akış korelasyonudur; Dittus-Boelter sadece yedek olarak kullanılır. Laminer/geçiş bölgesi sonuçları ön tasarım kabulüdür.",
            "- Termal yağ verileri quadratic cp(T) korelasyon modeli ile hesaplanır; üretici datasheet değerleri ile doğrulanmalıdır.",
        ]
    )

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
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("  ", "&nbsp;&nbsp;")
        return Paragraph(safe, style)

    def hr():
        return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"))

    story = []
    story.append(Paragraph("Isı Değiştirici Hesap Raporu", title_style))
    story.append(Paragraph(f"Oluşturulma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", note))
    story.append(hr())

    inputs = context["inputs"]
    methods = context["methods"]
    fluids = context["fluids"]
    results = context["results"]
    geometry = context.get("geometry") or {}
    geo_result = context.get("geo_result")
    actual_result = context.get("actual_result")
    crosscheck_results = context.get("crosscheck_results") or []
    selected = results["main"]

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
        ("Sıcak akışkan", fluids["hot"].get("label")),
        ("Sıcak debi", f"{_fmt(inputs.get('m_hot_kg_s'), 6)} kg/s"),
        ("Sıcak giriş", f"{_fmt(inputs.get('T_hot_in_C'), 3)} °C"),
        ("Soğuk akışkan", fluids["cold"].get("label")),
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
        rows.append(
            [
                p(key),
                p(f"{_fmt(fluids['hot'].get(tr), 4)}" if fluids["hot"].get(tr) else "-"),
                p(f"{_fmt(fluids['cold'].get(tr), 4)}" if fluids["cold"].get(tr) else "-"),
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
            ("İç türbülanslı Nu", "Gnielowski (birincil); Dittus-Boelter (yedek)"),
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
    C_h = (inputs.get("m_hot_kg_s") or 0.0) * (fluids.get("hot", {}).get("cp") or 0.0)
    C_c = (inputs.get("m_cold_kg_s") or 0.0) * (fluids.get("cold", {}).get("cp") or 0.0)
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
    res_data = [
        ("Metot", selected.get("Method")),
        ("Kaynak", selected.get("Source")),
        ("Durum", selected.get("status", "ok")),
        ("Q (kW)", f"{_fmt(selected.get('Q [W]') / 1000, 4)}"),
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
        perf_data = [
            ("Q_hot (kW)", f"{_fmt(actual_result.get('Q_hot [W]') / 1000, 4)}"),
            ("Q_cold (kW)", f"{_fmt(actual_result.get('Q_cold [W]') / 1000, 4)}"),
            ("Q_avg (kW)", f"{_fmt(actual_result.get('Q_avg [W]') / 1000, 4)}"),
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
            if ref_q and ref_q > 0:
                diff = f" sapma={_fmt(abs(r.get('Q [W]') - ref_q) / ref_q * 100, 4)}%"
            rows.append(
                [
                    p(f"{r.get('Method')}/{r.get('Source')}"),
                    p(f"{_fmt(r.get('Q [W]') / 1000, 4)}"),
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

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
