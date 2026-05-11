# 演示视频录制指南

> 录前 30 分钟把整个清单过一遍。一次录失败重来 = 半小时没了。

---

## 一、设备 & 软件

### 必备
- **录屏**：OBS Studio（免费，跨平台）—— 推荐
- **替代**：Loom（在线，自动生成 transcript）/ ScreenStudio（Mac，自动 zoom）
- **麦克风**：USB 电容麦（罗技 Yeti / 铁三角 AT2020）；笔电内置麦也能用但音质差一档
- **耳机**：监听用，别用蓝牙（延迟）
- **第二屏幕**：放脚本和 setlist，不入镜

### 不必要的
- 摄像头（人脸出镜对企业 Demo 帮助不大，省事）
- 灯光（屏幕录制用不上）

---

## 二、OBS 配置参数

打开 Settings：

### Output
- **Output Mode**: Advanced
- **Recording Format**: MP4
- **Encoder**: x264（CPU 够强）/ NVENC H.264（NVIDIA 显卡）
- **Rate Control**: CBR
- **Bitrate**: 8000 Kbps（1080p 足够）
- **Audio Track**: 1
- **Audio Bitrate**: 192 Kbps
- **Recording Path**: 单独建一个文件夹，方便清理

### Video
- **Base (Canvas) Resolution**: 1920×1080
- **Output (Scaled) Resolution**: 1920×1080
- **FPS**: 30（演示视频不需要 60）

### Audio
- **Sample Rate**: 48 kHz
- **Channels**: Stereo
- 在 Filters 给麦克风加：
  - Noise Suppression（RNNoise，免费内置）
  - Compressor（ratio 4:1, threshold -18dB）
  - Gain（+3 ~ +6dB 视麦灵敏度）

### Hotkeys
- **Start Recording**: `Ctrl+Shift+R`
- **Stop Recording**: `Ctrl+Shift+S`
- **Pause Recording**: `Ctrl+Shift+P`（演示中如要"暂停整理思路"用得上）

---

## 三、浏览器准备

1. 关闭所有其他 tab，只留 ERP OS
2. **隐身模式**（避免 Chrome 收藏栏 / 历史记录入镜）
3. **窗口最大化**，不要全屏（全屏会隐藏标签和地址栏，但全屏后 mouse position 录制可能漂移）
4. **缩放 100%**（`Ctrl+0` 复位）
5. 开发者工具 / extension 全关
6. 检查地址栏：用 `https://erp-demo.example.my` 而不是 `localhost:3000`（更专业）

---

## 四、Demo 数据预热

**录制前 1 小时执行：**

```bash
# 1. Reset demo data（如果不是凌晨 3am 自动跑过的话）
ssh demo-server "docker compose exec backend celery -A app.tasks.celery_app call app.tasks.demo_reset.demo_reset_nightly"
# 或本地：
docker compose exec backend python -c "from app.services.demo_reset import run_demo_reset; run_demo_reset()"

# 2. 用 admin 登录一次，让 Dashboard 缓存预热
curl -X POST https://erp-demo.example.my/api/auth/login \
  -d '{"email":"admin@demo.my","password":"Admin@123"}'

# 3. 触发一次 AI 日报生成
curl -X POST https://erp-demo.example.my/api/dashboard/ai-summary/refresh \
  -H "Authorization: Bearer $TOKEN"

# 4. 浏览器打开几个关键页，让 React 路由预加载
#    Dashboard / SKU / Purchase Orders / Sales Orders / Branch Inventory
```

**录制前 5 分钟检查清单**：
- [ ] Dashboard KPI 数字真实（不全是 0）
- [ ] AI 日报卡片有内容（不是 "Loading..."）
- [ ] 至少 1 张 PO 在 CONFIRMED 状态可演示 GR
- [ ] 至少 1 张 SO 在 CONFIRMED 可演示 DO + Invoice
- [ ] 至少 1 张 invoice 在 FINAL 状态可演示 Credit Note
- [ ] OCR 测试用的 sample invoice PDF 放桌面，路径短

---

## 五、关闭通知干扰

