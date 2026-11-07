# 技术原理笔记

记录这套工具链在赛题环境中摸索出的关键结论，供参赛选手理解原理、少走弯路。
（以下均为 CTF 沙箱环境中的观察，不构成对任何真实系统的描述。）

## 1. 目标架构（沙箱赛题）

```
支付宝主进程 com.eg.android.AlipayGphone
 ├─ 主小程序（学校服务号壳）
 │    └─ recordFlow.create RPC → 拉起跑步工具子程序
 └─ 跑步工具子程序（页面容器）
      ├─ 可能运行在主进程
      └─ 冷启动后常运行在 :sandboxed_privilege_process0 ← 注意！
```

关键点：**子程序容器进程不固定**。挂载器必须同时覆盖主进程与 sandboxed 子进程，
否则症状是"计时器在走、轨迹不动"（JS 在另一个进程里读的是真实 GPS）。

## 2. 三道本地校验及其放行方式

| 校验 | 位置 | 放行方式 |
|---|---|---|
| 计步权限 | `com.alibaba.health.pedometer` 的 PermissionManager / PedometerAgent | 强制返回 GRANTED（Java hook） |
| 传感器授权 JSAPI | `PedometerKitBridgeExtension.queryDeviceSportAuthorize` | 回调应答 `{"success":true,"authStateInfos":[{"authType":"sensor","authOpen":true}]}` |
| 模拟定位检测 | `Location.isFromMockProvider` | 恒 false |

**最重要的细节**：JSAPI 应答结构里起作用的是 **`authOpen`** 字段。
JS 端包装层把 `authStateInfos[]` 转成 map：`if (e.authOpen) t[e.authType].authState = true`。
返回 `authState:true`（老结构）是无效的——查询"成功"但状态表为空，起跑按钮无反应。

## 3. 轨迹引擎设计

### 时间驱动，不是调用驱动

v1 按调用次数推进（每次 `Location.getLatitude()` 走一步），结果 App 不读定位时
引擎就停摆，配速被算成 10'+。正确做法：

```
里程表 CUMD[s] = ∫₀ˢ spdAt(t)dt   （每秒预积分，梯形法）
位置 f(墙钟) → CUMD[elapsed] → 环线参数角 θ → 经纬度
```

App 端无论以什么频率采样，看到的都是一条物理上自洽的轨迹。

### 环线几何

参数化椭圆 + 低幅谐波，避免"完美圆"特征：

- `r(θ) = A·B/√(B²cos²θ + A²sin²θ) × (1 + Σ aᵢ·sin(kᵢθ+φᵢ))`
- 速度 `spdAt(t) = PACE·(1 + 0.045·sin(t/47) + 0.03·sin(t/173+1.3))`，前 28s 线性热身
- GPS 噪声：AR(1) 随机游走（ρ=0.86），精度 4~12m 慢漂
- 航向：前视 1.5m 差分，保证 bearing 连续

**椭圆弧长必须用 √(r²+r'²) 数值积分**（720 段中点法），轴比 >1.5 时
朴素 r·dθ 会短算 ~8%，导致圈长/配速系统性偏差。

## 4. 坐标系链路

注入值语义 = **WGS-84**（高德 SDK 内部转 GCJ-02 渲染/上报）。

三段转换全部有公开标准算法，`tools/calib.py` 附带三重验证锚点：

```
BD09MC --MC2LL--> BD09 --bd2gcj--> GCJ02 --迭代反解--> WGS84
```

实测教训：
- 手搓迭代反解时，"验证"和"迭代"必须用**同一份正确实现**——
  我们曾用错误的 `tr()` 同时做迭代与 roundtrip 验证，得到自洽但偏差 1.8km 的结果。
- 想定真实 POI：百度 `map.baidu.com/?qt=s` 带 `Referer: https://map.baidu.com/` 可免登录；
  返回墨卡托单位 0.01m。

## 5. 反注入对抗（沙箱内观察）

- 默认 frida-server 端口 27042 会被检测 → 使用改名/改端口分支。
- spawn 模式与目标自带的 ByteHook（libmyhook.so）冲突 → 只用 attach。
- 同进程反复 attach/script load 会触发自毁（native exit 屏蔽也救不回）→
  **单会话原则**：一次挂载到位，中途换脚本先杀 loader。
- native 层 hook（libc exit/kill）与目标 hook 框架冲突 SIGSEGV → 只动 Java 层。
- 系统层真授权优于 hook 欺骗：
  `pm grant com.eg.android.AlipayGphone android.permission.ACTIVITY_RECOGNITION`，
  一次授权永久有效，还能让部分弹窗不再出现。

## 6. 调试经验

- `adb` 掉线：`adb kill-server && adb start-server` 再 connect（MuMu 长跑常见）。
- Git Bash 下设备路径要写 `//sdcard/...` 防止被 MSYS 改写。
- 屏幕判定用像素采样（PIL），注意模拟器重启后可能从竖屏变横屏，
  用 `settings put system user_rotation 0` 锁定。
