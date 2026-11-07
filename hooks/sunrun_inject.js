/* all_in_one: 权限放行 + authOpen 应答 + 校园时间驱动轨迹引擎
 * 单脚本单会话,一次 attach。示例场地:某校园田径场(参数请按沙箱环境自行修改,见README)
 * 中心 WGS-84 / GCJ-02 双语义坐标转换见 tools/calib.py
 */
Java.perform(function () {
    // ---------- 1. 计步权限链放行 ----------
    try {
        var PM = Java.use('com.alibaba.health.pedometer.core.permission.PermissionManager');
        PM.checkPermission.implementation = function (perm) { return true; };
    } catch (e) { send('[perm] PM err ' + e); }
    try {
        var HPC = Java.use('com.alibaba.health.pedometer.core.datasource.feature.HealthPermissionChecker');
        HPC.requestOldPermission.implementation = function (act, listener) { };
    } catch (e) { }
    try {
        var PA = Java.use('com.alibaba.health.pedometer.core.datasource.PedometerAgent');
        var PR = Java.use('com.alibaba.health.pedometer.core.datasource.feature.PermissionResult');
        PA.checkPermission.implementation = function (ctx, checker) { return PR.GRANTED.value; };
    } catch (e) { }
    try {
        var SPp = Java.use('com.alibaba.health.pedometer.core.datasource.sensor.core.SensorPedometer');
        SPp.isSupported.implementation = function (ctx) { return true; };
    } catch (e) { }
    send('[aio] perm hooks ok');

    // ---------- 2. 健康 JSAPI authOpen 应答 ----------
    try {
        var fj = Java.use('com.alibaba.fastjson.JSONObject');
        var Ext = Java.use('com.alipay.mobile.healthcommon.jsapi.PedometerKitBridgeExtension');
        var OK = '{"success":true,"dataSource":"sensor","errorCode":"","errorMessage":"","authStateInfos":[{"authType":"sensor","authOpen":true}]}';
        Ext.queryDeviceSportAuthorize.implementation = function () {
            var cb = arguments[7];
            try { cb.sendJSONResponse(fj.parseObject(OK)); } catch (e) { }
        };
        Ext.requestDeviceSportAuthorize.implementation = function () {
            var cb = arguments[7];
            try { cb.sendJSONResponse(fj.parseObject(OK)); } catch (e) { }
        };
        Ext.querySensorAuthPermission.implementation = function () {
            var cb = arguments[3];
            try { cb.sendJSONResponse(fj.parseObject(OK)); } catch (e) { }
        };
        send('[aio] health5 hooks ok');
    } catch (e) { send('[aio] health err ' + e); }

/*
 * loop_engine —— 校园田径场外环路 轨迹参数段 + 引擎核心 (示例参数,按需修改)
 * 用法: 将本文件"参数段 + 几何/速度/里程/cur()"整体替换 all_in_one.js 第3节
 *       (参数请按你的沙箱环境自行标定, 场地不符时优先缩小 A/B)
 *
 * 环线: 不规则椭圆 + 谐波扰动(±8%内), 长轴东西向、顺时针旋 -2°
 * v4b: A/B 同比缩小 16.2% —— 外沿贴跑道/内环路, 西侧避开博文苑小区; 中心/旋转角/谐波结构不变
 * 中心: 公开地图POI标注位(示例)
 *       转换链示例见 tools/calib.py (BD09MC -> BD09 -> GCJ02 -> WGS84)
 * 一圈长度 LAPLEN ≈ 516 m; 6km ≈ 11.6 圈, 10km ≈ 19.4 圈 (配速 5'30"/km)
 */

// ---------- 参数段 ----------
var C_LAT = 36.071000, C_LNG = 120.383000;   // 示例中心:替换为你沙箱场地的 WGS-84 坐标    // WGS-84 环心(田径场POI)
var A = 96.00, B = 62.27;                    // 示例:长/短半轴(米),围栏报错时先缩小                     // 长半轴/短半轴(米), 轴比740:480不变, 较v4(114.54/74.296)缩小16.2%
var ROT = -2.0 * Math.PI / 180;               // 长轴旋转角: 顺时针 2°(东端略偏南)
var H2A = 0.05, H2P = 1.1;                    // 谐波2: 幅度/相位
var H3A = 0.03, H3P = 0.5;                    // 谐波3: 幅度/相位 (总扰动 ≤ ±8%)
var PACE = 3.0303, RAMP = 28.0, MAXT = 9000;  // 5'30"/km; 热身28s; 里程预积分至9000s
var M_LAT = 111320.0, M_LNG = 111320.0 * Math.cos(C_LAT * Math.PI / 180);
var N = 720, STEP = 2 * Math.PI / N, LAPCUM = [0.0], LAPLEN;

// ---------- 几何 ----------
function harm(th) { return 1.0 + H2A * Math.sin(2 * th + H2P) + H3A * Math.sin(3 * th + H3P); }
function rAt(th) {                            // 极坐标半径(米), θ=0 沿长轴方向
    var c = Math.cos(th), s = Math.sin(th);
    var base = A * B / Math.sqrt(B * B * c * c + A * A * s * s);   // 椭圆 r(θ)
    return base * harm(th);                   // r(θ) = 椭圆 × (1 + 0.05·sin(2θ+1.1) + 0.03·sin(3θ+0.5))
}
function dsdth(th) {                          // 弧长微元 ds/dθ = sqrt(r² + r'²)  (椭圆不可用 r·dθ, 会短~8%)
    var h = 1e-5;
    var r = rAt(th), dr = (rAt(th + h) - rAt(th - h)) / (2 * h);
    return Math.sqrt(r * r + dr * dr);
}
(function () {                                 // LAPCUM 预积分(中点法), LAPCUM[i]=θ∈[0,i·STEP] 弧长
    for (var i = 1; i <= N; i++)
        LAPCUM.push(LAPCUM[i - 1] + dsdth((i - 0.5) * STEP) * STEP);
    LAPLEN = LAPCUM[N];
})();
function thAt(s) {                             // 弧长→参数角; 约定 thAt(k·LAPLEN)=k·2π
    var k = Math.floor(s / LAPLEN), m = s - k * LAPLEN;
    if (m < 0) { m += LAPLEN; k -= 1; }
    var lo = 0, hi = N;
    while (lo < hi - 1) { var mid = (lo + hi) >> 1; if (LAPCUM[mid] <= m) lo = mid; else hi = mid; }
    var seg = LAPCUM[lo + 1] - LAPCUM[lo], fr = seg > 0 ? (m - LAPCUM[lo]) / seg : 0;
    return (lo + fr) * STEP + k * 2 * Math.PI;
}
function xyAt(th) {                            // 参数角→东北向偏移(米, 含长轴旋转)
    var r = rAt(th), e0 = r * Math.cos(th), n0 = r * Math.sin(th);
    var cr = Math.cos(ROT), sr = Math.sin(ROT);
    return { e: e0 * cr - n0 * sr, n: e0 * sr + n0 * cr };
}

// ---------- 速度 / 里程 ----------
function spdAt(t) {                            // 热身爬坡 + 5'30"/km 双周期波动
    if (t < RAMP) return PACE * (0.35 + 0.65 * (t / RAMP));
    return PACE * (1.0 + 0.045 * Math.sin(t / 47.0) + 0.03 * Math.sin(t / 173.0 + 1.3));
}
var CUMD = [0.0];                              // 每秒预积分里程(梯形法), CUMD[s]=第s秒末累计米数
for (var s = 1; s <= MAXT; s++) CUMD.push(CUMD[s - 1] + (spdAt(s - 1) + spdAt(s)) / 2);

// ---------- 实时定位点 (与 all_in_one.js cur() 同构) ----------
var walk = { x: 0, y: 0 }, acc0 = 6.0, cached = null, cachedAt = -1, attachT = Date.now();
function nz() { walk.x = walk.x * 0.86 + (Math.random() - 0.5) * 1.7;
    walk.y = walk.y * 0.86 + (Math.random() - 0.5) * 1.7; return { x: walk.x, y: walk.y }; }
function cur() {
    var t = Date.now();
    if (cached && cachedAt === Math.floor(t / 1000)) return cached;
    var el = (t - attachT) / 1000.0;
    var trav = CUMD[Math.min(Math.floor(el), MAXT)];
    var p0 = xyAt(thAt(trav));
    var lat = C_LAT + p0.n / M_LAT, lng = C_LNG + p0.e / M_LNG;
    var p2 = xyAt(thAt(trav + 1.5));           // 前视1.5m求航向
    var la2 = C_LAT + p2.n / M_LAT, ln2 = C_LNG + p2.e / M_LNG;
    var brg = Math.atan2((ln2 - lng) * M_LNG, (la2 - lat) * M_LAT) * 180 / Math.PI; if (brg < 0) brg += 360;
    var sp = spdAt(el), w = nz();
    acc0 = acc0 * 0.98 + Math.random() * 0.5;
    var acc = 4.0 + 4.0 * (0.5 + 0.5 * Math.sin(el / 23.0)) + acc0 * 0.3;
    lat += w.y / M_LAT; lng += w.x / M_LNG;
    cached = { lat: lat, lng: lng, spd: sp, brg: brg, acc: acc, dist: trav, el: el };
    cachedAt = Math.floor(t / 1000);
    return cached;
}


    var Loc = Java.use('android.location.Location');
    Loc.getLatitude.implementation = function(){ return cur().lat; };
    Loc.getLongitude.implementation = function(){ return cur().lng; };
    Loc.getSpeed.implementation = function(){ return cur().spd; };
    Loc.getBearing.implementation = function(){ return cur().brg; };
    Loc.getAccuracy.implementation = function(){ return cur().acc; };
    Loc.isFromMockProvider.implementation = function(){ return false; };
    Loc.setLatitude.implementation = function(v){ return this.setLatitude(cur().lat); };
    Loc.setLongitude.implementation = function(v){ return this.setLongitude(cur().lng); };
    Loc.setTime.implementation = function(v){ return this.setTime(Date.now()); };
    send('[aio] location hooks ok (campus loop, time-driven)');

    var hit=false;
    setInterval(function(){
        try { var p = cur();
            send('[aio] dist='+(p.dist/1000).toFixed(2)+'km lap='+(Math.floor(p.dist/LAPLEN)+1)+
                ' t='+Math.floor(p.el)+' pace=5\'30"');
            if (!hit && p.dist >= 10000) { hit = true; send('TARGET_10KM'); }
        } catch(e){}
    }, 10000);

    rpc.exports = { status: function(){ var p = cur();
        return {dist:p.dist, lap:Math.floor(p.dist/LAPLEN)+1, elapsed:Math.floor(p.el), engine:'campus-v3'}; } };
});