### Windows
- `Win+A` → 打开 Focus Assist → "Alarms only"
- 关闭 Slack / WeChat / Discord / 钉钉
- 邮件客户端关掉（Outlook / Mail）
- 任务栏右下角通知图标全清

### macOS
- 控制中心 → Do Not Disturb → 开
- 关掉 Slack / WeChat / 邮件

### 都要做
- 手机静音 + 翻面
- 路由器旁边的人发消息一律忽略

---

## 六、屏幕分辨率提醒

如果用 4K 屏录制，OBS 输出 1080p 会缩放，文字依然清晰。但要注意：
- 鼠标指针会变小 → OBS 设置 → Cursor → Highlight Cursor（黄圈跟随）
- 字体如果太小，可以临时把浏览器 zoom 调到 110%（不要超过，超了 Layout 会乱）

---

## 七、录制流程

### 单段录制（推荐新手）
- 按脚本分段录，每段 30s-2min
- 录砸了立即重录这一段（不要手抖去 stop 整段）
- 后期用 DaVinci Resolve / Premiere 拼接

### 一镜到底（适合熟练后）
- 完整跑 5min / 15min
- 容许 1-2 处小失误（后期 cut 掉那 5 秒）
- 优点：自然流畅，听众感觉真实

---

## 八、后期剪辑要点

### 必做
- 删头（按 Record 到开始说话之间的 3-5 秒）
- 删尾（说完最后一句到按 Stop 之间）
- 切掉明显失误（误点 / 长时间 loading）

### 锦上添花
- 章节标记（YouTube / Bilibili 的 Chapter）
- 数字字幕（"5 秒" / "72 小时" / "RM 60K" 出现时叠加 lower-third）
- 重点操作 2x 慢放（OCR 进度条 / Precheck 弹窗 / 倒计时）
- 背景音乐（Epidemic Sound / YouTube Audio Library 找轻商务风，音量 -25dB）
- 片头片尾 logo（3 秒 + 5 秒）

### 工具推荐
- **DaVinci Resolve**（免费版功能足够）—— 跨平台
- **CapCut**（免费）—— 简单快速，AI 字幕生成准
- **Premiere Pro**（付费）—— 专业但要订阅

---

## 九、上传 & 分发

### 主仓
- **YouTube**（公开 / unlisted 都行）—— 国际客户
- **Bilibili**（unlisted）—— 中国 / 港台客户
- **Vimeo**（无广告，付费版可定制播放器）—— 嵌 landing page

### 备份
- Google Drive / Dropbox（直接发链接）
- 本地 NAS（演示当天宽带挂了的兜底）

### Setlist 必带
- 录制原始 mp4 + 1080p 压缩版 + 720p 压缩版 各一份
- 字幕文件 .srt（YouTube 自动生成后下载校对）
- 封面图 1280×720（用 Canva 5 分钟搞定）

---

## 十、常见翻车 & 应对

| 现象 | 原因 | 解决 |
|---|---|---|
| 录完没声音 | OBS 没选对 Audio Source | Settings → Audio → Mic/Auxiliary Audio 选对设备 |
| 视频卡顿 | CPU 编码跟不上 / 磁盘写入慢 | 降到 720p 录 / 用 NVENC / 录到 SSD |
| 鼠标看不清 | 默认指针太小 | OBS Cursor → Highlight |
| 中文字体糊 | 录制源缩放问题 | OBS Output Resolution 跟 Base 一致 |
| Demo 数据不对 | reset 没跑成 / 缓存旧 | 强制 reset + clear Redis |
| 浏览器弹更新 | Chrome 自动升级 | 录前 Chrome → About → 升完再录 |

---

## 十一、演示视频版本管理

录完后建议命名规范：

```
demo/videos/recordings/
├── 5min-en-v1-2026-05-12.mp4
├── 5min-zh-v1-2026-05-12.mp4
├── 15min-en-v1-2026-05-12.mp4
├── 15min-zh-v1-2026-05-12.mp4
└── archive/                  # 历史版本
```

**重大功能更新后重录**（约每季度一次），旧版本归档不删。
