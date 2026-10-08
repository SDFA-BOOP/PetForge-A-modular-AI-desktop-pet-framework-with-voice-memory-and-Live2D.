# PetForge

**PetForge — An AI voice desktop-pet framework.**

一个可复用的 AI 桌宠框架：**套上任意角色**（Live2D / 立绘 / 精灵图），即可获得 AI 语音对话、长期记忆、动作系统与多端同步。

> **由来**：这个项目最初是为动画角色「小鸟游六花」（《中二病也要谈恋爱！》）（示例）打造的桌宠，
> 后来抽离成通用框架。仓库里保留的默认人设（`persona`）与示例配置仍是六花（示例），可自行替换成任何角色。
>
> 邪王真眼是最强的！QAQ

> 本项目为「框架 + 示例」，训练好的语音模型、API Key、运行时数据等均未包含，需要自行准备。

## 特性

- 🎭 **角色无关**：角色是插件。内置 `register_model` 注册表，Live2D / 图片 / 精灵图 / 分层都能接入，换角色不改核心。
- 💬 **AI 对话**：OpenAI 兼容 API（如 DeepSeek），支持流式输出、人设提示词、情绪与动作。
- 🔊 **语音**：edge-tts 开箱即用；可接到本地 **GPT-SoVITS** 原声（含手机端本地推理）。
- 🧠 **记忆**：短期日志 + 长期摘要 + 每日整理，支持与手机同步。
- 🎬 **动作系统**：AI 可在回复末尾返回 `[动作:xxx]` / `[表情:xxx]`，用户可注册自定义动作。
- 📱 **多端**：电脑端（Python）+ 安卓端（Java/WebView）+ 本地语音引擎（Rust），局域网自动发现与记忆同步。

## 目录结构

```
PetForge/
├── desktop/                 # 电脑端桌宠（Python）
│   ├── main.py              # 入口
│   ├── phone_bridge.py      # 手机桥接服务（局域网 HTTP + UDP 自动发现 + 记忆同步）
│   ├── petforge/            # 核心包（框架内核）
│   ├── character/           # 角色素材目录（需自行放入，见其中 README）
│   ├── user_actions.py      # 用户自定义 AI 动作示例
│   └── config.example.json  # 配置示例（去掉密钥）
├── android/                 # 安卓端桌宠（Java + WebView 源码）
├── engine/                  # 本地 GPT-SoVITS 语音引擎（Rust）
├── voice/                   # 语音接入接口（模型配置模板 + 参数契约）
├── characters/              # 角色素材说明（素材本身不入库）
└── diary/                   # 日记软件（独立，后续单独整理）
```

> 说明：角色素材（Live2D / 立绘）**不随仓库分发**，请按 `characters/README.md` 放入各端目录。

## 技术栈

| 部分 | 语言 / 技术 |
|------|------|
| 电脑端 | Python 3、Tkinter、live2d-py、edge-tts、pygame |
| 安卓端 | Java、JavaScript、HTML/CSS、WebView、PIXI.js、Cubism SDK |
| 语音引擎 | Rust、ONNX Runtime、cargo-ndk、jpreprocess |

## 文档

- [使用说明书 / Live2D 参数绑定 / 自定义动作](docs/MANUAL.md)
- [构建与运行](docs/BUILD.md)

## 快速开始

- 电脑端：见 `docs/BUILD.md` 与 `desktop/requirements.txt`
- 安卓端：见 `docs/BUILD.md`
- 语音引擎：见 `docs/BUILD.md`（需先导出 GPT-SoVITS 模型）

