from heat_exchanger import FinTubeHeatExchanger, Fluid


def main():
    print("--- Fin-Tube Isı Değiştirici İleri Seviye Hesaplama & Cross-Check ---")
    print("Sıcak Akışkan: Doğal Gaz Türbin Egzoz Gazı")
    print("Soğuk Akışkan: Isı Transfer Yağı (T66)\n")

    # Akışkanların tanımlanması
    hot_fluid = Fluid(name="Exhaust Gas", cp=1100.0, density=0.5, is_coolprop=False)

    try:
        cold_fluid = Fluid(name="T66", is_coolprop=True, calc_temp_c=150.0)
        print(f"CoolProp'tan T66 Cp değeri çekildi: {cold_fluid.cp:.2f} J/kg.K\n")
    except Exception as e:
        print(f"CoolProp hatası: {e}")
        cold_fluid = Fluid(name="Thermal Oil", cp=2200.0, density=850.0, is_coolprop=False)

    # Değiştirici Tasarım Parametreleri
    U_value = 50.0  # W/m^2.K
    Area = 200.0  # m^2
    m_hot = 15.0  # kg/s
    m_cold = 5.0  # kg/s
    T_hot_in = 450.0  # °C
    T_cold_in = 120.0  # °C

    print("Girdiler:")
    print(f"Sıcak Akışkan: m = {m_hot} kg/s, T_in = {T_hot_in} °C")
    print(f"Soğuk Akışkan: m = {m_cold} kg/s, T_in = {T_cold_in} °C")
    print(f"U = {U_value} W/m²K, Alan = {Area} m²\n")

    # 1. Çapraz Akış (Cross Flow) Testi
    print("=== ÇAPRAZ AKIŞ (CROSS FLOW - UNMIXED) ===")
    hx_cross = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=U_value, A=Area, flow_type="cross_unmixed")
    hx_cross.cross_check(m_hot, m_cold, T_hot_in, T_cold_in)

    # 2. Ters Akış (Counter Flow) Testi
    print("\n=== TERS AKIŞ (COUNTER FLOW) ===")
    hx_counter = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=U_value, A=Area, flow_type="counter")
    hx_counter.cross_check(m_hot, m_cold, T_hot_in, T_cold_in)

    # 3. Paralel Akış (Parallel Flow) Testi
    print("\n=== PARALEL AKIŞ (PARALLEL FLOW) ===")
    hx_parallel = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=U_value, A=Area, flow_type="parallel")
    hx_parallel.cross_check(m_hot, m_cold, T_hot_in, T_cold_in)


if __name__ == "__main__":
    main()
