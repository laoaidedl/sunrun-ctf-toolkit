# -*- coding: utf-8 -*-
"""loop 参数标定 v2: 百度POI(MC) -> BD09 -> GCJ02 -> WGS84 + 椭圆环路反解
统一约定: 所有函数返回 (lon, lat); 打印一律标注。
验证锚点: 1) 天安门POI MC->LL 应=(116.403963,39.915119)
          2) 天安门 BD->GCJ 公开算例
          3) GCJ->WGS roundtrip 误差应≈0
"""
import json, math

PI = math.pi

# ---------- 1. BD09 墨卡托 -> BD09 经纬度 (百度官方分带多项式) ----------
MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
MC2LL = [
    [1.410526172116255e-8, 8.98305509648872e-6, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 8.983055097726239e-6, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 8.98305509983578e-6, 0.30071316287616, 59.74293618442277, 7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 8.983055099779535e-6, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 8.983055096812155e-6, 6.995724062e-5, 23.10934304144901, -2.3663490511e-4, -0.6321817810242, -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 8.983055095805407e-6, -3.068298e-8, 7.47137025468032, -3.53937994e-6, -0.02145144861037, -1.234426596e-5, 1.0322952773e-4, -3.23890364e-6, 826088.5],
]

def mc2ll(x_m, y_m):
    """BD09MC(米) -> (lon, lat) BD09"""
    ax, ay = abs(x_m), abs(y_m)
    row = MC2LL[-1]
    for i, band in enumerate(MCBAND):
        if ay >= band:
            row = MC2LL[i]
            break
    lng = row[0] + row[1] * ax
    m = ay / row[9]
    lat = (row[2] + row[3]*m + row[4]*m**2 + row[5]*m**3 +
           row[6]*m**4 + row[7]*m**5 + row[8]*m**6)
    return (math.copysign(lng, x_m), math.copysign(lat, y_m))

# ---------- 2. BD09 -> GCJ02 (任务给定标准公式) ----------
def bd2gcj(bd_lon, bd_lat):
    """(lon, lat) BD09 -> (lon, lat) GCJ02.
    x=lon-0.0065, y=lat-0.006, z=sqrt(x^2+y^2)-0.00002*sin(y*pi*3000/180),
    th=atan2(y,x)-0.000003*cos(x*pi*3000/180);
    z*sin(th)=纬向分量, z*cos(th)=经向分量 -> 返回 (z*cos(th), z*sin(th))"""
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    th = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    return (z * math.cos(th), z * math.sin(th))

# ---------- 3. GCJ02 <-> WGS84 (克拉索夫斯基椭球, 迭代反解) ----------
AA = 6378245.0
EE = 0.00669342162296594323

def _tlat(x, y):
    r = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    r += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0/3.0
    r += (20.0*math.sin(y*PI) + 40.0*math.sin(y/3.0*PI)) * 2.0/3.0
    r += (160.0*math.sin(y/12.0*PI) + 320.0*math.sin(y*PI/30.0)) * 2.0/3.0
    return r

def _tlng(x, y):
    r = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    r += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0/3.0
    r += (20.0*math.sin(x*PI) + 40.0*math.sin(x/3.0*PI)) * 2.0/3.0
    r += (150.0*math.sin(x/12.0*PI) + 300.0*math.sin(x/30.0*PI)) * 2.0/3.0
    return r

def wgs2gcj(wgs_lon, wgs_lat):
    dlat = _tlat(wgs_lon - 105.0, wgs_lat - 35.0)
    dlng = _tlng(wgs_lon - 105.0, wgs_lat - 35.0)
    radlat = wgs_lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sq = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((AA * (1 - EE)) / (magic * sq) * PI)
    dlng = (dlng * 180.0) / (AA / sq * math.cos(radlat) * PI)
    return (wgs_lon + dlng, wgs_lat + dlat)

def gcj2wgs(gcj_lon, gcj_lat, iters=5):
    wlon, wlat = gcj_lon, gcj_lat
    for _ in range(iters):
        tlon, tlat = wgs2gcj(wlon, wlat)
        wlon += gcj_lon - tlon
        wlat += gcj_lat - tlat
    return (wlon, wlat)

def chain_mc_to_wgs(x_m, y_m, tag):
    bd = mc2ll(x_m, y_m)
    gcj = bd2gcj(*bd)
    wgs = gcj2wgs(*gcj)
    rt = wgs2gcj(*wgs)
    rt_err = max(abs(rt[0]-gcj[0]), abs(rt[1]-gcj[1]))
    print(f"[{tag}] BD09(lon,lat)=({bd[0]:.6f},{bd[1]:.6f}) GCJ=({gcj[0]:.6f},{gcj[1]:.6f}) "
          f"WGS=({wgs[0]:.6f},{wgs[1]:.6f}) roundtrip_err={rt_err:.2e}deg")
    return bd, gcj, wgs

print("========== 校验 1: 天安门 MC->LL (公认 BD09: 116.403963,39.915119) ==========")
tam = mc2ll(12958170.88, 4825940.97)
print(f"天安门 BD09(lon,lat)=({tam[0]:.6f},{tam[1]:.6f})")

print("========== 校验 2: 公开BD->GCJ算例 (天安门, 公认值) ==========")
g = bd2gcj(116.403963, 39.915119)
# 天安门旗杆 BD09 -> GCJ02 公开换算参考值(多种实现共同结果附近, 容差 1e-5 deg)
g_ref = (116.397499, 39.908722)
print(f"GCJ(lon,lat)=({g[0]:.6f},{g[1]:.6f})  参考 lon={g_ref[0]:.6f} lat={g_ref[1]:.6f}  "
      f"偏差=({abs(g[0]-g_ref[0]):.2e}, {abs(g[1]-g_ref[1]):.2e}) deg")

