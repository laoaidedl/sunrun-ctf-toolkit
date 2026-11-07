# SunRun CTF Toolkit

> 支付宝小程序「校园阳光跑」类 CTF 赛题的定位注入研究工具链。
> 适用于 **CTF 竞赛 / 授权安全教学沙箱 / 逆向工程学习**。请完整阅读下方免责声明后再使用。

---

## ⚠️ 免责声明（DISCLAIMER）

**1. 授权范围（适用人群与场景）**
本工具链面向以下两类用途：
- **CTF 竞赛选手**：在赛事方明确授权的沙箱环境（比赛专用模拟器、比赛下发的镜像、比赛靶机平台）中进行解题研究；
- **逆向工程学习者 / 安全研究人员**：在**自建的实验环境**（自己的模拟器 + 自己注册/搭建的测试目标）中，学习移动应用逆向、动态分析（frida hook）、定位服务原理等技术。

**2. 禁止用途**
- ❌ **严禁在任何真实高校场景中使用**，包括但不限于：代替本人/他人完成体育课程打卡、体育测试、晨跑任务等。
- ❌ 严禁绕过、破坏任何真实学校正在使用的考勤/体测系统的正常功能。
- ❌ 严禁将本工具链用于任何商业代跑、有偿代刷服务。

**3. 责任划分**
- 本项目作者不持有、不维护、不背书任何针对真实生产环境的适配。
- **任何超出第 1 条授权范围的使用——尤其是真实学校学生将其用于体育课程打卡、体育测试等——所产生的一切后果，包括但不限于成绩作废、纪律处分、学籍处理，均由使用者本人承担，与本项目作者无关。**
- 使用即代表你已阅读、理解并同意本声明。不同意请立即停止使用并删除本仓库。

**4. 无担保**
本项目按"现状"提供，不附带任何明示或默示的担保。作者不对使用本工具造成的任何直接或间接损失负责。

---

## 项目结构

```
sunrun-ctf-oss/
├── hooks/
│   └── sunrun_inject.js     # 注入脚本：权限放行 + JSAPI 授权应答 + 轨迹引擎
├── loader/
│   └── aio_run.py           # 单会话挂载器（主进程 + sandboxed 子进程双挂载）
├── tools/
│   └── calib.py             # 坐标系转换链（BD09/MC → GCJ02 → WGS84，含验证锚点）
└── docs/
    └── PRINCIPLE.md         # 技术原理笔记
```

## 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| MuMu 模拟器 | Android 12 镜像 | 赛题标准环境 |
| frida-server | **16.6.6**（勿用 17.x） | 17.x 的 Java bridge 在 MuMu x64 翻译层下不可用 |
| frida CLI（宿主） | 16.6.6 | 与 server 版本必须一致 |
| Python | 3.8+ | 仅标准库 + frida |
| adb | platform-tools | 宿主机 |

> frida-server 建议使用反检测分支（如 Florida），以隐藏默认端口 27042 特征。
> 本仓库不分发任何 frida-server 二进制，请自行获取。

## 快速开始

```bash
# 1. 连接模拟器
adb connect 127.0.0.1:16384

# 2. 启动 frida-server（设备内，路径与端口按自己的部署调整）
adb -s 127.0.0.1:16384 shell "su -c 'nohup /data/local/tmp/<你的frida-server> -l 0.0.0.0:39571 >/dev/null 2>&1 &'"
adb -s 127.0.0.1:16384 forward tcp:39571 tcp:39571

# 3. 挂载注入脚本（在仓库根目录执行）
python loader/aio_run.py hooks/sunrun_inject.js

# 4. 在模拟器里打开赛题小程序，正常走打卡流程即可
```

挂载器会自动发现支付宝主进程和 sandboxed 子进程并分别注入（见下文"已知坑"）。

## 注入脚本做了什么（技术概要）

`hooks/sunrun_inject.js` 在目标进程内做三件事，全部发生在 **客户端本地**，不触碰任何服务器协议、签名、报文：

