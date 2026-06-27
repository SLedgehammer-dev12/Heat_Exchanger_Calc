from dataclasses import dataclass, field

from exceptions import InvalidGeometryError, InvalidInputError


@dataclass
class GeometryInput:
    """Heat exchanger geometry parameters (SI units).

    Supports three exchanger types:
    - finned_tube: tube bank with fins, pitch plus fin params
    - shell_and_tube: TEMA shell, baffles, tube bundle layout
    - double_pipe: concentric annulus
    """

    # Common
    exchanger_type: str = "finned_tube"
    D_o: float = 0.0  # dış çap [m]
    D_i: float = 0.0  # iç çap [m]
    L: float = 0.0  # boru uzunluğu [m]
    N_tubes: int = 1  # boru sayısı
    k_wall: float = 45.0  # boru malzemesi ısıl iletkenliği [W/m·K]

    # Fin parameters (finned_tube)
    is_finned: bool = False
    fin_height: float = 0.0  # [m]
    fin_thickness: float = 0.0  # [m]
    fin_density: float = 0.0  # [1/m]
    k_fin: float = 237.0  # [W/m·K]
    fin_type: str = "annular"  # "annular" | "rectangular"

    # Tube bank layout (finned_tube)
    pitch: float = 0.0  # transverse pitch [m]
    pitch_parallel: float = 0.0  # longitudinal pitch [m]
    tube_arrangement: str = "staggered"  # "inline" | "staggered"

    # Shell-side (shell_and_tube, double_pipe)
    D_shell: float = 0.0  # shell inner diameter [m]
    baffle_spacing: float = 0.0  # baffle spacing [m] (shell_and_tube)
    baffle_cut: float = 0.25  # baffle cut fraction (0.15–0.45)
    tube_layout_angle: str = "30"  # "30" | "45" | "60" | "90" degrees
    shell_passes: int = 1

    # Fouling
    R_f_i: float = 0.0  # inside fouling [m²·K/W]
    R_f_o: float = 0.0  # outside fouling [m²·K/W]

    def validate(self) -> None:
        if self.D_o <= 0:
            raise InvalidGeometryError("Dış çap (D_o) sıfırdan büyük olmalıdır.")
        if self.D_i <= 0:
            raise InvalidGeometryError("İç çap (D_i) sıfırdan büyük olmalıdır.")
        if self.D_i >= self.D_o:
            raise InvalidGeometryError("Dış çap (D_o) iç çaptan (D_i) büyük olmalıdır.")
        if self.L <= 0:
            raise InvalidGeometryError("Boru uzunluğu (L) sıfırdan büyük olmalıdır.")
        if self.N_tubes < 1:
            raise InvalidGeometryError("Boru sayısı (N_tubes) en az 1 olmalıdır.")
        if self.k_wall <= 0:
            raise InvalidGeometryError("Isıl iletkenlik (k_wall) sıfırdan büyük olmalıdır.")
        if self.exchanger_type not in ("finned_tube", "shell_and_tube", "double_pipe"):
            raise InvalidInputError(f"Desteklenmeyen eşanjör tipi: {self.exchanger_type}")
        if self.baffle_cut < 0.0 or self.baffle_cut > 0.5:
            raise InvalidGeometryError("Baffle cut oranı 0.0–0.5 arasında olmalıdır.")

    def __post_init__(self):
        if self.pitch_parallel <= 0 and self.pitch > 0:
            self.pitch_parallel = self.pitch
        if self.D_shell <= 0:
            self.D_shell = self.D_o * 1.5
        if self.baffle_spacing <= 0:
            self.baffle_spacing = self.L * 0.2

    @classmethod
    def from_dict(cls, d: dict) -> "GeometryInput":
        return cls(
            exchanger_type=d.get("exchanger_type", "finned_tube"),
            D_o=d.get("D_o", 0.0),
            D_i=d.get("D_i", 0.0),
            L=d.get("L", 0.0),
            N_tubes=int(d.get("N_tubes", 1)),
            k_wall=d.get("k_wall", 45.0),
            is_finned=bool(d.get("is_finned", False)),
            fin_height=d.get("fin_height", 0.0),
            fin_thickness=d.get("fin_thickness", 0.0),
            fin_density=d.get("fin_density", 0.0),
            k_fin=d.get("k_fin", 237.0),
            fin_type=d.get("fin_type", "annular"),
            pitch=d.get("pitch", 0.0),
            pitch_parallel=d.get("pitch_parallel", 0.0),
            tube_arrangement=d.get("tube_arrangement", "staggered"),
            D_shell=d.get("D_shell", 0.0),
            baffle_spacing=d.get("baffle_spacing", 0.0),
            baffle_cut=d.get("baffle_cut", 0.25),
            tube_layout_angle=d.get("tube_layout_angle", "30"),
            shell_passes=int(d.get("shell_passes", 1)),
            R_f_i=d.get("R_f_i", 0.0),
            R_f_o=d.get("R_f_o", 0.0),
        )

    def to_dict(self) -> dict:
        return {
            "exchanger_type": self.exchanger_type,
            "D_o": self.D_o,
            "D_i": self.D_i,
            "L": self.L,
            "N_tubes": self.N_tubes,
            "k_wall": self.k_wall,
            "is_finned": self.is_finned,
            "fin_height": self.fin_height,
            "fin_thickness": self.fin_thickness,
            "fin_density": self.fin_density,
            "k_fin": self.k_fin,
            "fin_type": self.fin_type,
            "pitch": self.pitch,
            "pitch_parallel": self.pitch_parallel,
            "tube_arrangement": self.tube_arrangement,
            "D_shell": self.D_shell,
            "baffle_spacing": self.baffle_spacing,
            "baffle_cut": self.baffle_cut,
            "tube_layout_angle": self.tube_layout_angle,
            "shell_passes": self.shell_passes,
            "R_f_i": self.R_f_i,
            "R_f_o": self.R_f_o,
        }


@dataclass
class CalcResult:
    """Unified result container for any solver output."""

    method: str = ""
    source: str = ""
    q: float = 0.0  # [W]
    epsilon: float = 0.0
    t_hot_in: float = 0.0
    t_cold_in: float = 0.0
    t_hot_out: float = 0.0
    t_cold_out: float = 0.0
    ntu: float = 0.0
    cr: float = 0.0
    status: str = "ok"
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        "Method" if self.method.startswith("Epsilon") else "Method"
        return {
            "Method": self.method,
            "Source": self.source,
            "Q [W]": self.q,
            "epsilon": self.epsilon,
            "T_hot_in [C]": self.t_hot_in,
            "T_cold_in [C]": self.t_cold_in,
            "T_hot_out [C]": self.t_hot_out,
            "T_cold_out [C]": self.t_cold_out,
            "NTU": self.ntu,
            "C_r": self.cr,
            "status": self.status,
            "warnings": list(self.warnings),
        }
