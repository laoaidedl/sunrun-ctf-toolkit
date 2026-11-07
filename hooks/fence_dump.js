/* fence_dump: 只读抓取 AMap 围栏 polygon 顶点 + 我们轨迹 polyline 顶点 */
Java.perform(function () {
    var seen = 0;
    function dumpPts(list, tag) {
        try {
            var JList = Java.use('java.util.List');
            var jl = Java.cast(list, JList);
            var sz = jl.size();
            if (sz === 0 || sz > 5000) return;
            var LL = Java.use('com.amap.api.maps.model.LatLng');
            var out = [];
            for (var i = 0; i < sz; i++) {
                var ll = Java.cast(jl.get(i), LL);
                out.push([ll.latitude.value.toFixed ? ll.latitude.value.toFixed(6) : String(ll.latitude.value), String(ll.longitude.value)]);
            }
            seen++;
            send('[fence] ' + tag + ' n=' + sz);
            send('PTS_' + tag + '_' + seen + '=' + JSON.stringify(out));
        } catch (e) { send('[fence] dump err ' + e); }
    }

    try {
        var AMap = Java.use('com.amap.api.maps.AMap');
        AMap.addPolygon.overload('com.amap.api.maps.model.PolygonOptions')
            .implementation = function (opts) {
                dumpPts(opts.getPoints(), 'POLY');
                return this.addPolygon(opts);
            };
        send('[fence] hook addPolygon ok');
    } catch (e) { send('[fence] addPolygon err ' + e); }

    try {
        var PO = Java.use('com.amap.api.maps.model.PolygonOptions');
        PO.addAll.implementation = function (list) {
            dumpPts(list, 'PO_ADD');
            return this.addAll(list);
        };
        send('[fence] hook addAll ok');
    } catch (e) { send('[fence] addAll err ' + e); }

    try {
        var LO = Java.use('com.amap.api.maps.model.PolylineOptions');
        LO.addAll.implementation = function (list) {
            dumpPts(list, 'LINE');
            return this.addAll(list);
        };
        send('[fence] hook lineAddAll ok');
    } catch (e) { }
});