1. **计步权限放行**：`PedometerAgent.checkPermission` / `PermissionManager.checkPermission` 强制返回已授权（模拟器无真实计步传感器时的通行证）。
2. **健康 JSAPI 授权应答**：拦截 `PedometerKitBridgeExtension.queryDeviceSportAuthorize` 等 JSAPI 回调，按 JS 端期望的结构应答 `authStateInfos: [{authType:"sensor", authOpen:true}]`。
3. **轨迹引擎**：`android.location.Location` 的读写全部重定向到一条**时间驱动**的参数化椭圆环线（含谐波扰动 + 随机游走 GPS 噪声 + 精度漂移），`isFromMockProvider` 恒 false。

引擎为纯时间驱动（预积分里程表 + 墙钟），定位点序列与真实跑步在统计特征上同构：速度带双周期波动、28 秒热身爬坡、航向连续、精度 4~12m 漂移。

## 修改跑步路径（适配你的沙箱场地）

脚本里的轨迹由一组**椭圆参数**完全确定，集中在 `hooks/sunrun_inject.js` 顶部：

```js
var C_LAT = 36.071000, C_LNG = 120.383000;  // 环线中心（WGS-84，十进制度）—— 示例值，替换成你的场地
var A = 96.00, B = 62.27;                   // 长半轴 / 短半轴（米）
var ROT = -2.0 * Math.PI / 180;             // 长轴旋转角（弧度，顺时针为负）
var H2A = 0.05, H2P = 1.1;                  // 谐波 #2 幅度 / 相位
var H3A = 0.03, H3P = 0.5;                  // 谐波 #3 幅度 / 相位
var PACE = 3.0303;                          // 配速 5'30"/km 对应速度（m/s）
```

**如果你的沙箱环境校验提示围栏/轨迹相关错误，按下面步骤把参数改成你自己的场地：**

1. 定一个环线中心 `C_LAT / C_LNG`（WGS-84）。地图坐标转换用 `tools/calib.py`，它带三个可复现的验证锚点（天安门 MC、已知 BD→GCJ 算例、GCJ→WGS 往返零误差）。
2. 定椭圆 `A / B`（米）与旋转角 `ROT`。圈长会由脚本自动数值积分，无需手算。
3. 改完保存，重新执行 `python loader/aio_run.py hooks/sunrun_inject.js` 即可，无需重启目标 App。
4. 起跑前可在脚本日志（`[aio] dist=... lap=...`）确认圈长与圈数符合预期。

> 椭圆参数只描述几何形状；不同沙箱的场地、围栏规则、里程规则可能不同，
> 属于正常的环境差异，按上述步骤调整即可。仓库不针对任何特定真实场地做适配。

## 已知坑（都替你踩过了）

| 坑 | 症状 | 解法 |
|---|---|---|
| frida 17.x | `Java is not defined` | 降级 16.6.6，server/client 同版本 |
| spawn 挂载 | SIGSEGV (0xdead1005) | 只用 **attach**，等 App 完全启动后再挂 |
| 多会话重复注入 | 目标自毁闪退 | **单会话原则**：挂一次后不再 attach；换脚本先 kill 旧 loader |
| 冷启动后轨迹不动 | 计时在走、地图蓝点不动 | 小程序容器跑在 `sandboxed_privilege_process0` 子进程里；aio_run.py 已自动双挂载 |
| 调用计数式引擎 | 配速 >10'/km 未达标 | 引擎必须时间驱动；本仓库引擎已是 |
| native 层 hook | 与目标自带 ByteHook 冲突崩溃 | 只 hook Java 层，勿碰 libc |
| 权限弹窗 | 起跑时弹"健身运动权限" | 宿主真授权：`adb shell pm grant com.eg.android.AlipayGphone android.permission.ACTIVITY_RECOGNITION` |

## FAQ

**Q: 为什么我挂上后地图上蓝点不动？**
A: 九成是容器在 sandboxed 子进程，aio_run.py 会自动处理；确认 loader 输出里有两条 `loaded into pid=`。

**Q: 配速显示不达标？**
A: 检查是否改坏了引擎的时间驱动逻辑；`CUMD` 必须按墙钟秒数积分，不能用调用计数。

**Q: 换了脚本想热切换？**
A: 先 `Stop-Process`（或 kill）旧 loader 进程，再重新运行 aio_run.py。频繁 attach/detach 会触发目标自毁。

## License

MIT — 仅限上述授权范围内使用。任何违反免责声明的使用不受本许可保护。