> **语音工具包**：模型请自备——用 [https://github.com/SDFA-BOOP/PetForge-A-modular-AI-desktop-pet-framework-with-voice-memory-and-Live2D./releases/tag/v0.1.0-voice-toolkit] 里的「语音工具包」（音色解析 nalyze_voice.py + 配音服务 gpt_sovits_server.py + 模型导出 xport/）接入你自己的 GPT-SoVITS 模型。

## 给它换个角色

1. 准备角色资源（Live2D `.model3.json` 或立绘 PNG）。
2. 在角色渲染里通过 `register_model` 接入（参考 `desktop/petforge/character/`）。
3. 换掉人设提示词（`persona`）与 `config.json` 里的角色配置即可。

## 一键训练自己的音色模型

PetForge 本身**不训练模型**，训练交给 **GPT-SoVITS 官方整合包**（Windows 免安装，自带 WebUI）。

**1. 准备素材**

- 一段干净的单人语音：建议 **1~5 分钟**，无 BGM / 混响 / 他人声音（wav / mp3 均可）。
- 可选：对应文本（长音频需要切分时用）。

**2. 一键训练（GPT-SoVITS WebUI）**

1. 下载并解压 GPT-SoVITS 整合包，双击 `go-webui.bat` 启动 WebUI。
2. 打开「1-训练」页，用顶部的 **一键三连**：
   - **1A 训练集格式化**：填音频目录 / 清单，选说话人与语言，点「开启一键格式化」。
   - **1B 微调训练**：SoVITS / GPT 轮数用默认值即可，点「开启一键训练」。
3. 训练完成后会得到：
   - `SoVITS_weights/*.pth`
   - `GPT_weights/*.ckpt`
4. 到「1C 推理」页选刚训练的权重 + 一段参考音频试听，确认音色满意。

> 更细的参数说明见 GPT-SoVITS 官方文档 / 整合包内「一键三连」说明。

## 接入自己的音色模型

接入接口只有一个配置文件：**`voice/model_config.example.json`**（参数契约见 `voice/README.md`）。

### 电脑端（HTTP 服务）

1. 复制模板并填写你的模型路径：
   ```bat
   copy voice\model_config.example.json desktop\sovits_config.json
   ```
2. 启动服务：
   ```bat
   python desktop\phone_bridge.py --port 8765
   ```
3. 桌宠设置里「配音后端」选 `gpt_sovits`，地址填服务地址即可。服务提供 `GET /health` 与 `POST /tts`。

### 安卓端（本地 ONNX 推理）

App 需要 5 个 ONNX + 参考音频，放在：

```
android/app/src/main/assets/tts/
```

导出：用 Release「语音工具包」里的 `export/`（即 GPT-SoVITS 的 `export_onnx_v2.py`），把训练的 `.ckpt/.pth` 导出成 KV-cache 版 ONNX。

### 音色解析（可选）

工具包里的 `analyze/analyze_voice.py` 可把参考音频解析成 SSL 内容特征，用于检查 / 调试音色：

```bat
python analyze/analyze_voice.py --ref ref.wav --gpt-sovits E:/GPT-SoVITS --device cuda
```

### 更改配音语言

GPT-SoVITS 的配音语言由合成时的 `text_lang` 参数决定。电脑端支持 **中文 / 日语 / 英语**，手机端引擎支持 **中文（含中英混读）/ 日语 / 粤语**。

#### 电脑端（设置里可直接切换）

在**设置 → 配音 → 配音语言**下拉框切换（对应 `config.json` 的 `tts.language`），可选 `zh` / `ja` / `en`：

| 配音语言 | `tts.language` | 实际 `text_lang` | 说明 |
|----------|----------------|------------------|------|
| 中文 | `zh` | `zh` | 直接用中文合成（默认） |
| 日语 | `ja` | `ja` | 先把回复翻译成日语，再合成 |
| 英语 | `en` | `en` | 先把回复翻译成英语，再合成 |

- **界面显示的文字始终是中文**，只有朗读语言会变。
- 这个设置对 `edge` 和 `gpt_sovits` 两种后端都生效；`edge` 后端会按语言自动选 `voice`（中文）/ `jp_voice`（日语）/ `en_voice`（英语）声线。
- 旧字段 `tts.japanese`（布尔）仍兼容：为 `true` 等价于 `tts.language="ja"`，但 `tts.language` 优先。

#### 安卓端（当前固定为日语）

App 默认「先把中文翻译成日语再合成」，且引擎语言在代码里写死为日语，暂无可切换的 UI。想改成中文配音需改两处：

- `android/app/src/main/assets/web/app.js`：去掉 `translateToJapanese(...)`，直接 `NativeTts.speak(原始中文)`。
- `android/app/src/main/java/com/petforge/live2ddemo/MainActivity.java`：把 `GSV_LANG_JA`（值 `1`）改成中文对应的 `0`（见下表）。

#### 引擎支持的语言代码

`text_lang` / JNI 传入的整型 → `LangId` 映射：

| JNI 值 | `LangId` | 说明 |
|--------|----------|------|
| `0` | `Auto` | 中文（英文按 G2P 混读） |
| `1` | `Ja` | 日语 |
| `2` | `AutoYue` | 粤语 |

> 参考：`engine/gpt-sovits-android/src/text/mod.rs`（`LangId`）与 `engine/gpt-sovits-android/examples/gpt_sovits_demo_jni.rs`（`lang_from_int`）。

#### 接入配置里的默认语言

`voice/model_config.example.json` 的 `tts.text_lang` 用来声明该模型的**推荐 / 默认语言**（示例填的是 `"ja"`），按你模型的实际情况填写即可。

## 界面外观自定义

电脑端的外观可以在**设置 → 界面**里调整，配置写在 `config.json` 顶层：

| 配置项 | 设置里对应 | 说明 |
|--------|------------|------|
| `dark_mode` | 「深色模式」勾选框 | 浅色 / 深色主题 |
| `ui_opacity` | 「窗口透明度（磨砂强度）」滑杆 | `0.78~1.00`，越小越透 |
| `ui_colors` | 「界面配色」各色块 | 逐项覆盖主题颜色，留空 = 用主题默认 |

### 自定义配色 `ui_colors`

在**设置 → 界面 → 界面配色**里，点每行的「选择」挑颜色、「清除」恢复该项默认、「全部恢复默认」一键重置。可覆盖的颜色：

| 键 | 影响 |
|----|------|
| `bg` | 窗口背景 |
| `fg` | 正文文字 |
| `btn_bg` / `btn_fg` | 按钮底色 / 按钮文字 |
| `entry_bg` / `entry_fg` | 输入框底色 / 文字 |
| `user` | 你的昵称与消息颜色 |
| `pet` | 角色昵称与消息颜色 |
| `sys` | 系统提示颜色 |

- 颜色用 `#RRGGBB`（如 `#7c5cff`）；留空即用当前主题（浅色 / 深色）的默认值。
- 深色与浅色模式**共用同一套自定义值**；不想要某个颜色时点「清除」即可。
- 改完点「保存」生效。

## 日记系统

桌宠内置一套**自动日记**：让角色作为**观察者**，用第三人称把「你」一天的日常写进已有的日记文件里。

> **声明**：日记的视角、口吻与称呼**由角色人设（persona）决定**——
> 换一个角色当主角或观察者，写出来的语气、称呼和风格就会随之改变；
> 但无论套上哪个角色、谁来做那个「观察者」，**你始终是这本日记的主角**——
> 记录的是你的经历，角色只是替你把它写下来。

- **角色是观察者，你才是主角**：以六花（示例）为例，正文记录的主角始终是「勇太」（示例）；六花只负责观察、担心、吐槽，或用中二的方式解释一件事，**不会把自己的日常写成主线**。
- **零散片段，不是作文**：每次生成 **4~8 条**按时间顺序排列的短记录，每条以 `HH:MM ` 开头，一件事一条；禁止总起段、过渡、总结、升华、抒情收尾和「这一天……」式串联。
- **只写拿到的事实**：主角统一直呼「勇太」，**禁止用「他」代指勇太（示例）**；不编造材料里没有的重要事实，也不得提及 AI / 模型 / 程序 / API / 日志 / 截图。

### 写入方式

生成的内容会**追加到外部日记软件当天日期文件的末尾**，这也是桌宠与日记软件之间的耦合点：

```
F:\祖传日记\2026年9月13日.txt
```

- 追加时带一行标题，默认是「偷偷在勇太睡觉的时候写的」：

  ```
  【小鸟游六花 · 偷偷在勇太睡觉的时候写的 · 2026年9月13日】
  ```

- 同一日期**只写一次**，靠标题去重；写过的日期不会重复追加。
- 日记目录自动探测：优先读日记软件的设置（`%LOCALAPPDATA%\WinFormsApp2\settings.json`），其次读旧存储指针文件，最后回退到默认目录。

### 触发与补写

- **定时触发**：默认每天 **22:00** 生成当天日记；后台每 30 秒检查一次。
- **启动补写**：程序启动时（约 2.5 秒后）会检查一次——如果昨天漏写，第二天启动时自动补上。`pending_dates()` 返回的正是「昨天未写」加「今天已过 22:00 但未写」的日期。
- **主动触发**：随时可以手动生成——右键菜单里的「📝 写今天的日记」，或界面底部的「📝 写日记」按钮。

### 素材来源

生成时把当天能拿到的材料拼成提示词，交给 AI 整理：

| 素材 | 说明 |
|------|------|
| 当天对话 | 带时间戳的聊天记录（勇太 / 六花）（示例） |
| 视觉观察摘要 | `vision_log` 里每条 **20~40 字**的屏幕观察 |
| 已有日记原文 | 当天 TXT 里你手写的部分（最高优先级事实来源） |
| 记忆摘要 | 当天短记忆 + 近期长期记忆 |

> 视觉观察由 `desktop/petforge/vision_log.py` 负责：每次屏幕读取后，把视觉模型的结果概括成一条 20~40 字的中文短句写进 `vision_log.txt`，再作为日记素材参与生成。

### 配置项

配置在 `config.json` 的 `journal` 段：

| 键 | 默认值 | 说明 |
|----|--------|------|
| `enabled` | `true` | 是否启用自动日记 |
| `time` | `"22:00"` | 每日触发时间 |
| `storage_dir` | `""` | 日记存放目录；留空则自动探测日记软件的设置 |
| `state_path` | `"journal_state.json"` | 去重状态文件 |
| `heading_note` | `"偷偷在勇太睡觉的时候写的"` | 追加标题里的那句话 |
| `max_context_chars` | `8000` | 拼给 AI 的上下文字符上限 |

### 目录与接口现状

- 生成逻辑：`desktop/petforge/journal_writer.py`（`JournalWriter`）。
- 视觉观察：`desktop/petforge/vision_log.py`（`VisionLog`）。
- `diary/` 目录**暂时是占位**——它规划为与桌宠解耦的独立「日记软件」（文字编辑、日期文件、自动保存、深色模式等），后续单独整理。

## 相关视频

- [演示视频 1](https://www.bilibili.com/video/BV1Teec6BE7q/)
- [演示视频 2](https://www.bilibili.com/video/BV1iubn6ZEnv/)
- [演示视频 3](https://www.bilibili.com/video/BV1VwtJ6DEmf/)

## 许可说明

- 本项目源码按仓库根目录 `LICENSE` 许可（默认 MIT）。
- `android/.../assets/web/lib/` 中的第三方库（PIXI.js / Cubism SDK / OpenCV.js 等）遵循各自原始许可，请自行确认后商用。
- 角色素材不随仓库分发；若你自行添加素材，请确认其版权许可。