print("========== 校验 3: GCJ<->WGS roundtrip (任意点, 应≈0) ==========")
gcj_test = (116.397499, 39.908722)
w_ref = gcj2wgs(*gcj_test)
rt_ref = wgs2gcj(*w_ref)
d_ref = math.hypot((rt_ref[0]-gcj_test[0])*88061, (rt_ref[1]-gcj_test[1])*110993)
print(f"GCJ({gcj_test[0]:.6f},{gcj_test[1]:.6f}) -> WGS({w_ref[0]:.6f},{w_ref[1]:.6f}) "
      f"-> GCJ({rt_ref[0]:.6f},{rt_ref[1]:.6f})  roundtrip 误差≈{d_ref:.4f} m (应<0.01m)")
assert d_ref < 0.01, "GCJ<->WGS roundtrip 失败: 转换实现有误!"

print("========== POI 链路演示 (虚构示例值, 演示转换流程) ==========")
# 以下 MC 坐标为虚构示例(数量级/分带与真实百度数据一致), 使用时替换为你自己的实抓值
field_mc  = (12958170.88, 4825940.97)   # 虚构示例: 校内田径场
school_mc = (12958520.00, 4826500.00)   # 虚构示例: 同校主体标注位
gate_mc   = (12958400.00, 4827000.00)   # 虚构示例: 校门
court_mc  = (12958600.00, 4826200.00)   # 虚构示例: 校内另一 POI

fb, fg, fw = chain_mc_to_wgs(*field_mc,  "示例田径场")
sb, sg, sw = chain_mc_to_wgs(*school_mc, "示例主体")
gb, gg, gw = chain_mc_to_wgs(*gate_mc,   "示例校门")
cb_, cg, cw = chain_mc_to_wgs(*court_mc, "示例球场")

print(f"\n布局验证: 球场相对田径场 = 东{(cb_[0]-fb[0])*88061:.0f}m 北{(cb_[1]-fb[1])*110993:.0f}m")
print(f"布局验证: 校门  相对田径场 = 东{(gb[0]-fb[0])*88061:.0f}m 北{(gb[1]-fb[1])*110993:.0f}m")

print("========== 椭圆反解 (周长600m, 轴比740:480) ==========")
def ramanujan(a, b):
    return PI * (3.0*(a+b) - math.sqrt((3.0*a+b)*(a+3.0*b)))

K = 740.0/480.0
TARGET = 600.0
gk = 3.0*(K+1.0) - math.sqrt((3.0*K+1.0)*(K+3.0))
B = TARGET / (PI * gk)
A = K * B
print(f"轴比 k={K:.6f}  g(k)={gk:.6f}  长半轴 a={A:.3f}m  短半轴 b={B:.3f}m "
      f"(基础椭圆周长={ramanujan(A,B):.2f}m)")

H2A, H2P = 0.05, 1.1
H3A, H3P = 0.03, 0.5

def r_base(th):
    c, s = math.cos(th), math.sin(th)
    return A*B / math.sqrt(B*B*c*c + A*A*s*s)

def r_full(th):
    return r_base(th) * (1.0 + H2A*math.sin(2*th + H2P) + H3A*math.sin(3*th + H3P))

def laplen_numeric(n=200000):
    h = 2*PI/n
    tot = 0.0
    for i in range(n):
        t = (i + 0.5) * h
        rr = r_full(t)
        r1, r2 = r_full(t - h/2), r_full(t + h/2)
        tot += math.sqrt(rr*rr + ((r2-r1)/h)**2) * h
    return tot

L_pred = laplen_numeric()
print(f"含谐波扰动预计 LAPLEN = {L_pred:.2f} m (要求550~700)")
print(f"10km 圈数 = {10000.0/L_pred:.3f}   东西跨度≈{2*A*1.08:.0f}m 南北跨度≈{2*B*1.08:.0f}m")

print("========== 中心汇总 ==========")
C_LAT, C_LNG = fw[1], fw[0]
M_LNG = 111320.0 * math.cos(C_LAT * PI / 180.0)
print(f"田径场中心 BD09 : lon={fb[0]:.6f} lat={fb[1]:.6f}")
print(f"田径场中心 GCJ02: lon={fg[0]:.6f} lat={fg[1]:.6f}")
print(f"田径场中心 WGS84: lat={C_LAT:.6f} lon={C_LNG:.6f}")
print(f"引擎常数: M_LAT=111320.0 M_LNG={M_LNG:.1f} ROT=-2.0deg")
print(f"参考: GCJ 偏移 = 东{(fg[0]-fw[0])*88061:.0f}m 北{(fg[1]-fw[1])*110993:.0f}m (GCJ在WGS东北,方向合理)")

json.dump({
    "bd": [fb[0], fb[1]], "gcj": [fg[0], fg[1]], "wgs": [C_LAT, C_LNG],
    "a": round(A, 2), "b": round(B, 2),
    "rot_deg": -2.0, "laplen_pred": round(L_pred, 1),
    "laps_10km": round(10000.0/L_pred, 2),
    "m_lng": round(M_LNG, 1),
}, open(r"C:\Users\admin\Desktop\zb\sunrun_pkg\calib_tmp\calib_result.json", "w"), ensure_ascii=False, indent=1)
print("saved calib_result.json")
