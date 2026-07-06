"""기상청 단기예보 DFS 격자 좌표 변환 (KMA DFS)."""

from __future__ import annotations

import math

RE = 6371.00877
GRID = 5.0
SLAT1 = 30.0
SLAT2 = 60.0
OLON = 126.0
OLAT = 38.0
XO = 43
YO = 136
GRID_SYSTEM = "KMA_DFS"


def validate_latlon(latitude: float, longitude: float) -> None:
    if latitude < -90 or latitude > 90:
        raise ValueError("위도는 -90~90 범위여야 합니다.")
    if longitude < -180 or longitude > 180:
        raise ValueError("경도는 -180~180 범위여야 합니다.")


def validate_kma_grid(nx: int, ny: int) -> None:
    if nx < 1 or ny < 1:
        raise ValueError("nx/ny는 양의 정수여야 합니다.")
    if nx > 200 or ny > 200:
        raise ValueError("nx/ny 값이 허용 범위를 벗어났습니다.")


def latlon_to_kma_grid(latitude: float, longitude: float) -> dict[str, int | str]:
    """위경도 → 기상청 단기예보 격자(nx, ny) 변환."""
    validate_latlon(latitude, longitude)
    deg_rad = math.pi / 180.0
    re = RE / GRID
    slat1 = SLAT1 * deg_rad
    slat2 = SLAT2 * deg_rad
    olon = OLON * deg_rad
    olat = OLAT * deg_rad

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + latitude * deg_rad * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = longitude * deg_rad - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn
    x = ra * math.sin(theta) + XO
    y = ro - ra * math.cos(theta) + YO
    nx = int(x + 1.5)
    ny = int(y + 1.5)
    validate_kma_grid(nx, ny)
    return {"nx": nx, "ny": ny, "grid_system": GRID_SYSTEM}
